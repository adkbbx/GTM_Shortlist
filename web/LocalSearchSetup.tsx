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
  const [editingModel, setEditingModel] = useState(false);
  const [modelSaved, setModelSaved] = useState(false);
  const [key, setKey] = useState('');
  const [state, setState] = useState<SaveState>({ kind: 'idle' });
  const editTrigger = useRef<HTMLButtonElement>(null);
  const modelTrigger = useRef<HTMLButtonElement>(null);
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
      onToggle={event => { if (event.newState === 'closed') { setEditing(false); setEditingModel(false); setModelSaved(false); setKey(''); setState({ kind: 'idle' }); } }}>
      <header className="local-settings-heading"><h2 id="local-settings-heading">Settings</h2><button type="button" popoverTarget="local-settings" popoverTargetAction="hide" aria-label="Close settings">×</button></header>
      <p className="hint">Local workspace · configuration on this computer</p>
      <dl className="provider-status">
        <div><dt>Company search</dt><dd>{readOnly ? searchStatus : <button className="text-button" ref={editTrigger} type="button" aria-label={`Company search: ${searchStatus}`} aria-expanded={editing} aria-controls="local-search-form" onClick={() => { setEditingModel(false); setModelSaved(false); if (editing) closeEditor(); else setEditing(true); }}>{searchStatus}</button>}</dd></div>
        <div><dt>Research model</dt><dd>{readOnly ? modelStatus : <button className="text-button" ref={modelTrigger} type="button" aria-label={`Research model: ${modelStatus}`} aria-expanded={editingModel} aria-controls="local-model-form" onClick={() => { setEditing(false); setKey(''); setState({ kind: 'idle' }); setModelSaved(false); setEditingModel(!editingModel); }}>{modelStatus}</button>}</dd></div>
        <div><dt>Research worker</dt><dd>{health.worker_online ? 'Online' : 'Offline'}</dd></div>
      </dl>
      <p className="hint">Configured means credentials or an endpoint are present. No provider connection has been tested here.</p>
      {!health.worker_online && <div className="worker-help"><p>No research worker is connected. It runs research in the background and saves progress while you browse.</p><p>{!health.search_ready || !health.gemma_ready ? 'Configure both providers, then start background research.' : 'Both providers are configured. Start background research to continue.'}</p><details><summary>How to start local research</summary><ol><li>Free port 8019 first. If you started the app in PowerShell, press Ctrl+C in that window. If Codex started your preview, ask Codex to switch it to research mode instead.</li><li>Open PowerShell in this GTM Shortlist checkout, where the <code>.venv</code> and <code>src</code> folders are.</li><li>Run these two commands, one line at a time:<p className="command-label">PowerShell</p><pre aria-label="PowerShell startup commands"><code>{'$env:PYTHONPATH = "$PWD/src"\n.venv/Scripts/python.exe -m shortlist.cli serve --port 8019'}</code></pre></li><li>Wait for the server to start, then reload the workspace at <a href="http://127.0.0.1:8019/">127.0.0.1:8019</a>.</li></ol><p>This starts the API and worker together. A worker can resume queued research and contact providers. The design preview on port 8018 stays separate.</p></details></div>}
      {health.local_search_error && <p role="alert">Saved provider settings could not be read. Check this computer’s provider configuration.</p>}
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
        {editingModel && <ModelSetup onSaved={updated => { onSaved(updated); setEditingModel(false); setModelSaved(true); modelTrigger.current?.focus(); }} onCancel={() => { setEditingModel(false); modelTrigger.current?.focus(); }} />}
        {modelSaved && <p role="status">Research model saved. No connection test or research request was made.</p>}
      </>}
    </section>
  </>;
}

function ModelSetup({ onSaved, onCancel }: { onSaved: (health: Health) => void; onCancel: () => void }) {
  const [endpoint, setEndpoint] = useState('');
  const [model, setModel] = useState('');
  const [key, setKey] = useState('');
  const [state, setState] = useState<SaveState>({ kind: 'idle' });
  const save = async (event: FormEvent) => {
    event.preventDefault(); setState({ kind: 'saving' });
    try { onSaved(await api.configureModel({ base_url: endpoint.trim(), model: model.trim(), key: key.trim() })); }
    catch (error) { setState({ kind: 'error', message: error instanceof Error ? error.message : 'Research model could not be saved. Try again.' }); }
  };
  return <form id="local-model-form" onSubmit={save}>
    <h3>Research model</h3>
    <p>Use a trusted OpenAI-compatible Gemma endpoint. Saved settings apply to the next run. Saving does not contact the model.</p>
    <label htmlFor="model-endpoint">Endpoint URL</label>
    <input id="model-endpoint" type="url" autoFocus required maxLength={1024} placeholder="http://localhost:8000/v1" value={endpoint} disabled={state.kind === 'saving'} onChange={event => setEndpoint(event.target.value)} />
    <label htmlFor="model-name">Model name</label>
    <input id="model-name" required maxLength={200} placeholder="Exact model ID from your server" value={model} disabled={state.kind === 'saving'} onChange={event => setModel(event.target.value)} />
    <label htmlFor="model-key">Model API key (optional)</label>
    <input id="model-key" type="password" autoComplete="off" autoCapitalize="none" spellCheck={false} maxLength={512} value={key} disabled={state.kind === 'saving'} onChange={event => setKey(event.target.value)} />
    <p className="hint">Enter all replacement settings. Existing values and keys are never loaded into this form. Leave the key blank only for a server that needs no authentication.</p>
    <div className="review-actions"><button disabled={state.kind === 'saving'} type="submit">{state.kind === 'saving' ? 'Saving model…' : 'Save research model'}</button><button className="secondary" type="button" disabled={state.kind === 'saving'} onClick={onCancel}>Cancel model change</button></div>
    {state.kind === 'error' && <p role="alert">{state.message}</p>}
  </form>;
}
