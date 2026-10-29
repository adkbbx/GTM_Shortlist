import { useEffect, useRef, useState } from 'react';
import type { FormEvent, ReactNode } from 'react';
import { clearKeptCompany, peekKeptCompany } from '../landing/kept-company';
import { turnstileToken } from '../landing/turnstile';
import { AgentBoard } from './AgentBoard';
import { agentApi, domainOf } from './agent-api';
import type { AgentRunSummary } from './agent-api';
import { AgentConfigContext, countOptions, localConfig, useAgentConfig } from './agent-config';
import type { AgentConfig } from './agent-config';
import './agent.css';

const describe = (error: unknown) => error instanceof Error ? error.message : 'Something went wrong. Please try again.';
const currentRun = () => new URLSearchParams(window.location.search).get('agent');

function AgentStart({ onOpen }: { onOpen: (id: string) => void }) {
  const config = useAgentConfig();
  // A website typed on the landing page only prefills the field; research waits for the visitor's click.
  const [website, setWebsite] = useState(peekKeptCompany);
  useEffect(() => { clearKeptCompany(); }, []);
  const [count, setCount] = useState(Math.min(10, config.maxCompanies));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [recent, setRecent] = useState<AgentRunSummary[]>([]);
  const check = useRef<HTMLDivElement>(null);
  // The public demo never lists other visitors' searches.
  useEffect(() => { if (!config.publicDemo) agentApi.list().then(setRecent).catch(() => undefined); }, [config.publicDemo]);
  const start = async (event: FormEvent) => {
    event.preventDefault();
    setBusy(true); setError('');
    try {
      const token = config.turnstileSiteKey && check.current ? await turnstileToken(config.turnstileSiteKey, check.current) : undefined;
      const { id } = await agentApi.start(website.trim(), count === 10 ? undefined : { company_count: count }, token);
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
          {countOptions(config.maxCompanies).map(value => <option key={value} value={value}>{value}</option>)}
        </select>
      </div>
      <div ref={check} className="agent-check" />
      {error && <p className="notice" role="alert">{error}</p>}
    </form>
    <p className="agent-hint">Nothing else to fill in. You can correct any assumption on the next screen, but you never have to.</p>
    {config.publicDemo && <p className="agent-hint">Public demo: up to {config.maxCompanies} companies per search. Anyone with a
      search's link can read it; only this browser can change it.</p>}
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

/** The website-only start flow and live board. Hosted installations keep the classic workspace; the public demo
 *  (classic is null) is agent-only. */
export function AgentApp({ classic }: { classic: ReactNode }) {
  const [mode, setMode] = useState<'loading' | 'agent' | 'classic'>('loading');
  const [config, setConfig] = useState<AgentConfig>(localConfig);
  const [runId, setRunId] = useState(currentRun);
  useEffect(() => {
    let cancelled = false;
    agentApi.health().then(health => {
      if (cancelled) return;
      if (health?.mode === 'hosted' && classic !== null) { setMode('classic'); return; }
      setConfig({ ...localConfig, publicDemo: health?.mode === 'public', maxCompanies: health?.max_companies ?? localConfig.maxCompanies,
        turnstileSiteKey: health?.turnstile_site_key ?? null });
      setMode('agent');
    }).catch(() => { if (!cancelled) setMode('agent'); });
    return () => { cancelled = true; };
  }, [classic]);
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
  return <AgentConfigContext.Provider value={config}>
    <a className="skip-link" href="#agent-main">Skip to content</a>
    <header className="agent-header">
      <a className="agent-brand" href="/" onClick={event => { event.preventDefault(); open(null); }}>GTM Shortlist</a>
      {!config.publicDemo && classic !== null && <a className="agent-header-link" href="/?classic=1">Earlier research</a>}
    </header>
    <main id="agent-main" className="agent-main" tabIndex={-1}>
      {runId ? <AgentBoard key={runId} runId={runId} onNew={() => open(null)} /> : <AgentStart onOpen={open} />}
      <p className="agent-footer">GTM Shortlist · Muse Spark investigates, Muse Spark Open checks every quote, fixed rules decide.
        Built with Muse Spark Open.</p>
    </main>
  </AgentConfigContext.Provider>;
}
