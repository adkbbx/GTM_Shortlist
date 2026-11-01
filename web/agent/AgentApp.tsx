import { useEffect, useState } from 'react';
import type { ReactNode } from 'react';
import { BrandfetchContext } from '../BrandfetchSettings';
import { configuredDirectoryId } from '../company-suggestions';
import { AgentBoard } from './AgentBoard';
import { AgentLanding } from './AgentLanding';
import { agentApi } from './agent-api';
import { AgentConfigContext, localConfig } from './agent-config';
import type { AgentConfig } from './agent-config';
import './agent.css';

const currentRun = () => new URLSearchParams(window.location.search).get('agent');

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
        turnstileSiteKey: health?.turnstile_site_key ?? null, examples: health?.examples ?? [] });
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
  return <BrandfetchContext.Provider value={configuredDirectoryId()}><AgentConfigContext.Provider value={config}>
    <a className="skip-link" href="#agent-main">Skip to content</a>
    <header className="agent-header">
      <a className="agent-brand" href="/" onClick={event => { event.preventDefault(); open(null); }}>GTM Shortlist</a>
      {!config.publicDemo && classic !== null && <a className="agent-header-link" href="/?classic=1">Earlier research</a>}
    </header>
    <main id="agent-main" className={`agent-main${runId ? '' : ' is-landing'}`} tabIndex={-1}>
      {runId ? <AgentBoard key={runId} runId={runId} onNew={() => open(null)} /> : <AgentLanding onOpen={open} />}
      <p className="agent-footer">GTM Shortlist · Muse Spark investigates, Muse Spark Open checks every quote, fixed rules decide.
        Built with Muse Spark Open.</p>
    </main>
  </AgentConfigContext.Provider></BrandfetchContext.Provider>;
}
