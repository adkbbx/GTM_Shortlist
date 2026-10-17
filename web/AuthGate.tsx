import { lazy, Suspense, useEffect, useState } from 'react';
import type { FormEvent, ReactNode } from 'react';
import type { Session, SupabaseClient } from '@supabase/supabase-js';
import { api, setSessionAccess } from './api';
import type { AuthSetup } from './api';
import { keepCompany, peekKeptCompany } from './landing/kept-company';

// Hosted visitors without a session see the public landing page; it loads separately from the workspace.
const PublicLanding = lazy(() => import('./landing/PublicLanding').then(module => ({ default: module.PublicLanding })));
type AuthView = 'signin' | 'signup' | null;
const authView = (): AuthView => { const view = new URLSearchParams(window.location.search).get('auth'); return view === 'signin' || view === 'signup' ? view : null; };

type HostedSetup = Extract<AuthSetup, { mode: 'hosted' }>;
type State = { kind: 'loading' } | { kind: 'local' } | { kind: 'error'; message: string } |
  { kind: 'hosted'; setup: HostedSetup; client: SupabaseClient; session: Session | null; recovery: boolean; expired: boolean };
const message = (error: unknown) => error instanceof Error ? error.message : 'Account access is unavailable. Please try again.';

function AccountForm({ client, setup, recovery, expired, externalError, onRecovered, initialMode = 'signin', keptCompany = '' }: {
  client: SupabaseClient; setup: HostedSetup; recovery: boolean; expired: boolean; externalError: string; onRecovered: () => void;
  initialMode?: 'signin' | 'signup'; keptCompany?: string;
}) {
  const [mode, setMode] = useState<'signin' | 'signup' | 'reset'>(initialMode);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [confirmationSent, setConfirmationSent] = useState(false);
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
  const changeMode = (next: typeof mode) => { setMode(next); setError(''); setNotice(''); setPassword(''); setConfirmationSent(false); };
  return <main className="account-page account-entry">
    <header className="account-header"><a className="account-brand" href="/">GTM Shortlist</a><a href="https://github.com/adkbbx/GTM_Shortlist" target="_blank" rel="noreferrer">Open-source project</a></header>
    <div className="account-layout"><aside className="account-context" aria-label="About GTM Shortlist">
      <h2>A shortlist you can <br />check for yourself.</h2>
      <p>Find potential customer companies and see the sources behind each fit assessment.</p>
      <ol><li><strong>Start with your company</strong><span>Confirm your offer and the customers you want to reach.</span></li><li><strong>Research the evidence</strong><span>Inspect source passages, unknowns and labelled hypotheses.</span></li><li><strong>Keep the useful companies</strong><span>Review your shortlist and export it to Excel.</span></li></ol>
    </aside><section className="sheet account-sheet" aria-labelledby="account-heading">
    <h1 id="account-heading">{confirmationSent ? 'Check your inbox' : title}</h1>
    <p className="intro">{confirmationSent ? 'Verify your email to finish creating your research workspace.' : mode === 'signup' ? 'Create a workspace for your company research. We will email you a confirmation link.' : mode === 'reset' ? 'Enter your account email and we will send a password reset link.' : recovery ? 'Set a new password to reopen your workspace.' : 'Welcome back. Open your saved company research.'}</p>
    {keptCompany && !recovery && !confirmationSent && mode !== 'reset' && <p className="notice kept-company" role="status">We kept <strong>{keptCompany}</strong>. {mode === 'signup' ? 'Create your account' : 'Sign in'}, then start research from your workspace. Nothing runs until you confirm the target.</p>}
    {expired && <p className="notice" role="status">Your session needs verification. Sign in again to reopen your saved research.</p>}
    {externalError && <p className="notice" role="alert">{externalError}</p>}
    {error && <p className="notice" role="alert">{error}</p>}{notice && <p className="notice" role="status">{notice}</p>}
    {!confirmationSent && <form onSubmit={submit}>
      {!recovery && <><label htmlFor="account-email">Email</label><input id="account-email" type="email" autoComplete="email" required maxLength={254} value={email} onChange={event => setEmail(event.target.value)} /></>}
      {(recovery || mode !== 'reset') && <><label htmlFor="account-password">{recovery ? 'New password' : 'Password'}</label><input id="account-password" type="password" autoComplete={recovery || mode === 'signup' ? 'new-password' : 'current-password'} required minLength={recovery || mode === 'signup' ? 12 : 1} maxLength={256} value={password} onChange={event => setPassword(event.target.value)} />{(recovery || mode === 'signup') && <p className="hint">Use at least 12 characters.</p>}</>}
      <button type="submit" disabled={saving}>{saving ? 'Please wait…' : recovery ? 'Save new password' : mode === 'signup' ? 'Create account' : mode === 'reset' ? 'Send reset link' : 'Sign in'}</button>
    </form>}
    {confirmationSent && <div className="account-confirmation"><p>Use the newest confirmation email for <strong>{email}</strong>. Open it in this browser to finish signing up.</p><button type="button" className="text-button" disabled={saving} onClick={() => { void resend(); }}>Resend confirmation email</button><button type="button" className="text-button" disabled={saving} onClick={() => { setConfirmationSent(false); setNotice(''); setError(''); }}>Use a different email</button></div>}
    {!recovery && <div className="account-actions"><button type="button" className="text-button" disabled={saving} onClick={() => changeMode(mode === 'signin' ? 'signup' : 'signin')}>{mode === 'signin' ? 'Create an account' : 'Back to sign in'}</button>{mode === 'signin' && <button type="button" className="text-button" disabled={saving} onClick={() => changeMode('reset')}>Forgot password?</button>}</div>}
  </section></div><footer className="account-footer">Company fit is a research assessment. Buying intent still needs a conversation.</footer></main>;
}

