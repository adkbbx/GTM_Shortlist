# Reader readiness, 18 October 2026

Baseline: branch `claude/signal-landing`, HEAD `18081e3df509e951ed653c03b2d858bcbea563ff`. No commits, publishing, provider requests or saved-database edits are authorized for this work.

## Audit

AS-IS line numbers refer to the baseline README unless another file is named.

| Priority / requirement | AS-IS | TO-BE | Status |
|---|---|---|---|
| P0 / R1 | README:25-34 creates a venv but uses unqualified Python and assumes activation. No clone command or Node prerequisite. UI build is separated at :53-59. | One complete source path, explicit Python executable and UI build, with Windows and POSIX commands. Clone the branch containing this implementation. | Fixed in README. Fresh external installation remains unverified under the no-fetch rule. |
| P0 / R1 | README:11-19 leads with a package whose publication is an open gate in LOW_FRICTION_PATHS.md. | Usable source route first; package instructions explicitly conditional on publication. | Documentation fixed. Package publication needs user. |
| P1 / R2 | Sample instructions are below contributor/provider commands at README:61. UI says what the product does, but at 390 × 844 the sample action sits below both provider steps, outside the initial viewport. | Key-free sample route before provider setup, with confirmation, evidence, review and export explained. | Fixed in README and web/main.tsx: sample action precedes provider steps. Regression requires the entire action in the initial viewport on phone and laptop; sample regression strengthened for keyboard start/confirmation, persisted acceptance and accepted-only CSV. |
| P1 / R3 | README:34 does not clearly explain that real research needs both provider categories. UI has Tavily-only key entry, while configuration also supports SerpApi. | Explain both requirements, Settings paths, exact SerpApi environment settings, restart and saved-Tavily precedence. | Fixed in README. Model guide and error recovery exercised with labelled transports. No real model access or key validation claimed. |
| P1 / R3 | Native credential save cannot operate in this sandbox's current-user protection context. | Confirm search/model save and reload through real Windows protection outside the sandbox. | Needs user verification. Production encryption remains intact. Exact failed checks below. |
| P1 / R4 | Evidence, links, review and three export formats exist, but the sample browser test only downloads CSV without checking review persistence or contents. | Prove that a sample acceptance survives reload and the accepted-only download contains one labelled reviewed company. | Regression added in tests/ui/sample-data.spec.ts. Existing full flow checks actual evidence links and CSV/JSON/Excel downloads. |
| P1 / R5 | README:34 calls the monthly cap global without stating database scope. Privacy details are scattered, and the main limit paragraph omits remote model inputs. | State database-local cap, provider-account allowance, possible costs, storage locations, permissions and outbound research data. | Fixed in README. No current provider prices claimed. |
| P1 / R6 | MIT licence exists. No CONTRIBUTING.md or SECURITY.md; README does not link a security route or actual workflow results. | Short contributing note, security report route, licence and CI links. | Files and links added. General mailbox monitoring and remote CI status need user verification. No response-time promise. |
| P1 / R7 | README does not explain the 18 October qualification changes. | Describe found-page evidence, hedged claims, quote diagnostics, bounded verification follow-up and excerpt recovery, with measured limits. | Fixed using only the top PROGRESS section. Comparison is explicitly not a controlled accuracy benchmark; the remaining menus-run unknown is retained. |
| P2 / R1 | The one-command path depends on a published package. | No Node/build requirement for package readers. | Deferred until user publishes and verifies the package. Source path remains available. |
| P2 / R3 | Hosted external account, email and deployment checks remain open in IMPLEMENTATION.md. | A verified hosted signup-to-export path. | Needs user. Local readiness does not imply hosted readiness. |

## Verification

The gate is not green. Native credential protection cannot complete in this sandbox, and external installation/package/CI checks need network access or user release actions.

