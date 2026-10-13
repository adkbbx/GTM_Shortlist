# Progress and handoff

## 14 October 2026, initial setup
Repository was empty. Cloned separately from Before I Call; copied the agreed planning sources into docs/planning. Existing goal is active. Heartbeat `resume-gtm-shortlist-build` created for this chat every five hours, with 18:00 JST today cutoff and weekly-limit stop instruction. User authorizes continuous work while unavailable and asks for thorough validation at phone/laptop sizes.

Architecture follows planning option B: shared Python domain/core, persisted jobs and separate API/worker. Local SQLite first; hosted Postgres/Auth remain explicit release gates. No discovery/search or model result has run yet. Use bundled Python at C:/Users/ADK/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe to bootstrap the project virtual environment. System python alias is unavailable.

Next: domain schemas/config, bounded public fetch, persistence and tests. Then provider adapters and a real saved run. Search credentials have not yet been found/configured. Do not label fixtures as real discovery.

## 14 October, 04:05 JST checkpoint

Initial core pushed as `709cce9`. Since then the guided React UI, API/worker seller confirmation, schema-generated client validation, local Host/origin protection, review/export flows and CI browser checks have been implemented. Current validation: 80 backend tests, Ruff, strict TypeScript/Vite build, six browser tests passed. Phone 390px and laptop 1366px flows were inspected; 320px/200% text, keyboard and reduced motion passed. See validation-2026-10-14.md. These UI tests use labelled synthetic providers, not real discoveries.

First real **assisted** Eygentic run is saved as `4916be8efe824106921f620fb70712dc` in ignored `data/shortlist.sqlite3`. Twelve domains came from an explicitly labelled operator web-search capture. Real HTTPS pages and Gemma inference produced Prismatic source-cited AI/B2B/SaaS assessments with private ownership unknown. Smeron source fetched but extraction failed schema validation; B2B Hub fetching failed. Both failures are honestly partial/unknown. Two saved sources, three supported findings, three candidate records. JSON/CSV exports verified by scripts/verify_saved_run.py. No human review decision or buying intent invented.

Gemma access works via the user's existing DigitalOcean inference credential, configured only in ignored `.env`. No secrets were copied into tracked files. Tavily/SerpApi credentials remain unavailable. Eygentic HTTPS fetching still fails certificate validation; manual confirmation uses the agreed brief instead. Do not claim live search adapter benchmarks or unattended discovery have passed.

Local UI server is running in exec session 29598 at port 8014. Browser panel open was queued. Keep the server while useful; no test server is left running. The six test screenshots are local under `.impeccable/review/` and ignored. The first-run probe file and exports are local under data/ and ignored.

Next priorities, continue without asking user:
1. Inspect and fix structured-output failure at its boundary. Preserve safe diagnostics and raw model output in a bounded checkpoint; schema repair consumes the shared model cap. Validate with real saved Smeron passages.
2. Add semantic labelled cases for negation, wrong entity, old evidence and entailment, plus explicit exclusion qualification. Thirty current citation rejection tests do not count as thirty semantic cases.
3. Improve query precision, successful-candidate selection and three-page coverage, source freshness reuse and full crash-recovery tests. The term private in the initial target search also returns private deployment products; evaluate query planning without weakening ownership evidence.
4. Add hosted Postgres/Auth isolation and demo entitlements, then deployment preparation. Actual external SMTP, hosted credentials, provider benchmarks and observed human tests remain release gates. Build/test independent work while recording unavailable services.
5. Maintain checklist, test changes appropriately, commit/push to the specified repository and check time/usage between steps. Goal remains active. Stop at 18:00 JST today or weekly exhaustion; scheduled heartbeat is resume-gtm-shortlist-build.

## 14 October, 04:12 JST checkpoint

GitHub CI for `52beace` passed both core and UI jobs. Impeccable finishing review returned `ship` after product status and extracted design-system documentation were reconciled. DESIGN.md and `.impeccable/design.json` now describe the actual interface. No layout changes.

Bounded model diagnostics and one explicit shared-budget repair now implemented. Invalid JSON/schema retains up to32k characters plus sanitized validation issues in local checkpoints, separate from exported research. Unknown finding reason is explicit in the model instruction. Repair never happens on transport/auth failures. Eight-call cap includes both original and repair attempts. Tests cover successful repair, repeated-invalid stop, budget exhaustion and restarting after saved diagnostics without repeating original inference. 86 backend tests and Ruff pass; six UI tests pass again.

New real assisted run `21f920ad6818469bbb302c9a3d59a4fe` passes saved-evidence verification: Smeron valid conservative unknowns, Prismatic three cited model assessments plus unknown ownership, B2B Hub fetch failure. No real repair was needed; do not portray fixture repair as an observed real failure recovery. Original run remains immutable. Both runs use imported web-search metadata, not live search adapters.

Next: persist successful provider outcomes atomically so a crash between response and checkpoint can restore results instead of conservative duplicate-dispatch stop. Then implement explicit exclusion findings and meaningful 30-case semantic evaluation, richer source coverage/cache and hosted isolation. Legacy planning documents remain historical; docs/IMPLEMENTATION.md and this file carry current status. At last usage check 59% five-hour,17% weekly consumed, ordinary usage permitted. No credits/reset used. Continue current goal without asking user until cutoff.

## 14 October, 04:20 JST checkpoint

Previous goal turn made verified progress (commit 23716f6). This turn adds a SQLite attempt-result journal. Reservation and request fingerprint precede dispatch. Success/failure state and its replayable value commit atomically under the active worker fence. Restart restores source IDs/dates, candidate search provenance, validated research and bounded model errors without another request. Input/provider/model/endpoint drift stops replay. Uncertain dispatches stop conservatively and continue counting toward caps; no exactly-once HTTP claim. Pre-journal legacy attempts stop safely if their stage checkpoint was not saved. Existing saved runs/exports still verify unchanged.

Tests now total 101 backend checks plus Ruff. Three subprocess tests abruptly terminate Python after a committed search/fetch/model outcome and verify reopened SQLite recovery with exactly two search calls, one fetch and one model call across both processes. Tests also cover accepted-review preservation, atomic rollback, unknown outcomes, replaced workers, concurrent claims, changed inputs and corrupt/legacy journals. Six phone/laptop browser tests passed again. GitHub core and UI for 23716f6 both passed. A Windows timestamp-tie test exposed random queue ordering; insertion order now resolves ties explicitly and the regression test forces tied timestamps.

Worker pending selection now reads oldest eligible jobs directly, separate from the 100 latest runs used by UI, avoiding starvation of older queued jobs. See docs/durability.md for recovery limits. No new paid requests or secrets introduced. Usage last checked 69% five-hour, 18% weekly, allowed. Goal remains active with the same 18:00 JST cutoff and five-hour heartbeat.

Next implementation chunk: explicit, source-grounded exclusion findings in qualification/UI/export. Then 30 meaningful semantic evaluation cases with dated/negated/wrong-entity passages, source coverage/cache, hosted Postgres/Auth/workspace isolation and deployment preparation. External credentials and observed-user tests remain release gates, not reasons to stop independent work.
