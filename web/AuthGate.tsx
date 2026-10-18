import { lazy, Suspense, useEffect, useState } from 'react';
import type { FormEvent, ReactNode } from 'react';
import type { Session, SupabaseClient } from '@supabase/supabase-js';
import { api, setSessionAccess } from './api';
import type { AuthSetup } from './api';
import { keepCompany, peekKeptCompany, peekKeptDraft } from './landing/kept-company';
import { configuredDirectoryId } from './company-suggestions';
import { DraftPreview } from './DraftPreview';

// Hosted visitors without a session see the public landing page; it loads separately from the workspace.
const PublicLanding = lazy(() => import('./landing/PublicLanding').then(module => ({ default: module.PublicLanding })));
type AuthView = 'signin' | 'signup' | null;
const authView = (): AuthView => { const view = new URLSearchParams(window.location.search).get('auth'); return view === 'signin' || view === 'signup' ? view : null; };
// Saved-run links and auth callbacks belong to returning users: they go to sign-in, never to the public landing page.
const returningLink = () => { const params = new URLSearchParams(window.location.search); return ['run', 'code', 'error', 'error_description'].some(name => params.has(name)); };
const draftView = () => new URLSearchParams(window.location.search).has('draft');
// A draft before signup needs a website: looking up a company name is a search, which waits for an account.
const isWebsite = (value: string) => /^(https?:\/\/)?[^\s/@]+\.[a-z]{2,}(\/\S*)?$/i.test(value.trim());

type HostedSetup = Extract<AuthSetup, { mode: 'hosted' }>;
type State = { kind: 'loading' } | { kind: 'local' } | { kind: 'error'; message: string } |
  { kind: 'hosted'; setup: HostedSetup; client: SupabaseClient; session: Session | null; recovery: boolean; expired: boolean };
const message = (error: unknown) => error instanceof Error ? error.message : 'Account access is unavailable. Please try again.';
// The demo is a separate page; this tab remembers what the visitor typed so returning keeps it.
const BEFORE_DEMO = 'gtm-shortlist-before-demo';
function beforeDemo(): { email?: string; mode?: 'signin' | 'signup' } {
  try { return JSON.parse(window.sessionStorage.getItem(BEFORE_DEMO) ?? '{}'); } catch { return {}; }
}

