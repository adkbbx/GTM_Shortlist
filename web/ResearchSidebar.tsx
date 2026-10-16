import { useEffect, useRef, useState } from 'react';
import type { Run } from './api';
import './ResearchSidebar.css';

export function ResearchSidebar({ runs, activeId, loading, onNew, onSelect }: {
  runs: Run[]; activeId?: string; loading: boolean; onNew: () => void; onSelect: (run: Run) => void;
}) {
  const [collapsed, setCollapsed] = useState(() => window.matchMedia('(max-width: 850px)').matches);
  const [narrow, setNarrow] = useState(() => window.matchMedia('(max-width: 850px)').matches);
  const drawer = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const query = window.matchMedia('(max-width: 850px)');
    const changed = () => { setNarrow(query.matches); setCollapsed(true); };
    query.addEventListener('change', changed);
    return () => query.removeEventListener('change', changed);
  }, []);
  useEffect(() => {
    const dialog = drawer.current;
    if (!narrow || collapsed || !dialog) return;
    dialog.showModal();
    const previous = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => { dialog.close(); document.body.style.overflow = previous; };
  }, [narrow, collapsed]);
  const navigation = <div id="research-navigation" className="research-navigation"><h2>Saved runs</h2>
      {loading ? <p className="sidebar-loading">Loading saved research…</p> : runs.length ? <nav aria-label="Research history">{runs.map(run => {
        const name = run.company_name ?? (run.seller_url ? new URL(run.seller_url).hostname : 'Website not selected');
        const status = run.status.replaceAll('_', ' ');
        const savedDate = new Intl.DateTimeFormat(undefined, { month: 'short', day: 'numeric' }).format(new Date(run.created_at));
        return <button key={run.id} type="button" className={`saved-run ${activeId === run.id ? 'selected' : ''}`}
          onClick={() => { onSelect(run); if (narrow) setCollapsed(true); }} aria-current={activeId === run.id ? 'page' : undefined}
          aria-label={`${name}, ${status}, ${savedDate}`} title={`${name} · ${status} · ${savedDate}`}>
          <svg className="saved-run-icon" width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M6 3h8l4 4v14H6V3Zm8 0v5h4M9 12h6m-6 4h4"/></svg>
          <span className="run-copy"><span className="run-name">{name}</span><span className="run-meta"><time dateTime={run.created_at}>{savedDate}</time><span>{status}</span></span></span>
        </button>;
      })}</nav> : <p className="sidebar-loading">Your saved runs will appear here.</p>}
    </div>;
  return <aside className={`sidebar research-sidebar ${collapsed ? 'is-collapsed' : ''}`} aria-label="Saved research">
    <div className="sidebar-header"><span className="sidebar-heading">Workspace</span><span className="mobile-brand">GTM Shortlist</span><button className="sidebar-toggle" type="button"
      aria-expanded={!collapsed} aria-controls={narrow ? 'research-drawer' : 'research-navigation'} aria-haspopup={narrow ? 'dialog' : undefined} aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
      title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'} onClick={() => setCollapsed(value => !value)}>
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" aria-hidden="true"><rect x="3" y="4" width="18" height="16" rx="3"/><path d={collapsed ? "M9 4v16m3-11 3 3-3 3" : "M9 4v16m6-11-3 3 3 3"}/></svg>
    </button></div>
    <button className="new-run" type="button" onClick={() => { onNew(); if (narrow) setCollapsed(true); }} aria-label="New shortlist" title="New shortlist">
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="m15 5 4 4M5 19l4-1L20 7a2.8 2.8 0 0 0-4-4L5 14l-1 6 6-1M4 8v-2a2 2 0 0 1 2-2h3"/></svg><span className="nav-label">New shortlist</span>
    </button>
    {narrow ? <dialog id="research-drawer" ref={drawer} className="research-drawer" aria-labelledby="drawer-title" onCancel={() => setCollapsed(true)} onKeyDown={event => {
      if (event.key !== 'Tab') return;
      const buttons = event.currentTarget.querySelectorAll<HTMLButtonElement>('button:not([disabled])');
      const first = buttons.item(0);
      const last = buttons.item(buttons.length - 1);
      if (event.shiftKey && event.target === first) { event.preventDefault(); last.focus(); }
      else if (!event.shiftKey && event.target === last) { event.preventDefault(); first.focus(); }
    }} onClick={event => {
      if (event.target !== event.currentTarget) return;
      const box = event.currentTarget.getBoundingClientRect();
      if (event.clientX < box.left || event.clientX > box.right || event.clientY < box.top || event.clientY > box.bottom) setCollapsed(true);
    }}>
      <div className="drawer-heading"><h2 id="drawer-title">Your workspace</h2><button type="button" aria-label="Close saved runs" onClick={() => setCollapsed(true)}>Close <span aria-hidden="true">×</span></button></div>
      {navigation}
    </dialog> : navigation}
  </aside>;
}
