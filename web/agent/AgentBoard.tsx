import { useCallback, useEffect, useRef, useState } from 'react';
import { Assumptions } from './Assumptions';
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

function CompanyCard({ company, run }: { company: Company; run: AgentRun }) {
  const verdict = company.verdict!;
  const headingId = `company-${company.domain.replace(/\W+/g, '-')}`;
  return <article className={`agent-card verdict-${verdict.kind}`} aria-labelledby={headingId}>
    <header className="agent-card-head">
      <h3 id={headingId}>{company.name || company.domain}</h3>
      <a href={company.url} target="_blank" rel="noopener noreferrer">{company.domain}</a>
    </header>
    {verdict.kind === 'rejected' && <div className="agent-reason">
      <p>{verdict.summary}</p>
      {verdict.disqualifier && <QuoteBlock quote={verdict.disqualifier.quote} />}
    </div>}
    {verdict.kind === 'needs_look' && <Missing items={verdict.missing} />}
    {verdict.kind === 'shortlisted' && <p className="agent-card-summary">{verdict.summary}</p>}
    <EvidenceList company={company} checkName={checkNamer(run)} />
    {company.checked_places.length > 0 && <p className="agent-checked"><span>Checked for competitors:</span> {company.checked_places.join(', ')}</p>}
    {company.found_via && <p className="agent-checked"><span>Found by:</span> {company.found_via}</p>}
  </article>;
}

