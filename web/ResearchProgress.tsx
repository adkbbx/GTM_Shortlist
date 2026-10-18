import { useEffect, useState } from 'react';
import { api } from './api';
import type { Run } from './api';
import { LiveProgress } from './LiveProgress';
import { researchStage, stagePhases } from './research-stages';
import { StatusMark, eventStatus, stageStatus } from './StatusMark';
import { OutboundLink, useSiteLabel } from './SampleData';
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

export function ResearchProgress({ run, connected = true, localResearch = false }: { run: Run; connected?: boolean; localResearch?: boolean }) {
  const [resuming, setResuming] = useState(false);
  const [resumeError, setResumeError] = useState('');
  const [viewedStage, setViewedStage] = useState<number | null>(null);
  const [showOlderSteps, setShowOlderSteps] = useState(false);
  const label = useSiteLabel();
  const resume = async () => {
    setResuming(true); setResumeError('');
    try { await api.resumeResearch(run.id); }
    catch (error) { setResumeError(error instanceof Error ? error.message : 'Research could not resume. Try again.'); }
    finally { setResuming(false); }
  };
  const { current, states, events, latest, pending, working, reviewed, reviewComplete, reviewLabel } = researchStage(run);
  // While research works, the view follows the current step; earlier stages open once it finishes or needs you.
  const following = pending && run.progress.worker_online && !run.termination;
  useEffect(() => { if (following) setViewedStage(null); }, [following]);
  const displayed = following ? current : viewedStage ?? current;
  const visibleEvents = viewedStage === null ? events : events.filter(event => stagePhases[displayed].includes(event.phase));
  const newestFirst = [...visibleEvents].reverse();
  const shownEvents = showOlderSteps ? newestFirst : newestFirst.slice(0, 3);
  const checkpointTimeline = <section className="real-history" aria-labelledby="checkpoints-heading">
    <header><h4 id="checkpoints-heading">Saved research checkpoints</h4><span className="history-meta">{shownEvents.length < visibleEvents.length ? `Showing ${shownEvents.length} of ${visibleEvents.length}` : visibleEvents.length} steps · latest first</span></header>
    {visibleEvents.length ? <ol id="saved-checkpoint-list" className="checkpoint-list" aria-label="Saved research checkpoints">{shownEvents.map(event => { const status = eventStatus(event, event.id === latest?.id, working, Boolean(run.termination)); return <li key={event.id} className={event.id === latest?.id ? 'latest-checkpoint' : undefined}><StatusMark status={status} /><div><p><span className={`checkpoint-word ${status}`}>{eventLabels[event.state]}</span><span className="checkpoint-detail"> · </span>{label(event.label)}</p>{event.detail && <p className="checkpoint-detail">{label(event.detail)}</p>}{event.state === 'reused' && <p className="checkpoint-detail">Saved evidence reused; no new provider request.</p>}</div><time dateTime={event.created_at}>{time(event.created_at)}</time></li>; })}</ol> : <p className="hint">No checkpoints saved for this stage. Older runs may predate the activity timeline.</p>}
    {visibleEvents.length > 3 && <button type="button" className="text-button" aria-expanded={showOlderSteps} aria-controls="saved-checkpoint-list" onClick={() => setShowOlderSteps(value => !value)}>{showOlderSteps ? 'Hide older steps' : `Show ${visibleEvents.length - 3} older steps`}</button>}
  </section>;
  const currentState = run.termination ? 'Research stopped' : !connected ? 'Reconnecting'
    : !pending ? current === 5 ? reviewComplete ? 'Review complete' : reviewed ? reviewLabel : run.status === 'partial' ? 'Partial research saved' : 'Ready for your review' : run.status === 'partial' ? 'Research interrupted' : 'Waiting for you'
      : !run.progress.worker_online ? 'Research paused' : run.status === 'queued' ? 'Queued' : working ? 'Research active' : 'Saving progress';
  const status = run.termination ? 'Processing has stopped. Saved sources and assessments remain available.'
    : !connected ? 'Showing the last saved checkpoint while the connection recovers.'
      : !pending && run.status === 'partial' && current !== 5 ? run.error ?? 'Research was interrupted. Inspect the saved checkpoints for details.'
      : pending && !run.progress.worker_online ? localResearch ? 'Your run is saved. Resume research to continue from its saved progress.' : 'Your run is saved. Processing will continue when the research service reconnects.'
        : run.status === 'queued' ? 'Waiting for the worker to pick up your saved run.'
          : current === 5 && reviewed ? reviewLabel : current === 5 ? run.records.some(record => !record.source_issue) ? 'Open a company research sheet below to inspect sources and decide.' : 'No company records were saved. Review the checkpoints for details.'
            : latest?.label ?? 'Your saved research is ready to continue.';
  const companyCount = run.records.filter(record => !record.source_issue).length;
  const offer = run.profile?.offer ?? run.draft?.offer;
  const sheet = <section className="real-research landing-demo" data-motion="paused" aria-labelledby="progress-heading">
    <div className="demo-intro"><div><h2 id="progress-heading">Your research, step by step</h2><p>Current stage and saved progress</p></div></div>
    {localResearch && pending && !run.progress.worker_online && <div className="notice"><p>{run.sample ? 'Sample data uses no providers or credits.' : 'Resuming research may use your provider credits.'}</p><button type="button" disabled={resuming} onClick={resume}>{resuming ? 'Resuming research…' : 'Resume research'}</button>{resumeError && <p role="alert">{resumeError}</p>}</div>}
    <div className="demo-workspace">
      <div className="demo-stage-rail"><p className="demo-step-count">Stage {current + 1} of 6 · {states[current].label}</p>
        <ol className="real-stage-list" aria-label="Research stages">{states.map((stage, index) => { const status = stageStatus(stage.state, working); return <li key={stage.label} aria-current={stage.current ? 'step' : undefined} className={stage.complete ? 'is-saved' : ''}>
          <button type="button" className="stage-review" aria-pressed={displayed === index} aria-controls="research-stage-panel" aria-disabled={following || undefined} title={following ? 'Available when this step finishes' : undefined} onClick={() => { if (following) return; setViewedStage(index); setShowOlderSteps(false); }}>{status ? <StatusMark status={status} className="demo-stage-number" /> : <span className="demo-stage-number" aria-hidden="true">{index + 1}</span>}<span><strong>{stage.label}</strong><small>{stage.state}</small></span></button>
        </li>; })}</ol><p className="demo-rail-note">{following ? 'Following the current step. Earlier stages open when this step finishes.' : 'Stages advance when work is saved. Confirmation and review need your judgment.'}</p>
      </div>
      <div className="demo-scene-wrap"><div className="demo-scene-top"><span>{currentState}</span><span>Progress from saved work</span></div>
        <div className="demo-scene real-scene" id="research-stage-panel" key={`${run.id}:${displayed}`} role="region" aria-label={`${states[displayed].label} saved information`}>
          {following && <LiveProgress run={run} current={current} />}
          <h3>{states[displayed].label}</h3><p>{descriptions[displayed]}</p>
          {viewedStage !== null && !following && <p className="hint">Reviewing saved information · {states[displayed].state}. <button className="text-button" onClick={() => { setViewedStage(null); setShowOlderSteps(false); }}>Follow current progress</button></p>}
          <div className="agent-activity"><div className="agent-observation"><p className="agent-domain">{run.sample ? 'Sample company' : run.seller_url ? new URL(run.seller_url).hostname : run.company_name ?? 'Your company'}</p><p role="status">{label(status)}</p>{latest?.detail && <p className="checkpoint-detail">{label(latest.detail)}</p>}</div></div>
          {checkpointTimeline}
          {offer && (viewedStage === null || displayed === 0) && <details className="real-saved-offer" open={viewedStage === 0}><summary>Saved offer summary</summary><p>{offer}</p>{run.seller_source && <details><summary>Inspect saved company page</summary><blockquote>{run.seller_source.text}</blockquote>{!run.sample && <a href={run.seller_source.url} target="_blank" rel="noopener noreferrer">Open saved source website</a>}</details>}</details>}
          {viewedStage !== null && <SavedStage run={run} stage={displayed} />}
          {viewedStage === null && current === 1 && run.market && <div className="demo-note"><p>{run.market.competitors.length} potential competitors · {run.market.campaigns.length} campaign hypotheses saved</p><p>Market observations, not verified comparisons. Inspect them at target confirmation.</p></div>}
          {viewedStage === null && current === 2 && <p className="demo-note">Confirm your offer and target in the form below. Research will wait for your confirmation.</p>}
          {run.stage === 'website' && <p className="demo-note">Choose or enter the correct company website below to continue.</p>}
          {current >= 3 && <div className="real-counts" aria-label="Saved research totals"><div><strong>{run.progress.candidates}</strong><span>Candidates saved</span></div><div><strong>{run.progress.sources}</strong><span>Company pages saved</span></div><div><strong>{run.progress.companies}</strong><span>Companies researched</span></div></div>}
          {viewedStage === null && current === 3 && !!run.selection?.length && <div className="real-candidates">{run.selection.slice(0, 3).map(candidate => <div className="demo-stagger" key={candidate.domain}><strong>{label(candidate.domain)}</strong><p>{candidate.explanation}</p></div>)}</div>}

        </div>
      </div>
    </div>
  </section>;
  if (pending) return sheet;
  const handoff = run.termination ? 'Research stopped' : current === 2
    ? offer ? 'Offer draft saved. Your confirmation is next.' : 'Offer summary unavailable. Enter your offer and target.'
    : current === 5 && reviewed ? reviewLabel : current === 5 ? `${companyCount} ${companyCount === 1 ? 'company' : 'companies'} saved for your review`
      : currentState;
  // While the target waits for confirmation, and once companies are ready for review, the history stays folded so the
  // decision is the first thing on the page. An interruption before review opens it to show what stopped.
  return <details className="research-recap" open={(run.status === 'partial' && current !== 5) || viewedStage !== null}><summary><span>{handoff}</span><span>View research history</span></summary>{sheet}</details>;
}

