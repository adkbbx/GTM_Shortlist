# Product targets, review progress, and existing-account signup

18 October 2026. Offline verification report. No provider calls, saved-evidence edits, commits, or deployments.

## Root causes and changes

- **Product targets.** Admission checked page identity but did not distinguish software vendors from businesses selling services to them. Draft recovery allowed the defining software category to remain optional. [relevance.py:242](../src/shortlist/relevance.py#L242) identifies product targets and explicit service identities in titles or introductory descriptions. [providers.py:328](../src/shortlist/providers.py#L328) deterministically requires the defining product check, or proposes one when missing. The drafting prompt also states this requirement. Service-provider targets remain eligible.
- **Replay policy.** [store.py:31](../src/shortlist/store.py#L31) assigns discovery policy 4 to new confirmations. New seller jobs carry seller_draft_policy 4. [worker.py:238](../src/shortlist/worker.py#L238) journals the new drafting input only for that policy, proposes the editable services exclusion, filters discovery candidates before selection, and checks fetched primary-page identity before inference. Earlier policies keep their recorded behavior. [api.py:363](../src/shortlist/api.py#L363) applies the saved drafting policy when recovering a failed draft.
- **Review progress.** The stored review checkpoint stayed waiting, and the frontend treated the current review stage as incomplete regardless of saved decisions. [progress.py:55](../src/shortlist/progress.py#L55) projects partial and completed review counts without changing stored events or research. [research-stages.ts:21](../web/research-stages.ts#L21), [ResearchProgress.tsx:32](../web/ResearchProgress.tsx#L32), and [StatusMark.tsx:31](../web/StatusMark.tsx#L31) show those counts and the completion mark. Invalid historical sources do not count. Human decisions remain separate from qualification.
- **Existing-account signup.** Any successful signUp response previously enabled the confirmation-email screen. [AuthGate.tsx:56](../web/AuthGate.tsx#L56) detects an empty identities array and displays the requested existing-account message. The existing sign-in action preserves the email and clears the password. An unconfirmed signup with an identity still gets the confirmation message.

## Measured admission and discovery

[scripts/measure_product_admission.py](../scripts/measure_product_admission.py) compares policies 3 and 4. Regression tests cover labelled drafts, service-target exceptions, product identities, required checks, exclusion proposals, immutable review history, read-only SQLite access, duplicate databases, and mixed-query checkpoints.

| Saved evaluation | Policy 3 | Policy 4 |
| --- | ---: | ---: |
| All labelled entries reaching research | 25 | 23 |
| Annotated service providers reaching research | 2 | 0 |
| Annotated product companies reaching research | 8 | 8 |
| Annotated product companies lost | 0 | 0 |
| Unique saved candidates across supplied databases | 33 | 33 |
| Service descriptions admitted in those saved candidates | 0 | 0 |

The two service entries are Widelly and the owner-reported Mike Sonders result. These measurements establish admission behavior on this evidence, not live discovery quality or complete classifier coverage.

The saved generic Eygentic target has two query groups:

- The official-website query saves 12 candidates. Admission refuses seven article or directory pages, three non-company sites, and two editorial pages. Admitted: 0 before, 0 after.
- The platform-pricing query saves nine candidates. Admission refuses three article or directory pages and six editorial pages. Admitted: 0 before, 0 after.

The shorter saved target has six candidates in each main query, all admitted before and after. Those searches use a different confirmed target, so they are not a controlled query comparison. The current planner already compacts generic targets. No additional query change is justified by saved alternatives for the same generic target. The reported one-company hosted run is absent from the supplied SQLite evidence. Mike Sonders is covered by the separately identified UI report.

Search journals can contain already-filtered candidates. The counts above describe saved evidence only. Checkpoint fallback candidates are grouped by their actual query. Duplicate runs, searches, and candidate observations are deduplicated by the measurement script.

Reproduction uses PYTHONPATH=src and .venv/Scripts/python.exe:

- scripts/measure_product_admission.py with ../../../data/shortlist.sqlite3 and the SQLite files under the supplied job evidence directory, including its compact and codex subdirectories.
- scripts/evaluate_discovery.py passes its existing policy-3 baseline: 21 of 21 company pages reach research, with zero fetched pages subsequently rejected.
- scripts/replay_saved_runs.py runs successfully on those databases in read-only mode. Its aggregate includes overlapping database copies and qualification-advice counterfactuals. Those totals are not used as the deduplicated admission measurement above.

The complete measurement output is saved in .impeccable/review/product-admission-measurement.json.

## Evaluation-entry audit

No existing URL, title, search provenance, or label changed in examples/evaluation/discovery-admission.json.

Added target_company=true to these existing entries to measure product identities represented by their saved titles:

- https://prismatic.io/
- https://b2bhub.ltd/
- https://tandemworks.ai/
- https://siesta.ai/
- https://freshify.io/pricing
- https://www.happyfox.com/crm/pricing/
- https://www.paloaltonetworks.com/
- https://www.salesforce.com/sales/partner-relationship-management/software

Added service_provider=true to https://widelly.com/revenue-operations/gtm-operations. Its saved title explicitly describes GTM operations services. Its original company label remains unchanged because a services firm is still a company.

Added one new entry: https://mikesonders.com/, title "Mike Sonders | Digital Marketing Consultant", search=reported_ui, label=service_provider, service_provider=true, and the target supplied in the brief. Its note identifies the product-owner UI report as the source. No page passage or provider result was invented.

The corpus note now explains the UI provenance and annotation limits. counts.service_provider=1 accounts for the one new primary label. The tentative annotations on the generic CAAC Go and Runwork pricing titles were removed during self-review because those titles alone do not describe a product identity. Their original entries and labels remain unchanged.

## Verification

The requested gate is green with only the permitted sandbox credential exceptions.

- Ruff prints All checks passed!.
- Full backend pytest: 736 passed, 48 skipped, 11 failed. Every failure is a sandbox DPAPI case listed below. The reviewer independently measured 743 passed and 48 skipped before the four additional tests in this resume.
- Schema export and openapi-typescript generation pass. git diff --exit-code -- web/generated returns 0.
- TypeScript tsc --noEmit and Vite production build pass. These are the installed CLIs used by npm run build. npm is absent from PATH, so the accessible Node runtime runs those CLIs directly. Vite reports the existing large-chunk warning.
- The 10 focused browser checks pass on phone and laptop after the fixture and keyboard corrections. The complete suite finishes with 153 passed, 3 intentional phone-project large-screen skips, and 4 sandbox native-credential failures. Both new flows pass in both projects.
- Inspected both existing-account screenshots and both partial-review and completed-review screenshots at 1366 x 900 and 390 x 844. The tests check overflow, keyboard focus, retained email, draft creation, and persistence after reload.

The permitted backend failures are:

- tests/test_local_credentials.py::test_actual_private_storage_roundtrip_and_separate_process
- tests/test_local_credentials.py::test_concurrent_replacement_is_complete_and_failed_write_keeps_old_key
- tests/test_local_credentials.py::test_corruption_fails_closed_and_dynamic_settings_never_mutate_original
- tests/test_local_credentials.py::test_local_key_boundary_never_echoes_or_overwrites_on_rejection
- tests/test_local_credentials.py::test_next_worker_run_loads_new_key_without_restarting_original_settings
- tests/test_local_credentials.py::test_corrupt_payload_keeps_startup_and_setup_available_without_provider_dispatch
- tests/test_local_credentials.py::test_real_process_death_recovers_the_last_committed_private_key[False]
- tests/test_local_credentials.py::test_real_process_death_recovers_the_last_committed_private_key[True]
- tests/test_local_model_setup.py::test_model_and_search_persist_independently_and_next_run_reads_replacement
- tests/test_local_model_setup.py::test_model_api_is_local_bounded_never_echoes_and_makes_no_network_request
- tests/test_local_model_setup.py::test_next_worker_uses_saved_model_and_failed_replacement_keeps_previous


The permitted browser failures occur on both laptop and phone:

- tests/ui/flow.spec.ts:34, local model status opens setup and explains the offline worker without dispatch. Native credential save returns 503.
- tests/ui/flow.spec.ts:404, local masked Tavily setup saves privately, recovers and clears browser input. The fixture cannot create its native encrypted key.

The normal command runner fails before launch. Checks run through the available Node runtime and child processes. For the final browser run, a temporary config retains the checked-in projects and tests while the synthetic server lifecycle is managed explicitly. The server uses a fresh temporary database. The server is stopped and the temporary config is deleted after the run.

The pre-existing debug.log contains Chromium GPU ReadPixels diagnostics, not application source or research evidence. It was locked while browser processes ran and was deleted after they closed. No logs are staged.

## Self-review and scope

Self-review covers the whole task diff against AGENTS.md. The contributor rules were re-read after the final documentation update. git diff --check passes. HEAD remains cf64dbf.

The diff preserves confirmed profiles, source snapshots, stored progress history, and independent human reviews. New research behavior is checkpoint-gated. The default exclusion goes through the existing editable confirmation and evidence-assessment path. Tests use labelled synthetic company facts and fake Supabase transports.

The new exclusion exposed two test assumptions. The confirmation test expected an absent exclusion field, and the synthetic model assessed exclusions by position. The corrected test checks the proposed value. The synthetic model now cites a separately labelled software-only passage for this exclusion. A regression test checks that exact saved passage. The review browser test uses Tab from the company input before Enter, then verifies keyboard focus, partial review, draft creation, completion, reload, and overflow at both viewports.

The reviewer-owned docs/planning/BACKLOG.md remains byte-for-byte unchanged. No commits were made. Hosted provider quality and actual email delivery remain unmeasured by these offline checks.

## Files changed

- examples/evaluation/discovery-admission.json
- scripts/evaluate_discovery.py
- scripts/measure_product_admission.py
- scripts/replay_saved_runs.py
- scripts/ui_test_providers.py
- src/shortlist/api.py
- src/shortlist/progress.py
- src/shortlist/providers.py
- src/shortlist/relevance.py
- src/shortlist/store.py
- src/shortlist/worker.py
- tests/test_discovery_policy.py
- tests/test_product_admission.py
- tests/test_review_progress.py
- tests/ui/auth.spec.ts
- tests/ui/flow.spec.ts
- tests/ui/review-progress.spec.ts
- web/AuthGate.tsx
- web/ResearchProgress.tsx
- web/StatusMark.tsx
- web/research-stages.ts
- docs/PROGRESS.md
- docs/target-review-signup-verification.md
