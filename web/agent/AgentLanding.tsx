import { createContext, useContext, useEffect, useId, useMemo, useRef, useState } from 'react';
import type { FormEvent, RefObject } from 'react';
import '@fontsource/schibsted-grotesk/500.css';
import '@fontsource/schibsted-grotesk/800.css';
import { CompanySearch } from '../CompanySearch';
import { SiteIcon } from '../SiteIcon';
import { configuredDirectoryId } from '../company-suggestions';
import { clearKeptCompany, peekKeptCompany } from '../landing/kept-company';
import { Reveal } from '../landing/Reveal';
import { turnstileToken } from '../landing/turnstile';
import { useLenis, usePrefersReducedMotion } from '../landing/useLenis';
import '../landing/landing.css';
import { STAGES, Stepper, prefixOf, stageOf, stepStates } from './AgentLive';
import { agentApi, domainOf, ownSearches } from './agent-api';
import type { AgentEvent, AgentRunSummary, AgentRunView, Company } from './agent-api';
import { countOptions, useAgentConfig } from './agent-config';
import { CountPicker } from './CountPicker';
import './agent-landing.css';

const describe = (error: unknown) => error instanceof Error ? error.message : 'Something went wrong. Please try again.';
const day = (value: string) => new Date(value).toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' });
function Arrow() { return <span className="pl-arrow" aria-hidden="true">→</span>; }

/** True while the element is on screen, so the replay plays only where it can be seen. */
function useInView(ref: RefObject<HTMLElement | null>) {
  const [inView, setInView] = useState(false);
  useEffect(() => {
    const node = ref.current;
    if (!node) return;
    const observer = new IntersectionObserver(entries => setInView(entries[0].isIntersecting), { threshold: 0.3 });
    observer.observe(node);
    return () => observer.disconnect();
  }, [ref]);
  return inView;
}

const STEP_MS = 1100;  // one step at a time, slow enough to read: every line at 420 ms felt jittery
const HOLD_STEPS = 6;  // about seven seconds on the finished result before it plays again

/** The steps worth watching: searches, what was read and confirmed, the skeptic's tally, verdicts and openers.
    Housekeeping and failed reads stay in the full log on the search's own page. */
function storyEvents(events: AgentEvent[]) {
  return events.filter(event => !(
    /^(?:Could not read|Investigating \d+ compan|Skeptic checking|Reviewing \d+ pieces|\d+ website\(s\) could not be read)/.test(event.message)
    || (event.stage === 'investigation' && /^(?:Read https?:|Searched )/.test(event.message))
    || event.message.includes('set aside')));
}

/** Plays the recorded steps one at a time while on screen, holds the result, then starts over. */
function usePlayback(total: number, playing: boolean, reduced: boolean) {
  const [tick, setTick] = useState(0);
  useEffect(() => {
    if (reduced || !playing || !total) return;
    const timer = window.setInterval(() => setTick(value => value >= total + HOLD_STEPS ? 0 : value + 1), STEP_MS);
    return () => window.clearInterval(timer);
  }, [total, playing, reduced]);
  return reduced ? total : Math.min(tick, total);
}

/** Children marked .al-rise fade up, one after another, when their section scrolls into view. */
function useRise(ref: RefObject<HTMLElement | null>, reduced: boolean, ready = true) {
  useEffect(() => {
    const node = ref.current;
    if (!node) return;
    if (reduced) { node.classList.add('is-in'); return; }
    const observer = new IntersectionObserver(entries => {
      if (entries[0].isIntersecting) { node.classList.add('is-in'); observer.disconnect(); }
    }, { threshold: 0.15 });
    observer.observe(node);
    return () => observer.disconnect();
  // ready: the section may mount after its data loads; watch it once it exists.
  }, [ref, reduced, ready]);
}

const TAG: Record<string, string> = { seller: 'Site', competitors: 'Rivals', discovery: 'Discover', investigation: 'Research',
  skeptic: 'Verify', verdict: 'Verdict', outreach: 'Opener', run: 'Run', overrides: 'Change' };