function AccountForm({ client, setup, recovery, expired, externalError, onRecovered, initialMode = 'signin', keptCompany = '', keptDraft = false }: {
  client: SupabaseClient; setup: HostedSetup; recovery: boolean; expired: boolean; externalError: string; onRecovered: () => void;
  initialMode?: 'signin' | 'signup'; keptCompany?: string; keptDraft?: boolean;
}) {
  const [mode, setMode] = useState<'signin' | 'signup' | 'reset'>(() => beforeDemo().mode ?? initialMode);
  const [email, setEmail] = useState(() => beforeDemo().email ?? '');
  useEffect(() => { try { window.sessionStorage.removeItem(BEFORE_DEMO); } catch { /* Storage unavailable: nothing to clear. */ } }, []);
  const tryDemo = () => { try { window.sessionStorage.setItem(BEFORE_DEMO, JSON.stringify({ email, mode: mode === 'signup' ? 'signup' : 'signin' })); } catch { /* The demo still opens. */ } };
  const [password, setPassword] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [confirmationSent, setConfirmationSent] = useState(false);
  // A 6-digit email code signs people in or up in this tab: no password and no confirmation link to open elsewhere.
  const [method, setMethod] = useState<'code' | 'password'>(setup.email_code ? 'code' : 'password');
  const [codeSent, setCodeSent] = useState(false);
  const [code, setCode] = useState('');
  const usingCode = method === 'code' && !recovery && mode !== 'reset';
  const title = recovery ? 'Choose a new password' : mode === 'signup' ? 'Create your account' : mode === 'reset' ? 'Reset your password' : 'Sign in to your shortlist';
  const submit = async (event: FormEvent) => {
    event.preventDefault(); setSaving(true); setError(''); setNotice('');
    try {
      if (recovery) {
        const result = await client.auth.updateUser({ password });
        if (result.error) throw result.error;
        setPassword(''); onRecovered();
      } else if (mode === 'reset') {
        const result = await client.auth.resetPasswordForEmail(email, { redirectTo: setup.redirect_url });
        if (result.error) throw result.error;
        setNotice('If this email has an account, check your inbox for a password reset link.');
      } else if (mode === 'signup') {
        const result = await client.auth.signUp({ email, password, options: { emailRedirectTo: setup.redirect_url } });
        if (result.error) throw result.error;
        if (result.data.user?.identities?.length === 0) {
          setPassword(''); setError('An account already exists for this email. Sign in instead, or reset your password.');
          return;
        }
        setPassword(''); setNotice('Check your inbox for an account confirmation link, then sign in.');
        setConfirmationSent(true);
      } else {
        const result = await client.auth.signInWithPassword({ email, password });
        if (result.error) throw result.error;
        setPassword('');
      }
    } catch (reason) { setError(message(reason)); } finally { setSaving(false); }
  };
  const resend = async () => {
    setSaving(true); setError(''); setNotice('');
    try {
      const result = await client.auth.resend({ type: 'signup', email, options: { emailRedirectTo: setup.redirect_url } });
      if (result.error) throw result.error;
      setNotice('A new confirmation link has been requested. Check your inbox and use the newest email.');
    } catch (reason) { setError(message(reason)); } finally { setSaving(false); }
  };
  const sendCode = async (event?: FormEvent) => {
    event?.preventDefault(); setSaving(true); setError(''); setNotice('');
    try {
      const result = await client.auth.signInWithOtp({ email, options: { shouldCreateUser: true, emailRedirectTo: setup.redirect_url } });
      if (result.error) throw result.error;
      // The intro already says where the code went; a resend confirms that a newer code is on its way.
      setNotice(codeSent ? 'We sent a new code. Use the newest one.' : ''); setCodeSent(true); setCode('');
    } catch (reason) { setError(message(reason)); } finally { setSaving(false); }
  };
  const verifyCode = async (event: FormEvent) => {
    event.preventDefault(); setSaving(true); setError(''); setNotice('');
    try {
      const result = await client.auth.verifyOtp({ email, token: code.trim(), type: 'email' });
      if (result.error) throw result.error;
    } catch (reason) { setError(message(reason)); } finally { setSaving(false); }
  };
  const continueWithGoogle = async () => {
    setSaving(true); setError(''); setNotice('');
    const result = await client.auth.signInWithOAuth({ provider: 'google', options: { redirectTo: setup.redirect_url } });
    if (result.error) { setError(message(result.error)); setSaving(false); }
  };
  const changeMethod = (next: typeof method) => { setMethod(next); setCodeSent(false); setCode(''); setPassword(''); setError(''); setNotice(''); setConfirmationSent(false); };
  const changeMode = (next: typeof mode) => { setMode(next); setError(''); setNotice(''); setPassword(''); setConfirmationSent(false); };
  return <main className="account-page account-entry">
    <header className="account-header"><a className="account-brand" href="/">GTM Shortlist</a><a href="https://github.com/adkbbx/GTM_Shortlist" target="_blank" rel="noreferrer">Open-source project</a></header>
    <div className="account-layout"><aside className="account-context" aria-label="About GTM Shortlist">
      <h2>A shortlist you can <br />check for yourself.</h2>
      <p>Find potential customer companies and see the sources behind each fit assessment.</p>
      <ol><li><strong>Start with your company</strong><span>Confirm your offer and the customers you want to reach.</span></li><li><strong>Research the evidence</strong><span>Inspect source passages, unknowns and labelled hypotheses.</span></li><li><strong>Keep the useful companies</strong><span>Review your shortlist and export it to Excel.</span></li></ol>
    </aside><section className="sheet account-sheet" aria-labelledby="account-heading">
    <h1 id="account-heading">{confirmationSent ? 'Check your inbox' : title}</h1>
    <p className="intro">{confirmationSent ? 'Verify your email to finish creating your research workspace.' : usingCode ? codeSent ? `Enter the 6-digit code we emailed to ${email}.` : 'We will email you a 6-digit code. No password needed.' : mode === 'signup' ? 'Create a workspace for your company research. We will email you a confirmation link.' : mode === 'reset' ? 'Enter your account email and we will send a password reset link.' : recovery ? 'Set a new password to reopen your workspace.' : 'Welcome back. Open your saved company research.'}</p>
    {keptCompany && keptDraft && !recovery && !confirmationSent && mode !== 'reset' && <p className="notice kept-company" role="status">Your draft for <strong>{keptCompany}</strong> is saved in this browser. It opens as soon as you {mode === 'signup' && !usingCode ? 'confirm your email and sign in' : 'sign in'}; company discovery waits until you confirm the target.</p>}
    {keptCompany && !keptDraft && !recovery && !confirmationSent && mode !== 'reset' && <p className="notice kept-company" role="status">Research for <strong>{keptCompany}</strong> starts as soon as you {mode === 'signup' && !usingCode ? 'confirm your email and sign in' : 'sign in'}. Company discovery waits until you confirm the target.</p>}
    {expired && <p className="notice" role="status">Your session needs verification. Sign in again to reopen your saved research.</p>}
    {externalError && <p className="notice" role="alert">{externalError}</p>}
    {error && <p className="notice" role="alert">{error}</p>}{notice && <p className="notice" role="status">{notice}</p>}
    {setup.google && !recovery && mode !== 'reset' && !confirmationSent && !codeSent && <div className="account-google"><button type="button" className="secondary" disabled={saving} onClick={() => { void continueWithGoogle(); }}><svg width="18" height="18" viewBox="0 0 24 24" aria-hidden="true"><path fill="#4285F4" d="M23.5 12.3c0-.8-.1-1.6-.2-2.3H12v4.4h6.5a5.6 5.6 0 0 1-2.4 3.6v3h3.9c2.2-2.1 3.5-5.1 3.5-8.7z" /><path fill="#34A853" d="M12 24c3.2 0 6-1.1 8-2.9l-3.9-3a7.2 7.2 0 0 1-10.8-3.8h-4v3.1A12 12 0 0 0 12 24z" /><path fill="#FBBC05" d="M5.3 14.3a7.2 7.2 0 0 1 0-4.6V6.6h-4a12 12 0 0 0 0 10.8l4-3.1z" /><path fill="#EA4335" d="M12 4.8c1.8 0 3.3.6 4.6 1.8l3.4-3.4A12 12 0 0 0 1.3 6.6l4 3.1A7.2 7.2 0 0 1 12 4.8z" /></svg>Continue with Google</button><p className="account-divider"><span>or</span></p></div>}
    {usingCode && !codeSent && <form onSubmit={sendCode}>
      <label htmlFor="account-email">Email</label><input id="account-email" type="email" autoComplete="email" required maxLength={254} value={email} onChange={event => setEmail(event.target.value)} />
      <button type="submit" disabled={saving}>{saving ? 'Sending code…' : 'Email me a sign-in code'}</button>
    </form>}
    {usingCode && codeSent && <form onSubmit={verifyCode}>
      <label htmlFor="account-code">6-digit code</label><input id="account-code" inputMode="numeric" autoComplete="one-time-code" required pattern="[0-9]{6}" minLength={6} value={code} onChange={event => setCode(event.target.value.replace(/\D/g, '').slice(0, 6))} autoFocus />
      <button type="submit" disabled={saving}>{saving ? 'Checking code…' : 'Sign in'}</button>
      <div className="account-actions"><button type="button" className="text-button" disabled={saving} onClick={() => { void sendCode(); }}>Resend code</button><button type="button" className="text-button" disabled={saving} onClick={() => { setCodeSent(false); setCode(''); setNotice(''); setError(''); }}>Use a different email</button></div>
    </form>}
    {!confirmationSent && !usingCode && <form onSubmit={submit}>
      {!recovery && <><label htmlFor="account-email">Email</label><input id="account-email" type="email" autoComplete="email" required maxLength={254} value={email} onChange={event => setEmail(event.target.value)} /></>}
      {(recovery || mode !== 'reset') && <><label htmlFor="account-password">{recovery ? 'New password' : 'Password'}</label><input id="account-password" type="password" autoComplete={recovery || mode === 'signup' ? 'new-password' : 'current-password'} required minLength={recovery || mode === 'signup' ? 12 : 1} maxLength={256} value={password} onChange={event => setPassword(event.target.value)} />{(recovery || mode === 'signup') && <p className="hint">Use at least 12 characters.</p>}</>}
      <button type="submit" disabled={saving}>{saving ? 'Please wait…' : recovery ? 'Save new password' : mode === 'signup' ? 'Create account' : mode === 'reset' ? 'Send reset link' : 'Sign in'}</button>
    </form>}
    {confirmationSent && <div className="account-confirmation"><p>Use the newest confirmation email for <strong>{email}</strong>. Open it in this browser to finish signing up.</p><button type="button" className="text-button" disabled={saving} onClick={() => { void resend(); }}>Resend confirmation email</button><button type="button" className="text-button" disabled={saving} onClick={() => { setConfirmationSent(false); setNotice(''); setError(''); }}>Use a different email</button></div>}
    {usingCode && !codeSent && <div className="account-actions"><button type="button" className="text-button" disabled={saving} onClick={() => changeMethod('password')}>Use a password instead</button></div>}
    {!recovery && !usingCode && <div className="account-actions"><button type="button" className="text-button" disabled={saving} onClick={() => changeMode(mode === 'signin' ? 'signup' : 'signin')}>{mode === 'signin' ? 'Create an account' : 'Back to sign in'}</button>{mode === 'signin' && <button type="button" className="text-button" disabled={saving} onClick={() => changeMode('reset')}>Forgot password?</button>}{setup.email_code && mode !== 'reset' && <button type="button" className="text-button" disabled={saving} onClick={() => changeMethod('code')}>Email me a code instead</button>}</div>}
    {!recovery && !confirmationSent && mode !== 'reset' && <p className="account-demo">{mode === 'signup' ? 'Not ready to sign up?' : 'No account yet?'} <a href="?demo=1" onClick={tryDemo}>Try the demo</a><span>Sample companies, no account, no research credits.</span></p>}
  </section></div><footer className="account-footer">Company fit is a research assessment. Buying intent still needs a conversation.</footer></main>;
}

