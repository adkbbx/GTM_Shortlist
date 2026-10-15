import { useRef, useState } from 'react';
import { api } from './api';
import type { Record, Run } from './api';

export function EmailDraftEditor({ record, runId, onSaved }: { record: Record; runId: string; onSaved: (run: Run) => void }) {
  const [base, setBase] = useState(record.email_draft ?? null);
  const [subject, setSubject] = useState(base?.subject ?? '');
  const [body, setBody] = useState(base?.body ?? '');
  const [person, setPerson] = useState(record.research.people[0]?.id ?? '');
  const [operation, setOperation] = useState<'create' | 'save' | 'load' | null>(null);
  const busy = operation !== null;
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const retry = useRef({ signature: '', key: '' });
  const dirty = subject !== (base?.subject ?? '') || body !== (base?.body ?? '');
  const identify = (signature: string) => {
    if (retry.current.signature !== signature) retry.current = { signature, key: crypto.randomUUID() };
    return retry.current.key;
  };
  const accept = (run: Run) => {
    const draft = run.records.find(item => item.research.id === record.research.id)?.email_draft ?? null;
    setBase(draft); setSubject(draft?.subject ?? ''); setBody(draft?.body ?? '');
    retry.current = { signature: '', key: '' }; onSaved(run);
  };
  const create = async () => {
    setOperation('create'); setError(''); setMessage('');
    try {
      accept(await api.startEmailDraft(runId, record.research.id, {
        request_key: identify(`start:${person}`), person_id: person || null, previous_id: null,
      }));
      setMessage('Starting draft saved. Edit it before use.');
    } catch (error) { setError(error instanceof Error ? error.message : 'Draft could not be created. Try again.'); }
    finally { setOperation(null); }
  };
  const save = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!base) return;
    setOperation('save'); setError(''); setMessage('');
    try {
      accept(await api.editEmailDraft(runId, record.research.id, {
        request_key: identify(JSON.stringify({ previous_id: base.id, subject, body })), previous_id: base.id, subject, body,
      }));
      setMessage('Draft saved. Nothing has been sent.');
    } catch (error) { setError(error instanceof Error ? error.message : 'Draft could not be saved. Your edits are still here.'); }
    finally { setOperation(null); }
  };
  const load = async () => {
    setOperation('load'); setError('');
    try { accept(await api.run(runId)); setMessage('Saved draft loaded.'); }
    catch (error) { setError(error instanceof Error ? error.message : 'Saved draft is unavailable.'); }
    finally { setOperation(null); }
  };
  const id = `email-${record.research.id}`;
  const recipient = record.research.people.find(item => item.id === base?.person_id);
  return <section className="email-draft" aria-label="Email draft"><h4>Email draft</h4>
    <p className="hint">A starting point from your confirmed offer and available research. No email is sent and no address is guessed.</p>
    {!base ? <div className="draft-start"><label htmlFor={`${id}-person`}>Draft for</label>
      <select id={`${id}-person`} value={person} disabled={busy} onChange={event => setPerson(event.target.value)}>
        <option value="">Company team</option>{record.research.people.map(item => <option key={item.id} value={item.id}>{item.name} · {item.role}</option>)}
      </select><button type="button" className="secondary" disabled={busy} onClick={create}>{operation === 'load' ? 'Loading…' : busy ? 'Creating draft…' : 'Create starting draft'}</button>
      <p className="hint">Uses saved research. No search or inference credits.</p></div>
      : <form onSubmit={save}><p className="draft-recipient">For {recipient ? `${recipient.name} · ${recipient.role}` : `${record.research.domain} team`}</p>
        <label htmlFor={`${id}-subject`}>Subject</label><input id={`${id}-subject`} value={subject} required maxLength={200} disabled={busy} onChange={event => { setSubject(event.target.value); setMessage(''); }} />
        <label htmlFor={`${id}-body`}>Message</label><textarea id={`${id}-body`} value={body} required maxLength={8000} rows={12} disabled={busy} onChange={event => { setBody(event.target.value); setMessage(''); }} />
        <p className="hint">Add your name and check every claim. Your edits are not automatically fact-checked. {dirty ? 'Unsaved changes.' : 'Saved draft.'}</p>
        {!!base.basis.length && <details className="draft-basis"><summary>Sources used for the starting draft</summary><ul>{base.basis.map((evidence, index) => {
          const source = record.research.sources.find(item => item.id === evidence.source_id);
          return <li key={`${evidence.source_id}-${index}`}><p>{evidence.claim}</p><blockquote>{evidence.passage}</blockquote>{source && <><a href={source.url} target="_blank" rel="noopener noreferrer">{source.title}</a><p className="hint">Retrieved {new Intl.DateTimeFormat(undefined, { dateStyle: 'medium' }).format(new Date(source.retrieved_at))}</p></>}</li>;
        })}</ul></details>}
        <div className="draft-actions"><button type="submit" disabled={busy || !dirty}>{operation === 'load' ? 'Loading…' : busy ? 'Saving…' : 'Save draft'}</button>
          {dirty && <button type="button" className="text-button" disabled={busy} onClick={load}>Discard changes and load saved draft</button>}</div>
      </form>}
    {message && <p className="hint" role="status">{message}</p>}
    {error && <div className="notice" role="alert"><p>{error}</p><button type="button" className="text-button" disabled={busy} onClick={load}>Load saved draft</button><p className="hint">Loading replaces unsaved edits. Copy any changes you want to keep first.</p></div>}
  </section>;
}
