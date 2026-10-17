/** Presentation-only examples for the public landing page. Invented `.example` companies; never sent to the research API. */

export const exampleShortlist = ['northstar', 'lumenly', 'ferrylane', 'oakpoint', 'brightpath', 'harbor-ops', 'cindertrail', 'tidewater',
  'kestrel-hq', 'mapleforge', 'driftwood-io', 'pinegrove', 'saltmarsh', 'quillstack', 'ridgeway-labs', 'beacon-ops'];

export const storySteps = ['Offer', 'Market', 'Target', 'Companies', 'Evidence', 'Decision'] as const;

// Scroll share of each story step; evidence gets the most because the highlighter is scrubbed by scroll.
export const storyWeights = [1, 1.1, 1.1, 1.3, 1.8, 1.3];

export const examplePassage = 'Our platform helps business teams manage customer onboarding, from the first welcome to the handover.';

export type FeedState = 'ok' | 'fail' | 'reuse' | 'work';

/** Example checkpoint feed: each step shows as working, then resolves to its saved state. */
export const exampleCheckpoints: Array<{ working: string; state: Exclude<FeedState, 'work'>; done: string }> = [
  { working: 'Searching for B2B onboarding software teams', state: 'ok', done: 'Search saved · 18 results to check' },
  { working: 'Reading northstar.example/product', state: 'ok', done: 'Saved company page northstar.example' },
  { working: 'Checking northstar.example against your target', state: 'ok', done: 'Fits: offers a B2B onboarding product' },
  { working: 'Reading quarry.example/about', state: 'fail', done: 'Couldn’t read quarry.example/about' },
  { working: 'Looking up brightpath.example', state: 'reuse', done: 'Reused saved page for brightpath.example' },
  { working: 'Checking quarry.example against your target', state: 'fail', done: 'Excluded: consumer-only product' },
  { working: 'Finding the exact words on northstar.example', state: 'ok', done: 'Supported: quote found on their page' },
  { working: 'Reading tidewater.example/customers', state: 'ok', done: 'Saved company page tidewater.example' },
];
