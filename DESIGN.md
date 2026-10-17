---
name: GTM Shortlist
description: Company discovery and prospect research for B2B sellers
colors:
  paper: "#f7f7f5"
  ink: "#1b1b1b"
  muted: "#64615b"
  orange-ink: "#b4501c"
  orange-hover: "#9b4215"
  rust: "#6a3417"
  rule: "#e1dfd9"
  sidebar: "#201e1b"
  preview: "#efede6"
  field: "#ffffff"
  field-border: "#c4c0b8"
  field-placeholder: "#68635c"
  quiet-selection: "#eeede9"
  text-selection: "#f6e0d3"
  notice-paper: "#faf3ed"
  notice-rule: "#dec9b9"
typography:
  display:
    fontFamily: "Schibsted Grotesk, sans-serif"
    fontSize: "clamp(30px,3.2vw,44px)"
    fontWeight: 700
    lineHeight: 1.12
    letterSpacing: "-.045em"
  title:
    fontFamily: "Schibsted Grotesk, sans-serif"
    fontSize: "1.375rem"
    fontWeight: 700
    lineHeight: 1.3
  body:
    fontFamily: "Schibsted Grotesk, sans-serif"
    fontSize: "1rem"
    fontWeight: 400
    lineHeight: 1.55
  passage:
    fontFamily: "Schibsted Grotesk, sans-serif"
    fontSize: ".9375rem"
    fontWeight: 400
    lineHeight: 1.65
  label:
    fontFamily: "Schibsted Grotesk, sans-serif"
    fontSize: ".9375rem"
    fontWeight: 600
  metadata:
    fontFamily: "Schibsted Grotesk, sans-serif"
    fontSize: ".8125rem"
    fontWeight: 400
rounded:
  control: "8px"
  sheet: "14px"
  preview: "12px"
  notice: "10px"
spacing:
  compact: "8px"
  control-gap: "12px"
  item: "16px"
  gutter-phone: "20px"
  section: "24px"
  sheet: "28px"
  heading: "32px"
components:
  button-primary:
    backgroundColor: "{colors.orange-ink}"
    textColor: "{colors.field}"
    rounded: "{rounded.control}"
    padding: "12px 20px"
  button-primary-hover:
    backgroundColor: "{colors.orange-hover}"
  button-secondary:
    backgroundColor: "{colors.field}"
    textColor: "{colors.ink}"
    rounded: "{rounded.control}"
    padding: "12px 20px"
  button-text:
    textColor: "{colors.orange-ink}"
    padding: "8px 4px"
  input:
    backgroundColor: "{colors.field}"
    textColor: "{colors.ink}"
    rounded: "{rounded.control}"
    padding: "14px 16px"
  research-sheet:
    backgroundColor: "{colors.field}"
    rounded: "{rounded.sheet}"
    padding: "32px"
  source-passage:
    backgroundColor: "{colors.field}"
    textColor: "{colors.ink}"
    typography: "{typography.passage}"
    padding: "16px 20px"
---

# Design System: GTM Shortlist

## Overview

**Creative North Star: "A clear research workspace"**

GTM Shortlist extends Eygentic's identity into the user-authorized modern product workspace. Paper, white surfaces, warm neutral rules, restrained orange, and Schibsted Grotesk create a calm setting for observations, source passages, and independent human review. Rounded controls and research sheets replace the earlier square drafting-sheet treatment.

This document records the latest CSS cascade in `web/styles.css` and the components in `web/main.tsx`, `web/ResearchProgress.tsx`, and `web/ResearchPreview.tsx`. The modern redesign is an explicitly authorized extension of the application system; it supersedes the earlier drafting grid, square sheets, and button ledge. Eygentic's separate marketing website remains its own authority.

**Key Characteristics:**

- Warm paper behind white research surfaces with quiet borders.
- Orange ink identifies actions and active research states.
- Exact source passages remain readable beside labelled unknowns.
- Human review is visually distinct from model qualification.

