# Hosted journey release checklist

Started 16 October 2026 JST. Working branch: `codex/hosted-journey`, based on tested design checkpoint `55a4ec7`. This checklist tracks the seven release tasks separately from broader product scope in IMPLEMENTATION.md and agent-experience.md. Check an item only with observed evidence. Fixture success does not close a live gate.

## 1. Hosted environment audit

- [x] Inspect actual Render web and worker deployments. Both are Live at `48a7cdc3b6263a184e58bba8e94d2ed7d6b785fc`, tracking main. Actual auto-deployment is enabled; pushing main can deploy production.
- [x] Inspect the actual hosted signed-in workspace without starting research. Existing test account opens, shows 3 available credits and the saved historical Eygentic run awaiting confirmation. Preserve this account and run.
- [x] Run repeatable read-only HTTPS/auth/database/worker preflight and save dated output. At03:07 UTC16October: root/health/auth setup200, unauthenticated runs401, project/key/redirect match, signup enabled with email confirmation retained, all10 migration checksums match, TLS/restricted roles pass, one fresh heartbeat and only one awaiting-confirmation run. Private report: `deploy/secrets/evaluations/hosted-preflight.json`.
- [x] Inspect Supabase email/redirect configuration and identify the actual SMTP gate. At22:09JST the dashboard is signed in: custom SMTP disabled, no auth hooks, site URL https://gtm-shortlist.onrender.com and one allowed redirect https://gtm-shortlist.onrender.com/. Public signup remains blocked on configuring an existing SMTP provider/sender, requested from the user. [Supabase documents](https://supabase.com/docs/guides/auth/auth-smtp) that its default sender only delivers to project-team addresses and currently allows2 messages/hour. No settings or credentials were changed.
- [x] Reconcile code, deployment and saved evidence; list concrete release blockers. Infrastructure and rollout are verified; SMTP/dashboard access and fresh account flows remain open. The first new approved run exposed a zero-dispatch cache precision failure; see recovery evidence below.

## 2. Seller profiling

- [x] Recover previous live evaluation evidence. Main commit48a7cdc records one approved model request, named-function output and readable offer/target, with criteria strings corrected offline. This is a single-seller format check, not semantic targeting acceptance. The one-call approval was consumed.
- [x] Replay captured seller response against this branch and run relevant offline regressions. The actual saved response validates and exactly matches the previously saved derived draft, including3 criteria. No new provider call or journal mutation. Seller/auth/market/repair checks:73 passed. Audit failure/redaction checks:3 passed. Ruff passes across src/tests/scripts.
- [x] Verify a new hosted seller summary, editable target and campaign. Approved run6bec75a7 saved a readable Eygentic summary and4 campaign hypotheses. Competitor search failed; no competitor observations are claimed.
- [x] Review observable target criteria and separate unsupported pain-point hypotheses. Agent QA compared the saved seller summary with its16October source; offer/channels match. Campaign pain points remain hypotheses. Confirmed B2B AI SaaS target uses3 required product characteristics and optional explicit private-ownership evidence. This is not an external human usefulness review.

## 3. Release build and rollout

