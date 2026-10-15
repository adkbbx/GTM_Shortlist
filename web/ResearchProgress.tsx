import { useEffect, useState } from 'react';
import type { Run } from './api';
import { researchStage } from './research-stages';
import './ResearchProgress.css';

const descriptions = [
  'Read your company website and save an offer summary.',
  'Explore potential competitors and propose campaign hypotheses.',
  'Check the offer and edit your target before discovery begins.',
  'Search for companies, then prioritize candidates against your confirmed target.',
  'Read company pages, assess fit, and verify the supporting evidence.',
  'Inspect the saved research below, make your decision, and prepare a draft.',
];
const time = (value: string) => new Intl.DateTimeFormat(undefined, { hour: '2-digit', minute: '2-digit', second: '2-digit' }).format(new Date(value));
const eventLabels = { started: 'Started', succeeded: 'Completed', failed: 'Failed', reused: 'Reused', waiting: 'Waiting' };

function SavedMark({ state }: { state: string }) {
  return <svg width="20" height="20" viewBox="0 0 24 24" fill="none" aria-hidden="true"><circle cx="12" cy="12" r="9" stroke="currentColor" strokeWidth="1.3" />{state === 'succeeded' || state === 'reused' ? <path d="m7 12 3 3 7-7" stroke="currentColor" strokeWidth="1.5" /> : state === 'failed' ? <path d="m8 8 8 8m0-8-8 8" stroke="currentColor" strokeWidth="1.5" /> : <circle cx="12" cy="12" r="2" fill="currentColor" />}</svg>;
}

