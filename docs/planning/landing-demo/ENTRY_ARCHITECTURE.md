# First-visit information architecture

16 October 2026. Scope: simplify the existing landing entry on codex/landing-demo-plan. Preserve the paper/orange identity and the real research flow.

## Usage and desired result

A new visitor enters a company name or website, chooses Start research, reviews the drafted offer/target, then confirms discovery. Someone who wants reassurance can open Try the demo without creating a run. A returning visitor can still open saved research.

## Observations and reference boundary

The current entry renders a large heading and explanation, two prominent entry buttons, a separate question/explanation and form, an always-visible sample sheet, a three-step method section and an empty saved-runs sidebar. Several components repeat the same orientation.

The public Explee homepage inspected in the browser on16 October puts a headline, short description and website field in the hero, followed by testimonials and process explanation below. The useful reference is the hierarchy and immediate input, not Explee's unverified outcome claims or outreach functionality. No form was submitted or account created. Reference: https://explee.com/.

REA doctor reports the Codex server registration missing. Its skill file is available, but no REA MCP tools are connected. These observations come from ordinary browser and repository inspection, not REA Evidence. Client configuration was not modified.

## Alternatives

1. Keep two equal entry buttons and move all supporting information into disclosures. This still asks visitors to choose a mode before entering their company, and leaves a duplicate research action.
2. Put the company form first, with one primary submit and a quiet optional demo. This removes the mode choice from the common path. Chosen for the user's new request to reduce initial information; it supersedes the earlier equal-prominence button treatment.
3. Create separate marketing, demo and workspace routes. This may suit later public acquisition, but introduces routing/auth handoff and typed-input persistence work beyond this entry refinement.

## Types, interfaces and ownership

- App remains the sole owner of company input, request key, API submission, saved runs and errors. The existing start command and frozen research profile stay unchanged.
- LandingDemo owns only its optional sample playback and sample editing. Its children slot receives the real form. Try the demo is its single entry control; sample content mounts only after that action.
- Whether the workspace sidebar is present is derived from an active run or actual saved runs, not persisted as another flag. Loading and failed history requests retain their existing explicit status/recovery treatment.
- Real ResearchProgress continues to derive its state from saved worker progress. It does not use sample timers.
- No new API, server state, route, provider operation or credit policy is introduced.

## Disclosure map

| When | What becomes visible |
| --- | --- |
| First visit | Brand/account controls, one promise, one company field, Start research, short confirmation reassurance and optional Try the demo |
| Choose demo | Existing labelled sample, stage controls, passage, review and draft interactions |
| Start real research | Current real stage, worker availability and checkpoint disclosure |
| Target confirmation | Editable offer, campaign/criteria, exclusions, batch size and exact credit cost |
| Results | Companies, evidence, unknowns, independent review and export formats |
| Returning visit | Actual saved-run navigation |

Remove the always-visible sample sheet and repeated method section from the initial screen. Keep sample evidence and explanations inside the optional demo and real evidence views. Local operator key setup remains available below the real form; errors are never hidden by the simplified layout.

## Invariants and verification

Try the demo sends no research mutation. Demo close restores entry-button focus; real input survives opening/closing the sample. Research still uses the same submit handler and cannot bypass target confirmation. A failed request preserves the entered company and offers the existing recovery. Saved research remains reachable, and a genuine empty account does not display an empty sidebar.

Verify actual built UI at1366x900 and390x844, keyboard navigation, reduced motion,320px overflow and200% text. Run the existing demo and real-flow browser regressions with labelled providers. No paid provider evaluation is authorized by this design task.

Supporting practitioner reference: [Uriel Bitton, SaaS Empty States: Help a New User Finish the First Task](https://dev.to/urielbitton/saas-empty-states-help-a-new-user-finish-the-first-task-3fkb), tags webdev/ux/saas. The article argues for one useful first task, distinct loading/error/empty states, and labelled optional samples. Its fetched comment thread was empty; this is design guidance, not measured evidence that our conversion rate improved.
