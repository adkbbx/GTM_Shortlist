import { useEffect, useState } from 'react';
import { api } from './api';
import type { CreditHistory, Wallet } from './api';

type Activity = { kind: 'loading' } | { kind: 'ready'; history: CreditHistory } | { kind: 'error'; message: string };
const labels = { signup: 'Signup credits', purchase: 'Credits added', usage: 'Company research', refund: 'Credits refunded' } satisfies Record<CreditHistory['entries'][number]['kind'], string>;
const date = (value: string) => new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value));

export function CreditActivity({ wallet }: { wallet: Wallet }) {
  const [activity, setActivity] = useState<Activity>({ kind: 'loading' });
  const [refresh, setRefresh] = useState(0);
  useEffect(() => {
    let cancelled = false;
    setActivity({ kind: 'loading' });
    api.creditHistory().then(history => {
      if (!cancelled) setActivity({ kind: 'ready', history });
    }).catch(error => {
      if (!cancelled) setActivity({ kind: 'error', message: error instanceof Error ? error.message : 'Credit activity is unavailable. Please try again.' });
    });
    return () => { cancelled = true; };
  }, [refresh, wallet.available, wallet.reserved, wallet.used]);

  return <section className="sheet credit-activity" aria-labelledby="activity-heading">
    <div className="activity-heading"><h2 id="activity-heading">Credit activity</h2><button className="text-button" disabled={activity.kind === 'loading'} onClick={() => setRefresh(value => value + 1)}>Refresh activity</button></div>
    <p className="hint">Latest 50 recorded credit changes. Batch reservations and unused credits returned appear with each research run.</p>
    {activity.kind === 'loading' && <p role="status" className="activity-notice">Loading credit activity…</p>}
    {activity.kind === 'error' && <p role="alert" className="notice">{activity.message}</p>}
    {activity.kind === 'ready' && (activity.history.entries.length === 0 ? <p className="activity-notice">No recorded credit changes yet.</p> : <ul className="activity-entries" aria-label="Recorded credit changes">
      {activity.history.entries.map(entry => <li key={entry.id}><div><span>{labels[entry.kind]}</span><time dateTime={entry.created_at}>{date(entry.created_at)}</time></div><span className="activity-amount">{entry.amount > 0 ? '+' : ''}{entry.amount} {Math.abs(entry.amount) === 1 ? 'credit' : 'credits'}</span></li>)}
    </ul>)}
  </section>;
}
