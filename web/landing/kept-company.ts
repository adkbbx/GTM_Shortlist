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