Inherited authority: [Eygentic design principles](<D:/Code_Projects/New folder/egentic/docs/design.md>) and [source CSS](<D:/Code_Projects/New folder/egentic/src/css/base.css>). The selected application direction is recorded in [docs/ui-direction.md](docs/ui-direction.md).

## Colors

The frontmatter records the implemented palette, including neutral control and notice states. Its CSS values are normative for this workspace.

### Primary

**Orange ink** marks primary actions, actionable links, focus outlines, SVG identity details, and contradicted findings. **Orange hover** darkens primary actions. **Rust** remains the text-action hover color; the button ledge is removed.

**The Action Ink Rule.** Reserve orange for something actionable or a meaningful state; paper and charcoal carry the research itself.

### Neutral

**Paper** covers the main workspace. **Field white** also serves as the header and research-sheet surface. **Sidebar** provides quiet navigation contrast. **Ink** carries body text; **muted** carries dates and descriptions. **Rule** separates findings and surfaces. **Preview** holds explanatory output guidance. The drafting background is removed.

**Field** distinguishes editable controls and quoted passages. **Field border** and **field placeholder** keep input affordances legible. **Quiet selection** marks saved-run selection and secondary hover. **Text selection** uses the inherited peach. **Notice paper** and **notice rule** distinguish an actionable error or limitation with a written explanation.

Supported, contradicted, and unknown findings have explicit text labels. Color never substitutes for a status or review decision. The broader Eygentic illustration palette remains available in its marketing system; unused seed colors are not extracted application tokens.

## Typography

Schibsted Grotesk is locally bundled and used for headings, body, controls, and metadata. The browser sans-serif fallback serves loading failure. No separate display, handwriting, or decorative monospace face is implemented in the workspace.

### Hierarchy

- **Display:** active research uses the frontmatter display role, limited to 26ch. The starting heading uses `clamp(36px,4.2vw,58px)` and 18ch; on phones it is 38px and 16ch, narrowing to 34px below 360px. Active headings are 32px on phones.
- **Title:** company and section headings use the title role. Section headings alone add -.015em tracking.
- **Body:** normal reading text uses the body role, generally no wider than 72ch. The main introduction is limited to 54ch with line-height 1.7.
- **Passage:** exact quotations use the passage role with preserved whitespace and wrapping for long tokens.
- **Label:** form labels use the label role; hints use .875rem.
- **Metadata:** dates and secondary state text use the metadata role. Saved-run metadata uses .75rem. Finding status is .75rem on laptop and .6875rem on phone, adjacent to the full finding title and explanation.

**The Readable Evidence Rule.** Preserve the passage role for source text; do not shrink or capitalize quotations to fit more records.

Sentence case is used for actions, research, and navigation. “Saved runs” now uses normal casing and tracking.

## Layout

The laptop workspace uses a 224px sidebar and a flexible main column, capped at 1680px. The white header is 76px tall. Main content is capped at 1320px with 48px vertical padding and `clamp(24px,4vw,64px)` horizontal padding. Sheets use white, quiet borders, the extracted sheet radius, and a 24px bottom gap. The start view places the seller form beside interactive output guidance at a 1.15:1 ratio.

At 1150px and below, the start grid becomes one column, explanatory content uses an internal two-column arrangement, and main padding becomes 36px by 28px. Existing 1050px rules stack exports and confirmation actions. At 700px and below, the header is 72px, the workspace becomes one column, and main padding is 30px by 20px. Saved runs form a horizontal strip of 170px items. Preview, company identity, and review controls stack. Below 360px, main gutters narrow to 16px.

The background is plain paper with no drafting grid. Laptop saved runs scroll within `calc(100vh - 320px)`. Company research remains a vertical series of sheets, never three compressed columns.

**The Shared Rule Rule.** Use aligned edges and thin separators to organize related research rather than detached dashboard tiles.

## Elevation & Depth

Research surfaces and buttons have no offset or ambient shadows, blur, glass, or layered gradients. White surfaces, paper, warm neutral rules, and hierarchy provide separation. Selected navigation uses an inset orange edge. Focused fields use a restrained 3px translucent orange ring.

