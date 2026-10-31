import { useEffect, useRef, useState } from 'react';
import type { FormEvent } from 'react';
import '@fontsource/schibsted-grotesk/800.css';
import { clearKeptCompany, peekKeptCompany } from '../landing/kept-company';
import { turnstileToken } from '../landing/turnstile';
import { STAGES, Stepper, prefixOf, stageOf, stepStates } from './AgentLive';
import { agentApi, domainOf } from './agent-api';
import type { AgentRunSummary, AgentRunView, Company } from './agent-api';
import { countOptions, useAgentConfig } from './agent-config';
import './agent-landing.css';

const describe = (error: unknown) => error instanceof Error ? error.message : 'Something went wrong. Please try again.';
const day = (value: string) => new Date(value).toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' });

function useReducedMotion() {
  const [reduced, setReduced] = useState(() => window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false);
  useEffect(() => {
    const query = window.matchMedia?.('(prefers-reduced-motion: reduce)');
    if (!query) return;
    const changed = () => setReduced(query.matches);
    query.addEventListener('change', changed);
    return () => query.removeEventListener('change', changed);
  }, []);
  return reduced;
}

/** Plays a finished run's real activity log back, step by step, then shows its result and starts again. */
function useReplay(total: number, reduced: boolean) {
  const [shown, setShown] = useState(0);
  useEffect(() => {
    if (!total) return;
    if (reduced) { setShown(total); return; }
    let step = 0;
    let timer = 0;
    const tick = () => {
      step = step >= total ? 0 : step + 1;
      setShown(step);
      timer = window.setTimeout(tick, step >= total ? 7000 : step === 0 ? 500 : 230);
    };
    timer = window.setTimeout(tick, 700);
    return () => window.clearTimeout(timer);
  }, [total, reduced]);
  return shown;
}

const TAG: Record<string, string> = { seller: 'Site', competitors: 'Rivals', discovery: 'Discover', investigation: 'Read',
  skeptic: 'Skeptic', verdict: 'Verdict', outreach: 'Opener', run: 'Run', overrides: 'Change' };

function supportedQuote(company: Company) {
  const supported = new Set(company.decisions.filter(d => d.decision === 'supports').map(d => d.evidence_id));
  const items = company.evidence.filter(e => supported.has(e.id));
  return items.find(e => e.claim_type === 'need' || e.claim_type === 'timing') ?? items[0];
}

function ReplayConsole({ view, onOpen }: { view: AgentRunView; onOpen: (id: string) => void }) {
  const reduced = useReducedMotion();
  const events = view.events;
  const shown = useReplay(events.length, reduced);
  const played = events.slice(0, shown);
  const finished = shown >= events.length;
  const decided = new Set(played.filter(e => e.stage === 'verdict' && e.company).map(e => e.company)).size;
  const shortlisted = view.run.companies.filter(c => c.verdict?.kind === 'shortlisted');
  const current = played.at(-1);
  return <figure className="al-console" aria-label={`Replay of a real search for ${domainOf(view.run.website)}`}>
    <div className="al-console-bar">
      <span className="al-chip"><span className="agent-live-dot" aria-hidden="true" />Replay of a real run</span>
      <span className="al-console-title">{domainOf(view.run.website)} · {day(view.run.created_at)}</span>
    </div>
    <Stepper states={stepStates(played, !finished)} compact />
    <div className="al-console-body" aria-hidden="true">
      {finished ? <div className="al-result">
        <p className="al-result-head">{shortlisted.length} shortlisted of {view.run.companies.length} researched</p>
        {shortlisted.slice(0, 2).map(company => {
          const quote = supportedQuote(company);
          return <div key={company.domain} className="al-result-row">
            <span className="al-verdict">Shortlisted</span><strong>{company.name || company.domain}</strong>
            {quote && <q>{quote.quote.text.length > 140 ? `${quote.quote.text.slice(0, 137)}...` : quote.quote.text}</q>}
          </div>;
        })}
      </div> : <ol className="al-lines">
        {played.slice(-7).map(event => <li key={event.seq} className={`level-${event.level}`}>
          <span className={`al-tag stage-${event.stage}`}>{TAG[event.stage] ?? event.stage}</span>
          <span className="al-line">{prefixOf(event) && <b>{prefixOf(event)} </b>}{event.message}</span>
        </li>)}
      </ol>}
    </div>
    <figcaption className="al-console-foot">
      <span>{finished ? 'Every verdict links to the exact sentence it rests on.'
        : current ? `${STAGES[Math.max(0, stageOf(current))].label} · ${decided}/${view.run.company_count} companies decided` : 'Starting'}</span>
      <a href={`?agent=${view.run.id}`} onClick={event => { event.preventDefault(); onOpen(view.run.id); }}>Open this search →</a>
    </figcaption>
  </figure>;
}

