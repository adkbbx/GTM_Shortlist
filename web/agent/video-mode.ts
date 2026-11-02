/** Video mode (?video=1): every company except the recording seller shows under an invented name on a reserved
    .example domain, so a demo video names no real company. Applied to the data as it arrives, so every screen agrees,
    and the page says so in a corner tag. ?video=0 turns it off. */

const KEY = 'gtm-video-mode';
const KEEP = new Set(['eygentic.com']);  // the seller in the video, shown as itself
// Job boards and news sites are places, not companies: their hosts stay, and a company's name in their paths changes.
const PLACES = /(?:^|\.)(?:lever\.co|greenhouse\.io|ashbyhq\.com|workable\.com|linkedin\.com|x\.com|twitter\.com|prnewswire\.com|businesswire\.com|globenewswire\.com|techcrunch\.com|crunchbase\.com|g2\.com|capterra\.com)$/;

// Hand-picked for the eygentic.com example, so the story reads well; anything else draws from NAMES.
const CHOSEN: Record<string, string> = {
  thrivecart: 'Loopcart', storable: 'Stackyard', scraperapi: 'Crawlbee', tenstreet: 'Fleetline', setsales: 'Pitchwell',
  northpeak: 'Peakline', conversionlab: 'Splitlab', tuff: 'Gritmode', tuffgrowth: 'Gritmode', tripledart: 'Arrowpoint',
  refinelabs: 'Polishlab', nogood: 'Halfmoon', kalungi: 'Kettlewise', advanceb2b: 'Forwardly', vanta: 'Auditly',
  crisp: 'Chatterly',
};
const NAMES = ['Brightdesk', 'Kitewave', 'Orbitly', 'Lumenpay', 'Tidebase', 'Quillstack', 'Nimbuspost', 'Harborly',
  'Copperleaf', 'Fernway', 'Glintly', 'Mapleforge', 'Northwick', 'Pebblepath', 'Ravenhill', 'Saltbox', 'Tallgrass',
  'Umberly', 'Vellum', 'Wrenfield', 'Yarrowly', 'Zestful', 'Ambermill', 'Birchline', 'Cloudnest', 'Driftwell',
  'Emberly', 'Foxglove', 'Gableworks', 'Hollowtree', 'Inkwell', 'Juniperly', 'Kindlebox', 'Lanternly', 'Mossway',
  'Nettlefield', 'Oakhurst', 'Pinecrest', 'Quarryline', 'Rosewater'];

export function videoMode(): boolean {
  try {
    const flag = new URLSearchParams(window.location.search).get('video');
    if (flag === '1') window.sessionStorage.setItem(KEY, '1');
    if (flag === '0') window.sessionStorage.removeItem(KEY);
    return window.sessionStorage.getItem(KEY) === '1';
  } catch { return false; }
}

const keyOf = (value: string) => value.toLowerCase().replace(/^https?:\/\//, '').replace(/^www\./, '').split('/')[0]
  .replace(/\.[a-z.]+$/, '').replace(/[^a-z0-9]/g, '');
const assigned = new Map<string, string>();
function aliasName(key: string): string {
  const known = CHOSEN[key] ?? assigned.get(key);
  if (known) return known;
  let hash = 0;
  for (const char of key) hash = (hash * 31 + char.charCodeAt(0)) >>> 0;
  const taken = new Set([...Object.values(CHOSEN), ...assigned.values()]);
  for (let step = 0; step < NAMES.length; step += 1) {
    const name = NAMES[(hash + step) % NAMES.length];
    if (!taken.has(name)) { assigned.set(key, name); return name; }
  }
  const name = `${NAMES[hash % NAMES.length]}${assigned.size}`;
  assigned.set(key, name);
  return name;
}

type Entity = { domain?: string | null; name?: string | null };
// Invented domain to the real one, so an action on the screen (Draft outreach) still reaches the right company.
const real = new Map<string, string>();
export const realDomain = (domain: string) => real.get(domain) ?? domain;
const escape = (text: string) => text.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');

/** Replace each company's domain, name and the bare name in its domain, keeping lower case where it was lower case. */
function swap(text: string, entities: Entity[]): string {
  const rules: [RegExp, (match: string) => string][] = [];
  const seen = new Set<string>();
  for (const { domain, name } of entities) {
    const host = domain ? domain.toLowerCase().replace(/^www\./, '') : '';
    if (host && (KEEP.has(host) || PLACES.test(host))) continue;
    const key = keyOf(host || name || '');
    if (!key || KEEP.has(`${key}.com`) || seen.has(`${key}|${host}|${name}`)) continue;
    seen.add(`${key}|${host}|${name}`);
    const alias = aliasName(key);
    const lower = alias.toLowerCase();
    if (host) {
      rules.push([new RegExp(`(?:www\\.)?${escape(host)}`, 'gi'), () => `${lower}.example`]);
      real.set(`${lower}.example`, host);
    }
    if (name && name.trim().length >= 3 && !name.includes('.')) {
      rules.push([new RegExp(`\\b${escape(name.trim())}\\b`, 'gi'), () => alias]);
    }
    const stem = host ? host.split('.')[0] : '';
    if (stem.length >= 4) {
      rules.push([new RegExp(`\\b${escape(stem)}\\b`, 'gi'), match => match === match.toLowerCase() ? lower : alias]);
    }
  }
  return rules.reduce((value, [pattern, replace]) => value.replace(pattern, replace), text);
}

const domainOfUrl = (url: string) => { try { return new URL(url).hostname; } catch { return url; } };

/** A search with every company renamed: the companies, candidates, competitors, the seller's named customers and,
    unless it is the recording seller, the seller itself. */
export function disguiseView<T>(view: T): T {
  // The shape is the generated AgentRunView; only names and domains are read here.
  const run = (view as { run?: Record<string, unknown> }).run as {
    website: string; profile?: { name?: string; existing_customers?: Entity[] } | null; companies?: Entity[];
    candidate_pool?: Entity[]; competitors?: Entity[]; set_aside?: Entity[] } | undefined;
  if (!run) return view;
  const entities: Entity[] = [
    { domain: domainOfUrl(run.website), name: run.profile?.name }, ...(run.companies ?? []), ...(run.candidate_pool ?? []),
    ...(run.competitors ?? []), ...(run.set_aside ?? []), ...(run.profile?.existing_customers ?? [])];
  remember(entities);
  return JSON.parse(swap(JSON.stringify(view), entities)) as T;
}

// Companies seen so far, so a live event naming only a domain is renamed the same way as the board.
const known: Entity[] = [];
function remember(entities: Entity[]) {
  for (const entity of entities) {
    if (!known.some(item => item.domain === entity.domain && item.name === entity.name)) known.push(entity);
  }
}

export function disguiseEvent<T extends { company?: string | null; message: string }>(event: T): T {
  const entities = [...known, ...(event.company ? [{ domain: event.company }] : [])];
  return JSON.parse(swap(JSON.stringify(event), entities)) as T;
}

/** The start page's examples: a website, Shortlisted names and "name: quote" rejections. */
export function disguiseText(text: string, identifiers: string[]): string {
  const entities = identifiers.map(value => value.includes('.') ? { domain: domainOfUrl(value.startsWith('http') ? value : `https://${value}`) }
    : { name: value });
  remember(entities);
  return swap(text, [...known, ...entities]);
}