Buttons transition state properties over .18s and do not lift on hover; active presses down 1px. Fields transition border and focus ring over .18s. The history chevron rotates with disclosure state; checkpoint pulsing is limited to a started action with a connected online worker. Reduced-motion preferences disable these transitions and pulses. No invented percentages or decorative activity imply progress.

## Shapes

Research sheets and controls use the extracted rounded scale with quiet 1px borders. Primary actions have a minimum height of 52px, inputs 48px, and source disclosures and text actions 44px. Checkbox labels provide a 44px interaction row around a native 20px checkbox. Checkbox inputs reset text-field padding and shadows; focus outlines surround the label row, and high-contrast mode retains native rendering. Keyboard focus is a 2px orange-ink outline with a 4px offset.

The identity mark is thin SVG construction linework. Arrow SVGs accompany navigation and source actions. No glyph icons, pill-shaped dashboards, or ornamental rocket illustrations are implemented.

## Components

### Buttons

Primary actions use orange ink, white text, a 600 weight, and the extracted padding. Secondary actions use white with a warm neutral border and quiet hover fill. Text actions use an orange label without an underline and a warm hover fill. Actual source and website links keep a fine neutral underline that darkens on hover. Disabled actions reduce opacity to .65 and retain their labels. Keyboard focus follows the shared outline treatment.

### Inputs / Fields

White fields have the extracted border and padding, with orange caret and visible focus. Textareas resize vertically. Labels sit above fields, and optional notes appear beside labels on laptop and underneath on phones. Error notices provide text; invalid submitted input remains available for correction.

### Navigation

The saved-run list uses lightly rounded rows with company domain, date, and persisted state. Selection adds white fill and an inset orange edge. Rows do not lift on hover. The phone strip retains the same information in 170px items and supports horizontal scrolling. The new-shortlist control remains separately visible.

### Research sheets

Identity, qualification, findings, hypotheses, and review occupy one white rounded company sheet. Identity and review areas use a subtly tinted white. Finding statuses use restrained neutral or warm fills and explicit labels; unknown retains its dashed rule. Qualification never implies buying intent. Review buttons save a separate human decision and written note.

### Source disclosure

A native details disclosure places the claim first and “Inspect passage” underneath. Opening it reveals the exact quotation on white, followed by a source link, retrieval date, and publication date or a written unknown. The disclosure is inline, keyboard accessible, and preserves the company context.

### Interactive research preview

Evidence and Unknowns are explanatory, selectable views of the output structure. The preview uses neutral selector states and a warm inset surface. It explicitly says it is a guide to the output, not a company result. It must never acquire fabricated company names, claims, or citations.

### Notices

Warm neutral notices contain a written failure, limitation, or corrective action. They wrap long text. A notice is not a fabricated success signal or an ornamental callout.

### Landing demonstration

The no-active-run start page uses `LandingDemo.tsx`, `LandingDemo.css`, and `landing-demo.data.ts` with the existing paper-first identity. The16 October first-visit refinement supersedes the two equally prominent entry buttons. A centered headline and short description lead directly to the company field and one orange "Start research" submit action. "Try the demo" is a quiet optional action below the form. The empty saved-runs sidebar is absent until there is an active run or actual saved history. Existing account controls, error recovery and local operator setup remain available. See docs/planning/landing-demo/ENTRY_ARCHITECTURE.md for the ownership and disclosure decisions.

The sample outcome and repeated method overview are absent from the initial screen. Opening the optional demo reveals one full-width sheet with six stages: understand offer, explore market, confirm target, discover companies, inspect evidence, and review and draft. Desktop uses a left stage rail; at850px and below, a native "All stages" disclosure and one content column replace it. At600px and below the real input and submit stack. Stage buttons use `aria-current="step"`; source inspection stays inline, review remains a separate human choice, and draft edits persist when revisiting stages. Invented companies, reserved `.example` domains, and synthetic passages stay explicitly labelled. The sample module has no research API imports and keeps its decisions and edits local. Opening/closing the demo preserves the real company input and restores focus.