export function AuthGate({ workspace }: { workspace: (identity: string, account: ReactNode) => ReactNode }) {
  const [state, setState] = useState<State>({ kind: 'loading' });
  const [signoutError, setSignoutError] = useState('');
  const [view, setView] = useState<AuthView>(authView);
  useEffect(() => {
    const sync = () => setView(authView());
    window.addEventListener('popstate', sync);
    return () => window.removeEventListener('popstate', sync);
  }, []);
  const signedIn = state.kind === 'hosted' && Boolean(state.session);
  useEffect(() => {
    // Once signed in, the account view parameter has done its job.
    if (!signedIn || !view) return;
    const params = new URLSearchParams(window.location.search); params.delete('auth');
    window.history.replaceState(null, '', params.size ? `?${params}` : window.location.pathname); setView(null);
  }, [signedIn, view]);
  const openAccount = (next: 'signin' | 'signup') => { window.history.pushState(null, '', `?auth=${next}`); setView(next); window.scrollTo(0, 0); };
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
  if (!state.session && !state.recovery && !state.expired && !view) return <Suspense fallback={<main className="account-page" />}><PublicLanding onSignIn={() => openAccount('signin')} onStart={company => { keepCompany(company); openAccount('signup'); }} /></Suspense>;
  if (!state.session || state.recovery || state.expired) return <AccountForm key={view ?? 'signin'} initialMode={view === 'signup' ? 'signup' : 'signin'} keptCompany={peekKeptCompany()} client={state.client} setup={state.setup} recovery={state.recovery} expired={state.expired} externalError={signoutError} onRecovered={() => setState(old => old.kind === 'hosted' ? { ...old, recovery: false } : old)} />;
  if (!state.session.user.email_confirmed_at || state.session.user.is_anonymous) return <main className="account-page"><section className="sheet account-sheet"><h1>Confirm your email</h1><p>Open the confirmation link in your inbox before starting research.</p>{signoutError && <p className="notice" role="alert">{signoutError}</p>}<button className="secondary" onClick={() => { void signout(); }}>Back to sign in</button></section></main>;
  return workspace(state.session.user.id, <div className="account-nav"><span>{state.session.user.email}</span><button className="text-button" onClick={() => { void signout(); }}>Sign out</button>{signoutError && <p role="alert">{signoutError}</p>}</div>);
}