| Gate | Measured result |
|---|---|
| Ruff | `All checks passed!` from `.venv/Scripts/python.exe -m ruff check .`. |
| Full backend | Reviewer, normal Windows session: 713 passed, 48 skipped, 0 failed. (In the audit sandbox, 11 native DPAPI cases could not run.) |
| TypeScript and UI build | `tsc --noEmit` and `vite build` pass after the UI reorder. Existing bundle-size warning remains. npm itself is unavailable in PATH. |
| Full Playwright | Reviewer, normal Windows session, after the sample-row move: 153 passed, 3 intentional phone-project large-screen skips, 0 failed. (In the audit sandbox, the 2 native credential scenarios failed on both projects because DPAPI was unavailable.) |
| Final affected UI checks | Twenty model, settings, Brandfetch and modal checks passed after the reorder. Both corrected sample checks then passed: 2 passed in 27.8s. Thus all 22 affected checks pass across those runs; the full suite was not repeated after this single-row move. |
| Source launcher | Passed in a temporary database with both provider types absent: API, online worker, built UI, sample creation, confirmation, three records and labelled JSON export. Browser-open URL checked using a stub. |
| Reader-document links | 30 local links in README, CONTRIBUTING and SECURITY pass `scripts/check_readme.py`; no remote page fetched. Check added to CI. |
| README commands | Every retained command is accounted for below. Fresh downloads and package install are unverified, with exact environment limitations. |
| Full diff | Reviewed all tracked diffs and new source/document files after the final update; whitespace checked with git diff --check. |

Full backend failures, all in the explicitly allowed native-credential groups:

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

Full Playwright failures, each on laptop and phone:

- `tests/ui/flow.spec.ts:34`, “local model status opens setup and explains the offline worker without dispatch”: model save returns HTTP 503 instead of 200.
- `tests/ui/flow.spec.ts:404`, “local masked Tavily setup saves privately, recovers and clears browser input”: the corrupt-provider fixture cannot create its initial native-protected key.

These failures are consistent with the backend `_dpapi` failures. Production protection was neither weakened nor replaced by a test-only success. Repeat in a normal OS-user session before claiming provider setup verified. PostgreSQL jobs were not configured locally; their checks are among the backend skips. Hosted credit browser projects require the separate Postgres fixture environment and were not instantiated.

The first focused post-reorder run passed 20 checks and failed the two new sample CSV assertions because the expectation used lowercase “accepted” while customer exports correctly use “Accepted”. The assertion was corrected to the actual CSV decision cell. The final sample rerun is recorded above.

Screenshots at 1366 × 900 and 390 × 844 were inspected for setup, results and evidence. Final reordered setup and accepted-review screenshots were also inspected: sample entry is fully visible without scrolling, with no horizontal overflow. Existing 320px/200% text, keyboard and modal tests ran. Sample start, target confirmation, company reopening and acceptance now use keyboard actions; overflow is asserted at each captured sample stage.

Evidence logs and the isolated launcher check are under `.impeccable/review/readiness/`; screenshots are under `.impeccable/review/`.

The shell runner could not create a process: `helper_unknown_error: setup refresh had errors`. Local commands instead ran through the local JavaScript runtime and child processes. Python execution used `.venv/Scripts/python.exe` with `PYTHONPATH=src`.

The checkout's `.venv` resolves to the parent repository's existing environment. No new editable install or venv reinitialization was performed there. The dependency command reported every pinned dependency already satisfied with `PIP_NO_INDEX=1` and version checks disabled.

## README command audit

