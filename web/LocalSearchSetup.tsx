import { useEffect, useRef, useState } from 'react';
import type { FormEvent } from 'react';
import { api } from './api';
import type { Health } from './api';
import './LocalSettings.css';
import { ModelSetup } from './ModelSetup';

type SaveState = { kind: 'idle' } | { kind: 'saving' } | { kind: 'saved' } | { kind: 'error'; message: string };

export function LocalSearchSetup({ health, onSaved, readOnly = false }: {
  health: Health; onSaved: (health: Health) => void; readOnly?: boolean;
}) {
  const [open, setOpen] = useState(false);
  const [statusError, setStatusError] = useState('');
  const [editing, setEditing] = useState(false);
  const [editingModel, setEditingModel] = useState(false);
  const [modelSaved, setModelSaved] = useState(false);
  const [key, setKey] = useState('');
  const [state, setState] = useState<SaveState>({ kind: 'idle' });
  const editTrigger = useRef<HTMLButtonElement>(null);
  const modelTrigger = useRef<HTMLButtonElement>(null);
  const closeModel = () => { setEditingModel(false); requestAnimationFrame(() => modelTrigger.current?.focus()); };
  useEffect(() => {
    if (!open || readOnly) return;
    let disposed = false;
    let timer: ReturnType<typeof setTimeout>;
    const refresh = async () => {
      try { const updated = await api.health(); if (!disposed) { onSaved(updated); setStatusError(''); } }
      catch { if (!disposed) setStatusError('Settings could not refresh. Showing the last known status; check that the local app is running.'); }
      if (!disposed) timer = setTimeout(refresh, 3000);
    };
    void refresh();
    return () => { disposed = true; clearTimeout(timer); };
  }, [open, readOnly, onSaved]);
  const searchStatus = health.local_search_error ? 'Settings unavailable' : health.search_ready ? 'Configured' : 'Not configured';
  const modelStatus = health.local_search_error ? 'Settings unavailable' : health.gemma_ready ? 'Configured' : 'Not configured';
  const closeEditor = () => { setEditing(false); setKey(''); setState({ kind: 'idle' }); editTrigger.current?.focus(); };
  const save = async (event: FormEvent) => {
    event.preventDefault(); setState({ kind: 'saving' });
    try {
      const updated = await api.configureTavily(key.trim());
      setKey(''); setEditing(false); setState({ kind: 'saved' }); onSaved(updated); editTrigger.current?.focus();
    } catch (error) { setState({ kind: 'error', message: error instanceof Error ? error.message : 'Search setup could not be saved. Please try again.' }); }
  };
  return <>
    <button className="local-settings-trigger secondary" type="button" popoverTarget="local-settings" aria-label="Settings" title="Settings"><svg width="20" height="20" viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M4 6h16M4 12h16M4 18h16" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" /></svg></button>
    <section id="local-settings" className="local-settings" popover="auto" role="dialog" aria-labelledby="local-settings-heading"
      onToggle={event => { setOpen(event.newState === 'open'); if (event.newState === 'closed') { setEditing(false); setEditingModel(false); setModelSaved(false); setKey(''); setState({ kind: 'idle' }); } }}>
      <header className="local-settings-heading"><h2 id="local-settings-heading">Settings</h2><button type="button" popoverTarget="local-settings" popoverTargetAction="hide" aria-label="Close settings">×</button></header>
      <p className="hint">Local workspace · configuration on this computer</p>
      {!editingModel && <><dl className="provider-status">
        <div><dt>Company search</dt><dd>{readOnly ? searchStatus : <button className="text-button" ref={editTrigger} type="button" aria-label={`Company search: ${searchStatus}`} aria-expanded={editing} aria-controls="local-search-form" onClick={() => { setEditingModel(false); setModelSaved(false); if (editing) closeEditor(); else setEditing(true); }}>{searchStatus}</button>}</dd></div>
        <div><dt>Research model</dt><dd>{readOnly ? modelStatus : <button className="text-button" ref={modelTrigger} type="button" aria-label={`Research model: ${modelStatus}`} aria-expanded={editingModel} aria-controls="local-model-form" onClick={() => { setEditing(false); setKey(''); setState({ kind: 'idle' }); setModelSaved(false); setEditingModel(!editingModel); }}>{modelStatus}</button>}</dd></div>
        <div><dt>Research service</dt><dd>{health.worker_online ? 'Running' : 'Stopped'}</dd></div>
      </dl>
      <p className="hint">Configured means settings are saved. Research quality has not been tested.</p>
      {statusError && <p role="alert">{statusError}</p>}
      {!health.worker_online && <p className="hint">Background research starts automatically when you start or resume research. Saving settings does not start research.</p>}

      {health.local_search_error && <p role="alert">Saved provider settings could not be read. Check this computer’s provider configuration.</p>}</>}
      {readOnly ? <p className="notice">Provider changes are disabled in this design preview. Open the local research workspace to configure providers.</p> : <>
        {editing && <form id="local-search-form" onSubmit={save}>
          <h3>Company search</h3>
          <p>Tavily finds company websites for this local workspace. Use your own API key from <a href="https://app.tavily.com/" target="_blank" rel="noopener noreferrer">Tavily</a>. Saving it makes no search request.</p>
          <label htmlFor="tavily-key">Tavily API key</label>
          <input id="tavily-key" type="password" autoFocus autoComplete="off" autoCapitalize="none" autoCorrect="off" spellCheck={false} required minLength={13} maxLength={256} placeholder="tvly-…" value={key} disabled={state.kind === 'saving'} onChange={event => { setKey(event.target.value); setState({ kind: 'idle' }); }} />
          <p className="hint">Keys stay on this computer and are never shown or exported. A saved key applies to your next confirmed run.</p>
          <div className="review-actions"><button disabled={state.kind === 'saving'} type="submit">{state.kind === 'saving' ? 'Saving key…' : 'Save search key'}</button><button className="secondary" type="button" disabled={state.kind === 'saving'} onClick={closeEditor}>Cancel key change</button></div>
        </form>}
        {state.kind === 'saved' && <p role="status">Search key saved. Company search is configured.</p>}
        {state.kind === 'error' && <p className="notice" role="alert">{state.message}</p>}
        {editingModel && <ModelSetup onSaved={updated => { onSaved(updated); closeModel(); setModelSaved(true); }} onCancel={closeModel} />}
        {modelSaved && <p role="status">Research model settings saved. No research was started.</p>}
      </>}
    </section>
  </>;
}
