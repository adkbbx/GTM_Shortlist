---
name: GTM Shortlist
description: Eygentic company discovery and prospect research
colors:
  paper: "#f7f7f5"
  ink: "#1b1b1b"
  muted: "#64615b"
  orange-ink: "#b4501c"
  orange-hover: "#9b4215"
  rust: "#6a3417"
  rule: "#e1dfd9"
  sidebar: "#f1f0eb"
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

Research sheets and controls use the extracted rounded scale with quiet 1px borders. Primary actions have a minimum height of 52px, inputs 48px, and source disclosures and text actions 44px. Checkbox labels provide a 44px interaction row around a 20px checkbox. Keyboard focus is a 2px orange-ink outline with a 4px offset.

The identity mark is thin SVG construction linework. Arrow SVGs accompany navigation and source actions. No glyph icons, pill-shaped dashboards, or ornamental rocket illustrations are implemented.

## Components

### Buttons

Primary actions use orange ink, white text, a 600 weight, and the extracted padding. Secondary actions use white with a warm neutral border and quiet hover fill. Text actions use an underlined orange label and no fill. Disabled actions reduce opacity to .65 and retain their labels. Keyboard focus follows the shared outline treatment.

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

## Do's and Don'ts

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
