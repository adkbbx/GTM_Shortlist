# Assessment A: shell, entry and walkthrough

Method: isolated design review by `/root/design_assessment_a`, completed without detector output.

Target: `web/main.tsx` and its shell, entry, optional sample and progress presentation. Reviewed `ResearchSidebar.tsx/css`, `WorkshopField.tsx/css`, `LandingDemo.tsx/css`, `ResearchProgress.tsx/css`, `ResearchActivity.tsx`, `landing-demo.data.ts`, `styles.css`, `DESIGN.md`, `PRODUCT.md` and `AGENTS.md`.

Evidence: inspected actual screenshots at `http://127.0.0.1:8018/` in a fresh browser 2 tab. Walked automatic offer and market playback, target confirmation, discovery, evidence reveal, review, reduced motion, Replay, Next, Resume and the real-task handoff. The observed viewport was approximately 1264 by 712. Did not resize it. The tab was closed. No research worker, provider requests, saved-run changes or detector were initiated. Live research states were reviewed in source only. Mobile and assistive-technology behavior were not exercised in this assessment.

## Design specificity verdict

The result is recognizably a source-based company-research workspace. The evidence-before-decision sequence, explicit unknowns, human acceptance and synthetic sample all express this product's actual position. The warm paper, Schibsted Grotesk, restrained rust-orange and mechanical linework form a coherent Eygentic engineering-workshop direction.

The entry is less specific than the workflow. Its calibration plate is carefully drawn but has no visible relationship to company fit or evidence. Its continuous shader sweep establishes atmosphere, while the walkthrough's source-to-analysis-to-sheet illustration explains an operation. The latter is the stronger design idea. Preserve the visual restraint and develop that shared visual vocabulary; adding a larger shader would not solve the remaining usability problems.

The dark history rail and broad rounded walkthrough sheet are conventional app structures, but their use is defensible in an operational workspace. The design does not need an unfamiliar navigation pattern to be distinctive. Its best opportunity is to make the evidence journey feel authored and consistently understandable at every playback speed and scroll position.

## Overall impression

Professional and calm, with unusually honest product language. The normal demo now makes automatic work versus required clicks explicit. The largest weakness is the reduced-motion playback contract, followed by a presentation that advances text faster than a reader can inspect the taller scenes. The preview also invites a real-task handoff that cannot succeed in that environment.

## Nielsen heuristics

Scores use 0 for absent and 4 for excellent. Mode is Operate with an optional guided introduction, so all ten apply. This is a scoped design assessment, not a claim of full product validation.

| # | Heuristic | Score | Evidence and limitation |
|---|---|---:|---|
| 1 | Visibility of system status | 3 | Inline "Demo playing" and "Your turn" cues are explicit. Current step and a second footer status are available. Scroll position can hide the top cue, and reduced mode contradicts its own Resume instruction. |
| 2 | Match between system and real world | 3 | Company, target, evidence and review follow a natural sequence. "Campaign hypothesis" and "first value" add some specialist translation work. |
| 3 | User control and freedom | 3 | Close, Previous, direct stage navigation, Pause and reduced motion exist. Resume in reduced mode fails to continue and can reset the selected stage. |
| 4 | Consistency and standards | 2 | Visual controls are coherent, but the same Resume label has incompatible outcomes by motion preference. Preview handoff promises more than the local form can perform. |
| 5 | Error prevention | 3 | Sample data is repeatedly labelled; confirmation and evidence have explicit main actions; the preview blocks research submission. The still-enabled handoff leads users toward that blocked action. |
| 6 | Recognition rather than recall | 3 | Stage rail and retained scene context explain location well. Six sibling stages and offscreen playback controls require some scanning. |
| 7 | Flexibility and efficiency | 2 | Experts can jump directly between stages and skip playback. No assessed accelerators beyond standard controls; reduced mode's Resume wastes actions. |
| 8 | Aesthetic and minimalist design | 3 | Restrained typography, borders and orange give the evidence room. Large diagram spacing and repeated instructions make some scenes taller than their content needs. |
| 9 | Error recognition and recovery | 2 | Source shows inline alerts with retained form state, but top-level failures share "Reload workspace" and pass through error messages. No failure flow was triggered, so strong recovery is unproven. |
| 10 | Help and documentation | 3 | The sample is task-focused contextual help with explicit click instructions, synthetic-data notices and unknowns. Its reduced-motion instructions currently send the user to the wrong control. |
| | Total | **27/40** | **Acceptable, with specific fixes needed** |

## What works

1. The normal walkthrough distinguishes automatic stages from human decisions. I observed "This step advances automatically. No click needed," then a persistent stop at "Confirm example target," then a stop at "Inspect example passage." Confirmation and evidence have no competing Next shortcut. This directly addresses the requested clarity.
2. Evidence and human judgment stay separate. The opened passage calls itself synthetic; the unknown budget owner stays visible; acceptance does not become an asserted fit fact. Review feedback says the decision is separate from the assessment. This builds trust through behavior.
3. The visual language is cohesive. Dark navigation anchors the workspace, the paper and white research areas remain readable, and thin orange traces relate the entry plate to the source-processing illustration. Motion is tied to a playing sample or saved worker state in source rather than a fabricated percentage.

