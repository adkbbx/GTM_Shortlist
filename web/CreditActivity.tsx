import { useEffect, useRef, useState } from 'react';
import { api } from './api';
import type { CreditHistory, Wallet } from './api';

type Activity = { kind: 'loading'; history: CreditHistory | null } | { kind: 'ready'; history: CreditHistory } | { kind: 'error'; history: CreditHistory | null; message: string };
const labels = { signup: 'Signup credits', purchase: 'Credits added', usage: 'Company research', refund: 'Credits refunded' } satisfies Record<CreditHistory['entries'][number]['kind'], string>;
const date = (value: string) => new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value));

export function CreditActivity({ wallet }: { wallet: Wallet }) {
  const [activity, setActivity] = useState<Activity>({ kind: 'loading', history: null });
  const [refresh, setRefresh] = useState(0);
  const [cursors, setCursors] = useState<string[]>([]);
  const before = cursors.at(-1) ?? null;
  const heading = useRef<HTMLHeadingElement>(null);
  const focusAfterLoad = useRef(false);
  const navigate = () => {
    focusAfterLoad.current = true;
    setActivity(value => ({ kind: 'loading', history: value.history }));
  };
  useEffect(() => {
    let cancelled = false;
    setActivity(value => ({ kind: 'loading', history: value.history }));
    api.creditHistory(before).then(history => {
      if (!cancelled) setActivity({ kind: 'ready', history });
    }).catch(error => {
      if (!cancelled) setActivity(value => ({ kind: 'error', history: value.history, message: error instanceof Error ? error.message : 'Credit activity is unavailable. Please try again.' }));
    });
    return () => { cancelled = true; };
  }, [refresh, before, wallet.available, wallet.reserved, wallet.used]);
  useEffect(() => {
    if (activity.kind !== 'loading' && focusAfterLoad.current) {
      focusAfterLoad.current = false;
      heading.current?.focus();
    }
  }, [activity.kind]);

  return <section className="sheet credit-activity" aria-labelledby="activity-heading">
    <div className="activity-heading"><h2 id="activity-heading" ref={heading} tabIndex={-1}>Credit activity</h2><button className="text-button" disabled={activity.kind === 'loading'} onClick={() => { navigate(); setCursors([]); setRefresh(value => value + 1); }}>Refresh activity</button></div>
    <p className="hint">Up to 50 recorded changes per page, newest first. Batch reservations and unused credits returned appear with each research run.</p>
    {activity.kind === 'loading' && <p role="status" className="activity-notice">Loading credit activity…</p>}
    {activity.kind === 'error' && <p role="alert" className="notice">{activity.message}</p>}
    {activity.kind === 'ready' && (activity.history.entries.length === 0 ? <p className="activity-notice">No recorded credit changes yet.</p> : <ul className="activity-entries" aria-label="Recorded credit changes">
      {activity.history.entries.map(entry => <li key={entry.id}><div><span>{labels[entry.kind]}</span><time dateTime={entry.created_at}>{date(entry.created_at)}</time></div><span className="activity-amount">{entry.amount > 0 ? '+' : ''}{entry.amount} {Math.abs(entry.amount) === 1 ? 'credit' : 'credits'}</span></li>)}
    </ul>)}
    <nav className="activity-pagination" aria-label="Credit activity pages">
      <button className="secondary" disabled={activity.kind === 'loading' || cursors.length === 0} onClick={() => { navigate(); setCursors(value => value.slice(0, -1)); }}>Newer activity</button>
      <button className="secondary" disabled={activity.kind !== 'ready' || !activity.history.next_cursor} onClick={() => {
        const next = activity.history?.next_cursor;
        if (next) { navigate(); setCursors(value => value.at(-1) === next ? value : [...value, next]); }
      }}>Earlier activity</button>
      {activity.kind === 'ready' && <p className="hint" role="status">Page {cursors.length + 1} · {activity.history.entries.length} recorded changes</p>}
    </nav>
  </section>;
}
