/** Presentation-only examples for the public landing page: invented companies, labelled once as an illustrative sample
    in the hero and in the footer. Never sent to the research API. */

/** Invented companies with drawn logo marks. Domains stay on the reserved .example names internally and are not shown;
    real companies' names, domains or favicons must not appear next to these made-up findings. */
const companies: Array<[name: string, domain: string]> = [
  ['Northstar Cloud', 'northstar.example'], ['Lumenly', 'lumenly.example'], ['Ferrylane', 'ferrylane.example'],
  ['Oakpoint Systems', 'oakpoint.example'], ['Brightpath HR', 'brightpath.example'], ['Harbor Ops', 'harbor-ops.example'],
  ['Cindertrail', 'cindertrail.example'], ['Tidewater Labs', 'tidewater.example'], ['Kestrel', 'kestrel-hq.example'],
  ['Mapleforge', 'mapleforge.example'], ['Driftwood', 'driftwood-io.example'], ['Pinegrove Analytics', 'pinegrove.example'],
  ['Saltmarsh', 'saltmarsh.example'], ['Quillstack', 'quillstack.example'], ['Ridgeway Labs', 'ridgeway-labs.example'],
  ['Beacon Ops', 'beacon-ops.example'], ['Signalhouse', 'signalhouse.example'], ['Pagelane', 'pagelane.example'],
  ['Quarry Stack', 'quarry.example'], ['Relay Studio', 'relay-studio.example'],
];
export const exampleShortlist = companies.slice(0, 16).map(([name, domain]) => ({ name, domain }));

const colours = ['#2457a6', '#1f6f6a', '#6a3417', '#1b1b1b', '#5b4b8a', '#b4501c', '#2f7d4f', '#8a6a1f', '#9b3b5a', '#3d6e8f'];
const glyphs = [
  '<circle cx="12" cy="12" r="5.5" fill="none" stroke="#fff" stroke-width="2.6"/>',
  '<path d="M12 6.5 18 17H6z" fill="#fff"/>',
  '<path d="m12 6 6 6-6 6-6-6z" fill="#fff"/>',
  '<path d="M7 8h10M7 12h7M7 16h10" stroke="#fff" stroke-width="2.2" stroke-linecap="round"/>',
  '<path d="M6.5 15.5a5.5 5.5 0 0 1 11 0z" fill="#fff"/>',
  '<circle cx="9" cy="12" r="2.7" fill="#fff"/><circle cx="15.2" cy="12" r="2.7" fill="#fff" opacity=".6"/>',
  '<path d="m8 8 4 4-4 4m5-8 4 4-4 4" fill="none" stroke="#fff" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/>',
  '<rect x="8" y="8" width="8" height="8" rx="1.5" fill="none" stroke="#fff" stroke-width="2.4"/>',
  '<path d="M12 6.5v11M6.5 12h11" stroke="#fff" stroke-width="2.6" stroke-linecap="round"/>',
  '<path d="M7 17c0-6 4-10 10-10 0 6-4 10-10 10z" fill="#fff"/>',
];
/** A small drawn logo for an invented company, so example rows read like real ones without borrowing real brands. */
export function exampleMark(domain: string) {
  const index = Math.max(0, companies.findIndex(([, known]) => known === domain));
  // Every company gets its own colour and shape pairing: shapes cycle every ten, colours shift by one each cycle.
  return `<svg viewBox="0 0 24 24" aria-hidden="true"><rect width="24" height="24" rx="6" fill="${colours[(index * 3 + Math.floor(index / glyphs.length)) % colours.length]}"/>${glyphs[index % glyphs.length]}</svg>`;
}

export const storySteps = ['Offer', 'Market', 'Target', 'Companies', 'Evidence', 'Decision'] as const;

// Scroll share of each story step; evidence gets the most because the highlighter is scrubbed by scroll.
export const storyWeights = [1, 1.1, 1.1, 1.3, 1.8, 1.3];

export const examplePassage = 'Our platform helps business teams manage customer onboarding, from the first welcome to the handover.';

export type FeedState = 'ok' | 'fail' | 'reuse' | 'work';

/** Example checkpoint feed: each step shows as working, then resolves to its saved state. */
export const exampleCheckpoints: Array<{ working: string; state: Exclude<FeedState, 'work'>; done: string }> = [
  { working: 'Searching for B2B onboarding software teams', state: 'ok', done: 'Search saved · 18 results to check' },
  { working: 'Reading the Northstar Cloud product page', state: 'ok', done: 'Saved the Northstar Cloud product page' },
  { working: 'Checking Northstar Cloud against your target', state: 'ok', done: 'Fits: offers a B2B onboarding product' },
  { working: 'Reading the Quarry Stack about page', state: 'fail', done: 'Couldn’t read the Quarry Stack about page' },
  { working: 'Looking up Brightpath HR', state: 'reuse', done: 'Reused the saved Brightpath HR page' },
  { working: 'Checking Quarry Stack against your target', state: 'fail', done: 'Excluded: consumer-only product' },
  { working: 'Finding the exact words on Northstar Cloud', state: 'ok', done: 'Supported: quote found on their page' },
  { working: 'Reading the Tidewater Labs customers page', state: 'ok', done: 'Saved the Tidewater Labs customers page' },
];
