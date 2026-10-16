import { useRef, useState } from 'react';
import type { FormEvent } from 'react';
import { api } from './api';
import type { Health } from './api';
import './LocalSettings.css';

type SaveState = { kind: 'idle' } | { kind: 'saving' } | { kind: 'saved' } | { kind: 'error'; message: string };

export function LocalSearchSetup({ health, onSaved, readOnly = false }: {
  health: Health; onSaved: (health: Health) => void; readOnly?: boolean;
}) {
  const [editing, setEditing] = useState(false);
  const [key, setKey] = useState('');
  const [state, setState] = useState<SaveState>({ kind: 'idle' });
  const editTrigger = useRef<HTMLButtonElement>(null);
  const closeEditor = () => { setEditing(false); setKey(''); setState({ kind: 'idle' }); editTrigger.current?.focus(); };
  const save = async (event: FormEvent) => {
    event.preventDefault(); setState({ kind: 'saving' });
    try {
      const updated = await api.configureTavily(key.trim());
      setKey(''); setEditing(false); setState({ kind: 'saved' }); onSaved(updated); editTrigger.current?.focus();
    } catch (error) { setState({ kind: 'error', message: error instanceof Error ? error.message : 'Search setup could not be saved. Please try again.' }); }
  };
  return <>
    <button className="local-settings-trigger secondary" type="button" popoverTarget="local-settings" aria-label="Settings">Settings</button>
    <section id="local-settings" className="local-settings" popover="auto" role="dialog" aria-labelledby="local-settings-heading"
      onToggle={event => { if (event.newState === 'closed') { setEditing(false); setKey(''); setState({ kind: 'idle' }); } }}>
      <header className="local-settings-heading"><h2 id="local-settings-heading">Settings</h2><button type="button" popoverTarget="local-settings" popoverTargetAction="hide" aria-label="Close settings">×</button></header>
      <p className="hint">Local workspace · configuration on this computer</p>
      <dl className="provider-status">
        <div><dt>Company search</dt><dd>{health.local_search_error ? 'Settings unavailable' : health.search_ready ? 'Configured' : 'Not configured'}</dd></div>
        <div><dt>Research model</dt><dd>{health.gemma_ready ? 'Configured' : 'Not configured'}</dd></div>
        <div><dt>Research worker</dt><dd>{health.worker_online ? 'Online' : 'Offline'}</dd></div>
      </dl>
      <p className="hint">Configured means credentials or an endpoint are present. No provider connection has been tested here.</p>
      {health.local_search_error && <p role="alert">Saved search settings could not be read. Save a replacement key or check this computer’s provider configuration.</p>}
      {readOnly ? <p className="notice">Provider changes are disabled in this design preview. Open the local research workspace to configure providers.</p> : <>
        <button className="text-button" ref={editTrigger} type="button" aria-expanded={editing} aria-controls="local-search-form" onClick={() => editing ? closeEditor() : setEditing(true)}>{health.search_ready ? 'Manage search key' : 'Set up company search'}</button>
        {editing && <form id="local-search-form" onSubmit={save}>
          <h3>Connect company search</h3>
          <p>Tavily finds company websites for this local workspace. Use your own API key from <a href="https://app.tavily.com/" target="_blank" rel="noopener noreferrer">Tavily</a>. Saving it makes no search request.</p>
          <label htmlFor="tavily-key">Tavily API key</label>
          <input id="tavily-key" type="password" autoFocus autoComplete="off" autoCapitalize="none" autoCorrect="off" spellCheck={false} required minLength={13} maxLength={256} placeholder="tvly-…" value={key} disabled={state.kind === 'saving'} onChange={event => { setKey(event.target.value); setState({ kind: 'idle' }); }} />
          <p className="hint">Keys stay on this computer and are never shown or exported. A saved key applies to your next confirmed run.</p>
          <div className="review-actions"><button disabled={state.kind === 'saving'} type="submit">{state.kind === 'saving' ? 'Saving key…' : 'Save search key'}</button><button className="secondary" type="button" disabled={state.kind === 'saving'} onClick={closeEditor}>Cancel key change</button></div>
        </form>}
        {state.kind === 'saved' && <p role="status">Search key saved. Company search is configured.</p>}
        {state.kind === 'error' && <p className="notice" role="alert">{state.message}</p>}
        {!health.gemma_ready && <p className="hint">Configure the model endpoint in this computer’s server settings before running research.</p>}
      </>}
    </section>
  </>;
}