const HOW = [
  { n: '01', title: 'Reads your site', by: 'Muse Spark', text: 'Works out what you sell, who buys it, your competitors and the size of company you serve. Nothing to fill in.' },
  { n: '02', title: 'Hunts for buying signals', by: 'Muse Spark + job boards', text: 'Searches Lever, Greenhouse and Ashby for open roles that mean a company needs you now, and confirms each is still open on its own board.' },
  { n: '03', title: 'Investigates, then doubts', by: 'Muse Spark Open', text: 'Each company is read page by page and quoted word for word. An open-weight skeptic accepts or rejects every quote.' },
  { n: '04', title: 'Rules decide, then it writes', by: 'Fixed rules', text: 'Code, not a model, sorts Shortlisted, Needs a look and Rejected. Shortlisted companies get why now and an opening line, checked against the quotes.' },
];

function ResultCards({ runs, onOpen }: { runs: AgentRunView[]; onOpen: (id: string) => void }) {
  const cards = runs.flatMap(view => view.run.companies.filter(c => c.verdict?.kind === 'shortlisted').map(company => ({ view, company }))).slice(0, 3);
  if (!cards.length) return null;
  return <section className="al-section" aria-labelledby="al-results-heading">
    <p className="al-kicker">Real output</p>
    <h2 id="al-results-heading">Not a score. A reason you can check, and a line you can send.</h2>
    <div className="al-cards">
      {cards.map(({ view, company }) => {
        const quote = supportedQuote(company);
        return <article key={view.run.id + company.domain} className="al-card">
          <header><span className="al-verdict">Shortlisted</span><span className="al-for">for {domainOf(view.run.website)}</span></header>
          <h3>{company.name || company.domain}</h3>
          {quote && <blockquote>“{quote.quote.text}”<cite>{domainOf(quote.quote.url)}</cite></blockquote>}
          {company.pitch && <div className="al-opener"><p>Opening line</p><span>{company.pitch.opener}</span></div>}
          <a href={`?agent=${view.run.id}`} onClick={event => { event.preventDefault(); onOpen(view.run.id); }}>See every quote →</a>
        </article>;
      })}
    </div>
  </section>;
}

