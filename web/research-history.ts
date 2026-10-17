import type { Run } from './api';

export function historyCompany(run: Run): string {
  if (run.sample) return 'Sample company';
  return run.company_name?.trim() || (run.seller_url ? new URL(run.seller_url).hostname : 'Website not selected');
}

export function historyTitle(run: Run): string {
  return run.profile?.target.trim() || historyCompany(run);
}

export function historyStatus(run: Run): string | null {
  const status = runStatus(run);
  return run.sample ? (status ? `Sample · ${status}` : 'Sample data') : status;
}

function runStatus(run: Run): string | null {
  if (run.termination === 'user_stopped') return 'Stopped';
  switch (run.status) {
    case 'awaiting_confirmation': return 'Needs confirmation';
    case 'queued': case 'running': return 'In progress';
    case 'ready': case 'partial': return null;
  }
}

/** Local calendar boundaries also work across daylight-saving changes. */
export function groupHistory(runs: Run[], now = new Date()) {
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const yesterday = new Date(today); yesterday.setDate(today.getDate() - 1);
  const week = new Date(today); week.setDate(today.getDate() - 7);
  const groups: { label: string; runs: Run[] }[] = [
    { label: 'Today', runs: [] },
    { label: 'Yesterday', runs: [] },
    { label: 'Previous 7 days', runs: [] },
    { label: 'Older', runs: [] },
  ];
  for (const run of [...runs].sort((a, b) => Date.parse(b.created_at) - Date.parse(a.created_at))) {
    const date = Date.parse(run.created_at);
    const group = date >= today.getTime() ? groups[0] : date >= yesterday.getTime() ? groups[1] : date >= week.getTime() ? groups[2] : groups[3];
    group.runs.push(run);
  }
  return groups.filter(group => group.runs.length);
}
