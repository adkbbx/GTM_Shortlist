# Build brief: alive public landing, live research and large screens

17 October 2026. Branch `claude/alive-landing-brief`, based on `codex/landing-demo-plan` at `589fccd`. Audience: the implementing agent (Codex). This brief is a plan with a working prototype; it does not change application code.

Prototype: [`prototype/index.html`](prototype/index.html) (public landing) and [`prototype/research.html`](prototype/research.html) (research in progress). Open either file directly in a browser; no build step. Add `?motion=reduce` to see the reduced-motion version. All companies, passages and the research run in the prototype are synthetic and labelled.

## 1. Decisions

Recorded from the user's requests on 17 October. Items 1 and 2 were proposed in review and the user asked to proceed with the brief and prototype; reverse them here if that reading is wrong.

1. **The public landing page and the demo use the full Eygentic visual language and expressive motion.** That means the drafting grid, sharp ruled panels, charcoal linework that draws itself, hand-lettered notes, the two-tone uppercase headline and the rust button ledge. The signed-in research workspace keeps its calm treatment, except for the live-progress changes in section 5. `DESIGN.md` is amended accordingly (section 8).
2. **Hosted, anonymous visitors see the landing page at `/`, not the sign-in form.** Sign-in moves to a header link. A company typed on the landing page survives signup and email confirmation.
3. **The landing page uses Lenis smooth scrolling**, matching usealia.com's feel. Only the public landing page uses it.
4. **Research in progress must look and feel like an agent is working**, with colour-coded checkpoint states (passed, failed, working, needs you, reused, upcoming), always paired with a glyph and a word.
5. **Layouts must hold on large screens.** The app currently breaks on every viewport wider than 1680 px, including 1920×1080 monitors (section 6).

The local, open-source start page stays as it is, apart from the shared large-screen fixes.

## 2. Why the current pages feel lifeless

Observed in the isolated preview (port 8031, synthetic providers) and on the live hosted site as an anonymous visitor:

- **Hosted root.** It shows only a sign-in card and three lines of pitch, with no illustration, SVG, canvas or motion.
- **Branch start page.** Mostly empty paper: a two-line headline, one field, and a 300×234 px calibration drawing whose WebGL scan stops after 4 s.
- **Demo page.** A column of identical white rounded panels with small text, which reads like a form wizard.
- **Live research.** Frames 1 s and 10 s apart are identical. The only motion is a pulse on one 20 px mark, and the checkpoint list sits below the fold. `SavedMark` draws tick, cross and dot all in `currentColor`, so passed, failed and waiting look the same.
- **Brand gap.** Eygentic's character (grid, blueprint drawings, hand notes, sharp panels, draw-in motion) was replaced by generic rounded white cards on beige.

## 3. Measured references

Taken from instrumented captures on 17 October. Use these as starting values, not as a licence to copy.

| Source | Pattern | Values |
|---|---|---|
| eygentic.com | Motion tokens | ease `cubic-bezier(.2,.7,.2,1)`; `drawLine` .6 s (stroke-dashoffset); `pinIn` .3 s (scale .4→1); `moduleIn` .4 s; `buttonRipple` .6 s; `plumeIgnite` 1.8 s |
| eygentic.com | Drawing style | charcoal 1.4 px strokes with round caps; leaders .9 px with orange pins; construction lines apricot .8 px dashed `10 4 2 4`; grid 40 px at `rgba(106,52,23,.055)`; hand notes in Architects Daughter, uppercase, rotated −8° |
| eygentic.com | Buttons | 2 px radius, 52 px minimum height; primary `#b4501c` on a `0 2px 0 #6a3417` ledge; hover lifts 2 px with a 4 px ledge; arrow slides 3 px |
| Explee | Hero lines | Canvas S-curves into the input. Hovering the field animates a speed value to 24× over 1 s with `easeInOut`, and back over 1 s on leave. Lines draw in with `setLineDash` over 1.2 s |
| Explee | Text swap | Chunks leave 40 px up with a 4 px blur and arrive 40 px from below; 420 ms each, 90 ms stagger, entry starts 520 ms after exit |
| usealia.com | Smooth scroll | Lenis; scenes are pure functions of scroll position, so they reverse on scroll-up |
| usealia.com | Word reveal | `.reveal-word`: opacity, `blur(.1em)` and `translateY(.1875em)` over 450 ms, delay `--w × 65ms` |
| usealia.com | Scroll typing | A sentence split into word spans; a soft opacity front about 4 words wide; fully revealed over about 250 px of scroll |