function supportedQuote(company: Company) {
  const supported = new Set(company.decisions.filter(d => d.decision === 'supports').map(d => d.evidence_id));
  const items = company.evidence.filter(e => supported.has(e.id));
  return items.find(e => e.claim_type === 'need' || e.claim_type === 'timing') ?? items[0];
}

function ReplayConsole({ view, events, onOpen, shown }: { view: AgentRunView; events: AgentEvent[]; onOpen: (id: string) => void;
  shown: number }) {
  const played = events.slice(0, shown);
  const finished = shown >= events.length;
  const decided = new Set(played.filter(e => e.stage === 'verdict' && e.company).map(e => e.company)).size;
  const shortlisted = view.run.companies.filter(c => c.verdict?.kind === 'shortlisted');
  const states = stepStates(played, !finished);
  const active = states.indexOf('active');
  return <figure className="al-console" aria-label={`Replay of a real search for ${domainOf(view.run.website)}`}>
    <div className="al-console-bar">
      <span className="al-chip"><span className="agent-live-dot" aria-hidden="true" />Replay of a real search</span>
      <span className="al-console-title">{domainOf(view.run.website)} · {day(view.run.created_at)}</span>
    </div>
    <Stepper states={states} compact />
    <div className="al-console-body" aria-hidden="true">
      {finished ? <div className="al-result">
        <p className="al-result-head">{shortlisted.length} shortlisted of {view.run.companies.length} researched</p>
        {shortlisted.slice(0, 2).map(company => {
          const quote = supportedQuote(company);
          return <div key={company.domain} className="al-result-row">
            <span className="al-verdict">Shortlisted</span><Logo company={company} /><strong>{company.name || company.domain}</strong>
            {quote && <q>{quote.quote.text.length > 140 ? `${quote.quote.text.slice(0, 137)}...` : quote.quote.text}</q>}
          </div>;
        })}
      </div> : <ol className="al-lines">
        {played.slice(-6).map(event => <li key={event.seq} className={`level-${event.level}`}>
          <span className={`al-tag stage-${event.stage}`}>{TAG[event.stage] ?? event.stage}</span>
          <span className="al-line">{prefixOf(event) && <b>{prefixOf(event)} </b>}{event.message}</span>
        </li>)}
      </ol>}
    </div>
    <figcaption className="al-console-foot">
      <span>{finished ? 'Every verdict links to the evidence behind it.'
        : played.length ? `${STAGES[Math.max(0, active)].label} · ${decided}/${view.run.company_count} companies decided` : 'Starting'}</span>
      <a href={`?agent=${view.run.id}`} onClick={event => { event.preventDefault(); onOpen(view.run.id); }}>Open this search <Arrow /></a>
    </figcaption>
  </figure>;
}

function Logo({ company }: { company: Company }) {
  return <SiteIcon lookup domain={company.domain} fallback={(company.name || company.domain).slice(0, 1).toUpperCase()} className="agent-logo" />;
}

/** The real run's recorded steps, replayed as they happened while the section is on screen. */
function Story({ view, onOpen, reduced }: { view: AgentRunView; onOpen: (id: string) => void; reduced: boolean }) {
  const root = useRef<HTMLElement>(null);
  const events = useMemo(() => storyEvents(view.events), [view.events]);
  const total = events.length;
  const shown = usePlayback(total, useInView(root), reduced);
  const states = stepStates(events.slice(0, shown), shown < total);
  return <section id="al-replay" ref={root} className="al-story al-section" aria-labelledby="al-replay-heading">
    <div className="al-story-pin pl-wrap">
      <div className="al-replay-copy">
        <p className="al-kicker">See it in action</p>
        <Reveal id="al-replay-heading" className="pl-h2" reduced={reduced} lead="A real search," accent="start to finish." />
        <p className="al-replay-text">The actual activity from a search for {domainOf(view.run.website)}, played back as it ran.</p>
        <ol className="al-story-steps">{STAGES.map((stage, index) => <li key={stage.label} className={`is-${states[index]}`}>
          <span className="al-story-dot" aria-hidden="true" /><span>{stage.label}</span><small>{stage.by}</small>
        </li>)}</ol>
        <div className="al-story-bar" aria-hidden="true"><span style={{ transform: `scaleX(${total ? shown / total : 1})` }} /></div>
      </div>
      <ReplayConsole view={view} events={events} onOpen={onOpen} shown={shown} />
    </div>
  </section>;
}

