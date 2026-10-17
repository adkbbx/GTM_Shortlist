/* The company typed on the public landing page survives signup and the email-confirmation round trip, which often
   opens in a new tab. It only prefills the workspace field; research never starts without the visitor's action. */
const key = 'shortlist-landing-company';
const lifetime = 24 * 60 * 60 * 1000;

export function keepCompany(company: string) {
  try { localStorage.setItem(key, JSON.stringify({ company: company.slice(0, 300), at: Date.now() })); } catch { /* Optional convenience. */ }
}

export function peekKeptCompany(): string {
  try {
    const saved = JSON.parse(localStorage.getItem(key) ?? 'null') as { company?: unknown; at?: unknown } | null;
    if (saved && typeof saved.company === 'string' && typeof saved.at === 'number' && Date.now() - saved.at < lifetime) return saved.company;
    if (saved) localStorage.removeItem(key);
  } catch { /* Unreadable or blocked storage simply means no prefill. */ }
  return '';
}

export function clearKeptCompany() {
  try { localStorage.removeItem(key); } catch { /* Optional convenience. */ }
}

/* A draft written before signup is claimed by this browser only: its claim token never leaves local storage except
   to read or claim that one draft, and it lapses with the draft after 24 hours. */
const draftKey = 'shortlist-landing-draft';
export type KeptDraft = { id: string; claim: string; website: string };

export function keepDraft(draft: KeptDraft) {
  try { localStorage.setItem(draftKey, JSON.stringify({ ...draft, at: Date.now() })); } catch { /* The visitor can still sign up; research starts from the website instead. */ }
}

export function peekKeptDraft(): KeptDraft | null {
  try {
    const saved = JSON.parse(localStorage.getItem(draftKey) ?? 'null') as Partial<KeptDraft> & { at?: unknown } | null;
    if (saved && typeof saved.id === 'string' && typeof saved.claim === 'string' && typeof saved.website === 'string'
        && typeof saved.at === 'number' && Date.now() - saved.at < lifetime) return { id: saved.id, claim: saved.claim, website: saved.website };
    if (saved) localStorage.removeItem(draftKey);
  } catch { /* Unreadable storage means there is no draft to claim. */ }
  return null;
}

export function clearKeptDraft() {
  try { localStorage.removeItem(draftKey); } catch { /* Optional convenience. */ }
}

/** A random ID for this browser, used only (as a keyed hash on the server) to allow one draft per browser per day. */
export function browserId(): string {
  try {
    const saved = localStorage.getItem('shortlist-browser-id');
    if (saved && /^[0-9a-f-]{36}$/.test(saved)) return saved;
    const created = crypto.randomUUID();
    localStorage.setItem('shortlist-browser-id', created);
    return created;
  } catch { return crypto.randomUUID(); }
}
