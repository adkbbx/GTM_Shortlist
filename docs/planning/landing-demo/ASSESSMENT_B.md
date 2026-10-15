# Assessment B — detector and browser evidence

Method: isolated Assessment B subagent. Target: `web/main.tsx` and imported research/sidebar/demo/workshop surfaces. Preview: `http://127.0.0.1:8018/`. Browser: fresh tab in browser 2, closed on completion. No code edits, provider calls, worker starts, configuration writes, or saved-run mutations.

## Provenance and limitations

Read the bundled critique Assessment B instructions. Ran `impeccable.cmd detect --json web` once; the tool envelope truncated that output. The parent expressly authorized one recovery run, captured below in full. Recovery run exited 0 and returned 87 advisory findings. Exit 0 means no non-advisory violations; it does not mean no advisories.

Browser evaluate is explicitly read-only. Mutable title/script preflight, detector injection, live server and overlay presentation were skipped. No user-visible detector overlay exists. Fallback evidence is the CLI scan plus real DOM, screenshots and computed styles. No console detector results are claimed. Browser warning/error log inspection returned no entries.

I inspected desktop at the existing 1280 × 720 viewport without changing browser-wide viewport settings. Mobile/responsive review remains with the parent. I did not select or change the existing queued saved run. ResearchProgress has source inspection only; its live worker states are not independently browser-tested here.

## Deterministic result

All 87 findings are advisory:

| Rule | Count |
|---|---:|
| design-system-font-size | 64 |
| design-system-color | 19 |
| design-system-radius | 3 |
| codex-grid-background | 1 |

| File | Count |
|---|---:|
| web/styles.css | 50 |
| web/ResearchSidebar.css | 16 |
| web/LandingDemo.css | 9 |
| web/ResearchProgress.css | 5 |
| web/Shortlist.css | 4 |
| web/WorkshopField.css | 3 |

The raw JSON below preserves all rule names, snippets, values and line locations. CSS is densely minified by line, so a single line can contain many declarations.

## False positives and interpretation

- `codex-grid-background` at `web/styles.css:2` is a rendered-state false positive. Legacy CSS still contains the two-axis gradient, but computed `background-image` on body, workspace and main is `none`, and the screenshots show plain paper. Do not claim the main page has an actual decorative grid. The workshop's small calibration plate is a separate, explicitly selected product illustration.
- Many type-ramp warnings are documentation/parser mismatch rather than evidence of poor typography. DESIGN.md prose explicitly documents `.875rem` hints, `.75rem` saved-run metadata, the large entry heading, phone 38/34px headings, and the 17px wordmark is from the later implemented navigation direction. Its frontmatter lists fewer sizes. Treat these as design-system synchronization, then decide whether each missing step is intentional.
- Sidebar colors in `ResearchSidebar.css` create a coherent dark navigation family, but several are absent from frontmatter. This is genuine documentation/token drift, not automatically a contrast defect. The cue colors `#62432c`, `#8d3b14` and 6px radius at `LandingDemo.css:28` are further undocumented additions.
- The detector scans legacy declarations even when later cascade rules win. The raw count therefore overstates the number of independent visible inconsistencies. It does not report 87 user-facing defects.

## Browser observations and measured evidence

1. **[P2] The useful demo entry starts below the initial laptop viewport.** Initial `Try the demo` button top was 723.79px in a 720px-tall viewport. The form input/submit were at 611.76px and 53.94px high. The preview-only warning occupied the top of the main area, the hero and workshop followed, and the optional demo was out of view. This is observed specifically in the isolated preview with existing history and its mandatory warning; do not generalize that the hosted first visit has the same fold. The actionable correction is to test a shorter first-screen composition or make the preview demo action available within the limitation notice.

2. **[P2] Playback controls are detached from the animation at laptop height.** Immediately after opening the demo, its heading was at 48.37px, status cue at 216.39px, and the market-stage animation was visible. Pause/Next were at 976.63px and Reduce motion at 1064.78px, well below the 720px viewport. The rail's six choices consume roughly 530px vertically and the scene is tall. Users can read “Pause whenever you like” only near controls farther down. Move the transport controls beside the scene status or use a compact persistent row inside the walkthrough. This is a control discoverability issue, not a claim that pause is absent.

3. **[P3] Sidebar collapse control is 40px wide.** DOM measurement: 40 × 44px at x171.43/y80, despite other controls meeting at least 44px height. Enlarge the horizontal hit target to 44px if applying the skill's 44 × 44 touch recommendation. This is not an assertion of a WCAG 2.2 minimum-target failure (that threshold is different).

4. **Six stage choices are simultaneously visible on desktop.** These are clearly ordered and grouped under an explicit current-step label. This is a manageable but above-four decision cluster; shorten descriptions or progressively disclose the rail if the main task becomes crowded. Do not count the six stages as six equal primary CTAs: the active scene has one explicit main action at confirmation/evidence.

5. **The primary walkthrough feedback works.** Opening the demo focused `#demo-heading`. Confirmation displays “Your turn” and the exact requested action, and has no competing Next button. Evidence inspection updates `aria-expanded` and reveals a clearly labelled synthetic passage inline; then “Review this example” moves focus to the review heading. “Accept example” updates its pressed state and the live status to “Example accepted. Your decision is separate from the fit assessment.” Closing returns focus to “Try the demo.” These interactions were synthetic and local only.

6. **The product-specific visual is restrained.** The real screenshot showed a small calibration diagram alongside the entry heading and source-to-research-sheet linework inside the demo. The page uses Schibsted Grotesk (confirmed computed font) and plain paper. Do not let the static gradient warning override this evidence.

7. **No horizontal overflow was observed at 1280px.** `document.documentElement.scrollWidth > innerWidth` was false. Stage rail descriptions computed to 13px, normal muted `rgb(100,97,91)`; common demo buttons were at least 44px high. Confirmation primary action measured 250.87 × 52px. I did not run a contrast checker or a full keyboard/assistive technology audit, so no blanket accessibility pass is claimed.

## Recommended synthesis weight

Prioritize the verified below-fold playback controls over raw style-advisory counts. Explain the warning's preview-specific impact. Fold the undocumented sizes/colors into one low-priority design-system synchronization item unless Assessment A independently observed an actual visual inconsistency. Preserve the positive evidence around user-controlled confirmation, synthetic-source disclosure and separate human review.

## Raw detector JSON

