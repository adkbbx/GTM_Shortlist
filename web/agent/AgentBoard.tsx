import { useCallback, useEffect, useRef, useState } from 'react';
import { SiteIcon } from '../SiteIcon';
import { Assumptions } from './Assumptions';
import { CountPicker } from './CountPicker';
import { EarlySteps, Feed, Monitor, Working } from './AgentLive';
import { EvidenceList, QuoteBlock } from './Evidence';
import { agentApi, domainOf, editToken, isActive } from './agent-api';
import { AgentConfigContext, countOptions, useAgentConfig } from './agent-config';
import type { AgentEvent, AgentRun, AgentRunView, Company, EvidenceItem, Overrides, Profile } from './agent-api';

const describe = (error: unknown) => error instanceof Error ? error.message : 'Something went wrong. Please try again.';
const COLUMNS = [
  { kind: 'shortlisted', title: 'Shortlisted', empty: 'No company has every required check yet.' },
  { kind: 'needs_look', title: 'Needs a look', empty: 'Nothing here.' },
  { kind: 'rejected', title: 'Rejected', empty: 'Nothing rejected.' },
] as const;

function checkNamer(run: AgentRun) {
  const profile = run.profile;
  const names = new Map<string, string>();
  for (const criterion of profile?.fit_criteria ?? []) names.set(criterion.id, criterion.text);
  for (const signal of [...profile?.need_signals ?? [], ...profile?.timing_signals ?? []]) names.set(signal.id, signal.text);
  for (const rule of run.disqualifiers) names.set(rule.id, rule.text);
  return (item: EvidenceItem) => names.get(item.criterion_id) ?? item.claim;
}

/** What keeps a company from Shortlisted, with unreadable pages folded into one line (a live card listed five 404s). */
function Missing({ items }: { items: string[] }) {
  const unread = items.filter(item => item.startsWith('Could not read '));
  const gaps = items.filter(item => !item.startsWith('Could not read '));
  return <div className="agent-missing">
    <p>What is missing</p>
    {gaps.length > 0 && <ul>{gaps.map(item => <li key={item}>{item}</li>)}</ul>}
    {unread.length > 0 && <details className="agent-unread">
      <summary>Could not read {unread.length} {unread.length === 1 ? 'page' : 'pages'}</summary>
      <ul>{unread.map(item => <li key={item}>{item.replace(/^Could not read /, '')}</li>)}</ul>
    </details>}
  </div>;
}

/** A post about a finished board, with its read-only link; nothing is posted until the visitor does it on X. */
function ExportLink({ run }: { run: AgentRun }) {
  return <a className="agent-share" href={`/api/agent/runs/${run.id}/shortlist.csv`} download>Download CSV</a>;
}

function useCopy() {
  const [copied, setCopied] = useState('');
  const copy = async (key: string, text: string) => {
    try { await navigator.clipboard.writeText(text); setCopied(key); window.setTimeout(() => setCopied(''), 2000); } catch { setCopied(''); }
  };
  return { copied, copy };
}

/** The opening line, for a viewer who cannot draft the email (a shared link). Why now is already the row's summary
    line, and the person who ran the search gets the whole email from Draft outreach instead. */
function PitchBlock({ pitch }: { pitch: NonNullable<Company['pitch']> }) {
  const { copied, copy } = useCopy();
  return <section className="agent-pitch" aria-label="Opening line">
    <p className="agent-pitch-label">Opening line</p>
    <blockquote className="agent-pitch-opener">{pitch.opener}</blockquote>
    <div className="agent-pitch-foot">
      <button type="button" className="agent-small-button" onClick={() => copy('opener', pitch.opener)}>{copied ? 'Copied' : 'Copy opening line'}</button>
      {pitch.checked && <span>✓ Checked against the quotes</span>}
    </div>
  </section>;
}