## 4. Public landing page (hosted)

### 4.1 Routing and auth

- **Hosted mode, no session:** render `PublicLanding` at `/`. Keep sign-in, signup and recovery reachable through the header "Sign in" link (for example `/?auth=signin`) and every existing auth route.
- **Signed-in hosted users:** go straight to the workspace, as today.
- **Local mode:** unchanged.
- **Start research while anonymous:** open the account sheet inline under the field (prototype: "Save this research to an account", with the typed company shown as "Company kept").
  - Store the company with the existing tab-local company recovery used by the demo page, scoped to the account once signed in.
  - After signup, email confirmation and the redirect, return to the workspace with the field filled in. Never start research automatically: the visitor still presses Start research and confirms the target.
- **No change** to credits, one-active-run checks, target confirmation or provider calls.

### 4.2 Visual system for public pages

Scope these rules to the landing page and demo (for example under `.public` or a separate stylesheet).

- **Tokens.** Add eygentic's palette to the existing tokens: paper `#f7f7f5`, peach `#f6e0d3`, apricot `#e4a07b`, orange `#d5682f`, orange-ink `#b4501c`, rust `#6a3417`, charcoal `#1b1b1b`, line `rgba(27,27,27,.16)`, line-soft `rgba(27,27,27,.09)`, grid `rgba(106,52,23,.055)`.
- **Type.**
  - Schibsted Grotesk (already bundled).
  - Add Architects Daughter for hand notes only. Self-host it with `@fontsource/architects-daughter` or a local woff2; no third-party font request in production.
  - Hero headline: weight 800, uppercase, `letter-spacing -.035em`, line-height .98, `clamp(2.75rem, 1.4rem + 3.4vw, 5.25rem)`, second line in orange-ink.
- **Surfaces.** Sharp 2 px panels with a 1 px charcoal rule. No rounded white cards, gradients, glass or ambient shadows. The button ledge is the only shadow.
- **Grid.** The page background is the 40 px drafting grid (2.5 rem so it scales).
- **Status colours** (shared with section 5): ok `#1f7a4d`/`#e2f1e7`, fail `#b3261e`/`#fbe7e4`, work `#b4501c`/`#f6e0d3`, you `#2457a6`/`#e4ecf8`, reuse `#1f6f6a`/`#e0f0ee`, idle `#8a857d`. Every use pairs the colour with a glyph and a visible word.

### 4.3 Smooth scroll

- **Package.** `lenis@1.3.26`, pinned (MIT, released 5 August 2026). Do not take 1.3.27 until it is at least two weeks old.
- **Setup.** Create it in a `useLenis` hook mounted only by `PublicLanding`. Call `destroy()` on unmount and before navigating into the workspace. Options: `{ autoRaf: true, lerp: 0.1, anchors: { offset: -72 } }`. Import `lenis/dist/lenis.css`.
- **Reduced motion.** Do not create Lenis at all under `prefers-reduced-motion: reduce`; use native scrolling.
- **Inner scrolling.** Add `data-lenis-prevent` to anything that scrolls inside the page: suggestion list, account sheet, modals.
- **Scroll lock.** Make `usePageScrollLock` call `lenis.stop()` and `lenis.start()` when a Lenis instance exists.
- **Scroll progress.** Drive scroll-linked scenes from one listener: `lenis.on('scroll')`, or the native scroll event when Lenis is absent.

### 4.4 Sections

Follow the prototype's order, copy and behaviour.