## Priority issues

### P1: reduced-motion Resume does not mean continue

Observed reproduction:

1. Reach review, enable Reduce motion, then click Replay.
2. Offer appears with "Demo paused. Click Resume below to continue, or choose another stage."
3. Click Resume. Nothing changes.
4. Click Next to reach market, then click Resume. The demo returns to offer.

`LandingDemo.tsx:85` tells reduced-mode users to Resume. At line 95, reduced-mode Resume calls `select('offer')` for every stage. The reduced-motion policy therefore changes navigation meaning, not merely animation. A reader who follows the instruction appears stuck or loses position.

Fix: make reduced mode explicitly manual. Hide Resume, label the cue "Manual example," and point to Next where an automatic stage needs manual advancement. Keep the distinct confirmation and evidence actions. Replay should return to the first stage once; it should not share logic with Resume. Retain the selected stage when changing animation preference unless the user explicitly requests a restart.

Suggested command: `/impeccable harden`, then `/impeccable clarify`.

### P2: automatic scenes outrun the reading area

`landing-demo.data.ts` allows three seconds for offer and four seconds for market and discovery. In the observed laptop viewport, the offer's note and playback controls were below the fold; the market's second observation and campaign hypothesis also extended below it. The timer continues while a user scrolls or reads. That makes it possible to miss the material being introduced before the scene replaces it.

After target confirmation, the retained page scroll position also clipped the new discovery heading and hid the top automatic-action cue. After discovery advanced, evidence's heading sat at the viewport's top edge. The footer status and the orange evidence button rescued the next action, so this was not a blocked flow, but the transition did not preserve a comfortable reading position.

Fix: keep a compact scene heading, state cue and playback controls in view together. Shorten the illustrative automatic scenes to one main observation, or give them a reader-controlled continuation. If autoplay stays, increase dwell time based on the actual visible content and expose a prominent Pause near the cue. On a stage change, preserve a deliberate scene anchor rather than an arbitrary lower scroll position; honor reduced motion for any repositioning.

Suggested command: `/impeccable layout` and `/impeccable animate`.

### P2: the preview's final handoff leads to a disabled primary action

The preview accurately explains that it cannot start research, and its link to the real workspace is useful. But the walkthrough still ends with an enabled orange "Research my website" button. I clicked it and it focused the company field beside a permanently disabled "Start research." The explanation and real-workspace link were then above the viewport. The sample's strongest closing action sent me to a task I could not finish there.

This is specific to the isolated preview, not evidence that hosted or configured research is blocked. The preview notice also pushed the initial "Try the demo" below the observed first viewport while the disabled action remained prominent.

Fix: pass preview context into the handoff. In the preview, make the final action "Open the research workspace" with the existing configured destination and a local explanation. Keep the form-focus handoff in an enabled workspace. Compress the preview notice or bring its "Try the demo" action into the notice so the available first action is visible immediately.

Suggested command: `/impeccable clarify` and `/impeccable onboard`.

## Cognitive load

Overall: moderate, with three checklist failures in the expanded walkthrough. The initial company entry itself is low load when considered independently of the preview notice.

| Check | Result | Observation |
|---|---|---|
| Single focus | Pass with caveat | One company input is primary. In the sample, the scene's main action is visually clear, although the persistent real-task handoff competes near the bottom. |
| Chunking | Fail | Six stage choices remain visible as one sibling group on desktop. The market scene additionally introduces two companies and a campaign hypothesis while explaining the process. |
| Grouping | Pass | Rail, scene, playback and handoff have clear boundaries. Evidence and unknowns have distinct local groups. |
| Visual hierarchy | Pass | Strong scene heading, quiet metadata and one orange action at required stops. The entry's preview notice is disproportionately prominent. |
| One thing at a time | Fail | Automatic scenes require reading, interpreting the illustration and managing playback before the timer advances. |
| Minimal choices | Fail | Six stage jumps exceed four options. They are secondary navigation, which reduces the severity, but remain six choices. |
| Working memory | Pass | Offer, target and evidence appear locally; the rail preserves sequence. No material memory bridge was required. |
| Progressive disclosure | Pass | Sample opens on demand; passage and editable draft require deliberate disclosure. |

Visible option counts: six stage buttons in the main stage group; offer/market playback has up to three transport buttons plus motion preference; review has Accept, Reject and draft disclosure as its local content actions. The interface does not present those review actions as equivalent to the six navigation choices, so their counts should not simply be added into one inflated total.

## Emotional journey

Arrival is calm and credible. The large headline and precise company field promise an easy start. In this preview, the disabled CTA and environment notice create the first small valley because the available path is the quiet demo below the fold.

Opening the sample gives the user a convincing research sequence. The moving source illustration explains the machine's role, and the confirmation stop restores agency. The peak is opening the passage: a conclusion becomes inspectable text with a plainly stated unknown. This is the product's most persuasive moment.

