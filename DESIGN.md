---
name: GTM Shortlist
description: Eygentic company discovery and prospect research
colors:
  paper: "#f7f7f5"
  ink: "#1b1b1b"
  muted: "#5c5853"
  orange-ink: "#b4501c"
  orange-hover: "#9b4215"
  rust: "#6a3417"
  rule: "rgba(27,27,27,.16)"
  drafting-grid: "rgba(106,52,23,.035)"
  field: "#ffffff"
  field-border: "#8c8881"
  field-placeholder: "#68635c"
  quiet-selection: "#eeede9"
  text-selection: "#f6e0d3"
  notice-paper: "#f5eee8"
  notice-rule: "#caa994"
typography:
  display:
    fontFamily: "Schibsted Grotesk, sans-serif"
    fontSize: "2rem"
    fontWeight: 700
    lineHeight: 1.2
    letterSpacing: "-.025em"
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
  control: "2px"
  sheet: "0px"
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
    backgroundColor: "{colors.paper}"
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
    padding: "12px"
  research-sheet:
    backgroundColor: "{colors.paper}"
    rounded: "{rounded.sheet}"
    padding: "28px 32px"
  source-passage:
    backgroundColor: "{colors.field}"
    textColor: "{colors.ink}"
    typography: "{typography.passage}"
    padding: "16px 20px"
---

# Design System: GTM Shortlist

## Overview

**Creative North Star: "Rocket assembly workshop and flight test lab"**

GTM Shortlist adopts Eygentic's existing engineering-paper identity. The implemented workspace feels like a technical research notebook: observations, criteria, source passages, and a shortlist a person can inspect before acting. Quiet paper, precise rules, restrained orange, and Schibsted Grotesk carry this world into the application.

This document records the local workspace in `web/styles.css` and `web/main.tsx`, inspected on 14 October 2026. It replaces the pre-implementation seed with observed application tokens while preserving the agreed identity. Eygentic's separate marketing website remains its own design authority; its marketing headline scale and illustrative palette are not application tokens.

**Key Characteristics:**

- Engineering paper behind flat, ruled research sheets.
- Orange ink identifies actions and active research states.
- Exact source passages remain readable beside labelled unknowns.
- Human review is visually distinct from model qualification.

Inherited authority: [Eygentic design principles](<D:/Code_Projects/New folder/egentic/docs/design.md>) and [source CSS](<D:/Code_Projects/New folder/egentic/src/css/base.css>). The selected application direction is recorded in [docs/ui-direction.md](docs/ui-direction.md).

## Colors

The frontmatter records the implemented palette, including neutral control and notice states. Its CSS values are normative for this workspace.

### Primary

**Orange ink** marks primary actions, actionable links, focus outlines, the identity linework, and contradicted findings. **Orange hover** darkens primary actions. **Rust** is inherited warm detail in the text-action hover and the approved primary-button ledge.

**The Action Ink Rule.** Reserve orange for something actionable or a meaningful state; paper and charcoal carry the research itself.

### Neutral

**Paper** covers the workspace, header, and research sheets. **Ink** carries body text and strong structural rules. **Muted** carries secondary descriptions, dates, and unknown reasons. **Rule** separates findings without creating floating panels. **Drafting grid** appears in the main workspace margins, underneath opaque paper sheets.

**Field** distinguishes editable controls and quoted passages. **Field border** and **field placeholder** keep input affordances legible. **Quiet selection** marks saved-run selection and secondary hover. **Text selection** uses the inherited peach. **Notice paper** and **notice rule** distinguish an actionable error or limitation with a written explanation.

Supported, contradicted, and unknown findings have explicit text labels. Color never substitutes for a status or review decision. The broader Eygentic illustration palette remains available in its marketing system; unused seed colors are not extracted application tokens.

## Typography

Schibsted Grotesk is locally bundled and used for headings, body, controls, and metadata. The browser sans-serif fallback serves loading failure. No separate display, handwriting, or decorative monospace face is implemented in the workspace.

### Hierarchy

- **Display:** the page heading uses the frontmatter display role, narrows to 1.75rem on phones, and has a maximum width of 24ch.
- **Title:** company and section headings use the title role. Section headings alone add -.015em tracking.
- **Body:** normal reading text uses the body role, generally no wider than 72ch. The main introduction is limited to 65ch.
- **Passage:** exact quotations use the passage role with preserved whitespace and wrapping for long tokens.
- **Label:** form labels use the label role; hints use .875rem.
- **Metadata:** dates and secondary state text use the metadata role. Saved-run metadata uses .75rem. Finding status is .75rem on laptop and .6875rem on phone, adjacent to the full finding title and explanation.

**The Readable Evidence Rule.** Preserve the passage role for source text; do not shrink or capitalize quotations to fit more records.

