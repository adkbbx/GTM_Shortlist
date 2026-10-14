import { useRef, useState } from 'react';
import { api } from './api';
import type { Run } from './api';

type StopState = { kind: 'idle' } | { kind: 'confirming'; error: string | null } | { kind: 'saving' };

export function ResearchStop({ run, onStopped }: { run: Run; onStopped: (run: Run) => void }) {
  const [state, setState] = useState<StopState>({ kind: 'idle' });
  const trigger = useRef<HTMLButtonElement>(null);
  const keep = () => { setState({ kind: 'idle' }); window.setTimeout(() => trigger.current?.focus(), 0); };
  const stop = async () => {
    setState({ kind: 'saving' });
    try { onStopped(await api.stop(run.id)); }
    catch (error) { setState({ kind: 'confirming', error: error instanceof Error ? error.message : 'Research could not be stopped. Please try again.' }); }
  };
  return <section className="stop-research" aria-label="Stop research">
    {state.kind === 'idle' ? <button ref={trigger} className="text-button" onClick={() => setState({ kind: 'confirming', error: null })}>Stop this run</button> : <>
      <h3>Stop this research run?</h3>
      <p>Keep completed sheets and return unused research credits. Completed company research remains charged. A request already underway may still finish.</p>
      <div className="review-actions"><button className="secondary" autoFocus disabled={state.kind === 'saving'} onClick={keep}>Keep researching</button><button className="secondary" disabled={state.kind === 'saving'} onClick={() => void stop()}>{state.kind === 'saving' ? 'Stopping…' : 'Stop research'}</button></div>
      {state.kind === 'confirming' && state.error && <p className="notice" role="alert">{state.error}</p>}
    </>}
  </section>;
}