const HOW = [
  { n: '01', title: 'Learns your business', by: 'From your website', text: 'Reads your site to understand what you sell, who buys it, who you compete with and the size of company you serve. No forms to fill in.' },
  { n: '02', title: 'Finds companies ready to buy', by: 'Hiring, funding, launches', text: 'Looks for companies hiring for the problem you solve, raising money, launching something new, or announcing it on LinkedIn or X.' },
  { n: '03', title: 'Checks every claim', by: 'A second, independent review', text: "Reads each company's own pages and job posts. A second model reviews every piece of evidence and throws out anything weak." },
  { n: '04', title: 'Gives you a clear answer', by: 'Shortlisted, Needs a look or Rejected', text: 'Every company gets a verdict and the reason for it. For the strongest fits, you also get why now and a first email.' },
];

/** The website field and its start logic; the same form opens the page and closes it. */
function StartForm({ id, label = 'Your company website', inputId = 'website', action, simple = false }: { id: string; label?: string;
  inputId?: string; action?: string; simple?: boolean }) {
  const config = useAgentConfig();
  const navigate = useStart();
  // A website typed on the landing page only prefills the field; research waits for the visitor's click.
  const [website, setWebsite] = useState(peekKeptCompany);
  useEffect(() => { clearKeptCompany(); }, []);
  // One company by default: quick and cheap; run again for the next one, which skips companies already researched.
  const [count, setCount] = useState(1);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [shake, setShake] = useState(0);
  const check = useRef<HTMLDivElement>(null);
  const start = async (event: FormEvent) => {
    event.preventDefault();
    const value = website.trim();
    if (!value) { document.querySelector<HTMLInputElement>(`#${id} input`)?.focus(); setShake(n => n + 1); return; }
    setBusy(true); setError('');
    try {
      const token = config.turnstileSiteKey && check.current ? await turnstileToken(config.turnstileSiteKey, check.current) : undefined;
      const { id: run } = await agentApi.start(value, { company_count: count }, token);
      navigate(run);
    } catch (reason) { setError(describe(reason)); setBusy(false); }
  };
  return <form id={id} className="yc-form" onSubmit={start} autoComplete="off" noValidate>
    {!simple && <Veins />}
    <div className={`yc-field${shake % 2 ? ' shake' : shake ? ' shake-b' : ''}`}>
      <CompanySearch value={website} clientId={configuredDirectoryId()} iconLookup disabled={busy} label={label}
        inputId={inputId} placeholder="yourcompany.com" onChange={setWebsite} />
      <button className="yc-btn" type="submit" disabled={busy} aria-busy={busy}>
        {busy ? 'Starting' : action ?? `Find ${count} ${count === 1 ? 'company' : 'companies'}`} <Arrow /></button>
    </div>
    {!simple && <div className="yc-form-foot">
      <CountPicker label="Companies to find" value={count} options={countOptions(config.maxCompanies)} disabled={busy} onChange={setCount} />
      {config.publicDemo && <span className="yc-note">Free demo: up to {config.maxCompanies} companies per search.</span>}
    </div>}
    <div ref={check} className="agent-check" />
    {error && <p className="notice" role="alert">{error}</p>}
  </form>;
}

const StartContext = createContext<(id: string) => void>(() => undefined);
const useStart = () => useContext(StartContext);

