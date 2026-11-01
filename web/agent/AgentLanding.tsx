import { useEffect, useRef, useState } from 'react';
import type { FormEvent, RefObject } from 'react';
import '@fontsource/schibsted-grotesk/500.css';
import '@fontsource/schibsted-grotesk/800.css';
import { clearKeptCompany, peekKeptCompany } from '../landing/kept-company';
import { Reveal } from '../landing/Reveal';
import { SignalStream } from '../landing/signal-stream';
import { turnstileToken } from '../landing/turnstile';
import { useLenis, usePrefersReducedMotion } from '../landing/useLenis';
import '../landing/landing.css';
import { STAGES, Stepper, prefixOf, stageOf, stepStates } from './AgentLive';
import { agentApi, domainOf } from './agent-api';
import type { AgentRunSummary, AgentRunView, Company } from './agent-api';
import { countOptions, useAgentConfig } from './agent-config';
import './agent-landing.css';

const describe = (error: unknown) => error instanceof Error ? error.message : 'Something went wrong. Please try again.';
const day = (value: string) => new Date(value).toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' });
// Same breakpoint as the hosted landing page: below it the stream runs top to bottom.
const verticalQuery = '(max-width: 1180px)';
function Arrow() { return <span className="pl-arrow" aria-hidden="true">→</span>; }

/** Plays a finished run's real activity log back, step by step, then shows its result and starts again. */
function useReplay(total: number, reduced: boolean, playing: boolean) {
  const [shown, setShown] = useState(0);
  useEffect(() => {
    if (!total) return;
    if (reduced) { setShown(total); return; }
    if (!playing) return;
    let step = 0;
    let timer = 0;
    const tick = () => {
      step = step >= total ? 0 : step + 1;
      setShown(step);
      timer = window.setTimeout(tick, step >= total ? 7000 : step === 0 ? 500 : 260);
    };
    timer = window.setTimeout(tick, 400);
    return () => window.clearTimeout(timer);
  }, [total, reduced, playing]);
  return shown;
}

/** True once the element has scrolled into view, so the replay starts where it can be seen. */
function useSeen(ref: RefObject<HTMLElement | null>) {
  const [seen, setSeen] = useState(false);
  useEffect(() => {
    const node = ref.current;
    if (!node || seen) return;
    const observer = new IntersectionObserver(entries => { if (entries[0].isIntersecting) { setSeen(true); observer.disconnect(); } }, { threshold: 0.3 });
    observer.observe(node);
    return () => observer.disconnect();
  }, [ref, seen]);
  return seen;
}

const TAG: Record<string, string> = { seller: 'Site', competitors: 'Rivals', discovery: 'Discover', investigation: 'Read',
  skeptic: 'Skeptic', verdict: 'Verdict', outreach: 'Opener', run: 'Run', overrides: 'Change' };

function supportedQuote(company: Company) {
  const supported = new Set(company.decisions.filter(d => d.decision === 'supports').map(d => d.evidence_id));
  const items = company.evidence.filter(e => supported.has(e.id));
  return items.find(e => e.claim_type === 'need' || e.claim_type === 'timing') ?? items[0];
}

function ReplayConsole({ view, onOpen, reduced }: { view: AgentRunView; onOpen: (id: string) => void; reduced: boolean }) {
  const root = useRef<HTMLElement>(null);
  const seen = useSeen(root);
  const events = view.events;
  const shown = useReplay(events.length, reduced, seen);
  const played = events.slice(0, shown);
  const finished = shown >= events.length;
  const decided = new Set(played.filter(e => e.stage === 'verdict' && e.company).map(e => e.company)).size;
  const shortlisted = view.run.companies.filter(c => c.verdict?.kind === 'shortlisted');
  const current = played.at(-1);
  return <figure ref={root} className="al-console" aria-label={`Replay of a real search for ${domainOf(view.run.website)}`}>
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
        {played.slice(-8).map(event => <li key={event.seq} className={`level-${event.level}`}>
          <span className={`al-tag stage-${event.stage}`}>{TAG[event.stage] ?? event.stage}</span>
          <span className="al-line">{prefixOf(event) && <b>{prefixOf(event)} </b>}{event.message}</span>
        </li>)}
      </ol>}
    </div>
    <figcaption className="al-console-foot">
      <span>{finished ? 'Every verdict links to the exact sentence it rests on.'
        : current ? `${STAGES[Math.max(0, stageOf(current))].label} · ${decided}/${view.run.company_count} companies decided` : 'Starting'}</span>
      <a href={`?agent=${view.run.id}`} onClick={event => { event.preventDefault(); onOpen(view.run.id); }}>Open this search <Arrow /></a>
    </figcaption>
  </figure>;
}

