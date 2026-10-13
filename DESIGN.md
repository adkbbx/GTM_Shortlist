---
name: GTM Shortlist
description: Eygentic company discovery and prospect research
---

# GTM Shortlist design

<!-- SEED: Eygentic's existing identity adopted by the user before implementation. Extract the actual GTM Shortlist tokens and components after code exists. -->

## Overview

GTM Shortlist belongs to Eygentic's existing **rocket assembly workshop and flight test lab** design world. The product feels like a technical research notebook: public observations, explicit criteria, source passages, and a shortlist a person can inspect before acting.

The visual identity comes from engineering paper, precise linework, restrained orange signals, and occasional handwritten notes. The interface exposes how a finding was reached. It must remain useful when an AI assessment is uncertain.

The user selected the product name and confirmed an open-source core with an Eygentic managed service. Customer-facing branding is **GTM Shortlist · by Eygentic**. Use the plain descriptor **Company discovery and prospect research**. It can sit alongside GTM Booster, GTM Raptor, and GTM Starship, or supply the research for a Raptor experiment.

This is a source-backed design seed, not a report of an implemented Shortlist UI. Brand values below are observed in Eygentic's source. Application-specific sizes and compositions are proposed adaptations and are identified as such. The application uses its own task-oriented action labels; Eygentic's existing homepage booking CTA and static-site implementation remain governed by that separate repository.

Design authority, inspected 14 October 2026:

- [Eygentic design principles](<D:/Code_Projects/New folder/egentic/docs/design.md>).
- [Current CSS tokens and typography](<D:/Code_Projects/New folder/egentic/src/css/base.css>).
- [Button behavior](<D:/Code_Projects/New folder/egentic/src/css/buttons.css>).
- [Form patterns](<D:/Code_Projects/New folder/egentic/src/css/contact.css>).
- [Offer specification modules](<D:/Code_Projects/New folder/egentic/src/css/offers.css>).
- [Stylesheet source notes](<D:/Code_Projects/New folder/egentic/src/css/README.md>).

Current CSS resolves differences between older examples in the design document and the shipped identity. Source examples of experiment metrics are illustrative design examples, not results to reuse in GTM Shortlist.

The landing page helps a visitor decide whether to try the sample. The application helps an operator confirm a target, inspect evidence, and review companies. Use more expressive drafting illustrations on the landing page and quieter linework in the research workspace. [Experience sketches](experience-sketches.md) describe the screens and states.

## Colors

Keep the existing Eygentic palette. These are inherited values, not a new palette invented for the app.

| Source token | Value | Role in GTM Shortlist |
| --- | --- | --- |
| `--paper` | `#F7F7F5` | Main paper background and research sheets. |
| `--peach` | `#F6E0D3` | Reserved secondary tone. Do not use broad peach section fills by default. |
| `--apricot` | `#E4A07B` | Occasional quiet illustration annotation. |
| `--terracotta` | `#DD8455` | Secondary illustration signal, used sparingly. |
| `--orange` | `#D5682F` | Active markers, measured signals, drafting lines, and large accent text. |
| `--orange-ink` | `#B4501C` | Small accent text, actionable links, focus outlines, and primary button backgrounds. |
| `--rust` | `#6A3417` | Structural button shadow and restrained dark warm detail. |
| `--charcoal` / `--text` | `#1B1B1B` | Body text, headings, technical drawing, and strong rules. |
| `--muted` | `#5C5853` | Metadata and secondary readable text. |
| `--line` | `rgba(27, 27, 27, .16)` | Neutral rules and source boundaries. |
| `--line-soft` | `rgba(27, 27, 27, .09)` | Quiet secondary separators. |
| `--grid` | `rgba(106, 52, 23, .055)` | Background drafting grid. |

Source form fields also use white, `#FFFFFF`, inside paper sheets. Preserve that distinction where it makes editable fields clear.

Orange means something is active or actionable. Keep it sparse so a selected segment, current stage, or main action is easy to spot. Eygentic's direction recommends roughly 65–75% paper and 5–8% burnt orange; treat this as compositional guidance rather than a pixel-count requirement.

The darker orange ink is deliberate. Calculated sRGB contrast is approximately 3.35:1 for burnt orange on paper, 4.77:1 for orange ink on paper, and 5.12:1 for white on orange ink. Use orange ink for small text and filled buttons. Do not copy burnt orange into every text/button role. These checks cover those pairs, not every future component.

Criterion states use a readable label and distinct mark: **Supported**, **Contradicted**, and **Unknown**. Selection and user acceptance are separate states. Keep the initial semantic treatment within the inherited palette; do not rely on color alone or invent green/red success badges across the app.

## Typography

Use **Schibsted Grotesk** for headings, body, controls, and labels, with the existing system sans-serif fallbacks. Use **Architects Daughter** only for brief human annotations. It must not carry criteria, source excerpts, prices, errors, or other information required to operate the product.

The current Eygentic CSS uses:

| Role | Inherited source value |
| --- | --- |
| Marketing H1 | `clamp(2.5rem, 1.4rem + 4.2vw, 5rem)`, weight 700, line-height 1.02, tracking `-.025em` |
| Marketing H2 | `clamp(2rem, 1.3rem + 2.4vw, 3.25rem)`, weight 700, line-height 1.08, tracking `-.02em` |
| Reading body | `1.0625rem`, line-height 1.6 |
| Smaller reading text | `.9375rem`, line-height 1.55 |
| Short metadata/form labels | `.78rem`, weight 600, tracking `.04em`, uppercase |
| Primary button | `1rem`, weight 600, line-height 1.2 |

