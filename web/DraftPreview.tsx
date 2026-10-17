import { useEffect, useRef, useState } from 'react';
import { api, ApiError } from './api';
import type { DraftView } from './api';
import { browserId, clearKeptDraft, keepDraft, peekKeptDraft } from './landing/kept-company';
import type { KeptDraft } from './landing/kept-company';
import { turnstileToken } from './landing/turnstile';
import { StatusMark } from './StatusMark';

function Arrow() {
  return <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M4 12h15m-6-6 6 6-6 6" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" /></svg>;
}

const hostOf = (website: string) => { try { return new URL(/^https?:\/\//i.test(website) ? website : `https://${website}`).hostname; } catch { return website; } };

/** Before signup: the visitor's own offer, target and fit checks, drafted live from their website. One page read and
    one model call; nothing is searched. Saving opens sign-up, and the draft becomes the account's first run. */
export function DraftPreview({ website, siteKey, onSave, onBack }: { website: string; siteKey: string; onSave: () => void; onBack: () => void }) {
  const check = useRef<HTMLDivElement>(null);
  const started = useRef(false);
  const [kept, setKept] = useState<KeptDraft | null>(() => {
    const draft = peekKeptDraft();
    if (draft && draft.website !== website) clearKeptDraft();  // A draft for another company is never claimed by mistake.
    return draft?.website === website ? draft : null;
  });
  const [draft, setDraft] = useState<DraftView | null>(null);
  const [error, setError] = useState('');
  useEffect(() => {
    if (kept || started.current || !check.current) return;
    started.current = true;
    const host = check.current;
    void (async () => {
      try {
        const created = await api.startDraft(website, browserId(), await turnstileToken(siteKey, host));
        const saved = { id: created.id, claim: created.claim_token, website };
        keepDraft(saved); setKept(saved);
      } catch (reason) { setError(reason instanceof Error ? reason.message : 'Your draft could not be started.'); }
    })();
  }, [kept, siteKey, website]);
  useEffect(() => {
    if (!kept) return;
    let cancelled = false;
    let timer: number | undefined;
    const poll = async () => {
      try {
        const next = await api.readDraft(kept.id, kept.claim);
        if (cancelled) return;
        setDraft(next);
        if (next.status === 'queued' || next.status === 'running') timer = window.setTimeout(poll, 1200);
      } catch (reason) {
        if (cancelled) return;
        if (reason instanceof ApiError && reason.status === 404) clearKeptDraft();
        setError(reason instanceof Error ? reason.message : 'Your draft could not be read.');
      }
    };
    void poll();
    return () => { cancelled = true; window.clearTimeout(timer); };
  }, [kept]);
  const host = hostOf(website);
  const ready = draft?.status === 'ready' ? draft.draft : null;
  const problem = error || (draft?.status === 'failed' ? draft.error ?? 'We couldn\'t finish the draft.' : '');
  // Each step shows once: a started step disappears when the step after it is saved.
  const steps = (draft?.events ?? []).filter((event, index, all) => event.state !== 'started' || index === all.length - 1);
  return <main className="account-page account-entry draft-page">
    <header className="account-header"><a className="account-brand" href="/" onClick={event => { event.preventDefault(); onBack(); }}>GTM Shortlist</a><button type="button" className="text-button" onClick={onBack}>Back</button></header>
    <section className="sheet account-sheet draft-sheet" aria-labelledby="draft-heading" aria-busy={!ready && !problem}>
      <h1 id="draft-heading">{ready ? 'Here is what we understood' : problem ? 'Your draft needs an account' : `Reading ${host}`}</h1>
      <p className="intro">{ready ? `Drafted from ${host}. Nothing was searched. Save it to find companies that fit; you can edit everything first.` : problem ? 'Create your free account and research starts from your website.' : 'One page read and one draft from it. No search, no account yet.'}</p>
      <div ref={check} className="draft-check" />
      {!ready && !problem && <ol className="draft-steps" aria-label="Draft progress" aria-live="polite">
        {(steps.length ? steps : [{ label: 'Checking this browser', state: 'started' as const, created_at: '' }]).map((step, index) =>
          <li key={`${step.label}-${index}`}><StatusMark status={step.state === 'succeeded' ? 'ok' : step.state === 'failed' ? 'fail' : 'work'} /><span>{step.label}</span></li>)}
      </ol>}
      {ready && <dl className="draft-result">
        <div><dt>What you sell</dt><dd>{ready.offer}</dd></div>
        <div><dt>Who to look for</dt><dd>{ready.target}</dd></div>
        {ready.criteria.length > 0 && <div><dt>Fit checks</dt><dd><ul>{ready.criteria.map(criterion => <li key={criterion.id}>{criterion.description}</li>)}</ul></dd></div>}
      </dl>}
      {problem && <p className="notice" role="alert">{problem}</p>}
      <div className="draft-actions">
        <button type="button" onClick={onSave}>{ready ? 'Save and find companies' : 'Create your free account'}<Arrow /></button>
        <p className="hint">First 3 companies free · no card needed. Discovery waits until you confirm the target.</p>
      </div>
    </section>
  </main>;
}
