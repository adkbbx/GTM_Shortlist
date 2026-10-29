import { useEffect, useState } from 'react';
import type { FormEvent, ReactNode } from 'react';
import { clearKeptCompany, peekKeptCompany } from '../landing/kept-company';
import { AgentBoard } from './AgentBoard';
import { agentApi, domainOf } from './agent-api';
import type { AgentRunSummary } from './agent-api';
import './agent.css';

const describe = (error: unknown) => error instanceof Error ? error.message : 'Something went wrong. Please try again.';
const currentRun = () => new URLSearchParams(window.location.search).get('agent');

function AgentStart({ onOpen }: { onOpen: (id: string) => void }) {
  // A website typed on the landing page only prefills the field; research waits for the visitor's click.
  const [website, setWebsite] = useState(peekKeptCompany);
  useEffect(() => { clearKeptCompany(); }, []);
  const [count, setCount] = useState(10);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [recent, setRecent] = useState<AgentRunSummary[]>([]);
  useEffect(() => { agentApi.list().then(setRecent).catch(() => undefined); }, []);
  const start = async (event: FormEvent) => {
    event.preventDefault();
    setBusy(true); setError('');
    try {
      const { id } = await agentApi.start(website.trim(), count === 10 ? undefined : { company_count: count });
      onOpen(id);
    } catch (reason) { setError(describe(reason)); setBusy(false); }
  };
  return <section className="agent-start" aria-labelledby="agent-start-heading">
    <h1 id="agent-start-heading">Find companies that need what you sell.</h1>
    <p className="agent-lede">Enter your website. The agent works out what you sell and who buys it, finds matching companies,
      and shows the exact quote behind every verdict.</p>
    <form className="agent-start-form" onSubmit={start}>
      <label htmlFor="agent-website">Your company website</label>
      <div className="agent-start-row">
        <input id="agent-website" name="website" inputMode="url" autoComplete="url" placeholder="yourcompany.com" required
          value={website} onChange={event => setWebsite(event.target.value)} disabled={busy} />
        <button type="submit" disabled={busy || !website.trim()} aria-busy={busy}>{busy ? 'Starting' : `Find ${count} companies`}</button>
      </div>
      <div className="agent-start-options">
        <label htmlFor="agent-count">How many companies <span className="optional">optional</span></label>
        <select id="agent-count" value={count} disabled={busy} onChange={event => setCount(Number(event.target.value))}>
          {[5, 10, 15, 20].map(value => <option key={value} value={value}>{value}</option>)}
        </select>
      </div>
      {error && <p className="notice" role="alert">{error}</p>}
    </form>
    <p className="agent-hint">Nothing else to fill in. You can correct any assumption on the next screen, but you never have to.</p>
    {recent.length > 0 && <section className="agent-recent" aria-labelledby="agent-recent-heading">
      <h2 id="agent-recent-heading">Recent searches</h2>
      <ul>{recent.map(item => <li key={item.id}>
        <a href={`?agent=${item.id}`} onClick={event => { event.preventDefault(); onOpen(item.id); }}>{domainOf(item.website)}</a>
        <span>{item.status === 'complete' ? `${item.shortlisted} shortlisted, ${item.needs_look} need a look, ${item.rejected} rejected` : item.status.replace('_', ' ')}</span>
        {item.synthetic && <span className="agent-tag">Synthetic</span>}
      </li>)}</ul>
    </section>}
  </section>;
}

/** The website-only start flow and live board. Hosted installations keep the classic workspace. */
export function AgentApp({ classic }: { classic: ReactNode }) {
  const [mode, setMode] = useState<'loading' | 'agent' | 'classic'>('loading');
  const [runId, setRunId] = useState(currentRun);
  useEffect(() => {
    let cancelled = false;
    fetch('/api/health').then(response => response.json()).then(health => { if (!cancelled) setMode(health?.mode === 'hosted' ? 'classic' : 'agent'); })
      .catch(() => { if (!cancelled) setMode('agent'); });
    return () => { cancelled = true; };
  }, []);
  useEffect(() => {
    const changed = () => setRunId(currentRun());
    window.addEventListener('popstate', changed);
    return () => window.removeEventListener('popstate', changed);
  }, []);
  const open = (id: string | null) => {
    const flow = new URLSearchParams(window.location.search).get('flow');
    const query = new URLSearchParams();
    if (flow) query.set('flow', flow);
    if (id) query.set('agent', id);
    window.history.pushState(null, '', query.toString() ? `?${query}` : window.location.pathname);
    setRunId(id);
    window.scrollTo({ top: 0 });
  };
  if (mode === 'loading') return null;
  if (mode === 'classic') return <>{classic}</>;
  return <>
    <a className="skip-link" href="#agent-main">Skip to content</a>
    <header className="agent-header">
      <a className="agent-brand" href="/" onClick={event => { event.preventDefault(); open(null); }}>GTM Shortlist</a>
      <a className="agent-header-link" href="/?classic=1">Earlier research</a>
    </header>
    <main id="agent-main" className="agent-main" tabIndex={-1}>
      {runId ? <AgentBoard key={runId} runId={runId} onNew={() => open(null)} /> : <AgentStart onOpen={open} />}
      <p className="agent-footer">GTM Shortlist · Muse Spark investigates, Muse Spark Open checks every quote, fixed rules decide.</p>
    </main>
  </>;
}
