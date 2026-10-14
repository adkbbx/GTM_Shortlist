import { useEffect, useState } from 'react';
import type { FormEvent, ReactNode } from 'react';
import type { Session, SupabaseClient } from '@supabase/supabase-js';
import { api, setSessionAccess } from './api';
import type { AuthSetup } from './api';

type HostedSetup = Extract<AuthSetup, { mode: 'hosted' }>;
type State = { kind: 'loading' } | { kind: 'local' } | { kind: 'error'; message: string } |
  { kind: 'hosted'; setup: HostedSetup; client: SupabaseClient; session: Session | null; recovery: boolean; expired: boolean };
const message = (error: unknown) => error instanceof Error ? error.message : 'Account access is unavailable. Please try again.';

function AccountForm({ client, setup, recovery, expired, externalError, onRecovered }: {
  client: SupabaseClient; setup: HostedSetup; recovery: boolean; expired: boolean; externalError: string; onRecovered: () => void;
}) {
  const [mode, setMode] = useState<'signin' | 'signup' | 'reset'>('signin');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
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
      } else {
        const result = await client.auth.signInWithPassword({ email, password });
        if (result.error) throw result.error;
        setPassword('');
      }
    } catch (reason) { setError(message(reason)); } finally { setSaving(false); }
  };
  const changeMode = (next: typeof mode) => { setMode(next); setError(''); setNotice(''); setPassword(''); };
  return <main className="account-page"><section className="sheet account-sheet" aria-labelledby="account-heading">
    <a className="account-brand" href="/">eygentic <span>GTM Shortlist</span></a>
    <h1 id="account-heading">{title}</h1>
    <p className="intro">Research company fit. Inspect the evidence. Keep your shortlist in your own workspace.</p>
    {expired && <p className="notice" role="status">Your session needs verification. Sign in again to reopen your saved research.</p>}
    {externalError && <p className="notice" role="alert">{externalError}</p>}
    <form onSubmit={submit}>
      {!recovery && <><label htmlFor="account-email">Email</label><input id="account-email" type="email" autoComplete="email" required maxLength={254} value={email} onChange={event => setEmail(event.target.value)} /></>}
      {(recovery || mode !== 'reset') && <><label htmlFor="account-password">{recovery ? 'New password' : 'Password'}</label><input id="account-password" type="password" autoComplete={recovery || mode === 'signup' ? 'new-password' : 'current-password'} required minLength={recovery || mode === 'signup' ? 12 : 1} maxLength={256} value={password} onChange={event => setPassword(event.target.value)} />{(recovery || mode === 'signup') && <p className="hint">Use at least 12 characters.</p>}</>}
      {error && <p className="notice" role="alert">{error}</p>}{notice && <p className="notice" role="status">{notice}</p>}
      <button type="submit" disabled={saving}>{saving ? 'Please wait…' : recovery ? 'Save new password' : mode === 'signup' ? 'Create account' : mode === 'reset' ? 'Send reset link' : 'Sign in'}</button>
    </form>
    {!recovery && <div className="account-actions"><button type="button" className="text-button" disabled={saving} onClick={() => changeMode(mode === 'signin' ? 'signup' : 'signin')}>{mode === 'signin' ? 'Create an account' : 'Back to sign in'}</button>{mode === 'signin' && <button type="button" className="text-button" disabled={saving} onClick={() => changeMode('reset')}>Forgot password?</button>}</div>}
  </section><p className="account-footer">Research supports judgment. It does not establish buying intent.</p></main>;
}

export function AuthGate({ workspace }: { workspace: (identity: string, account: ReactNode) => ReactNode }) {
  const [state, setState] = useState<State>({ kind: 'loading' });
  const [signoutError, setSignoutError] = useState('');
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
  if (!state.session || state.recovery || state.expired) return <AccountForm client={state.client} setup={state.setup} recovery={state.recovery} expired={state.expired} externalError={signoutError} onRecovered={() => setState(old => old.kind === 'hosted' ? { ...old, recovery: false } : old)} />;
  if (!state.session.user.email_confirmed_at || state.session.user.is_anonymous) return <main className="account-page"><section className="sheet account-sheet"><h1>Confirm your email</h1><p>Open the confirmation link in your inbox before starting research.</p>{signoutError && <p className="notice" role="alert">{signoutError}</p>}<button className="secondary" onClick={() => { void signout(); }}>Back to sign in</button></section></main>;
  return workspace(state.session.user.id, <div className="account-nav"><span>{state.session.user.email}</span><button className="text-button" onClick={() => { void signout(); }}>Sign out</button>{signoutError && <p role="alert">{signoutError}</p>}</div>);
}
