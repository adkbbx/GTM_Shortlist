import { useState } from 'react';
import { api } from './api';
import type { Run } from './api';

export function ContinueDiscovery({ run, onSaved }: { run: Run; onSaved: (run: Run) => void }) {
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const resume = async () => {
    setSaving(true); setError(null);
    try { onSaved(await api.continueDiscovery(run.id)); }
    catch (reason) { setError(reason instanceof Error ? reason.message : 'Saved research could not continue.'); }
    finally { setSaving(false); }
  };
  return <section className="sheet" aria-label="Continue saved discovery"><h3>Your saved search candidates are available</h3>
    <p>Continue this batch once using the candidates already saved. No search is repeated. Your confirmed target and research limits stay the same.</p>
    {run.credits && <p>Up to {run.credits.maximum} returned credits will be reserved again. Only delivered research uses credits.</p>}
    <button className="secondary" disabled={saving} onClick={() => void resume()}>{saving ? 'Continuing saved research…' : 'Continue with saved candidates'}</button>
    {error && <p className="notice" role="alert">{error}</p>}
  </section>;
}
