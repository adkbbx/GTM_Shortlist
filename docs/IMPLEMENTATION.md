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
- [x] Implement SerpApi and Tavily adapters, bounded query planner and saved search provenance.
- [ ] Verify unattended discovery with actual search-provider credentials.
- [x] Canonicalize domains, deduplicate and exclude directories/seller domains.
- [x] Preserve unreadable candidate failures and try replacements within six candidates without consuming the three review slots.
- [ ] Compare providers on identical queries and actual measured cost/coverage.

## 4. Fetch and sources
- [x] Reject unsafe URLs, private addresses, unsafe redirects and DNS rebinding.
- [x] Bound network time, bytes, redirects and up to three same-company pages; preserve text, hashes and retrieval dates.
- [x] Add freshness-aware immutable source reuse, preserved retrieval dates, journal precedence and failure/unknown handling.

## 5. Extraction and qualification
- [x] Confirm bounded unique exclusions; persist matched/ruled-out/unknown assessments with citation checks in UI and JSON/CSV.
- [x] Project unassessed exclusions in older runs as unknown without rewriting sources or human reviews.
- [x] Add an independent budgeted, journaled semantic gate; unsupported/unverified assessments become unknown. Real Smeron regression corrected; see semantic-evaluation.md.
- [x] Save bounded invalid model output and schema issues locally; attempt one repair using the shared model budget.
- [x] Test malformed JSON/schema, failed repair, transport failure, capped repair and restart after saved diagnostics.
- [x] Gemma structured output from supplied passages, unknowns and labelled hypotheses; real repair and independently gated findings saved.
- [x] Validate source identity/exact passages, retain dates and fill missing mandatory outcomes as unknown; semantic/date cases measured separately.
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
- [x] Real checkpoint timeline, saved counts, worker availability, offline/reconnect states and one-command API/worker startup.
- [x] Research sheets with evidence passages, source dates and independent accept/reject decisions.
- [x] CSV/JSON export preserves evidence and protects against spreadsheet formulas.
- [x] Test complete flow at 390px phone and 1366px laptop; also 320px, zoom, keyboard and reduced motion.
- [x] Save browser screenshots and repeatable functional checks; repair discovered defects.

## 8. Hosted product
- [x] Implement checksummed Postgres migrations and adapter; verify private roles, two synthetic workspace isolation, concurrent claims, shared quotas and journal replay against PostgreSQL 18.6.
- [x] Wire verified-user API access, request-scoped Postgres and workspace-selected worker; reject invalid/unconfirmed sessions and atomically reserve one demo per workspace in actual database tests.
- [ ] Build signup/login/session recovery UI and verify hosted accounts on phone/laptop.
- [x] Build signup/login/confirmation/password recovery, session refresh/signout and authenticated export; verify with real SDK and labelled browser transport fixtures.
- [ ] Validate signup/email/identity verification against an actual Supabase project.
- [ ] Workspace isolation tested with two actual accounts; private schema/role policies.
- [x] Preserve once-only signup grants and shared attempt caps through research deletion; provide bounded retention preview/apply command.
- [ ] Complete account closure, Supabase identity/session removal and production retention/backup policy.
- [x] Add optional configured setup-call link and owner-scoped click tracking; never infer a booked appointment.
- [x] Add a bounded owner-scoped read-only operator triage queue for unreviewed/needs-research sheets.
- [ ] Complete independent operator annotations/outcomes and verified external calendar confirmation if required.
- [x] Build and test the actual non-root web/API/worker image, isolated database migration/replay and restart in CI; validate private Compose edge configuration.
- [ ] Public HTTPS deployment and persistent database with configured external SMTP.
- [ ] Five real runs across three sellers and observed external user test.
- [ ] Publish accurate demo/setup/evaluation documentation and launch only after checks pass.

## Commercial validation, after product readiness
- [x] Plan credit wallet, three-company signup grant, batch reservation/settlement and paid top-ups in docs/credits.md; pricing remains unvalidated.
- [x] Implement private append-only wallet ledger, automatic signup grants, legacy grant migration and batch holds; prove isolation/concurrency/replay/rollback/process death against real Postgres.
- [x] Integrate credit reservation, atomic research delivery/debit, technical-failure returns and batch-cost UI; preserve legacy demos without a second signup grant.
- [x] Add verified-owner recent credit activity API; prove grant/usage history and two-workspace isolation.
- [x] Expose recent owner-scoped credit activity with authenticated runtime validation, refresh/retry and responsive customer UI.
- [ ] Implement verified paid checkout, complete activity pagination, cancellation and measured larger batches.
- [ ] Identify 30 potential buyers and prioritize 10; prepare offer-specific samples.
- [ ] Validate three $99 reviewed pilots and repeat demand before $49 subscription/billing.

Out of scope: automated outreach, contact databases, CRM integrations and Experiment Judge.

## Continuation rules
The user manually requested Continue after the 18:00 cutoff on 14 October 2026. This renews active implementation authorization. The expired heartbeat is paused; no new automatic work window or rolling retry has been scheduled. Continue small verified steps with ordinary usage, preserving unfinished acceptance gates. The original scheduled window below is historical.

Continue without clarification until 18:00 JST on 14 October 2026 or weekly usage exhaustion. Preserve a handoff at each step and session limit. The13:40JST wake-up occurred after the user’s13:39reset. The same heartbeat now has one final18:00JST cutoff-only check to disable itself/save a handoff; it must not resume implementation at that wake-up. Do not use a rolling five-hour delay. No fabricated results, user tests, credentials, buying intent, deployments or payments. Provider/hosting credentials and actual external testing may create release blockers; implement and test independent work while recording them. Do not copy secrets from unrelated projects into Git. User requested thorough phone and laptop validation.