Use uppercase only for short metadata labels. Keep company names, descriptions, hypotheses, and action text in normal sentence case. Use tabular numerals for counts and dates. Do not introduce a monospace face as decoration; Eygentic's current identity explicitly uses grotesk labels.

For the application, proposed starting sizes are 28–36px page titles, 20–24px company titles, 16–17px reading text, and 15px source excerpts. Keep source passages readable instead of shrinking them to fit a dense table. These app sizes need viewport verification once implemented; they are not existing Eygentic CSS tokens.

Keep the marketing headline concise and let the app title be small enough for research to dominate. Do not transfer the marketing H1's 13-character width constraint to company names or workspace headings.

## Layout

The inherited sheet is paper white with a subtle **40px drafting grid**. The source uses a 1280px maximum wrapper, 24px default gutters, and a 72px navigation bar. Current homepage sections share the same paper rather than alternating background colors.

Use plain paper behind dense evidence text and editable controls. Keep the grid visible in outer margins and diagrams; it must not compete with source passages. If grain is retained from the source, keep it subtle and ensure it does not affect readability or pointer interaction.

The application adaptation starts with:

- A compact header identifying GTM Shortlist and Eygentic, account access, and a saved-sample link.
- One centered form for signup and seller input.
- One research sheet for offer correction, a selected segment, required criteria, and exclusions.
- A truthful stage log for ongoing work, with saved status and actual counts.
- A vertically stacked company shortlist with source/evidence disclosure. Do not make three cards squeeze side by side merely because the demo contains three companies.

Use ruled boundaries and shared alignment rather than independent floating panels. Each sheet has one primary action. Give source inspection and review more space than decorative metrics.

At phone widths, keep the workflow in one column and evidence inline or in a full-width accessible dialog. On larger screens, a source pane may sit beside the active company if it improves comparison without hiding the company identity or review controls. Adapt the source site's 700px phone and 1100px tablet ranges where useful; exact app breakpoints follow actual content fit rather than copying every homepage breakpoint.

Use 24px outer gutters as the starting desktop value and 20–24px on phones, with enough internal space to distinguish criteria, sources, and actions. Treat these as inherited direction and proposed app usage, not proof of a finished responsive layout.

## Elevation & Depth

Surfaces stay flat. Depth comes from paper, thin rules, offset notes, and clear hierarchy. Avoid ambient card shadows, blur, glass, or layered gradients.

Eygentic buttons use a structural ledge: primary `0 2px 0` in rust at rest, `0 4px 0` on hover, and `0 1px 0` when pressed. Secondary buttons use a charcoal border and the same restrained mechanical lift. This shadow vocabulary does not extend to every research sheet.

Inherited motion uses `cubic-bezier(.2, .7, .2, 1)`, with 150ms movement and 200ms color/state transitions. Hover raises a button 2px; active presses it 1px. Disable movement for reduced-motion preferences and disabled controls. Source pages contain more expressive assembly illustrations, but the application uses motion to explain a real state change rather than to imply continuous AI work.

No bounce, floating particles, or looping rockets in the results workspace. Loading status reports persisted work; it must not stage a fake percentage or “signal found” animation before a result exists.

## Shapes

Use square research sheets, fine linework, and **2px corners** for buttons and fields, matching the inherited CSS. Avoid large rounded dashboard cards and decorative pill-shaped containers.

The source has 52px primary buttons, 48px form fields, 44px navigation controls, and a 2px orange-ink focus outline. Carry those dimensions into corresponding app controls unless an observed usability need justifies a change. Preserve visible focus and a clear hit area for small source links.

Engineering illustrations use thin charcoal strokes, construction marks, selected orange annotations, and meaningful labels. If a diagram appears, it must explain seller understanding, qualification, provenance, or a workflow dependency. Keep rocket illustrations to appropriate brand/marketing moments rather than putting a rocket beside every company.

Handwritten notes are brief, restrained, and attached to something real. A note such as “Check the source” can annotate the inspection affordance. Do not stamp “PASS,” “READY,” or “SIGNAL FOUND” on unverified claims or imply that a company is ready to buy.

## Do's and Don'ts

### Do

- Use the existing paper, type, linework, and orange-ink roles so the product belongs to Eygentic.
- Show company identity, criterion findings, source passages, dates, unknowns, and the user's review decision.
- Separate a model's qualification, the user's acceptance, and actual buying intent.
- Keep the sample fully inspectable before the optional setup call.
- Preserve saved inputs and review state through loading, errors, reloads, and sign-in.
- Make partial results and unavailable sources understandable without technical provider jargon.
- Test keyboard use, focus return, phone layouts, zoom, and reduced motion against the actual implementation.
- Label fixture examples and manual review honestly.

### Don't

- Introduce a dark sci-fi theme, neon/glow effects, abstract node networks, decorative planets, or glossy 3D rockets.
- Substitute Inter or Geist for the inherited Schibsted Grotesk identity.
- Apply orange to every label, status, line, and background.
- Turn the research workspace into a wall of large rounded KPI cards.
- Render source excerpts as handwriting, low-contrast microtext, or uppercase paragraphs.
- Treat source design examples as actual experiment results or customer testimonials.
- Show invented intent scores, fake progress, guaranteed meetings, or inferred customer pain as fact.
- Claim the entire system is proprietary when the research core is public.

The workflow details belong in [experience-sketches.md](experience-sketches.md); the implementation boundaries belong in [architecture.md](architecture.md). After the app exists, extract its actual tokens/components and add the design sidecar. No component preview sidecar is generated for this pre-implementation seed.
