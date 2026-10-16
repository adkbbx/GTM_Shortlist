import { useState } from 'react';
import type { FormEvent } from 'react';
import { api } from './api';
import type { Health } from './api';

const presets = {
  lmstudio: { name: 'LM Studio', local: true, address: 'http://localhost:1234/v1' },
  ollama: { name: 'Ollama', local: true, address: 'http://localhost:11434/v1' },
  'custom-local': { name: 'Another local server', local: true, address: '' },
  openrouter: { name: 'OpenRouter', local: false, address: 'https://openrouter.ai/api/v1' },
  'custom-hosted': { name: 'Another hosted provider', local: false, address: '' },
} satisfies Record<string, { name: string; local: boolean; address: string }>;
type Server = keyof typeof presets;
type Lookup = { kind: 'idle' } | { kind: 'loading' } | { kind: 'ready'; models: string[] } | { kind: 'error'; message: string };
type Save = { kind: 'idle' } | { kind: 'saving' } | { kind: 'error'; message: string };

export function ModelSetup({ onSaved, onCancel }: { onSaved: (health: Health) => void; onCancel: () => void }) {
  const [server, setServer] = useState<Server | null>(null);
  const [address, setAddress] = useState('');
  const [model, setModel] = useState('');
  const [key, setKey] = useState('');
  const [manual, setManual] = useState(false);
  const [lookup, setLookup] = useState<Lookup>({ kind: 'idle' });
  const [saveState, setSaveState] = useState<Save>({ kind: 'idle' });
  const preset = server === null ? null : presets[server];
  const needsKey = server === 'openrouter';
  const busy = lookup.kind === 'loading' || saveState.kind === 'saving';
  const choose = (next: Server) => {
    setServer(next); setAddress(presets[next].address); setKey(''); setModel('');
    setLookup({ kind: 'idle' }); setSaveState({ kind: 'idle' }); setManual(false);
  };
  const invalidate = () => { setLookup({ kind: 'idle' }); setModel(''); setSaveState({ kind: 'idle' }); };
  const findModels = async () => {
    setLookup({ kind: 'loading' }); setModel(''); setSaveState({ kind: 'idle' });
    try { setLookup({ kind: 'ready', models: await api.availableModels({ base_url: address.trim(), key: key.trim() }) }); }
    catch (error) { setLookup({ kind: 'error', message: error instanceof Error ? error.message : 'Models could not be listed. Check the server and try again.' }); }
  };
  const save = async (event: FormEvent) => {
    event.preventDefault();
    if (!model.trim() || !address.trim()) return;
    setSaveState({ kind: 'saving' });
    try { onSaved(await api.configureModel({ base_url: address.trim(), model: model.trim(), key: key.trim() })); }
    catch (error) { setSaveState({ kind: 'error', message: error instanceof Error ? error.message : 'Model settings could not be saved. Try again.' }); }
  };
  const endpointField = <>
    <label htmlFor="model-endpoint">Server address</label>
    <input id="model-endpoint" type="url" required maxLength={1024} value={address} disabled={busy} onChange={event => { setAddress(event.target.value); invalidate(); }} />
    <p className="hint">Use the OpenAI-compatible API base address from your server or provider, ending in /v1. This is not the model’s download page.</p>
  </>;
  const keyField = <>
    <label htmlFor="model-key">{needsKey ? 'Model API key' : 'Model API key (optional)'}</label>
    <input id="model-key" type="password" required={needsKey} autoComplete="off" autoCapitalize="none" spellCheck={false} maxLength={512} value={key} disabled={busy} onChange={event => { setKey(event.target.value); invalidate(); }} />
    <p className="hint">{preset?.local ? 'Leave blank unless you enabled authentication in your model server.' : 'Use a key from this model provider, not your Tavily search key. It stays on this computer.'}</p>
  </>;
  return <form id="local-model-form" className="model-setup" onSubmit={save}>
    <h3>Connect a research model</h3>
    <p>Use a Gemma model on this computer or connect to a provider that runs it for you.</p>
    <fieldset className="model-location" disabled={busy}>
      <legend>Where will your model run?</legend>
      <label><input type="radio" name="model-location" autoFocus checked={preset?.local === true} onChange={() => choose('lmstudio')} />On this computer</label>
      <label><input type="radio" name="model-location" checked={preset?.local === false} onChange={() => choose('openrouter')} />Hosted provider</label>
    </fieldset>
    {preset && <>
      <label htmlFor="model-server">{preset.local ? 'Which app runs your model?' : 'Which provider runs your model?'}</label>
      <select id="model-server" value={server ?? ''} disabled={busy} onChange={event => {
        const value = event.target.value;
        if (value === 'lmstudio' || value === 'ollama' || value === 'custom-local' || value === 'openrouter' || value === 'custom-hosted') choose(value);
      }}>
        {preset.local ? <><option value="lmstudio">LM Studio</option><option value="ollama">Ollama</option><option value="custom-local">Another local server</option></> : <><option value="openrouter">OpenRouter</option><option value="custom-hosted">Another hosted provider</option></>}
      </select>
      {server === 'lmstudio' && <ol className="model-steps"><li>Open <a href="https://lmstudio.ai/download" target="_blank" rel="noopener noreferrer">LM Studio</a> and download a Gemma model that fits your computer.</li><li>Load the model, then start the server in the Developer tab. <a href="https://lmstudio.ai/docs/developer/core/server" target="_blank" rel="noopener noreferrer">Show the server setup guide</a>.</li></ol>}
      {server === 'ollama' && <ol className="model-steps"><li>Install <a href="https://ollama.com/download" target="_blank" rel="noopener noreferrer">Ollama</a> and download a Gemma model using its model library.</li><li>Keep Ollama running, then find your installed models below. <a href="https://docs.ollama.com/api/openai-compatibility" target="_blank" rel="noopener noreferrer">Ollama connection guide</a>.</li></ol>}
      {server === 'openrouter' && <ol className="model-steps"><li>Create an <a href="https://openrouter.ai/settings/keys" target="_blank" rel="noopener noreferrer">OpenRouter API key</a> and paste it below.</li><li>Choose an available Gemma model. Review the provider’s pricing and limits before starting research.</li></ol>}
      {(server === 'custom-local' || server === 'custom-hosted') && <p>Use a server that supports OpenAI-compatible Chat Completions and structured output. Get its API base address from the server screen or provider’s connection guide.</p>}
      {(server === 'custom-local' || server === 'custom-hosted') && endpointField}
      {!preset.local && keyField}
      {preset.local && server === 'custom-local' && keyField}
      {server !== 'custom-local' && server !== 'custom-hosted' && <details className="model-advanced"><summary>{preset.local ? 'Change server address or authentication' : 'Change provider address'}</summary>
        {endpointField}
        {preset.local && keyField}
      </details>}
      <div className="model-discovery">
        <button className="secondary" type="button" disabled={busy || !address.trim() || (needsKey && !key.trim())} onClick={findModels}>{lookup.kind === 'loading' ? 'Finding models…' : 'Find available models'}</button>
        <p className="hint">Only reads model names from this server. It does not generate text, download a model or start research.</p>
      </div>
      {lookup.kind === 'error' && <p role="alert">{lookup.message}</p>}
      {lookup.kind === 'ready' && <>
        {lookup.models.length ? <>
          <label htmlFor="model-choice">Choose your Gemma model</label>
          <select id="model-choice" value={manual ? '' : model} disabled={busy || manual} onChange={event => setModel(event.target.value)}><option value="">Select a model from your server</option>{lookup.models.map(id => <option key={id} value={id}>{id}</option>)}</select>
          <p className="hint">{lookup.models.some(id => id.toLowerCase().includes('gemma')) ? 'Gemma-labelled models appear first. Availability does not establish research quality.' : 'No Gemma-labelled model was found. Install or deploy Gemma first, or select its custom alias if you assigned one.'}</p>
        </> : <p role="status">No models were returned. Install or deploy a Gemma model, keep its server running, then try again.</p>}
      </>}
      <details className="model-advanced" open={manual} onToggle={event => { const next = event.currentTarget.open; if (next !== manual) { setManual(next); setModel(''); } }}><summary>Enter a model ID manually</summary>
        <p>Use this if your server cannot list models. Copy the exact deployed model ID from its model screen or connection guide.</p>
        <label htmlFor="model-name">Model ID</label><input id="model-name" required={manual} maxLength={200} value={manual ? model : ''} disabled={busy} onChange={event => setModel(event.target.value)} />
      </details>
      <p className="hint">Saving replaces the previous model settings. Saved credentials are never loaded into this form.</p>
    </>}
    {saveState.kind === 'error' && <p role="alert">{saveState.message}</p>}
    <div className="review-actions">{preset && <button disabled={busy || !model.trim() || !address.trim() || (needsKey && !key.trim())} type="submit">{saveState.kind === 'saving' ? 'Saving model…' : 'Save research model'}</button>}<button className="secondary" type="button" disabled={saveState.kind === 'saving'} onClick={onCancel}>Cancel model change</button></div>
  </form>;
}
