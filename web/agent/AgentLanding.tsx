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
import type { AgentEvent, AgentRunSummary, AgentRunView, Company, SellerDescription } from './agent-api';
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
  const [describing, setDescribing] = useState(false);
  /** Starts from a website or a description; the browser check renders in `place`, which must be reachable. */
  const launch = async (seller: string | SellerDescription, place: HTMLDivElement | null, fail: (message: string) => void) => {
    setBusy(true); setError('');
    try {
      const token = config.turnstileSiteKey && place ? await turnstileToken(config.turnstileSiteKey, place) : undefined;
      const { id: run } = await agentApi.start(seller, { company_count: count }, token);
      navigate(run);
    } catch (reason) { fail(describe(reason)); setBusy(false); }
  };
  const start = (event: FormEvent) => {
    event.preventDefault();
    const value = website.trim();
    if (!value) { document.querySelector<HTMLInputElement>(`#${id} input`)?.focus(); setShake(n => n + 1); return; }
    void launch(value, check.current, setError);
  };
  return <><form id={id} className="yc-form" onSubmit={start} autoComplete="off" noValidate>
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
      <button type="button" className="yc-describe-link" onClick={() => setDescribing(true)} disabled={busy}>I don't have a website</button>
    </div>}
    <div ref={check} className="agent-check" />
    {error && <p className="notice" role="alert">{error}</p>}
  </form>
  {describing && <Describe count={count} busy={busy} onClose={() => setDescribing(false)} onStart={launch} />}</>;
}

/** For a business without a website: its own words stand in for the site, and every claim about it quotes them. */
function Describe({ count, busy, onClose, onStart }: { count: number; busy: boolean; onClose: () => void;
  onStart: (seller: SellerDescription, place: HTMLDivElement | null, fail: (message: string) => void) => Promise<void> }) {
  const dialog = useRef<HTMLDialogElement>(null);
  const check = useRef<HTMLDivElement>(null);
  const [fields, setFields] = useState({ offer: '', buyer: '', markets: '', name: '' });
  const [error, setError] = useState('');
  // showModal focuses the first control, the close button; the first question is where typing starts.
  useEffect(() => { dialog.current?.showModal(); dialog.current?.querySelector<HTMLTextAreaElement>('#describe-offer')?.focus(); }, []);
  const set = (key: keyof typeof fields) => (event: { target: { value: string } }) =>
    { setFields(previous => ({ ...previous, [key]: event.target.value })); setError(''); };
  const submit = (event: FormEvent) => {
    event.preventDefault();
    const missing = (['offer', 'buyer'] as const).find(key => fields[key].trim().length < 10);
    if (missing) {
      setError(missing === 'offer' ? 'Say what you sell or want to build, in a sentence.' : 'Say who your ideal customer is, in a sentence.');
      dialog.current?.querySelector<HTMLTextAreaElement>(`#describe-${missing}`)?.focus();
      return;
    }
    setError('');
    void onStart({ offer: fields.offer.trim(), buyer: fields.buyer.trim(), markets: fields.markets.trim(), name: fields.name.trim() },
      check.current, setError);
  };
  return <dialog ref={dialog} className="yc-describe" aria-labelledby="describe-title" onClose={onClose}>
    <form onSubmit={submit} noValidate>
      <div className="yc-describe-head">
        <h2 id="describe-title">Describe your business</h2>
        <button type="button" className="yc-describe-close" onClick={() => dialog.current?.close()} aria-label="Close">
          <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true"><path d="m7 7 10 10M17 7 7 17" /></svg>
        </button>
      </div>
      <p className="yc-describe-sub">Your answers stand in for a website. Everything we say about you quotes your own words.</p>
      <label htmlFor="describe-offer">What do you sell or want to build?</label>
      <textarea id="describe-offer" rows={2} maxLength={600} value={fields.offer} onChange={set('offer')} disabled={busy}
        placeholder="Bookkeeping software for independent cafés" />
      <label htmlFor="describe-buyer">Who is your ideal customer?</label>
      <textarea id="describe-buyer" rows={2} maxLength={600} value={fields.buyer} onChange={set('buyer')} disabled={busy}
        placeholder="Owners of cafés with 2 to 10 staff who still do their books by hand" />
      <label htmlFor="describe-markets">Which markets or geography? <span>Optional</span></label>
      <input id="describe-markets" maxLength={300} value={fields.markets} onChange={set('markets')} disabled={busy}
        placeholder="UK and Ireland" />
      <label htmlFor="describe-name">Business name <span>Optional</span></label>
      <input id="describe-name" maxLength={120} value={fields.name} onChange={set('name')} disabled={busy}
        placeholder="Names your search" />
      <div ref={check} className="agent-check" />
      {error && <p className="notice" role="alert">{error}</p>}
      <div className="yc-describe-actions">
        <button type="button" className="yc-describe-cancel" onClick={() => dialog.current?.close()} disabled={busy}>Cancel</button>
        <button className="yc-btn" type="submit" disabled={busy} aria-busy={busy}>
          {busy ? 'Starting' : `Find ${count} ${count === 1 ? 'company' : 'companies'}`} <Arrow /></button>
      </div>
    </form>
  </dialog>;
}