/** A real Shortlisted company from a finished search, shown as the product would show it. */
function ProductShot({ view, onOpen }: { view: AgentRunView; onOpen: (id: string) => void }) {
  const company = view.run.companies.find(c => c.verdict?.kind === 'shortlisted' && supportedQuote(c));
  if (!company) return null;
  const quote = supportedQuote(company)!;
  const message = company.outreach?.body.split('\n').filter(Boolean).slice(0, 3).join(' ') ?? company.pitch?.opener;
  return <figure className="yc-shot" aria-label={`A real result: ${company.name || company.domain} for ${domainOf(view.run.website)}`}>
    <div className="yc-shot-bar" aria-hidden="true"><span /><span /><span /><em>Shortlist for {domainOf(view.run.website)}</em></div>
    <div className="yc-shot-body">
      <div className="yc-shot-company">
        <Logo company={company} />
        <div><strong>{company.name || company.domain}</strong><small>{company.domain}</small></div>
        <span className="yc-pill-ok">Shortlisted</span>
      </div>
      <div className="yc-shot-grid">
        <div className="yc-shot-card">
          <p className="yc-shot-label">Why now</p>
          <blockquote>“{quote.quote.text.length > 220 ? `${quote.quote.text.slice(0, 217)}...` : quote.quote.text}”</blockquote>
          <p className="yc-shot-source">{domainOf(quote.quote.url)}{quote.quote.open_posting ? ' · open job post' : ''}
            {quote.quote.published_date ? ` · ${day(quote.quote.published_date)}` : ''}</p>
        </div>
        {message && <div className="yc-shot-card">
          <p className="yc-shot-label">First message</p>
          <p className="yc-shot-message">{message}</p>
          <p className="yc-shot-source">✓ Every claim matches the evidence</p>
        </div>}
      </div>
    </div>
    <figcaption><a href={`?agent=${view.run.id}`} onClick={event => { event.preventDefault(); onOpen(view.run.id); }}>
      A real result from a search for {domainOf(view.run.website)}. See the full search <Arrow /></a></figcaption>
  </figure>;
}

/* Veins behind the start field: branches from the page edge merge into trunks that enter the field (its left edge sits
   at x 612 and its middle at y 260 in this 1800 × 520 box, drawn at 1:1). The right side is the left turned 180°. */
const VEIN_TRUNKS = ['C450,236 520,244 618,244', 'C430,268 520,262 618,262', 'C480,320 540,282 618,280'];
const VEINS = [
  'M0,40 C130,50 200,180 230,196 S300,208 330,214 ' + VEIN_TRUNKS[0],
  'M0,150 C100,150 190,196 250,200 S310,210 330,214 ' + VEIN_TRUNKS[0],
  'M0,232 C100,240 160,330 210,322 S280,305 300,300 ' + VEIN_TRUNKS[1],
  'M0,360 C100,360 180,330 230,317 S285,304 300,300 ' + VEIN_TRUNKS[1],
  'M0,490 C120,480 200,390 270,372 S340,355 360,350 ' + VEIN_TRUNKS[2],
  'M0,410 C110,400 200,380 290,367 S345,354 360,350 ' + VEIN_TRUNKS[2],
];
const VEIN_DOTS = VEINS.flatMap((_, vein) => [0, 1].map(n => ({ vein, dur: 5.2 + (vein % 3) * .9, begin: -(vein * 1.7 + n * 3.1) })));

