import { useState } from 'react';
import { api } from './api';
import type { Run } from './api';

export function RetrySeller({ run, onSaved }: { run: Run; onSaved: (run: Run) => void }) {
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const retry = async () => {
    setSaving(true); setError(null);
    try { onSaved(await api.retrySeller(run.id, run.sample)); }
    catch (reason) { setError(reason instanceof Error ? reason.message : 'Company setup could not be retried.'); }
    finally { setSaving(false); }
  };
  return <section className="sheet" aria-label="Retry company setup"><h3>Company setup stopped before any provider request</h3>
    <p>After the setup issue is resolved, retry this saved run once. Your research limits stay the same.</p>
    <button className="secondary" disabled={saving} onClick={() => void retry()}>{saving ? 'Retrying company setup…' : 'Retry company setup'}</button>
    {error && <p className="notice" role="alert">{error}</p>}
  </section>;
}
