import { Fragment, useEffect, useRef, useState } from 'react';
import type { FormEvent, RefObject } from 'react';
import type Lenis from 'lenis';
import '@fontsource/schibsted-grotesk/500.css';
import '@fontsource/schibsted-grotesk/800.css';
import { SignalStream } from './signal-stream';
import { CompanySearch } from '../CompanySearch';
import { exampleCheckpoints, examplePassage, storySteps, storyWeights } from './landing-data';
import type { FeedState } from './landing-data';
import { useLenis, usePrefersReducedMotion } from './useLenis';
import './landing.css';

export const sourceCodeUrl = 'https://github.com/adkbbx/GTM_Shortlist';
const verticalQuery = '(max-width: 1180px)';
const domainOf = (value: string) => value.trim().replace(/^https?:\/\//, '').replace(/^www\./, '').split('/')[0];
// The hero field is the workspace's company search (input id 'website'), with Brandfetch suggestions when configured.
const companyInput = () => document.getElementById('website') as HTMLInputElement | null;
const clamp01 = (t: number) => Math.max(0, Math.min(1, t));
const smoother = (t: number) => { t = clamp01(t); return t * t * t * (t * (t * 6 - 15) + 10); };

function Arrow() { return <span className="pl-arrow" aria-hidden="true">→</span>; }
function Lock() { return <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true"><rect x="3" y="7" width="10" height="7" rx="1" /><path d="M5.5 7V5a2.5 2.5 0 0 1 5 0v2" /></svg>; }
const glyph = {
  ok: <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true"><path d="m4 8 3 3 5-6" /></svg>,
  you: <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true"><path d="M4 8h8M8 4v8" /></svg>,
  fail: <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true"><path d="m5 5 6 6m0-6-6 6" /></svg>,
};
const glyphHtml = {
  ok: '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="m4 8 3 3 5-6"/></svg>',
  you: '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M4 8h8M8 4v8"/></svg>',
  fail: '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="m5 5 6 6m0-6-6 6"/></svg>',
  reuse: '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><path d="M4 7a4 4 0 0 1 7-2l1 1M12 9a4 4 0 0 1-7 2l-1-1"/><path d="M12 3v3H9M4 13v-3h3"/></svg>',
};

type ScrollTo = (y: number, done?: () => void) => void;
function useScrollTo(lenis: RefObject<Lenis | null>): ScrollTo {
  return (y, done) => {
    if (lenis.current) lenis.current.scrollTo(y, { duration: 1.1, onComplete: () => done?.() });
    else { window.scrollTo({ top: y }); done?.(); }
  };
}

/** Words fade up when the heading enters view (Alia's technique). Reduced motion shows them at once; the hidden state
    is also scoped to `prefers-reduced-motion: no-preference` in CSS, so text is never left invisible. */
function Reveal({ as: Tag = 'h2', id, className, reduced, lead, accent, br = false }: { as?: 'h1' | 'h2'; id: string; className?: string; reduced: boolean; lead: string; accent: string; br?: boolean }) {
  const ref = useRef<HTMLHeadingElement>(null);
  const [shown, setShown] = useState(reduced);
  useEffect(() => {
    if (reduced) { setShown(true); return; }
    const node = ref.current; if (!node) return;
    const observer = new IntersectionObserver(entries => { if (entries[0].isIntersecting) { setShown(true); observer.disconnect(); } }, { threshold: 0.35 });
    observer.observe(node); return () => observer.disconnect();
  }, [reduced]);
  let index = 0;
  const words = (text: string) => text.split(' ').map((word, k, all) => <Fragment key={k}><span className="pl-w" style={{ ['--i' as string]: index++ }}>{word}</span>{k < all.length - 1 ? ' ' : null}</Fragment>);
  return <Tag ref={ref} id={id} className={className} data-reveal={shown ? 'shown' : 'hidden'}>{words(lead)}{br ? <br /> : ' '}<span className="pl-accent">{words(accent)}</span></Tag>;
}

function Hero({ reduced, onStart, directoryId, iconLookup, instrumentRef }: { reduced: boolean; onStart: (company: string) => void; directoryId: string; iconLookup: boolean; instrumentRef: RefObject<HTMLDivElement | null> }) {
  const [company, setCompany] = useState('');
  const [invite, setInvite] = useState(true);
  const [shake, setShake] = useState(0);
  const [starting, setStarting] = useState(false);
  const stream = useRef<SignalStream | null>(null);
  const canvas = useRef<HTMLCanvasElement>(null), cardIn = useRef<HTMLFormElement>(null), cardOut = useRef<HTMLElement>(null), streamEl = useRef<HTMLDivElement>(null);
  const rows = useRef<HTMLOListElement>(null), count = useRef<HTMLSpanElement>(null), portOut = useRef<HTMLSpanElement>(null);
  const [on, setOn] = useState(false);
  useEffect(() => {
    const instrument = instrumentRef.current;
    if (!instrument || !canvas.current || !cardIn.current || !cardOut.current || !streamEl.current || !rows.current || !count.current || !portOut.current) return;
    const all = <T extends HTMLElement>(selector: string) => [...instrument.querySelectorAll<T>(selector)];
    let created: SignalStream | null = null, cancelled = false;
    const elements = { instrument, canvas: canvas.current, cardIn: cardIn.current, cardOut: cardOut.current, stream: streamEl.current,
      gates: all('.pl-gate'), gateTops: all('.pl-g-top'), gateBottoms: all('.pl-g-bot'), kept: all('[data-kept]'), checked: all('[data-checked]'),
      count: count.current, rows: rows.current, portOut: portOut.current };
    // Lay the stream out against final type metrics, but never wait long for fonts.
    void Promise.race([document.fonts?.ready ?? Promise.resolve(), new Promise(resolve => window.setTimeout(resolve, 1200))]).then(() => {
      if (cancelled) return;
      created = new SignalStream(elements, reduced, window.matchMedia(verticalQuery));
      stream.current = created; setOn(true);
    });
    return () => { cancelled = true; created?.destroy(); stream.current = null; elements.rows.replaceChildren(); };
  }, [reduced, instrumentRef]);

  const domain = domainOf(company);
  const submit = (event: FormEvent) => {
    event.preventDefault();
    const value = company.trim();
    if (!value) { companyInput()?.focus(); setShake(n => n + 1); return; }
    setStarting(true); stream.current?.burst();
    window.setTimeout(() => onStart(value), reduced ? 0 : 450);
  };
  return <section className="pl-hero" aria-labelledby="pl-hero-title">
    <div className="pl-hero-in pl-wrap">
      <div className="pl-hero-top">
        <div><span className="pl-kicker">Company research for B2B sellers</span>
          <Reveal as="h1" id="pl-hero-title" reduced={reduced} lead="Find who fits." accent="Check why." br /></div>
        <p className="pl-lede">Start with your company. GTM Shortlist checks the web against <strong>your offer</strong> and <strong>your target</strong>, and keeps only the companies it can back with <strong>the exact words on their own site</strong>.</p>
      </div>
      <div className={`pl-instrument${on ? ' on' : ''}`} ref={instrumentRef}>
        <canvas ref={canvas} aria-hidden="true" />
        <form ref={cardIn} className={`pl-card pl-intake${invite ? ' invite' : ''}`} onSubmit={submit} autoComplete="off" noValidate
          onPointerEnter={() => stream.current?.setHover(true)} onPointerLeave={() => stream.current?.setHover(document.activeElement === companyInput())}>
          <label className="pl-label" htmlFor="website">Start with your company</label>
          <div className="pl-controls">
            <div className={`pl-field${shake % 2 ? ' shake' : shake ? ' shake-b' : ''}`} onFocus={() => { setInvite(false); stream.current?.setHover(true); }} onBlur={() => stream.current?.setHover(false)}>
              <CompanySearch value={company} clientId={directoryId} iconLookup={iconLookup} disabled={starting} label="Start with your company" placeholder="Company name or website"
                onChange={value => { setInvite(false); setCompany(value); stream.current?.boost(1100); }} /></div>
            <button className="pl-btn pl-btn-primary pl-btn-block" type="submit" disabled={starting} aria-busy={starting}>{starting ? 'Starting research' : 'Start research'} <Arrow /></button>
          </div>
          <p className="pl-note"><Lock /><span>Nothing runs until you confirm the target.</span></p>
          <span className="pl-port" aria-hidden="true" />
        </form>
        <div className="pl-stream" ref={streamEl} aria-hidden="true">
          {[['01', 'Offer', domain ? `Fits ${domain}` : 'Needs what you sell'], ['02', 'Target', 'Your confirmed buyers'], ['03', 'Evidence', 'Proof on their own site']].map(([n, name, sub]) =>
            <div className="pl-gate" key={name}>
              <div className="pl-g-top"><span className="pl-g-h"><i>{n}</i>{name}</span><span className="pl-g-sub">{sub}</span></div>
              <div className="pl-g-bot"><b data-kept="">0</b><span>kept of <em data-checked="">0</em></span></div>
            </div>)}
        </div>
        <section ref={cardOut} className="pl-card pl-shortlist" aria-label="Example shortlist with synthetic companies">
          <span ref={portOut} className="pl-port" aria-hidden="true" />
          <header><div><strong>Shortlist</strong><small>Example run · synthetic companies</small></div><span ref={count} className="pl-badge" aria-label="Companies kept in this example">0</span></header>
          <ol ref={rows} className="pl-rows" />
          <footer><a href="#evidence">Every row opens to its sources <Arrow /></a></footer>
        </section>
      </div>
    </div>
  </section>;
}

function Story({ reduced, scrollTo }: { reduced: boolean; scrollTo: ScrollTo }) {
  const root = useRef<HTMLElement>(null);
  const total = storyWeights.reduce((a, b) => a + b, 0);
  const starts = storyWeights.reduce<number[]>((acc, _, i) => (acc.push(i ? acc[i - 1] + storyWeights[i - 1] / total : 0), acc), []);
  const jump = (index: number) => {
    const node = root.current; if (!node) return;
    const top = node.getBoundingClientRect().top + window.scrollY;
    scrollTo(top + starts[index] * (node.offsetHeight - window.innerHeight) + 4);
  };
  useEffect(() => {
    const node = root.current; if (!node) return;
    const stages = [...node.querySelectorAll<HTMLElement>('.pl-stage')], steps = [...node.querySelectorAll<HTMLElement>('.pl-stepper li')];
    const fill = node.querySelector<HTMLElement>('.pl-fill'), passage = node.querySelector<HTMLElement>('.pl-passage');
    const words = passage ? [...passage.querySelectorAll<HTMLElement>('.pl-hw')] : [];
    const rows = [...node.querySelectorAll<HTMLElement>('[data-done]')];
    const byId = (id: string) => node.querySelector<HTMLElement>(`[data-part="${id}"]`);
    const setRow = (row: HTMLElement, done: boolean) => {
      const kind = row.dataset.kind as 'ok' | 'you' | 'fail', mark = row.querySelector<HTMLElement>('.pl-mark');
      if (mark) { mark.className = `pl-mark ${done ? kind : 'work'}`; mark.innerHTML = done ? glyphHtml[kind] : ''; }
      row.querySelector('.pl-show')?.classList.toggle('on', done);
    };
    if (reduced) {
      stages.forEach(stage => stage.classList.add('active'));
      node.querySelectorAll('.pl-fade, .pl-show').forEach(el => el.classList.add('on'));
      words.forEach(word => word.style.setProperty('--f', '100%')); rows.forEach(row => setRow(row, true));
      byId('confirm')?.classList.add('pressed'); byId('accept')?.classList.add('primary', 'pressed');
      return;
    }
    let lastIndex = -1;
    const render = () => {
      const top = node.getBoundingClientRect().top + window.scrollY, range = node.offsetHeight - window.innerHeight;
      const p = clamp01((window.scrollY - top) / Math.max(1, range));
      let index = 0; for (let i = 0; i < starts.length; i++) if (p >= starts[i]) index = i;
      const local = clamp01((p - starts[index]) / (storyWeights[index] / total));
      if (index !== lastIndex) {
        stages.forEach((stage, i) => { stage.classList.toggle('active', i === index); stage.setAttribute('aria-hidden', String(i !== index)); });
        lastIndex = index;
      }
      steps.forEach((step, i) => {
        step.classList.toggle('done', i < index || (i === index && local > 0.9)); step.classList.toggle('now', i === index && local <= 0.9);
        const button = step.querySelector('button'); if (i === index) button?.setAttribute('aria-current', 'step'); else button?.removeAttribute('aria-current');
      });
      fill?.style.setProperty('--p', String(Math.min(1, (index + smoother(local)) / (starts.length - 1))));
      stages[index].querySelectorAll<HTMLElement>('.pl-fade').forEach(el => el.classList.toggle('on', local >= Number(el.dataset.at)));
      if (index === 2) { const on = local > 0.6; byId('confirm')?.classList.toggle('pressed', on); byId('confirmed')?.classList.toggle('on', on); }
      if (index === 3) rows.forEach(row => setRow(row, local >= Number(row.dataset.done)));
      if (index === 4) { const k = clamp01((local - 0.05) / 0.6) * words.length; words.forEach((word, i) => word.style.setProperty('--f', `${clamp01(k - i) * 100}%`)); byId('supported')?.classList.toggle('on', local > 0.68); }
      if (index === 5) { const on = local > 0.45, accept = byId('accept'); accept?.classList.toggle('primary', on); accept?.classList.toggle('pressed', on); byId('accepted')?.classList.toggle('on', on); }
    };
    render();
    window.addEventListener('scroll', render, { passive: true }); window.addEventListener('resize', render);
    return () => { window.removeEventListener('scroll', render); window.removeEventListener('resize', render); };
  // starts and total derive from constant weights
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [reduced]);

  const check = <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2.2" aria-hidden="true"><path d="m4 8 3 3 5-6" /></svg>;
  return <section className="pl-story" id="how" ref={root} aria-labelledby="pl-story-title">
    <div className="pl-story-stage pl-wrap">
      <div className="pl-story-head">
        <div><span className="pl-kicker">How it works</span><h2 className="pl-h2" id="pl-story-title">How a shortlist <span className="pl-accent">gets made.</span></h2></div>
        <p>Six steps from your website to a shortlist you can check. You confirm the target before anything runs, and you make the final call.</p>
      </div>
      <nav className="pl-stepper" aria-label="Steps">
        <ol>{storySteps.map((step, i) => <li key={step} className={i === 2 || i === 5 ? 'you' : undefined}>
          <button type="button" aria-label={`Step ${i + 1}: ${step}`} onClick={() => jump(i)}><span className="pl-node"><b>{i + 1}</b>{check}</span><span className="pl-name">{step}</span></button>
        </li>)}</ol>
        <div className="pl-track" aria-hidden="true"><span className="pl-fill"><i /><i /><i /></span></div>
      </nav>
      <div className="pl-stages">
        <article className="pl-stage">
          <div className="pl-stage-text"><span className="pl-step-no">Step 1 of 6</span><h3>Understand your offer</h3><p>We read your website once and draft what you sell. Every word stays editable.</p></div>
          <div className="pl-card pl-ui">
            <div className="pl-ui-head"><span className="pl-label">Offer draft</span><span className="pl-tag">Synthetic example</span></div>
            <div className="pl-ui-row pl-fade" data-at="0"><span className="pl-mark ok">{glyph.ok}</span><div className="pl-grow"><b>relay-studio.example</b><small>Homepage read once and saved</small></div></div>
            <div className="pl-ui-block pl-fade" data-at=".15"><span className="pl-label">What you sell</span><p className="pl-quote">Customer onboarding workflow reviews for B2B software teams.</p></div>
            <div className="pl-ui-block pl-fade" data-at=".3"><span className="pl-label">Who it is for</span><p>Teams that want to improve the journey from signup to first value.</p></div>
            <div className="pl-ui-foot pl-fade" data-at=".45"><span className="pl-btnlike">Edit offer</span><span className="pl-btnlike">Edit target</span></div>
          </div>
        </article>
        <article className="pl-stage">
          <div className="pl-stage-text"><span className="pl-step-no">Step 2 of 6</span><h3>Explore the market</h3><p>Nearby companies and campaign ideas, labelled as observations and hypotheses. Nothing is presented as fact.</p></div>
          <div className="pl-card pl-ui">
            <div className="pl-ui-head"><span className="pl-label">Market</span><span className="pl-tag">Synthetic example</span></div>
            <div className="pl-ui-row pl-fade" data-at="0"><span className="pl-ini">SH</span><div className="pl-grow"><b>signalhouse.example</b><small>Observation · publishes onboarding case studies</small></div><span className="pl-pill ok">Saved</span></div>
            <div className="pl-ui-row pl-fade" data-at=".2"><span className="pl-ini">TW</span><div className="pl-grow"><b>tidewater.example</b><small>Observation · sells to the same buyers</small></div><span className="pl-pill ok">Saved</span></div>
            <div className="pl-ui-row pl-fade" data-at=".4"><span className="pl-ini">PL</span><div className="pl-grow"><b>pagelane.example</b><small>Page could not be read</small></div><span className="pl-pill fail">Failed</span></div>
            <div className="pl-ui-row pl-fade pl-last" data-at=".6"><span className="pl-ini">H1</span><div className="pl-grow"><b>Time-to-value audit</b><small>Campaign idea · mid-size SaaS with self-serve signup</small></div><span className="pl-pill hyp">Hypothesis</span></div>
          </div>
        </article>
        <article className="pl-stage">
          <div className="pl-stage-text"><span className="pl-step-no">Step 3 of 6 · You decide</span><h3>Confirm the target</h3><p>No company search runs until you confirm who you want to reach and what counts as evidence.</p></div>
          <div className="pl-card pl-ui">
            <div className="pl-ui-head"><span className="pl-label">Your target</span><span className="pl-pill you">Needs you</span></div>
            <ul className="pl-criteria"><li>B2B software teams with an onboarding product or flow</li><li>A company-owned page that describes that product</li><li>Exclude directories and consumer-only products</li></ul>
            <div className="pl-ui-foot"><span className="pl-btnlike primary" data-part="confirm">Confirm target <Arrow /></span><span className="pl-btnlike">Edit</span><span className="pl-pill you pl-show" data-part="confirmed">{glyph.ok}Confirmed by you</span></div>
          </div>
        </article>
        <article className="pl-stage">
          <div className="pl-stage-text"><span className="pl-step-no">Step 4 of 6</span><h3>Discover companies</h3><p>Candidates are checked against your confirmed criteria. Only the ones that pass are researched, and nothing is padded to look busy.</p></div>
          <div className="pl-card pl-ui pl-discover">
            <div className="pl-ui-head"><span className="pl-label">Candidates</span><span className="pl-tag">Synthetic example</span></div>
            <div className="pl-ui-row pl-fade" data-at="0" data-done=".25" data-kind="ok"><span className="pl-mark work" /><span className="pl-ini">NC</span><div className="pl-grow"><b>Northstar Cloud</b><small>northstar.example · onboarding product page</small></div><span className="pl-pill ok pl-show">Fits</span></div>
            <div className="pl-ui-row pl-fade" data-at=".25" data-done=".5" data-kind="you"><span className="pl-mark work" /><span className="pl-ini">BH</span><div className="pl-grow"><b>Brightpath HR</b><small>brightpath.example · ownership unclear</small></div><span className="pl-pill you pl-show">Needs a call</span></div>
            <div className="pl-ui-row pl-fade pl-last" data-at=".5" data-done=".75" data-kind="fail"><span className="pl-mark work" /><span className="pl-ini">QS</span><div className="pl-grow"><b>Quarry Stack</b><small>quarry.example · consumer-only</small></div><span className="pl-pill fail pl-show">Excluded</span></div>
            <div className="pl-ui-foot"><span className="pl-src">Only companies marked Fits move on to research.</span></div>
          </div>
        </article>
        <article className="pl-stage">
          <div className="pl-stage-text"><span className="pl-step-no">Step 5 of 6</span><h3>Inspect the evidence</h3><p>Every claim opens to the exact words on the company's own page. What we could not find stays marked as unknown.</p></div>
          <div className="pl-card pl-ui">
            <div className="pl-ui-head"><span className="pl-label">Finding</span><span className="pl-pill ok pl-show" data-part="supported">Supported in source</span></div>
            <div className="pl-ui-block"><b>Northstar Cloud offers a B2B onboarding product</b></div>
            <p className="pl-passage">“{examplePassage.split(' ').map((word, i) => <span key={i}><span className="pl-hw">{word}</span>{' '}</span>)}”</p>
            <p className="pl-src">Synthetic passage · northstar.example/product · invented for this example</p>
            <div className="pl-ui-row pl-fade pl-last pl-unknown" data-at=".75"><span className="pl-mark idle" /><div className="pl-grow"><b>Unknown</b><small>Who owns the onboarding budget is not established.</small></div></div>
            <div className="pl-ui-foot"><span className="pl-btnlike">Open the saved page <Arrow /></span></div>
          </div>
        </article>
        <article className="pl-stage">
          <div className="pl-stage-text"><span className="pl-step-no">Step 6 of 6 · You decide</span><h3>Make the call</h3><p>Fit is an assessment, not buying intent. Accepting a company is your decision, saved separately from the model's.</p></div>
          <div className="pl-card pl-ui">
            <div className="pl-ui-head"><span className="pl-label">Your review</span><span className="pl-tag">Synthetic example</span></div>
            <div className="pl-ui-block"><b>Northstar Cloud</b><p className="pl-src">Evidence: describes a business onboarding product. Unknown: budget ownership.</p></div>
            <p className="pl-fade pl-draft-line" data-at=".7">Optional: <span className="pl-accent">draft an email that cites this source <Arrow /></span></p>
            <div className="pl-ui-foot"><span className="pl-btnlike" data-part="accept">Accept</span><span className="pl-btnlike">Not a fit</span><span className="pl-btnlike">Needs a conversation</span><span className="pl-pill ok pl-show" data-part="accepted">{glyph.ok}Accepted by you</span></div>
          </div>
        </article>
      </div>
    </div>
  </section>;
}

function Evidence({ reduced }: { reduced: boolean }) {
  const grid = useRef<HTMLDivElement>(null);
  const [on, setOn] = useState(reduced);
  const [hot, setHot] = useState(0);
  useEffect(() => {
    if (reduced) { setOn(true); return; }
    const node = grid.current; if (!node) return;
    const observer = new IntersectionObserver(entries => { if (entries[0].isIntersecting) { setOn(true); observer.disconnect(); } }, { threshold: 0.3 });
    observer.observe(node); return () => observer.disconnect();
  }, [reduced]);
  const part = (n: number) => hot === n ? ' hot' : '';
  const notes = [
    { n: 1, quote: '“…helps business teams manage…”', source: 'northstar.example/product · exact words saved' },
    { n: 2, quote: '“…customer onboarding, from the first welcome…”', source: 'Same page · highlighted in context' },
    { n: 3, quote: 'Unknown: budget owner', source: 'Not on their site, so it needs a conversation' },
  ];
  return <section className={`pl-section pl-ev${on ? ' on' : ''}`} id="evidence" aria-labelledby="pl-ev-title">
    <div className="pl-wrap">
      <div className="pl-section-head">
        <div><span className="pl-kicker">Evidence</span><Reveal id="pl-ev-title" className="pl-h2" reduced={reduced} lead="Every row opens to" accent="its sources." /></div>
        <p>Claims are tied to the exact words on the company's own pages, with the page and the date it was read. Unknowns stay visible, so you know what still needs a conversation.</p>
      </div>
      <div className="pl-ev-grid" ref={grid}>
        <div>
          <span className="pl-card pl-chip"><span className="pl-mark ok">{glyph.ok}</span><b>northstar.example</b><span>3 sources · synthetic example</span></span>
          <p className="pl-sentence">Northstar Cloud helps <span className={`pl-hl${part(1)}`}>business teams</span><sup>1</sup> manage <span className={`pl-hl second${part(2)}`}>customer onboarding</span><sup>2</sup>, from the first welcome to the handover. <span className={`pl-unk${part(3)}`}>Who owns that budget is not established.</span><sup className="u">3</sup></p>
        </div>
        <ol className="pl-notes">{notes.map(note => <li key={note.n} className={note.n === 3 ? 'unknown' : undefined} onPointerEnter={() => setHot(note.n)} onPointerLeave={() => setHot(0)}>
          <span className="pl-num">{note.n}</span><span>{note.quote}</span><small>{note.source}</small></li>)}</ol>
      </div>
    </div>
  </section>;
}

const stateWord: Record<FeedState, string> = { ok: 'Completed', fail: 'Failed', reuse: 'Reused', work: 'Working' };
function Checkpoints({ reduced }: { reduced: boolean }) {
  const list = useRef<HTMLOListElement>(null);
  useEffect(() => {
    const feed = list.current; if (!feed) return;
    let index = 0, clock = 16 * 3600 + 41 * 60 + 20, timer = 0, working: HTMLLIElement | null = null;
    const stamp = () => { clock += 4 + ((Math.random() * 5) | 0); return [clock / 3600 | 0, (clock % 3600) / 60 | 0, clock % 60].map(n => String(n).padStart(2, '0')).join(':'); };
    const fill = (li: HTMLLIElement, state: FeedState, text: string) => {
      li.innerHTML = `<span class="pl-mark ${state}">${state === 'work' ? '' : glyphHtml[state]}</span><span class="pl-txt"><span class="pl-st ${state}">${stateWord[state]}</span> · </span><time>${stamp()}</time>`;
      li.querySelector('.pl-txt')?.append(text);
    };
    const row = (state: FeedState, text: string, animate: boolean) => {
      const li = document.createElement('li'); if (animate) li.className = 'new'; fill(li, state, text);
      feed.prepend(li); while (feed.children.length > 7) feed.lastChild?.remove(); return li;
    };
    const resolve = (li: HTMLLIElement, state: FeedState, text: string) => {
      const time = li.querySelector('time')?.textContent ?? '';
      fill(li, state, text); const t = li.querySelector('time'); if (t) t.textContent = time;
    };
    for (let i = 0; i < 5; i++) { const step = exampleCheckpoints[index++]; row(step.state, step.done, false); }
    if (reduced) return () => feed.replaceChildren();
    working = row('work', exampleCheckpoints[index % exampleCheckpoints.length].working, false);
    const tick = () => {
      const step = exampleCheckpoints[index % exampleCheckpoints.length]; index++;
      if (working) { resolve(working, step.state, step.done); working = null; }
      timer = window.setTimeout(() => { working = row('work', exampleCheckpoints[index % exampleCheckpoints.length].working, true); timer = window.setTimeout(tick, 1600); }, 700);
    };
    const observer = new IntersectionObserver(entries => { window.clearTimeout(timer); if (entries[0].isIntersecting) timer = window.setTimeout(tick, 1200); }, { threshold: 0.4 });
    observer.observe(feed);
    return () => { observer.disconnect(); window.clearTimeout(timer); feed.replaceChildren(); };
  }, [reduced]);
  return <div className="pl-card pl-feed" aria-label="Example checkpoints">
    <header><span className="pl-label">Checkpoints</span><span className="pl-live-dot">Example run</span></header>
    <ol ref={list} />
  </div>;
}

function Closing({ reduced, onStart }: { reduced: boolean; onStart: (company: string) => void }) {
  const [company, setCompany] = useState('');
  const [shake, setShake] = useState(0);
  const field = useRef<HTMLInputElement>(null);
  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (!company.trim()) { field.current?.focus(); setShake(n => n + 1); return; }
    onStart(company.trim());
  };
  return <section className="pl-closing" aria-labelledby="pl-closing-title">
    <div className="pl-wrap pl-closing-in">
      <span className="pl-kicker">Start with your company</span>
      <Reveal id="pl-closing-title" reduced={reduced} lead="Find who fits." accent="Check why." br />
      <p>Enter your company. You confirm the target, then every company that reaches your shortlist comes with its sources.</p>
      <form onSubmit={submit} autoComplete="off" noValidate>
        <div className={`pl-field${shake % 2 ? ' shake' : shake ? ' shake-b' : ''}`}><input ref={field} aria-label="Company name or website" placeholder="yourcompany.com" spellCheck={false} autoCapitalize="off" maxLength={300} value={company} onChange={event => setCompany(event.target.value)} /></div>
        <button className="pl-btn pl-btn-primary" type="submit">Start research <Arrow /></button>
      </form>
      <p className="pl-note"><Lock /><span>Nothing runs until you confirm the target.</span></p>
    </div>
  </section>;
}

/** The public landing page for hosted visitors without a session. It makes no research API or provider requests;
    company suggestions contact Brandfetch only when the installation configures a public client ID. */
export function PublicLanding({ onStart, onSignIn, directoryId, iconLookup = false }: { onStart: (company: string) => void; onSignIn: () => void; directoryId: string; iconLookup?: boolean }) {
  const reduced = usePrefersReducedMotion();
  const lenis = useLenis(!reduced);
  const scrollTo = useScrollTo(lenis);
  const instrument = useRef<HTMLDivElement>(null);
  const focusField = () => {
    const node = instrument.current; if (!node) return;
    const header = parseFloat(getComputedStyle(document.documentElement).fontSize) * 6;
    const y = Math.max(0, node.getBoundingClientRect().top + window.scrollY - header);
    scrollTo(y, () => companyInput()?.focus({ preventScroll: true }));
  };
  const startLink = (label: string, extra = '') => <a className={`pl-btn pl-btn-primary${extra}`} href="#website" onClick={event => { event.preventDefault(); focusField(); }}>{label} <Arrow /></a>;
  const signIn = (className: string, label = 'Sign in') => <a className={className} href="?auth=signin" onClick={event => { event.preventDefault(); onSignIn(); }}>{label}</a>;
  useEffect(() => { document.title = 'GTM Shortlist · Find who fits. Check why.'; return () => { document.title = 'GTM Shortlist'; }; }, []);
  return <div className="pl" id="top">
    <a className="pl-skip" href="#website" onClick={event => { event.preventDefault(); companyInput()?.focus(); }}>Skip to company field</a>
    <header className="pl-site-head">
      <div className="pl-wrap">
        <a className="pl-wordmark" href="#top"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" aria-hidden="true"><path d="M3 6h12M3 12h8M3 18h5" /><circle cx="17.5" cy="15.5" r="3.5" stroke="#b4501c" /><path d="m20 18 2.5 2.5" stroke="#b4501c" /></svg>GTM Shortlist</a>
        <nav aria-label="Sections"><a href="#how">How it works</a><a href="#evidence">Evidence</a><a href="#open">Open source</a></nav>
        {signIn('pl-signin')}
        <a className="pl-btn pl-btn-primary pl-btn-sm" href="#website" onClick={event => { event.preventDefault(); focusField(); }}><span className="pl-long">Start research</span><span className="pl-short">Start</span> <Arrow /></a>
      </div>
    </header>
    <main>
      <Hero reduced={reduced} onStart={onStart} directoryId={directoryId} iconLookup={iconLookup} instrumentRef={instrument} />
      <Story reduced={reduced} scrollTo={scrollTo} />
      <Evidence reduced={reduced} />
      <section className="pl-section" id="live" aria-labelledby="pl-live-title">
        <div className="pl-wrap pl-live">
          <div><span className="pl-kicker">While it runs</span><Reveal id="pl-live-title" className="pl-h2" reduced={reduced} lead="Watch the work," accent="not a spinner." />
            <p>Every search, page read and check is saved as it happens. You see what passed, what failed and why, with real timestamps. No made-up percentages, and you can leave the page at any time.</p>
            <a className="pl-btn pl-btn-ghost" href="?demo=1">Try the interactive demo <Arrow /></a></div>
          <Checkpoints reduced={reduced} />
        </div>
      </section>
      <section className="pl-section" id="open" aria-labelledby="pl-open-title">
        <div className="pl-wrap">
          <div className="pl-section-head">
            <div><span className="pl-kicker">Two ways to run it</span><Reveal id="pl-open-title" className="pl-h2" reduced={reduced} lead="Open source core." accent="Hosted if you want it." /></div>
            <p>The research engine is open source. Run it with your own keys, or use the hosted version and keep your research in an account.</p>
          </div>
          <div className="pl-duo">
            <div className="pl-card"><span className="pl-label">Open source</span><h3>Run it yourself</h3><ul><li>MIT-licensed web app, API and worker</li><li>Your own search and model keys</li><li>Research stays in your own database</li></ul><a className="pl-btn pl-btn-ghost" href={sourceCodeUrl} target="_blank" rel="noreferrer">Read the setup guide <Arrow /></a></div>
            <div className="pl-card"><span className="pl-label">Hosted</span><h3>Use the hosted version</h3><ul><li>An account that keeps your saved research</li><li>Research credits instead of provider keys</li><li>An optional call to talk through your shortlist</li></ul>{startLink('Start research')}</div>
          </div>
        </div>
      </section>
      <Closing reduced={reduced} onStart={onStart} />
    </main>
    <footer className="pl-footer"><div className="pl-wrap"><div className="pl-big">GTM Shortlist</div><div className="pl-links"><span>Open-source company research</span><a href={sourceCodeUrl} target="_blank" rel="noreferrer">Source code</a>{signIn('', 'Sign in')}<a href="?demo=1">Interactive demo</a></div></div></footer>
  </div>;
}
