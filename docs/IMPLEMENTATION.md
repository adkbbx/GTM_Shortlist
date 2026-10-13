# Implementation checklist

Last updated 14 October 2026 JST. Check a task only after its acceptance evidence is saved in PROGRESS.md. This file is the source of truth for automatic continuation.

## 1. Project and contracts
- [x] Clone dedicated repository and preserve planning sources.
- [x] Install pinned dependencies, CLI and API health/config checks.
- [x] Define immutable confirmed profiles, identity, dated sources, evidence, findings, hypotheses, review decisions and run states.
- [x] Establish open-source licence, contributor setup and CI checks.

## 2. Seller and confirmation
- [ ] Fetch seller pages with provenance and draft offer/target using Gemma.
- [x] Persist editable draft and explicit immutable confirmation before discovery.
- [ ] Validate Eygentic offer and configurable targets for other sellers.

## 3. Discovery and identity
- [ ] Implement SerpApi and Tavily adapters, bounded query planner and saved search provenance.
- [x] Canonicalize domains, deduplicate and exclude directories/seller domains.
- [ ] Compare providers on identical queries and actual measured cost/coverage.

## 4. Fetch and sources
- [x] Reject unsafe URLs, private addresses, unsafe redirects and DNS rebinding.
- [ ] Bound time, bytes, redirects and pages; preserve text, hashes and retrieval dates.
- [ ] Add freshness-aware source reuse and failure/unknown handling.

## 5. Extraction and qualification
- [x] Confirm bounded unique exclusions; persist matched/ruled-out/unknown assessments with citation checks in UI and JSON/CSV.
- [x] Project unassessed exclusions in older runs as unknown without rewriting sources or human reviews.
- [x] Add an independent budgeted, journaled semantic gate; unsupported/unverified assessments become unknown. Real Smeron regression corrected; see semantic-evaluation.md.
- [x] Save bounded invalid model output and schema issues locally; attempt one repair using the shared model budget.
- [x] Test malformed JSON/schema, failed repair, transport failure, capped repair and restart after saved diagnostics.
- [ ] Gemma structured output from supplied passages with explicit unknowns and labelled hypotheses.
- [ ] Validate citation identity, exact passages, dates and mandatory criterion outcomes.
- [x] Measure the real verifier on 30 labelled semantic cases including negation, wrong entity, old facts and compound exclusions; preserve corpus and actual outputs.
- [ ] Benchmark real Gemma checkpoints on the same saved passages.

## 6. Durable execution and limits
- [x] Persist stage jobs, leases, fencing, checkpoints and replayable provider outcomes for restart/resume.
- [x] Idempotent commands reject changed payloads under reused request keys.
- [x] Atomically cap run/global provider attempts including failed/uncertain dispatches.
- [x] Test retries, concurrent starts, expired leases and actual process death against persisted SQLite data.

## First milestone
- [x] One real assisted Eygentic run discovers companies, saves inspectable evidence and exports research. See validation-2026-10-14.md; fully unattended SerpApi/Tavily discovery is still pending.
- [x] Saved report distinguishes source-cited model assessments, unknowns, hypotheses and human acceptance.

## 7. Guided UI and export
- [x] Seller website, editable confirmation, persisted run status and honest partial results.
- [x] Research sheets with evidence passages, source dates and independent accept/reject decisions.
- [x] CSV/JSON export preserves evidence and protects against spreadsheet formulas.
- [x] Test complete flow at 390px phone and 1366px laptop; also 320px, zoom, keyboard and reduced motion.
- [x] Save browser screenshots and repeatable functional checks; repair discovered defects.

## 8. Hosted product
- [ ] Postgres persistence and migrations, Supabase verified signup and JWT validation.
- [ ] Workspace isolation tested with two actual accounts; private schema/role policies.
- [ ] Atomic one-demo entitlement with shared attempt caps; account deletion/retention.
- [ ] Optional configured booking link and operator review queue; separate click/booked metrics.
- [ ] Container/web/worker deployment and persistent database with configured external SMTP.
- [ ] Five real runs across three sellers and observed external user test.
- [ ] Publish accurate demo/setup/evaluation documentation and launch only after checks pass.

## Commercial validation, after product readiness
- [ ] Identify 30 potential buyers and prioritize 10; prepare offer-specific samples.
- [ ] Validate three $99 reviewed pilots and repeat demand before $49 subscription/billing.

Out of scope: automated outreach, contact databases, CRM integrations and Experiment Judge.

## Continuation rules
Continue without clarification until 18:00 JST on 14 October 2026 or weekly usage exhaustion. Preserve a handoff at each step and session limit. Five-hour heartbeat retries this chat. No fabricated results, user tests, credentials, buying intent, deployments or payments. Provider/hosting credentials and actual external testing may create release blockers; implement and test independent work while recording them. Do not copy secrets from unrelated projects into Git. User requested thorough phone and laptop validation.