Playback starts on request, pauses at confirmation and evidence, and stops on the result. Manual navigation, pause, resume, and replay remain available. Hidden documents, leaving the viewport after visibility, mouse movement over the scene, and focus on scene controls pause playback until deliberate resume. Existing controls retain 180ms feedback; scenes enter over 280ms with 6px movement, rows over 240ms with 60ms stagger, and passages over 220ms. A single 900ms scan runs only in the playing sample. The OS reduced-motion preference and visible "Reduce motion" control both show the final review stage immediately, disable movement, and preserve readable manual navigation. Real research continues through the existing form, authentication, saved worker progress, and explicit target confirmation.

### Live research stages

`ResearchProgress` extends the same six-stage sheet and motion grammar to each saved run. Its read-only rail follows persisted stage boundaries through `research-stages.ts`. Stage labels distinguish Saved, Saved with gaps, No saved result, Not included, Stopped, and stages that need input. Review and draft ends at "Your review" without accepting a company. Counts show actual saved candidates, company pages, and researched companies. The desktop rail becomes three columns at 850px and two at 700px; existing paper, orange, typography, and control tokens continue to apply.

The scene enters only when the run or actual stage changes; polling the same stage does not replay it. Latest-checkpoint entry follows the persisted event ID. The activity scan and checkpoint pulse require a running run, a latest started event, an online worker, a connected page, and a visible document. The "Reduce motion" control and OS reduced-motion CSS suppress movement while keeping saved content readable. Stages advance through saved work, without presentation timers. Saved checkpoint history exposes outcomes and timestamps, including failures and reused evidence. Website choice, target confirmation, company review, and editable draft forms remain outside the changing scene, preserving their mounted state across polling and keeping human actions explicit.

## Do's and Don'ts

### Compact shortlist review

Results begin with flat company rows showing saved descriptions, separate qualification and human decisions, dated company statements when present, sourced people counts and draft state. Unknown activity remains explicit. Each native details disclosure belongs to the run's exclusive group. Its research sheet stays mounted while closed so unsaved notes and email edits survive switching companies. Back to shortlist restores focus to that row. Completed checkpoints and offer-management controls follow the list. Phone rows stack naturally; the detail reveal respects reduced motion.

### Do

- **Do** use paper, white surfaces, Schibsted Grotesk, quiet borders, and restrained orange ink for new application surfaces.
- **Do** keep exact passages readable and show retrieval dates and unknown publication dates.
- **Do** distinguish model qualification, human acceptance, and buying intent.
- **Do** preserve visible keyboard focus, minimum control heights, and reduced-motion behavior.
- **Do** verify content at phone and laptop widths, including narrow screens and enlarged text.

### Don't

- **Don't** introduce a dark sci-fi world, neon glows, glass, or glossy decorative rockets.
- **Don't** substitute Inter or Geist for the approved Schibsted Grotesk identity.
- **Don't** flood labels, rules, and backgrounds with orange.
- **Don't** replace inspectable research with decorative KPI cards or compress company sheets into three columns.
- **Don't** present inferred pain, unknown ownership, buying intent, or progress as observed fact.
- **Don't** restore drafting backgrounds, offset button ledges, or ambient card shadows in this modern workspace.


## Research workspace refinement, 16 October

Mode: Operate. The wordmark is plain type aligned with a dark navigation column; no decorative triangle or redundant company-research subtitle. Navigation uses warm off-white primary text and legible muted text, compact history rows, keyboard-accessible collapse controls, and a desktop icon rail. Phone navigation folds above the content.

The walkthrough always distinguishes automatic playback from user input beside the scene. Confirmation and evidence inspection have one explicit main action, with no competing Next shortcut. Pointer movement never silently pauses playback. Source-to-sheet SVG motion illustrates automatic stages; live research selects motion from worker state and saved checkpoints, never timers or made-up completion percentages. Manual, device, hidden-tab and offscreen motion controls remain supported.

