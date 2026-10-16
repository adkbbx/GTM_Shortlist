import Ajv from 'ajv';
import addFormats from 'ajv-formats';
import type { components, paths } from './generated/api';
import runSchema from './generated/RunView.json';
import healthSchema from './generated/Health.json';
import authSchema from './generated/AuthSetup.json';
import walletSchema from './generated/WalletView.json';
import serviceSchema from './generated/ServiceView.json';
import creditHistorySchema from './generated/CreditHistory.json';
import modelsSchema from './generated/LocalModels.json';

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
const isModels = ajv.compile<components['schemas']['LocalModels']>(modelsSchema);
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
  const unavailable = 'We could not connect to the app service. It may be starting up or temporarily unavailable. Wait a moment, then try again.';
  if (!response.headers.get('content-type')?.includes('application/json')) throw new Error(unavailable);
  let data: unknown;
  try { data = await response.json(); } catch { throw new Error(unavailable); }
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

async function localResearchHealth(): Promise<Health> {
  const health = await request('/api/health');
  if (!isHealth(health)) throw new Error('Research readiness could not be checked. Try again.');
  if (health.mode === 'local' && (!health.search_ready || !health.gemma_ready || health.local_search_error)) {
    throw new Error('Set up company search and the research model in Settings before starting research.');
  }
  return health;
}

async function startLocalResearch(health: Health) {
  if (health.mode !== 'local' || health.worker_online) return;
  const started = await request('/api/local/service/start', { confirmation: 'start_research_service' });
  if (!isHealth(started) || !started.worker_online) throw new Error('Background research could not start. Try again.');
}

async function researchCommand(path: string, input: unknown): Promise<Run> {
  const health = await localResearchHealth();
  const run = parseRun(await request(path, input));
  try { if (['queued', 'running'].includes(run.status)) await startLocalResearch(health); }
  catch (error) {
    throw new Error(`Research was saved, but background processing could not start. Retry this action or open the saved run and choose Resume research. ${error instanceof Error ? error.message : ''}`);
  }
  return run;
}

export const api = {
  async availableModels(input: paths['/api/local/model/models']['post']['requestBody']['content']['application/json']) {
    const data = await request('/api/local/model/models', input);
    if (!isModels(data)) throw new Error('The server returned an unreadable model list. Use advanced setup or try again.');
    return data.models;
  },
  async resumeResearch(id: string) {
    const run = parseRun(await request(`/api/runs/${encodeURIComponent(id)}`));
    if (!['queued', 'running'].includes(run.status) || run.termination) throw new Error('This run is no longer waiting to resume. Reload the saved research.');
    await startLocalResearch(await localResearchHealth());
  },
  async startEmailDraft(id: string, recordId: string, input: components['schemas']['StartEmailDraft']) {
    return parseRun(await request(`/api/runs/${encodeURIComponent(id)}/records/${encodeURIComponent(recordId)}/email-draft/start`, input));
  },
  async editEmailDraft(id: string, recordId: string, input: components['schemas']['EditEmailDraft']) {
    return parseRun(await request(`/api/runs/${encodeURIComponent(id)}/records/${encodeURIComponent(recordId)}/email-draft`, input));
  },
  async chooseWebsite(id: string, website_url: string) {
    return researchCommand(`/api/runs/${encodeURIComponent(id)}/website`, { website_url });
  },
  async configureTavily(key: string) {
    const data = await request('/api/local/tavily', { key });
    if (!isHealth(data)) throw new Error('Search setup could not be confirmed. Please reload.');
    return data;
  },
  async configureModel(input: { base_url: string; model: string; key: string }) {
    const data = await request('/api/local/model', input);
    if (!isHealth(data)) throw new Error('Research model setup could not be confirmed. Please reload.');
    return data;
  },
  async stop(id: string) {
    return parseRun(await request(`/api/runs/${encodeURIComponent(id)}/stop`, { confirmation: 'stop' }));
  },
  async retrySeller(id: string) {
    return researchCommand(`/api/runs/${encodeURIComponent(id)}/retry-seller`, { confirmation: 'retry_unstarted_seller' });
  },
  async continueDiscovery(id: string) {
    return researchCommand(`/api/runs/${encodeURIComponent(id)}/continue-discovery`, { confirmation: 'use_saved_candidates_without_search' });
  },
  async creditHistory(before: string | null = null) {
    const data = await request(`/api/credits/history${before ? `?before=${encodeURIComponent(before)}` : ''}`);
    if (!isCreditHistory(data)) throw new Error('Credit activity is unavailable. Please try again.');
    return data;
  },
  async reuse(id: string, request_key: string) {
    return researchCommand(`/api/runs/${encodeURIComponent(id)}/reuse`, { request_key });
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
  async download(id: string, format: 'xlsx' | 'csv' | 'json', acceptedOnly: boolean) {
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
    return researchCommand('/api/sellers', { seller_url, request_key, experience_version: 2 });
  },
  async confirm(id: string, input: Confirmation) {
    return researchCommand(`/api/runs/${encodeURIComponent(id)}/confirm`, input);
  },
  async review(id: string, recordId: string, decision: Review['decision'], reason: string) {
    return parseRun(await request(`/api/runs/${encodeURIComponent(id)}/records/${encodeURIComponent(recordId)}/review`, { decision, reason }));
  },
};
