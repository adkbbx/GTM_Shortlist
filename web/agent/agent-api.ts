import Ajv from 'ajv';
import addFormats from 'ajv-formats';
import type { components } from '../generated/api';
import runSchema from '../generated/AgentRunView.json';

export type AgentRunView = components['schemas']['AgentRunView'];
export type AgentRun = AgentRunView['run'];
export type AgentRunSummary = components['schemas']['AgentRunSummary'];
export type AgentEvent = components['schemas']['AgentEvent'];
export type Overrides = components['schemas']['Overrides-Input'];
export type Company = AgentRun['companies'][number];
export type EvidenceItem = Company['evidence'][number];
export type Quote = EvidenceItem['quote'];
export type Profile = NonNullable<AgentRun['profile']>;
export type Competitor = AgentRun['competitors'][number];

const ajv = new Ajv({ strict: false });
addFormats(ajv);
const isRun = ajv.compile<AgentRunView>(runSchema);

export class AgentError extends Error {
  constructor(message: string, readonly status: number) { super(message); }
}

/** Server facts the start page needs. The public demo answers mode "public" with its limits. */
export type AgentHealth = { mode?: string; max_companies?: number; turnstile_site_key?: string | null; synthetic?: boolean;
  examples?: { id: string; website: string; shortlisted: number; created_at: string }[] };

/** The public demo returns an edit token to the browser that started a search; only that browser may correct it. */
const tokenKey = (id: string) => `gtm-agent-edit:${id}`;
export function editToken(id: string): string | null {
  try { return window.localStorage.getItem(tokenKey(id)); } catch { return null; }
}
/** Searches this browser started (it holds their edit tokens), newest last, at most 30. */
export function ownSearches(): { id: string; token: string }[] {
  try {
    const found: { id: string; token: string }[] = [];
    for (let index = 0; index < window.localStorage.length; index++) {
      const key = window.localStorage.key(index) ?? '';
      const id = key.startsWith('gtm-agent-edit:') ? key.slice('gtm-agent-edit:'.length) : '';
      const token = id ? window.localStorage.getItem(key) : null;
      if (/^[0-9a-f]{32}$/.test(id) && token) found.push({ id, token });
    }
    return found.slice(-30);
  } catch { return []; }
}
function keepEditToken(id: string, token: string) {
  try { window.localStorage.setItem(tokenKey(id), token); } catch { /* without storage the search stays read-only here */ }
}

async function call(path: string, body?: unknown, headers: Record<string, string> = {}): Promise<unknown> {
  const response = await fetch(path, body === undefined ? {} : {
    method: 'POST', headers: { 'Content-Type': 'application/json', ...headers }, body: JSON.stringify(body),
  });
  let data: unknown = null;
  try { data = await response.json(); } catch { /* handled below */ }
  if (!response.ok) {
    const detail = data && typeof data === 'object' && 'detail' in data ? (data as { detail: unknown }).detail : null;
    const message = typeof detail === 'string' ? detail
      : Array.isArray(detail) ? 'Enter your company website, for example yourcompany.com.'
        : 'The research service is not answering. Wait a moment, then try again.';
    throw new AgentError(message, response.status);
  }
  return data;
}

function parseRun(data: unknown): AgentRunView {
  if (!isRun(data)) throw new AgentError('The saved run could not be read. Please reload.', 500);
  return data;
}

export const agentApi = {
  health: async () => await call('/api/health') as AgentHealth,
  start: async (website: string, overrides?: Overrides, turnstile?: string) => {
    // This browser's earlier searches, so the new one skips companies already researched for the same website.
    const previous = ownSearches();
    const started = await call('/api/agent/runs', { website, ...(overrides ? { overrides } : {}), ...(turnstile ? { turnstile } : {}),
      ...(previous.length ? { previous } : {}) }) as
      { id: string; status: string; edit_token?: string | null };
    if (started.edit_token) keepEditToken(started.id, started.edit_token);
    return started;
  },
  run: async (id: string) => parseRun(await call(`/api/agent/runs/${encodeURIComponent(id)}`)),
  list: async () => await call('/api/agent/runs') as AgentRunSummary[],
  override: async (id: string, overrides: Overrides) => {
    const token = editToken(id);
    return parseRun(await call(`/api/agent/runs/${encodeURIComponent(id)}/overrides`, overrides, token ? { 'X-Agent-Edit-Token': token } : {}));
  },
  /** Server-Sent Events for one run. Returns a function that closes the stream. */
  follow(id: string, after: number, onEvent: (event: AgentEvent) => void, onEnd: () => void): () => void {
    const source = new EventSource(`/api/agent/runs/${encodeURIComponent(id)}/events?after=${after}`);
    source.addEventListener('progress', message => {
      try { onEvent(JSON.parse((message as MessageEvent<string>).data) as AgentEvent); } catch { /* ignore a malformed line */ }
    });
    source.addEventListener('end', () => { source.close(); onEnd(); });
    source.onerror = () => { source.close(); onEnd(); };
    return () => source.close();
  },
};

const ACTIVE = new Set(['queued', 'running']);
export const isActive = (status: string) => ACTIVE.has(status);

/** Encode one text-fragment term: the fragment syntax reserves "-", "," and "&". */
const term = (text: string) => encodeURIComponent(text).replace(/-/g, '%2D');

/** The source page, scrolled to the quote with a text fragment when the quote is readable page text. */
export function quoteLink(quote: Quote): string {
  if (quote.location === 'html') return quote.url;
  const words = quote.text.replace(/\s+/g, ' ').trim().split(' ');
  const fragment = words.length > 12
    ? `${term(words.slice(0, 5).join(' '))},${term(words.slice(-5).join(' '))}`
    : term(words.join(' '));
  return `${quote.url}#:~:text=${fragment}`;
}

export const domainOf = (url: string) => { try { return new URL(url).hostname.replace(/^www\./, ''); } catch { return url; } };