The isolated preview cannot submit real research or save provider configuration. It preserves existing runs, explains its lack of a worker and links to the configured local research workspace. This preview guard is not part of hosted authentication or billing.


The user selected an engineering workshop direction after inspecting eygentic.com: restrained orange, paper, calibration grids and mechanical linework. The entry illustration is a decorative SVG calibration plate with a lightweight WebGL scan overlay, not a live work indicator. WebGL failure retains the SVG. Rendering is capped to 1.5 device pixel ratio and approximately 30fps; manual pause, device reduced motion, offscreen and hidden-tab states stop the loop. Context loss retains the static plate. No provider calls or new graphics dependencies are needed.


### Walkthrough controls after independent review
Playback controls sit immediately above the scene and stay available while reading. Reduced motion is manual navigation: Next advances automatic stages, confirmation and evidence retain their own explicit action, and no Resume control appears. Changing motion preferences preserves the selected stage. Initial entry with a device reduced-motion preference still opens the static review example. Automatic holds are6/8/6 seconds for offer/market/discovery, with explicit Pause available beside the scene. Explicit scene choices focus and reveal the new heading. The preview handoff is a real workspace link, not a disabled-form focus action. The preview notice is compact and the sidebar collapse target is44px square.


### Human handoff and account confirmation
Once automation is waiting for input or has saved results, research stages move into a compact expandable history strip. The explicit target-confirmation form or company list/export toolbar leads. Campaign ideas, company-page context and market observations remain available inside an optional disclosure. Active or queued research keeps the full honest progress presentation. Mobile history starts folded, with a44px labelled expand control; desktop retains the full navigation.

Signup success replaces the credential form with Check your inbox, the retained email address and resend/correct-email/sign-in actions. It does not leave another Create account submission in front of someone who has already signed up. Correcting an email restores an empty password field. A textual space around the responsive line break preserves the account headline on phones.

## Navigation on small screens

At850 CSS pixels and below, show one56px charcoal header with a hamburger saved-runs opener at the top left, the product name centered and a plain plus at the top right only while viewing a run. Saved runs use a native modal drawer, not an expanding full-width strip. Keep the underlying content stationary; trap keyboard focus, close with Escape/Close/backdrop, restore opener focus and unlock page scrolling on close or resize. Crossing the layout boundary closes navigation. Desktop keeps a224px sidebar or64px icon rail beneath a full product wordmark; never replace the brand with GS. The isolated preview uses a quiet status line rather than a large warning panel.

## Shared application frame and account tray

The desktop header shares the sidebar's dark surface and border, including the initial load before saved runs arrive. Keep the full product name and a quiet Account control. Email, credit balance, activity and sign-out live inside the Account tray, using native popover light-dismiss and Escape behavior. The desktop account trigger stays fixed while data loads; show the complete, wrapping email inside the tray. On phone, Account opens from the saved-run drawer and the header geometry stays fixed as credits arrive. Credit history opens within the tray and scrolls there.

The shell uses flex allocation from a100dvh root rather than subtracting a duplicated header-height constant. A short page places the footer near the bottom with the normal content padding; desktop navigation stretches to the same bottom edge. The sidebar chevron points right when closed and left when open without rotating the panel divider.

## Local settings and phone navigation, 17 October

Provider configuration belongs in a labelled local Settings popover. Show search/model configuration presence and worker availability separately; never imply a successful connection test from saved credentials. Keep masked key editing and its recovery states inside Settings. A missing search configuration gets one compact entry prompt; a configured workspace gets no secondary continuation. Settings in the design-only preview is read-only. Hosted users retain Account without local provider controls.

