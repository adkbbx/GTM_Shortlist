# Evaluate discovery from a confirmed target

Use this command only after specific human approval for the live evaluation. The flag is a technical guard, not approval. Tests use labelled fixtures by default.

This evaluation reuses an already confirmed target and optional saved campaign context. It tests discovery, bounded activity-source selection and company research. It does not validate fresh seller profiling, market planning, hosted signup or real users.

1. Select a run with a confirmed profile in the local SQLite database.
2. Choose a separate, ignored evaluation database. Reuse that output database and request key when resuming.
3. After approval, run inside the project virtual environment:

```sh
python scripts/evaluate_shortlist.py --source-db data/shortlist.sqlite3 --source-run RUN_ID --output-db data/evaluations/confirmed-target.sqlite3 --request-key confirmed-target-review --allow-provider-calls
```

The runner reads provider settings from ignored `deploy/secrets/worker.env`. It opens the source database read-only and rejects the same file, including hard-link aliases. It freezes the original profile and campaign context; changed context under the same request key fails before provider work.

The separate evaluation database allows at most two search attempts across its runs, including failed or uncertain attempts. Each run retains the worker's eight-model and21-fetch caps. Activity pages add no search or inference calls. A failed model response can use repair attempts within the same cap, so three completed records are not guaranteed. Do not create another output database merely to bypass a cap.

The command prints only the evaluation run ID, state and attempt counts. Inspect the actual saved records, passages, dates, unknowns and journal before assessing quality. Replaying a finished evaluation makes no further provider calls. An uncertain dispatch remains stopped for inspection.

Use the local CLI with `SHORTLIST_DB` pointing at the evaluation database to inspect or export its saved run. Keep exports private when the confirmed offer contains confidential details. Never describe this saved-target replay as a hosted customer test or a fresh end-to-end seller investigation.
