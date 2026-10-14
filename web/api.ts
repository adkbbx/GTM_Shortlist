import Ajv from 'ajv';
import addFormats from 'ajv-formats';
import type { components } from './generated/api';
import runSchema from './generated/RunView.json';
import healthSchema from './generated/Health.json';
import authSchema from './generated/AuthSetup.json';
import walletSchema from './generated/WalletView.json';
import serviceSchema from './generated/ServiceView.json';
import creditHistorySchema from './generated/CreditHistory.json';

export type Run = components['schemas']['RunView'];
export type Health = components['schemas']['Health'];
export type AuthSetup = components['schemas']['LocalAuth'] | components['schemas']['HostedAuth'];
export type Wallet = components['schemas']['WalletView'];
export type CreditHistory = components['schemas']['CreditHistory'];
export type Service = components['schemas']['ServiceView'];
export type Confirmation = components['schemas']['Confirmation'];
export type Record = Run['records'][number];
export type Finding = Record['research']['findings'][number];
export type ExclusionFinding = Record['research']['exclusion_findings'][number];
export type Evidence = components['schemas']['Evidence'];
export type Review = NonNullable<Record['review']>;

const ajv = new Ajv({ strict: false });
addFormats(ajv);
const isRun = ajv.compile<Run>(runSchema);
const isHealth = ajv.compile<Health>(healthSchema);
const isAuthSetup = ajv.compile<AuthSetup>(authSchema);
const isWallet = ajv.compile<Wallet>(walletSchema);
const isService = ajv.compile<Service>(serviceSchema);
const isCreditHistory = ajv.compile<CreditHistory>(creditHistorySchema);
let accessToken: (() => Promise<string | null>) | null = null;
let sessionExpired: ((token: string | null) => void) | null = null;

export function setSessionAccess(token: (() => Promise<string | null>) | null, expired: ((token: string | null) => void) | null) {
  accessToken = token; sessionExpired = expired;
}

async function authorizedFetch(path: string, options: RequestInit = {}) {
  const token = await accessToken?.();
  const headers = new Headers(options.headers);
  if (token) headers.set('Authorization', `Bearer ${token}`);
  const response = await fetch(path, { ...options, headers });
  if (response.status === 401) sessionExpired?.(token ?? null);
  return response;
}

async function request(path: string, body?: unknown): Promise<unknown> {
  const response = await authorizedFetch(path, body === undefined ? undefined : {
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
  async creditHistory(before: string | null = null) {
    const data = await request(`/api/credits/history${before ? `?before=${encodeURIComponent(before)}` : ''}`);
    if (!isCreditHistory(data)) throw new Error('Credit activity is unavailable. Please try again.');
    return data;
  },
  async reuse(id: string, request_key: string) {
    return parseRun(await request(`/api/runs/${encodeURIComponent(id)}/reuse`, { request_key }));
  },
  async service() {
    const data = await request('/api/service');
    if (!isService(data)) throw new Error('Setup-call configuration is unavailable.');
    return data;
  },
  async bookingClick(id: string) {
    const response = await authorizedFetch(`/api/runs/${encodeURIComponent(id)}/booking-click`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ request_key: crypto.randomUUID() }), keepalive: true,
    });
    if (!response.ok) throw new Error('Setup-call click was not recorded');
  },
  async deleteRun(id: string) {
    const response = await authorizedFetch(`/api/runs/${encodeURIComponent(id)}`, { method: 'DELETE' });
    if (!response.ok) {
      const data: unknown = await response.json();
      throw new Error(data && typeof data === 'object' && 'detail' in data && typeof data.detail === 'string'
        ? data.detail : 'Research could not be deleted. Please try again.');
    }
  },
  async credits() {
    const data = await request('/api/credits');
    if (!isWallet(data)) throw new Error('Credit balance is unavailable. Please reload.');
    return data;
  },
  async authSetup() {
    const data = await request('/api/auth/setup');
    if (!isAuthSetup(data)) throw new Error('Account setup is unavailable. Please reload.');
    return data;
  },
  async download(id: string, format: 'csv' | 'json', acceptedOnly: boolean) {
    const response = await authorizedFetch(`/api/runs/${encodeURIComponent(id)}/export?format=${format}&accepted_only=${acceptedOnly}`);
    if (!response.ok) throw new Error('Export could not be downloaded. Check your session and try again.');
    const url = URL.createObjectURL(await response.blob());
    const link = document.createElement('a');
    link.href = url; link.download = `shortlist-${id}.${format}`;
    document.body.append(link); link.click(); link.remove();
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  },
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
