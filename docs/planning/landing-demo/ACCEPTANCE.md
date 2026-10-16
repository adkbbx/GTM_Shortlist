# Scoped design acceptance — 16 October 2026

This record covers the local design branch, not full product quality or a hosted release. The user selected an engineering-workshop direction and authorized unattended design work through 17 October 2026,21:00 Asia/Tokyo. Keep the research core neutral for every seller.

## Reopened responsive defect — 16 October

The user supplied a concrete failure after the earlier acceptance: at731 CSS pixels, expanded navigation used mobile flex wrapping inside a224px desktop grid column. Workspace/New shortlist overlapped and wrapped flex lines distributed down the tall sidebar. Earlier fixed-viewport checks did not establish resize usability. The earlier acceptance is limited accordingly.

Correction: the workspace and sidebar now share the850px mode boundary. Desktop navigation explicitly owns column alignment; mobile navigation owns a two-column header grid and full-width history. The hero responds to its main content container instead of viewport width, stacking when sidebar space would squeeze the headline.

Verification: the new regression keeps the same mounted page, resizes through1366/1024/851/850/731/701/700/390/320 and back, and toggles both states at every width. It asserts top alignment, disjoint controls, history placement, usable input/heading width and page overflow. All eight sidebar cases passed across phone/laptop projects; the broader26 sidebar/workshop/demo cases also passed. Build, Ruff and40 focused backend checks passed. Actual preview inspection reproduced the original731px failure and checked corrected expanded731px,1024px,851px and390px states, plus phone collapse. Screenshots saved under `.impeccable/review/resize-fix-*`.

The first local test invocation accidentally resolved an editable installation from the main checkout through the shared virtualenv. It was discarded, then all eight cases passed with the correct source path. Playwright now pins both fixture servers to this checkout in configuration so this does not depend on shell environment.

