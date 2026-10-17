export type CompanySuggestion = { domain: string; name: string; icon?: string };
export const configuredDirectoryId = () => document.querySelector<HTMLMetaElement>('meta[name="shortlist-company-suggestions-client-id"]')?.content.trim() ?? import.meta.env.VITE_BRANDFETCH_CLIENT_ID?.trim() ?? '';

function publicDomain(value: unknown): value is string {
  if (typeof value !== 'string' || value.length > 253 || !/^(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$/i.test(value)) return false;
  try { return new URL(`https://${value}`).hostname === value.toLowerCase(); } catch { return false; }
}

/** Parse the public directory boundary. Never treat directory metadata as research evidence. */
export function parseSuggestions(value: unknown): CompanySuggestion[] {
  if (!Array.isArray(value)) throw new Error('Company suggestions are temporarily unavailable. Enter a website to continue.');
  const companies = new Map<string, CompanySuggestion>();
  for (const item of value.slice(0, 50)) {
    if (!item || typeof item !== 'object' || !('domain' in item) || !publicDomain(item.domain)) continue;
    const domain = item.domain.toLowerCase();
    const name = 'name' in item && typeof item.name === 'string' ? item.name.trim().slice(0, 160) : domain;
    let icon: string | undefined;
    if ('icon' in item && typeof item.icon === 'string') {
      try {
        const url = new URL(item.icon);
        if (url.protocol === 'https:' && !url.username && !url.password && (url.hostname === 'brandfetch.io' || url.hostname.endsWith('.brandfetch.io'))) icon = url.href;
      } catch { /* Use the site's favicon instead. */ }
    }
    if (!companies.has(domain)) companies.set(domain, { domain, name: name || domain, icon });
  }
  return [...companies.values()].slice(0, 6);
}

export async function directorySuggestions(query: string, clientId: string, signal: AbortSignal) {
  const url = new URL(`https://api.brandfetch.io/v2/search/${encodeURIComponent(query)}`);
  url.searchParams.set('c', clientId);
  const response = await fetch(url, { signal, credentials: 'omit', referrerPolicy: 'no-referrer', redirect: 'error' });
  if (!response.ok) throw new Error(response.status === 429 ? 'Company suggestions are busy. Enter a website or try again later.' : 'Company suggestions are temporarily unavailable. Enter a website to continue.');
  const body = await response.text();
  if (body.length > 65536) throw new Error('Company suggestions are temporarily unavailable. Enter a website to continue.');
  return parseSuggestions(JSON.parse(body));
}