function Columns({ run, apply, busy }: { run: AgentRun; apply: (overrides: Overrides) => void; busy: boolean }) {
  const { editable, maxCompanies } = useAgentConfig();
  const decided = run.companies.filter(company => company.verdict);
  const working = run.companies.filter(company => !company.verdict);
  return <section className="agent-results" aria-labelledby="results-heading">
    <div className="agent-section-head agent-results-head">
      <div><h2 id="results-heading">Companies</h2>
        <p>{decided.length} of {run.companies.length} checked. Verdicts are decided by fixed rules over quotes the skeptic accepted.</p></div>
      {editable && <label className="agent-count-control">Research up to
        <select value={run.company_count} disabled={busy || isActive(run.status)} onChange={event => apply({ company_count: Number(event.target.value) })}>
          {countOptions(maxCompanies, run.company_count).map(count => <option key={count} value={count}>{count} companies</option>)}
        </select>
      </label>}
    </div>
    {working.length > 0 && <p className="agent-working" role="status"><span className="agent-pulse" aria-hidden="true" />Investigating {working.map(c => c.domain).join(', ')}</p>}
    <div className="agent-columns">
      {COLUMNS.map(column => {
        const companies = decided.filter(company => company.verdict!.kind === column.kind);
        return <section key={column.kind} className={`agent-column column-${column.kind}`} aria-labelledby={`column-${column.kind}`}>
          <h3 id={`column-${column.kind}`} className="agent-column-title">{column.title}<span className="agent-count">{companies.length}</span></h3>
          {companies.length ? companies.map(company => <CompanyCard key={company.domain} company={company} run={run} />)
            : <p className="agent-empty">{working.length ? 'Waiting for results.' : column.empty}</p>}
        </section>;
      })}
    </div>
  </section>;
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

function StatusLine({ view, events }: { view: AgentRunView; events: AgentEvent[] }) {
  const run = view.run;
  const latest = events.at(-1);
  const counts = COLUMNS.map(column => `${run.companies.filter(c => c.verdict?.kind === column.kind).length} ${column.title.toLowerCase()}`);
  const text = isActive(view.status) ? latest?.message ?? 'Starting'
    : view.status === 'needs_choice' ? 'Waiting for your choice'
      : view.status === 'failed' ? 'Stopped' : `Done: ${counts.join(', ')}`;
  return <p className={`agent-status status-${view.status}`} role="status" aria-live="polite">
    {isActive(view.status) && <span className="agent-pulse" aria-hidden="true" />}
    <span>{text}</span>
  </p>;
}

function Activity({ events }: { events: AgentEvent[] }) {
  if (!events.length) return null;
  return <details className="agent-log">
    <summary>Activity ({events.length} steps)</summary>
    <ol>{[...events].reverse().slice(0, 60).map(event => <li key={event.seq} className={`level-${event.level}`}>
      <time dateTime={event.at}>{new Intl.DateTimeFormat(undefined, { timeStyle: 'medium' }).format(new Date(event.at))}</time>
      <span>{event.company ? `${event.company}: ` : ''}{event.message}</span>
    </li>)}</ol>
  </details>;
}

function Transparency({ run }: { run: AgentRun }) {
  if (!run.dropped.length && !run.set_aside.length) return null;
  return <section className="agent-transparency" aria-label="What was left out">
    {run.dropped.length > 0 && <details>
      <summary>{run.dropped.length} model {run.dropped.length === 1 ? 'claim was' : 'claims were'} left out: the quote was not on the page</summary>
      <ul>{run.dropped.map((item, index) => <li key={index}>{item.company ? `${item.company}, ` : ''}{item.stage} ({item.claim_type}): {item.reason}</li>)}</ul>
    </details>}
    {run.set_aside.length > 0 && <details>
      <summary>{run.set_aside.length} search {run.set_aside.length === 1 ? 'result was' : 'results were'} set aside</summary>
      <ul>{run.set_aside.map(item => <li key={item.domain}>{item.domain}: {item.reason}
        {item.previous_run && <> · <a href={`?agent=${item.previous_run}`}>open that search</a></>}</li>)}</ul>
    </details>}
  </section>;
}

function Telemetry({ run }: { run: AgentRun }) {
  const t = run.telemetry;
  const models = [...new Set(t.calls.map(call => `${call.provider} ${call.model}`))];
  return <footer className="agent-telemetry">
    <p><strong>${t.cost_usd.toFixed(3)}</strong> estimated of ${t.budget_usd.toFixed(2)} budget
      <span>{(t.elapsed_ms / 1000).toFixed(1)} s</span><span>{t.model_calls} model calls</span>
      <span>{t.searches} searches</span><span>{t.pages_fetched} pages read</span>
      {t.budget_reached && <span className="agent-budget">Budget reached</span>}</p>
    {models.length > 0 && <p className="agent-models">Models: {models.join(' · ')}{run.skeptic ? '' : ' · run without the skeptic'}</p>}
  </footer>;
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
      <div><p className="agent-eyebrow">Shortlist for</p><h1 ref={heading} tabIndex={-1}>{domainOf(run.website)}</h1></div>
      <button type="button" className="secondary" onClick={onNew}>New search</button>
    </div>
    {!editable && <p className="notice agent-shared" role="note">You are viewing a shared shortlist. Start your own search to change its assumptions.</p>}
    {run.synthetic && <p className="notice agent-synthetic" role="note"><strong>Synthetic test data.</strong> Invented companies on reserved .example domains. Nothing was searched or fetched.</p>}
    <StatusLine view={view} events={events} />
    {error && <p className="notice" role="alert">{error}</p>}
    {view.status === 'failed' && <section className="notice agent-failed" role="alert"><p>{run.error ?? 'The run stopped.'}</p>
      {/* Only a site too vague to read: a provider failure has no profile, and typing would not fix it. */}
      {run.profile && !run.profile.offer && editable && <Describe apply={apply} busy={busy} summary="Describe your offer and buyer (optional)" />}</section>}
    {view.status === 'needs_choice' && run.profile && <ReadingChoice profile={run.profile} apply={apply} busy={busy} />}
    {run.profile && view.status !== 'needs_choice' && run.profile.offer && <Assumptions run={run} apply={apply} busy={busy} />}
    {run.companies.length > 0 && <Columns run={run} apply={apply} busy={busy} />}
    <Transparency run={run} />
    <Activity events={events} />
    <Telemetry run={run} />
  </div></AgentConfigContext.Provider>;
}
