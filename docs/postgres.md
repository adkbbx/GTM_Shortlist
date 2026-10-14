# PostgreSQL foundation

The adapter and migrations are implemented and tested against PostgreSQL 18.6. The public API and worker still use local SQLite; hosted account wiring is the next step. This is not a deployed hosted service.

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

The six checks cover two synthetic workspaces, cross-workspace read/write rejection, role escalation rejection, operator credential rejection, concurrent claims and shared quota reservations, worker research/review/export with labelled providers, isolated source caching, saved progress events, replay without duplicate dispatch and stale lease fencing. They do not prove actual Supabase account signup, SMTP, hosted deployment or PostgreSQL process-death recovery. Those remain release checks.
