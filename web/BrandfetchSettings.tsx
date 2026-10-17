import { createContext, useState } from 'react';
import type { FormEvent } from 'react';

export const BrandfetchContext = createContext('');
const storageKey = 'shortlist-brandfetch-public-client-id';

export function savedBrandfetchId(): string | null {
  try { return localStorage.getItem(storageKey); } catch { return null; }
}

export function BrandfetchSetup({ clientId, onSaved, onCancel }: {
  clientId: string; onSaved: (id: string) => void; onCancel: () => void;
}) {
  const [value, setValue] = useState(clientId);
  const [error, setError] = useState('');
  const save = (id: string) => {
    try { localStorage.setItem(storageKey, id); onSaved(id); }
    catch { setError('This browser could not save the setting. Allow site storage and try again.'); }
  };
  const submit = (event: FormEvent) => { event.preventDefault(); save(value.trim()); };
  return <form id="local-brandfetch-form" onSubmit={submit}>
    <h3>Brandfetch</h3>
    <p>Shows company suggestions and icons. Get a public client ID from <a href="https://developers.brandfetch.com/register" target="_blank" rel="noopener noreferrer">Brandfetch</a>, then paste it below.</p>
    <label htmlFor="brandfetch-client-id">Public client ID</label>
    <input id="brandfetch-client-id" autoFocus required maxLength={200} pattern="[A-Za-z0-9_-]+" autoComplete="off" autoCapitalize="none" spellCheck={false} value={value} onChange={event => { setValue(event.target.value); setError(''); }} />
    <p className="hint">Use the public client ID, never a secret API key. Saved in this browser for this local workspace. No rebuild is needed. Suggestions and icons contact Brandfetch; saving makes no provider request and starts no research.</p>
    {error && <p role="alert">{error}</p>}
    <div className="review-actions"><button type="submit">Save Brandfetch</button><button type="button" className="secondary" onClick={onCancel}>Cancel</button>{clientId && <button type="button" className="text-button" onClick={() => save('')}>Turn off Brandfetch</button>}</div>
  </form>;
}