export function AgentLanding({ onOpen }: { onOpen: (id: string) => void }) {
  const config = useAgentConfig();
  // A website typed on the landing page only prefills the field; research waits for the visitor's click.
  const [website, setWebsite] = useState(peekKeptCompany);
  useEffect(() => { clearKeptCompany(); }, []);
  const [count, setCount] = useState(Math.min(10, config.maxCompanies));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [recent, setRecent] = useState<AgentRunSummary[]>([]);
  const [examples, setExamples] = useState<AgentRunView[]>([]);
  const check = useRef<HTMLDivElement>(null);
  // The public demo never lists other visitors' searches.
  useEffect(() => { if (!config.publicDemo) agentApi.list().then(setRecent).catch(() => undefined); }, [config.publicDemo]);
  useEffect(() => {
    let cancelled = false;
    const ordered = [...config.examples].sort((a, b) => b.shortlisted - a.shortlisted);
    Promise.all(ordered.map(item => agentApi.run(item.id).catch(() => null)))
      .then(views => { if (!cancelled) setExamples(views.filter((view): view is AgentRunView => view !== null)); });
    return () => { cancelled = true; };
  }, [config.examples]);
  const start = async (event: FormEvent) => {
    event.preventDefault();
    setBusy(true); setError('');
    try {
      const token = config.turnstileSiteKey && check.current ? await turnstileToken(config.turnstileSiteKey, check.current) : undefined;
      const { id } = await agentApi.start(website.trim(), count === 10 ? undefined : { company_count: count }, token);
      onOpen(id);
    } catch (reason) { setError(describe(reason)); setBusy(false); }
  };
  const replay = examples[0];
  return <div className="al">
    <section className="al-hero" aria-labelledby="agent-start-heading">
      <div className="al-hero-inner">
        <div className="al-hero-copy">
          <p className="al-eyebrow">A sales research agent on Muse Spark</p>
          <h1 id="agent-start-heading" className="al-title">Find who needs it.<span>See the proof.</span></h1>
          <p className="al-lede">Enter your website. The agent finds companies hiring for the problem you solve, quotes the exact
            sentence behind every verdict, and writes the first line of your email.</p>
          <form className="al-form" onSubmit={start}>
            <label htmlFor="agent-website">Your company website</label>
            <div className="al-form-row">
              <input id="agent-website" name="website" inputMode="url" autoComplete="url" placeholder="yourcompany.com" required
                value={website} onChange={event => setWebsite(event.target.value)} disabled={busy} />
              <button type="submit" disabled={busy} aria-busy={busy}>{busy ? 'Starting' : `Find ${count} companies`}<span aria-hidden="true">→</span></button>
            </div>
            <div className="al-form-options">
              <label htmlFor="agent-count">How many companies <span className="optional">optional</span></label>
              <select id="agent-count" value={count} disabled={busy} onChange={event => setCount(Number(event.target.value))}>
                {countOptions(config.maxCompanies).map(value => <option key={value} value={value}>{value}</option>)}
              </select>
              <span className="al-form-note">Nothing else to fill in.</span>
            </div>
            <div ref={check} className="agent-check" />
            {error && <p className="notice" role="alert">{error}</p>}
          </form>
          {config.publicDemo && <p className="al-hint">Public demo: up to {config.maxCompanies} companies per search. Anyone with a
            search's link can read it; only this browser can change it.</p>}
        </div>
        <div className="al-hero-visual">
          {replay ? <ReplayConsole view={replay} onOpen={onOpen} /> : <div className="al-console al-console-static">
            <div className="al-console-bar"><span className="al-chip">How a search runs</span></div>
            <Stepper states={STAGES.map(() => 'todo')} compact />
            <p className="al-static-note">Start a search to watch each step here as it happens.</p>
          </div>}
        </div>
      </div>
    </section>

    <section className="al-section" aria-labelledby="al-how-heading">
      <p className="al-kicker">How it works</p>
      <h2 id="al-how-heading">Two models and a rulebook. No step you have to trust blindly.</h2>
      <ol className="al-how">{HOW.map(step => <li key={step.n}>
        <span className="al-how-n">{step.n}</span><h3>{step.title}</h3><p className="al-how-by">{step.by}</p><p>{step.text}</p>
      </li>)}</ol>
    </section>

    <ResultCards runs={examples} onOpen={onOpen} />

    {config.examples.length > 0 && <section className="al-section agent-recent" aria-labelledby="agent-examples-heading">
      <h2 id="agent-examples-heading">See a finished search first</h2>
      <ul>{config.examples.map(item => <li key={item.id}>
        <a href={`?agent=${item.id}`} onClick={event => { event.preventDefault(); onOpen(item.id); }}>{domainOf(item.website)}</a>
        <span>{item.shortlisted} shortlisted, real search from {day(item.created_at)}</span>
      </li>)}</ul>
    </section>}
    {recent.length > 0 && <section className="al-section agent-recent" aria-labelledby="agent-recent-heading">
      <h2 id="agent-recent-heading">Recent searches</h2>
      <ul>{recent.map(item => <li key={item.id}>
        <a href={`?agent=${item.id}`} onClick={event => { event.preventDefault(); onOpen(item.id); }}>{domainOf(item.website)}</a>
        <span>{item.status === 'complete' ? `${item.shortlisted} shortlisted, ${item.needs_look} need a look, ${item.rejected} rejected` : item.status.replace('_', ' ')}</span>
        {item.synthetic && <span className="agent-tag">Synthetic</span>}
      </li>)}</ul>
    </section>}
  </div>;
}