Review then hands judgment back to the user. Editable draft disclosure is a sensible optional next step. The normal closing handoff would be a useful end, but the preview's disabled destination weakens it. Reduced-mode Resume creates a sharper valley because the instruction fails immediately after the user asks for a more comfortable experience.

## Persona red flags

### Jordan, first-time user

The required clicks in normal playback are now clear. Jordan can still miss market content before the four-second advance. In the preview, "Research my website" ends at a disabled form, with the explanation above the viewport. "Campaign hypothesis" is understandable for GTM professionals but receives less plain-language help than the evidence concepts.

### Sam, user who needs reduced motion or keyboard navigation

Reduced motion removes animation, but the cue continues to instruct Resume and that control does not continue. This is an observed defect, not a hypothetical accessibility concern. Focus restoration and button labels exist in source; stage transitions focus a heading with `preventScroll`, which can leave it clipped after lower-page actions. Actual screen-reader announcements and a full keyboard pass were not tested here.

### Alex, experienced practitioner

Direct stage jumps are a useful shortcut. The low-information source animation occupies much of each automatic scene while transport controls sit below the fold. Alex can bypass it via the rail, but must discover that shortcut. The sample ends at a single-company review rather than a compact multi-company shortlist comparison, so it only partially demonstrates the product outcome promised by the entry headline.

## Minor observations

- The entry plate is attractive but more atmospheric than explanatory. Its scan resembles inspection while no input exists. The implementation correctly marks it decorative and never calls it progress. A shared source/evidence motif would create a stronger connection without inventing activity.
- The headline and description are separated by more vertical space than their semantic relationship needs. The illustration sets the two-row grid's height, and the centered form begins on a different left edge. A tighter text block would make the entry feel more deliberate.
- "Pause visual," "Reduce motion" and live research's "Pause animations" each scope motion differently. Their local placement helps, but the preferences are not a single product-wide setting. Avoid implying that one stops every animation.
- The review scene says "Your turn" at the top while its footer says "Example complete." Both can be true, but "Walkthrough complete. Try the review" would make the distinction plainer.
- The stage rail checks all earlier positions, even when direct navigation skipped them. These are positional markers, not proof that the user completed those actions. Use a neutral visited/progress treatment or record actual sample completion if completion is intended.
- The sidebar is readable and compact at the inspected width. A collapsed rail intentionally hides company names, so tooltips and accessible names matter for distinguishing saved runs. Mobile overflow and large saved histories require separate verification.
- Documentation describes a mouse-movement pause, but the inspected current scene implements focus capture, hidden-document and offscreen pauses. The later refinement text correctly says pointer movement does not silently pause. Consolidate that documentation when implementation work resumes.

## Questions for synthesis

1. Should the sample primarily demonstrate the automation quickly, or teach the user to inspect research? A short autoplay plus an explicitly manual evidence lesson would support both more clearly.
2. Should the final sample show a compact three-company shortlist before opening one research sheet, so the promised output is visible before asking the visitor to start?
3. Can the entry plate and the operational source diagram share one recognizable evidence-processing motif, while keeping decorative motion separate from real progress?

No detector findings were received or used. These questions are supplied to the parent for synthesis; this assessment does not ask the user to approve implementation.

## Correction verification addendum

Scope: only the three priority issues above. This is a source verification, not a second live design review. CUA could not create the requested fresh browser 2 tab because browser 2 was unavailable; a fresh inventory returned no browsers. No tab was created, no viewport was changed, and no provider call or saved-run mutation occurred. The original live evidence remains valid for the original build only.

- Reduced-motion defect: corrected in the inspected source. Manual offer and market stages render Next without Resume. Replay at review selects offer once; Next selects market, and the reduce transition preserves the current stage. The manual cue explicitly says "Click Next above." This removes the previously observed no-op and reset paths.
- Reading and scroll issue: the inspected source moves transport controls above the scene and makes them sticky, doubles automatic holds to 6/8/6 seconds, and calls an instant centered scene-heading scroll after stage selection, confirmation and evidence-to-review choices. These changes address the identified causes. Actual sticky placement, available reading area and scroll landing have not been visually reverified in this subagent turn.
- Preview handoff: corrected in source. `main.tsx` passes the preview marker as `researchUrl`; `LandingDemo` renders an "Open research workspace" anchor with that URL instead of focusing the disabled form. The preview launcher defaults the marker to `http://127.0.0.1:8019/`. The actual rebuilt DOM href could not be inspected here.

Parent-supplied verification: the parent reports an actual CUA phone check showing manual mode retains offer without Resume, controls above the cue, and the preview handoff's actual href `http://127.0.0.1:8019/`. The parent also reports all 12 final phone/laptop demo tests passed, including reduced manual navigation. This evidence is attributed to the parent and was not independently repeated here.

Disposition: ship for these reported priorities. No remaining defect identified in the inspected correction paths, and the parent supplied the live and automated verification above. This subagent does not claim an independent fresh visual sign-off.