function Veins() {
  const still = usePrefersReducedMotion();
  const id = useId().replace(/:/g, '');
  const side = (turn: boolean) => <g key={String(turn)} transform={turn ? 'rotate(180 900 260)' : undefined}>
    {VEINS.map((d, vein) => <path key={vein} id={`${id}-${turn ? 'r' : 'l'}${vein}`} d={d} />)}
    {!still && VEIN_DOTS.map(({ vein, dur, begin }) => <g key={`${vein}-${begin}`} className="yc-vein-dot">
      <circle r="6" opacity=".16" /><circle r="2.25" />
      <animateMotion dur={`${dur + (turn ? .6 : 0)}s`} begin={`${begin - (turn ? 1.3 : 0)}s`} repeatCount="indefinite"
        calcMode="spline" keyPoints="0;1" keyTimes="0;1" keySplines=".35 0 .65 1"><mpath href={`#${id}-${turn ? 'r' : 'l'}${vein}`} /></animateMotion>
      <animate attributeName="opacity" values="0;1;1;0" keyTimes="0;.18;.9;1" dur={`${dur + (turn ? .6 : 0)}s`}
        begin={`${begin - (turn ? 1.3 : 0)}s`} repeatCount="indefinite" />
    </g>)}
  </g>;
  return <svg className="yc-veins" viewBox="0 0 1800 520" aria-hidden="true" focusable="false">
    <defs><linearGradient id={`${id}-fade`} gradientUnits="userSpaceOnUse" x1="0" y1="0" x2="618" y2="0">
      <stop offset="0" stopColor="#d5682f" stopOpacity="0" /><stop offset=".55" stopColor="#d5682f" stopOpacity=".2" />
      <stop offset="1" stopColor="#d5682f" stopOpacity=".38" /></linearGradient></defs>
    <g fill="none" stroke={`url(#${id}-fade)`} strokeWidth="1.25" strokeLinecap="round">{side(false)}{side(true)}</g>
  </svg>;
}

function Hero({ example, onOpen }: { example?: AgentRunView; onOpen: (id: string) => void }) {
  return <section className="yc-hero" aria-labelledby="agent-start-heading">
    <div className="yc-wrap yc-center">
      <p className="yc-eyebrow">For founders and small sales teams</p>
      <h1 id="agent-start-heading" className="yc-h1">Building got easy.<br /><span>Finding customers didn't.</span></h1>
      <p className="yc-sub">Enter your website. GTM Shortlist finds the companies that need what you sell right now, shows the
        evidence behind each one, and drafts your first message.</p>
      <StartForm id="website-start" />
    </div>
    {example && <div className="yc-wrap"><ProductShot view={example} onOpen={onOpen} /></div>}
  </section>;
}

const FAQ = [
  ['Where does the evidence come from?', "Public pages only: each company's own website, its job posts, news coverage and public posts. Every claim links to the page it came from, so you can check it in one click."],
  ['How is this different from a lead database?', 'A database gives you thousands of names that match a filter. GTM Shortlist gives you a few companies with a reason to talk to you this month, and shows you that reason.'],
  ['What does it cost?', 'The demo is free, up to 5 companies per search, with no signup. A search takes a few minutes.'],
  ['Does it contact anyone for me?', 'No. It drafts the email and a LinkedIn message for you to review and send yourself. It researches companies, never individual people.'],
];