Sentence case is used for actions and research. The short navigation label “Saved runs” is uppercase with .04em tracking; it is a navigation label, not a decorative eyebrow.

## Layout

The laptop workspace is a two-column layout with a 240px saved-run sidebar and a flexible main column, capped at 1600px. The header is 88px tall. Main padding is 44px vertically and 48px horizontally. Research sheets use the frontmatter sheet padding, a dark top rule, and a 28px bottom gap. Company sheets share the same flat boundary but divide their internal content into separately padded identity, findings, hypotheses, and review areas.

At 1050px and below, the sidebar narrows to 200px, main padding becomes 32px by 28px, and forms, exports, and confirmation actions stack where content requires it. At 700px and below, the header is 76px tall and the workspace becomes one column with 20px outer gutters. Saved runs become a horizontally scrollable strip; seller and confirmation actions fill the available width. Company identity and review headings stack. The instructional sequence becomes a vertical list.

The main drafting grid repeats every 40px. Paper sheets and evidence blocks cover it behind dense reading. A company shortlist is a vertical series of research sheets, never three compressed columns.

**The Shared Rule Rule.** Use aligned edges and thin separators to organize related research rather than detached dashboard tiles.

## Elevation & Depth

Research surfaces have no ambient shadows, blur, glass, or layered gradients. White fields, paper sheets, text hierarchy, and rules provide separation. The primary button retains the approved inherited 2px rust ledge (`0 2px 0 #6a3417`) at rest. Secondary and text actions have no shadow. This limited button treatment does not establish a general shadow vocabulary for research sheets or future components.

Buttons transition background over .2s and transform over .15s. Hover moves up 1px and active moves down 1px; disabled controls stop movement. Reduced-motion preferences disable transitions and button transforms. Loading states describe saved worker progress without decorative continuous motion or invented percentages.

## Shapes

Research sheets are square. Controls use the frontmatter control radius, with 1px borders. Primary actions have a minimum height of 52px, inputs 48px, and source disclosures and text actions 44px. Checkbox labels provide a 44px interaction row around a 20px checkbox. Keyboard focus is a 2px orange-ink outline with a 4px offset.

The identity mark is thin SVG construction linework. Arrow SVGs accompany navigation and source actions. No glyph icons, pill-shaped dashboards, or ornamental rocket illustrations are implemented.

## Components

### Buttons

Primary actions use orange ink, white text, a 600 weight, and the extracted padding. Secondary actions use paper and a charcoal border, with quiet selection on hover. Text actions use an underlined orange label and no fill. Disabled actions reduce opacity to .65 and retain their labels. Keyboard focus follows the shared outline treatment.

### Inputs / Fields

White fields have the extracted border and padding, with orange caret and visible focus. Textareas resize vertically. Labels sit above fields, and optional notes appear beside labels on laptop and underneath on phones. Error notices provide text; invalid submitted input remains available for correction.

### Navigation

The saved-run list uses ruled rows with company domain, date, and persisted state. Selection adds quiet neutral fill and an orange left edge. Rows do not lift on hover. The phone strip retains the same information in 180px items and supports horizontal scrolling. The new-shortlist control remains separately visible.

### Research sheets

Identity, qualification, findings, hypotheses, and review occupy one flat company sheet. Finding status is labelled and ruled; unknown uses a dashed rule. Qualification never implies buying intent. Review buttons save a separate human decision and written note.

### Source disclosure

A native details disclosure places the claim first and “Inspect passage” underneath. Opening it reveals the exact quotation on white, followed by a source link, retrieval date, and publication date or a written unknown. The disclosure is inline, keyboard accessible, and preserves the company context.

### Notices

Warm neutral notices contain a written failure, limitation, or corrective action. They wrap long text. A notice is not a fabricated success signal or an ornamental callout.

## Do's and Don'ts

### Do

- **Do** use paper, Schibsted Grotesk, ruled alignment, and restrained orange ink for new application surfaces.
- **Do** keep exact passages readable and show retrieval dates and unknown publication dates.
- **Do** distinguish model qualification, human acceptance, and buying intent.
- **Do** preserve visible keyboard focus, minimum control heights, and reduced-motion behavior.
- **Do** verify content at phone and laptop widths, including narrow screens and enlarged text.

### Don't

- **Don't** introduce a dark sci-fi world, neon glows, glass, or glossy decorative rockets.
- **Don't** substitute Inter or Geist for the approved Schibsted Grotesk identity.
- **Don't** flood labels, rules, and backgrounds with orange.
- **Don't** turn research into floating, rounded KPI cards or compress company sheets into three columns.
- **Don't** present inferred pain, unknown ownership, buying intent, or progress as observed fact.
- **Don't** extend the inherited primary-button ledge into a general shadow vocabulary.
