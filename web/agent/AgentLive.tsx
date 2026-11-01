import { useEffect, useState } from 'react';
import type { ReactNode } from 'react';
import { SiteIcon } from '../SiteIcon';
import { isActive } from './agent-api';
import type { AgentEvent, AgentRun, AgentRunView, Company } from './agent-api';
import './agent-live.css';

/** The agent's six steps, in the order a run reaches them. Investigation, the skeptic and the verdict repeat per
 *  company, so a later step can light up while an earlier one is still working on the next company. */
export const STAGES = [
  { label: 'Read your site', by: 'Muse Spark' },
  { label: 'Map competitors', by: 'Muse Spark' },
  { label: 'Find hiring signals', by: 'Job boards' },
  { label: 'Investigate', by: 'Muse Spark' },
  { label: 'Check every quote', by: 'Muse Spark Open' },
  { label: 'Decide and write', by: 'Fixed rules' },
] as const;
const STAGE_INDEX: Record<string, number> = { seller: 0, competitors: 1, discovery: 2, investigation: 3, skeptic: 4, verdict: 5, outreach: 5 };
export const stageOf = (event: AgentEvent) => STAGE_INDEX[event.stage] ?? -1;
const STAGE_TAG: Record<string, string> = { seller: 'Site', competitors: 'Competitors', discovery: 'Discovery', investigation: 'Investigate',
  skeptic: 'Skeptic', verdict: 'Verdict', outreach: 'Opener', overrides: 'Your change', run: 'Run' };

type StepState = 'done' | 'active' | 'todo';
export function stepStates(events: AgentEvent[], running: boolean): StepState[] {
  if (!running) {
    const seen = new Set(events.map(stageOf).filter(index => index >= 0));
    return STAGES.map((_, index) => seen.has(index) ? 'done' : 'todo');
  }
  // Companies run in parallel and some finish early (an unreadable site goes straight to a verdict), so a step is done
  // only when every company still in progress is past it: the frontier is the furthest-behind company's step.
  const latest = new Map<string, number>();
  const decided = new Set<string>();
  for (const event of events) {
    if (!event.company) continue;
    if (event.stage === 'verdict') decided.add(event.company);
    const index = stageOf(event);
    if (index >= 3) latest.set(event.company, index);
  }
  const working = [...latest].filter(([company]) => !decided.has(company)).map(([, index]) => index);
  const frontier = working.length ? Math.min(...working) : [...events].reverse().map(stageOf).find(index => index >= 0) ?? 0;
  return STAGES.map((_, index) => index < frontier ? 'done' : index === frontier ? 'active' : 'todo');
}

export function Stepper({ states, compact = false }: { states: StepState[]; compact?: boolean }) {
  return <ol className={`agent-stepper${compact ? ' is-compact' : ''}`}>
    {STAGES.map((stage, index) => <li key={stage.label} className={`step-${states[index]}`} aria-current={states[index] === 'active' ? 'step' : undefined}>
      <span className="agent-step-dot" aria-hidden="true">{states[index] === 'done' ? '✓' : index + 1}</span>
      <span className="agent-step-text"><span>{stage.label}</span></span>
      <span className="sr-only">{states[index] === 'done' ? ', done' : states[index] === 'active' ? ', working now' : ', not started'}</span>
    </li>)}
  </ol>;
}

function useNow(running: boolean) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (!running) return;
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, [running]);
  return now;
}

const clock = (ms: number) => {
  const seconds = Math.max(0, Math.round(ms / 1000));
  return seconds < 60 ? `${seconds}s` : `${Math.floor(seconds / 60)}m ${String(seconds % 60).padStart(2, '0')}s`;
};

export function doneText(run: AgentRun) {
  const count = (kind: string) => run.companies.filter(c => c.verdict?.kind === kind).length;
  return `Done: ${count('shortlisted')} shortlisted, ${count('needs_look')} needs a look, ${count('rejected')} rejected`;
}

