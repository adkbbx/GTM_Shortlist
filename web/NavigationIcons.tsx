/** Shared navigation icons use the same 24px grid and stroke. */
export function MenuToggleIcon({ open }: { open: boolean }) {
  return <svg className={`menu-toggle-icon${open ? ' is-open' : ''}`} width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" aria-hidden="true"><path className="menu-line first" d="M4 12h16" /><path className="menu-line middle" d="M4 12h16" /><path className="menu-line last" d="M4 12h16" /></svg>;
}

export function PlusIcon() {
  return <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" aria-hidden="true"><path d="M12 5v14M5 12h14" /></svg>;
}

export function SettingsIcon() {
  return <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M10.26 2.15 13.74 2.15 14.60 4.86 16.89 6.18 19.66 5.57 21.40 8.58 19.48 10.68 19.48 13.32 21.40 15.42 19.66 18.43 16.89 17.82 14.60 19.14 13.74 21.85 10.26 21.85 9.40 19.14 7.11 17.82 4.34 18.43 2.60 15.42 4.52 13.32 4.52 10.68 2.60 8.58 4.34 5.57 7.11 6.18 9.40 4.86Z" /><circle cx="12" cy="12" r="3" /></svg>;
}

export function PersonIcon() {
  return <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><circle cx="12" cy="8" r="3.5" /><path d="M5 21v-2a7 7 0 0 1 14 0v2" /></svg>;
}
