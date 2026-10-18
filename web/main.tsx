import { openLocalSetup, openWorkspacePanel } from './workspace-panels';
import { MenuToggleIcon, PlusIcon } from './NavigationIcons';
import { lazy, StrictMode, Suspense, useCallback, useContext, useEffect, useRef, useState } from 'react';
import type { FormEvent, ReactNode } from 'react';
import { createRoot } from 'react-dom/client';
import '@fontsource/schibsted-grotesk/400.css';
import '@fontsource/schibsted-grotesk/600.css';
import '@fontsource/schibsted-grotesk/700.css';
import { api, ApiError } from './api';
import type { Confirmation, Evidence, ExclusionFinding, Finding, Health, Record, Review, Run, Service, Wallet } from './api';
import { ResearchProgress } from './ResearchProgress';
import { DemoPage, LandingDemo } from './LandingDemo';
import { WorkshopField } from './WorkshopField';
import { ResearchSidebar } from './ResearchSidebar';
import { SiteIcon } from './SiteIcon';
import { CompanySearch } from './CompanySearch';
import { configuredDirectoryId } from './company-suggestions';
import { BrandfetchContext, savedBrandfetchId } from './BrandfetchSettings';
import { AuthGate } from './AuthGate';
import { AccountTray } from './AccountTray';
import { ResearchStop } from './ResearchStop';
import { RetrySeller } from './RetrySeller';
import { ContinueDiscovery } from './ContinueDiscovery';
import { MarketOverview } from './MarketOverview';
import { EmailDraftEditor } from './EmailDraftEditor';
import { LocalSearchSetup } from './LocalSearchSetup';
import { WebsiteChoice } from './WebsiteChoice';
import { clearKeptCompany, clearKeptDraft, keepCompany, peekKeptCompany, peekKeptDraft } from './landing/kept-company';
import { StatusMark } from './StatusMark';
import { SampleContext, sampleMark } from './SampleData';
import { rarelyPublicCheck } from './criteria';
import './styles.css';
import './Shortlist.css';

const previewWorkspace = document.querySelector<HTMLMetaElement>('meta[name="shortlist-preview-workspace"]')?.content;

const describeError = (error: unknown) => error instanceof Error ? error.message : 'Something went wrong. Please try again.';
const date = (value: string) => new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value));
const qualification = { fits: 'Fits the required criteria', needs_verification: 'Needs verification', does_not_fit: 'Does not fit' };

function Arrow() {
  return <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M4 12h15m-6-6 6 6-6 6" stroke="currentColor" strokeWidth="1.5" /></svg>;
}

type TargetPart = 'offer' | 'target' | 'criteria' | 'exclusions';
const targetFields: { [part in TargetPart]: string } = { offer: 'offer', target: 'target', criteria: 'criterion-0', exclusions: 'exclusions' };

/** One part of the target: readable text with an Edit button, or its fields once edited or when it needs input. */
function TargetPartView({ title, editLabel, editing, onEdit, review, children }: { title: string; editLabel: string; editing: boolean; onEdit: () => void; review: ReactNode; children: ReactNode }) {
  return <div className={`target-part${editing ? ' is-editing' : ''}`}>
    {editing ? children : <><div className="target-part-head"><h3>{title}</h3><button type="button" className="text-button" aria-label={editLabel} onClick={onEdit}>Edit</button></div>{review}</>}
  </div>;
}

