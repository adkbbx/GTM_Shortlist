import type { Run } from './api';

export const researchStages = [
  'Understand offer', 'Explore market', 'Confirm target',
  'Discover companies', 'Inspect evidence', 'Review and draft',
] as const;
export const stagePhases = [['seller'], ['market', 'campaigns'], ['confirmation'], ['discovery'], ['research'], ['review']];

/** Project persisted boundaries, never elapsed time or optimistic item counts. */
export function researchStage(run: Run) {
  const lastWork = [...run.progress.events].reverse().find(event => event.phase !== 'review');
  const stage = run.stage === 'stopped' ? lastWork?.phase ?? (run.profile ? 'discovery' : 'seller') : run.stage;
  const current = ['identity', 'website', 'seller'].includes(stage) ? 0
    : ['market', 'campaigns'].includes(stage) ? 1
      : stage === 'confirmation' ? 2
        : ['discovery', 'selection'].includes(stage) ? 3
          : stage === 'review' ? 5 : 4;
  const checkpoints = new Map<string, Run['progress']['events'][number]>();
  run.progress.events.forEach(event => checkpoints.set(`${event.phase}:${event.label}`, event));
  const events = [...checkpoints.values()].sort((a, b) => a.id - b.id);
  const eligible = run.records.filter(record => !record.source_issue);
  const reviewed = eligible.filter(record => record.review).length;
  const reviewComplete = eligible.length > 0 && reviewed === eligible.length;
  const reviewLabel = `Reviewed ${reviewed} of ${eligible.length} companies`;
  const pending = run.status === 'queued' || run.status === 'running';
  const latest = run.progress.events.at(-1);
  const working = run.status === 'running' && run.progress.worker_online && latest?.state === 'started';
  const phases = stagePhases;
  const states = researchStages.map((label, index) => {
    const failures = events.some(event => phases[index].includes(event.phase) && event.state === 'failed');
    const saved = index === 0 ? Boolean(run.draft || run.profile)
      : index === 1 ? Boolean(run.market) : index === 2 ? Boolean(run.profile)
        : index === 3 ? current > 3 : index === 4 ? current === 5 && run.records.length > 0 : false;
    const skipped = index === 1 && run.experience_version !== 2;
    const state = index === 5 && current === 5 && reviewed ? reviewLabel : skipped ? 'Not included' : index === current
      ? run.termination ? 'Stopped' : !pending ? (index === 5 ? 'Your review' : run.status === 'partial' ? 'Interrupted' : 'Needs your input') : 'Current stage'
      : index < current ? saved ? failures || (index === 1 && run.market?.status === 'partial') || (index === 4 && run.status === 'partial') ? 'Saved with gaps' : 'Saved' : 'No saved result'
        : 'Upcoming';
    return { label, state, complete: state === 'Saved' || (index === 5 && reviewComplete), current: index === current };
  });
  return { current, states, events, latest, pending, working, reviewed, reviewComplete, reviewLabel };
}
