import { PersonIcon, SettingsIcon } from './NavigationIcons';
import { MenuToggleIcon, PlusIcon } from './NavigationIcons';
import { openWorkspacePanel } from './workspace-panels';
import { usePageScrollLock } from './usePageScrollLock';
import { useEffect, useRef, useState } from 'react';
import type { Run } from './api';
import { SiteIcon } from './SiteIcon';
import './ResearchSidebar.css';

export function ResearchSidebar({ runs, activeId, loading, onNew, onSelect, mobileOpen, onMobileClose, settingsTarget, visibleDesktop, collapsed }: {
  runs: Run[]; activeId?: string; loading: boolean; onNew: () => void; onSelect: (run: Run) => void;
  mobileOpen: boolean; onMobileClose: () => void; settingsTarget?: 'local-settings' | 'account-tray'; visibleDesktop: boolean; collapsed: boolean;
}) {
  const [narrow, setNarrow] = useState(() => window.matchMedia('(max-width: 850px)').matches);
  const drawer = useRef<HTMLDialogElement>(null);
  usePageScrollLock(narrow && mobileOpen);
  useEffect(() => {
    const query = window.matchMedia('(max-width: 850px)');
    const changed = () => { setNarrow(query.matches); onMobileClose(); };
    query.addEventListener('change', changed);
    return () => query.removeEventListener('change', changed);
  }, [onMobileClose]);
  useEffect(() => {
    const dialog = drawer.current;
    if (!narrow || !mobileOpen || !dialog) return;
    dialog.showModal();
    return () => { dialog.close(); };
  }, [narrow, mobileOpen]);
  const navigation = <div id="research-navigation" className="research-navigation"><h2>Saved runs</h2>
      {loading ? <p className="sidebar-loading">Loading saved research…</p> : runs.length ? <nav aria-label="Research history">{runs.map(run => {
        const name = run.company_name ?? (run.seller_url ? new URL(run.seller_url).hostname : 'Website not selected');
        const status = run.status.replaceAll('_', ' ');
        const savedDate = new Intl.DateTimeFormat(undefined, { month: 'short', day: 'numeric' }).format(new Date(run.created_at));
        const identity = name.replace(/^www\./, '').split(/[\s.-]+/).filter(Boolean);
        const initials = (run.company_name && identity.length > 1 ? identity.map(part => part[0]).slice(0, 2).join('') : (identity[0] ?? '?').slice(0, 2)).toUpperCase();
        return <button key={run.id} type="button" className={`saved-run ${activeId === run.id ? 'selected' : ''}`}
          onClick={() => { onSelect(run); if (narrow) onMobileClose(); }} aria-current={activeId === run.id ? 'page' : undefined}
          aria-label={`${name}, ${status}, ${savedDate}`} title={`${name} · ${status} · ${savedDate}`}>
          <SiteIcon runId={run.id} domain={run.seller_url ? new URL(run.seller_url).hostname : undefined} fallback={initials} className="saved-run-identity" />
          <span className="run-copy"><span className="run-name">{name}</span><span className="run-meta"><time dateTime={run.created_at}>{savedDate}</time><span>{status}</span></span></span>
        </button>;
      })}</nav> : <p className="sidebar-loading">Your saved runs will appear here.</p>}
    </div>;
  return <aside className={`sidebar research-sidebar ${collapsed ? 'is-collapsed' : ''}${visibleDesktop ? '' : 'is-empty'}`} aria-label="Saved research">
    <button className="new-run" type="button" onClick={onNew} aria-label="New shortlist" title="New shortlist">
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" aria-hidden="true"><rect x="4" y="4" width="16" height="16" rx="3"/><path d="M12 8v8m-4-4h8"/></svg><span className="nav-label">New shortlist</span>
    </button>
    {narrow ? <dialog id="research-drawer" ref={drawer} className="research-drawer" aria-labelledby="drawer-title" onCancel={onMobileClose} onKeyDown={event => {
      if (event.key !== 'Tab') return;
      const buttons = event.currentTarget.querySelectorAll<HTMLButtonElement>('button:not([disabled])');
      const first = buttons.item(0);
      const last = buttons.item(buttons.length - 1);
      if (event.shiftKey && event.target === first) { event.preventDefault(); last.focus(); }
      else if (!event.shiftKey && event.target === last) { event.preventDefault(); first.focus(); }
    }} onClick={event => {
      if (event.target !== event.currentTarget) return;
      const box = event.currentTarget.getBoundingClientRect();
      if (event.clientX < box.left || event.clientX > box.right || event.clientY < box.top || event.clientY > box.bottom) onMobileClose();
    }}>
      <div className="drawer-heading"><h2 id="drawer-title">Your workspace</h2><button type="button" aria-label="Close saved runs" onClick={onMobileClose}><MenuToggleIcon open={mobileOpen} /></button></div>
      <button className="drawer-new" type="button" onClick={() => { drawer.current?.close(); onMobileClose(); onNew(); }}><PlusIcon /><span>New shortlist</span></button>
      {navigation}
      {settingsTarget && <button className="drawer-settings" type="button" aria-haspopup="dialog" aria-controls={settingsTarget} onClick={() => {
        drawer.current?.close(); onMobileClose();
        openWorkspacePanel(settingsTarget);
      }}>{settingsTarget === 'local-settings' ? <SettingsIcon /> : <PersonIcon />}<span>{settingsTarget === 'local-settings' ? 'Settings' : 'Account'}</span></button>}
    </dialog> : navigation}
  </aside>;
}