const HOW = [
  { n: '01', title: 'Reads your site', by: 'Muse Spark', text: 'Works out what you sell, who buys it, your competitors and the size of company you serve. Nothing to fill in.' },
  { n: '02', title: 'Hunts for buying signals', by: 'Muse Spark + job boards', text: 'Searches Lever, Greenhouse and Ashby for open roles that mean a company needs you now, and confirms each is still open on its own board.' },
  { n: '03', title: 'Investigates, then doubts', by: 'Muse Spark Open', text: 'Each company is read page by page and quoted word for word. An open-weight skeptic accepts or rejects every quote.' },
  { n: '04', title: 'Rules decide, then it writes', by: 'Fixed rules', text: 'Code, not a model, sorts Shortlisted, Needs a look and Rejected. Shortlisted companies get why now and an opening line, checked against the quotes.' },
];

function ResultCards({ runs, onOpen, reduced }: { runs: AgentRunView[]; onOpen: (id: string) => void; reduced: boolean }) {
  const cards = runs.flatMap(view => view.run.companies.filter(c => c.verdict?.kind === 'shortlisted').map(company => ({ view, company }))).slice(0, 3);
  if (!cards.length) return null;
  return <section className="al-section pl-wrap" aria-labelledby="al-results-heading">
    <p className="al-kicker">Real output</p>
    <Reveal id="al-results-heading" className="pl-h2" reduced={reduced} lead="Not a score. A reason you can check," accent="and a line you can send." />
    <div className="al-cards">
      {cards.map(({ view, company }) => {
        const quote = supportedQuote(company);
        return <article key={view.run.id + company.domain} className="al-card">
          <header><span className="al-verdict">Shortlisted</span><span className="al-for">for {domainOf(view.run.website)}</span></header>
          <h3>{company.name || company.domain}</h3>
          {quote && <blockquote>“{quote.quote.text}”<cite>{domainOf(quote.quote.url)}</cite></blockquote>}
          {company.pitch && <div className="al-opener"><p>Opening line</p><span>{company.pitch.opener}</span></div>}
          <a href={`?agent=${view.run.id}`} onClick={event => { event.preventDefault(); onOpen(view.run.id); }}>See every quote <Arrow /></a>
        </article>;
      })}
    </div>
  </section>;
}

const GATES = [['Hiring signal', 'Open role on a job board'], ['Investigated', 'Quoted from their pages'], ['Skeptic', 'Kept by Muse Spark Open']];