const StartContext = createContext<(id: string) => void>(() => undefined);
const useStart = () => useContext(StartContext);

/** A real Shortlisted company from a finished search, shown as the product would show it. */
const SHOT_VERDICT = { shortlisted: ['Shortlisted', 'yc-pill-ok'], needs_look: ['Needs a look', 'yc-pill-look'],
  rejected: ['Rejected', 'yc-pill-no'] } as const;
const SHOT_ORDER = { shortlisted: 0, needs_look: 1, rejected: 2 } as const;

/** Why a row got its verdict, in a few words: the dated evidence for a Shortlisted company, the first thing missing
    for the rest. */
function shotReason(company: Company) {
  const quote = supportedQuote(company);
  if (company.verdict?.kind === 'shortlisted' && quote)
    return quote.quote.source_type === 'own_site' && !quote.quote.open_posting ? 'Shown on their own site'
      : [quote.quote.open_posting ? 'Open job post' : 'Recent evidence', domainOf(quote.quote.url),
        quote.quote.published_date ? day(quote.quote.published_date) : ''].filter(Boolean).join(' · ');
  return company.verdict?.missing?.[0]?.split(/[:(]/)[0].trim() ?? 'Not finished';
}

/** The product, not one company: a real search as the board shows it, with what every row comes with. */
function ProductShot({ view, onOpen }: { view: AgentRunView; onOpen: (id: string) => void }) {
  const rows = view.run.companies.filter(c => c.verdict).sort((a, b) => SHOT_ORDER[a.verdict!.kind] - SHOT_ORDER[b.verdict!.kind]).slice(0, 4);
  if (!rows.some(c => c.verdict?.kind === 'shortlisted')) return null;
  const count = (kind: string) => view.run.companies.filter(c => c.verdict?.kind === kind).length;
  const found = view.run.candidate_pool?.length ?? 0;
  return <figure className="yc-shot" aria-label={`A real search for ${domainOf(view.run.website)}`}>
    <div className="yc-shot-bar" aria-hidden="true"><span /><span /><span /><em>GTM Shortlist · search for {domainOf(view.run.website)}</em></div>
    <div className="yc-shot-body">
      <div className="yc-shot-stats">
        {found > 0 && <p><strong>{found}</strong> companies found</p>}
        <p><strong>{view.run.companies.length}</strong> researched</p>
        <p className="is-ok"><strong>{count('shortlisted')}</strong> shortlisted</p>
        <p><strong>{count('needs_look') + count('rejected')}</strong> held back, with the reason</p>
      </div>
      <ul className="yc-shot-rows">{rows.map(company => {
        const [label, tone] = SHOT_VERDICT[company.verdict!.kind];
        return <li key={company.domain}>
          <SiteIcon lookup domain={company.domain} fallback={(company.name || company.domain).slice(0, 1).toUpperCase()} className="yc-shot-mark" />
          <span className="yc-shot-name">{company.domain}</span>
          <span className="yc-shot-why">{shotReason(company)}</span>
          <span className={tone}>{label}</span>
        </li>;
      })}</ul>
      <ul className="yc-shot-features">
        <li><strong>The evidence</strong><span>The quote and link behind every verdict</span></li>
        <li><strong>A second check</strong><span>Another model tries to disprove each claim</span></li>
        <li><strong>A first message</strong><span>An email and a LinkedIn note, checked too</span></li>
      </ul>
    </div>
    <figcaption><a href={`?agent=${view.run.id}`} onClick={event => { event.preventDefault(); onOpen(view.run.id); }}>
      Open this search <Arrow /></a></figcaption>
  </figure>;
}

/* The search, drawn behind the start field: many companies flow in from the left and most drop away on the way; a few
   leave on the right, in orange. Drawn 1:1 in an 1800 × 1100 box centred on the field (left edge x 612, right edge
   x 1188, middle y 550). */
const FAN = 13;
const noise = (n: number) => { const x = Math.sin(n * 12.9898) * 43758.5453; return x - Math.floor(x); };
const round = (n: number) => Math.round(n);
const IN_LINES = Array.from({ length: FAN }, (_, i) => {
  const t = -1 + 2 * i / (FAN - 1), a = Math.abs(t);
  const end = 550 + t * 22;
  const fromEdge = a < .55;
  const sx = fromEdge ? -10 : (a - .55) / .45 * 360, sy = fromEdge ? 550 + t * 960 : t < 0 ? -10 : 1110;
  const k = Math.min(1, Math.max(0, (a - .3) / .7));
  const c1x = sx + (612 - sx) * (.45 - .33 * k), c1y = sy + (end - sy) * .55 * k;
  return `M${round(sx)},${round(sy)} C${round(c1x)},${round(c1y)} ${round(Math.max(380, sx + 80))},${round(end)} 616,${round(end)}`;
});
const OUT_LINES = [-1, 0, 1].map(t => `M1184,${550 + t * 12} C1420,${550 + t * 12} 1500,${550 + t * 150} 1810,${550 + t * 190}`);
// Most companies coming in drop out part of the way, like the ones a search sets aside.
const IN_DOTS = IN_LINES.flatMap((_, line) => [0, 1, 2].map(n => {
  const seed = line * 11 + n * 5;
  return { line, dur: 7 + noise(seed) * 4, begin: -noise(seed + 1) * 11, drop: noise(seed + 2) < .6 ? .35 + noise(seed + 3) * .35 : 0 };
}));
const OUT_DOTS = OUT_LINES.flatMap((_, line) => [0, 1].map(n => ({ line, dur: 6.5 + line * .8, begin: -(line * 2.3 + n * 3.6) })));

function Veins() {
  const still = usePrefersReducedMotion();
  const id = useId().replace(/:/g, '');
  const every = { repeatCount: 'indefinite' };
  return <svg className="yc-veins" viewBox="0 0 1800 1100" aria-hidden="true" focusable="false">
    <defs>
      <linearGradient id={`${id}-in`} gradientUnits="userSpaceOnUse" x1="0" y1="0" x2="420" y2="0">
        <stop offset="0" stopColor="#1b1b1b" stopOpacity="0" /><stop offset="1" stopColor="#1b1b1b" stopOpacity=".1" /></linearGradient>
      <linearGradient id={`${id}-out`} gradientUnits="userSpaceOnUse" x1="1188" y1="0" x2="1800" y2="0">
        <stop offset="0" stopColor="#d5682f" stopOpacity=".45" /><stop offset="1" stopColor="#d5682f" stopOpacity="0" /></linearGradient>
    </defs>
    <g fill="none" strokeWidth="1">
      {IN_LINES.map((d, line) => <path key={line} id={`${id}-i${line}`} d={d} stroke={`url(#${id}-in)`} />)}
      {OUT_LINES.map((d, line) => <path key={line} id={`${id}-o${line}`} d={d} stroke={`url(#${id}-out)`} strokeWidth="1.25" />)}
    </g>
    {!still && IN_DOTS.map(({ line, dur, begin, drop }, n) => {
      const time = { dur: `${dur.toFixed(2)}s`, begin: `${begin.toFixed(2)}s`, ...every };
      const fade = drop ? { values: '0;.9;.9;0;0', keyTimes: `0;.1;${(drop - .08).toFixed(2)};${drop.toFixed(2)};1` }
        : { values: '0;.9;.9;0', keyTimes: '0;.1;.92;1' };
      return <circle key={n} r="1.75" fill="#9c958c">
        <animateMotion {...time}><mpath href={`#${id}-i${line}`} /></animateMotion>
        <animate attributeName="opacity" {...fade} {...time} />
      </circle>;
    })}
    {!still && OUT_DOTS.map(({ line, dur, begin }, n) => {
      const time = { dur: `${dur}s`, begin: `${begin}s`, ...every };
      return <circle key={n} r="2.5" fill="#d5682f">
        <animateMotion {...time}><mpath href={`#${id}-o${line}`} /></animateMotion>
        <animate attributeName="opacity" values="0;1;1;0" keyTimes="0;.08;.7;1" {...time} />
      </circle>;
    })}
  </svg>;
}

/** A returning visitor's way back: the latest search, and the full list on Your shortlist when there are more. */
function Continue({ last, more, onOpen }: { last: AgentRunSummary; more: boolean; onOpen: (id: string | null, list?: boolean) => void }) {
  const status = last.status === 'complete' ? `${last.shortlisted} shortlisted` : last.status.replace('_', ' ');
  return <nav className="yc-continue" aria-label="Your searches">
    <a href={`?agent=${last.id}`} onClick={event => { event.preventDefault(); onOpen(last.id); }}>
      Your last search: {domainOf(last.website)} <span>· {status}</span> <Arrow /></a>
    {more && <a className="yc-continue-all" href="?shortlist=1" onClick={event => { event.preventDefault(); onOpen(null, true); }}>All your searches</a>}
  </nav>;
}

function Hero({ example, last, more, onOpen }: { example?: AgentRunView; last?: AgentRunSummary; more: boolean;
  onOpen: (id: string | null, list?: boolean) => void }) {
  return <section className="yc-hero" aria-labelledby="agent-start-heading">
    <div className="yc-wrap yc-center">
      <p className="yc-eyebrow">For founders and small sales teams</p>
      <h1 id="agent-start-heading" className="yc-h1">Building got easy.<br /><span>Finding customers didn't.</span></h1>
      <p className="yc-sub">Enter your website. GTM Shortlist finds the companies that need what you sell right now, shows the
        evidence behind each one, and drafts your first message.</p>
      <StartForm id="website-start" />
      {last && <Continue last={last} more={more} onOpen={onOpen} />}
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

export function AgentLanding({ onOpen }: { onOpen: (id: string | null, list?: boolean) => void }) {
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
    <Hero example={examples[0]} last={recent[0]} more={recent.length > 1} onOpen={onOpen} />

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

  </div></StartContext.Provider>;
}
