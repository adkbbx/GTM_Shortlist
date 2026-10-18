import type { ReactNode } from 'react';
import type { Run } from './api';

/** Colour-coded research states. Colour never stands alone: every mark has a glyph and sits next to a visible word. */
export type Status = 'ok' | 'fail' | 'work' | 'you' | 'reuse' | 'idle' | 'stopped';
type ProgressEvent = Run['progress']['events'][number];

const glyphs: Partial<Record<Status, ReactNode>> = {
  ok: <path d="m7.5 12.5 3 3 6-7" />,
  fail: <path d="m8.5 8.5 7 7m0-7-7 7" />,
  you: <path d="M12 7.5v5.5M12 16.5v.01" />,
  reuse: <><path d="M7 11a5 5 0 0 1 8.6-3.4L17 9M17 13a5 5 0 0 1-8.6 3.4L7 15" /><path d="M17 5.5V9h-3.5M7 18.5V15h3.5" /></>,
  stopped: <rect x="9" y="9" width="6" height="6" rx="1" fill="currentColor" stroke="none" />,
};

export function StatusMark({ status, className = '', children }: { status: Status; className?: string; children?: ReactNode }) {
  const glyph = glyphs[status];
  return <span className={`status-mark ${status} ${className}`.trim()} aria-hidden="true">{glyph ? <svg viewBox="0 0 24 24">{glyph}</svg> : children}</span>;
}

/** The spinner belongs only to the newest started step while the worker is online; older open steps are idle or stopped. */
export function eventStatus(event: ProgressEvent, latest: boolean, working: boolean, stopped: boolean): Status {
  if (event.state === 'succeeded') return 'ok';
  if (event.state === 'failed') return 'fail';
  if (event.state === 'reused') return 'reuse';
  if (event.state === 'waiting') return 'you';
  return latest && working ? 'work' : stopped ? 'stopped' : 'idle';
}

/** Stage words from research-stages.ts mapped to marks; null keeps the stage number. */
export function stageStatus(state: string, working: boolean): Status | null {
  if (/^Reviewed (\d+) of \1 companies$/.test(state) || state === 'Saved' || state === 'Saved with gaps') return 'ok';
  if (state.startsWith('Reviewed ') || state === 'Needs your input' || state === 'Your review') return 'you';
  if (state === 'Interrupted') return 'fail';
  if (state === 'Stopped') return 'stopped';
  if (state === 'Current stage' && working) return 'work';
  return null;
}