1. **Header.** Sticky, paper background at 92% opacity. A 1 px bottom rule fades in after 20 px of scroll. Wordmark, then the links How it works · What you get · Open source, then "Sign in", then the primary button "Start research →", which scrolls to the field and focuses it.
2. **Hero.** Two columns, the left about 1.08fr.
   - **Text and form.** Label "Company research for B2B sellers", then the headline "Find who fits. / Check why." with a word reveal on load. Body copy and the company form follow, reusing the existing `CompanySearch` combobox restyled to sharp panels.
   - **Flow lines** (canvas behind the hero):
     - nine grey S-curves rise from the bottom edge into the field's lower edge;
     - five orange curves run from the field's right edge up into the machine's hopper.
   - **Dots.** About 3 per curve, 3–3.5 px squares. 22% are orange. Each fades over the first 1/8 and last 1/6 of its curve.
   - **Speed.** Ease toward the target with `1 − e^(−3.2·dt)`. Base `0.045` curve-lengths per second. Hovering or focusing the field sets 12×; each keystroke sets 24× for 1.2 s.
   - **Line draw-in.** Over 1.4 s with an ease-out cubic.
   - **Performance and fallback.** Cap the device-pixel ratio at 1.5. Pause when offscreen or the tab is hidden. Under reduced motion, draw one static frame.
   - **Shortlist machine** (inline SVG, right column; see the prototype for geometry): hopper "Your website" → OFFER sheet → TARGET dial → EVIDENCE sheet with a magnifier → output tray.
     - The tray holds three status cards: "Fits · supported", "Needs a call", "Not a fit".
     - Labels sit on leader lines with orange pins. A dashed apricot centreline and a rotated "One research run" dimension complete the blueprint.
     - The drawing draws in on first view: strokes over .9 s with eygentic's ease, staggered about 0–2 s; pins pop; modules fade.
     - The dial's ticks rotate with the flow speed.
     - A hand note reads "Site → offer → target → evidence → you".