export function AgentLanding({ onOpen }: { onOpen: (id: string | null) => void }) {
  const config = useAgentConfig();
  const reduced = usePrefersReducedMotion();
  useLenis(!reduced);
  const [recent, setRecent] = useState<AgentRunSummary[]>([]);
  const [examples, setExamples] = useState<AgentRunView[]>([]);
  // Locally: every saved search. Public demo: only searches this browser started (it holds their edit tokens), never
  // other visitors'.
  useEffect(() => {
    let cancelled = false;
    if (!config.publicDemo) { agentApi.list().then(found => { if (!cancelled) setRecent(found); }).catch(() => undefined); }
    else {
      Promise.all(ownSearches().map(own => agentApi.run(own.id).catch(() => null))).then(views => {
        if (cancelled) return;
        const count = (view: AgentRunView, kind: string) => view.run.companies.filter(c => c.verdict?.kind === kind).length;
        setRecent(views.filter((view): view is AgentRunView => view !== null)
          .sort((a, b) => b.created_at.localeCompare(a.created_at)).slice(0, 10)
          .map(view => ({ id: view.id, created_at: view.created_at, status: view.status, website: view.run.website,
            synthetic: view.run.synthetic, shortlisted: count(view, 'shortlisted'), needs_look: count(view, 'needs_look'),
            rejected: count(view, 'rejected') })));
      });
    }
    return () => { cancelled = true; };
  }, [config.publicDemo]);
  useEffect(() => {
    let cancelled = false;
    const ordered = [...config.examples].sort((a, b) => b.shortlisted - a.shortlisted);
    Promise.all(ordered.map(item => agentApi.run(item.id).catch(() => null)))
      .then(views => { if (!cancelled) setExamples(views.filter((view): view is AgentRunView => view !== null && view.events.length > 0)); });
    return () => { cancelled = true; };
  }, [config.examples]);
  const replay = examples[0];
  const how = useRef<HTMLElement>(null);
  useRise(how, reduced);
  return <StartContext.Provider value={id => onOpen(id)}><div className="pl al yc">
    <Hero example={examples[0]} onOpen={onOpen} />

    <section ref={how} className="yc-section" aria-labelledby="al-how-heading">
      <div className="yc-wrap">
        <p className="yc-eyebrow">How it works</p>
        <h2 id="al-how-heading" className="yc-h2">The research you'd do by hand, done in minutes.</h2>
        <ol className="yc-steps">{HOW.map((step, index) => <li key={step.n} className="al-rise" style={{ ['--rise' as string]: index }}>
          <span className="yc-step-n">{step.n}</span><h3>{step.title}</h3><p>{step.text}</p>
        </li>)}</ol>
      </div>
    </section>

    {replay && <Story view={replay} onOpen={onOpen} reduced={reduced} />}

    {config.examples.length > 0 && <section className="al-section pl-wrap" aria-labelledby="agent-examples-heading">
      <p className="al-kicker">Examples</p>
      <h2 id="agent-examples-heading" className="al-examples-title">Explore a finished search</h2>
      <p className="al-examples-note">Real searches from {[...new Set(config.examples.map(item => day(item.created_at)))].join(', ')}. Open one to see every
        company we checked, the evidence and the verdict.</p>
      <ul className="al-examples">{config.examples.map(item => <li key={item.id}>
        <a href={`?agent=${item.id}`} onClick={event => { event.preventDefault(); onOpen(item.id); }}>
          <span className="al-example-for">For {domainOf(item.website)}</span>
          <strong>{item.shortlisted_names?.length ? `${item.shortlisted_names.join(' and ')} shortlisted` : 'Nothing shortlisted'}</strong>
          {item.rejected?.[0] && <span className="al-example-rejected"><b>Rejected</b> {item.rejected[0]}</span>}
          <span className="al-example-open">View search <span aria-hidden="true">→</span></span>
        </a>
      </li>)}</ul>
    </section>}
    <section className="yc-section" aria-labelledby="yc-faq-heading">
      <div className="yc-wrap yc-narrow">
        <h2 id="yc-faq-heading" className="yc-h2">Questions</h2>
        <div className="yc-faq">{FAQ.map(([question, answer]) => <details key={question}><summary>{question}</summary><p>{answer}</p></details>)}</div>
      </div>
    </section>

    <section className="yc-cta" aria-labelledby="yc-cta-heading">
      <div className="yc-wrap yc-center">
        <h2 id="yc-cta-heading" className="yc-h2">Find the companies that need you this week.</h2>
        <p className="yc-sub">Start with your website. Nothing to set up.</p>
        <StartForm id="website-end" label="Your website" inputId="website-again" action="Start your search" simple />
      </div>
    </section>

    {recent.length > 0 && <section className="al-section pl-wrap agent-recent" aria-labelledby="agent-recent-heading">
      <h2 id="agent-recent-heading">{config.publicDemo ? 'Your searches' : 'Recent searches'}</h2>
      <ul>{recent.map(item => <li key={item.id}>
        <a href={`?agent=${item.id}`} onClick={event => { event.preventDefault(); onOpen(item.id); }}>{domainOf(item.website)}</a>
        <span>{day(item.created_at)} · {item.status === 'complete' ? `${item.shortlisted} shortlisted, ${item.needs_look} need a look, ${item.rejected} rejected` : item.status.replace('_', ' ')}</span>
        {item.synthetic && <span className="agent-tag">Synthetic</span>}
      </li>)}</ul>
    </section>}
  </div></StartContext.Provider>;
}