/** Pinned under the page header while you scroll: what the agent is doing right now, how far it got, and what it cost. */
export function Monitor({ view, events, feedOpen, onFeed }: { view: AgentRunView; events: AgentEvent[]; feedOpen: boolean; onFeed: () => void }) {
  const run = view.run;
  const running = isActive(view.status);
  const now = useNow(running);
  const latest = events.at(-1);
  const text = running ? latest?.message ?? 'Starting'
    : view.status === 'needs_choice' ? 'Waiting for your choice'
      : view.status === 'failed' ? 'Stopped' : doneText(run);
  const decided = run.companies.filter(c => c.verdict).length;
  const supported = run.companies.reduce((sum, c) => sum + c.decisions.filter(d => d.decision === 'supports').length, 0);
  const checked = run.companies.reduce((sum, c) => sum + c.decisions.length, 0);
  const elapsed = running ? now - new Date(view.created_at).getTime() : run.telemetry.elapsed_ms;
  return <section className={`agent-monitor status-${view.status}${running ? ' is-live' : ''}`} aria-label="What the agent is doing">
    <div className="agent-monitor-row">
      <div className="agent-monitor-now">
        <p className="agent-monitor-label">{running ? <><span className="agent-live-dot" aria-hidden="true" />Working now</> : view.status === 'complete' ? 'Finished' : 'Paused'}
          {latest?.company && running && <span className="agent-monitor-company">{latest.company}</span>}</p>
        <p className="agent-status" role="status" aria-live="polite">{text}</p>
      </div>
      <dl className="agent-monitor-stats">
        <div><dt>Time</dt><dd>{clock(elapsed)}</dd></div>
        <div><dt>Shortlisted</dt><dd>{run.companies.filter(c => c.verdict?.kind === 'shortlisted').length}<span>/{run.company_count}</span></dd></div>
        <div><dt>Checked</dt><dd>{decided}</dd></div>
        <div><dt>Quotes kept</dt><dd>{supported}<span>/{checked}</span></dd></div>
        <div><dt>Searches</dt><dd>{run.telemetry.searches}</dd></div>
        <div><dt>Cost</dt><dd>${run.telemetry.cost_usd.toFixed(2)}</dd></div>
      </dl>
      <button type="button" className="agent-feed-toggle" aria-expanded={feedOpen} aria-controls="agent-feed" onClick={onFeed}>
        {feedOpen ? 'Hide steps' : `Steps (${events.length})`}</button>
    </div>
    <Stepper states={stepStates(events, running)} />
  </section>;
}

/** The company to name before a step's message, unless the message already starts with it. */
export const prefixOf = (event: AgentEvent) => event.company && !event.message.startsWith(event.company) ? event.company : null;

const time = (value: string) => new Intl.DateTimeFormat(undefined, { hour: '2-digit', minute: '2-digit', second: '2-digit' }).format(new Date(value));

/** Every step, newest first. A side rail on wide screens; a sheet from the monitor's Steps button on small ones. */
export function Feed({ events, open, onClose, live }: { events: AgentEvent[]; open: boolean; onClose: () => void; live: boolean }) {
  // A finished search shows its last few steps; everything is one click away.
  const [all, setAll] = useState(false);
  const shown = all || live ? 150 : 8;
  return <aside id="agent-feed" className={`agent-rail${open ? ' is-open' : ''}`} aria-label="Activity">
    <section className="agent-log">
      <div className="agent-log-head"><h2>Activity</h2><span>{events.length} steps</span>
        <button type="button" className="agent-feed-close" aria-label="Close steps" onClick={onClose}>Close</button></div>
      {events.length === 0 ? <p className="agent-log-empty">Waiting for the first step.</p>
        : <ol>{[...events].reverse().slice(0, shown).map(event => <li key={event.seq} className={`level-${event.level}`}>
          <span className={`agent-log-tag stage-${event.stage}`}>{STAGE_TAG[event.stage] ?? event.stage}</span>
          <p>{prefixOf(event) && <strong>{prefixOf(event)} </strong>}{event.message}</p>
          <time dateTime={event.at}>{time(event.at)}</time>
        </li>)}</ol>}
      {!live && !all && events.length > shown && <button type="button" className="agent-log-more" onClick={() => setAll(true)}>
        Show all {events.length} steps</button>}
    </section>
  </aside>;
}

/** A company still being researched, with the last thing the agent did for it. */
export function WorkingCard({ company, events }: { company: Company; events: AgentEvent[] }) {
  const mine = events.filter(event => event.company === company.domain);
  const latest = mine.at(-1);
  const stage = latest ? STAGES[Math.max(0, stageOf(latest))] : null;
  return <article className="agent-working-card" aria-label={`${company.domain}, in progress`}>
    <header><SiteIcon lookup domain={company.domain} fallback={(company.name || company.domain).slice(0, 1).toUpperCase()} className="agent-logo" />
      <h4>{company.name || company.domain}</h4><span className="agent-live-dot" aria-hidden="true" /></header>
    <ol className="agent-track" aria-hidden="true">{['Investigate', 'Skeptic', 'Verdict'].map((label, index) => {
      const at = latest ? Math.max(0, stageOf(latest) - 3) : -1;
      return <li key={label} className={index < at ? 'is-done' : index === at ? 'is-now' : ''}><span />{label}</li>;
    })}</ol>
    <p className="agent-working-step">{stage ? stage.label : 'Queued'}</p>
    <p className="agent-working-message">{latest?.message ?? 'Waiting for its turn.'}</p>
    {mine.length > 0 && <p className="agent-working-count">
      <b>{mine.filter(e => e.message.startsWith('Read ')).length}</b> pages read · <b>{mine.filter(e => e.message.startsWith('Searched ')).length}</b> searches</p>}
  </article>;
}

export function Working({ companies, events }: { companies: Company[]; events: AgentEvent[] }): ReactNode {
  if (!companies.length) return null;
  return <section className="agent-working-grid" aria-label="Being researched now">
    {companies.map(company => <WorkingCard key={company.domain} company={company} events={events} />)}
  </section>;
}