/** The outreach email in a dialog: opens at once on Draft outreach, shows that it is writing, then the email. */
export function EmailDialog({ company, open, drafting, error, onClose }: { company: Company; open: boolean; drafting: boolean; error: string;
  onClose: () => void }) {
  const dialog = useRef<HTMLDialogElement>(null);
  const { copied, copy } = useCopy();
  useEffect(() => {
    const node = dialog.current;
    if (!node) return;
    if (open && !node.open) node.showModal();
    if (!open && node.open) node.close();
  }, [open]);
  const email = company.outreach;
  const mail = email ? `mailto:?${new URLSearchParams({ subject: email.subject, body: email.body }).toString().replace(/\+/g, '%20')}` : '';
  return <dialog ref={dialog} className="agent-dialog" aria-label="Outreach email" onClose={onClose}
    onClick={event => { if (event.target === dialog.current) onClose(); }}>
    <header className="agent-dialog-head">
      <SiteIcon lookup domain={company.domain} fallback={(company.name || company.domain).slice(0, 1).toUpperCase()} className="agent-logo agent-row-logo" />
      <div><p>Outreach email</p><h2>{company.name || company.domain}</h2></div>
      <button type="button" className="agent-dialog-close" aria-label="Close" onClick={onClose}>
        <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true"><path d="m7 7 10 10M17 7 7 17" /></svg></button>
    </header>
    {email ? <div className="agent-dialog-body">
      <p className="agent-dialog-label">Subject</p>
      <p className="agent-email-subject">{email.subject}</p>
      <div className="agent-email-body">{email.body}</div>
      <footer className="agent-dialog-foot">
        <button type="button" onClick={() => copy('email', `Subject: ${email.subject}\n\n${email.body}`)}>{copied ? 'Copied' : 'Copy email'}</button>
        <a className="agent-dialog-link" href={mail}>Open in mail app</a>
        {email.checked && <span className="agent-dialog-checked">✓ Checked against the quotes</span>}
      </footer>
    </div> : error ? <div className="agent-dialog-body"><p className="notice" role="alert">{error}</p></div>
      : <div className="agent-dialog-body agent-dialog-wait" role="status">
        <p><span className="agent-spinner" aria-hidden="true" />{drafting ? 'Writing from the quotes the skeptic accepted' : 'Starting'}</p>
        <span className="agent-skeleton" /><span className="agent-skeleton" /><span className="agent-skeleton short" />
      </div>}
  </dialog>;
}

const VERDICT = { shortlisted: 'Shortlisted', needs_look: 'Needs a look', rejected: 'Rejected' } as const;

/** One line on why the company sits where it does. */
function reasonOf(company: Company) {
  const verdict = company.verdict!;
  if (verdict.kind === 'shortlisted') return company.pitch?.why_now ?? verdict.summary;
  if (verdict.kind === 'rejected') return verdict.summary;
  return verdict.missing.find(item => !item.startsWith('Could not read ')) ?? verdict.missing[0] ?? 'Needs a look';
}

/** The agent's own steps for this company, in order. */
function Trace({ events }: { events: AgentEvent[] }) {
  if (!events.length) return null;
  return <details className="agent-trace">
    <summary>How the agent checked this ({events.length} {events.length === 1 ? 'step' : 'steps'})</summary>
    <ol>{events.map(event => <li key={event.seq} className={`level-${event.level}`}>
      <span className={`agent-log-tag stage-${event.stage}`}>{event.stage === 'investigation' ? 'Investigate' : event.stage}</span>
      <span>{event.message}</span>
    </li>)}</ol>
  </details>;
}

