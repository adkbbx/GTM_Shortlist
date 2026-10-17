import type { KeyboardEvent } from 'react';

type PanelId = 'local-settings' | 'account-tray';

export function workspacePanelOpen(id: PanelId) {
  const panel = document.getElementById(id);
  return Boolean(panel?.matches(':popover-open') || (panel instanceof HTMLDialogElement && panel.open));
}

export function openWorkspacePanel(id: PanelId) {
  const panel = document.getElementById(id);
  if (!panel || workspacePanelOpen(id)) return;
  if (panel.hasAttribute('popover')) panel.showPopover();
  else if (panel instanceof HTMLDialogElement) panel.showModal();
}

/** First-run setup: open local Settings straight at the model or company-search section. */
export type LocalSetupSection = 'model' | 'search';
export function openLocalSetup(section: LocalSetupSection) {
  window.dispatchEvent(new CustomEvent<LocalSetupSection>('shortlist:local-setup', { detail: section }));
}

export function closeWorkspacePanel(id: PanelId) {
  const panel = document.getElementById(id);
  if (panel?.matches(':popover-open')) panel.hidePopover();
  else if (panel instanceof HTMLDialogElement && panel.open) panel.close();
}

export function trapPanelTab(event: KeyboardEvent<HTMLElement>) {
  if (event.key !== 'Tab') return;
  const controls = Array.from(event.currentTarget.querySelectorAll<HTMLElement>('button:not([disabled]),input:not([disabled]),select:not([disabled]),textarea:not([disabled]),a[href],summary,[tabindex="0"]')).filter(element => element.getClientRects().length > 0);
  const first = controls[0];
  const last = controls.at(-1);
  if (event.shiftKey && event.target === first) { event.preventDefault(); last?.focus(); }
  else if (!event.shiftKey && event.target === last) { event.preventDefault(); first?.focus(); }
}
