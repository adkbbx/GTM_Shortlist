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