function CompanyRow({ company, run, events, runId, onUpdate }: { company: Company; run: AgentRun; events: AgentEvent[]; runId: string;
  onUpdate: (view: AgentRunView) => void }) {
  const { editable } = useAgentConfig();
  const verdict = company.verdict!;
  const [open, setOpen] = useState(false);
  const [drafting, setDrafting] = useState(false);
  const [error, setError] = useState('');
  const [mailOpen, setMailOpen] = useState(false);
  const headingId = `company-${company.domain.replace(/\W+/g, '-')}`;
  const panelId = `${headingId}-details`;
  const draft = async () => {
    setMailOpen(true);
    if (company.outreach || drafting) return;
    setDrafting(true); setError('');
    try {
      const next = await agentApi.outreach(runId, company.domain);
      onUpdate(next);
      if (!next.run.companies.find(c => c.domain === company.domain)?.outreach)
        setError('No email this time: nothing it wrote could be checked against the quotes.');
    } catch (reason) { setError(describe(reason)); } finally { setDrafting(false); }
  };
  const mine = events.filter(event => event.company === company.domain);
  return <article className={`agent-row verdict-${verdict.kind}${open ? ' is-open' : ''}`} aria-labelledby={headingId}>
    <div className="agent-row-main">
      <SiteIcon lookup domain={company.domain} fallback={(company.name || company.domain).slice(0, 1).toUpperCase()} className="agent-logo agent-row-logo" />
      <div className="agent-row-text">
        <div className="agent-row-title"><h3 id={headingId}>{company.name || company.domain}</h3>
          <span className={`agent-verdict-pill pill-${verdict.kind}`}>{VERDICT[verdict.kind]}</span></div>
        <p className="agent-row-reason">{reasonOf(company)}</p>
      </div>
      <div className="agent-row-actions">
        {verdict.kind === 'shortlisted' && company.outreach && <button type="button" className="agent-expand" onClick={draft}>View email</button>}
        {verdict.kind === 'shortlisted' && editable && !company.outreach && <button type="button" className="agent-draft" onClick={draft}
          aria-busy={drafting}>{drafting ? 'Drafting' : 'Draft outreach'}</button>}
        <button type="button" className="agent-expand" aria-expanded={open} aria-controls={panelId} onClick={() => setOpen(value => !value)}>
          {open ? 'Hide' : 'Details'}<span aria-hidden="true" className="agent-expand-mark" /></button>
      </div>
    </div>
    <div id={panelId} className="agent-row-panel" hidden={!open}>
      <p className="agent-row-site"><a href={company.url} target="_blank" rel="noopener noreferrer">{company.domain}</a></p>
      {verdict.kind === 'shortlisted' && company.pitch && !editable && !company.outreach && <PitchBlock pitch={company.pitch} />}
      {verdict.kind === 'shortlisted' && (verdict.unconfirmed ?? []).length > 0 && <div className="agent-unconfirmed">
        <p>Check before you reach out</p>
        <ul>{verdict.unconfirmed!.map(item => <li key={item}>{item}</li>)}</ul>
      </div>}
      {verdict.kind === 'shortlisted' && <p className="agent-card-summary">{verdict.summary}</p>}
      {verdict.kind === 'rejected' && <div className="agent-reason">
        <p>{verdict.summary}</p>
        {verdict.disqualifier && <QuoteBlock quote={verdict.disqualifier.quote} />}
      </div>}
      {verdict.kind === 'needs_look' && <Missing items={verdict.missing} />}
      <EvidenceList company={company} checkName={checkNamer(run)} />
      {company.checked_places.length > 0 && <p className="agent-checked"><span>Checked for competitors:</span> {company.checked_places.join(', ')}</p>}
      {company.found_via && <p className="agent-checked"><span>Found by:</span> {company.found_via}</p>}
      <Trace events={mine} />
    </div>
    <EmailDialog company={company} open={mailOpen} drafting={drafting} error={error} onClose={() => setMailOpen(false)} />
  </article>;
}

function Columns({ run, events, apply, busy, onUpdate }: { run: AgentRun; events: AgentEvent[]; apply: (overrides: Overrides) => void; busy: boolean;
  onUpdate: (view: AgentRunView) => void }) {
  const { editable, maxCompanies } = useAgentConfig();
  const decided = run.companies.filter(company => company.verdict);
  const working = run.companies.filter(company => !company.verdict);
  return <section className="agent-results" aria-labelledby="results-heading">
    <div className="agent-section-head agent-results-head">
      <div><h2 id="results-heading">Companies</h2></div>
      {editable && <CountPicker label="Shortlist" value={run.company_count} options={countOptions(maxCompanies, run.company_count)}
        disabled={busy || isActive(run.status)} onChange={count => apply({ company_count: count })} />}
    </div>
    <Working companies={working} events={events} />
    <div className="agent-groups">
      {COLUMNS.map(column => {
        const companies = decided.filter(company => company.verdict!.kind === column.kind);
        if (!companies.length && column.kind !== 'shortlisted') return null;
        return <section key={column.kind} className={`agent-group column-${column.kind}`} aria-labelledby={`column-${column.kind}`}>
          <h3 id={`column-${column.kind}`} className="agent-column-title">{column.title}<span className="agent-count">{companies.length}</span></h3>
          {companies.length ? companies.map(company => <CompanyRow key={company.domain} company={company} run={run} events={events} runId={run.id} onUpdate={onUpdate} />)
            : <p className="agent-empty">{working.length ? 'Waiting for results.' : column.empty}</p>}
        </section>;
      })}
    </div>
  </section>;
}

