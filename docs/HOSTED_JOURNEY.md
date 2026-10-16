# Hosted journey release checklist

Started 16 October 2026 JST. Working branch: `codex/hosted-journey`, based on tested design checkpoint `55a4ec7`. This checklist tracks the seven release tasks separately from broader product scope in IMPLEMENTATION.md and agent-experience.md. Check an item only with observed evidence. Fixture success does not close a live gate.

## 1. Hosted environment audit

- [x] Inspect actual Render web and worker deployments. Both are Live at `48a7cdc3b6263a184e58bba8e94d2ed7d6b785fc`, tracking main. Actual auto-deployment is enabled; pushing main can deploy production.
- [x] Inspect the actual hosted signed-in workspace without starting research. Existing test account opens, shows 3 available credits and the saved historical Eygentic run awaiting confirmation. Preserve this account and run.
- [x] Run repeatable read-only HTTPS/auth/database/worker preflight and save dated output. At03:07 UTC16October: root/health/auth setup200, unauthenticated runs401, project/key/redirect match, signup enabled with email confirmation retained, all10 migration checksums match, TLS/restricted roles pass, one fresh heartbeat and only one awaiting-confirmation run. Private report: `deploy/secrets/evaluations/hosted-preflight.json`.
- [ ] Inspect Supabase email/redirect configuration and identify the actual SMTP gate. Dashboard is signed out; user login requested. Public settings cannot establish SMTP configuration/delivery.
- [x] Reconcile code, deployment and saved evidence; list concrete release blockers. Infrastructure and rollout are verified; SMTP/dashboard access and fresh account flows remain open. The first new approved run exposed a zero-dispatch cache precision failure; see recovery evidence below.

## 2. Seller profiling

- [x] Recover previous live evaluation evidence. Main commit48a7cdc records one approved model request, named-function output and readable offer/target, with criteria strings corrected offline. This is a single-seller format check, not semantic targeting acceptance. The one-call approval was consumed.
- [x] Replay captured seller response against this branch and run relevant offline regressions. The actual saved response validates and exactly matches the previously saved derived draft, including3 criteria. No new provider call or journal mutation. Seller/auth/market/repair checks:73 passed. Audit failure/redaction checks:3 passed. Ruff passes across src/tests/scripts.
- [ ] Verify a new hosted seller summary, editable target and campaign. Requires approval for the specific bounded provider evaluation.
- [ ] Review observable target criteria and separate unsupported pain-point hypotheses.

## 3. Release build and rollout

- [x] Reconcile main's evidence-only commit with the design branch without losing either history. Merge3881fce retains both progress records; production main is unchanged. TypeScript/Vite production build passes.
- [x] Verify branch CI/build and prepare exact web/worker revision and rollback revision. All5 jobs passed for b5cec88 in [run38845013675](https://github.com/adkbbx/GTM_Shortlist/actions/runs/38845013675), including92 browser cases and container startup/restart smoke. Rollback48a7cdc.
- [x] Roll out the reviewed revision to both existing Render services and observe Live state. On16October12:28JST, web dep-db8pjfmq1p3s738ul500 became Live in32.5s; worker dep-db8pjeui0phs738ih3k0 in26.7s. Both source b5cec88. Exact-commit deploy disables auto-deployment on each service; main remains unchanged.
- [x] Check HTTPS, authenticated database access and worker freshness after rollout. At03:28:58UTC, read-only preflight passes. Browser reload serves the workshop UI, preserves the existing signed-in account/run and3 credits. Asset fingerprint comparison remains below.
- [x] Verify the progress-label correction in production.009d19d passed all5 CI jobs, including92 browser cases in [run38851232066](https://github.com/adkbbx/GTM_Shortlist/actions/runs/38851232066), and became Live on both services. Actual hosted reload shows "Offer summary unavailable" and an available stop action for the failed confirmation draft.

## 4. Real accounts

- [ ] Verify signup and actual confirmation email arriving at a user-controlled test mailbox.
- [ ] Verify confirmation redirect, sign-in, signout and session recovery.
- [ ] Verify password recovery email; user completes credential entry/change when required.
- [ ] Verify two real accounts cannot read/mutate each other's runs, exports or credits. Never disable email confirmation to pass this gate.

## 5. One complete hosted research journey

- [x] Agree a specific bounded live evaluation and record its search/model caps and seller before dispatch. On16October the human replied "Approve it" after the bounded-run request: one new hosted Eygentic run, up to3 companies, maximum4 search/8 model/21 fetch attempts and3 app credits. No allowance for a second run or increased caps. Initial start was rejected before creation because the historical run occupies the active slot; zero provider dispatch from that request.
- [ ] Seller entry → saved summary → explicit target/campaign confirmation → actual discovery/research.
- [ ] Inspect exact source passages, retrieval dates, unknowns and company identity.
- [ ] Save human review; download/open Excel and CSV; confirm evidence matches saved results.
- [ ] Verify holds, delivered-record charges and unused-credit returns against saved ledger.

## 6. Persistence and failure recovery

- [ ] Reload/reconnect during an approved run without duplicate provider dispatch or debit.
- [ ] Verify worker restart and saved checkpoint recovery; avoid disrupting another active run.
- [ ] Verify stop and partial-result/credit handling within the approved evaluation budget.
- [ ] Reopen saved review/export after restart.
- [ ] Exercise real hosted phone/laptop, keyboard and reduced-motion flows; inspect screenshots.

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

## Rollout plan

Use the tested release-branch application tree for both existing Render services. Rollback revision is the currently Live `48a7cdc3b6263a184e58bba8e94d2ed7d6b785fc`. No new service, compute upgrade, provider change or migration is required by the design changes. Render currently follows main with automatic deployment enabled. Do not push a main merge casually: it is a production action. Observe full release-branch CI before rollout, then check actual deployed revisions, asset paths, fresh worker heartbeat and preserved account/run/credits. An existing session does not establish a fresh signup or recovery flow.

After the12:28JST exact-commit rollout, both services remain configured for main but auto-deployment is disabled by Render. Future pushes do not deploy automatically until an operator deliberately reenables that setting. The rollback target48a7cdc remains available; the currently Live release is b5cec88 pending the narrow progress-label correction above.

Community review: [Oyinkansola Yahaya's Supabase confirmation debugging report](https://dev.to/kansoldev/fixing-an-email-confirmation-problem-in-supabase-4560) describes a missing UPDATE policy that made saved email status misleading. The article has no comments. We use this as a reminder to inspect each real account operation; its permissive waitlist policy is unsuitable for this app and is not applied.
