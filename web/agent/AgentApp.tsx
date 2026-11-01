import { useEffect, useState } from 'react';
import type { ReactNode } from 'react';
import { BrandfetchContext } from '../BrandfetchSettings';
import { configuredDirectoryId } from '../company-suggestions';
import { AgentBoard } from './AgentBoard';
import { AgentLanding } from './AgentLanding';
import { YourShortlist } from './YourShortlist';
import { agentApi } from './agent-api';
import { AgentConfigContext, localConfig } from './agent-config';
import type { AgentConfig } from './agent-config';
import './agent.css';

const currentRun = () => new URLSearchParams(window.location.search).get('agent');
const onShortlist = () => new URLSearchParams(window.location.search).get('shortlist') === '1';

/** The website-only start flow and live board. Hosted installations keep the classic workspace; the public demo
 *  (classic is null) is agent-only. */
export function AgentApp({ classic }: { classic: ReactNode }) {
  const [mode, setMode] = useState<'loading' | 'agent' | 'classic'>('loading');
  const [config, setConfig] = useState<AgentConfig>(localConfig);
  const [runId, setRunId] = useState(currentRun);
  const [shortlist, setShortlist] = useState(onShortlist);
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
    const changed = () => { setRunId(currentRun()); setShortlist(onShortlist()); };
    window.addEventListener('popstate', changed);
    return () => window.removeEventListener('popstate', changed);
  }, []);
  const open = (id: string | null, list = false) => {
    const flow = new URLSearchParams(window.location.search).get('flow');
    const query = new URLSearchParams();
    if (flow) query.set('flow', flow);
    if (id) query.set('agent', id);
    if (list) query.set('shortlist', '1');
    window.history.pushState(null, '', query.toString() ? `?${query}` : window.location.pathname);
    setRunId(id);
    setShortlist(list);
    window.scrollTo({ top: 0 });
  };
  if (mode === 'loading') return null;
  if (mode === 'classic') return <>{classic}</>;
  return <BrandfetchContext.Provider value={configuredDirectoryId()}><AgentConfigContext.Provider value={config}>
    <a className="skip-link" href="#agent-main">Skip to content</a>
    <header className="agent-header">
      <a className="agent-brand" href="/" onClick={event => { event.preventDefault(); open(null); }}>
        <svg className="agent-brand-mark" viewBox="0 0 64 64" aria-hidden="true"><path fill="#e0692c" fillRule="evenodd" d="M18 4H46Q48 4 48 6V20Q60 25 60 38V58Q60 60 58 60H48Q46 60 46 58V36Q46 32 42 32H22Q18 32 18 36V58Q18 60 16 60H6Q4 60 4 58V38Q4 25 16 20V6Q16 4 18 4ZM24 12V20H30V12ZM36 12V20H42V12Z"/><path fill="#e0692c" d="M22 46L27 41L31 45L39 37L44 42L31 55Z"/></svg>
        <span>GTM Shortlist</span></a>
      <nav className="agent-header-nav" aria-label="Main">
        <a className="agent-header-link" href="?shortlist=1" aria-current={shortlist ? 'page' : undefined}
          onClick={event => { event.preventDefault(); open(null, true); }}>Your shortlist</a>
        {!config.publicDemo && classic !== null && <a className="agent-header-link" href="/?classic=1">Earlier research</a>}
      </nav>
    </header>
    <main id="agent-main" className={`agent-main${runId || shortlist ? '' : ' is-landing'}`} tabIndex={-1}>
      {runId ? <AgentBoard key={runId} runId={runId} onNew={() => open(null)} />
        : shortlist ? <YourShortlist onOpen={id => open(id)} onNew={() => open(null)} /> : <AgentLanding onOpen={open} />}
      <p className="agent-footer">GTM Shortlist · Muse Spark investigates, Muse Spark Open checks every quote, fixed rules decide.
        Built with Muse Spark Open.</p>
    </main>
  </AgentConfigContext.Provider></BrandfetchContext.Provider>;
}