/** What we assumed: open while there are no companies to show, then out of the way unless you open it. */
function Assumed({ run, apply, busy }: { run: AgentRun; apply: (overrides: Overrides) => void; busy: boolean }) {
  const [chosen, setChosen] = useState<boolean | null>(null);
  const open = chosen ?? run.companies.length === 0;
  return <details className="agent-assumed" open={open}>
    <summary onClick={event => { event.preventDefault(); setChosen(!open); }}>
      <span>What we assumed about {domainOf(run.website)}</span><small>{run.profile?.offer?.value}</small></summary>
    <Assumptions run={run} apply={apply} busy={busy} />
  </details>;
}

function ReadingChoice({ profile, apply, busy }: { profile: Profile; apply: (overrides: Overrides) => void; busy: boolean }) {
  const { editable } = useAgentConfig();
  return <section className="agent-choice" aria-labelledby="choice-heading">
    <h2 id="choice-heading">Which reading is closest?</h2>
    <p>Your site can be read more than one way. Pick the closest; there is nothing to type.</p>
    <div className="agent-readings">
      {profile.interpretations.map(reading => <button key={reading.id} type="button" className="agent-reading" disabled={busy || !editable}
        onClick={() => apply({ interpretation: reading.id })}>
        <strong>{reading.offer}</strong><span>for {reading.buyer}</span><small>From your site: “{reading.quotes[0]?.text}”</small>
      </button>)}
    </div>
    {editable && <Describe apply={apply} busy={busy} summary="None of these? Describe it yourself (optional)" />}
  </section>;
}

function Describe({ apply, busy, summary }: { apply: (overrides: Overrides) => void; busy: boolean; summary: string }) {
  const [offer, setOffer] = useState('');
  const [buyer, setBuyer] = useState('');
  return <details className="agent-add agent-describe">
    <summary>{summary}</summary>
    <form onSubmit={event => { event.preventDefault(); apply({ offer: offer.trim(), buyer: buyer.trim() }); }}>
      <label htmlFor="describe-offer">What you sell</label>
      <input id="describe-offer" value={offer} maxLength={600} onChange={event => setOffer(event.target.value)} />
      <label htmlFor="describe-buyer">Which companies buy it</label>
      <input id="describe-buyer" value={buyer} maxLength={600} onChange={event => setBuyer(event.target.value)} />
      <button type="submit" disabled={busy || offer.trim().length < 3 || buyer.trim().length < 3}>Continue</button>
    </form>
  </details>;
}

