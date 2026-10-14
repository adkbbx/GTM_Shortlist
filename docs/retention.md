# Research deletion and retention

Status: research deletion, repeatable operator retention and bounded managed account closure are implemented. Customer self-service, observed real Supabase identity removal, published retention terms and backup rotation remain release gates.

## What deletion does

The user can delete finished or confirmation-stage research after an explicit confirmation. Queued/running work rejects deletion: it must finish before its outputs can be erased safely. Deletion is idempotent and uses the verified workspace boundary. Other accounts are unaffected.

One transaction removes company sheets, customer review notes, independent operator annotation history and progress events; clears the seller profile, checkpoint, diagnostic error and provider-response payloads; and invalidates that workspace's source cache. In local mode the single-operator cache is cleared. Saved research in other runs stays intact; its optional reusable cache may need to be fetched again.

A content-free run tombstone and request identity remain so a replay cannot recreate deleted research. Provider attempt counts, kinds, provider names, timestamps and outcome states remain to enforce spending limits. Operation URLs and result request hashes are removed. The hosted signup decision, credit ledger and settled reservation remain: deleting research neither refunds delivered work nor issues a new free grant. These records are not exposed as research or exportable company sheets.

Deleted runs disappear from lists, reads and exports. Confirmation cannot restart them. Clearing an account's cache cannot change another account's cache. Real Postgres checks cover these boundaries and credit preservation; phone/laptop checks cover cancellation of confirmation, error/retry and persisted deletion.

## Operator retention

Preview inactive research older than an explicit number of days:

```sh
shortlist retention --older-than-days 30
```

Erase those eligible records with:

```sh
shortlist retention --older-than-days 30 --apply
```

The value is operator-selected, not a currently advertised 30-day customer policy. The command processes at most100 records, oldest first; repeat until empty. It only selects finished or confirmation-stage runs by their last pipeline update. Active queued/running work is never eligible. Preview is the default and changes nothing. In hosted mode a separate worker credential enumerates candidates, then each deletion runs under its assigned workspace scope. It uses the same transaction and tombstones as customer deletion. It never resets credits or provider allowances. Concurrent confirmation may reject deletion; inspect and rerun rather than cancelling active work silently.

No recurring retention job is enabled on the current development database. Choose and publish customer retention terms before scheduling this command in production. Recent viewing alone does not extend the pipeline timestamp; distinguish this from a last-login or last-view policy.

## Storage and account boundaries

Deletion removes content from application access. Database free pages, PostgreSQL old row versions, SQLite WAL, logs and backups require a separate storage/backup lifecycle. Do not claim immediate forensic erasure or backup removal. Production configuration must define backup expiration, restoration handling, logging redaction and a tested deletion replay after restore.

Research deletion is not account deletion. The new managed operator command freezes the exact workspace, rejects active jobs, erases at most100 inactive runs per call and removes the Supabase identity only after research is erased. It uses a dedicated server-only admin secret and persistent closing/closed state; ambiguous provider outcomes stay unconfirmed and retryable. API reads and mutation locks reject closing/closed accounts even if an old token is still accepted remotely. A closed user UUID cannot recreate its signup grant. See account-closure.md for the command and precise retained fields.

Operator procedures must reconcile wallet/payment obligations before running closure; this command does not issue refunds. The credit ledger and its business identifiers remain under the current spending policy. Matching a new Auth UUID to a previous person is not implemented. Customer self-service, an actual Supabase deletion/session test, explicit retention/anti-abuse terms and backup expiration/replay remain unfinished, as do actual SMTP/two-account and external-user checks.
