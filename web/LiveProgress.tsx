import { useEffect, useState } from 'react';
import type { Run } from './api';
import { useSiteLabel } from './SampleData';
import './LiveProgress.css';

type Event = Run['progress']['events'][number];
type Kind = 'search' | 'page' | 'model';
// Seconds per step until this run has timed its own; its finished steps replace these.
const TYPICAL: Record<Kind, number> = { search: 15, page: 10, model: 45 };
const PER_COMPANY: Kind[] = ['page', 'page', 'page', 'model', 'model'];

const kindOf = (label: string): Kind | null => /^Searching|competitors/i.test(label) ? 'search'
  : /^Reading/i.test(label) ? 'page' : /Assessing|Checking|Understanding|Proposing/i.test(label) ? 'model' : null;
const seconds = (event: Event) => new Date(event.created_at).getTime() / 1000;

/** Typical step durations measured from this run's own started and finished events. */
function measured(events: Event[]) {
  const totals: Record<Kind, number[]> = { search: [], page: [], model: [] };
  events.forEach((event, index) => {
    const kind = kindOf(event.label);
    if (!kind || event.state !== 'succeeded') return;
    const start = events.slice(0, index).reverse().find(item => item.label === event.label && item.state === 'started');
    if (start) totals[kind].push(Math.max(1, seconds(event) - seconds(start)));
  });
  return (kind: Kind) => totals[kind].length ? totals[kind].reduce((a, b) => a + b, 0) / totals[kind].length : TYPICAL[kind];
}

/** Remaining work the saved run already implies, until the user's next turn. Never a promise. */
export function estimate(run: Run, current: number, now: number) {
  const events = run.progress.events;
  const typical = measured(events);
  const done = (kind: Kind) => events.filter(event => event.state === 'succeeded' && kindOf(event.label) === kind).length;
  const limit = run.progress.company_limit ?? 1;
  const left: Kind[] = current === 0 ? ['model', 'search', 'model'] : current === 1 ? ['model']
    : current === 3 ? [...Array(Math.max(0, 2 - done('search'))).fill('search'), ...Array(limit).fill(PER_COMPANY).flat()]
      : current === 4 ? Array(Math.max(1, limit - run.progress.companies)).fill(PER_COMPANY).flat() : [];
  if (!left.length) return null;
  const latest = events.at(-1);
  const running = latest?.state === 'started' ? Math.max(0, now / 1000 - seconds(latest)) : 0;
  const total = Math.max(0, left.reduce((sum, kind) => sum + typical(kind), 0) - running);
  const finished = events.filter(event => event.state === 'succeeded' && kindOf(event.label)).length;
  return { seconds: total, share: finished / (finished + left.length), next: current <= 1 ? 'your confirmation' : 'your review' };
}

const clock = (value: number) => `${Math.floor(value / 60)}:${String(Math.floor(value % 60)).padStart(2, '0')}`;

export function LiveProgress({ run, current }: { run: Run; current: number }) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => { const timer = window.setInterval(() => setNow(Date.now()), 1000); return () => window.clearInterval(timer); }, []);
  const label = useSiteLabel();
  const latest = run.progress.events.at(-1);
  const active = latest?.state === 'started' ? latest : undefined;
  const since = latest ? Math.max(0, (now - new Date(latest.created_at).getTime()) / 1000) : 0;
  const step = run.status === 'queued' ? 'Waiting for the research worker' : active ? label(active.label) : 'Saving progress and preparing the next step';
  const reading = active && /^Reading /.test(active.label);
  const eta = run.status === 'running' ? estimate(run, current, now) : null;
  const found = (run.selection ?? []).slice(0, 6);
  return <div className="live-progress">
    <div className="live-rail" aria-hidden="true"><span style={{ width: `${Math.round(Math.max(0.04, eta?.share ?? 0.04) * 100)}%` }} /></div>
    <p className="live-step"><span className="live-pulse" aria-hidden="true" /><span className={reading ? 'live-scan' : undefined}>{step}</span><span className="live-elapsed" aria-label={`${Math.floor(since)} seconds on this step`}>{clock(since)}</span></p>
    {since > 90 && <p className="checkpoint-detail">Still working on this step. Slow websites and models can take a few minutes.</p>}
    {eta && <p className="live-eta">{eta.seconds < 45 ? 'Less than a minute' : `About ${Math.ceil(eta.seconds / 60)} min`} until {eta.next} · estimate</p>}
    {found.length > 0 && <ul className="live-found" aria-label="Companies found so far">{found.map(candidate => <li key={candidate.domain}>{label(candidate.domain)}</li>)}</ul>}
  </div>;
}