type Tile = { key: string; kind: 'page' | 'search' | 'hiring' | 'rival'; domain?: string; title: string; detail?: string; board?: string };
const BOARDS: [RegExp, string][] = [[/lever\.co/i, 'Lever'], [/greenhouse\.io/i, 'Greenhouse'], [/ashbyhq\.com/i, 'Ashby']];
const hostOf = (url: string) => { try { return new URL(url).hostname.replace(/^www\./, ''); } catch { return ''; } };
const pathOf = (url: string) => { try { const path = new URL(url).pathname; return path === '/' ? 'homepage' : path; } catch { return url; } };

/** What the agent has touched so far, as tiles, read from its own step messages and the run's saved competitors. */
export function tilesOf(run: AgentRun, events: AgentEvent[]): Tile[] {
  const tiles: Tile[] = [];
  for (const event of events) {
    const read = /^Read (?:your homepage \()?(https?:\/\/[^\s)]+)/.exec(event.message);
    const searched = /^Searched "(.+)"/.exec(event.message);
    const hiring = /^Confirmed open on (\w+): (.+) \(([^()]+)\)$/.exec(event.message);
    if (read) tiles.push({ key: `p${event.seq}`, kind: 'page', domain: hostOf(read[1]), title: pathOf(read[1]), detail: hostOf(read[1]) });
    else if (searched) tiles.push({ key: `s${event.seq}`, kind: 'search', title: searched[1].replace(/site:\S+\s*/g, '').trim() || searched[1],
      board: BOARDS.find(([pattern]) => pattern.test(searched[1]))?.[1] });
    else if (hiring) tiles.push({ key: `h${event.seq}`, kind: 'hiring', title: hiring[3], detail: hiring[2], board: hiring[1] });
  }
  for (const rival of run.competitors.filter(c => c.classification === 'direct'))
    tiles.push({ key: `r${rival.domain}`, kind: 'rival', domain: rival.domain, title: rival.name, detail: 'competitor' });
  return tiles;
}

const KIND_LABEL = { page: 'Read', search: 'Searched', hiring: 'Hiring now', rival: 'Competitor' } as const;

function Wall({ tiles }: { tiles: Tile[] }) {
  if (!tiles.length) return null;
  return <ul className="agent-wall" aria-label="Found so far">
    {tiles.slice(-12).map(tile => <li key={tile.key} className={`agent-tile tile-${tile.kind}`}>
      {tile.domain ? <SiteIcon lookup domain={tile.domain} fallback={(tile.domain ?? tile.title).slice(0, 1).toUpperCase()} className="agent-logo agent-tile-logo" />
        : <span className="agent-tile-glyph" aria-hidden="true">{tile.kind === 'hiring' ? '●' : '⌕'}</span>}
      <span className="agent-tile-text"><small>{KIND_LABEL[tile.kind]}{tile.board ? ` · ${tile.board}` : ''}</small>
        <strong>{tile.title}</strong>{tile.detail && tile.kind !== 'page' && <em>{tile.detail}</em>}</span>
    </li>)}
  </ul>;
}

const EARLY = new Set(['run', 'seller', 'competitors', 'discovery']);
const HEADLINE = ['Reading your site', 'Mapping your competitors', 'Finding companies with hiring signals'];

/** Before the first company arrives: what the agent is doing right now and what it has learned so far, at the top of
 *  the page, so the early minutes never look stuck. */
export function EarlySteps({ run, events }: { run: AgentRun; events: AgentEvent[] }) {
  const steps = events.filter(event => EARLY.has(event.stage)).slice(-7);
  const current = [...events].reverse().map(stageOf).find(index => index >= 0) ?? 0;
  const profile = run.profile;
  const competitors = run.competitors.filter(c => c.classification === 'direct');
  return <section className="agent-early" aria-label="Working now" aria-live="polite">
    <div className="agent-early-head"><span className="agent-spinner" aria-hidden="true" />
      <h2>{HEADLINE[Math.min(current, 2)]}</h2><span className="agent-early-step">Step {Math.min(current, 2) + 1} of 6</span></div>
    <ol className="agent-early-list">{steps.map((event, index) => <li key={event.seq} className={index === steps.length - 1 ? 'is-now' : 'is-done'}>
      <span className="agent-early-mark" aria-hidden="true" />{event.message}</li>)}</ol>
    <Wall tiles={tilesOf(run, events)} />
    {(profile?.offer || competitors.length > 0) && <div className="agent-early-learned">
      <p className="agent-pitch-label">What it has learned so far</p>
      {profile?.offer && <p><span>You sell</span> {profile.offer.value}</p>}
      {profile?.buyer && <p><span>To</span> {profile.buyer.value}</p>}
      {competitors.length > 0 && <p><span>Competitors</span> {competitors.slice(0, 6).map(c => <b key={c.domain} className="agent-early-chip">{c.name}</b>)}</p>}
    </div>}
  </section>;
}
