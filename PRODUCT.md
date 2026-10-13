# GTM Shortlist
<!-- impeccable:product-schema 1 -->

## Platform

Web application with an open-source local UI and CLI, plus an Eygentic managed hosted service.

## Stack

Proposed: Python/FastAPI core and API, React/Vite/TypeScript UI, SQLite for local use, Postgres for hosted state, Supabase Auth, a separate durable research worker, configurable search adapters, and Gemma inference. See [architecture.md](architecture.md). This application is not implemented yet.

## Users

Eygentic is the first internal user. Its prospects are private AI B2B SaaS startups that could buy acquisition audits and experiments. The proposed first external paying users are small GTM consultancies, outbound agencies, and fractional growth practitioners who repeatedly prepare campaign lists. The seller profile is configurable for other B2B markets.

## Product purpose

Turn a seller's website and confirmed target criteria into discovered company candidates, source-grounded research, and a human-reviewed shortlist. The system generates candidates rather than requiring an existing lead list.

## Capabilities and constraints

Hosted flow: verified signup, seller website, editable offer and target confirmation, up to three researched company records, review/export, and an optional setup call after value. The public core includes the research workflow using the user's own providers. The paid service supplies operation, saved accounts, onboarding, and optionally human review. No automated outbound or guaranteed buying intent.

## Brand and offering

The user selected GTM Shortlist as an Eygentic offering alongside GTM Booster, GTM Raptor, and GTM Starship. On 14 October 2026, the user explicitly confirmed an open-source core with an Eygentic managed service. Describe it as Eygentic's AI system for company discovery and prospect research. Do not claim that the public core is closed source or that we own the underlying open-weight models.

GTM Shortlist can be sold independently or supply company research for a Raptor experiment. It does not replace Booster's acquisition diagnosis or Starship's ongoing experiments.

## Product principles

Experience first. Confirm the seller's offer before discovery. Distinguish observed evidence, unknowns, and hypotheses. Keep saved progress independent of browser lifetime. Return honest partial results. Make the three-company sample useful before inviting a call.

## Evidence and open decisions

Eygentic's services, design documentation, and CSS were inspected. Explee's company-first demo and OpenGTM's source were evaluated. No new application runtime, customer payment, or research performance has been demonstrated. Model checkpoint, inference host, search default, turnaround, prices, and repeat demand remain subject to measured tests.

## Design authority

Use [DESIGN.md](DESIGN.md), which adapts Eygentic's existing paper-first engineering identity. The workspace-root PRODUCT.md and DESIGN.md belong to Before I Call and are not GTM Shortlist's product context. The Eygentic website is a separate repository; its static-site architecture is not this application's architecture.
