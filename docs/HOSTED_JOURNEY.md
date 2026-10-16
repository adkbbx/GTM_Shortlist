# Hosted journey release checklist

Started 16 October 2026 JST. Working branch: `codex/hosted-journey`, based on tested design checkpoint `55a4ec7`. This checklist tracks the seven release tasks separately from broader product scope in IMPLEMENTATION.md and agent-experience.md. Check an item only with observed evidence. Fixture success does not close a live gate.

## 1. Hosted environment audit

- [x] Inspect actual Render web and worker deployments. Both are Live at `48a7cdc3b6263a184e58bba8e94d2ed7d6b785fc`, tracking main. Actual auto-deployment is enabled; pushing main can deploy production.
- [x] Inspect the actual hosted signed-in workspace without starting research. Existing test account opens, shows 3 available credits and the saved historical Eygentic run awaiting confirmation. Preserve this account and run.
- [x] Run repeatable read-only HTTPS/auth/database/worker preflight and save dated output. At03:07 UTC16October: root/health/auth setup200, unauthenticated runs401, project/key/redirect match, signup enabled with email confirmation retained, all10 migration checksums match, TLS/restricted roles pass, one fresh heartbeat and only one awaiting-confirmation run. Private report: `deploy/secrets/evaluations/hosted-preflight.json`.
- [ ] Inspect Supabase email/redirect configuration and identify the actual SMTP gate. Dashboard is signed out; user login requested. Public settings cannot establish SMTP configuration/delivery.
- [ ] Reconcile code, deployment and saved evidence; list concrete release blockers.

## 2. Seller profiling

- [x] Recover previous live evaluation evidence. Main commit48a7cdc records one approved model request, named-function output and readable offer/target, with criteria strings corrected offline. This is a single-seller format check, not semantic targeting acceptance. The one-call approval was consumed.
- [x] Replay captured seller response against this branch and run relevant offline regressions. The actual saved response validates and exactly matches the previously saved derived draft, including3 criteria. No new provider call or journal mutation. Seller/auth/market/repair checks:73 passed. Audit failure/redaction checks:3 passed. Ruff passes across src/tests/scripts.
- [ ] Verify a new hosted seller summary, editable target and campaign. Requires approval for the specific bounded provider evaluation.
- [ ] Review observable target criteria and separate unsupported pain-point hypotheses.

## 3. Release build and rollout

- [x] Reconcile main's evidence-only commit with the design branch without losing either history. Merge3881fce retains both progress records; production main is unchanged. TypeScript/Vite production build passes.
- [ ] Verify branch CI/build and prepare exact web/worker revision and rollback revision.
- [ ] Roll out the reviewed revision to both existing Render services and observe Live state.
- [ ] Check served assets, HTTPS, authenticated database access and worker freshness after rollout.

## 4. Real accounts

- [ ] Verify signup and actual confirmation email arriving at a user-controlled test mailbox.
- [ ] Verify confirmation redirect, sign-in, signout and session recovery.
- [ ] Verify password recovery email; user completes credential entry/change when required.
- [ ] Verify two real accounts cannot read/mutate each other's runs, exports or credits. Never disable email confirmation to pass this gate.

## 5. One complete hosted research journey

- [ ] Agree a specific bounded live evaluation and record its search/model caps and seller before dispatch.
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

Re-run preflight with `.venv/Scripts/python.exe scripts/audit_hosted.py`. It performs read-only HTTP requests and TLS database queries, and never dispatches research, sends email or mutates account/billing state. Its output does not prove real signup, email delivery, provider quality, account isolation or successful research.

## Rollout plan

Use the tested release-branch application tree for both existing Render services. Rollback revision is the currently Live `48a7cdc3b6263a184e58bba8e94d2ed7d6b785fc`. No new service, compute upgrade, provider change or migration is required by the design changes. Render currently follows main with automatic deployment enabled. Do not push a main merge casually: it is a production action. Observe full release-branch CI before rollout, then check actual deployed revisions, asset paths, fresh worker heartbeat and preserved account/run/credits. An existing session does not establish a fresh signup or recovery flow.

Community review: [Oyinkansola Yahaya's Supabase confirmation debugging report](https://dev.to/kansoldev/fixing-an-email-confirmation-problem-in-supabase-4560) describes a missing UPDATE policy that made saved email status misleading. The article has no comments. We use this as a reminder to inspect each real account operation; its permissive waitlist policy is unsuitable for this app and is not applied.
