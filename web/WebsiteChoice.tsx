import { useState } from 'react';
import type { FormEvent } from 'react';
import { api } from './api';
import type { Run } from './api';

export function WebsiteChoice({ run, onSaved }: { run: Run; onSaved: (run: Run) => void }) {
  const [website, setWebsite] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const matches = run.website_matches ?? [];
  const choose = async (url: string) => {
    setSaving(true); setError('');
    try { onSaved(await api.chooseWebsite(run.id, url)); }
    catch (reason) { setError(reason instanceof Error ? reason.message : 'Website could not be saved. Please try again.'); }
    finally { setSaving(false); }
  };
  const submit = (event: FormEvent) => { event.preventDefault(); void choose(website); };
  return <section className="sheet website-choice" aria-labelledby="website-choice-heading">
    <h2 id="website-choice-heading">Which website belongs to {run.company_name}?</h2>
    <p className="intro">Confirm your business before we read its offer. Search matches may refer to another company with the same name.</p>
    {run.error && <p className="notice" role="status">{run.error}</p>}
    {matches.length > 0 && <ul aria-label="Company website matches">{matches.map(match => <li key={match.domain}>
      <div><p>{match.name}</p><a href={match.url} target="_blank" rel="noopener noreferrer">{match.url}</a></div>
      <button className="secondary" disabled={saving} onClick={() => void choose(match.url)}>Use {match.domain}</button>
    </li>)}</ul>}
    <form onSubmit={submit}><label htmlFor="chosen-website">Company website</label><p className="hint">If these matches aren't yours, enter the correct website.</p>
      <div className="website-form"><input id="chosen-website" type="text" inputMode="url" autoCapitalize="none" autoCorrect="off" spellCheck={false} required maxLength={2048} placeholder="your-company.com" value={website} disabled={saving} onChange={event => setWebsite(event.target.value)} /><button disabled={saving} type="submit">{saving ? 'Saving website…' : 'Use this website'}</button></div>
    </form>
    {error && <p className="notice" role="alert">{error}</p>}
  </section>;
}
