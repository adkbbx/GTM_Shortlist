# Worker recovery

The API and CLI queue confirmed immutable runs. A separate worker claims the oldest eligible run with a 180-second lease and a monotonic fence. Each checkpoint renews the lease. Replacement workers cannot be overwritten by stale workers, including when committing provider outcomes.

Before an external call, the worker atomically reserves an attempt under the per-run cap and global monthly search cap. Failed calls and unresolved dispatches count. Each operation has a stable name and an input hash, including the confirmed profile, supplied source snapshots and configured model where applicable. Changing inputs or provider stops replay and requires a new run.

Successful results and safe failure details are journaled in the same transaction as the attempt's final state. A restart returns saved candidates, sources, research or errors instead of calling the provider again. The saved source IDs, dates, and generated record IDs remain stable. Immutable record inserts preserve existing human review. Invalid model content is bounded and stays in operator-local storage; it is not part of normal research exports.

If a process dies before the provider result commits, the attempt remains `outcome_unknown`. The remote service might have charged for or completed it. The worker stops automatic redispatch and shows an error. This does not claim exactly-once HTTP execution. Inspect the provider and saved run before deciding whether to start a fresh run. A fresh run has its own allowance and does not overwrite prior evidence.

Run `python -m shortlist.cli worker` to process queued runs and recover abandoned running runs after their leases expire. `python -m shortlist.cli resume RUN_ID` attempts a claim of an eligible queued/abandoned running run; completed/partial runs are not automatically reopened. `python -m shortlist.cli show RUN_ID` inspects saved progress. Old pre-journal attempts can continue from saved stage checkpoints; if only a dispatch was saved, they stop conservatively.

Rerun `pytest -q tests/test_journal.py tests/test_model_repair.py tests/test_store.py` to verify recovery, caps and fencing. The subprocess fixtures intentionally exit abruptly after actual SQLite commits, but their external providers are labelled synthetic and make no network calls.

Extraction and independent entailment verification are separate journaled model operations sharing the eight-attempt cap. Verifier results are stored in the run checkpoint; the original extraction remains in the result journal. Missing judgments, verifier failures and exhausted verification budgets downgrade observations to unknown with their sources preserved. Corrupt saved verifier identities stop replay without another dispatch. A fourth subprocess interruption case now covers the verifier commit.
