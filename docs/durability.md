# Worker recovery

The API and CLI queue confirmed immutable runs. A separate worker claims the oldest eligible run with a 180-second lease and a monotonic fence. Each checkpoint renews the lease. Replacement workers cannot be overwritten by stale workers, including when committing provider outcomes.

Before an external call, the worker atomically reserves an attempt under the per-run cap and global monthly search cap. Failed calls and unresolved dispatches count. Each operation has a stable name and an input hash, including the confirmed profile, supplied source snapshots and configured model where applicable. Changing inputs or provider stops replay and requires a new run.

Successful results and safe failure details are journaled in the same transaction as the attempt's final state. A restart returns saved candidates, sources, research or errors instead of calling the provider again. The saved source IDs, dates, and generated record IDs remain stable. Immutable record inserts preserve existing human review. Invalid model content is bounded and stays in operator-local storage; it is not part of normal research exports.

If a process dies before the provider result commits, the attempt remains `outcome_unknown`. The remote service might have charged for or completed it. The worker stops automatic redispatch and shows an error. This does not claim exactly-once HTTP execution. Inspect the provider and saved run before deciding whether to start a fresh run. A fresh run has its own allowance and does not overwrite prior evidence.

Run `python -m shortlist.cli worker` to process queued runs and recover abandoned running runs after their leases expire. `python -m shortlist.cli resume RUN_ID` attempts a claim of an eligible queued/abandoned running run; completed/partial runs are not automatically reopened. `python -m shortlist.cli show RUN_ID` inspects saved progress. Old pre-journal attempts can continue from saved stage checkpoints; if only a dispatch was saved, they stop conservatively.

Rerun `pytest -q tests/test_journal.py tests/test_model_repair.py tests/test_store.py` to verify recovery, caps and fencing. The subprocess fixtures intentionally exit abruptly after actual SQLite commits, but their external providers are labelled synthetic and make no network calls.

Extraction and independent entailment verification are separate journaled model operations sharing the eight-attempt cap. Verifier results are stored in the run checkpoint; the original extraction remains in the result journal. Missing judgments, verifier failures and exhausted verification budgets downgrade observations to unknown with their sources preserved. Corrupt saved verifier identities stop replay without another dispatch. A fourth subprocess interruption case now covers the verifier commit.

## Public page reuse

Fresh snapshots are reused across local runs by exact canonical requested URL and company domain. SHORTLIST_SOURCE_CACHE_HOURS defaults to 24, accepts 0–168, and 0 disables reuse. Reuse preserves the original ID, text/hash and retrieval date; it never claims the page was fetched again. The checkpoint records source_reuse metadata. A cache hit makes no fetch reservation and consumes no fetch attempt. Expired/future-dated snapshots are not reused. Stored snapshots are immutable and cache writes require the active worker fence. Corrupt cache values stop explicitly.

An existing fetch journal entry takes precedence over the cache, including unresolved attempts. Recovery therefore cannot use a fresh page from another run to hide an uncertain dispatch. Old snapshots remain in prior records; cache expiry does not rewrite evidence. The current cache stores successful public sources only, without cookies or credentials. Hosted retention and tenant policy remain release work.

## Network deadlines

DNS waits at most five seconds and also respects the remaining 35-second network-fetch budget. At most four system lookups may remain outstanding per process. A timed-out system lookup cannot be forcibly cancelled; its daemon thread holds its slot until resolution finishes. If all slots are occupied, later fetches fail explicitly rather than creating unbounded threads. Returning results still reject mixed/private addresses and pin one validated address with original-hostname TLS verification. TCP/TLS, request writing, response headers and body reads use the remaining budget. Parsing stays bounded by the existing one-megabyte input limit.

The Future wait timeout does not cancel running work; Python's [Future documentation](https://docs.python.org/3/library/concurrent.futures.html) describes this distinction. The cap therefore applies to outstanding resolver work, not just callers currently waiting. Tests deliberately stall DNS, prove deadlines/capacity and release it to verify recovery.
