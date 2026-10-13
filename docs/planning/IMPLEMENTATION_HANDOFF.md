# GTM Shortlist implementation handoff

14 October 2026. Planning and research are complete; the new application has not been implemented. Start with this brief, then consult the linked documents for detail.

## Product and business

Build **GTM Shortlist**, Eygentic's AI system for company discovery and prospect research. The user confirmed **an open-source core with an Eygentic managed service**. It joins GTM Booster, GTM Raptor, and GTM Starship. Shortlist supplies company research; Booster diagnoses acquisition questions, Raptor runs focused experiments, and Starship supports ongoing experimentation. Shortlist can also be bought independently.

The job is to discover suitable companies and research why they may be relevant to a seller's offer. Generate the lead list rather than requiring one. Eygentic is the first internal user, targeting private AI B2B SaaS startups for its acquisition services. The proposed first paying app customers are small GTM consultancies and outbound agencies; this buyer choice remains a hypothesis. Profiles must work for other sellers and audiences.

Hosted journey: **verified signup → seller website → editable offer and target confirmation → up to three researched company records → review/export → optional setup call → paid pilot**. Every record includes company identity, criterion-level evidence, source links/passages, freshness, unknowns, and clearly labelled hypotheses. A human accepts or rejects it. Do not infer buying intent, budget, or acquisition problems from a plausible summary.

Public core: profiling, discovery, research, qualification, saved runs, review, export, local UI, and CLI using own providers. Paid value: managed credentials/inference, accounts, operations, onboarding, and optional human review. Proposed offers are USD 99 for a reviewed twenty-record pilot, then USD 49/month for recurring self-service use only after repeat demand and measured delivery capacity. Neither offer is validated revenue.

## Architecture and design

Use the proposed Python/FastAPI core, React/Vite/TypeScript UI, SQLite locally, Postgres hosted, Supabase Auth, and a separate database-backed research worker. Keep one domain core shared by CLI/API/worker. Confirmed target snapshots are immutable; account permissions, budget reservation, identity, evidence, and run transitions each have a clear owner.

Gemma generates seller/segment drafts and structured research. Compare real checkpoints and select inference hosting after measuring quality, hardware, latency, and cost. SerpApi and Tavily are interchangeable search candidates. Jev/Laya are optional narrow classifiers after evaluation, not discovery or generative summarizers.

Free hosted demo starting policy: one saved session per verified account; four total search attempts, twelve candidate domains, six researched candidates, up to three output records, three pages per seller/company, and eight model attempts including seller profiling/repair. All stages and retries share caps. Respect the global SerpApi allowance of 250/month; the proposed allocation is 50 evaluation searches and 200 live searches. Return fewer records honestly if coverage is insufficient.

Apply [DESIGN.md](DESIGN.md): Eygentic's technical-paper identity, restrained orange, Schibsted Grotesk, Architects Daughter for occasional notes, flat ruled research sheets, precise linework, 2px control corners, and visible evidence. Small accent text and white-on-orange buttons use `#B4501C`; the brighter `#D5682F` is a signal/line accent. The app is an operating interface rather than a decorative dashboard.

## Small implementation chunks

Each row is a bounded change. Complete its acceptance check before dependent work. Do not build every future integration in the first pass.

| Chunk | Work | Done when |
| --- | --- | --- |
| 1 | Create a separate project/repository, core types, configuration and labelled fixtures | A local command reads validated config; no secrets or confusion with Week 1. |
| 2 | Seller-page extraction and editable target snapshot | Eygentic's offer is correct; manual corrections persist before discovery. |
| 3 | Search adapter, query planning and canonical company identity | Real new candidate domains are found with provenance; directories and duplicates are handled. |
| 4 | Safe bounded fetches, source storage and cache | Public pages produce dated snapshots; private-network/unsafe redirects are blocked. |
| 5 | Gemma structured extraction | Research outputs reference supplied sources; malformed/unsupported output becomes partial or unknown. |
| 6 | Criterion qualification and grounding evaluation | Supported/contradicted/unknown, negation, old dates and wrong-company cases pass meaningful checks. |
| 7 | Durable stage jobs and resume | Restart continues a saved run; duplicate commands and lost leases cannot duplicate/overwrite work. |
| 8 | Account grants and atomic provider budgets | Attempts and global credits remain capped under retries and concurrent starts. |
| 9 | Local guided UI, evidence review and CSV/JSON export | A person confirms a target, inspects a passage, accepts/rejects records and exports without coaching. |
| 10 | Hosted auth, workspace isolation and persistence | External email signup works; two accounts cannot access each other's records or exports. |
| 11 | Hosted limited demo, optional booking link and operator queue | One saved sample per account; partial results/manual review are honest; click and booked-call metrics differ. |
| 12 | Deploy, real external test and challenge documentation | A real user completes an actual run; setup, demo, measurements, failures and credits are accurate. |
| Later | Deliver paid pilots, then test recurring billing/refresh | Payment, usefulness, repeat demand and contribution support the next feature. |

First milestone: **one real, saved Eygentic run that discovers companies and exports inspectable research**. Do not start with a large dashboard, contact database, or automated SDR.

## Validation, acquisition and boundaries

Use at least thirty labelled evidence cases plus five real discovery runs across three different seller profiles. Benchmark search providers on the same criteria, and models on the same saved passages. Verify actual account isolation, safe fetching, restart/resume, duplicate-command behavior, and global budgets.

Find thirty potential app buyers, prioritize ten, prepare samples for their own offers, and run observed sessions. Aim for three paid pilots, then test whether anyone buys again. Customer messages, payments, publishing, and deployment are future task actions; none was performed by this planning work.

No automated outreach, personal-email database, CRM marketplace, full Clay spreadsheet, or Experiment Judge in the initial release. Optional contact enrichment and campaign feedback follow demonstrated demand. Do not fake a third result, instant turnaround, user interview, payment, or intent signal.

Public launch needs configured SMTP, a persistent hosted database, safe URL handling, working account boundaries, and actual inference capacity. Render free local storage is unsuitable for persistent accounts/jobs. Supabase's default SMTP is unsuitable for general external signup. See [architecture.md](architecture.md) for the verified provider constraints.

Week 2 closes **19 October 2026 at 15:59 JST**. Prioritize a working open-weight research core, usable evidence, an external test, and honest writing. The commercial release remains gated by actual runtime and customer evidence.

## Files and scope

- [Product plan](product-plan.md): problem, ICP, scope, business, pricing experiments, outreach and decision gates.
- [Experience sketches](experience-sketches.md): onboarding alternatives, chosen journey and all important states.
- [Architecture](architecture.md): types, contracts, ownership, budget/job semantics, access and deployment.
- [Delivery plan](delivery-plan.md): schedule, acceptance checks, evaluation, submission and 90-day gates.
- [Product context](PRODUCT.md) and [design authority](DESIGN.md): selected name, brand, operating model and inherited Eygentic design.

These files are the GTM Shortlist planning source. The workspace-root app, PRODUCT.md and DESIGN.md belong to **Before I Call**. Create the new app separately rather than overwriting that project. Eygentic's repository at `D:/Code_Projects/New folder/egentic` was inspected for service and design references; it was not edited. Copy the relevant GTM Shortlist planning files into the new project's documentation when establishing it.