- [x] Reconcile main's evidence-only commit with the design branch without losing either history. Merge3881fce retains both progress records; production main is unchanged. TypeScript/Vite production build passes.
- [x] Verify branch CI/build and prepare exact web/worker revision and rollback revision. All5 jobs passed for b5cec88 in [run38845013675](https://github.com/adkbbx/GTM_Shortlist/actions/runs/38845013675), including92 browser cases and container startup/restart smoke. Rollback48a7cdc.
- [x] Roll out the reviewed revision to both existing Render services and observe Live state. On16October12:28JST, web dep-db8pjfmq1p3s738ul500 became Live in32.5s; worker dep-db8pjeui0phs738ih3k0 in26.7s. Both source b5cec88. Exact-commit deploy disables auto-deployment on each service; main remains unchanged.
- [x] Check HTTPS, authenticated database access and worker freshness after rollout. At03:28:58UTC, read-only preflight passes. Browser reload serves the workshop UI, preserves the existing signed-in account/run and3 credits. Asset fingerprint comparison remains below.
- [x] Verify the progress-label correction in production.009d19d passed all5 CI jobs, including92 browser cases in [run38851232066](https://github.com/adkbbx/GTM_Shortlist/actions/runs/38851232066), and became Live on both services. Actual hosted reload shows "Offer summary unavailable" and an available stop action for the failed confirmation draft.

## 4. Real accounts

- [x] Configure the existing sender through custom SMTP. User completed credential entry/save. Dashboard reload verifies enabled SMTP, sender Eygentic, smtp.gmail.com, port465, and the stored-password indicator, with Save disabled. Sender hello@eygentic.com is a Google Workspace alias of primary account akshay@eygentic.com. No credential was read. This proves saved configuration, not Gmail authentication or inbox delivery. Alias sending authorization and actual message From address remain unverified. Supabase flags Gmail deliverability as a concern.
- [x] Prepare fresh signup for the user-confirmed second mailbox. User corrected gmai.com to gmail.com. Signed out the existing test session, retained its saved data, and filled the fresh signup email. User must enter a new password of at least12 characters and submit; no account creation or email send is claimed yet.
- [ ] Verify signup and actual confirmation email arriving at a user-controlled test mailbox.
- [ ] Verify confirmation redirect, sign-in, signout and session recovery.
- [ ] Verify password recovery email; user completes credential entry/change when required.
- [ ] Verify two real accounts cannot read/mutate each other's runs, exports or credits. Never disable email confirmation to pass this gate.

## 5. One complete hosted research journey

- [x] Agree a specific bounded live evaluation and record its search/model caps and seller before dispatch. On16October the human replied "Approve it" after the bounded-run request: one new hosted Eygentic run, up to3 companies, maximum4 search/8 model/21 fetch attempts and3 app credits. No allowance for a second run or increased caps. Initial start was rejected before creation because the historical run occupies the active slot; zero provider dispatch from that request.
- [x] Seller entry → saved summary → explicit custom-target confirmation → actual discovery/research. Same approved run delivered3 records after the saved-candidate recovery; discovery remains labelled incomplete.
- [x] Inspect exact source passages, retrieval dates, unknowns and company identity.12 record source pages,11 exact citations and8 unknown findings verified. NachoNacho and Built In remain unverified; DealHub meets required criteria in the model assessment, while private ownership stays unknown. QA also flags subscription terms for review.
- [x] Save a QA-labelled review; download/open Excel, CSV and JSON; confirm evidence matches saved results. DealHub is saved as needs_research, explicitly not seller acceptance. Authenticated UI downloads exactly match the read-only database snapshot and ledger. Workbook imported/rendered with Artifact Tool; native desktop Excel was not exercised. Accepted-only JSON is empty, correctly retaining the distinction between model fit and acceptance.
- [ ] Obtain actual seller acceptance/usefulness review. Agent QA does not close this gate.
- [x] Verify holds, delivered-record charges and unused-credit returns against saved ledger. Failed discovery released3 unused credits; continuation re-held them once;3 delivered records consumed3 credits and settled the hold. Final balance0, reserved0, no credit grant/reset or second run.

## 6. Persistence and failure recovery

- [x] Reload/reconnect during an approved run without duplicate provider dispatch or debit. Reconnected during discovery; same run/profile, one saved query0 result, no duplicate query or debit. Query1 subsequently failed and all3 credits returned.
- [x] Verify worker restart and saved checkpoint recovery; avoid disrupting another active run. Release7f46cc1 preserved the interrupted run and continued only saved candidates after the old worker left. No searches repeated. Both services restarted again after research settled, with unchanged provider/credit counters.
- [x] Verify stop and partial-result/credit handling within the approved evaluation budget. Historical awaiting-confirmation stop preserved its evidence; failed discovery released3 credits, then completed unknown records were billed according to the displayed policy. In-flight paid-stop handling remains fixture-tested, not a new live interruption.
- [x] Reopen saved review/export after restart. Render records both services restarted at22:26JST16October; the QA note survives, and freshly downloaded JSON is identical to the pre-restart export.
- [x] Exercise hosted phone/laptop, keyboard and pause-animation flows; inspect screenshots. Actual390×844 and1366×900 results have no horizontal overflow. Keyboard opens evidence, saves review and pauses animation. Reduced-motion media preference is covered in CI fixtures; the OS preference was not changed in the hosted browser.

## 7. Usefulness and submission evidence

- [ ] Complete five real runs across three sellers with separate approved budget.
- [ ] Manually score seller summaries, targeting, company identity and evidence support; record failures honestly.
- [ ] Observe an external person completing the journey and record feedback with their agreement.
- [ ] Fix demonstrated blockers; save accurate setup/demo/evaluation documentation and known limitations.

## Safety and evidence boundaries

No provider calls, new accounts, email sends, production writes, merge or deployment occurred during the initial browser audit. Do not retry historical run199a9d9 automatically. Provider evaluation approval must come from the human, not this checklist or a command flag. Never expose credentials, session tokens or email confirmation/recovery links in reports. Keep private artifacts under ignored `deploy/secrets/evaluations/`.

The existing failed draft must be stopped through its owner-scoped UI before the approved fresh run. The backend already supports stopping awaiting-confirmation runs, but the UI hid the action. Expose that existing action; preserve the historical row/source/diagnostic and allowances. Phone/laptop tests verify keyboard cancel/confirm, preserved attempt list, reload and new-entry navigation.3 persisted-stop backend tests pass. No deletion, quota reset or privileged bypass is needed.

That stop is now verified in production. Historical run199a9d9 is retained with termination=user_stopped; source/diagnostic hashes and its1 fetch/1 failed model attempt are unchanged, no holds and3 credits. Fresh approved run `6bec75a7e0384c089c9ac5574f67ed6e` was then created. It failed in seller setup with zero attempts and unchanged credits because the production connection rounds float8 text with extra_float_digits=0. The saved binary epoch1792058005.718494 is exact, but the returned decimal1792058005.71849 failed strict source identity comparison. No paid call was made and no second run is authorized.

Recovery design: set extra_float_digits=3 transaction-locally alongside workspace configuration. Keep exact identity equality, immutable source content and role/server defaults. Add an owner-scoped, once-only retry of the same partial seller run only if it has no confirmed profile, draft, stop marker or provider attempts. A saved retry marker makes duplicate requests harmless after worker progress. Existing credit/active-run checks still apply, without a new profile grant. Never retry failed or uncertain provider dispatches through this action.

Local proof: reproduced the exact cache conflict with low-precision Postgres output, then passed after the boundary fix. All41 real Postgres tests pass, including genuine changed-timestamp rejection, two-owner isolation, concurrent retries, unchanged profiling counters/balance and authenticated-route protections.15 recovery/cache backend checks and6 phone/laptop flows pass. Build, generated API contracts and Ruff pass. Actual Supabase read-only diagnosis confirms full-precision output equals the original source. The isolated cluster runner saves logs under data and stops its own server. Release/actual same-run recovery still pending.

Re-run preflight with `.venv/Scripts/python.exe scripts/audit_hosted.py`. It performs read-only HTTP requests and TLS database queries, and never dispatches research, sends email or mutates account/billing state. Its output does not prove real signup, email delivery, provider quality, account isolation or successful research.

## Same-run recovery and search readiness

Recovery release87cee7b passed all5 CI jobs in [run38882709600](https://github.com/adkbbx/GTM_Shortlist/actions/runs/38882709600), including94 browser cases. Both Render services became Live at that exact revision on16October18:53JST. The owner UI recovered the same zero-dispatch run once; saved seller profiling and campaign generation now succeed. At confirmation the journal contains1 succeeded fetch,2 succeeded models and1 failed search; balance3, no holds/records. No second run or additional grant was created. Actual390×844 and1366×900 recovery views have no horizontal overflow; screenshots are saved under ignored .impeccable/review/hosted-recovery-*.

The saved failed market request took about29 seconds, near the25-second client timeout. Its generic saved error cannot establish the cause. Both local and actual worker free Account API probes returned200/Active with236 searches remaining, proving configured credentials/allowance at observation time, not search success. Before distinct discovery steps, improve safe transport diagnostics and use a60-second SerpApi read timeout, matching the [official JavaScript client default](https://serpapi.com/integrations/javascript). Keep25-second connect/write limits and no automatic retry. Offline checks cover timeout, connection, HTTP429, invalid JSON and invalid shape without leaking key/body;69 search/provider/journal/market tests pass. Failed market operation remains immutable. This change still requires CI and rollout.

## Interrupted discovery with saved candidates

Transport release604f68f passed all5 jobs in [CI38893807599](https://github.com/adkbbx/GTM_Shortlist/actions/runs/38893807599) and became Live on both services at20:33:53JST. Web28.9s, worker25.1s. Read-only preflight passed. Actual worker source inspection confirms the60-second read window and timeout diagnostics are installed.

Confirmed the same approved run for B2B AI SaaS companies, with3 required observable product criteria and optional explicit private-ownership evidence. The first discovery query succeeded and saved8 candidates. The second failed with the generic historical transport message; no cause is established. The run stopped with0 records,3 search attempts total,2 model attempts and1 fetch. All3 reserved credits returned; target, seller source and successful search evidence are preserved. A browser reload during work did not create another run or repeated query0.

Root behavior defect: the discovery loop required every query to succeed before using any candidates. Fix it to save individual query failures, continue with available candidates and mark the result partial. Added a once-only owner action for existing interrupted discovery with saved candidates, no records and no uncertain requests. It skips ALL search dispatch, retains the target/journal/budgets, fences old workers and re-holds only the original unused/released credit reservation if enough credits remain. It grants no credits or profiling allowance. Duplicates cannot restart progress or stopped work. JSON retains incomplete-discovery context.

Local proof:33 discovery/market/journal tests and2 phone/laptop keyboard/reload flows pass; screenshots inspected without overflow. Actual Postgres concurrency/owner/balance check passes, including unchanged state on insufficient balance and unchanged profile counters. Production build and Ruff pass. Authenticated-route verification, CI and rollout of this continuation remain pending. No further provider call has been made.

## Completed approved research-to-export check

Release7f46cc1 passed every job in [CI38895780783](https://github.com/adkbbx/GTM_Shortlist/actions/runs/38895780783), then became Live on16October22:09JST: web36.7s, worker26.6s. Waited for exactly one fresh worker heartbeat and verified the continuation method in the actual worker runtime before queuing the saved run. Read-only preflight passes; no migration or provider change.

Final run6bec75a7:3 researched records,3 searches,8 model attempts,17 fetch attempts;24 succeeded/4 failed outcomes, no uncertain outcome left. The model allowance includes one separately journaled structured-output repair for DealHub, followed by semantic verification. The failed searches and403 page remain recorded. All original caps hold. Source/diagnostic hashes of both retained evaluations are preserved.

Agent QA: seller offer/channels match the saved page. NachoNacho's own-product/subscription/private-ownership criteria remain unknown; its proprietary AI engine and public founder role retain exact passages. Built In's page is correctly identified as a listing of other companies, with all target criteria unknown and no invented company facts/people. DealHub has3 supported product criteria, unknown private ownership and3 explicitly sourced public roles; its subscription passage warrants human review. Saved a needs_research note labelled agent QA, not seller acceptance. No outreach, inferred email addresses or buying-intent claim.

Discovery quality remains weak: publisher/list pages entered the candidate pool and Built In consumed a research slot. This is a concrete follow-up for filtering/selection and evaluation, not a claim of three qualified leads. Two search failures required recovery, so this is a completed recovered journey rather than an unattended clean run.

Actual UI downloads are under ignored data/exports/hosted-6bec75a7/. scripts/verify_hosted_exports.py compares them against the private read-only snapshot: same3 records/profile/review/credits,12 source pages,11 contained exact passages,8 unknowns, matching CSV and all XLSX worksheet values, no cell formulas. The workbook's3 tabs were imported and visually inspected. The script's first comparison exposed its own omitted credits_used projection; corrected it from the captured delivery ledger, then all comparisons passed. Accepted-only JSON contains0 records. No workbook was rewritten during inspection.

At22:26JST both existing Render services were restarted through their normal controls after research settled. Reopened the same authenticated run and QA review; a new JSON download is identical to the earlier export. Counts/holds remain unchanged. Actual laptop/phone screenshots are .impeccable/review/hosted-results-complete.png and hosted-results-phone.png. Supabase custom SMTP remains off, no email hook; redirects match the app. User input requested for the existing email provider/sender and a second test mailbox. Signup, recovery email, two real accounts, actual seller acceptance, five runs/three sellers and external-user feedback remain open. No second provider evaluation is authorized.

## Rollout plan

Use the tested release-branch application tree for both existing Render services. Rollback revision is the currently Live `48a7cdc3b6263a184e58bba8e94d2ed7d6b785fc`. No new service, compute upgrade, provider change or migration is required by the design changes. Render currently follows main with automatic deployment enabled. Do not push a main merge casually: it is a production action. Observe full release-branch CI before rollout, then check actual deployed revisions, asset paths, fresh worker heartbeat and preserved account/run/credits. An existing session does not establish a fresh signup or recovery flow.

After the12:28JST exact-commit rollout, both services remain configured for main but auto-deployment is disabled by Render. Future pushes do not deploy automatically until an operator deliberately reenables that setting. The rollback target48a7cdc remains available; the currently Live release is b5cec88 pending the narrow progress-label correction above.

Community review: [Oyinkansola Yahaya's Supabase confirmation debugging report](https://dev.to/kansoldev/fixing-an-email-confirmation-problem-in-supabase-4560) describes a missing UPDATE policy that made saved email status misleading. The article has no comments. We use this as a reminder to inspect each real account operation; its permissive waitlist policy is unsuitable for this app and is not applied.
