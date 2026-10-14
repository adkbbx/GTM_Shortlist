# PostgreSQL foundation

The adapter, migrations, verified-user API access, hosted worker selection and browser account flows are implemented. PostgreSQL 18.6 tests use restricted database roles; browser tests use the actual Supabase SDK with explicitly labelled transport fixtures. The existing local service remains in SQLite mode. Actual Supabase accounts/email delivery and deployment remain unverified.

Install the `hosted` extra or use the pinned repository requirements. Apply migrations with a dedicated operator credential:

```sh
python scripts/migrate_postgres.py
```

Set `SHORTLIST_MIGRATION_DATABASE_URL` in the operator environment. The script applies migrations in one transaction under an advisory lock and records each normalized file's SHA-256 checksum. Repeating the command is safe. Changing an applied migration is rejected; add a new numbered migration instead. Never supply migration credentials to the application.

Provision separate login credentials as members of `shortlist_api` and `shortlist_worker`. Login roles must not be superusers or have `BYPASSRLS`; the adapter rejects those privileges. The API login must not be a member of the worker role. The runtime roles do not own tables or have schema modification privileges.

The private `shortlist` schema must remain outside exposed PostgREST schemas. API transactions assume `shortlist_api` and set the verified workspace UUID with transaction-local configuration. Every tenant table enforces row security for reads and writes. Composite foreign keys prevent records, events and provider outcomes from linking to another workspace's run. A worker uses its separate role for cross-workspace scheduling and a workspace-scoped store when processing a run.

The shared search allowance uses an atomic security-definer counter with a fixed empty search path. Runtime accounts cannot read its private aggregate table. The counter is independent of workspace row visibility and remains charged after deleting research. Short mutating commands serialize under a database advisory lock; network/provider dispatch occurs outside that transaction.

## Repeatable checks

Set `SHORTLIST_TEST_PG_URL` to an isolated PostgreSQL operator connection, then run:

```sh
pytest -q tests/test_postgres.py
```

The fixture creates a uniquely named database, applies migrations twice, provisions restricted test login roles, and drops only the database it created. Use a disposable cluster: the login roles remain after tests. CI runs this module against its PostgreSQL service. Without the environment variable, the module explicitly skips; skipped checks do not establish database compatibility.

Database checks cover two synthetic workspaces, cross-workspace read/write rejection, role escalation rejection, operator credential rejection, concurrent claims and shared quota reservations, worker research/review/export with labelled providers, isolated source caching, saved progress events, replay without duplicate dispatch and stale lease fencing. They also exercise verified-user API scoping, worker-loop workspace selection, concurrent wallet reservations, atomic delivery debits and process-death recovery. Scheduler workers can enumerate workspaces; once assigned a workspace, their row policies restrict reads/writes and source reuse to that owner. Supabase responses are explicitly stubbed in these tests. They do not prove actual Supabase account signup, SMTP, hosted deployment or live payment processing. Those remain release checks.

## Hosted runtime configuration

Keep `SHORTLIST_MODE=local` for the existing trusted loopback service. To exercise the hosted API after provisioning the database and credentials, set these server environment variables:

| Variable | Value |
| --- | --- |
| `SHORTLIST_MODE` | `hosted` |
| `SHORTLIST_DATABASE_URL` | Restricted API login's PostgreSQL connection string |
| `SHORTLIST_WORKER_DATABASE_URL` | Separate restricted worker login's connection string |
| `SUPABASE_URL` | Your Supabase project's HTTPS origin |
| `SUPABASE_PUBLISHABLE_KEY` | Your project's public publishable key |
| `SHORTLIST_APP_URL` | Your app's HTTPS origin |

Launch the API with `uvicorn shortlist.api:app` behind the HTTPS ingress and the durable worker separately with `shortlist worker`. The local `shortlist serve` and direct research CLI commands reject hosted mode. Do not deploy this configuration publicly until the remaining release checks pass.

Protected research routes require `Authorization: Bearer <user-access-token>`. The API calls the configured Supabase `/auth/v1/user` endpoint over verified HTTPS for each request. It never trusts caller-selected workspace IDs or decoded JWT claims. Supabase verifies the token; the API requires a confirmed, non-anonymous, non-deleted, non-banned authenticated user and derives the personal workspace UUID from that user's ID. Auth errors return 401; unavailable/malformed provider responses return 503 without authorizing access. Requests use bounded response size, no redirects and a five-second transport timeout. No service-role key is required for verification.

Each personal workspace receives three signup credits once. Confirming a batch reserves 1–3; completed company research and its one-credit debit commit atomically. Technical failure records are uncharged, and terminal runs return unused holds. Idempotent requests cannot spend twice. Existing legacy demos are exempt, with no retroactive charge or second signup grant. Free automated seller profiling is capped separately at three drafts and one active run; paid operator grants permit ten profiles daily. Actual paid checkout, complete account deletion and retention remain unfinished. The public health route reports hosted worker availability as false before authentication; the authenticated run progress contains the actual shared worker heartbeat.

### Browser accounts and email setup

The public /api/auth/setup response distinguishes local access from hosted account configuration. It exposes only a publishable key and the trusted auth/redirect origins; secret/service-role keys are rejected at settings validation. New publishable keys must begin sb_publishable_. The SDK is loaded only in hosted mode. API calls and exports carry the active user access token in headers, never URL parameters. Sign-out removes the current workspace from the screen; API401 returns to sign-in and preserves server research. An old request's token cannot expire a newer account session.

In Supabase, enable email confirmation, configure external SMTP, and set the Site URL and allowed redirect URL to SHORTLIST_APP_URL plus the trailing slash. The browser uses PKCE signup/recovery links; open the email link in the browser that began the request. Cross-browser/device link completion remains an external-testing case; an email-code flow may be preferable if those tests show confusion. Do not disable confirmation to hide an email configuration failure. Sign-in, signup notices, reset request, PKCE password update, expired-token refresh, failed sign-out recovery and authenticated export are covered with labelled fixtures, not actual email or production accounts. Keep the two-real-account isolation check as a release gate.
