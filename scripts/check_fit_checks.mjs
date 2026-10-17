// Fit checks the confirmation form flags as rarely stated on a company's own website (web/criteria.ts).
// The flagged set includes every required check that stayed unknown in saved research; the observable set must stay quiet.
import assert from 'node:assert/strict';
import { rarelyPublicCheck } from '../web/criteria.ts';

const flagged = [
  'Privately held startup, with explicit current evidence of ownership and startup stage', 'Seed or Series A funding stage',
  'Unsure if they are targeting the right customer profile (ICP).', 'Uncertain if the current messaging resonates with the target audience.',
  'Spending on growth/channels without knowing which specific one produces conversations.', 'Uncertainty regarding whether the current offer converts.',
  'Want to scale growth but lack confidence that the system/infrastructure is ready.', 'Venture-backed SaaS company',
  'Annual revenue of more than $10M', 'Has a budget for outbound tools', 'Planning to expand into Europe', 'Recently raised a Series B',
];
const observable = [
  'Offers software with artificial intelligence as a core capability', 'Sells software to businesses', 'Offers software as a subscription or hosted service',
  'SaaS company', 'B2B company', 'Sells revenue operations software', 'Offers investor relations software', 'Provides property valuation services',
  'Confidential computing platform', 'Sells spend management software', 'Has an implementation team that runs customer onboarding',
  'Lists a partner program on its website', 'Publishes pricing for business plans', 'Has 50 or more employees', 'Offers budgeting software for finance teams',
];
for (const text of flagged) assert.equal(rarelyPublicCheck(text), true, `should flag: ${text}`);
for (const text of observable) assert.equal(rarelyPublicCheck(text), false, `should not flag: ${text}`);
console.log(`Fit-check advice: ${flagged.length} rarely public and ${observable.length} observable checks classified correctly`);