export function AgentBoard({ runId, onNew }: { runId: string; onNew: () => void }) {
  const config = useAgentConfig();
  // In the public demo only the browser that started a search holds its edit token; a shared link is read-only.
  const editable = !config.publicDemo || Boolean(editToken(runId));
  const [view, setView] = useState<AgentRunView | null>(null);
  const [events, setEvents] = useState<AgentEvent[]>([]);
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);
  const [retry, setRetry] = useState(0);
  const [feedOpen, setFeedOpen] = useState(false);
  const lastSeq = useRef(0);
  const heading = useRef<HTMLHeadingElement>(null);
  const load = useCallback(async () => {
    const next = await agentApi.run(runId);
    setView(next); setEvents(next.events); lastSeq.current = next.events.at(-1)?.seq ?? 0; setError('');
    return next;
  }, [runId]);
  useEffect(() => { load().catch(reason => setError(describe(reason))); }, [load]);
  const focused = useRef(false);
  const loaded = view !== null;
  useEffect(() => {
    // Move focus to the run's heading once, when it first appears, so keyboard and screen-reader users land on it.
    if (loaded && !focused.current) { focused.current = true; heading.current?.focus(); }
  }, [loaded]);
  const active = view ? isActive(view.status) : false;
  useEffect(() => {
    if (!active) return;
    let closed = false;
    let timer: number | undefined;
    const refresh = () => { window.clearTimeout(timer); timer = window.setTimeout(() => { void load().catch(() => undefined); }, 250); };
    const stop = agentApi.follow(runId, lastSeq.current, event => {
      lastSeq.current = Math.max(lastSeq.current, event.seq);
      setEvents(old => old.some(item => item.seq === event.seq) ? old : [...old, event]);
      refresh();
    }, () => {
      if (closed) return;
      void load().then(next => { if (!closed && isActive(next.status)) timer = window.setTimeout(() => setRetry(value => value + 1), 1000); })
        .catch(() => { if (!closed) timer = window.setTimeout(() => setRetry(value => value + 1), 2000); });
    });
    return () => { closed = true; stop(); window.clearTimeout(timer); };
  }, [runId, active, retry, load]);

  const apply = async (overrides: Overrides) => {
    setSaving(true); setError('');
    try {
      const next = await agentApi.override(runId, overrides);
      setView(next); setEvents(next.events); lastSeq.current = next.events.at(-1)?.seq ?? 0;
    } catch (reason) { setError(describe(reason)); } finally { setSaving(false); }
  };

  if (!view) return <div className="agent-board">{error ? <p className="notice" role="alert">{error}</p> : <p className="agent-status" role="status">Loading the run</p>}</div>;
  const run = view.run;
  const busy = saving || active;
  return <AgentConfigContext.Provider value={{ ...config, editable }}><div className="agent-board">
    <div className="agent-board-head">
      <div><p className="agent-eyebrow">Shortlist for</p>
        <div className="agent-title"><SiteIcon lookup domain={domainOf(run.website)} fallback={domainOf(run.website).slice(0, 1).toUpperCase()} className="agent-logo agent-title-logo" />
          <h1 ref={heading} tabIndex={-1}>{domainOf(run.website)}</h1></div>
        {!editable && <p className="agent-shared" role="note">You are viewing a shared shortlist. Read only.</p>}</div>
      <div className="agent-board-actions">
        {run.status === 'complete' && <ExportLink run={run} />}
        <button type="button" className="secondary" onClick={onNew}>New search</button>
      </div>
    </div>
    {run.synthetic && <p className="notice agent-synthetic" role="note"><strong>Synthetic test data.</strong> Invented companies on reserved .example domains. Nothing was searched or fetched.</p>}
    <Monitor view={view} events={events} feedOpen={feedOpen} onFeed={() => setFeedOpen(open => !open)} />
    {error && <p className="notice" role="alert">{error}</p>}
    <div className="agent-board-grid"><div className="agent-board-main">
    {active && run.companies.length === 0 && <EarlySteps run={run} events={events} />}
    {view.status === 'failed' && <section className="notice agent-failed" role="alert"><p>{run.error ?? 'The run stopped.'}</p>
      {/* Only a site too vague to read: a provider failure has no profile, and typing would not fix it. */}
      {run.profile && !run.profile.offer && editable && <Describe apply={apply} busy={busy} summary="Describe your offer and buyer (optional)" />}</section>}
    {view.status === 'needs_choice' && run.profile && <ReadingChoice profile={run.profile} apply={apply} busy={busy} />}
    {run.companies.length > 0 && <Columns run={run} events={events} apply={apply} busy={busy} onUpdate={next => { setView(next); setEvents(next.events); lastSeq.current = next.events.at(-1)?.seq ?? 0; }} />}
    {run.profile && view.status !== 'needs_choice' && run.profile.offer && <Assumed run={run} apply={apply} busy={busy} />}
    </div><Feed events={events} open={feedOpen} onClose={() => setFeedOpen(false)} live={active} /></div>
  </div></AgentConfigContext.Provider>;
}
