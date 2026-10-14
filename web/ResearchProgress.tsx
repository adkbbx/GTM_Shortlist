import type { Run } from './api';

const time = (value: string) => new Intl.DateTimeFormat(undefined, {
  hour: '2-digit', minute: '2-digit', second: '2-digit',
}).format(new Date(value));

function CheckpointIcon({ state, active }: { state: string; active: boolean }) {
  return <svg className={`checkpoint-icon ${active ? 'is-active' : ''}`} width="20" height="20" viewBox="0 0 24 24" fill="none" aria-hidden="true">
    <circle cx="12" cy="12" r="9" stroke="currentColor" strokeWidth="1.3" />
    {state === 'succeeded' || state === 'reused' ? <path d="m7 12 3 3 7-7" stroke="currentColor" strokeWidth="1.5" />
      : state === 'failed' ? <path d="m8 8 8 8m0-8-8 8" stroke="currentColor" strokeWidth="1.5" />
        : <circle cx="12" cy="12" r="2" fill="currentColor" />}
  </svg>;
}

export function ResearchProgress({ run, connected = true }: { run: Run; connected?: boolean }) {
  const progress = run.progress;
  const pending = run.status === 'queued' || run.status === 'running';
  const latest = progress.events.at(-1);
  // Pair a started step with its actual final observation, keeping its latest state.
  const steps = new Map<string, typeof progress.events[number]>();
  progress.events.forEach(event => steps.set(`${event.phase}:${event.label}`, event));
  const checkpoints = [...steps.values()].sort((a, b) => a.id - b.id);
  const visible = pending ? checkpoints.slice(-6) : checkpoints;
  const phases = [
    { label: 'Understand offer', complete: !!run.draft || !!run.profile, active: run.status === 'running' && run.stage === 'seller' },
    { label: 'Confirm target', complete: !!run.profile, active: run.status === 'awaiting_confirmation' },
    { label: 'Discover companies', complete: progress.candidates > 0, active: run.status === 'running' && run.stage === 'discovery' },
    { label: 'Research evidence', complete: run.stage === 'review', active: run.status === 'running' && run.stage === 'research' },
  ];
  const heading = pending ? !connected ? 'Reconnecting to your research' : !progress.worker_online ? 'Research is waiting for a worker'
    : run.status === 'queued' ? 'Your research is next in line'
      : run.stage === 'identity' ? 'Finding your company website' : run.stage === 'seller' ? 'Understanding your company' : 'Building your shortlist'
    : 'Research checkpoints';
  const content = <>
    <ol className="research-phases" aria-label="Research stages">{phases.map(phase => <li key={phase.label}
      className={phase.complete ? 'phase-complete' : phase.active ? 'phase-current' : ''}
      aria-current={phase.active && !phase.complete ? 'step' : undefined}>
      <CheckpointIcon state={phase.complete ? 'succeeded' : 'waiting'} active={connected && pending && phase.active && progress.worker_online} />
      <span className="sr-only">{phase.complete ? 'Completed: ' : phase.active && connected && progress.worker_online ? 'Current step: ' : 'Not yet completed: '}</span>
      <span>{phase.label}</span>
    </li>)}</ol>
    {pending && <p className="current-checkpoint" role="status">{!connected ? 'Your research is saved. Showing the last checkpoint while the connection recovers.' : !progress.worker_online
      ? 'Your run is saved. Processing will begin when the research worker connects.'
      : latest?.label ?? 'Waiting for the worker to pick up your saved run.'}</p>}
    {(progress.candidates > 0 || progress.sources > 0) && <p className="progress-counts">
      <span>{progress.candidates} candidates discovered</span><span>{progress.sources} company pages saved</span>
      <span>{progress.companies} of up to 3 companies researched</span>
    </p>}
    {visible.length > 0 && <ol className="checkpoint-list" aria-label="Saved research checkpoints">{visible.map(event => <li key={event.id}>
      <CheckpointIcon state={event.state} active={connected && pending && progress.worker_online && event.id === latest?.id && event.state === 'started'} />
      <div><p><span className="sr-only">{{ started: 'Started', succeeded: 'Completed', failed: 'Failed', reused: 'Reused saved evidence', waiting: 'Waiting' }[event.state]}: </span>{event.label}</p>{event.detail && <p className="checkpoint-detail">{event.detail}</p>}
        {event.state === 'reused' && <p className="checkpoint-detail">Saved evidence reused; no new provider request.</p>}
      </div><time dateTime={event.created_at}>{time(event.created_at)}</time>
    </li>)}</ol>}
    {!pending && !checkpoints.length && <p className="hint">This older run predates the activity timeline. Its saved sources and review remain available.</p>}
    {pending && <p className="hint">Every checkpoint is saved. You can leave this page and return.</p>}
    {pending && !progress.worker_online && <p className="notice">The local worker is offline. Start the app with <code>shortlist serve</code> to run the website and worker together.</p>}
  </>;
  return pending ? <section className="sheet research-progress" aria-labelledby="progress-heading"><h2 id="progress-heading">{heading}</h2>{content}</section>
    : <details className="sheet research-progress progress-history"><summary><span>{heading}</span><span className="history-meta">{checkpoints.length} saved steps<svg className="history-chevron" width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="m8 4 8 8-8 8" stroke="currentColor" strokeWidth="1.5" /></svg></span></summary>{content}</details>;
}