export function AuthGate({ workspace }: { workspace: (identity: string, account: ReactNode) => ReactNode }) {
  const [state, setState] = useState<State>({ kind: 'loading' });
  const [signoutError, setSignoutError] = useState('');
  const [view, setView] = useState<AuthView>(authView);
  const [drafting, setDrafting] = useState(draftView);
  useEffect(() => {
    const sync = () => { setView(authView()); setDrafting(draftView()); };
    window.addEventListener('popstate', sync);
    return () => window.removeEventListener('popstate', sync);
  }, []);
  const signedIn = state.kind === 'hosted' && Boolean(state.session);
  useEffect(() => {
    // Once signed in, the account and draft view parameters have done their job.
    if (!signedIn || (!view && !drafting)) return;
    const params = new URLSearchParams(window.location.search); params.delete('auth'); params.delete('draft');
    window.history.replaceState(null, '', params.size ? `?${params}` : window.location.pathname); setView(null); setDrafting(false);
  }, [signedIn, view, drafting]);
  const openAccount = (next: 'signin' | 'signup') => { window.history.pushState(null, '', `?auth=${next}`); setView(next); window.scrollTo(0, 0); };
  const openDraft = () => { window.history.pushState(null, '', '?draft=1'); setDrafting(true); window.scrollTo(0, 0); };
  const closeDraft = () => { window.history.replaceState(null, '', window.location.pathname); setDrafting(false); };
  useEffect(() => {
    let cancelled = false;
    let unsubscribe: (() => void) | undefined;
    let client: SupabaseClient | undefined;
    api.authSetup().then(async setup => {
      if (cancelled) return;
      if (setup.mode === 'local') { setState({ kind: 'local' }); return; }
      const { createClient } = await import('@supabase/supabase-js');
      if (cancelled) return;
      client = createClient(setup.supabase_url, setup.publishable_key, { auth: { flowType: 'pkce' } });
      const authClient = client;
      setSessionAccess(async () => {
        const result = await authClient.auth.getSession();
        if (result.error) throw result.error;
        return result.data.session?.access_token ?? null;
      }, token => setState(old => old.kind === 'hosted' && old.session?.access_token === token ? { ...old, expired: true } : old));
      const { data } = authClient.auth.onAuthStateChange((event, session) => {
        if (cancelled) return;
        if (event === 'SIGNED_IN') setSignoutError('');
        // A returning user who signs out (or whose session ends) goes back to sign-in, not the public landing page.
        if (event === 'SIGNED_OUT') { window.history.replaceState(null, '', '?auth=signin'); setView('signin'); }
        // Synchronous callback: no auth SDK requests while its session lock is held.
        setState(old => ({ kind: 'hosted', setup, client: authClient, session,
          recovery: event === 'PASSWORD_RECOVERY' || (old.kind === 'hosted' && old.recovery),
          expired: old.kind === 'hosted' && old.expired && old.session?.access_token === session?.access_token }));
      });
      unsubscribe = () => data.subscription.unsubscribe();
      authClient.auth.getSession().then(result => {
        if (cancelled) return;
        if (result.error) throw result.error;
        setState(old => old.kind === 'hosted' ? { ...old, session: result.data.session } :
          { kind: 'hosted', setup, client: authClient, session: result.data.session, recovery: false, expired: false });
      }).catch(reason => { if (!cancelled) setState({ kind: 'error', message: message(reason) }); });
    }).catch(reason => { if (!cancelled) setState({ kind: 'error', message: message(reason) }); });
    return () => { cancelled = true; unsubscribe?.(); client?.auth.stopAutoRefresh(); setSessionAccess(null, null); };
  }, []);

  if (state.kind === 'loading') return <main className="account-page"><p role="status">Opening your workspace…</p></main>;
  if (state.kind === 'error') return <main className="account-page"><section className="sheet account-sheet"><h1>Account access unavailable</h1><p className="notice" role="alert">{state.message}</p><button onClick={() => window.location.reload()}>Retry account access</button></section></main>;
  if (state.kind === 'local') return workspace('local', null);
  const signout = async () => {
    setSignoutError('');
    const result = await state.client.auth.signOut({ scope: 'local' });
    if (result.error) setSignoutError(result.error.message);
  };
  const drafts = state.setup.draft_site_key;
  const kept = peekKeptCompany();
  if (!state.session && !state.recovery && !state.expired && !view && drafting && drafts && isWebsite(kept)) return <DraftPreview key={kept} website={kept} siteKey={drafts} onSave={() => openAccount('signup')} onBack={closeDraft} />;
  if (!state.session && !state.recovery && !state.expired && !view && !returningLink()) return <Suspense fallback={<main className="account-page" />}><PublicLanding hosted directoryId={configuredDirectoryId()} onSignIn={() => openAccount('signin')} onStart={company => { keepCompany(company); if (drafts && isWebsite(company)) openDraft(); else openAccount('signup'); }} /></Suspense>;
  if (!state.session || state.recovery || state.expired) return <AccountForm key={view ?? 'signin'} initialMode={view === 'signup' ? 'signup' : 'signin'} keptCompany={kept} keptDraft={peekKeptDraft()?.website === kept} client={state.client} setup={state.setup} recovery={state.recovery} expired={state.expired} externalError={signoutError} onRecovered={() => setState(old => old.kind === 'hosted' ? { ...old, recovery: false } : old)} />;
  if (!state.session.user.email_confirmed_at || state.session.user.is_anonymous) return <main className="account-page"><section className="sheet account-sheet"><h1>Confirm your email</h1><p>Open the confirmation link in your inbox before starting research.</p>{signoutError && <p className="notice" role="alert">{signoutError}</p>}<button className="secondary" onClick={() => { void signout(); }}>Back to sign in</button></section></main>;
  return workspace(state.session.user.id, <div className="account-nav"><span>{state.session.user.email}</span><button className="text-button" onClick={() => { void signout(); }}>Sign out</button>{signoutError && <p role="alert">{signoutError}</p>}</div>);
}
