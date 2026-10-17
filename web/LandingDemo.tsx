import { useReducer, useRef, useState } from 'react';
import type { ReactNode } from 'react';
import { demoStages, demoTransition, sample } from './landing-demo.data';
import './LandingDemo.css';

function Arrow() {
  return <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M4 12h15m-6-6 6 6-6 6" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" /></svg>;
}

/** The start page. `demo` is off while a local setup card offers sample data, so there is one way to try the product. */
export function LandingDemo({ children, demo = true }: { children: ReactNode; demo?: boolean }) {
  return <div className="landing-experience"><div className="landing-start">{children}</div>{demo && <div className="landing-entry"><a className="text-button" href="?demo=1">Try the demo<Arrow /></a></div>}</div>;
}

export function DemoPage() {
  const [state, dispatch] = useReducer(demoTransition, { mode: 'paused', stage: 'offer' });
  const [passageOpen, setPassageOpen] = useState(false);
  const [decision, setDecision] = useState<'accepted' | 'rejected' | null>(null);
  const [draftOpen, setDraftOpen] = useState(false);
  const [subject, setSubject] = useState('A look at your onboarding workflow');
  const [body, setBody] = useState('Hello Northstar team,\n\nYour example product description covers customer onboarding. Relay Studio reviews onboarding workflows for B2B software teams. Would a short conversation about the handover be useful?');
  const sceneHeading = useRef<HTMLHeadingElement>(null);
  const stage = demoStages.find(item => item.id === state.stage) ?? demoStages[0];
  const index = demoStages.findIndex(item => item.id === state.stage);
  const select = (id: typeof stage.id) => {
    dispatch({ type: 'select', stage: id });
    window.requestAnimationFrame(() => { sceneHeading.current?.focus({ preventScroll: true }); sceneHeading.current?.scrollIntoView({ block: 'nearest' }); });
  };
  return <>
    <header className="demo-page-header"><a className="brand" href="/">GTM Shortlist</a><a href="/">Back to workspace</a></header>
    <main className="demo-page-main"><section className="landing-demo" aria-labelledby="demo-heading" data-motion="reduced">
      <div className="demo-intro"><div><h1 id="demo-heading">See how a shortlist takes shape.</h1><p>Synthetic example · invented companies and passages</p></div></div>
      <div className="demo-workspace">
        <div className="demo-stage-rail"><p className="demo-step-count">Step {index + 1} of 6 · {stage.title}</p><details className="demo-stage-list"><summary>All stages</summary><ol aria-label="Example research stages">{demoStages.map((item, position) => <li key={item.id}><button type="button" aria-current={item.id === state.stage ? 'step' : undefined} onClick={() => select(item.id)}><span className="demo-stage-number">{position + 1}</span><span><strong>{item.title}</strong><small>{item.detail}</small></span></button></li>)}</ol></details></div>
        <div className="demo-scene-wrap"><div className="demo-scene-top"><span>{sample.seller}</span><span>{sample.domain}</span></div>
          <div className="demo-scene" key={stage.id} data-stage={stage.id}>
            <h2 ref={sceneHeading} tabIndex={-1}>{stage.title}</h2>
            {stage.id === 'offer' && <><p>First, make sure the offer is understood.</p><div className="demo-offer"><div className="demo-scan-line" aria-hidden="true" /><span className="demo-label">Example offer</span><h4>{sample.offer}</h4><p>For teams that want to improve the journey from signup to first value.</p></div><div className="demo-note">Next, we explore the market. You confirm the target before company discovery.</div></>}
            {stage.id === 'market' && <><p>Market observations inform a campaign hypothesis.</p><div className="demo-market-row demo-stagger"><strong>Harbor Workflows</strong><span>harbor-workflows.example</span><p>Example observation: onboarding workflow software.</p></div><div className="demo-market-row demo-stagger"><strong>Fieldwork Suite</strong><span>fieldwork-suite.example</span><p>Example observation: customer operations software.</p></div><div className="demo-campaign demo-stagger"><span className="demo-label">Campaign hypothesis</span><h4>B2B teams improving onboarding</h4><p>A direction to confirm, not evidence of buying intent.</p></div></>}
            {stage.id === 'confirm' && <><p>You choose what a good fit means.</p><dl className="demo-criteria"><div><dt>Offer</dt><dd>{sample.offer}</dd></div><div><dt>Target</dt><dd>B2B software teams with an onboarding product.</dd></div><div><dt>Evidence to look for</dt><dd>A company-owned page describing its product and customers.</dd></div><div><dt>Exclude</dt><dd>Directories and consumer-only products.</dd></div></dl><button type="button" onClick={() => { select('discover'); }}>Confirm example target<Arrow /></button></>}
            {stage.id === 'discover' && <><p>Compare candidates against the confirmed criteria.</p><div className="demo-candidate demo-stagger"><span className="demo-initials">NC</span><div><strong>{sample.company}</strong><p>Customer onboarding software</p></div><span>Inspect next</span></div><div className="demo-candidate demo-stagger"><span className="demo-initials">HW</span><div><strong>Harbor Workflows</strong><p>Customer workflow software</p></div><span>Candidate</span></div><div className="demo-note">Two illustrative candidates. Actual runs return only the research available.</div></>}
            {stage.id === 'evidence' && <><p>Read the source before trusting the summary.</p><div className="demo-company-line"><strong>{sample.company}</strong><span>{sample.companyDomain}</span></div><div className="demo-evidence-finding"><div><h4>B2B onboarding product</h4><span>Supported in this sample</span></div><button className={passageOpen ? "text-button" : "demo-primary-action"} type="button" aria-expanded={passageOpen} onClick={() => setPassageOpen(value => !value)}>{passageOpen ? 'Hide example passage' : 'Inspect example passage'}<Arrow /></button>{passageOpen && <div className="demo-passage"><span className="demo-label">Synthetic example passage</span><blockquote>“{sample.passage}”</blockquote><p>Invented text for this demonstration. No real source or date is claimed.</p></div>}</div><div className="demo-unknown"><strong>Unknown</strong><p>{sample.unknown}</p></div>{passageOpen && <button type="button" onClick={() => { select('review'); }}>Review this example<Arrow /></button>}</>}
            {stage.id === 'review' && <><p>Company fit is an assessment. The decision is yours.</p><div className="demo-company-line"><strong>{sample.company}</strong><span>B2B onboarding software</span></div><div className="demo-review-summary"><p><strong>Evidence:</strong> the example passage describes a business onboarding product.</p><p><strong>Unknown:</strong> budget ownership still needs a conversation.</p></div><div className="demo-review-actions" aria-label="Example review decision"><button type="button" className="secondary" aria-pressed={decision === 'accepted'} onClick={() => setDecision('accepted')}>Accept example</button><button type="button" className="secondary" aria-pressed={decision === 'rejected'} onClick={() => setDecision('rejected')}>Reject example</button></div><p className="demo-decision" role="status">{decision ? `Example ${decision}. Your decision is separate from the fit assessment.` : 'Not reviewed. Choose a decision to try the workflow.'}</p><button type="button" className="text-button" aria-expanded={draftOpen} onClick={() => setDraftOpen(value => !value)}>{draftOpen ? 'Hide example draft' : 'Explore an example draft'}<Arrow /></button>{draftOpen && <div className="demo-passage demo-draft"><span className="demo-label">Illustrative draft · nothing is sent</span><label htmlFor="demo-subject">Example subject</label><input id="demo-subject" value={subject} onChange={event => setSubject(event.target.value)} /><label htmlFor="demo-body">Example draft</label><textarea id="demo-body" rows={5} value={body} onChange={event => setBody(event.target.value)} /><p>Based on the synthetic product passage. No recipient or address is inferred.</p></div>}</>}
            {stage.hold !== null && <button type="button" onClick={() => { dispatch({ type: 'next' }); window.requestAnimationFrame(() => sceneHeading.current?.focus()); }}>Continue<Arrow /></button>}
          </div>
        </div>
      </div>
      {stage.id === 'review' && <div className="demo-handoff"><h3>Demo complete</h3><a className="button-link demo-research-link" href="/">Return to workspace<Arrow /></a></div>}
    </section></main>
  </>;
}