function ConfirmationForm({ run, wallet, hostedAccount, onSaved }: { run: Run & { seller_url: string }; wallet: Wallet | null; hostedAccount: boolean; onSaved: (run: Run) => void }) {
  const [offer, setOffer] = useState(run.draft?.offer ?? '');
  const [target, setTarget] = useState(run.draft?.target ?? '');
  const [criteria, setCriteria] = useState<Confirmation['criteria']>(run.draft?.criteria.length ? run.draft.criteria : [{ id: 'criterion-1', description: '', required: true }]);
  const [exclusions, setExclusions] = useState((run.draft_exclusions ?? []).join('\n'));
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [companyLimit, setCompanyLimit] = useState(3);
  const [campaignName, setCampaignName] = useState<string | null>(run.campaign_name ?? null);
  const [discoveryTerms, setDiscoveryTerms] = useState(run.discovery_terms ?? run.draft?.target.slice(0, 300) ?? '');
  // Review first: drafted parts read as text. A part opens for editing when chosen, or when it needs the person's input.
  const [editing, setEditing] = useState<{ [part in TargetPart]: boolean }>(() => {
    const drafted = run.draft?.criteria ?? [];
    return { offer: !run.draft?.offer.trim(), target: !run.draft?.target.trim(),
      criteria: !drafted.length || drafted.some(item => !item.description.trim()) || Boolean(run.draft?.criteria_issues?.length),
      exclusions: Boolean(run.draft_exclusions?.length) };
  });
  const edit = (...parts: TargetPart[]) => {
    setEditing(old => ({ ...old, ...Object.fromEntries(parts.map(part => [part, true])) }));
    window.requestAnimationFrame(() => document.getElementById(targetFields[parts[0]])?.focus());
  };
  const unverifiableExclusions = exclusions.split('\n').map(line => line.trim()).filter(line => line && rarelyPublicCheck(line));
  const available = run.legacy_credit_exempt ? 3 : wallet?.available ?? 3;
  useEffect(() => { if (wallet?.mode === 'hosted' && available > 0) setCompanyLimit(old => Math.min(old, available)); }, [available, wallet?.mode]);
  const submit = async (event: FormEvent) => {
    event.preventDefault(); setSaving(true); setError('');
    try {
      onSaved(await api.confirm(run.id, { offer, target, criteria, company_limit: companyLimit,
        exclusions: exclusions.split('\n').map(s => s.trim()).filter(Boolean), campaign_name: campaignName,
        discovery_terms: campaignName ? discoveryTerms : null }, run.sample));
    } catch (e) { setError(describeError(e)); } finally { setSaving(false); }
  };
  return <section className="sheet confirmation" aria-labelledby="confirm-heading">
    <div className="sheet-heading"><h2 id="confirm-heading">Confirm what a good fit means</h2><span className="step-label">Your target</span></div>
    <p className="intro">{run.sample ? 'Drafted from the sample company page' : <>Drafted from <a href={run.seller_url} target="_blank" rel="noopener noreferrer">{new URL(run.seller_url).hostname}</a></>}. Check it, edit anything that is off, then start discovery.</p>
    {run.reused_offer && <p className="notice">Copied from your saved offer. Review it and choose the maximum cost before starting. Companies already in your earlier shortlists for this offer are set aside, so each batch looks for new ones.</p>}
    {run.error && <div className="notice" role="status">{run.error}</div>}
    <form onSubmit={submit}>
      <TargetPartView title="What you sell" editLabel="Edit what you sell" editing={editing.offer} onEdit={() => edit('offer')} review={<p className="target-text">{offer}</p>}>
        <label htmlFor="offer">What do you sell?</label>
        <textarea id="offer" required minLength={10} maxLength={4000} rows={4} value={offer} onChange={e => setOffer(e.target.value)} />
      </TargetPartView>
      <TargetPartView title="Who to look for" editLabel="Edit who to look for" editing={editing.target} onEdit={() => edit('target')}
        review={<><p className="target-text">{target}</p>{campaignName && <p className="hint">Campaign: {campaignName} · Search keywords: {discoveryTerms}</p>}</>}>
        <label htmlFor="target">Who should we look for?</label>
        <textarea id="target" required minLength={5} maxLength={2000} rows={2} value={target} onChange={e => setTarget(e.target.value)} />
        {campaignName && <><label htmlFor="discovery-terms">Search keywords</label><input id="discovery-terms" required minLength={5} maxLength={300} value={discoveryTerms} onChange={e => setDiscoveryTerms(e.target.value)} aria-describedby="discovery-help" /><p id="discovery-help" className="hint">Observable company terms, such as industry, product and public announcements. Private performance assumptions belong in hypotheses.</p></>}
      </TargetPartView>
      <TargetPartView title="Fit checks" editLabel="Edit fit checks" editing={editing.criteria} onEdit={() => edit('criteria')}
        review={<ul className="target-checks">{criteria.map(criterion => <li key={criterion.id}><span>{criterion.description}
          {rarelyPublicCheck(criterion.description) && (criterion.required
            ? <span className="target-check-note">Rarely on a company's own website, so it usually stays unknown and keeps every company at Needs verification. {criteria.filter(c => c.required).length > 1
              ? <button type="button" className="text-button" onClick={() => setCriteria(criteria.map(c => c.id === criterion.id ? { ...c, required: false } : c))}>Make it nice to have</button>
              : 'Add a required check a company website shows, then make this one nice to have.'}</span>
            : <span className="target-check-note">Rarely on a company's own website: it orders the shortlist when a page states it, and is a question for the conversation.</span>)}
        </span><span className="target-check-kind">{criterion.required ? 'Required' : 'Nice to have'}</span></li>)}</ul>}>
      <fieldset><legend>Fit criteria</legend><p className="hint">These checks guide company research and determine fit with your target customer. Use observable characteristics, such as industry or customers served. Required checks need supporting evidence; missing evidence stays unknown.</p>
        {!!run.draft?.criteria_issues?.length && <div className="notice" role="status"><p>Unsupported suggestions were removed. {run.draft.criteria.length ? 'Review the remaining criteria before confirming.' : 'Add at least one observable customer characteristic before confirming.'} Your offer summary is kept for editing.</p><details><summary>Review {run.draft.criteria_issues.length} removed {run.draft.criteria_issues.length === 1 ? 'suggestion' : 'suggestions'}</summary><ul>{run.draft.criteria_issues.map((issue, index) => <li key={index}><p>{issue.description}</p><p className="hint">{issue.reason}</p></li>)}</ul></details></div>}
        {criteria.map((criterion, index) => <div className="criterion-input" key={criterion.id}>
          <label htmlFor={`criterion-${index}`}>Criterion {index + 1}</label>
          <input id={`criterion-${index}`} value={criterion.description} required minLength={3} maxLength={500}
            onChange={e => setCriteria(criteria.map((c, i) => i === index ? { ...c, description: e.target.value } : c))} />
          <div className="criterion-controls"><label className="checkbox-label"><input type="checkbox" checked={criterion.required}
            onChange={e => setCriteria(criteria.map((c, i) => i === index ? { ...c, required: e.target.checked } : c))} />Required</label>
            {criteria.length > 1 && <button type="button" className="text-button" onClick={() => setCriteria(criteria.filter((_, i) => i !== index))} aria-label={`Remove criterion ${index + 1}`}>Remove</button>}</div>
          {criterion.required && rarelyPublicCheck(criterion.description) && <p className="hint target-check-note">Rarely on a company's own website: as a required check it usually stays unknown and keeps every company at Needs verification. Consider making it nice to have and asking about it in conversation.</p>}
        </div>)}
        <button type="button" className="secondary" disabled={criteria.length >= 12} onClick={() => setCriteria([...criteria, { id: crypto.randomUUID(), description: '', required: true }])}>Add a criterion</button>
      </fieldset>
      </TargetPartView>
      {editing.exclusions && <div className="target-part is-editing"><label htmlFor="exclusions">Exclude from consideration <span className="optional">Optional, one per line</span></label>
        <textarea id="exclusions" value={exclusions} rows={2} maxLength={6012} onChange={e => setExclusions(e.target.value)} aria-describedby="exclusions-help" />
        <p id="exclusions-help" className="hint">Up to 12 conditions, 3–500 characters each. Each needs evidence; an unverified exclusion stays unknown.</p>
        {unverifiableExclusions.length > 0 && <p className="hint target-check-note" role="status">Rarely on a company's own website: {unverifiableExclusions.map(line => `"${line}"`).join(', ')}. An exclusion that stays unknown keeps every company at Needs verification, so ask about it in conversation instead. <button type="button" className="text-button" onClick={() => setExclusions(exclusions.split('\n').filter(line => !rarelyPublicCheck(line.trim())).join('\n'))}>Remove {unverifiableExclusions.length === 1 ? 'it' : 'them'}</button></p>}</div>}
      {(!editing.exclusions || run.market) && <div className="target-optional">
        {!editing.exclusions && <button type="button" className="text-button" onClick={() => edit('exclusions')}>Add exclusions</button>}
        {run.market && <details className="confirmation-context"><summary>Explore campaign ideas and source context</summary><MarketOverview run={run} selected={campaignName} onChoose={campaign => {
          setCampaignName(campaign.name); setTarget(campaign.target); setCriteria(campaign.criteria);
          setDiscoveryTerms(campaign.search_terms || run.draft?.target.slice(0, 300) || '');
          setEditing(old => ({ ...old, target: true, criteria: true }));
        }} /></details>}
      </div>}
      {run.draft?.unknowns.length ? <div className="unknowns"><h3>Still needs review</h3><ul>{run.draft.unknowns.map(u => <li key={u}>{u}</li>)}</ul></div> : null}
      {hostedAccount && wallet === null && <p className="notice" role="status">Your credit balance must load before you can confirm the batch cost. Reload the workspace to retry.</p>}
      {wallet?.mode === 'hosted' && <section className="batch-choice"><label htmlFor="company-limit">Companies in this batch</label><select id="company-limit" value={companyLimit} onChange={event => setCompanyLimit(Number(event.target.value))}>{[1, 2, 3].map(quantity => <option key={quantity} value={quantity} disabled={quantity > available}>{quantity} {quantity === 1 ? 'company' : 'companies'}</option>)}</select><p>{run.legacy_credit_exempt ? 'Your original demo allowance is preserved.' : `Maximum ${companyLimit} ${companyLimit === 1 ? 'credit' : 'credits'} · ${wallet.available} available`}</p><p className="hint">Completed unknown or non-fit research counts. Credits for technical failures are returned. Review and export are free.</p>{available === 0 && <p className="notice">No research credits available. Saved research stays accessible. Credit purchases are not available yet.</p>}</section>}
      {error && <p className="notice" role="alert">{error}</p>}
      <div className="form-footer"><p>No outreach is sent. You review every company.</p><button type="submit" disabled={saving || (hostedAccount && wallet === null) || (wallet?.mode === 'hosted' && available < companyLimit)}>{saving ? 'Saving target…' : 'Confirm target and discover'}<Arrow /></button></div>
    </form>
  </section>;
}

/** First run on a local install: two steps, each opening the right Settings section. Keys never leave this computer.
    Sample data runs the same flow on invented companies first, for anyone without keys yet. */
function LocalSetupCard({ health, onSample, starting }: { health: Health; onSample: () => void; starting: boolean }) {
  const steps = [
    { id: 'model', title: 'Research model', ready: health.gemma_ready, action: 'Set up model', detail: 'Ollama, LM Studio or any OpenAI-compatible endpoint' },
    { id: 'search', title: 'Company search', ready: health.search_ready, action: 'Add search key', detail: 'A Tavily API key; Tavily has a free tier' },
  ] as const;
  return <section className="local-setup-card" aria-labelledby="local-setup-heading">
    <h3 id="local-setup-heading">Set up local research in two steps</h3>
    <div className="local-setup-sample"><span>No keys yet?</span><button type="button" className="text-button" disabled={starting} onClick={onSample}>{starting ? 'Starting the sample…' : 'Try it with sample data'}<Arrow /></button></div>
    <ol>{steps.map((step, index) => <li key={step.id}>
      <StatusMark status={step.ready ? 'ok' : 'idle'}>{index + 1}</StatusMark>
      <span className="local-setup-step"><strong>{step.title}</strong><span>{step.ready ? 'Ready' : step.detail}</span></span>
      {!step.ready && <button type="button" className="secondary" onClick={() => openLocalSetup(step.id)}>{step.action}</button>}
    </li>)}</ol>
    <p className="hint">Keys stay on this computer. Sample data uses invented companies and runs no searches.</p>
  </section>;
}

function EvidenceDetails({ passages, record }: { passages: Evidence[]; record: Record }) {
  const sample = useContext(SampleContext);
  return passages.map((evidence, index) => {
      const source = record.research.sources.find(s => s.id === evidence.source_id);
      return <details className="evidence" key={`${evidence.source_id}-${index}`}><summary>{evidence.claim}<span>Inspect passage</span></summary>
        <blockquote>{evidence.passage}</blockquote>
        {source && <div className="source-meta">{sample ? <span>{source.title} · sample page</span> : <a href={source.url} target="_blank" rel="noopener noreferrer">{source.title}<Arrow /></a>}<p>Retrieved {date(source.retrieved_at)}</p><p>{source.published_at ? `Published ${date(source.published_at)}` : 'Publication date unknown'}</p></div>}
      </details>;
    });
}

function FindingSheet({ finding, record, run }: { finding: Finding; record: Record; run: Run }) {
  const criterion = run.profile?.criteria.find(c => c.id === finding.criterion_id);
  return <section className="finding"><div className="finding-heading"><h4>{criterion?.description ?? finding.criterion_id}</h4><span className={`finding-status ${finding.status}`}>{finding.status === 'supported' ? 'Supported' : finding.status === 'contradicted' ? 'Contradicted' : 'Unknown'}</span></div>
    {finding.status === 'unknown' ? <p className="unknown-reason">{finding.reason}</p> : <EvidenceDetails passages={finding.evidence} record={record} />}
  </section>;
}

function ExclusionSheet({ finding, record, run }: { finding: ExclusionFinding; record: Record; run: Run }) {
  const exclusion = run.profile?.exclusions.find((_, i) => `exclude-${i + 1}` === finding.exclusion_id);
  const label = { matched: 'Matched', cleared: 'Ruled out', unknown: 'Unknown' };
  return <section className="finding"><div className="finding-heading"><h4>{exclusion ?? finding.exclusion_id}</h4><span className={`finding-status ${finding.status === 'matched' ? 'contradicted' : finding.status}`}>{label[finding.status]}</span></div>
    {finding.status === 'unknown' ? <p className="unknown-reason">{finding.reason}</p> : <EvidenceDetails passages={finding.evidence} record={record} />}
  </section>;
}

/** How close an assessment is, so "Needs verification" with three of four checks reads differently from none of four. */
function evidenceSummary(record: Record, run: Run) {
  const required = run.profile?.criteria.filter(criterion => criterion.required) ?? [];
  const status = new Map(record.research.findings.map(finding => [finding.criterion_id, finding.status]));
  const against = record.research.findings.filter(finding => finding.status === 'contradicted').length
    + record.research.exclusion_findings.filter(finding => finding.status === 'matched').length;
  if (against) return `${against} ${against === 1 ? 'check' : 'checks'} against your target`;
  if (!required.length) return '';
  const supported = required.filter(criterion => status.get(criterion.id) === 'supported').length;
  return supported === required.length ? `All ${required.length} required ${required.length === 1 ? 'check' : 'checks'} supported`
    : `${supported} of ${required.length} required checks supported`;
}

function CompanyReview({ record, run, onSaved }: { record: Record; run: Run; onSaved: (run: Run) => void }) {
  const disclosure = useRef<HTMLDetailsElement>(null);
  const summary = useRef<HTMLElement>(null);
  const [unsaved, setUnsaved] = useState(false);
  const research = record.research;
  const description = research.company_facts.find(fact => fact.kind === 'description');
  const selection = run.selection?.find(item => item.domain === research.domain);
  const signal = selection?.signals.find(item => item.campaign_relevant) ?? selection?.signals[0];
  const decision = record.review ? { accepted: 'Accepted', rejected: 'Rejected', needs_research: 'Needs more research' }[record.review.decision] : 'Not reviewed';
  const evidence = evidenceSummary(record, run);
  const close = () => {
    if (disclosure.current) disclosure.current.open = false;
    summary.current?.focus();
  };
  return <details className="company-item" name={`shortlist-${run.id}`} ref={disclosure}>
    <summary className="company-row" ref={summary}>
      <span className="shortlist-identity"><SiteIcon runId={run.id} domain={research.domain} mark={sampleMark(run.sample, research.domain)} fallback={research.name.trim().slice(0, 1).toUpperCase()} className="company-initial" />
        <span><span className="shortlist-name">{research.name}</span><span className="shortlist-domain">{run.sample ? 'Sample company' : research.domain}</span></span></span>
      <span className="shortlist-description">{description?.evidence.claim ?? 'Company description not established from saved sources.'}</span>
      <span className="shortlist-assessment"><span>{qualification[research.qualification]}</span>{evidence && <span className="shortlist-evidence">{evidence}</span>}<span className="shortlist-decision">{decision}</span></span>
      <span className="shortlist-action"><span className="row-inspect">Inspect</span><span className="row-close">Close</span><svg className="row-chevron" viewBox="0 0 20 20" fill="none" aria-hidden="true"><path d="m7 4 6 6-6 6" stroke="currentColor" strokeWidth="1.5" /></svg></span>
      <span className="shortlist-context"><span className="shortlist-signal">{signal ? <>{signal.label} · <time dateTime={signal.event_date}>{new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeZone: 'UTC' }).format(new Date(signal.event_date))}</time> · Company statement</> : 'No dated company activity established'}</span>
        <span>{research.people.length ? `${research.people.length} ${research.people.length === 1 ? 'person' : 'people'} identified` : 'No team roles established'}</span>
        {record.email_draft && <span>Draft saved</span>}{unsaved && <span className="unsaved-indicator">Unsaved edits</span>}</span>
    </summary>
    <div className="company-panel"><CompanySheet record={record} run={run} onSaved={onSaved} onUnsavedChange={setUnsaved} />
      <div className="company-panel-footer"><button type="button" className="secondary" onClick={close}>Back to shortlist<Arrow /></button><p className="hint">Unsaved edits stay in this sheet while you switch between companies.</p></div>
    </div>
  </details>;
}

function CompanySheet({ record, run, onSaved, onUnsavedChange }: { record: Record; run: Run; onSaved: (run: Run) => void; onUnsavedChange: (dirty: boolean) => void }) {
  const [reason, setReason] = useState(record.review?.reason ?? '');
  const [draftDirty, setDraftDirty] = useState(false);
  const reviewDirty = reason !== (record.review?.reason ?? '');
  useEffect(() => { onUnsavedChange(reviewDirty || draftDirty); }, [reviewDirty, draftDirty, onUnsavedChange]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const save = async (decision: Review['decision']) => {
    setSaving(true); setError('');
    try { onSaved(await api.review(run.id, record.research.id, decision, reason)); }
    catch (e) { setError(describeError(e)); } finally { setSaving(false); }
  };
  const research = record.research;
  const selection = run.selection?.find(item => item.domain === research.domain);
  return <article className="sheet company-sheet">
    <header className="company-heading"><div><h3>{research.name}</h3>{run.sample ? <span className="hint">Sample company · invented</span> : <a href={`https://${research.domain}`} target="_blank" rel="noopener noreferrer">{research.domain}<Arrow /></a>}</div>
      <p className="qualification">{qualification[research.qualification]}<span>{research.status === 'partial' ? 'Partial research' : 'Research saved'}</span></p></header>
    <section className="company-overview" aria-label="Company overview"><dl>
      {(['description', 'location', 'team_size'] satisfies Array<NonNullable<typeof research.company_facts>[number]['kind']>).map(kind => {
        const fact = research.company_facts.find(item => item.kind === kind);
        return <div key={kind}><dt>{{ description: 'What they do', location: 'Location', team_size: 'Team size' }[kind]}</dt>
          <dd>{fact ? <EvidenceDetails passages={[fact.evidence]} record={record} /> : <p className="hint">Not established from saved sources</p>}</dd></div>;
      })}
    </dl></section>
    <section className="people-research" aria-label="People to consider"><h4>People to consider</h4>
      {research.people.length ? <><p className="hint">Roles stated on saved company pages. Confirm responsibility for your offer before contacting anyone.</p>
        <ul>{research.people.map(person => <li key={person.id}><div className="person-identity"><h5>{person.name}</h5><p>{person.role}</p></div>
          <EvidenceDetails passages={[person.evidence]} record={record} /></li>)}</ul></>
        : <p className="hint">No current team roles established from the saved pages.</p>}
    </section>
    {selection && <details className="selection-reason"><summary>Why this company was researched</summary><p>{selection.explanation}</p>
      {selection.signals.map((signal, index) => <div key={`${signal.source_id}-${signal.label}-${signal.event_date}-${index}`}><h4>{signal.label} · dated company statement</h4><blockquote>{signal.passage}</blockquote><p>Statement date: <time dateTime={signal.event_date}>{new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeZone: 'UTC' }).format(new Date(signal.event_date))}</time>{signal.campaign_relevant ? ' · Matches campaign signal type' : ''}</p>{!run.sample && <a href={signal.source_url} target="_blank" rel="noopener noreferrer">Inspect company source</a>}<p className="hint">A dated first-party statement, not independently corroborated buying intent.</p></div>)}
      {selection.clues.map(clue => <div key={clue.label}><h4>{clue.label} · search clue</h4><blockquote>{clue.passage}</blockquote>{!run.sample && <a href={clue.source_url} target="_blank" rel="noopener noreferrer">Search result source</a>}<p className="hint">Observed {date(clue.observed_at)}. Event date, ownership and current relevance are unverified.</p></div>)}
      <p className="hint">Search clues help prioritize research. They do not establish fit or buying intent.</p></details>}
    {record.credits_used != null && <p className="delivery-credit">{record.credits_used ? '1 research credit used' : 'No research credit charged'}</p>}
    <div className="findings">{research.findings.map(f => <FindingSheet key={f.criterion_id} finding={f} record={record} run={run} />)}</div>
    {!!research.exclusion_findings.length && <section className="hypotheses exclusion-checks"><h4>Exclusion checks</h4><p className="hint">A matched exclusion means the company does not fit. Missing evidence remains unknown.</p>{research.exclusion_findings.map(f => <ExclusionSheet key={f.exclusion_id} finding={f} record={record} run={run} />)}</section>}
    {!!research.hypotheses.length && <section className="hypotheses"><h4>Hypotheses to test</h4><p className="hint">Possible relevance, not observed buying intent.</p>{research.hypotheses.map(h => <div key={h.text}><p>{h.text}</p><p className="hint">Assumptions: {h.assumptions.join('; ')}</p></div>)}</section>}
    {!research.sources.length && <p className="notice">No readable source was saved. Verify this company before accepting it.</p>}
    <EmailDraftEditor record={record} runId={run.id} onSaved={onSaved} onDirtyChange={setDraftDirty} />
    {record.operator_review && <section className="service-review" aria-label="Service review"><div className="review-heading"><h4>Service review</h4><span>{record.operator_review.annotation.outcome === 'reviewed' ? 'Evidence reviewed' : 'More research needed'}</span></div><p className="service-note">{record.operator_review.annotation.note}</p><p className="hint">Recorded by {record.operator_review.annotation.reviewer} · {date(record.operator_review.reviewed_at)}</p><p className="hint">This note is separate from your decision and does not establish buying intent.</p>{!!record.operator_review.annotation.source_ids.length && <div className="service-sources source-meta"><p>Inspected sources</p>{research.sources.filter(source => record.operator_review?.annotation.source_ids.includes(source.id)).map(source => <a key={source.id} href={source.url} target="_blank" rel="noopener noreferrer">{source.title}<Arrow /></a>)}</div>}</section>}
    <section className="review"><div className="review-heading"><h4>Your review</h4><span aria-live="polite">{record.review ? `Saved: ${record.review.decision.replace('_', ' ')}` : 'Not reviewed'}</span></div>
      <label htmlFor={`reason-${research.id}`}>Review note <span className="optional">Optional</span></label>
      <textarea id={`reason-${research.id}`} rows={2} value={reason} onChange={e => setReason(e.target.value)} />
      <div className="review-actions"><button disabled={saving} onClick={() => save('accepted')} className={record.review?.decision === 'accepted' ? '' : 'secondary'}>Accept company</button><button disabled={saving} onClick={() => save('needs_research')} className="secondary">Needs research</button><button disabled={saving} onClick={() => save('rejected')} className="text-button">Reject</button></div>
      {error && <p role="alert" className="notice">{error}</p>}
    </section>
  </article>;
}

function ReuseOffer({ run, onSaved }: { run: Run; onSaved: (run: Run) => void }) {
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const requestKey = useRef(crypto.randomUUID());
  const reuse = async () => {
    setSaving(true); setError('');
    try { onSaved(await api.reuse(run.id, requestKey.current)); }
    catch (reason) { setError(describeError(reason)); setSaving(false); }
  };
  return <div className="reuse-offer"><button className="secondary" disabled={saving} onClick={() => void reuse()}>{saving ? 'Copying offer…' : 'Reuse this offer'}<Arrow /></button><p className="hint">Skip website profiling. Review the target and batch cost before new research starts.</p>{error && <p className="notice" role="alert">{error}</p>}</div>;
}

function DeleteResearch({ run, onDeleted }: { run: Run; onDeleted: () => void }) {
  const [confirming, setConfirming] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState('');
  const remove = async () => {
    setDeleting(true); setError('');
    try { await api.deleteRun(run.id); onDeleted(); }
    catch (reason) { setError(describeError(reason)); setDeleting(false); }
  };
  return <section className="delete-research" aria-label="Delete research">
    {confirming ? <><h3>Delete this saved research?</h3><p>Export anything you need first. This removes the offer, company sheets, reviews and saved source content. It cannot be undone. Used credits are not refunded; billing and spending records remain.</p><div className="review-actions"><button className="secondary" autoFocus disabled={deleting} onClick={() => { setConfirming(false); setError(''); }}>Keep research</button><button className="danger-button" disabled={deleting} onClick={() => void remove()}>{deleting ? 'Deleting…' : 'Delete permanently'}</button></div>{error && <p role="alert" className="notice">{error}</p>}</> : <button className="text-button" onClick={() => setConfirming(true)}>Delete saved research</button>}
  </section>;
}

function App({ account, identity }: { account: ReactNode; identity: string }) {
  const [health, setHealth] = useState<Health | null>(null);
  const [mobileHistoryOpen, setMobileHistoryOpen] = useState(false);
  const [historyCollapsed, setHistoryCollapsed] = useState(() => window.matchMedia('(max-width: 850px)').matches);
  useEffect(() => {
    const query = window.matchMedia('(max-width: 850px)');
    const changed = () => setHistoryCollapsed(true);
    query.addEventListener('change', changed);
    return () => query.removeEventListener('change', changed);
  }, []);
  const historyTrigger = useRef<HTMLButtonElement>(null);
  const closeMobileHistory = useCallback(() => setMobileHistoryOpen(false), []);
  const restoreMobileMenuFocus = () => {
    if (!window.matchMedia('(max-width: 850px)').matches) return;
    const focused = document.activeElement;
    // A delayed native close event must not steal focus from a newly chosen page control.
    if (!(focused instanceof HTMLElement) || focused === document.body ||
        !focused.getClientRects().length || focused.closest('#local-settings, #account-tray, #research-drawer')) {
      historyTrigger.current?.focus();
    }
  };
  const [brandfetchOverride, setBrandfetchOverride] = useState(savedBrandfetchId);
  const brandfetchClientId = previewWorkspace ? '' : health?.mode === 'local' ? brandfetchOverride ?? configuredDirectoryId() : health ? configuredDirectoryId() : '';
  const [wallet, setWallet] = useState<Wallet | null>(null);
  const [showActivity, setShowActivity] = useState(false);
  const [service, setService] = useState<Service | null>(null);
  const [runs, setRuns] = useState<Run[]>([]);
  const [active, setActive] = useState<Run | null>(null);
  // A company typed on the public landing page prefills the field once; research still waits for Start research.
  const [website, setWebsite] = useState(() => { const kept = peekKeptCompany(); if (kept) return kept; try { return sessionStorage.getItem('shortlist-company-entry:' + identity) ?? ''; } catch { return ''; } });
  useEffect(() => { clearKeptCompany(); }, []);
  // Start research pressed on the public landing page carries through signup: the run begins once, here, instead of
  // asking again. Discovery and credits still wait for target confirmation; a saved-run link never starts research.
  const [handoff, setHandoff] = useState(peekKeptCompany);
  const handingOff = useRef(false);
  useEffect(() => { try { sessionStorage.setItem('shortlist-company-entry:' + identity, website); } catch { /* Optional tab-local input recovery. */ } }, [website, identity]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [acceptedOnly, setAcceptedOnly] = useState(false);
  const [message, setMessage] = useState('');
  const requestKey = useRef(crypto.randomUUID());
  const headingRef = useRef<HTMLHeadingElement>(null);
  const activeRef = useRef(active);
  activeRef.current = active;
  const selectionEpoch = useRef(0);

  useEffect(() => {
    let cancelled = false;
    api.service().then(value => { if (!cancelled) setService(value); }).catch(() => { if (!cancelled) setService(null); });
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    let cancelled = false;
    Promise.all([api.health(), api.runs()]).then(([status, saved]) => {
      if (cancelled) return;
      setHealth(status); setRuns(saved);
      const id = new URLSearchParams(window.location.search).get('run');
      setActive(saved.find(r => r.id === id) ?? null);
    }).catch(e => { if (!cancelled) setError(describeError(e)); }).finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, []);
  useEffect(() => {
    let cancelled = false;
    api.credits().then(balance => { if (!cancelled) setWallet(balance); })
      .catch(reason => { if (!cancelled) setError(describeError(reason)); });
    return () => { cancelled = true; };
  }, [active?.id, active?.status, active?.credits?.used, active?.credits?.reserved]);
  useEffect(() => {
    if (!active || !['queued', 'running'].includes(active.status)) return;
    let cancelled = false;
    const epoch = selectionEpoch.current;
    let timer: number | undefined;
    const poll = async () => {
      try {
        const run = await api.run(active.id);
        if (!cancelled && epoch === selectionEpoch.current) { setActive(run); setError(''); setRuns(old => old.map(r => r.id === run.id ? run : r)); }
      } catch (e) { if (!cancelled && epoch === selectionEpoch.current) setError(describeError(e)); }
      finally { if (!cancelled) timer = window.setTimeout(poll, 700); }
    };
    void poll();
    return () => { cancelled = true; window.clearInterval(timer); };
  }, [active?.id, active?.status]);

  const select = (run: Run | null, focus = true) => {
    selectionEpoch.current += 1; activeRef.current = run;
    setActive(run); setError(''); setMessage(''); setAcceptedOnly(false);
    window.history.replaceState(null, '', run ? `?run=${run.id}` : window.location.pathname);
    if (focus) window.setTimeout(() => headingRef.current?.focus(), 0);
  };
  const eligibleRecords = active?.records.filter(record => !record.source_issue) ?? [];
  const withheldRecords = active?.records.filter(record => record.source_issue) ?? [];
  const saved = (run: Run) => { setActive(run); setRuns(old => [run, ...old.filter(r => r.id !== run.id)]); };
  const websiteChosen = (run: Run) => {
    setRuns(old => old.map(value => value.id === run.id ? run : value));
    if (activeRef.current?.id === run.id) {
      activeRef.current = run; setActive(run);
      window.setTimeout(() => { if (activeRef.current?.id === run.id) headingRef.current?.focus(); }, 0);
    }
  };
  const stopped = (run: Run) => {
    setRuns(old => old.map(value => value.id === run.id ? run : value));
    if (activeRef.current?.id === run.id) {
      selectionEpoch.current += 1; activeRef.current = run; setActive(run);
      window.setTimeout(() => { if (activeRef.current?.id === run.id) headingRef.current?.focus(); }, 0);
    }
    void api.credits().then(setWallet).catch(reason => setError(describeError(reason)));
  };
  const deleted = () => {
    if (!active) return;
    setRuns(old => old.filter(run => run.id !== active.id)); select(null);
    requestKey.current = crypto.randomUUID(); setMessage('Saved research deleted. Your credit balance is unchanged.');
  };
  // A draft written before signup for this company becomes the run: no second page read or model call. Claiming waits
  // while it is still being written, starts afresh if it expired, and leaves it in place if the account cannot start yet.
  const startResearch = async (company: string) => {
    const draft = peekKeptDraft();
    if (draft && draft.website === company) {
      for (let attempt = 0; attempt < 40; attempt++) {
        try { const run = await api.claimDraft(draft.id, draft.claim); clearKeptDraft(); return run; }
        catch (reason) {
          if (reason instanceof ApiError && reason.status === 409) { await new Promise(resolve => window.setTimeout(resolve, 1500)); continue; }
          if (reason instanceof ApiError && reason.status === 404) { clearKeptDraft(); break; }
          throw reason;
        }
      }
    }
    return api.start(company, requestKey.current);
  };
  const begin = async (company: string) => {
    setSaving(true); setError('');
    try {
      const run = await startResearch(company);
      saved(run); select(run); requestKey.current = crypto.randomUUID();
    } catch (e) { setError(describeError(e)); } finally { setSaving(false); setHandoff(''); }
  };
  const start = async (event: FormEvent) => { event.preventDefault(); await begin(website); };
  const trySample = async () => {
    setSaving(true); setError('');
    try {
      const run = await api.startSample(requestKey.current);
      saved(run); select(run); requestKey.current = crypto.randomUUID();
    } catch (e) { setError(describeError(e)); } finally { setSaving(false); }
  };
  useEffect(() => {
    if (!handoff || loading || handingOff.current) return;
    if (active || previewWorkspace) { setHandoff(''); return; }
    handingOff.current = true;
    void begin(handoff);
  // begin reads the current request key and setters; it runs at most once per handoff
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [handoff, loading, active]);
  const handingOver = Boolean(handoff && !active);
  const needsSetup = Boolean(!previewWorkspace && health?.mode === 'local' && (!health.search_ready || !health.gemma_ready));
  const pending = active && ['queued', 'running'].includes(active.status);
  const results = active && active.seller_url && ['ready', 'partial'].includes(active.status);
  const showSidebar = Boolean(active || runs.length);
  return <BrandfetchContext value={brandfetchClientId}>
    <a className="skip-link" href="#main">Skip to research</a>
    <header className="topbar"><button ref={historyTrigger} className="mobile-history-trigger" type="button" aria-label="Saved runs" aria-controls="research-drawer" aria-expanded={mobileHistoryOpen} aria-haspopup="dialog" onClick={() => setMobileHistoryOpen(true)}><MenuToggleIcon open={mobileHistoryOpen} /></button><a className="brand" href="/" onClick={e => { e.preventDefault(); select(null); }}><span>GTM Shortlist</span></a>{showSidebar && <button className="desktop-history-toggle" type="button" aria-controls="research-navigation" aria-expanded={!historyCollapsed} aria-label={historyCollapsed ? 'Show saved runs' : 'Hide saved runs'} title={historyCollapsed ? 'Show saved runs' : 'Hide saved runs'} onClick={() => setHistoryCollapsed(value => !value)}><svg width="20" height="20" viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d={historyCollapsed ? 'm9 6 6 6-6 6' : 'm15 6-6 6 6 6'} /></svg></button>}{active && <button className="mobile-new-trigger" type="button" aria-label="New shortlist" title="New shortlist" onClick={() => { select(null); requestKey.current = crypto.randomUUID(); }}><PlusIcon /></button>}<div className="workspace-account">{!account && <span className="local-label">Local research workspace</span>}{active && <button className="desktop-new-trigger" type="button" aria-label="New shortlist" onClick={() => { select(null); requestKey.current = crypto.randomUUID(); }}><PlusIcon /><span>New shortlist</span></button>}{account ? <AccountTray onClosed={restoreMobileMenuFocus} account={account} wallet={wallet} showActivity={showActivity} onActivity={() => setShowActivity(value => !value)} /> : health?.mode === 'local' && <LocalSearchSetup onClosed={restoreMobileMenuFocus} health={health} onSaved={setHealth} readOnly={Boolean(previewWorkspace)} brandfetchClientId={brandfetchClientId} onBrandfetchSaved={setBrandfetchOverride} /> }</div></header>
    <div className={`workspace ${active ? 'has-research' : 'new-research'}${showSidebar ? '' : ' first-visit'}`}><ResearchSidebar collapsed={historyCollapsed} visibleDesktop={showSidebar} mobileOpen={mobileHistoryOpen} onMobileClose={closeMobileHistory} settingsTarget={account ? 'account-tray' : health?.mode === 'local' ? 'local-settings' : undefined} runs={runs} activeId={active?.id} loading={loading} onNew={() => { select(null); requestKey.current = crypto.randomUUID(); }} onSelect={run => select(run)} />
    <SampleContext value={Boolean(active?.sample)}><main id="main" className="main" tabIndex={-1}>{previewWorkspace && <aside className="notice preview-notice" role="note"><p>Design preview · no live research</p><a href={previewWorkspace}>Open the research workspace<Arrow /></a></aside>}
      {active?.sample && <aside className="notice sample-notice" role="note"><p><strong>Sample data</strong> · Invented companies and pages. Nothing was searched or fetched.</p>{health?.mode === 'local' && (!health.search_ready || !health.gemma_ready) && <button type="button" className="text-button" onClick={() => openLocalSetup(health.gemma_ready ? 'search' : 'model')}>Set up real research<Arrow /></button>}</aside>}<div className="page-heading">{!active && !handingOver && <WorkshopField />}<h1 ref={headingRef} tabIndex={-1}>{handingOver ? 'Starting your research' : active?.termination === 'user_stopped' ? 'Research stopped' : pending ? active?.status === 'queued' && !active.progress.worker_online ? 'Research is waiting' : 'Researching your shortlist' : active ? active.status === 'awaiting_confirmation' ? 'Confirm your target' : active.profile ? 'Review your shortlist' : 'Define your shortlist' : 'Find companies that fit your offer.'}</h1><p>{handingOver ? 'You confirm the target before company discovery.' : active?.status === 'awaiting_confirmation' ? 'Review your offer and target below. Discovery starts after you confirm.' : active ? 'Saved research. Trace every assessment back to its source.' : 'Start with your company. We’ll help you build a shortlist backed by sources.'}</p>{handingOver && <p className="handoff-status" role="status"><StatusMark status="work" />Reading {handoff}</p>}</div>
      {error && <div className="notice" role="alert">{error}<button className="text-button" onClick={() => window.location.reload()}>Reload workspace</button></div>}
      {active?.can_retry_seller && <RetrySeller key={`retry-${active.id}`} run={active} onSaved={websiteChosen} />}
      {active?.can_continue_discovery && <ContinueDiscovery key={`continue-${active.id}`} run={active} onSaved={websiteChosen} />}
      {!active && !handingOver && <LandingDemo demo={!needsSetup}><section className="sheet start-sheet" aria-labelledby="start-heading"><h2 id="start-heading" className="sr-only">Start your company research</h2><form onSubmit={start}><label htmlFor="website">Company name or website</label><div className="website-form"><CompanySearch value={website} onChange={value => { setWebsite(value); requestKey.current = crypto.randomUUID(); }} clientId={brandfetchClientId} disabled={saving} /><button disabled={saving || loading || Boolean(previewWorkspace)} aria-busy={saving} type="submit">{saving ? 'Starting research…' : 'Start research'}<Arrow /></button></div></form><p className="hint">Up to three companies. You confirm the target before discovery.</p>{needsSetup && health && <LocalSetupCard health={health} onSample={() => void trySample()} starting={saving} />}</section></LandingDemo>}
      {active && <ResearchProgress key={active.id} run={active} connected={!error} localResearch={health?.mode === 'local' && !previewWorkspace} />}{active && ['queued', 'running'].includes(active.status) && <ResearchStop key={`stop-${active.id}`} run={active} onStopped={stopped} />}{active?.credits && <p className="batch-credit-summary" role="status">{active.credits.used} {active.credits.used === 1 ? 'credit' : 'credits'} used · {active.credits.reserved} reserved · {active.credits.returned} returned</p>}
      {active && !pending && !active.termination && !active.seller_url && <WebsiteChoice key={`website-${active.id}`} run={active} onSaved={websiteChosen} />}{active?.status === 'awaiting_confirmation' && active.seller_url && <>{health && !health.search_ready && !active.sample && <p className="notice">Company search is not configured. Your target can be saved; configure search before discovery.</p>}<ConfirmationForm key={`offer-${active.id}`} run={{ ...active, seller_url: active.seller_url }} wallet={wallet} hostedAccount={account != null} onSaved={saved} /></>}{active?.status === 'awaiting_confirmation' && <ResearchStop key={`stop-${active.id}`} run={active} onStopped={stopped} />}
      {results && <><div className="results-toolbar"><div><h2>{eligibleRecords.length} {eligibleRecords.length === 1 ? 'company' : 'companies'} researched</h2><p>{active.status === 'partial' ? 'Some questions remain open. Review the unknowns before using these records.' : 'Model assessments are ready for your review.'}</p></div>{!!active.records.length && <div className="export-controls"><label className="checkbox-label"><input type="checkbox" checked={acceptedOnly} onChange={e => setAcceptedOnly(e.target.checked)} />Accepted only</label><div className="export-links">{(['xlsx', 'csv', 'json'] as const).map(format => <a className="secondary button-link" key={format} href={`/api/runs/${active.id}/export?format=${format}&accepted_only=${acceptedOnly}`} onClick={event => { event.preventDefault(); void api.download(active.id, format, acceptedOnly, active.sample).catch(reason => setError(describeError(reason))); }}>Export {format === 'xlsx' ? 'Excel' : format.toUpperCase()}</a>)}</div></div>}</div>
        {active.error && <p className="notice" role="status">{active.error}</p>}
        {!!withheldRecords.length && <section className="notice" aria-label="Excluded saved sources"><h3>{withheldRecords.length} saved {withheldRecords.length === 1 ? "source" : "sources"} excluded from the shortlist</h3><p>These historical entries do not establish an official company. Original evidence is preserved in research history and JSON export.</p><ul>{withheldRecords.map(record => <li key={record.research.id}>{record.research.domain}: {record.source_issue}</li>)}</ul></section>}
        {eligibleRecords.length ? <section className="company-shortlist" aria-label="Researched companies"><p className="shortlist-instruction">Compare the companies, then open a research sheet to inspect evidence and decide.</p>{eligibleRecords.map(record => <CompanyReview key={record.research.id} record={record} run={active} onSaved={saved} />)}</section> : <section className="sheet"><h3>{withheldRecords.length ? "No eligible company records" : "No company records yet"}</h3><p>{withheldRecords.length ? "The saved sources did not establish official company identities." : "The run stopped before usable research could be saved."} {active.profile ? 'Your confirmed target is preserved.' : 'Your saved seller inputs remain available.'}</p><button className="secondary" onClick={() => select(null)}>Start another shortlist</button></section>}
        <section className="results-context" aria-label="Research context">
        {active.profile && <details className="target-summary"><summary>Confirmed target and offer</summary><p>{active.profile.offer}</p><p>{active.profile.target}</p>{!!active.profile.exclusions.length && <p>Exclusions: {active.profile.exclusions.join('; ')}</p>}<p className="hint">Confirmed {date(active.profile.confirmed_at)}. Start a new run to change this target.</p></details>}
        {active.profile && !active.sample && <ReuseOffer key={active.id} run={active} onSaved={run => { saved(run); select(run); }} />}
        </section>
      </>}
      {results && active.profile && eligibleRecords.length > 0 && service?.booking_url && <section className="setup-call" aria-labelledby="setup-heading"><div><h2 id="setup-heading">Discuss your shortlist</h2><p>Get help with your target, evidence and next steps. The setup call is optional.</p></div><a className="secondary button-link" href={service.booking_url} target="_blank" rel="noopener noreferrer" onClick={() => { if (navigator.doNotTrack !== '1') void api.bookingClick(active.id).catch(() => undefined); }}>Book an optional setup call<Arrow /></a></section>}
      {active && !pending && <DeleteResearch key={`delete-${active.id}`} run={active} onDeleted={deleted} />}
      {message && <p className="notice" role="status">{message}</p>}
      <footer className="workspace-footer"><p>GTM Shortlist</p></footer>
    </main></SampleContext></div>
  </BrandfetchContext>;
}

const root = document.getElementById('root');
if (!root) throw new Error('Application root is missing');
// ?landing=1 previews the hosted landing page in any mode; its Start research hands the company to this workspace.
const LandingPreview = lazy(() => import('./landing/PublicLanding').then(module => ({ default: () => <module.PublicLanding directoryId={savedBrandfetchId() ?? configuredDirectoryId()} iconLookup onSignIn={() => window.location.assign('/?auth=signin')} onStart={company => { keepCompany(company); window.location.assign('/'); }} /> })));
const params = new URLSearchParams(window.location.search);
createRoot(root).render(<StrictMode>{params.get('demo') === '1' ? <DemoPage /> : params.get('landing') === '1' ? <Suspense fallback={null}><LandingPreview /></Suspense> : <AuthGate workspace={(identity, account) => <App key={identity} identity={identity} account={account} />} />}</StrictMode>);