| Commands retained | Execution or exact limitation |
|---|---|
| `git clone --branch claude/signal-landing https://github.com/adkbbx/GTM_Shortlist.git`, `cd GTM_Shortlist` | Network clone forbidden by the no-fetch rule. Working directory, branch, HEAD and cached remote branch verified locally. The reader-facing changes are uncommitted and must be made public by the user. |
| `py -m venv .venv` | This sandbox's launcher reports `No installed Python found!`. Project Python works. Existing .venv is a junction to the parent environment, so recreating it would touch outside this worktree. Not executed against it. |
| Windows `pip install -r requirements.lock.txt` | Executed with indexes and version checks disabled. Passed; all dependencies already satisfied. This is not proof of fresh downloads. |
| Windows `pip install -e . --no-deps` | Not run against the shared environment. Setuptools is absent, and build isolation would need a forbidden download. |
| `npm ci`, `npm run build` | npm is absent from PATH. Direct invocation of installed TypeScript and Vite CLIs passed. Fresh dependency installation is unverified; no registry requests were made. |
| Windows `python -m shortlist.cli serve --port 8014 --open` | Module executed through a bootstrap with the same arguments, PYTHONPATH=src and an isolated temporary database. Browser-open function was stubbed and its loopback URL observed. API, worker, UI, sample confirmation, three records and labelled JSON export passed. |
| POSIX `python3 -m venv` and `.venv/bin/python` install/serve commands | Windows checkout has no POSIX Python environment. Not executable here. Commands match the repository's POSIX CI layout; fresh macOS/Linux installation remains to verify. |
| `uvx gtm-shortlist`, `pipx run gtm-shortlist` | Would fetch from a registry and depend on release publication. Not run. User must verify after publishing. |
| Inline `shortlist serve` | Same supervisor tested by the isolated source-launcher smoke and backend lifecycle tests. |
| Inline `python scripts/landing_demo_preview.py` | Port 8018 is already occupied by the existing preview. It was not restarted. Script arguments inspected; preview UI also exercised by existing browser transport fixtures. |
| Inline `node --experimental-strip-types scripts/check_landing_demo.mjs` | Executed using installed Node by absolute path. Passed all playback scenarios. |

## Needs the user

1. Review these uncommitted changes and make the intended source revision public through the chosen merge/release process. This work performed no commit, push or branch change.
2. On an ordinary Windows session with working current-user encryption, rerun the named native credential tests and full browser suite. Confirm saving and reloading both provider settings.
3. Verify clean source installs on Windows, macOS and Linux with network dependency installation available. Run the README commands as printed. No fresh-machine success is claimed here.
4. Check the linked Checks and Package workflows on the revision readers will receive, including Postgres and package jobs. No remote CI status was fetched.
5. If the package is not already published, configure the PyPI trusted publisher for project `gtm-shortlist`, workflow `package.yml`, environment `pypi`, and the matching GitHub environment. Publish the reviewed release through the tag workflow, then verify both uvx and pipx installs. These are instructions only; nothing was published.
6. Confirm that hello@eygentic.com is monitored for security reports or replace it with the intended private contact before making this revision public.
7. To offer hosted access, complete the real account/email/deployment gates in IMPLEMENTATION.md and HOSTED_JOURNEY.md. Enabling anonymous drafts additionally requires migration 011, Turnstile configuration and explicit operator switches.
8. Supply your own provider setup and separately authorize a bounded live evaluation if one is wanted. This report does not prove current provider acceptance or general research quality.
9. Record any demo and choose the final post wording yourself. Describe sample companies as invented, and distinguish local availability from hosted/package release status.

## Changed files

- README.md: reader setup, sample route, provider requirements, privacy, limits, measured qualification changes and project links.
- web/main.tsx: existing sample action moved before provider steps.
- .github/workflows/checks.yml: local reader-document link check in the core CI job.
- CONTRIBUTING.md: short contributor workflow and required checks.
- SECURITY.md: private security report route and storage/deployment boundaries.
- scripts/check_readme.py: repeatable local link check and README command inventory, with no network access.
- tests/ui/sample-data.spec.ts: keyboard entry/confirmation, persisted acceptance and labelled accepted-only CSV.
- docs/READER_READINESS.md: audit, verification and handoff.
- docs/PROGRESS.md: milestone evidence and exact unfinished work.

## Self-review

The complete diff and new files were read after the final update. The only product-code change moves an existing sample action before provider steps. Confirmed profiles, saved sources, provider dispatch, credential protection and human-review semantics are unchanged. Tests retain explicit sample labels. New prose contains no em dashes or generated-content attribution. Native credential failures and unavailable fresh-install/remote checks remain explicit. No provider, deployment, publication, user test or payment claim is inferred from fixtures.
