import { useState } from 'react';
import type { Run } from './api';
import './ResearchSidebar.css';

export function ResearchSidebar({ runs, activeId, loading, onNew, onSelect }: {
  runs: Run[]; activeId?: string; loading: boolean; onNew: () => void; onSelect: (run: Run) => void;
}) {
  const [collapsed, setCollapsed] = useState(false);
  return <aside className={`sidebar research-sidebar ${collapsed ? 'is-collapsed' : ''}`} aria-label="Saved research">
    <div className="sidebar-header"><span className="sidebar-heading">Workspace</span><button className="sidebar-toggle" type="button"
      aria-expanded={!collapsed} aria-controls="research-navigation" aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
      title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'} onClick={() => setCollapsed(value => !value)}>
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" aria-hidden="true"><rect x="3" y="4" width="18" height="16" rx="3"/><path d="M9 4v16m6-11-3 3 3 3"/></svg>
    </button></div>
    <button className="new-run" type="button" onClick={onNew} aria-label="New shortlist" title="New shortlist">
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="m15 5 4 4M5 19l4-1L20 7a2.8 2.8 0 0 0-4-4L5 14l-1 6 6-1M4 8v-2a2 2 0 0 1 2-2h3"/></svg><span className="nav-label">New shortlist</span>
    </button>
    <div id="research-navigation" className="research-navigation"><h2>Saved runs</h2>
      {loading ? <p className="sidebar-loading">Loading saved research…</p> : runs.length ? <nav aria-label="Research history">{runs.map(run => {
        const name = run.company_name ?? (run.seller_url ? new URL(run.seller_url).hostname : 'Website not selected');
        const status = run.status.replaceAll('_', ' ');
        const savedDate = new Intl.DateTimeFormat(undefined, { month: 'short', day: 'numeric' }).format(new Date(run.created_at));
        return <button key={run.id} type="button" className={`saved-run ${activeId === run.id ? 'selected' : ''}`}
          onClick={() => onSelect(run)} aria-current={activeId === run.id ? 'page' : undefined}
          aria-label={`${name}, ${status}, ${savedDate}`} title={`${name} · ${status} · ${savedDate}`}>
          <svg className="saved-run-icon" width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M6 3h8l4 4v14H6V3Zm8 0v5h4M9 12h6m-6 4h4"/></svg>
          <span className="run-copy"><span className="run-name">{name}</span><span className="run-meta"><time dateTime={run.created_at}>{savedDate}</time><span>{status}</span></span></span>
        </button>;
      })}</nav> : <p className="sidebar-loading">Your saved runs will appear here.</p>}
    </div>
  </aside>;
}
