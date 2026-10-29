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

async function call(path: string, body?: unknown): Promise<unknown> {
  const response = await fetch(path, body === undefined ? {} : {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
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
  start: async (website: string, overrides?: Overrides) =>
    await call('/api/agent/runs', overrides ? { website, overrides } : { website }) as { id: string; status: string },
  run: async (id: string) => parseRun(await call(`/api/agent/runs/${encodeURIComponent(id)}`)),
  list: async () => await call('/api/agent/runs') as AgentRunSummary[],
  override: async (id: string, overrides: Overrides) =>
    parseRun(await call(`/api/agent/runs/${encodeURIComponent(id)}/overrides`, overrides)),
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