```json
[
  {
    "antipattern": "design-system-font-size",
    "name": "Font size outside DESIGN.md",
    "description": "A literal font-size is off the type ramp documented in DESIGN.md typography. Use a documented size step or update the design system if the new step is intentional.",
    "severity": "advisory",
    "category": "quality",
    "file": "C:\\Users\\ADK\\.codex\\worktrees\\gtm-landing-demo-plan\\web\\LandingDemo.css",
    "line": 1,
    "snippet": "font-size: 1.125rem is off the DESIGN.md type ramp",
    "advisory": true,
    "ignoreValue": "1.125rem",
    "importedBy": [
      "main.tsx"
    ]
  },
  {
    "antipattern": "design-system-font-size",
    "name": "Font size outside DESIGN.md",
    "description": "A literal font-size is off the type ramp documented in DESIGN.md typography. Use a documented size step or update the design system if the new step is intentional.",
    "severity": "advisory",
    "category": "quality",
    "file": "C:\\Users\\ADK\\.codex\\worktrees\\gtm-landing-demo-plan\\web\\LandingDemo.css",
    "line": 1,
    "snippet": "font-size: .875rem is off the DESIGN.md type ramp",
    "advisory": true,
    "ignoreValue": ".875rem",
    "importedBy": [
      "main.tsx"
    ]
  },
  {
    "antipattern": "design-system-font-size",
    "name": "Font size outside DESIGN.md",
    "description": "A literal font-size is off the type ramp documented in DESIGN.md typography. Use a documented size step or update the design system if the new step is intentional.",
    "severity": "advisory",
    "category": "quality",
    "file": "C:\\Users\\ADK\\.codex\\worktrees\\gtm-landing-demo-plan\\web\\LandingDemo.css",
    "line": 18,
    "snippet": "font-size: clamp(36px,4.2vw,58px) has fluid endpoints 36px and 58px off the DESIGN.md type ramp",
    "advisory": true,
    "ignoreValue": "36px",
    "importedBy": [
      "main.tsx"
    ]
  },
  {
    "antipattern": "design-system-font-size",
    "name": "Font size outside DESIGN.md",
    "description": "A literal font-size is off the type ramp documented in DESIGN.md typography. Use a documented size step or update the design system if the new step is intentional.",
    "severity": "advisory",
    "category": "quality",
    "file": "C:\\Users\\ADK\\.codex\\worktrees\\gtm-landing-demo-plan\\web\\LandingDemo.css",
    "line": 26,
    "snippet": "font-size: clamp(32px,8.5vw,42px) has fluid endpoints 32px and 42px off the DESIGN.md type ramp",
    "advisory": true,
    "ignoreValue": "32px",
    "importedBy": [
      "main.tsx"
    ]
  },
  {
    "antipattern": "design-system-color",
    "name": "Color outside DESIGN.md",
    "description": "A literal color is outside the DESIGN.md palette and sidecar tonal ramps. This may be legitimate, but it should be an intentional design-system addition rather than drift.",
    "severity": "advisory",
    "category": "quality",
    "file": "C:\\Users\\ADK\\.codex\\worktrees\\gtm-landing-demo-plan\\web\\LandingDemo.css",
    "line": 28,
    "snippet": "Undocumented color #62432c is outside DESIGN.md colors",
    "advisory": true,
    "ignoreValue": "#62432c",
    "importedBy": [
      "main.tsx"
    ]
  },
  {
    "antipattern": "design-system-color",
    "name": "Color outside DESIGN.md",
    "description": "A literal color is outside the DESIGN.md palette and sidecar tonal ramps. This may be legitimate, but it should be an intentional design-system addition rather than drift.",
    "severity": "advisory",
    "category": "quality",
    "file": "C:\\Users\\ADK\\.codex\\worktrees\\gtm-landing-demo-plan\\web\\LandingDemo.css",
    "line": 28,
    "snippet": "Undocumented color #8d3b14 is outside DESIGN.md colors",
    "advisory": true,
    "ignoreValue": "#8d3b14",
    "importedBy": [
      "main.tsx"
    ]
  },
  {
    "antipattern": "design-system-radius",
    "name": "Radius outside DESIGN.md",
    "description": "A border-radius value is outside the DESIGN.md rounded scale. Use a documented radius token or update the design system if the new shape is intentional.",
    "severity": "advisory",
    "category": "quality",
    "file": "C:\\Users\\ADK\\.codex\\worktrees\\gtm-landing-demo-plan\\web\\LandingDemo.css",
    "line": 28,
    "snippet": "border-radius: 6px is outside the DESIGN.md rounded scale",
    "advisory": true,
    "ignoreValue": "6px",
    "importedBy": [
      "main.tsx"
    ]
  },
  {
    "antipattern": "design-system-font-size",
    "name": "Font size outside DESIGN.md",
    "description": "A literal font-size is off the type ramp documented in DESIGN.md typography. Use a documented size step or update the design system if the new step is intentional.",
    "severity": "advisory",
    "category": "quality",
    "file": "C:\\Users\\ADK\\.codex\\worktrees\\gtm-landing-demo-plan\\web\\LandingDemo.css",
    "line": 28,
    "snippet": "font-size: .875rem is off the DESIGN.md type ramp",
    "advisory": true,
    "ignoreValue": ".875rem",
    "importedBy": [
      "main.tsx"
    ]
  },
  {
    "antipattern": "design-system-font-size",
    "name": "Font size outside DESIGN.md",
    "description": "A literal font-size is off the type ramp documented in DESIGN.md typography. Use a documented size step or update the design system if the new step is intentional.",
    "severity": "advisory",
    "category": "quality",
    "file": "C:\\Users\\ADK\\.codex\\worktrees\\gtm-landing-demo-plan\\web\\LandingDemo.css",
    "line": 30,
    "snippet": "font-size: .75rem is off the DESIGN.md type ramp",
    "advisory": true,
    "ignoreValue": ".75rem",
    "importedBy": [
      "main.tsx"
    ]
  },
  {
    "antipattern": "design-system-font-size",
    "name": "Font size outside DESIGN.md",
    "description": "A literal font-size is off the type ramp documented in DESIGN.md typography. Use a documented size step or update the design system if the new step is intentional.",
    "severity": "advisory",
    "category": "quality",
    "file": "C:\\Users\\ADK\\.codex\\worktrees\\gtm-landing-demo-plan\\web\\ResearchProgress.css",
    "line": 1,
    "snippet": "font-size: .875rem is off the DESIGN.md type ramp",
    "advisory": true,
    "ignoreValue": ".875rem",
    "importedBy": [
      "ResearchProgress.tsx",
      "main.tsx"
    ]
  },
  {
    "antipattern": "design-system-font-size",
    "name": "Font size outside DESIGN.md",
    "description": "A literal font-size is off the type ramp documented in DESIGN.md typography. Use a documented size step or update the design system if the new step is intentional.",
    "severity": "advisory",
    "category": "quality",
    "file": "C:\\Users\\ADK\\.codex\\worktrees\\gtm-landing-demo-plan\\web\\ResearchProgress.css",
    "line": 1,
    "snippet": "font-size: 1.75rem is off the DESIGN.md type ramp",
    "advisory": true,
    "ignoreValue": "1.75rem",
    "importedBy": [
      "ResearchProgress.tsx",
      "main.tsx"
    ]
  },
  {
    "antipattern": "design-system-font-size",
    "name": "Font size outside DESIGN.md",
    "description": "A literal font-size is off the type ramp documented in DESIGN.md typography. Use a documented size step or update the design system if the new step is intentional.",
    "severity": "advisory",
    "category": "quality",
    "file": "C:\\Users\\ADK\\.codex\\worktrees\\gtm-landing-demo-plan\\web\\ResearchProgress.css",
    "line": 2,
    "snippet": "font-size: .75rem is off the DESIGN.md type ramp",
    "advisory": true,
    "ignoreValue": ".75rem",
    "importedBy": [
      "ResearchProgress.tsx",
      "main.tsx"
    ]
  },
  {
    "antipattern": "design-system-font-size",
    "name": "Font size outside DESIGN.md",
    "description": "A literal font-size is off the type ramp documented in DESIGN.md typography. Use a documented size step or update the design system if the new step is intentional.",
    "severity": "advisory",
    "category": "quality",
    "file": "C:\\Users\\ADK\\.codex\\worktrees\\gtm-landing-demo-plan\\web\\ResearchProgress.css",
    "line": 3,
    "snippet": "font-size: 1.5rem is off the DESIGN.md type ramp",
    "advisory": true,
    "ignoreValue": "1.5rem",
    "importedBy": [
      "ResearchProgress.tsx",
      "main.tsx"
    ]
  },
  {
    "antipattern": "design-system-font-size",
    "name": "Font size outside DESIGN.md",
    "description": "A literal font-size is off the type ramp documented in DESIGN.md typography. Use a documented size step or update the design system if the new step is intentional.",
    "severity": "advisory",
    "category": "quality",
    "file": "C:\\Users\\ADK\\.codex\\worktrees\\gtm-landing-demo-plan\\web\\ResearchProgress.css",
    "line": 40,
    "snippet": "font-size: .75rem is off the DESIGN.md type ramp",
    "advisory": true,
    "ignoreValue": ".75rem",
    "importedBy": [
      "ResearchProgress.tsx",
      "main.tsx"
    ]
  },
  {
    "antipattern": "design-system-color",
    "name": "Color outside DESIGN.md",
    "description": "A literal color is outside the DESIGN.md palette and sidecar tonal ramps. This may be legitimate, but it should be an intentional design-system addition rather than drift.",
    "severity": "advisory",
    "category": "quality",
    "file": "C:\\Users\\ADK\\.codex\\worktrees\\gtm-landing-demo-plan\\web\\ResearchSidebar.css",
    "line": 1,
    "snippet": "Undocumented color #e8e4dd is outside DESIGN.md colors",
    "advisory": true,
    "ignoreValue": "#e8e4dd",
    "importedBy": [
      "ResearchSidebar.tsx",
      "main.tsx"
    ]
  },
  {
    "antipattern": "design-system-color",
    "name": "Color outside DESIGN.md",
    "description": "A literal color is outside the DESIGN.md palette and sidecar tonal ramps. This may be legitimate, but it should be an intentional design-system addition rather than drift.",
    "severity": "advisory",
    "category": "quality",
    "file": "C:\\Users\\ADK\\.codex\\worktrees\\gtm-landing-demo-plan\\web\\ResearchSidebar.css",
    "line": 1,
    "snippet": "Undocumented color #37332e is outside DESIGN.md colors",
    "advisory": true,
    "ignoreValue": "#37332e",
    "importedBy": [
      "ResearchSidebar.tsx",
      "main.tsx"
    ]
  },
  {
    "antipattern": "design-system-font-size",
    "name": "Font size outside DESIGN.md",
    "description": "A literal font-size is off the type ramp documented in DESIGN.md typography. Use a documented size step or update the design system if the new step is intentional.",
    "severity": "advisory",
    "category": "quality",
    "file": "C:\\Users\\ADK\\.codex\\worktrees\\gtm-landing-demo-plan\\web\\ResearchSidebar.css",
    "line": 3,
    "snippet": "font-size: .875rem is off the DESIGN.md type ramp",
    "advisory": true,
    "ignoreValue": ".875rem",
    "importedBy": [
      "ResearchSidebar.tsx",
      "main.tsx"
    ]
  },
  {
    "antipattern": "design-system-color",
    "name": "Color outside DESIGN.md",
    "description": "A literal color is outside the DESIGN.md palette and sidecar tonal ramps. This may be legitimate, but it should be an intentional design-system addition rather than drift.",
    "severity": "advisory",
    "category": "quality",
    "file": "C:\\Users\\ADK\\.codex\\worktrees\\gtm-landing-demo-plan\\web\\ResearchSidebar.css",
    "line": 5,
    "snippet": "Undocumented color #302d28 is outside DESIGN.md colors",
    "advisory": true,
    "ignoreValue": "#302d28",
    "importedBy": [
      "ResearchSidebar.tsx",
      "main.tsx"
    ]
  },
  {
    "antipattern": "design-system-color",
    "name": "Color outside DESIGN.md",
    "description": "A literal color is outside the DESIGN.md palette and sidecar tonal ramps. This may be legitimate, but it should be an intentional design-system addition rather than drift.",
    "severity": "advisory",
    "category": "quality",
    "file": "C:\\Users\\ADK\\.codex\\worktrees\\gtm-landing-demo-plan\\web\\ResearchSidebar.css",
    "line": 6,
    "snippet": "Undocumented color #efa779 is outside DESIGN.md colors",
    "advisory": true,
    "ignoreValue": "#efa779",
    "importedBy": [
      "ResearchSidebar.tsx",
      "main.tsx"
    ]
  },
  {
    "antipattern": "design-system-font-size",
    "name": "Font size outside DESIGN.md",
    "description": "A literal font-size is off the type ramp documented in DESIGN.md typography. Use a documented size step or update the design system if the new step is intentional.",
    "severity": "advisory",
    "category": "quality",
    "file": "C:\\Users\\ADK\\.codex\\worktrees\\gtm-landing-demo-plan\\web\\ResearchSidebar.css",
    "line": 9,
    "snippet": "font-size: .875rem is off the DESIGN.md type ramp",
    "advisory": true,
    "ignoreValue": ".875rem",
    "importedBy": [
      "ResearchSidebar.tsx",
      "main.tsx"
    ]
  },
  {
    "antipattern": "design-system-font-size",
    "name": "Font size outside DESIGN.md",
    "description": "A literal font-size is off the type ramp documented in DESIGN.md typography. Use a documented size step or update the design system if the new step is intentional.",
    "severity": "advisory",
    "category": "quality",
    "file": "C:\\Users\\ADK\\.codex\\worktrees\\gtm-landing-demo-plan\\web\\ResearchSidebar.css",
    "line": 10,
    "snippet": "font-size: .75rem is off the DESIGN.md type ramp",
    "advisory": true,
    "ignoreValue": ".75rem",
    "importedBy": [
      "ResearchSidebar.tsx",
      "main.tsx"
    ]
  },
  {
    "antipattern": "design-system-color",
    "name": "Color outside DESIGN.md",
    "description": "A literal color is outside the DESIGN.md palette and sidecar tonal ramps. This may be legitimate, but it should be an intentional design-system addition rather than drift.",
    "severity": "advisory",
    "category": "quality",
    "file": "C:\\Users\\ADK\\.codex\\worktrees\\gtm-landing-demo-plan\\web\\ResearchSidebar.css",
    "line": 13,
    "snippet": "Undocumented color #35312b is outside DESIGN.md colors",
    "advisory": true,
    "ignoreValue": "#35312b",
    "importedBy": [
      "ResearchSidebar.tsx",
      "main.tsx"
    ]
  },
  {
    "antipattern": "design-system-color",
    "name": "Color outside DESIGN.md",
    "description": "A literal color is outside the DESIGN.md palette and sidecar tonal ramps. This may be legitimate, but it should be an intentional design-system addition rather than drift.",
    "severity": "advisory",
    "category": "quality",
    "file": "C:\\Users\\ADK\\.codex\\worktrees\\gtm-landing-demo-plan\\web\\ResearchSidebar.css",
    "line": 15,
    "snippet": "Undocumented color #efa779 is outside DESIGN.md colors",
    "advisory": true,
    "ignoreValue": "#efa779",
    "importedBy": [
      "ResearchSidebar.tsx",
      "main.tsx"
    ]
  },
  {
    "antipattern": "design-system-font-size",
    "name": "Font size outside DESIGN.md",
    "description": "A literal font-size is off the type ramp documented in DESIGN.md typography. Use a documented size step or update the design system if the new step is intentional.",
    "severity": "advisory",
    "category": "quality",
    "file": "C:\\Users\\ADK\\.codex\\worktrees\\gtm-landing-demo-plan\\web\\ResearchSidebar.css",
    "line": 17,
    "snippet": "font-size: .875rem is off the DESIGN.md type ramp",
    "advisory": true,
    "ignoreValue": ".875rem",
    "importedBy": [
      "ResearchSidebar.tsx",
      "main.tsx"
    ]
  },
  {
    "antipattern": "design-system-font-size",
    "name": "Font size outside DESIGN.md",
    "description": "A literal font-size is off the type ramp documented in DESIGN.md typography. Use a documented size step or update the design system if the new step is intentional.",
    "severity": "advisory",
    "category": "quality",
    "file": "C:\\Users\\ADK\\.codex\\worktrees\\gtm-landing-demo-plan\\web\\ResearchSidebar.css",
    "line": 18,
    "snippet": "font-size: .75rem is off the DESIGN.md type ramp",
    "advisory": true,
    "ignoreValue": ".75rem",
    "importedBy": [
      "ResearchSidebar.tsx",
      "main.tsx"
    ]
  },
  {
    "antipattern": "design-system-color",
    "name": "Color outside DESIGN.md",
    "description": "A literal color is outside the DESIGN.md palette and sidecar tonal ramps. This may be legitimate, but it should be an intentional design-system addition rather than drift.",
    "severity": "advisory",
    "category": "quality",
    "file": "C:\\Users\\ADK\\.codex\\worktrees\\gtm-landing-demo-plan\\web\\ResearchSidebar.css",
    "line": 26,
    "snippet": "Undocumented color #37332e is outside DESIGN.md colors",
    "advisory": true,
    "ignoreValue": "#37332e",
    "importedBy": [
      "ResearchSidebar.tsx",
      "main.tsx"
    ]
  },
  {
    "antipattern": "design-system-font-size",
    "name": "Font size outside DESIGN.md",
    "description": "A literal font-size is off the type ramp documented in DESIGN.md typography. Use a documented size step or update the design system if the new step is intentional.",
    "severity": "advisory",
    "category": "quality",
    "file": "C:\\Users\\ADK\\.codex\\worktrees\\gtm-landing-demo-plan\\web\\ResearchSidebar.css",
    "line": 31,
    "snippet": "font-size: 17px is off the DESIGN.md type ramp",
    "advisory": true,
    "ignoreValue": "17px",
    "importedBy": [
      "ResearchSidebar.tsx",
      "main.tsx"
    ]
  },
  {
    "antipattern": "design-system-color",
    "name": "Color outside DESIGN.md",
    "description": "A literal color is outside the DESIGN.md palette and sidecar tonal ramps. This may be legitimate, but it should be an intentional design-system addition rather than drift.",
    "severity": "advisory",
    "category": "quality",
    "file": "C:\\Users\\ADK\\.codex\\worktrees\\gtm-landing-demo-plan\\web\\ResearchSidebar.css",
    "line": 34,
    "snippet": "Undocumented color #e8e4dd is outside DESIGN.md colors",
    "advisory": true,
    "ignoreValue": "#e8e4dd",
    "importedBy": [
      "ResearchSidebar.tsx",
      "main.tsx"
    ]
  },
  {
    "antipattern": "design-system-color",
    "name": "Color outside DESIGN.md",
    "description": "A literal color is outside the DESIGN.md palette and sidecar tonal ramps. This may be legitimate, but it should be an intentional design-system addition rather than drift.",
    "severity": "advisory",
    "category": "quality",
    "file": "C:\\Users\\ADK\\.codex\\worktrees\\gtm-landing-demo-plan\\web\\ResearchSidebar.css",
    "line": 34,
    "snippet": "Undocumented color #37332e is outside DESIGN.md colors",
    "advisory": true,
    "ignoreValue": "#37332e",
    "importedBy": [
      "ResearchSidebar.tsx",
      "main.tsx"
    ]
  },
  {
    "antipattern": "design-system-color",
    "name": "Color outside DESIGN.md",
    "description": "A literal color is outside the DESIGN.md palette and sidecar tonal ramps. This may be legitimate, but it should be an intentional design-system addition rather than drift.",
    "severity": "advisory",
    "category": "quality",
    "file": "C:\\Users\\ADK\\.codex\\worktrees\\gtm-landing-demo-plan\\web\\ResearchSidebar.css",
    "line": 34,
    "snippet": "Undocumented color #efa779 is outside DESIGN.md colors",
    "advisory": true,
    "ignoreValue": "#efa779",
    "importedBy": [
      "ResearchSidebar.tsx",
      "main.tsx"
    ]
  },
  {
    "antipattern": "design-system-font-size",
    "name": "Font size outside DESIGN.md",
    "description": "A literal font-size is off the type ramp documented in DESIGN.md typography. Use a documented size step or update the design system if the new step is intentional.",
    "severity": "advisory",
    "category": "quality",
    "file": "C:\\Users\\ADK\\.codex\\worktrees\\gtm-landing-demo-plan\\web\\Shortlist.css",
    "line": 16,
    "snippet": "font-size: .875rem is off the DESIGN.md type ramp",
    "advisory": true,
    "ignoreValue": ".875rem",
    "importedBy": [
      "main.tsx"
    ]
  },
  {
    "antipattern": "design-system-font-size",
    "name": "Font size outside DESIGN.md",
    "description": "A literal font-size is off the type ramp documented in DESIGN.md typography. Use a documented size step or update the design system if the new step is intentional.",
    "severity": "advisory",
    "category": "quality",
    "file": "C:\\Users\\ADK\\.codex\\worktrees\\gtm-landing-demo-plan\\web\\Shortlist.css",
    "line": 30,
    "snippet": "font-size: .75rem is off the DESIGN.md type ramp",
    "advisory": true,
    "ignoreValue": ".75rem",
    "importedBy": [
      "main.tsx"
    ]
  },
  {
    "antipattern": "design-system-font-size",
    "name": "Font size outside DESIGN.md",
    "description": "A literal font-size is off the type ramp documented in DESIGN.md typography. Use a documented size step or update the design system if the new step is intentional.",
    "severity": "advisory",
    "category": "quality",
    "file": "C:\\Users\\ADK\\.codex\\worktrees\\gtm-landing-demo-plan\\web\\Shortlist.css",
    "line": 33,
    "snippet": "font-size: .75rem is off the DESIGN.md type ramp",
    "advisory": true,
    "ignoreValue": ".75rem",
    "importedBy": [
      "main.tsx"
    ]
  },
  {
    "antipattern": "design-system-font-size",
    "name": "Font size outside DESIGN.md",
    "description": "A literal font-size is off the type ramp documented in DESIGN.md typography. Use a documented size step or update the design system if the new step is intentional.",
    "severity": "advisory",
    "category": "quality",
    "file": "C:\\Users\\ADK\\.codex\\worktrees\\gtm-landing-demo-plan\\web\\Shortlist.css",
    "line": 40,
    "snippet": "font-size: .75rem is off the DESIGN.md type ramp",
    "advisory": true,
    "ignoreValue": ".75rem",
    "importedBy": [
      "main.tsx"
    ]
  },
  {
    "antipattern": "design-system-color",
    "name": "Color outside DESIGN.md",
    "description": "A literal color is outside the DESIGN.md palette and sidecar tonal ramps. This may be legitimate, but it should be an intentional design-system addition rather than drift.",
    "severity": "advisory",
    "category": "quality",
    "file": "C:\\Users\\ADK\\.codex\\worktrees\\gtm-landing-demo-plan\\web\\WorkshopField.css",
    "line": 1,
    "snippet": "Undocumented color #91897b is outside DESIGN.md colors",
    "advisory": true,
    "ignoreValue": "#91897b",
    "importedBy": [
      "WorkshopField.tsx",
      "main.tsx"
    ]
  },
  {
    "antipattern": "design-system-font-size",
    "name": "Font size outside DESIGN.md",
    "description": "A literal font-size is off the type ramp documented in DESIGN.md typography. Use a documented size step or update the design system if the new step is intentional.",
    "severity": "advisory",
    "category": "quality",
    "file": "C:\\Users\\ADK\\.codex\\worktrees\\gtm-landing-demo-plan\\web\\WorkshopField.css",
    "line": 1,
    "snippet": "font-size: .75rem is off the DESIGN.md type ramp",
    "advisory": true,
    "ignoreValue": ".75rem",
    "importedBy": [
      "WorkshopField.tsx",
      "main.tsx"
    ]
  },
  {
    "antipattern": "design-system-font-size",
    "name": "Font size outside DESIGN.md",
    "description": "A literal font-size is off the type ramp documented in DESIGN.md typography. Use a documented size step or update the design system if the new step is intentional.",
    "severity": "advisory",
    "category": "quality",
    "file": "C:\\Users\\ADK\\.codex\\worktrees\\gtm-landing-demo-plan\\web\\WorkshopField.css",
    "line": 1,
    "snippet": "font-size: clamp(36px,4vw,54px) has fluid endpoints 36px and 54px off the DESIGN.md type ramp",
    "advisory": true,
    "ignoreValue": "36px",
    "importedBy": [
      "WorkshopField.tsx",
      "main.tsx"
    ]
  },
  {
    "antipattern": "codex-grid-background",
    "name": "Decorative grid-line background",
    "description": "A decorative grid or line-field background drawn with hairline linear-gradient layers tiled by a fixed pixel cell is a recurring generated-UI signature. Reserve grid overlays for actual canvas, map, blueprint, or measurement surfaces; elsewhere use product structure or a plain surface.",
    "severity": "advisory",
    "category": "slop",
    "file": "C:\\Users\\ADK\\.codex\\worktrees\\gtm-landing-demo-plan\\web\\styles.css",
    "line": 2,
    "snippet": "two-axis grid-line gradient background",
    "advisory": true,
    "importedBy": [
      "main.tsx"
    ]
  },
  {
    "antipattern": "design-system-color",
    "name": "Color outside DESIGN.md",
    "description": "A literal color is outside the DESIGN.md palette and sidecar tonal ramps. This may be legitimate, but it should be an intentional design-system addition rather than drift.",
    "severity": "advisory",
    "category": "quality",
    "file": "C:\\Users\\ADK\\.codex\\worktrees\\gtm-landing-demo-plan\\web\\styles.css",
    "line": 1,
    "snippet": "Undocumented color #5c5853 is outside DESIGN.md colors",
    "advisory": true,
    "ignoreValue": "#5c5853",
    "importedBy": [
      "main.tsx"
    ]
  },
  {
    "antipattern": "design-system-font-size",
    "name": "Font size outside DESIGN.md",
    "description": "A literal font-size is off the type ramp documented in DESIGN.md typography. Use a documented size step or update the design system if the new step is intentional.",
    "severity": "advisory",
    "category": "quality",
    "file": "C:\\Users\\ADK\\.codex\\worktrees\\gtm-landing-demo-plan\\web\\styles.css",
    "line": 4,
    "snippet": "font-size: .875rem is off the DESIGN.md type ramp",
    "advisory": true,
    "ignoreValue": ".875rem",
    "importedBy": [
      "main.tsx"
    ]
  },
  {
    "antipattern": "design-system-font-size",
    "name": "Font size outside DESIGN.md",
    "description": "A literal font-size is off the type ramp documented in DESIGN.md typography. Use a documented size step or update the design system if the new step is intentional.",
    "severity": "advisory",
    "category": "quality",
    "file": "C:\\Users\\ADK\\.codex\\worktrees\\gtm-landing-demo-plan\\web\\styles.css",
    "line": 4,
    "snippet": "font-size: 1.75rem is off the DESIGN.md type ramp",
    "advisory": true,
    "ignoreValue": "1.75rem",
    "importedBy": [
      "main.tsx"
    ]
  },
  {
    "antipattern": "design-system-font-size",
    "name": "Font size outside DESIGN.md",
    "description": "A literal font-size is off the type ramp documented in DESIGN.md typography. Use a documented size step or update the design system if the new step is intentional.",
    "severity": "advisory",
    "category": "quality",
    "file": "C:\\Users\\ADK\\.codex\\worktrees\\gtm-landing-demo-plan\\web\\styles.css",
    "line": 4,
    "snippet": "font-size: .6875rem is off the DESIGN.md type ramp",
    "advisory": true,
    "ignoreValue": ".6875rem",
    "importedBy": [
      "main.tsx"
    ]
  },
  {
    "antipattern": "design-system-font-size",
    "name": "Font size outside DESIGN.md",
    "description": "A literal font-size is off the type ramp documented in DESIGN.md typography. Use a documented size step or update the design system if the new step is intentional.",
    "severity": "advisory",
    "category": "quality",
    "file": "C:\\Users\\ADK\\.codex\\worktrees\\gtm-landing-demo-plan\\web\\styles.css",
    "line": 7,
    "snippet": "font-size: .875rem is off the DESIGN.md type ramp",
    "advisory": true,
    "ignoreValue": ".875rem",
    "importedBy": [
      "main.tsx"
    ]
  },
  {
    "antipattern": "design-system-font-size",
    "name": "Font size outside DESIGN.md",
    "description": "A literal font-size is off the type ramp documented in DESIGN.md typography. Use a documented size step or update the design system if the new step is intentional.",
    "severity": "advisory",
    "category": "quality",
    "file": "C:\\Users\\ADK\\.codex\\worktrees\\gtm-landing-demo-plan\\web\\styles.css",
    "line": 7,
    "snippet": "font-size: 1.125rem is off the DESIGN.md type ramp",
    "advisory": true,
    "ignoreValue": "1.125rem",
    "importedBy": [
      "main.tsx"
    ]
  },
  {
    "antipattern": "design-system-font-size",
    "name": "Font size outside DESIGN.md",
    "description": "A literal font-size is off the type ramp documented in DESIGN.md typography. Use a documented size step or update the design system if the new step is intentional.",
    "severity": "advisory",
    "category": "quality",
    "file": "C:\\Users\\ADK\\.codex\\worktrees\\gtm-landing-demo-plan\\web\\styles.css",
    "line": 7,
    "snippet": "font-size: .75rem is off the DESIGN.md type ramp",
    "advisory": true,
    "ignoreValue": ".75rem",
    "importedBy": [
      "main.tsx"
    ]
  },
  {
    "antipattern": "design-system-color",
    "name": "Color outside DESIGN.md",
    "description": "A literal color is outside the DESIGN.md palette and sidecar tonal ramps. This may be legitimate, but it should be an intentional design-system addition rather than drift.",
    "severity": "advisory",
    "category": "quality",
    "file": "C:\\Users\\ADK\\.codex\\worktrees\\gtm-landing-demo-plan\\web\\styles.css",
    "line": 18,
    "snippet": "Undocumented color #b9b5ad is outside DESIGN.md colors",
    "advisory": true,
    "ignoreValue": "#b9b5ad",
    "importedBy": [
      "main.tsx"
    ]
  },
  {
    "antipattern": "design-system-color",
    "name": "Color outside DESIGN.md",
    "description": "A literal color is outside the DESIGN.md palette and sidecar tonal ramps. This may be legitimate, but it should be an intentional design-system addition rather than drift.",
    "severity": "advisory",
    "category": "quality",
    "file": "C:\\Users\\ADK\\.codex\\worktrees\\gtm-landing-demo-plan\\web\\styles.css",
    "line": 20,
    "snippet": "Undocumented color #918b80 is outside DESIGN.md colors",
    "advisory": true,
    "ignoreValue": "#918b80",
    "importedBy": [
      "main.tsx"
    ]
  },
  {
    "antipattern": "design-system-font-size",
    "name": "Font size outside DESIGN.md",
    "description": "A literal font-size is off the type ramp documented in DESIGN.md typography. Use a documented size step or update the design system if the new step is intentional.",
    "severity": "advisory",
    "category": "quality",
    "file": "C:\\Users\\ADK\\.codex\\worktrees\\gtm-landing-demo-plan\\web\\styles.css",
    "line": 23,
    "snippet": "font-size: 1.1rem is off the DESIGN.md type ramp",
    "advisory": true,
    "ignoreValue": "1.1rem",
    "importedBy": [
      "main.tsx"
    ]
  },
  {
    "antipattern": "design-system-font-size",
    "name": "Font size outside DESIGN.md",
    "description": "A literal font-size is off the type ramp documented in DESIGN.md typography. Use a documented size step or update the design system if the new step is intentional.",
    "severity": "advisory",
    "category": "quality",
    "file": "C:\\Users\\ADK\\.codex\\worktrees\\gtm-landing-demo-plan\\web\\styles.css",
    "line": 23,
    "snippet": "font-size: .75rem is off the DESIGN.md type ramp",
    "advisory": true,
    "ignoreValue": ".75rem",
    "importedBy": [
      "main.tsx"
    ]
  },
  {
    "antipattern": "design-system-font-size",
    "name": "Font size outside DESIGN.md",
    "description": "A literal font-size is off the type ramp documented in DESIGN.md typography. Use a documented size step or update the design system if the new step is intentional.",
    "severity": "advisory",
    "category": "quality",
    "file": "C:\\Users\\ADK\\.codex\\worktrees\\gtm-landing-demo-plan\\web\\styles.css",
    "line": 27,
    "snippet": "font-size: .875rem is off the DESIGN.md type ramp",
    "advisory": true,
    "ignoreValue": ".875rem",
    "importedBy": [
      "main.tsx"
    ]
  },
  {
    "antipattern": "design-system-font-size",
    "name": "Font size outside DESIGN.md",
    "description": "A literal font-size is off the type ramp documented in DESIGN.md typography. Use a documented size step or update the design system if the new step is intentional.",
    "severity": "advisory",
    "category": "quality",
    "file": "C:\\Users\\ADK\\.codex\\worktrees\\gtm-landing-demo-plan\\web\\styles.css",
    "line": 31,
    "snippet": "font-size: clamp(36px,4.2vw,58px) has fluid endpoints 36px and 58px off the DESIGN.md type ramp",
    "advisory": true,
    "ignoreValue": "36px",
    "importedBy": [
      "main.tsx"
    ]
  },
  {
    "antipattern": "design-system-font-size",
    "name": "Font size outside DESIGN.md",
    "description": "A literal font-size is off the type ramp documented in DESIGN.md typography. Use a documented size step or update the design system if the new step is intentional.",
    "severity": "advisory",
    "category": "quality",
    "file": "C:\\Users\\ADK\\.codex\\worktrees\\gtm-landing-demo-plan\\web\\styles.css",
    "line": 36,
    "snippet": "font-size: 1.0625rem is off the DESIGN.md type ramp",
    "advisory": true,
    "ignoreValue": "1.0625rem",
    "importedBy": [
      "main.tsx"
    ]
  },
  {
    "antipattern": "design-system-font-size",
    "name": "Font size outside DESIGN.md",
    "description": "A literal font-size is off the type ramp documented in DESIGN.md typography. Use a documented size step or update the design system if the new step is intentional.",
    "severity": "advisory",
    "category": "quality",
    "file": "C:\\Users\\ADK\\.codex\\worktrees\\gtm-landing-demo-plan\\web\\styles.css",
    "line": 36,
    "snippet": "font-size: .875rem is off the DESIGN.md type ramp",
    "advisory": true,
    "ignoreValue": ".875rem",
    "importedBy": [
      "main.tsx"
    ]
  },
  {
    "antipattern": "design-system-color",
    "name": "Color outside DESIGN.md",
    "description": "A literal color is outside the DESIGN.md palette and sidecar tonal ramps. This may be legitimate, but it should be an intentional design-system addition rather than drift.",
    "severity": "advisory",
    "category": "quality",
    "file": "C:\\Users\\ADK\\.codex\\worktrees\\gtm-landing-demo-plan\\web\\styles.css",
    "line": 37,
    "snippet": "Undocumented color #e9e5dc is outside DESIGN.md colors",
    "advisory": true,
    "ignoreValue": "#e9e5dc",
    "importedBy": [
      "main.tsx"
    ]
  },
  {
    "antipattern": "design-system-font-size",
    "name": "Font size outside DESIGN.md",
    "description": "A literal font-size is off the type ramp documented in DESIGN.md typography. Use a documented size step or update the design system if the new step is intentional.",
    "severity": "advisory",
    "category": "quality",
    "file": "C:\\Users\\ADK\\.codex\\worktrees\\gtm-landing-demo-plan\\web\\styles.css",
    "line": 38,
    "snippet": "font-size: .75rem is off the DESIGN.md type ramp",
    "advisory": true,
    "ignoreValue": ".75rem",
    "importedBy": [
      "main.tsx"
    ]
  },
  {
    "antipattern": "design-system-font-size",
    "name": "Font size outside DESIGN.md",
    "description": "A literal font-size is off the type ramp documented in DESIGN.md typography. Use a documented size step or update the design system if the new step is intentional.",
    "severity": "advisory",
    "category": "quality",
    "file": "C:\\Users\\ADK\\.codex\\worktrees\\gtm-landing-demo-plan\\web\\styles.css",
    "line": 38,
    "snippet": "font-size: .6875rem is off the DESIGN.md type ramp",
    "advisory": true,
    "ignoreValue": ".6875rem",
    "importedBy": [
      "main.tsx"
    ]
  },
  {
    "antipattern": "design-system-font-size",
    "name": "Font size outside DESIGN.md",
    "description": "A literal font-size is off the type ramp documented in DESIGN.md typography. Use a documented size step or update the design system if the new step is intentional.",
    "severity": "advisory",
    "category": "quality",
    "file": "C:\\Users\\ADK\\.codex\\worktrees\\gtm-landing-demo-plan\\web\\styles.css",
    "line": 39,
    "snippet": "font-size: .875rem is off the DESIGN.md type ramp",
    "advisory": true,
    "ignoreValue": ".875rem",
    "importedBy": [
      "main.tsx"
    ]
  },
  {
    "antipattern": "design-system-radius",
    "name": "Radius outside DESIGN.md",
    "description": "A border-radius value is outside the DESIGN.md rounded scale. Use a documented radius token or update the design system if the new shape is intentional.",
    "severity": "advisory",
    "category": "quality",
    "file": "C:\\Users\\ADK\\.codex\\worktrees\\gtm-landing-demo-plan\\web\\styles.css",
    "line": 40,
    "snippet": "border-radius: 5px is outside the DESIGN.md rounded scale",
    "advisory": true,
    "ignoreValue": "5px",
    "importedBy": [
      "main.tsx"
    ]
  },
  {
    "antipattern": "design-system-font-size",
    "name": "Font size outside DESIGN.md",
    "description": "A literal font-size is off the type ramp documented in DESIGN.md typography. Use a documented size step or update the design system if the new step is intentional.",
    "severity": "advisory",
    "category": "quality",
    "file": "C:\\Users\\ADK\\.codex\\worktrees\\gtm-landing-demo-plan\\web\\styles.css",
    "line": 42,
    "snippet": "font-size: 32px is off the DESIGN.md type ramp",
    "advisory": true,
    "ignoreValue": "32px",
    "importedBy": [
      "main.tsx"
    ]
  },
  {
    "antipattern": "design-system-font-size",
    "name": "Font size outside DESIGN.md",
    "description": "A literal font-size is off the type ramp documented in DESIGN.md typography. Use a documented size step or update the design system if the new step is intentional.",
    "severity": "advisory",
    "category": "quality",
    "file": "C:\\Users\\ADK\\.codex\\worktrees\\gtm-landing-demo-plan\\web\\styles.css",
    "line": 42,
    "snippet": "font-size: 38px is off the DESIGN.md type ramp",
    "advisory": true,
    "ignoreValue": "38px",
    "importedBy": [
      "main.tsx"
    ]
  },
  {
    "antipattern": "design-system-font-size",
    "name": "Font size outside DESIGN.md",
    "description": "A literal font-size is off the type ramp documented in DESIGN.md typography. Use a documented size step or update the design system if the new step is intentional.",
    "severity": "advisory",
    "category": "quality",
    "file": "C:\\Users\\ADK\\.codex\\worktrees\\gtm-landing-demo-plan\\web\\styles.css",
    "line": 42,
    "snippet": "font-size: .75rem is off the DESIGN.md type ramp",
    "advisory": true,
    "ignoreValue": ".75rem",
    "importedBy": [
      "main.tsx"
    ]
  },
  {
    "antipattern": "design-system-font-size",
    "name": "Font size outside DESIGN.md",
    "description": "A literal font-size is off the type ramp documented in DESIGN.md typography. Use a documented size step or update the design system if the new step is intentional.",
    "severity": "advisory",
    "category": "quality",
    "file": "C:\\Users\\ADK\\.codex\\worktrees\\gtm-landing-demo-plan\\web\\styles.css",
    "line": 43,
    "snippet": "font-size: 34px is off the DESIGN.md type ramp",
    "advisory": true,
    "ignoreValue": "34px",
    "importedBy": [
      "main.tsx"
    ]
  },
  {
    "antipattern": "design-system-font-size",
    "name": "Font size outside DESIGN.md",
    "description": "A literal font-size is off the type ramp documented in DESIGN.md typography. Use a documented size step or update the design system if the new step is intentional.",
    "severity": "advisory",
    "category": "quality",
    "file": "C:\\Users\\ADK\\.codex\\worktrees\\gtm-landing-demo-plan\\web\\styles.css",
    "line": 46,
    "snippet": "font-size: 2rem is off the DESIGN.md type ramp",
    "advisory": true,
    "ignoreValue": "2rem",
    "importedBy": [
      "main.tsx"
    ]
  },
  {
    "antipattern": "design-system-font-size",
    "name": "Font size outside DESIGN.md",
    "description": "A literal font-size is off the type ramp documented in DESIGN.md typography. Use a documented size step or update the design system if the new step is intentional.",
    "severity": "advisory",
    "category": "quality",
    "file": "C:\\Users\\ADK\\.codex\\worktrees\\gtm-landing-demo-plan\\web\\styles.css",
    "line": 46,
    "snippet": "font-size: .875rem is off the DESIGN.md type ramp",
    "advisory": true,
    "ignoreValue": ".875rem",
    "importedBy": [
      "main.tsx"
    ]
  },
  {
    "antipattern": "design-system-font-size",
    "name": "Font size outside DESIGN.md",
    "description": "A literal font-size is off the type ramp documented in DESIGN.md typography. Use a documented size step or update the design system if the new step is intentional.",
    "severity": "advisory",
    "category": "quality",
    "file": "C:\\Users\\ADK\\.codex\\worktrees\\gtm-landing-demo-plan\\web\\styles.css",
    "line": 46,
    "snippet": "font-size: .75rem is off the DESIGN.md type ramp",
    "advisory": true,
    "ignoreValue": ".75rem",
    "importedBy": [
      "main.tsx"
    ]
  },
  {
    "antipattern": "design-system-font-size",
    "name": "Font size outside DESIGN.md",
    "description": "A literal font-size is off the type ramp documented in DESIGN.md typography. Use a documented size step or update the design system if the new step is intentional.",
    "severity": "advisory",
    "category": "quality",
    "file": "C:\\Users\\ADK\\.codex\\worktrees\\gtm-landing-demo-plan\\web\\styles.css",
    "line": 47,
    "snippet": "font-size: 1.75rem is off the DESIGN.md type ramp",
    "advisory": true,
    "ignoreValue": "1.75rem",
    "importedBy": [
      "main.tsx"
    ]
  },
  {
    "antipattern": "design-system-font-size",
    "name": "Font size outside DESIGN.md",
    "description": "A literal font-size is off the type ramp documented in DESIGN.md typography. Use a documented size step or update the design system if the new step is intentional.",
    "severity": "advisory",
    "category": "quality",
    "file": "C:\\Users\\ADK\\.codex\\worktrees\\gtm-landing-demo-plan\\web\\styles.css",
    "line": 49,
    "snippet": "font-size: .6875rem is off the DESIGN.md type ramp",
    "advisory": true,
    "ignoreValue": ".6875rem",
    "importedBy": [
      "main.tsx"
    ]
  },
  {
    "antipattern": "design-system-color",
    "name": "Color outside DESIGN.md",
    "description": "A literal color is outside the DESIGN.md palette and sidecar tonal ramps. This may be legitimate, but it should be an intentional design-system addition rather than drift.",
    "severity": "advisory",
    "category": "quality",
    "file": "C:\\Users\\ADK\\.codex\\worktrees\\gtm-landing-demo-plan\\web\\styles.css",
    "line": 55,
    "snippet": "Undocumented color #a33224 is outside DESIGN.md colors",
    "advisory": true,
    "ignoreValue": "#a33224",
    "importedBy": [
      "main.tsx"
    ]
  },
  {
    "antipattern": "design-system-color",
    "name": "Color outside DESIGN.md",
    "description": "A literal color is outside the DESIGN.md palette and sidecar tonal ramps. This may be legitimate, but it should be an intentional design-system addition rather than drift.",
    "severity": "advisory",
    "category": "quality",
    "file": "C:\\Users\\ADK\\.codex\\worktrees\\gtm-landing-demo-plan\\web\\styles.css",
    "line": 56,
    "snippet": "Undocumented color #84291e is outside DESIGN.md colors",
    "advisory": true,
    "ignoreValue": "#84291e",
    "importedBy": [
      "main.tsx"
    ]
  },
  {
    "antipattern": "design-system-radius",
    "name": "Radius outside DESIGN.md",
    "description": "A border-radius value is outside the DESIGN.md rounded scale. Use a documented radius token or update the design system if the new shape is intentional.",
    "severity": "advisory",
    "category": "quality",
    "file": "C:\\Users\\ADK\\.codex\\worktrees\\gtm-landing-demo-plan\\web\\styles.css",
    "line": 66,
    "snippet": "border-radius: 4px is outside the DESIGN.md rounded scale",
    "advisory": true,
    "ignoreValue": "4px",
    "importedBy": [
      "main.tsx"
    ]
  },
  {
    "antipattern": "design-system-font-size",
    "name": "Font size outside DESIGN.md",
    "description": "A literal font-size is off the type ramp documented in DESIGN.md typography. Use a documented size step or update the design system if the new step is intentional.",
    "severity": "advisory",
    "category": "quality",
    "file": "C:\\Users\\ADK\\.codex\\worktrees\\gtm-landing-demo-plan\\web\\styles.css",
    "line": 114,
    "snippet": "font-size: .875rem is off the DESIGN.md type ramp",
    "advisory": true,
    "ignoreValue": ".875rem",
    "importedBy": [
      "main.tsx"
    ]
  },
  {
    "antipattern": "design-system-font-size",
    "name": "Font size outside DESIGN.md",
    "description": "A literal font-size is off the type ramp documented in DESIGN.md typography. Use a documented size step or update the design system if the new step is intentional.",
    "severity": "advisory",
    "category": "quality",
    "file": "C:\\Users\\ADK\\.codex\\worktrees\\gtm-landing-demo-plan\\web\\styles.css",
    "line": 119,
    "snippet": "font-size: 1.125rem is off the DESIGN.md type ramp",
    "advisory": true,
    "ignoreValue": "1.125rem",
    "importedBy": [
      "main.tsx"
    ]
  },
  {
    "antipattern": "design-system-font-size",
    "name": "Font size outside DESIGN.md",
    "description": "A literal font-size is off the type ramp documented in DESIGN.md typography. Use a documented size step or update the design system if the new step is intentional.",
    "severity": "advisory",
    "category": "quality",
    "file": "C:\\Users\\ADK\\.codex\\worktrees\\gtm-landing-demo-plan\\web\\styles.css",
    "line": 119,
    "snippet": "font-size: clamp(2rem,3.5vw,3rem) has fluid endpoints 2rem and 3rem off the DESIGN.md type ramp",
    "advisory": true,
    "ignoreValue": "2rem",
    "importedBy": [
      "main.tsx"
    ]
  },
  {
    "antipattern": "design-system-font-size",
    "name": "Font size outside DESIGN.md",
    "description": "A literal font-size is off the type ramp documented in DESIGN.md typography. Use a documented size step or update the design system if the new step is intentional.",
    "severity": "advisory",
    "category": "quality",
    "file": "C:\\Users\\ADK\\.codex\\worktrees\\gtm-landing-demo-plan\\web\\styles.css",
    "line": 119,
    "snippet": "font-size: .875rem is off the DESIGN.md type ramp",
    "advisory": true,
    "ignoreValue": ".875rem",
    "importedBy": [
      "main.tsx"
    ]
  },
  {
    "antipattern": "design-system-font-size",
    "name": "Font size outside DESIGN.md",
    "description": "A literal font-size is off the type ramp documented in DESIGN.md typography. Use a documented size step or update the design system if the new step is intentional.",
    "severity": "advisory",
    "category": "quality",
    "file": "C:\\Users\\ADK\\.codex\\worktrees\\gtm-landing-demo-plan\\web\\styles.css",
    "line": 119,
    "snippet": "font-size: 1.625rem is off the DESIGN.md type ramp",
    "advisory": true,
    "ignoreValue": "1.625rem",
    "importedBy": [
      "main.tsx"
    ]
  },
  {
    "antipattern": "design-system-font-size",
    "name": "Font size outside DESIGN.md",
    "description": "A literal font-size is off the type ramp documented in DESIGN.md typography. Use a documented size step or update the design system if the new step is intentional.",
    "severity": "advisory",
    "category": "quality",
    "file": "C:\\Users\\ADK\\.codex\\worktrees\\gtm-landing-demo-plan\\web\\styles.css",
    "line": 119,
    "snippet": "font-size: .75rem is off the DESIGN.md type ramp",
    "advisory": true,
    "ignoreValue": ".75rem",
    "importedBy": [
      "main.tsx"
    ]
  },
  {
    "antipattern": "design-system-font-size",
    "name": "Font size outside DESIGN.md",
    "description": "A literal font-size is off the type ramp documented in DESIGN.md typography. Use a documented size step or update the design system if the new step is intentional.",
    "severity": "advisory",
    "category": "quality",
    "file": "C:\\Users\\ADK\\.codex\\worktrees\\gtm-landing-demo-plan\\web\\styles.css",
    "line": 120,
    "snippet": "font-size: 2rem is off the DESIGN.md type ramp",
    "advisory": true,
    "ignoreValue": "2rem",
    "importedBy": [
      "main.tsx"
    ]
  },
  {
    "antipattern": "design-system-font-size",
    "name": "Font size outside DESIGN.md",
    "description": "A literal font-size is off the type ramp documented in DESIGN.md typography. Use a documented size step or update the design system if the new step is intentional.",
    "severity": "advisory",
    "category": "quality",
    "file": "C:\\Users\\ADK\\.codex\\worktrees\\gtm-landing-demo-plan\\web\\styles.css",
    "line": 121,
    "snippet": "font-size: 1.75rem is off the DESIGN.md type ramp",
    "advisory": true,
    "ignoreValue": "1.75rem",
    "importedBy": [
      "main.tsx"
    ]
  },
  {
    "antipattern": "design-system-font-size",
    "name": "Font size outside DESIGN.md",
    "description": "A literal font-size is off the type ramp documented in DESIGN.md typography. Use a documented size step or update the design system if the new step is intentional.",
    "severity": "advisory",
    "category": "quality",
    "file": "C:\\Users\\ADK\\.codex\\worktrees\\gtm-landing-demo-plan\\web\\styles.css",
    "line": 121,
    "snippet": "font-size: 1.5rem is off the DESIGN.md type ramp",
    "advisory": true,
    "ignoreValue": "1.5rem",
    "importedBy": [
      "main.tsx"
    ]
  },
  {
    "antipattern": "design-system-font-size",
    "name": "Font size outside DESIGN.md",
    "description": "A literal font-size is off the type ramp documented in DESIGN.md typography. Use a documented size step or update the design system if the new step is intentional.",
    "severity": "advisory",
    "category": "quality",
    "file": "C:\\Users\\ADK\\.codex\\worktrees\\gtm-landing-demo-plan\\web\\styles.css",
    "line": 124,
    "snippet": "font-size: 1.125rem is off the DESIGN.md type ramp",
    "advisory": true,
    "ignoreValue": "1.125rem",
    "importedBy": [
      "main.tsx"
    ]
  },
  {
    "antipattern": "design-system-font-size",
    "name": "Font size outside DESIGN.md",
    "description": "A literal font-size is off the type ramp documented in DESIGN.md typography. Use a documented size step or update the design system if the new step is intentional.",
    "severity": "advisory",
    "category": "quality",
    "file": "C:\\Users\\ADK\\.codex\\worktrees\\gtm-landing-demo-plan\\web\\styles.css",
    "line": 124,
    "snippet": "font-size: .75rem is off the DESIGN.md type ramp",
    "advisory": true,
    "ignoreValue": ".75rem",
    "importedBy": [
      "main.tsx"
    ]
  },
  {
    "antipattern": "design-system-font-size",
    "name": "Font size outside DESIGN.md",
    "description": "A literal font-size is off the type ramp documented in DESIGN.md typography. Use a documented size step or update the design system if the new step is intentional.",
    "severity": "advisory",
    "category": "quality",
    "file": "C:\\Users\\ADK\\.codex\\worktrees\\gtm-landing-demo-plan\\web\\styles.css",
    "line": 124,
    "snippet": "font-size: .875rem is off the DESIGN.md type ramp",
    "advisory": true,
    "ignoreValue": ".875rem",
    "importedBy": [
      "main.tsx"
    ]
  },
  {
    "antipattern": "design-system-font-size",
    "name": "Font size outside DESIGN.md",
    "description": "A literal font-size is off the type ramp documented in DESIGN.md typography. Use a documented size step or update the design system if the new step is intentional.",
    "severity": "advisory",
    "category": "quality",
    "file": "C:\\Users\\ADK\\.codex\\worktrees\\gtm-landing-demo-plan\\web\\styles.css",
    "line": 130,
    "snippet": "font-size: 1.125rem is off the DESIGN.md type ramp",
    "advisory": true,
    "ignoreValue": "1.125rem",
    "importedBy": [
      "main.tsx"
    ]
  },
  {
    "antipattern": "design-system-font-size",
    "name": "Font size outside DESIGN.md",
    "description": "A literal font-size is off the type ramp documented in DESIGN.md typography. Use a documented size step or update the design system if the new step is intentional.",
    "severity": "advisory",
    "category": "quality",
    "file": "C:\\Users\\ADK\\.codex\\worktrees\\gtm-landing-demo-plan\\web\\styles.css",
    "line": 130,
    "snippet": "font-size: .875rem is off the DESIGN.md type ramp",
    "advisory": true,
    "ignoreValue": ".875rem",
    "importedBy": [
      "main.tsx"
    ]
  },
  {
    "antipattern": "design-system-font-size",
    "name": "Font size outside DESIGN.md",
    "description": "A literal font-size is off the type ramp documented in DESIGN.md typography. Use a documented size step or update the design system if the new step is intentional.",
    "severity": "advisory",
    "category": "quality",
    "file": "C:\\Users\\ADK\\.codex\\worktrees\\gtm-landing-demo-plan\\web\\styles.css",
    "line": 134,
    "snippet": "font-size: .875rem is off the DESIGN.md type ramp",
    "advisory": true,
    "ignoreValue": ".875rem",
    "importedBy": [
      "main.tsx"
    ]
  },
  {
    "antipattern": "design-system-font-size",
    "name": "Font size outside DESIGN.md",
    "description": "A literal font-size is off the type ramp documented in DESIGN.md typography. Use a documented size step or update the design system if the new step is intentional.",
    "severity": "advisory",
    "category": "quality",
    "file": "C:\\Users\\ADK\\.codex\\worktrees\\gtm-landing-demo-plan\\web\\styles.css",
    "line": 136,
    "snippet": "font-size: .75rem is off the DESIGN.md type ramp",
    "advisory": true,
    "ignoreValue": ".75rem",
    "importedBy": [
      "main.tsx"
    ]
  },
  {
    "antipattern": "design-system-font-size",
    "name": "Font size outside DESIGN.md",
    "description": "A literal font-size is off the type ramp documented in DESIGN.md typography. Use a documented size step or update the design system if the new step is intentional.",
    "severity": "advisory",
    "category": "quality",
    "file": "C:\\Users\\ADK\\.codex\\worktrees\\gtm-landing-demo-plan\\web\\styles.css",
    "line": 137,
    "snippet": "font-size: .875rem is off the DESIGN.md type ramp",
    "advisory": true,
    "ignoreValue": ".875rem",
    "importedBy": [
      "main.tsx"
    ]
  }
]
```