function Hero({ reduced, onOpen }: { reduced: boolean; onOpen: (id: string) => void }) {
  const config = useAgentConfig();
  // A website typed on the landing page only prefills the field; research waits for the visitor's click.
  const [website, setWebsite] = useState(peekKeptCompany);
  useEffect(() => { clearKeptCompany(); }, []);
  const [count, setCount] = useState(Math.min(10, config.maxCompanies));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [invite, setInvite] = useState(true);
  const [shake, setShake] = useState(0);
  const check = useRef<HTMLDivElement>(null);
  const instrument = useRef<HTMLDivElement>(null);
  const stream = useRef<SignalStream | null>(null);
  const canvas = useRef<HTMLCanvasElement>(null), cardIn = useRef<HTMLFormElement>(null), cardOut = useRef<HTMLElement>(null), streamEl = useRef<HTMLDivElement>(null);
  const rows = useRef<HTMLOListElement>(null), tally = useRef<HTMLSpanElement>(null), portOut = useRef<HTMLSpanElement>(null);
  const [on, setOn] = useState(false);
  useEffect(() => {
    const node = instrument.current;
    if (!node || !canvas.current || !cardIn.current || !cardOut.current || !streamEl.current || !rows.current || !tally.current || !portOut.current) return;
    const all = <T extends HTMLElement>(selector: string) => [...node.querySelectorAll<T>(selector)];
    let created: SignalStream | null = null, cancelled = false;
    const elements = { instrument: node, canvas: canvas.current, cardIn: cardIn.current, cardOut: cardOut.current, stream: streamEl.current,
      gates: all('.pl-gate'), gateTops: all('.pl-g-top'), gateBottoms: all('.pl-g-bot'), kept: all('[data-kept]'), checked: all('[data-checked]'),
      count: tally.current, rows: rows.current, portOut: portOut.current };
    // Lay the stream out against final type metrics, but never wait long for fonts.
    void Promise.race([document.fonts?.ready ?? Promise.resolve(), new Promise(resolve => window.setTimeout(resolve, 1200))]).then(() => {
      if (cancelled) return;
      created = new SignalStream(elements, reduced, window.matchMedia(verticalQuery));
      stream.current = created; setOn(true);
    });
    return () => { cancelled = true; created?.destroy(); stream.current = null; elements.rows.replaceChildren(); };
  }, [reduced]);

  const start = async (event: FormEvent) => {
    event.preventDefault();
    const value = website.trim();
    if (!value) { document.getElementById('agent-website')?.focus(); setShake(n => n + 1); return; }
    setBusy(true); setError(''); stream.current?.burst();
    try {
      const token = config.turnstileSiteKey && check.current ? await turnstileToken(config.turnstileSiteKey, check.current) : undefined;
      const { id } = await agentApi.start(value, count === 10 ? undefined : { company_count: count }, token);
      onOpen(id);
    } catch (reason) { setError(describe(reason)); setBusy(false); }
  };
  const domain = domainOf(website);
  return <section className="pl-hero" aria-labelledby="agent-start-heading">
    <div className="pl-hero-in pl-wrap">
      <div className="pl-hero-top">
        <div><p className="al-eyebrow">A sales research agent on Muse Spark</p>
          <Reveal as="h1" id="agent-start-heading" reduced={reduced} lead="Find who needs it." accent="See the proof." br /></div>
        <p className="pl-lede">Enter your website. The agent finds companies hiring for the problem you solve, shows <strong>the exact
          sentence behind every verdict</strong>, and writes the first line of your email.</p>
      </div>
      <div className={`pl-instrument${on ? ' on' : ''}`} ref={instrument}>
        <canvas ref={canvas} aria-hidden="true" />
        <form ref={cardIn} className={`pl-card pl-intake${invite ? ' invite' : ''}`} onSubmit={start} autoComplete="off" noValidate
          onPointerEnter={() => stream.current?.setHover(true)} onPointerLeave={() => stream.current?.setHover(document.activeElement?.id === 'agent-website')}>
          <label className="pl-label" htmlFor="agent-website">Your company website</label>
          <div className="pl-controls">
            <div className={`pl-field${shake % 2 ? ' shake' : shake ? ' shake-b' : ''}`} onFocus={() => { setInvite(false); stream.current?.setHover(true); }} onBlur={() => stream.current?.setHover(false)}>
              <input id="agent-website" name="website" inputMode="url" autoComplete="url" placeholder="yourcompany.com" required
                value={website} disabled={busy} onChange={event => { setInvite(false); setWebsite(event.target.value); stream.current?.boost(1100); }} /></div>
            <button className="pl-btn pl-btn-primary pl-btn-block" type="submit" disabled={busy} aria-busy={busy}>{busy ? 'Starting' : `Find ${count} companies`} <Arrow /></button>
          </div>
          <div className="al-count">
            <label htmlFor="agent-count">How many companies <span className="optional">optional</span></label>
            <select id="agent-count" value={count} disabled={busy} onChange={event => setCount(Number(event.target.value))}>
              {countOptions(config.maxCompanies).map(value => <option key={value} value={value}>{value}</option>)}
            </select>
          </div>
          <div ref={check} className="agent-check" />
          {error && <p className="notice" role="alert">{error}</p>}
          <span className="pl-port" aria-hidden="true" />
        </form>
        <div className="pl-stream" ref={streamEl} aria-hidden="true">
          {GATES.map(([name, sub], index) => <div className="pl-gate" key={name}>
            <div className="pl-g-top"><span className="pl-g-h">{name}</span><span className="pl-g-sub">{index === 0 && domain ? `Needs ${domain}` : sub}</span></div>
            <div className="pl-g-bot"><b data-kept="">0</b><span>kept of <em data-checked="">0</em></span></div>
          </div>)}
        </div>
        <section ref={cardOut} className="pl-card pl-shortlist" aria-label="Illustrative sample shortlist">
          <span ref={portOut} className="pl-port" aria-hidden="true" />
          <header><div><strong>Shortlist</strong><small>Illustrative sample</small></div><span ref={tally} className="pl-badge" aria-label="Companies kept in this example">0</span></header>
          <ol ref={rows} className="pl-rows" />
          <footer><a href="#al-replay">Watch a real run <Arrow /></a></footer>
        </section>
      </div>
      {config.publicDemo && <p className="al-hint">Public demo: up to {config.maxCompanies} companies per search. Anyone with a
        search's link can read it; only this browser can change it.</p>}
    </div>
  </section>;
}

export function AgentLanding({ onOpen }: { onOpen: (id: string) => void }) {
  const config = useAgentConfig();
  const reduced = usePrefersReducedMotion();
  useLenis(!reduced);
  const [recent, setRecent] = useState<AgentRunSummary[]>([]);
  const [examples, setExamples] = useState<AgentRunView[]>([]);
  // The public demo never lists other visitors' searches.
  useEffect(() => { if (!config.publicDemo) agentApi.list().then(setRecent).catch(() => undefined); }, [config.publicDemo]);
  useEffect(() => {
    let cancelled = false;
    const ordered = [...config.examples].sort((a, b) => b.shortlisted - a.shortlisted);
    Promise.all(ordered.map(item => agentApi.run(item.id).catch(() => null)))
      .then(views => { if (!cancelled) setExamples(views.filter((view): view is AgentRunView => view !== null && view.events.length > 0)); });
    return () => { cancelled = true; };
  }, [config.examples]);
  const replay = examples[0];
  return <div className="pl al">
    <Hero reduced={reduced} onOpen={onOpen} />

    {replay && <section id="al-replay" className="al-section al-replay pl-wrap" aria-labelledby="al-replay-heading">
      <div className="al-replay-copy">
        <p className="al-kicker">Watch it work</p>
        <Reveal id="al-replay-heading" className="pl-h2" reduced={reduced} lead="A real search," accent="step by step." />
        <p className="al-replay-text">This is the recorded activity of a real search for {domainOf(replay.run.website)}: every job board it
          searched, every page it read, every quote the skeptic kept or threw out. Your search shows the same steps live.</p>
      </div>
      <ReplayConsole view={replay} onOpen={onOpen} reduced={reduced} />
    </section>}

    <section className="al-section pl-wrap" aria-labelledby="al-how-heading">
      <p className="al-kicker">How it works</p>
      <Reveal id="al-how-heading" className="pl-h2" reduced={reduced} lead="Two models and a rulebook." accent="Nothing to trust blindly." />
      <ol className="al-how">{HOW.map(step => <li key={step.n}>
        <span className="al-how-n">{step.n}</span><h3>{step.title}</h3><p className="al-how-by">{step.by}</p><p>{step.text}</p>
      </li>)}</ol>
    </section>

    <ResultCards runs={examples} onOpen={onOpen} reduced={reduced} />

    {config.examples.length > 0 && <section className="al-section pl-wrap agent-recent" aria-labelledby="agent-examples-heading">
      <h2 id="agent-examples-heading">See a finished search first</h2>
      <ul>{config.examples.map(item => <li key={item.id}>
        <a href={`?agent=${item.id}`} onClick={event => { event.preventDefault(); onOpen(item.id); }}>{domainOf(item.website)}</a>
        <span>{item.shortlisted} shortlisted, real search from {day(item.created_at)}</span>
      </li>)}</ul>
    </section>}
    {recent.length > 0 && <section className="al-section pl-wrap agent-recent" aria-labelledby="agent-recent-heading">
      <h2 id="agent-recent-heading">Recent searches</h2>
      <ul>{recent.map(item => <li key={item.id}>
        <a href={`?agent=${item.id}`} onClick={event => { event.preventDefault(); onOpen(item.id); }}>{domainOf(item.website)}</a>
        <span>{item.status === 'complete' ? `${item.shortlisted} shortlisted, ${item.needs_look} need a look, ${item.rejected} rejected` : item.status.replace('_', ' ')}</span>
        {item.synthetic && <span className="agent-tag">Synthetic</span>}
      </li>)}</ul>
    </section>}
  </div>;
}