3. **"How a shortlist gets made".** A pinned scroll story.
   - **Pin.** The section is 680 vh tall on desktop and 760 vh on phones. A sticky frame below the header holds the title, the trace line, the stage content and a six-part progress bar.
   - **Stage weights.** Offer 1, Market 1.1, Target 1.1, Companies 1.3, Evidence 2, Decision 1.3. Evidence gets the most scroll.
   - **Trace line.** A dashed apricot base line. A 3 px orange-ink run line draws to the current station, then creeps toward the next one over the last 45% of a stage.
     - Each station is a 26 px ring with a line icon. Finished stations get a green pin; the current one pulses orange, or blue at "Target".
     - At Companies the line forks into three branches ending in a red ✕, a blue +, and the main line.
   - **Stage switching.** Stage text and card cross-fade over 280 ms with an 8 px rise. Each element inside a card appears at a set point of local progress (the `data-at` values in the prototype).
   - **Stage contents:**
     - **Offer:** the page is saved, then the offer draft and the Edit buttons.
     - **Market:** two observations, one failed page and one hypothesis, each with its pill.
     - **Target:** the criteria. At 62%, "Confirm target" presses and a blue "Confirmed by you" stamp lands.
     - **Companies:** three rows arrive with spinners, then resolve to Fits (green), Needs a call (blue) and Excluded (red).
     - **Evidence:** a highlighter sweeps the synthetic passage word by word, scrubbed by scroll (Alia's typing technique). A "Supported in source" pill and an "Unknown" row follow.
     - **Decision:** Accept presses and a green "Accepted by you" stamp lands; then the optional email-draft line.
   - **Progress bar.** Its buttons jump to each stage's start.
   - **Phone.** Hide station labels, the hand note and the section label; clamp body text to two lines; place stamps in the flow.
   - **Reduced motion.** No pinning: render all six stages as a static list in their final state.
4. **"What one research run gives you".** A spec-sheet table with Input, Your control, Output, Evidence and Decision rows. Copy is in the prototype and limited to verified product behaviour.
5. **"Open source core. Hosted if you want it."** Two ruled panels with line icons that draw in. Self-host: MIT core, your own keys, your own database. Hosted: saved research, credits, an optional call. No prices.
6. **Closing.** "Stop guessing who fits." swaps with "Start from the source." every 3.2 s, only while visible, using the Explee chunk timings above. Supporting line: "Three companies you can check for yourself beat a list of three hundred you can't." A CTA follows with a second canvas whose 8 lines converge from the bottom edge into the button and speed up on hover.
7. **Footer.** Charcoal, with a large wordmark and the links.

### 4.5 Honesty rules (unchanged product principles)

- No invented counters, testimonials, logos, customer outcomes, live activity or prices.
- Example companies use reserved `.example` domains and every example surface says "Synthetic example".
- The machine's three output cards are illustrations of states, not results. They carry no company names.
- "Fit" is never described as buying intent.

## 5. Live research progress ("agent at work")

### 5.1 Status system

Replace `SavedMark` with a `StatusMark` variant per state. It is a 28 px circle (20 px in dense rows) with a 1.5 px ring, a soft fill and a glyph.

| Status | Source | Colour | Glyph | Word |
|---|---|---|---|---|
| ok | event `succeeded`; stage "Saved" | ok green | tick | Completed / Saved |
| fail | event `failed` | fail red | cross | Failed |
| work | latest event `started`, worker online, page visible | orange-ink, spinning 2 px arc (1 s linear) | none | Working |
| you | event `waiting`; stages "Needs your input" and "Your review" | you blue | exclamation | Needs you |
| reuse | event `reused` | reuse teal | loop arrows | Reused |
| idle | stages "Upcoming", "No saved result", "Not included" | idle grey, dashed ring | none | Upcoming / No saved result / Not included |
| stopped | `run.termination` | charcoal | square | Stopped |

- **"Saved with gaps"** stays ok green with that text as the stage subtitle.
- **Colour never stands alone.** Keep the visible state word on every row, as today.
- **Contrast (computed 17 October).**
  - **State words.** Put them on white or paper, never on the soft fills. Every status colour passes there: ok 5.32, fail 6.54, work 5.12, you 7.03 and reuse 5.93 on white; all at least 4.77 on paper.
  - **Marks.** They need the 3:1 non-text minimum against their soft fill: work on peach is 4.02, the others 4.55–5.91.
  - **Idle grey** `#8a857d` is 3.66 on white. Use it only for rings and glyphs; "Upcoming" text uses `#6f6a63` (5.36) or the existing muted colour.
  - Verify again in CI with axe or a contrast script.

### 5.2 Layout

These are the prototype's `research.html` proportions.

- **Compact run header.**
  - Left: the title and the confirmed target line.
  - Right: "Running for m:ss" (from the first event's `created_at`), "You can leave this page. Research continues and is saved.", and a "Notify me when it's ready" toggle.
- **Stage trace.** A horizontal line with six stations below the header. It uses `StatusMark` states, an orange run line to the current station, and a small orange signal dot that travels from the previous station to the current one while work is happening. Station labels and state words sit below; on phones only the marks show.
- **Body.**
  - At 1280 px and wider: two columns, the agent console (1.2fr) and the checkpoint feed (.8fr).
  - Narrower: stacked.
  - The feed is sticky with its own scroll area, at most `100dvh − 9rem` tall.

### 5.3 Agent console

- **Action line.** The latest event's label, shown large. Words reveal (50 ms stagger, 380 ms) only when a new event id arrives, never on polling the same event.
- **Step timer.** "for m:ss", counted from that event's `created_at`.
- **Live visual.** It changes with the current activity:

  | Activity | Visual |
  |---|---|
  | search | Query chips pop in; candidate rows slide in from the left, newest on top, at most 6 |
  | prioritise / assess | Candidate rows each fill three criteria boxes green, blue or red; the selected rows get an orange border |
  | read | A browser frame showing the domain or URL being read, a page skeleton, and an orange scan line sweeping down every 2.2 s; matched lines get a peach highlight |
  | verify | The claim and its saved passage, with a highlighter sweeping word by word (90 ms per word) |
  | wait / review | "Your turn" and the saved companies with their status pills, plus a primary action |

  - Only show content that exists in saved run data: candidate domains from `run.selection` or progress, passages from `run.records`.
  - When the data is not saved yet, show the skeleton and scan without invented text.
- **Counters.** Use `run.progress.candidates`, `sources` and `companies` (of the selected count). They count up over 500 ms with an ease-out cubic when the value changes.
- **"Saved" strip.** Appears when a verification succeeds, summarising that company's saved findings and unknowns.

### 5.4 Checkpoint feed

- **Contents.** Show every saved event, newest first, grouped under sticky stage headings (from `stagePhases`).
- **Older steps.** Drop the "latest three" limit for the live view. The feed scrolls instead, and "Show older steps" is no longer needed there; keep it in the completed-run recap.
- **Row anatomy.** Each row has a `StatusMark`, a coloured state word, the label, a muted detail and a tabular time.
- **Filters.** Chips for All / Completed / Failed / Working / Needs you / Reused, each with its count.
- **Event arrival.** A new event id slides in from 10 px above (420 ms) with a peach background flash fading over 1.6 s. When a started row's state changes in place, its mark pops (scale 1.25, 350 ms). Events already present on first load do not animate.

### 5.5 Data needed

This is a small, additive API change.

- **New optional fields on `ProgressUpdate`/`ProgressEvent`:**
  - `activity`: `search | assess | read | verify | draft | wait | review`;
  - `subject`: domain or URL, at most 200 characters.
- **Where they come from.** Set both where `step_label()` is computed (`src/shortlist/progress.py`):

  | Worker step | `activity` |
  |---|---|
  | `kind == "search"`, `market:search`, `seller:identity` | search |
  | `kind == "fetch"`, `seller:fetch` | read |
  | `verify:` | verify |
  | `repair:` and other model steps | assess |
  | `seller:model`, `market:campaigns` | draft |
  | waiting events | wait |

  `subject` is the domain or fetched URL already passed to `step_label`.
- **Compatibility.** The UI falls back to the phase when `activity` is absent (older runs). Regenerate `web/generated/*` and the runtime schemas.

### 5.6 Honesty and motion rules (keep and extend the existing ones)

- **Ambient motion** (spinner, scan line, travelling signal, live dot) runs only while `run.status === 'running'`, the worker is online, the latest event is `started`, the page is connected and the document is visible. Otherwise it stops and shows the saved state.
- **Entrance animations** fire only for newly persisted events. Timers come from saved timestamps. No percentages, ETAs or presentation timers.
- **Reduced motion** (OS setting or the existing "Reduce motion" control): no spinner rotation, scan, signal or flashes. State is still shown through colour, glyph and word.
- **Leave and return:**
  - **Tab title.** `● Researching (stage/6) · GTM Shortlist`, then "Ready for review · GTM Shortlist" or "Research stopped · GTM Shortlist".
  - **Notifications.** The toggle asks for browser notification permission on click. Notify once, when the run reaches awaiting review, partial or stopped while the document is hidden. Never ask on page load.

## 6. Large screens

### 6.1 Root cause (measured on the fixture server)

| Viewport | Header x / width | Sidebar x | Main x / width | h1 |
|---|---|---|---|---|
| 1366 | 0 / 1366 | 0 | 224 / 1142 | 54 px |
| 1680 | 0 / 1680 | 0 | 292 / 1320 | 54 px |
| 1920 | **120** / 1680 | **120** | 412 / 1320 | 54 px |
| 2560 | **440** / 1680 | **440** | 732 / 1320 | 54 px |
| 3840 | **1080** / 1680 | **1080** | 1372 / 1320 | 54 px |

- **The frame is capped and centred.** `header.topbar { max-width: 1680px; margin: auto }` in `web/ResearchSidebar.css` and `.workspace { max-width: 1680px }` in `web/styles.css` keep the dark header and sidebar inside a 1,680 px block, while the page background is full width. On any screen above 1680 px, pale strips appear on both sides of the dark frame. At 4K it is a floating L-shape.
- **Sizes are fixed.** Everything is in px, so at 3840 px the content is a 1,320 px island of 16 px text.

### 6.2 Fix

1. **Make the frame full-bleed at every width.**
   - Remove both `max-width: 1680px` caps.
   - The header spans the viewport and the sidebar sits at x = 0.
   - Cap only the reading content inside `main`: `width: min(100%, 82rem)` for forms and sheets. On wide screens the research view may use up to `92rem` for its two columns.
2. **Fluid root size.** Set `html { font-size: clamp(100%, calc(.3125vw + 10.7px), 140%) }`. That gives 16 px up to about 1,700 px wide, 16.7 px at 1920, 18.7 px at 2560 and 22.4 px at 3840.
3. **Convert fixed px to rem.** Covers the header height, sidebar width (224 px → 14 rem), control heights, gaps and type sizes, so the whole UI scales with the root.
   - Keep hairlines at 1 px.
   - Leave the existing small-screen breakpoints as they are, or switch them to `em` media queries so they track the user's font size.
4. **Large-screen tiers.**
   - At 1280 px and up: the two-column research layout (section 5).
   - At 1600 px wide and 860 px tall or more: the landing hero fills the first screen.
   - At 2200 px and up: the landing content width grows to 92 rem.
5. **Canvases and images.** Size canvases from their container. Cap the device-pixel ratio at 1.5. Provide 2× favicon sources or SVG.

### 6.3 Test matrix

- **Viewports:** 320, 390, 768, 1024, 1366×768, 1440×900, 1920×1080, 2560×1440 (a 4K screen at 150% scaling), 3840×2160 (4K at 100%). Also 200% text zoom at 1440.
- **New test file `tests/ui/large-screens.spec.ts`.** At 1920, 2560 and 3840 it asserts:
  - the header starts at x = 0 and spans the viewport;
  - the sidebar starts at x = 0;
  - there is no horizontal overflow;
  - the root font size matches the formula;
  - the research two-column layout is active at 1280 px and above.

## 7. Suggested file plan

- `web/landing/PublicLanding.tsx`, `landing.css`: the sections in 4.4.
- `web/landing/ShortlistMachine.tsx`, `TraceLine.tsx`: blueprint SVGs, ported from the prototype markup.
- `web/landing/FlowLines.ts`: the canvas engine (prototype `shared.js` `FlowLines`) with hover, focus and typing speed, a DPR cap and offscreen pause.
- `web/landing/useLenis.ts`, `useScrollProgress.ts`, `RevealText.tsx`, `useDrawIn.ts`.
- `web/StatusMark.tsx`: shared by `ResearchProgress`, saved history and the landing story.
- `web/AgentConsole.tsx`, `web/CheckpointFeed.tsx`: extracted from `ResearchProgress.tsx`. `research-stages.ts` gains a status-key projection.
- `web/styles.css`, `ResearchSidebar.css`: the full-bleed frame and rem conversion.
- `src/shortlist/progress.py`, `worker.py`: `activity`/`subject` on events. Update the OpenAPI export and generated types.
- `package.json`: add `lenis@1.3.26` and `@fontsource/architects-daughter`. No animation framework is needed. The prototype uses only CSS, SVG, one canvas loop and Lenis.

## 8. DESIGN.md amendment (included in this branch)

`DESIGN.md` gains a section titled "Public pages, live research and large screens, 17 October". It scopes the expressive Eygentic language to the public landing page and demo, adds the status colours and live-progress motion rules, and records the full-bleed frame and fluid sizing. Existing "Don't" rules still apply to the research sheets themselves.

## 9. Acceptance

Before declaring this done:

- Run the existing build, Ruff and tests.
- Exercise the real flows on phone and laptop as `AGENTS.md` requires, and inspect screenshots.

Specifically:

- [ ] An anonymous hosted visit to `/` shows the landing page. Sign-in works from the header. A typed company survives signup, confirmation and the redirect, and research does not start automatically.
- [ ] Lenis is active only on the landing page, absent under reduced motion, and destroyed on entering the workspace. Drawers and modals still lock scrolling.
- [ ] The hero lines speed up on hover, focus and typing and pause offscreen. The machine draws in once. With reduced motion everything is static and fully visible.
- [ ] The pinned story works forward and backward, its progress buttons jump to stages, it fits at 390×844 without clipped cards, and it becomes a static list under reduced motion.
- [ ] The live research view shows the console visual for each activity, colour-coded marks with words, a feed with filters, entrance animation only for new events, and ambient motion only under the worker and visibility conditions above. The tab title and notifications work.
- [ ] At 1920, 2560 and 3840 the frame is edge to edge, there is no horizontal overflow and type scales, verified by `large-screens.spec.ts` and inspected screenshots.
- [ ] Keyboard focus is visible everywhere, there are no `aria-hidden` traps, 200% zoom works and contrast passes.
- [ ] No fabricated data appears outside labelled synthetic examples, and no provider calls are made by the landing page.

## 10. Verified so far (prototype only)

The prototype was checked in Chrome at 390×844, 1440×900, 1920×1080, 2560×1440 and 3840×2160:

- no console errors and no horizontal overflow;
- the root font size computed to 16, 16.7, 18.7 and 22.4 px;
- all six story stages render at desktop and phone sizes;
- the simulated research run completes;
- reduced-motion versions render their final states.

This checks the prototype, not the application. App implementation, CI and user acceptance remain open.