function SavedStage({ run, stage }: { run: Run; stage: number }) {
  const label = useSiteLabel();
  if (stage === 0) return !run.profile && !run.draft ? <p>No offer summary saved for this stage.</p> : null;
  if (stage === 1) return run.market ? <div className="saved-stage-content"><h4>Potential competitors</h4>{run.market.competitors.length ? run.market.competitors.map(company => <p key={company.domain}><OutboundLink href={company.url}>{label(company.domain)}</OutboundLink> · {company.excerpt.slice(0, 240)}{company.excerpt.length > 240 ? "…" : ""}</p>) : <p>No competitors saved.</p>}<h4>Campaign hypotheses</h4>{run.market.campaigns.map(campaign => <section key={campaign.name}><h5>{campaign.name}</h5><p>{campaign.target}</p><p>{campaign.rationale}</p><ul>{campaign.criteria.map(criterion => <li key={criterion.id}>{criterion.description}</li>)}</ul></section>)}{run.market.issues.map(issue => <p key={issue}>{issue}</p>)}</div> : <p>No market observations saved for this stage.</p>;
  if (stage === 2) return run.profile ? <div className="saved-stage-content"><h4>Confirmed offer and target</h4><p>{run.profile.offer}</p><p>{run.profile.target}</p><ul>{run.profile.criteria.map(criterion => <li key={criterion.id}>{criterion.description}{criterion.required ? ' · Required' : ''}</li>)}</ul>{run.profile.exclusions.length > 0 && <><h4>Exclusions</h4><ul>{run.profile.exclusions.map(item => <li key={item}>{item}</li>)}</ul></>}</div> : <p>No confirmed target saved. Review the target form below when it becomes available.</p>;
  if (stage === 3) return <div className="saved-stage-content"><h4>Saved discovery</h4>{run.selection?.length ? run.selection.map(candidate => <section key={candidate.domain}><h5>{label(candidate.domain)}</h5><p>{candidate.explanation}</p></section>) : <p>No prioritized candidates saved for this stage.</p>}</div>;
  return <div className="saved-stage-content"><h4>{stage === 4 ? 'Saved evidence' : 'Saved company reviews'}</h4>{run.records.length ? run.records.map(record => <section key={record.research.id}><h5>{record.source_issue ? record.research.domain : record.research.name}</h5>{record.source_issue ? <p>Excluded source · {record.source_issue}</p> : <p>{record.research.status === 'partial' ? 'Partial research · inspect missing evidence in the company sheet below.' : 'Research saved'}</p>}{stage === 4 ? record.research.sources.map(source => <p key={source.id}><OutboundLink href={source.url}>{source.title}</OutboundLink></p>) : record.source_issue ? null : <p>{record.review ? `Decision: ${record.review.decision} · ${record.review.reason}` : 'Not reviewed. Open the company sheet below to review.'}</p>}</section>) : <p>No company research saved for this stage.</p>}</div>;
}
