# Broad-target guidance verification

18 October 2026. Baseline `34b6a92`, branch `claude/signal-landing`.

The gate passes with only the named sandbox-native credential exceptions below.

The confirmation accepted generic company categories without discovery advice. The review API projected progress and qualification, but omitted limited discovery coverage. The change adds an advisory backend rule and a read-only projection of saved checkpoint facts. Search planning, admission, profiles, sources, qualification and human decisions are unchanged.

Seven manually labelled confirmed targets were read using SQLite `mode=ro`, `uri=True`. Exact target text, source database filename, run ID and label rationale are in `examples/evaluation/target-breadth.json`. The offline checker agrees with all seven labels. This is a regression check, not a measured live discovery improvement.

| Saved target | Result |
| --- | --- |
| Generic acquisition audience | Broad |
| Private AI B2B SaaS startups | Specific |
| Mid-market channel partner networks | Specific |
| Seed to Series A SaaS with a launched product | Broad |
| Generic brands with acquisition intent | Broad |
| Sales and marketing operations buyer function | Specific |
| Channel partner programmes | Specific |

The low-yield note applies to finished confirmed runs with fewer records than their batch size and fewer saved unique candidates than that size. Counts of rejected content, service providers and previously researched companies appear only when saved. Provider-side filtered results have no saved count, so the UI does not count unseen articles. The advisory request and copying an offer dispatch no provider work. Existing hosted balance and active-run policy still applies to offer reuse.

Verification:

- Ruff prints `All checks passed!`.
- Full backend: 771 passed, 48 skipped, 11 named DPAPI/native credential failures. All 29 new backend checks pass.
- Python schema export and the installed schema CLI pass. A second export produces identical hashes. Comparing generated JSON with HEAD confirms that only the guidance endpoint, its two request/response schemas and nullable review explanation changed. The three intended generated files are listed below.
- Installed TypeScript and Vite CLIs pass, matching the package build script. npm is unavailable in PATH, so its schema and build scripts were executed through those installed CLIs. No tool download was attempted.
- Final full Playwright pass uses the standard configuration, a fresh synthetic fixture database and `--retries=1`: 161 passed, 3 intentional skips, 4 named native credential failures. No other failures or recovered flaky cases remain in this pass.
- All eight new phone/laptop checks pass. They cover nonblocking broad confirmation, live edits, direct keyboard focus and viewport visibility for the first saved campaign, zero/one-company review, overflow, and offer reuse with no attempts and no confirmed profile in the copied run.
- Inspected all six final screenshots in `.impeccable/review`: phone and laptop broad target, one-company review and empty review. Final native browser traces are retained under `test-results/target-guidance-final`.
- Earlier reused-fixture passes exhausted their synthetic search allowance. The final pass uses a fresh fixture database. After all tests finished, the session-owned fixture listener was stopped through its process handle because sandbox process-tree shutdown was unavailable. Playwright then reported the final result and exited with its four named failures.
- The recovery browser test excludes the read-only guidance POST from its command counter. It still compares the entire saved run before and after to prove immutability.

Named sandbox-only backend failures, rooted in DPAPI storage or its HTTP 503 response:

- `tests/test_local_credentials.py::test_actual_private_storage_roundtrip_and_separate_process`
- `tests/test_local_credentials.py::test_concurrent_replacement_is_complete_and_failed_write_keeps_old_key`
- `tests/test_local_credentials.py::test_corruption_fails_closed_and_dynamic_settings_never_mutate_original`
- `tests/test_local_credentials.py::test_local_key_boundary_never_echoes_or_overwrites_on_rejection`
- `tests/test_local_credentials.py::test_next_worker_run_loads_new_key_without_restarting_original_settings`
- `tests/test_local_credentials.py::test_corrupt_payload_keeps_startup_and_setup_available_without_provider_dispatch`
- `tests/test_local_credentials.py::test_real_process_death_recovers_the_last_committed_private_key[False]`
- `tests/test_local_credentials.py::test_real_process_death_recovers_the_last_committed_private_key[True]`
- `tests/test_local_model_setup.py::test_model_and_search_persist_independently_and_next_run_reads_replacement`
- `tests/test_local_model_setup.py::test_model_api_is_local_bounded_never_echoes_and_makes_no_network_request`
- `tests/test_local_model_setup.py::test_next_worker_uses_saved_model_and_failed_replacement_keeps_previous`

Named sandbox-only browser failures:

- `[laptop] tests/ui/flow.spec.ts:34 local model status opens setup and explains the offline worker without dispatch`
- `[laptop] tests/ui/flow.spec.ts:404 local masked Tavily setup saves privately, recovers and clears browser input`
- `[phone] tests/ui/flow.spec.ts:34 local model status opens setup and explains the offline worker without dispatch`
- `[phone] tests/ui/flow.spec.ts:404 local masked Tavily setup saves privately, recovers and clears browser input`

The model setup cases receive HTTP 503 when native encryption is unavailable. The Tavily cases cannot create their deliberately corrupted synthetic credential fixture because its initial DPAPI save fails. No real credentials or provider calls are involved.

The full diff was reviewed against AGENTS.md, which was re-read after the final changes. Temporary verification files and the GPU debug log were removed. The reviewer-owned backlog is unchanged. No provider calls, saved-evidence writes, commits, pushes, branch changes or deployments occurred. Remaining work is to run the named native credential checks in a normal user session.

Changed files:

- `src/shortlist/providers.py:159`
- `src/shortlist/progress.py:30`
- `src/shortlist/api.py:133`
- `web/api.ts:118`
- `web/main.tsx:58`
- `scripts/ui_test_server.py:136`
- `tests/ui/seller-recovery.spec.ts:10`
- `examples/evaluation/target-breadth.json:1`
- `scripts/check_target_breadth.py:1`
- `tests/test_target_guidance.py:1`
- `tests/ui/target-guidance.spec.ts:1`
- `web/generated/RunView.json:1658`
- `web/generated/openapi.json:8`
- `web/generated/api.d.ts:7`
- `docs/PROGRESS.md:3`
- `docs/target-guidance-verification.md:1`
