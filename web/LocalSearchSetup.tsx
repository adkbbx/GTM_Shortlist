import { useEffect, useRef, useState } from 'react';
import type { FormEvent } from 'react';
import { api } from './api';
import type { Health } from './api';

type SaveState = { kind: 'idle' } | { kind: 'saving' } | { kind: 'saved' } | { kind: 'error'; message: string };

export function LocalSearchSetup({ ready, onSaved, onContinue, compact = false }: { ready: boolean; onSaved: (health: Health) => void; onContinue?: () => void; compact?: boolean }) {
  const [open, setOpen] = useState(false);
  const [key, setKey] = useState('');
  const [state, setState] = useState<SaveState>({ kind: 'idle' });
  const trigger = useRef<HTMLButtonElement>(null);
  const status = useRef<HTMLParagraphElement>(null);
  useEffect(() => { if (state.kind === 'saved') status.current?.focus(); }, [state.kind]);
  const close = () => { setOpen(false); setKey(''); setState({ kind: 'idle' }); window.setTimeout(() => trigger.current?.focus(), 0); };
  const save = async (event: FormEvent) => {
    event.preventDefault(); setState({ kind: 'saving' });
    try {
      const health = await api.configureTavily(key.trim());
      setKey(''); setOpen(false); setState({ kind: 'saved' }); onSaved(health);
    } catch (error) { setState({ kind: 'error', message: error instanceof Error ? error.message : 'Search setup could not be saved. Please try again.' }); }
  };
  return <section className={`local-search-setup${compact && ready && !open ? ' is-compact' : ''}`} aria-label="Local search setup">
    {!open && (ready || state.kind === 'saved') && <div className="search-setup-summary">
      <p ref={status} tabIndex={-1} role="status">{state.kind === 'saved' ? 'Tavily key saved.' : 'Search key saved.'}<span className="hint">{onContinue ? 'Enter your company website to continue.' : 'Your next confirmed run will use the saved key.'}</span></p>
      {onContinue && <button className="secondary" onClick={onContinue}>Continue to your website</button>}
    </div>}
    <button className="text-button" ref={trigger} aria-expanded={open} aria-controls="local-search-form" disabled={state.kind === 'saving'} onClick={() => open ? close() : setOpen(true)}>{ready ? 'Update search key' : 'Connect Tavily'}</button>
    {open && <div id="local-search-form">
      <h2>Connect your search provider</h2>
      <p>Paste your Tavily API key here. It stays in this computer’s research workspace and is never included in research exports.</p>
      <form onSubmit={save}>
        <label htmlFor="tavily-key">Tavily API key</label>
        <input id="tavily-key" type="password" autoFocus autoComplete="off" autoCapitalize="none" autoCorrect="off" spellCheck={false} required minLength={13} maxLength={256} placeholder="tvly-…" value={key} disabled={state.kind === 'saving'} onChange={event => { setKey(event.target.value); setState({ kind: 'idle' }); }} />
        <p className="hint">Saving makes no search request. Your next confirmed run uses this key; requests already underway keep their current settings.</p>
        <div className="review-actions"><button disabled={state.kind === 'saving'} type="submit">{state.kind === 'saving' ? 'Saving key…' : 'Save search key'}</button><button className="secondary" type="button" disabled={state.kind === 'saving'} onClick={close}>Close setup</button></div>
      </form>
      {state.kind === 'error' && <p className="notice" role="alert">{state.message}</p>}
    </div>}
  </section>;
}