Later17 October feedback simplifies the menu trigger to a labelled-accessible hamburger icon. Keep the main entry free of motion controls and repeated provider/judgment disclaimers. Try the demo navigates to a standalone synthetic-example page, with Back/Return to workspace and account-scoped tab-local company input recovery. Do not mount research/auth API flows on the demo page. Replace the demo transport panel with one forward action for each explanatory step; retain the essential confirmation, evidence and review interactions. A single synthetic-data label distinguishes the sample. The decorative entry scan settles after four seconds, retaining device motion preferences and static fallback without a visible pause button.

The latest user feedback replaces the bottom actions with one56px charcoal phone header: a hamburger at the top left opens saved runs, Settings or Account lives inside that drawer, and a plain plus at the top right appears only while viewing a run. Keep the product name centered. There is no bottom bar or reserved bottom gap. Empty history still opens the drawer and exposes Settings before the first run. Settings and Account use matching gear/person icons with visible labels inside the drawer. On desktop, Settings remains a gear-plus-label chip in the header, matching the hosted Account chip; never move it exclusively to a rail that is absent on first visit. The local workspace label has no vertical divider. Retain native drawer focus, Escape, backdrop, scrolling and resize behavior. Saved company favicons use rounded containers with initials fallback; expanded history retains full names, dates and statuses.

## Saved-stage review and site icons, 17 October

History is a text-led list grouped by local-calendar Today, Yesterday, Previous 7 days and Older, newest first. Use the confirmed profile target as the single-line title, falling back to company name. Show a muted company second line only when multiple distinct companies exist in the full history. Omit row dates and routine ready/partial statuses; only Needs confirmation, In progress and Stopped need status text. Rows have no borders, faint hover fill, and the open run has a2px orange left edge with #35312b background and aria-current=page. The24px rounded favicon fills its box with a light backing and no frame; initials keep their border. Icons are muted/grayscale until hover, keyboard focus or selection; transitions honor reduced motion. A history of more than15 runs shows a search field matching target and company.

Closing desktop history hides the panel completely and gives the main content the full workspace width, without an icon rail. The stationary header toggle still reopens it. Desktop New shortlist is a plus-and-label header button beside Settings/Account only while viewing a run, absent on the start screen. The desktop panel has no New shortlist button; phone retains its run-only header plus and labelled drawer action.

Desktop saved-run visibility is controlled in the header after the wordmark, never before it or inside the panel. Anchor the44px button above the expanded panel's right inset and keep it stationary when collapsed. Use a left/right chevron for hide/show, a visible button surface with hover fill, and matching Hide saved runs / Show saved runs accessible names and tooltips. Phone keeps its top-left hamburger before the centered wordmark.

Phone Settings opens as a centered, rounded native modal with a dimmed backdrop, at least16px margins and content-sized height. Long setup forms scroll within it while the close control stays visible. Desktop retains its header popover. Preserve form drafts and focus when resizing across850/851px; drawer-to-Settings handoff must keep background scrolling locked until dismissal. The phone drawer has a labelled New shortlist action above saved runs even on the entry page; the header plus remains run-only. Keep the hamburger and close icon in the same44px position, with a short180ms transition and no authored animation under reduced motion.

User feedback replaces the large live-research animation with a visible six-stage plan and an expanded newest-first checkpoint timeline. Each stage is a keyboard-operable read-only review action; viewing an earlier stage never moves the actual progress marker or starts provider work. Missing saved results stay explicit. Keep partial/confirmation history open. Use each site's own favicon in company results and saved history, with existing initials as fallback and no third-party icon lookup.

Checkpoint history refinement: show the latest three saved steps, newest first. Older steps are revealed only through Show older steps and can be hidden again. Reset this disclosure when selecting another stage.

## Company suggestions, 17 October

Use an editable combobox beneath company entry with compact rows of icon, company name and right-aligned domain. Preserve the existing Start research action and workshop styling. Choosing a suggestion fills its domain; it never starts research. Display directory loading/empty/error states without blocking manual entry. Without directory configuration, retain manual entry without presenting synthetic or saved companies as live directory results. Use directory icons when supplied, with initials only for missing/failed images; synthetic review screens must include both successful icon fixtures and a broken-image fallback.
