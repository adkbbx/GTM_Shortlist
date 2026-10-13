import Ajv from 'ajv';
import addFormats from 'ajv-formats';
import type { components } from './generated/api';
import runSchema from './generated/RunView.json';
import healthSchema from './generated/Health.json';

export type Run = components['schemas']['RunView'];
export type Health = components['schemas']['Health'];
export type Confirmation = components['schemas']['Confirmation'];
export type Record = Run['records'][number];
export type Finding = Record['research']['findings'][number];
export type Review = NonNullable<Record['review']>;

const ajv = new Ajv({ strict: false });
addFormats(ajv);
const isRun = ajv.compile<Run>(runSchema);
const isHealth = ajv.compile<Health>(healthSchema);

async function request(path: string, body?: unknown): Promise<unknown> {
  const response = await fetch(path, body === undefined ? undefined : {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
  });
  const data: unknown = await response.json();
  if (!response.ok) {
    const message = data && typeof data === 'object' && 'detail' in data && typeof data.detail === 'string'
      ? data.detail : 'The request could not be saved. Check the fields and try again.';
    throw new Error(message);
  }
  return data;
}

function parseRun(data: unknown): Run {
  if (!isRun(data)) throw new Error('The saved research response is incomplete. Please reload.');
  return data;
}

export const api = {
  async health() {
    const data = await request('/api/health');
    if (!isHealth(data)) throw new Error('Service status is unavailable.');
    return data;
  },
  async runs() {
    const data = await request('/api/runs');
    if (!Array.isArray(data)) throw new Error('Saved runs could not be loaded.');
    return data.map(parseRun);
  },
  async run(id: string) { return parseRun(await request(`/api/runs/${encodeURIComponent(id)}`)); },
  async start(seller_url: string, request_key: string) {
    return parseRun(await request('/api/sellers', { seller_url, request_key }));
  },
  async confirm(id: string, input: Confirmation) {
    return parseRun(await request(`/api/runs/${encodeURIComponent(id)}/confirm`, input));
  },
  async review(id: string, recordId: string, decision: Review['decision'], reason: string) {
    return parseRun(await request(`/api/runs/${encodeURIComponent(id)}/records/${encodeURIComponent(recordId)}/review`, { decision, reason }));
  },
};