Full CI for correction5b1d735: [run38830476549](https://github.com/adkbbx/GTM_Shortlist/actions/runs/38830476549) passed core, Postgres, Windows lifecycle, UI and container. The09:55 JST16 October scheduled check confirmed the ordinary reset and disabled its fired one-time continuation; the17 October21:00 cutoff remains active. No additional aesthetic changes were warranted by that check.

## Navigation interaction supersedes earlier chrome —16 October

Further user screenshots rejected the stacked dark mobile bars and full-width expanding history even after overlap was corrected. The current interaction replaces that layout: one56px light toolbar, native modal saved-run drawer at850px and below, complete desktop wordmark, and a quiet preview status line. Earlier screenshot acceptance does not apply to this replacement.

Verification includes actual790px tablet/390px phone/1366px laptop browser inspection,26 sidebar/demo/workshop cases, then eight final sidebar cases after adding explicit keyboard wrapping. Final tests cover Escape/Close/selection dismissal, focus return, background scroll restoration, drawer open during viewport change,11 viewport transitions, preserved company input, long history and no content displacement. Build, Ruff and40 backend checks passed. Full hosted CI for this new implementation remains pending after push; no deployment or live research is claimed.

## Connected frame and account tray —16 October

User feedback added three corrections: remove the20px bottom strip, make the chevron indicate the opening direction, and connect header/sidebar visually. A flex shell now allocates actual header height, keeps the footer at the bottom of short pages, and stretches desktop navigation to the same edge. Desktop chrome shares one dark surface before and after history loads.

The user then requested that email, balance, credit activity and sign-out move into a tray. They now live in one native Account popover, with history inside the tray. Delayed-wallet tests caught and corrected a separate mobile trigger shift when history appeared. The trigger geometry now stays unchanged while credits resolve; email wraps inside the panel. Escape, Close, outside click, focus return and sign-out are covered.

58 phone/laptop auth/sidebar/research-flow cases passed, plus build, Ruff and40 backend checks. Hosted credit-history coverage uses an isolated local Postgres and labelled transports; no real account/provider call is involved. Screenshot evidence includes laptop-account-tray.png, phone-account-tray.png and hosted credit-history cases under ignored `.impeccable/review/`. Local preview was restarted with its preserved database; live Render is unchanged. All16 hosted cases passed across the main14-case pass and two corrected navigation reruns. The disposable database is stopped; automatic review blocked file removal, so only its ignored fixture files remain. Details are recorded in PROGRESS.md.

## Reference and direction

Inspected [Eygentic](https://eygentic.com/) and [Explee](https://explee.com/) in the browser. Eygentic informs paper, orange, schematic linework and controlled mechanical motion; Explee informs one clear entry action and a visible distinction between automatic work and required input. No reference signup or research was submitted. These were browser observations, not REA Evidence or conversion measurements.

## Acceptance evidence

| Gate | Evidence | Result |
| --- | --- | --- |
| Focused entry | One company input/Start research; optional labelled synthetic walkthrough; input survives sample interactions | Passed browser regressions |
| Truthful activity | Real worker/checkpoint projection; offline stays waiting; human confirmation remains explicit | Passed fixture worker, stop and serialized-poll flows |
| Action clarity | Automatic versus Your turn cue; near-scene controls; confirmation and evidence have one main action | Passed phone/laptop walkthrough |
| Reduced motion | Manual Next without Resume; changing preference preserves stage; initial reduced-mode entry is a static example | Passed pure transitions and browser checks |
| Creative motion | SVG calibration plate plus WebGL scan; static fallback, manual pause, device preference, offscreen suspension | Passed rendering/fallback/offscreen checks |
| Readable navigation | Dark 224px rail, 64px collapse alignment, folded phone history, no 25-row compression,44px controls | Passed geometry/keyboard/history checks |
| Contrast | Computed Workspace 13.12:1; heading/metadata 7.23:1; run names 11.16:1 | Measured in actual preview |
| Human handoff | Saved progress collapsed; target form and company list/export lead; context stays inspectable | Passed actual API/worker fixture flows |
| Account handoff | Signup success removes credential form; resend/correct-email/sign-in remain; no merged mobile headline | Passed 16 auth scenarios plus focused correction checks |
| Preserved state | Unsaved draft/review edits survive switching companies; saved review/export/reload retained | Passed three-company and end-to-end checks |
| Small screens | 390px phone, 1366px laptop, 320px/200% text and keyboard; 734x687 preview demo fits initial viewport | Passed documented checks |
| Preview boundary | No provider setup/research submission; saved queued run preserved; real-workspace link | Passed backend guard and actual browser inspection |
| Full CI checkpoint |3b921b6: 419 core tests, 39 Postgres tests, Windows lifecycle, 88 browser cases, container smoke | All jobs passed in run 38801770446 |
| Final tablet correction | c48fa0e: left-aligned mobile header and compact preview spacing; four targeted browser cases pass | All jobs passed:90 browser cases, core, Postgres, Windows and container in run 38803090099 |

## Review and limits

The isolated Impeccable baseline scored 27/40 before correction. Its P1 manual-navigation issue and P2 control-placement/preview-handoff issues were corrected. The follow-up reviewer approved those source changes; its browser was unavailable, so live evidence is attributed to the parent and repeatable tests. The detector returned 87 advisories and no non-advisory findings; legacy overridden rules and token-frontmatter drift are documented, not 87 distinct visible defects. No mutable browser overlay is claimed.

No paid search/inference/enrichment evaluation, real signup/email send, production migration, main merge or Render deployment was performed in this pass. Core-platform/database skips are not counted as passes in the core CI job. Device viewport tests are not physical-phone/all-browser or assistive-technology certification. The full research product still has separate real-provider quality and hosted rollout gates.

The latest ignored visual proof is .impeccable/review/final-workshop-preview.jpg, with confirmation/results/account and near-scene-control captures alongside it. Port 8018 remains the isolated preview. Existing queued run 1618c3adbd16463a9d7557246d1dc9a2 is preserved with no provider dispatch from this task.

## Final verified checkpoint

Application commit: `c48fa0e`. [Full CI run38803090099](https://github.com/adkbbx/GTM_Shortlist/actions/runs/38803090099) passed every job, including90 browser scenarios. This closes the final tablet acceptance gate. The subsequent acceptance-record commit changes documentation only; it does not reopen the tested application tree.

The earlier scoped design implementation met the then-recorded fixed-viewport gates; the responsive defect and correction above supersede that usability conclusion. Preserve this ready preview while the authorized work window remains open. Act on new user feedback, a demonstrated regression or a failed check; do not manufacture additional aesthetic work to fill the time. Broader product quality and rollout remain separate from this result.

## Continuation

Resume 09:55 JST16 October after actual 09:54:18 allowance reset. Check final CI and act on a real failure or new user feedback; do not repeatedly restyle passed surfaces. The separate 21:00 JST17 October cutoff heartbeat stops work and saves a handoff. Never buy credits, consume reset credits or run paid provider evaluations without specific approval.

Community design reference: [Uriel Bitton on useful SaaS empty states](https://dev.to/urielbitton/saas-empty-states-help-a-new-user-finish-the-first-task-3fkb). Applied the one-useful-first-action and labelled-sample guidance; no conversion improvement is claimed.