export function ResearchProgress({ run, connected = true }: { run: Run; connected?: boolean }) {
  const [visible, setVisible] = useState(!document.hidden);
  const [reduced, setReduced] = useState(false);
  useEffect(() => {
    const change = () => setVisible(!document.hidden);
    document.addEventListener('visibilitychange', change);
    return () => document.removeEventListener('visibilitychange', change);
  }, []);
  const { current, states, events, latest, pending, working } = researchStage(run);
  const moving = working && connected && visible && !reduced;
  const currentState = run.termination ? 'Research stopped' : !connected ? 'Reconnecting'
    : !pending ? current === 5 ? run.status === 'partial' ? 'Partial research saved' : 'Ready for your review' : run.status === 'partial' ? 'Research interrupted' : 'Waiting for you'
      : !run.progress.worker_online ? 'Waiting for a worker' : run.status === 'queued' ? 'Queued' : working ? 'Worker active' : 'Saving progress';
  const status = run.termination ? 'Processing has stopped. Saved sources and assessments remain available.'
    : !connected ? 'Showing the last saved checkpoint while the connection recovers.'
      : !pending && run.status === 'partial' && current !== 5 ? run.error ?? 'Research was interrupted. Inspect the saved checkpoints for details.'
      : pending && !run.progress.worker_online ? 'Your run is saved. Processing will continue when a research worker connects.'
        : run.status === 'queued' ? 'Waiting for the worker to pick up your saved run.'
          : current === 5 ? run.records.length ? 'Open a company research sheet below to inspect sources and decide.' : 'No company records were saved. Review the checkpoints for details.'
            : latest?.label ?? 'Your saved research is ready to continue.';
  const offer = run.profile?.offer ?? run.draft?.offer;
  return <section className="real-research landing-demo" data-motion={moving ? 'playing' : 'paused'} data-reduced={reduced} aria-labelledby="progress-heading">
    <div className="demo-intro"><div><h2 id="progress-heading">Your research, step by step</h2><p>Live work · stages follow saved worker checkpoints</p></div><button className="text-button" aria-pressed={reduced} onClick={() => setReduced(value => !value)}>{reduced ? 'Motion reduced' : 'Reduce motion'}</button></div>
    <div className="demo-workspace">
      <div className="demo-stage-rail"><p className="demo-step-count">Stage {current + 1} of 6 · {states[current].label}</p>
        <ol className="real-stage-list" aria-label="Research stages">{states.map((stage, index) => <li key={stage.label} aria-current={stage.current ? 'step' : undefined} className={stage.complete ? 'is-saved' : ''}>
          <span className={`demo-stage-number ${stage.complete ? 'real-stage-saved' : ''}`} aria-hidden="true">{stage.complete ? <SavedMark state="succeeded" /> : index + 1}</span><span><strong>{stage.label}</strong><small>{stage.state}</small></span>
        </li>)}</ol><p className="demo-rail-note">Stages advance when work is saved. Confirmation and review need your judgment.</p>
      </div>
      <div className="demo-scene-wrap"><div className="demo-scene-top"><span>{currentState}</span><span>Progress from saved work</span></div>
        <div className="demo-scene real-scene" key={`${run.id}:${current}`}>
          <h3>{states[current].label}</h3><p>{descriptions[current]}</p>
          <div className={`agent-activity ${moving ? 'is-working' : ''}`}><div className="agent-paper" aria-hidden="true"><svg viewBox="0 0 80 96" fill="none"><path d="M14 4h36l16 16v72H14V4Z" stroke="currentColor" strokeWidth="1.5"/><path d="M50 4v17h16M25 34h30M25 44h25M25 54h30M25 64h19M25 74h26" stroke="currentColor" strokeWidth="1.5"/></svg><span className="agent-scan" /></div><div className="agent-observation"><p className="agent-domain">{run.seller_url ? new URL(run.seller_url).hostname : run.company_name ?? 'Your company'}</p><p role="status">{status}</p>{latest?.detail && <p className="checkpoint-detail">{latest.detail}</p>}</div></div>
          {offer && <details className="real-saved-offer"><summary>Saved offer summary</summary><p>{offer}</p>{run.profile && <p>{run.profile.target}</p>}</details>}
          {current === 1 && run.market && <div className="demo-note"><p>{run.market.competitors.length} potential competitors · {run.market.campaigns.length} campaign hypotheses saved</p><p>Market observations, not verified comparisons. Inspect them at target confirmation.</p></div>}
          {current === 2 && <p className="demo-note">Confirm your offer and target in the form below. Research will wait for your confirmation.</p>}
          {run.stage === 'website' && <p className="demo-note">Choose or enter the correct company website below to continue.</p>}
          {current >= 3 && <div className="real-counts" aria-label="Saved research totals"><div><strong>{run.progress.candidates}</strong><span>Candidates saved</span></div><div><strong>{run.progress.sources}</strong><span>Company pages saved</span></div><div><strong>{run.progress.companies}</strong><span>Companies researched</span></div></div>}
          {current === 3 && !!run.selection?.length && <div className="real-candidates">{run.selection.slice(0, 3).map(candidate => <div className="demo-stagger" key={candidate.domain}><strong>{candidate.domain}</strong><p>{candidate.explanation}</p></div>)}</div>}
          {latest && <div className="real-latest" key={latest.id}><span className="demo-label">Latest saved checkpoint · {eventLabels[latest.state]}</span><p>{latest.label}</p><p className="checkpoint-detail">{latest.state === 'started' ? 'Awaiting a saved outcome.' : latest.state === 'failed' ? 'This step failed. See the saved detail below.' : latest.state === 'waiting' ? 'Waiting at this checkpoint.' : 'Saved to this run.'}</p></div>}
        </div>
      </div>
    </div>
    <details className="real-history"><summary>Saved research checkpoints <span className="history-meta">{events.length} steps</span></summary>
      {events.length ? <ol className="checkpoint-list" aria-label="Saved research checkpoints">{events.map(event => <li key={event.id}><span className={`real-event-mark ${moving && event.id === latest?.id && event.state === 'started' ? 'is-active' : ''}`} aria-hidden="true"><SavedMark state={event.state} /></span><div><p><span className="checkpoint-detail">{eventLabels[event.state]} · </span>{event.label}</p>{event.detail && <p className="checkpoint-detail">{event.detail}</p>}{event.state === 'reused' && <p className="checkpoint-detail">Saved evidence reused; no new provider request.</p>}</div><time dateTime={event.created_at}>{time(event.created_at)}</time></li>)}</ol> : <p className="hint">No worker checkpoints saved yet. Older runs may predate the activity timeline.</p>}
    </details>
  </section>;
}
