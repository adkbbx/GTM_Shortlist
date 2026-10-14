import { StrictMode, useEffect, useRef, useState } from 'react';
import type { FormEvent, ReactNode } from 'react';
import { createRoot } from 'react-dom/client';
import '@fontsource/schibsted-grotesk/400.css';
import '@fontsource/schibsted-grotesk/600.css';
import '@fontsource/schibsted-grotesk/700.css';
import { api } from './api';
import type { Confirmation, Evidence, ExclusionFinding, Finding, Health, Record, Review, Run, Service, Wallet } from './api';
import { ResearchProgress } from './ResearchProgress';
import { ResearchPreview } from './ResearchPreview';
import { AuthGate } from './AuthGate';
import './styles.css';

const describeError = (error: unknown) => error instanceof Error ? error.message : 'Something went wrong. Please try again.';
const date = (value: string) => new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value));
const qualification = { fits: 'Fits the required criteria', needs_verification: 'Needs verification', does_not_fit: 'Does not fit' };

function Arrow() {
  return <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M4 12h15m-6-6 6 6-6 6" stroke="currentColor" strokeWidth="1.5" /></svg>;
}

function ConfirmationForm({ run, wallet, hostedAccount, onSaved }: { run: Run; wallet: Wallet | null; hostedAccount: boolean; onSaved: (run: Run) => void }) {
  const [offer, setOffer] = useState(run.draft?.offer ?? '');
  const [target, setTarget] = useState(run.draft?.target ?? '');
  const [criteria, setCriteria] = useState<Confirmation['criteria']>(run.draft?.criteria ?? [{ id: 'criterion-1', description: '', required: true }]);
  const [exclusions, setExclusions] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [companyLimit, setCompanyLimit] = useState(3);
  const available = run.legacy_credit_exempt ? 3 : wallet?.available ?? 3;
  useEffect(() => { if (wallet?.mode === 'hosted' && available > 0) setCompanyLimit(old => Math.min(old, available)); }, [available, wallet?.mode]);
  const submit = async (event: FormEvent) => {
    event.preventDefault(); setSaving(true); setError('');
    try {
      onSaved(await api.confirm(run.id, { offer, target, criteria, company_limit: companyLimit,
        exclusions: exclusions.split('\n').map(s => s.trim()).filter(Boolean) }));
    } catch (e) { setError(describeError(e)); } finally { setSaving(false); }
  };
  const useEygentic = () => {
    setOffer('Eygentic helps B2B SaaS companies test customer acquisition hypotheses through focused experiments, from GTM diagnosis to ongoing experimentation.');
    setTarget('Private AI B2B SaaS startups');
    setCriteria([
      { id: 'ai', description: 'Offers software with artificial intelligence as a core capability', required: true },
      { id: 'b2b', description: 'Sells software to businesses', required: true },
      { id: 'saas', description: 'Offers software as a subscription or hosted service', required: true },
      { id: 'private', description: 'Privately held startup, with explicit current evidence of ownership and startup stage', required: true },
    ]);
  };
  return <section className="sheet confirmation" aria-labelledby="confirm-heading">
    <div className="sheet-heading"><h2 id="confirm-heading">Confirm what a good fit means</h2><span className="step-label">Your target</span></div>
    <p className="intro">Edit the offer and criteria before discovery. This version stays attached to the research it produces.</p>
    {run.error && <div className="notice" role="status">{run.error}</div>}
    <p className="website">Seller website <a href={run.seller_url} target="_blank" rel="noopener noreferrer">{run.seller_url}</a></p>
    {['eygentic.com', 'www.eygentic.com'].includes(new URL(run.seller_url).hostname) && <button type="button" className="text-button" onClick={useEygentic}>Use the agreed Eygentic brief</button>}
    <form onSubmit={submit}>
      <label htmlFor="offer">What do you sell?</label>
      <textarea id="offer" required minLength={10} maxLength={4000} rows={4} value={offer} onChange={e => setOffer(e.target.value)} />
      <label htmlFor="target">Who should we look for?</label>
      <textarea id="target" required minLength={5} maxLength={2000} rows={2} value={target} onChange={e => setTarget(e.target.value)} />
      <fieldset><legend>Fit criteria</legend><p className="hint">Required criteria must have evidence. An unknown stays visible as a question to verify.</p>
        {criteria.map((criterion, index) => <div className="criterion-input" key={criterion.id}>
          <label htmlFor={`criterion-${index}`}>Criterion {index + 1}</label>
          <input id={`criterion-${index}`} value={criterion.description} required minLength={3} maxLength={500}
            onChange={e => setCriteria(criteria.map((c, i) => i === index ? { ...c, description: e.target.value } : c))} />
          <div className="criterion-controls"><label className="checkbox-label"><input type="checkbox" checked={criterion.required}
            onChange={e => setCriteria(criteria.map((c, i) => i === index ? { ...c, required: e.target.checked } : c))} />Required</label>
            {criteria.length > 1 && <button type="button" className="text-button" onClick={() => setCriteria(criteria.filter((_, i) => i !== index))} aria-label={`Remove criterion ${index + 1}`}>Remove</button>}</div>
        </div>)}
        <button type="button" className="secondary" disabled={criteria.length >= 12} onClick={() => setCriteria([...criteria, { id: crypto.randomUUID(), description: '', required: true }])}>Add a criterion</button>
      </fieldset>
      <label htmlFor="exclusions">Exclude from consideration <span className="optional">Optional, one per line</span></label>
      <textarea id="exclusions" value={exclusions} rows={2} maxLength={6012} onChange={e => setExclusions(e.target.value)} aria-describedby="exclusions-help" />
      <p id="exclusions-help" className="hint">Up to 12 conditions, 3–500 characters each. Each needs evidence; an unverified exclusion stays unknown.</p>
      {run.draft?.unknowns.length ? <div className="unknowns"><h3>Still unknown about your offer</h3><ul>{run.draft.unknowns.map(u => <li key={u}>{u}</li>)}</ul></div> : null}
      {hostedAccount && wallet === null && <p className="notice" role="status">Your credit balance must load before you can confirm the batch cost. Reload the workspace to retry.</p>}
      {wallet?.mode === 'hosted' && <section className="batch-choice"><label htmlFor="company-limit">Companies in this batch</label><select id="company-limit" value={companyLimit} onChange={event => setCompanyLimit(Number(event.target.value))}>{[1, 2, 3].map(quantity => <option key={quantity} value={quantity} disabled={quantity > available}>{quantity} {quantity === 1 ? 'company' : 'companies'}</option>)}</select><p>{run.legacy_credit_exempt ? 'Your original demo allowance is preserved.' : `Maximum ${companyLimit} ${companyLimit === 1 ? 'credit' : 'credits'} · ${wallet.available} available`}</p><p className="hint">Completed unknown or non-fit research counts. Credits for technical failures are returned. Review and export are free.</p>{available === 0 && <p className="notice">No research credits available. Saved research stays accessible. Credit purchases are not available yet.</p>}</section>}
      {error && <p className="notice" role="alert">{error}</p>}
      <div className="form-footer"><p>No outreach is sent. You review every company.</p><button type="submit" disabled={saving || (hostedAccount && wallet === null) || (wallet?.mode === 'hosted' && available < companyLimit)}>{saving ? 'Saving target…' : 'Confirm target and discover'}<Arrow /></button></div>
    </form>
  </section>;
}

