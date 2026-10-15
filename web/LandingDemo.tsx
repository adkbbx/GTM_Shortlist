import { useEffect, useReducer, useRef, useState } from 'react';
import type { ReactNode } from 'react';
import { demoStages, demoTransition, sample } from './landing-demo.data';
import './LandingDemo.css';
import { ResearchActivity } from './ResearchActivity';

function Arrow({ play = false }: { play?: boolean }) {
  return <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true">{play
    ? <path d="m9 5 10 7-10 7V5Z" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" />
    : <path d="M4 12h15m-6-6 6 6-6 6" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />}</svg>;
}

export function LandingDemo({ children, onResearch }: { children: ReactNode; onResearch: () => void }) {
  const [state, dispatch] = useReducer(demoTransition, { mode: 'finished', stage: 'review' });
  const [expanded, setExpanded] = useState(false);
  const [systemReduced, setSystemReduced] = useState(() => window.matchMedia('(prefers-reduced-motion: reduce)').matches);
  const [motionOff, setMotionOff] = useState(false);
  const reduced = systemReduced || motionOff;
  const [wide, setWide] = useState(() => window.matchMedia('(min-width: 851px)').matches);
  const [passageOpen, setPassageOpen] = useState(false);
  const [decision, setDecision] = useState<'accepted' | 'rejected' | null>(null);
  const [draftOpen, setDraftOpen] = useState(false);
  const [subject, setSubject] = useState('A look at your onboarding workflow');
  const [body, setBody] = useState('Hello Northstar team,\n\nYour example product description covers customer onboarding. Relay Studio reviews onboarding workflows for B2B software teams. Would a short conversation about the handover be useful?');
  const frame = useRef<HTMLElement>(null);
  const sceneHeading = useRef<HTMLHeadingElement>(null);
  const playEntry = useRef<HTMLButtonElement>(null);
  const heading = useRef<HTMLHeadingElement>(null);
  const stage = demoStages.find(item => item.id === state.stage) ?? demoStages[5];
  const index = demoStages.findIndex(item => item.id === state.stage);

  useEffect(() => {
    const query = window.matchMedia('(prefers-reduced-motion: reduce)');
    const width = window.matchMedia('(min-width: 851px)');
    const resize = () => setWide(width.matches);
    const update = () => { setSystemReduced(query.matches); if (query.matches) dispatch({ type: 'reduce' }); };
    query.addEventListener('change', update);
    width.addEventListener('change', resize);
    return () => { query.removeEventListener('change', update); width.removeEventListener('change', resize); };
  }, []);
  useEffect(() => {
    if (!expanded || reduced || state.mode !== 'playing' || stage.hold === null) return;
    const timer = window.setTimeout(() => dispatch({ type: 'next' }), stage.hold);
    return () => window.clearTimeout(timer);
  }, [expanded, reduced, stage, state.mode]);
  useEffect(() => {
    const hide = () => { if (document.hidden) dispatch({ type: 'pause' }); };
    document.addEventListener('visibilitychange', hide);
    const element = frame.current;
    let seen = false;
    const observer = new IntersectionObserver(entries => {
      for (const entry of entries) {
        if (entry.isIntersecting) seen = true;
        else if (seen) dispatch({ type: 'pause' });
      }
    });
    if (element) observer.observe(element);
    return () => { document.removeEventListener('visibilitychange', hide); observer.disconnect(); };
  }, [expanded]);

  const open = (play: boolean) => {
    setExpanded(true);
    setPassageOpen(false); setDecision(null); setDraftOpen(false);
    if (play && !reduced) { dispatch({ type: 'select', stage: 'offer' }); dispatch({ type: 'play' }); }
    else dispatch({ type: 'select', stage: play ? 'review' : 'evidence' });
    window.requestAnimationFrame(() => {
      heading.current?.focus({ preventScroll: true });
      frame.current?.scrollIntoView({ behavior: 'instant', block: 'start' });
    });
  };
  const select = (id: typeof stage.id) => { dispatch({ type: 'select', stage: id }); };

  return <div className="landing-experience">
    <div className="landing-start">{children}</div>
    <div className="landing-entry" role="group" aria-label="Explore an example">
      <button ref={playEntry} type="button" className="text-button" onClick={() => open(true)}><Arrow play />Try the demo</button>
      <span>No research credits used.</span>
    </div>
    {expanded && <section className="landing-demo" ref={frame} aria-labelledby="demo-heading" data-motion={reduced ? 'reduced' : state.mode}>
      <div className="demo-intro"><div><h2 ref={heading} tabIndex={-1} id="demo-heading">See how a shortlist takes shape.</h2><p>Illustrative sample · invented companies and passages · no live research</p></div><button type="button" className="text-button" onClick={() => { dispatch({ type: 'pause' }); setExpanded(false); playEntry.current?.focus(); }}>Close example</button></div>
      <div className="demo-workspace">
        <div className="demo-stage-rail"><p className="demo-step-count">Step {index + 1} of 6 · {stage.title}</p><details className="demo-stage-list" open={wide || undefined}><summary>All stages</summary><ol aria-label="Example research stages">{demoStages.map((item, position) => <li key={item.id}><button type="button" aria-current={item.id === state.stage ? 'step' : undefined} onClick={() => select(item.id)}><span className="demo-stage-number">{position + 1}</span><span><strong>{item.title}</strong><small>{item.detail}</small></span>{position < index && <svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="m5 12 4 4L19 6" stroke="currentColor" strokeWidth="1.5" /></svg>}</button></li>)}</ol></details><p className="demo-rail-note">An example you control.<br />Actual research follows saved worker progress.</p></div>
        <div className="demo-scene-wrap"><div className="demo-scene-top"><span>{sample.seller}</span><span>{sample.domain}</span></div>
          <div className="demo-scene" key={stage.id} data-stage={stage.id} onFocusCapture={event => { if (event.target instanceof HTMLElement && event.target.matches('button,input,textarea,summary,a')) dispatch({ type: 'pause' }); }}>
            <div className="demo-action-cue" role="status"><strong>{stage.hold === null ? 'Your turn' : state.mode === 'playing' && !reduced ? 'Demo playing' : 'Demo paused'}</strong><span>{stage.id === 'confirm' ? 'Review the criteria, then click Confirm example target to continue.' : stage.id === 'evidence' ? passageOpen ? 'Click Review this example to continue.' : 'Click Inspect example passage to see the evidence.' : stage.id === 'review' ? 'Try accepting or rejecting this company. Nothing is sent.' : state.mode === 'playing' && !reduced ? 'This step advances automatically. No click needed.' : 'Click Resume below to continue, or choose another stage.'}</span></div>
            <h3 ref={sceneHeading} tabIndex={-1}>{stage.title}</h3>
            {stage.hold !== null && <div className="demo-process-visual"><ResearchActivity stage={index} mode={state.mode === 'playing' && !reduced ? 'working' : 'still'} /></div>}
            {stage.id === 'offer' && <><p>First, make sure the offer is understood.</p><div className="demo-offer"><div className="demo-scan-line" aria-hidden="true" /><span className="demo-label">Example offer</span><h4>{sample.offer}</h4><p>For teams that want to improve the journey from signup to first value.</p></div><div className="demo-note">Next, we explore the market. You confirm the target before company discovery.</div></>}
            {stage.id === 'market' && <><p>Market observations inform a campaign hypothesis.</p><div className="demo-market-row demo-stagger"><strong>Harbor Workflows</strong><span>harbor-workflows.example</span><p>Example observation: onboarding workflow software.</p></div><div className="demo-market-row demo-stagger"><strong>Fieldwork Suite</strong><span>fieldwork-suite.example</span><p>Example observation: customer operations software.</p></div><div className="demo-campaign demo-stagger"><span className="demo-label">Campaign hypothesis</span><h4>B2B teams improving onboarding</h4><p>A direction to confirm, not evidence of buying intent.</p></div></>}
            {stage.id === 'confirm' && <><p>You choose what a good fit means.</p><dl className="demo-criteria"><div><dt>Offer</dt><dd>{sample.offer}</dd></div><div><dt>Target</dt><dd>B2B software teams with an onboarding product.</dd></div><div><dt>Evidence to look for</dt><dd>A company-owned page describing its product and customers.</dd></div><div><dt>Exclude</dt><dd>Directories and consumer-only products.</dd></div></dl><button type="button" onClick={() => { if (reduced) select('discover'); else dispatch({ type: 'confirm' }); window.requestAnimationFrame(() => sceneHeading.current?.focus({ preventScroll: true })); }}>Confirm example target<Arrow /></button><p className="demo-caption">This confirms only the sample. Your real target needs a separate confirmation.</p></>}
            {stage.id === 'discover' && <><p>Compare candidates against the confirmed criteria.</p><div className="demo-candidate demo-stagger"><span className="demo-initials">NC</span><div><strong>{sample.company}</strong><p>Customer onboarding software</p></div><span>Inspect next</span></div><div className="demo-candidate demo-stagger"><span className="demo-initials">HW</span><div><strong>Harbor Workflows</strong><p>Customer workflow software</p></div><span>Candidate</span></div><div className="demo-note">Two illustrative candidates. Actual runs return only the research available.</div></>}
            {stage.id === 'evidence' && <><p>Read the source before trusting the summary.</p><div className="demo-company-line"><strong>{sample.company}</strong><span>{sample.companyDomain}</span></div><div className="demo-evidence-finding"><div><h4>B2B onboarding product</h4><span>Supported in this sample</span></div><button className={passageOpen ? "text-button" : "demo-primary-action"} type="button" aria-expanded={passageOpen} onClick={() => setPassageOpen(value => !value)}>{passageOpen ? 'Hide example passage' : 'Inspect example passage'}<Arrow /></button>{passageOpen && <div className="demo-passage"><span className="demo-label">Synthetic example passage</span><blockquote>“{sample.passage}”</blockquote><p>Invented text for this demonstration. No real source or date is claimed.</p></div>}</div><div className="demo-unknown"><strong>Unknown</strong><p>{sample.unknown}</p></div>{passageOpen && <button type="button" onClick={() => { dispatch({ type: 'next' }); window.requestAnimationFrame(() => sceneHeading.current?.focus({ preventScroll: true })); }}>Review this example<Arrow /></button>}</>}
            {stage.id === 'review' && <><p>Company fit is an assessment. The decision is yours.</p><div className="demo-company-line"><strong>{sample.company}</strong><span>B2B onboarding software</span></div><div className="demo-review-summary"><p><strong>Evidence:</strong> the example passage describes a business onboarding product.</p><p><strong>Unknown:</strong> budget ownership still needs a conversation.</p></div><div className="demo-review-actions" aria-label="Example review decision"><button type="button" className="secondary" aria-pressed={decision === 'accepted'} onClick={() => setDecision('accepted')}>Accept example</button><button type="button" className="secondary" aria-pressed={decision === 'rejected'} onClick={() => setDecision('rejected')}>Reject example</button></div><p className="demo-decision" role="status">{decision ? `Example ${decision}. Your decision is separate from the fit assessment.` : 'Not reviewed. Choose a decision to try the workflow.'}</p><button type="button" className="text-button" aria-expanded={draftOpen} onClick={() => setDraftOpen(value => !value)}>{draftOpen ? 'Hide example draft' : 'Explore an example draft'}<Arrow /></button>{draftOpen && <div className="demo-passage demo-draft"><span className="demo-label">Illustrative draft · nothing is sent</span><label htmlFor="demo-subject">Example subject</label><input id="demo-subject" value={subject} onChange={event => setSubject(event.target.value)} /><label htmlFor="demo-body">Example draft</label><textarea id="demo-body" rows={5} value={body} onChange={event => setBody(event.target.value)} /><p>Based on the synthetic product passage. No recipient or address is inferred.</p></div>}</>}
          </div>
          <div className="demo-playback"><button type="button" className="text-button demo-motion-choice" aria-pressed={reduced} disabled={systemReduced} onClick={() => { setMotionOff(value => !value); if (!motionOff) dispatch({ type: 'reduce' }); }}>{systemReduced ? 'Device motion preference respected' : 'Reduce motion'}</button><div className="demo-playback-buttons"><button type="button" className="secondary" disabled={index === 0} onClick={() => dispatch({ type: 'previous' })}>Previous</button>{state.mode === 'playing' ? <button type="button" className="secondary" onClick={() => dispatch({ type: 'pause' })}>Pause</button> : stage.hold !== null || stage.id === 'review' ? <button type="button" className="secondary" onClick={() => { if (reduced) select('offer'); else dispatch({ type: 'play' }); }}>{stage.id === 'review' ? 'Replay' : 'Resume'}</button> : null}{stage.hold !== null && <button type="button" className="secondary" onClick={() => dispatch({ type: 'next' })}>Next</button>}</div><p role="status">{reduced ? 'Reduced motion. Explore each stage at your pace.' : state.mode === 'playing' ? 'Playing example. Pause whenever you like.' : stage.id === 'confirm' ? 'Your turn: confirm the example target.' : stage.id === 'evidence' ? passageOpen ? 'Passage opened. Review the example when ready.' : 'Your turn: inspect the example passage.' : stage.id === 'review' ? 'Example complete. Review it at your pace.' : 'Paused. Resume or choose a stage.'}</p></div>
        </div>
      </div>
      <div className="demo-handoff"><div><h3>Now start with your company.</h3><p>Your offer, confirmed criteria, and saved sources.</p></div><button type="button" onClick={onResearch}>Research my website<Arrow /></button></div>
    </section>}
  </div>;
}