function EvidenceDetails({ passages, record }: { passages: Evidence[]; record: Record }) {
  return passages.map((evidence, index) => {
      const source = record.research.sources.find(s => s.id === evidence.source_id);
      return <details className="evidence" key={`${evidence.source_id}-${index}`}><summary>{evidence.claim}<span>Inspect passage</span></summary>
        <blockquote>{evidence.passage}</blockquote>
        {source && <div className="source-meta"><a href={source.url} target="_blank" rel="noopener noreferrer">{source.title}<Arrow /></a><p>Retrieved {date(source.retrieved_at)}</p><p>{source.published_at ? `Published ${date(source.published_at)}` : 'Publication date unknown'}</p></div>}
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

function CompanySheet({ record, run, onSaved }: { record: Record; run: Run; onSaved: (run: Run) => void }) {
  const [reason, setReason] = useState(record.review?.reason ?? '');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const save = async (decision: Review['decision']) => {
    setSaving(true); setError('');
    try { onSaved(await api.review(run.id, record.research.id, decision, reason)); }
    catch (e) { setError(describeError(e)); } finally { setSaving(false); }
  };
  const research = record.research;
  return <article className="sheet company-sheet">
    <header className="company-heading"><div><h3>{research.name}</h3><a href={`https://${research.domain}`} target="_blank" rel="noopener noreferrer">{research.domain}<Arrow /></a></div>
      <p className="qualification">{qualification[research.qualification]}<span>{research.status === 'partial' ? 'Partial research' : 'Research saved'}</span></p></header>
    {record.credits_used != null && <p className="delivery-credit">{record.credits_used ? '1 research credit used' : 'No research credit charged'}</p>}
    <div className="findings">{research.findings.map(f => <FindingSheet key={f.criterion_id} finding={f} record={record} run={run} />)}</div>
    {!!research.exclusion_findings.length && <section className="hypotheses exclusion-checks"><h4>Exclusion checks</h4><p className="hint">A matched exclusion means the company does not fit. Missing evidence remains unknown.</p>{research.exclusion_findings.map(f => <ExclusionSheet key={f.exclusion_id} finding={f} record={record} run={run} />)}</section>}
    {!!research.hypotheses.length && <section className="hypotheses"><h4>Hypotheses to test</h4><p className="hint">Possible relevance, not observed buying intent.</p>{research.hypotheses.map(h => <div key={h.text}><p>{h.text}</p><p className="hint">Assumptions: {h.assumptions.join('; ')}</p></div>)}</section>}
    {!research.sources.length && <p className="notice">No readable source was saved. Verify this company before accepting it.</p>}
    <section className="review"><div className="review-heading"><h4>Your review</h4><span aria-live="polite">{record.review ? `Saved: ${record.review.decision.replace('_', ' ')}` : 'Not reviewed'}</span></div>
      <label htmlFor={`reason-${research.id}`}>Review note <span className="optional">Optional</span></label>
      <textarea id={`reason-${research.id}`} rows={2} value={reason} onChange={e => setReason(e.target.value)} />
      <div className="review-actions"><button disabled={saving} onClick={() => save('accepted')} className={record.review?.decision === 'accepted' ? '' : 'secondary'}>Accept company</button><button disabled={saving} onClick={() => save('needs_research')} className="secondary">Needs research</button><button disabled={saving} onClick={() => save('rejected')} className="text-button">Reject</button></div>
      {error && <p role="alert" className="notice">{error}</p>}
    </section>
  </article>;
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

function App({ account }: { account: ReactNode }) {
  const [health, setHealth] = useState<Health | null>(null);
  const [wallet, setWallet] = useState<Wallet | null>(null);
  const [service, setService] = useState<Service | null>(null);
  const [runs, setRuns] = useState<Run[]>([]);
  const [active, setActive] = useState<Run | null>(null);
  const [website, setWebsite] = useState('');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [acceptedOnly, setAcceptedOnly] = useState(false);
  const [message, setMessage] = useState('');
  const requestKey = useRef(crypto.randomUUID());
  const headingRef = useRef<HTMLHeadingElement>(null);

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
    let timer: number | undefined;
    const poll = async () => {
      try {
        const run = await api.run(active.id);
        if (!cancelled) { setActive(run); setError(''); setRuns(old => old.map(r => r.id === run.id ? run : r)); }
      } catch (e) { if (!cancelled) setError(describeError(e)); }
      finally { if (!cancelled) timer = window.setTimeout(poll, 700); }
    };
    void poll();
    return () => { cancelled = true; window.clearInterval(timer); };
  }, [active?.id, active?.status]);

  const select = (run: Run | null, focus = true) => {
    setActive(run); setError(''); setMessage(''); setAcceptedOnly(false);
    window.history.replaceState(null, '', run ? `?run=${run.id}` : window.location.pathname);
    if (focus) window.setTimeout(() => headingRef.current?.focus(), 0);
  };
  const saved = (run: Run) => { setActive(run); setRuns(old => [run, ...old.filter(r => r.id !== run.id)]); };
  const deleted = () => {
    if (!active) return;
    setRuns(old => old.filter(run => run.id !== active.id)); select(null);
    requestKey.current = crypto.randomUUID(); setMessage('Saved research deleted. Your credit balance is unchanged.');
  };
  const start = async (event: FormEvent) => {
    event.preventDefault(); setSaving(true); setError('');
    try {
      const run = await api.start(website, requestKey.current);
      saved(run); select(run); requestKey.current = crypto.randomUUID();
    } catch (e) { setError(describeError(e)); } finally { setSaving(false); }
  };
  const pending = active && ['queued', 'running'].includes(active.status);
  const results = active && ['ready', 'partial'].includes(active.status);
  return <>
    <a className="skip-link" href="#main">Skip to research</a>
    <header className="topbar"><a className="brand" href="/" onClick={e => { e.preventDefault(); select(null); }}><span className="brand-mark" aria-hidden="true"><svg viewBox="0 0 32 32" fill="none"><path d="M5 25 16 5l11 20H5Zm6-7h10M16 5v22M8 28h16" stroke="currentColor" strokeWidth="1.2" /></svg></span><span>eygentic<span className="brand-product">GTM Shortlist</span></span></a><div className="workspace-account">{wallet?.mode === 'hosted' && <p className="wallet-balance" aria-live="polite">{wallet.available} {wallet.available === 1 ? 'credit' : 'credits'} available{wallet.reserved > 0 && <span>{wallet.reserved} reserved</span>}</p>}{account ?? <span className="local-label">Local research workspace</span>}</div></header>
    <div className={`workspace ${active ? 'has-research' : 'new-research'}`}><aside className="sidebar" aria-label="Saved research"><button className="new-run secondary" onClick={() => { select(null); requestKey.current = crypto.randomUUID(); }}>New shortlist<Arrow /></button><h2>Saved runs</h2>
      {loading ? <p>Loading saved research…</p> : runs.length ? <nav>{runs.map(run => <button key={run.id} className={`saved-run ${active?.id === run.id ? 'selected' : ''}`} onClick={() => select(run)} aria-current={active?.id === run.id ? 'page' : undefined}><span>{new URL(run.seller_url).hostname}</span><small>{date(run.created_at)}</small><small>{run.status.replaceAll('_', ' ')}</small></button>)}</nav> : <p className="hint">Your research will stay here after you close the browser.</p>}
      <div className="sidebar-note"><p>Evidence before outreach.</p><p className="hint">Company fit, your acceptance, and buying intent are separate things.</p></div>
    </aside>
    <main id="main" className="main" tabIndex={-1}><div className="page-heading"><h1 ref={headingRef} tabIndex={-1}>{active ? active.profile ? 'Review your shortlist' : 'Define your shortlist' : 'Find your next shortlist.'}</h1><p>{active ? 'Saved research. Trace every assessment back to its source.' : 'Turn your offer into a focused list of companies. Understand the fit, inspect the sources, and make the call.'}</p></div>
      {error && <div className="notice" role="alert">{error}<button className="text-button" onClick={() => window.location.reload()}>Reload workspace</button></div>}
      {!active && <><div className="start-grid"><section className="sheet start-sheet" aria-labelledby="start-heading"><h2 id="start-heading">What is your company website?</h2><p>We’ll draft your offer and target from the website. You can correct both before any company discovery starts.</p><form onSubmit={start}><label htmlFor="website">Seller website</label><div className="website-form"><input id="website" type="url" placeholder="https://your-company.com" required maxLength={2048} value={website} onChange={e => { setWebsite(e.target.value); requestKey.current = crypto.randomUUID(); }} /><button disabled={saving || loading} type="submit">{saving ? 'Saving…' : 'Understand my offer'}<Arrow /></button></div></form><p className="hint">Up to three research sheets. Saved sources. CSV and JSON export.</p></section><ResearchPreview /></div><section className="method" aria-label="How research works"><h2>A shortlist you can inspect</h2><ol><li><span>Confirm your offer</span><p>Edit who you serve and what counts as a fit.</p></li><li><span>Trace the evidence</span><p>Read source passages and see what remains unknown.</p></li><li><span>Review and export</span><p>Accept or reject each company using your own judgment.</p></li></ol></section></>}
      {active && <ResearchProgress run={active} connected={!error} />}{active?.credits && <p className="batch-credit-summary" role="status">{active.credits.used} {active.credits.used === 1 ? 'credit' : 'credits'} used · {active.credits.reserved} reserved · {active.credits.returned} returned</p>}
      {active?.status === 'awaiting_confirmation' && <>{health && !health.search_ready && <p className="notice">Live company search is not configured yet. Your target can be saved, but discovery needs Tavily or SerpApi connected.</p>}<ConfirmationForm key={active.id} run={active} wallet={wallet} hostedAccount={account != null} onSaved={saved} /></>}
      {results && <><div className="results-toolbar"><div><h2>{active.records.length} {active.records.length === 1 ? 'company' : 'companies'} researched</h2><p>{active.status === 'partial' ? 'Some questions remain open. Review the unknowns before using these records.' : 'Model assessments are ready for your review.'}</p></div>{!!active.records.length && <div className="export-controls"><label className="checkbox-label"><input type="checkbox" checked={acceptedOnly} onChange={e => setAcceptedOnly(e.target.checked)} />Accepted only</label><div className="export-links">{(['csv', 'json'] as const).map(format => <a className="secondary button-link" key={format} href={`/api/runs/${active.id}/export?format=${format}&accepted_only=${acceptedOnly}`} onClick={event => { event.preventDefault(); void api.download(active.id, format, acceptedOnly).catch(reason => setError(describeError(reason))); }}>Export {format.toUpperCase()}</a>)}</div></div>}</div>
        {active.error && <p className="notice" role="status">{active.error}</p>}
        {active.profile && <details className="target-summary"><summary>Confirmed target and offer</summary><p>{active.profile.offer}</p><p>{active.profile.target}</p>{!!active.profile.exclusions.length && <p>Exclusions: {active.profile.exclusions.join('; ')}</p>}<p className="hint">Confirmed {date(active.profile.confirmed_at)}. Start a new run to change this target.</p></details>}
        {active.records.length ? active.records.map(record => <CompanySheet key={record.research.id} record={record} run={active} onSaved={saved} />) : <section className="sheet"><h3>No company records yet</h3><p>The run stopped before usable research could be saved. Your confirmed target is preserved.</p><button className="secondary" onClick={() => select(null)}>Start another shortlist</button></section>}
      </>}
      {results && active.profile && active.records.length > 0 && service?.booking_url && <section className="setup-call" aria-labelledby="setup-heading"><div><h2 id="setup-heading">Discuss your shortlist</h2><p>Get help with your target, evidence and next steps. The setup call is optional.</p></div><a className="secondary button-link" href={service.booking_url} target="_blank" rel="noopener noreferrer" onClick={() => { if (navigator.doNotTrack !== '1') void api.bookingClick(active.id).catch(() => undefined); }}>Book an optional setup call<Arrow /></a></section>}
      {active && !pending && <DeleteResearch key={active.id} run={active} onDeleted={deleted} />}
      {message && <p className="notice" role="status">{message}</p>}
      <footer className="workspace-footer"><p>GTM Shortlist by Eygentic</p><p>Research supports judgment. It does not establish buying intent.</p>{health && <p className="hint">{health.search_ready && health.gemma_ready ? 'Research providers configured' : 'Research providers still need configuration'}</p>}</footer>
    </main></div>
  </>;
}

const root = document.getElementById('root');
if (!root) throw new Error('Application root is missing');
createRoot(root).render(<StrictMode><AuthGate workspace={(identity, account) => <App key={identity} account={account} />} /></StrictMode>);
