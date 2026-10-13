# GTM Shortlist: delivery and validation plan

14 October 2026. Proposed sequence for one builder. Dates are targets; releases depend on the acceptance checks. This planning task has not built or submitted the product.

Start with [IMPLEMENTATION_HANDOFF.md](IMPLEMENTATION_HANDOFF.md) for a compact build brief and manageable chunks. Use [DESIGN.md](DESIGN.md) to keep the new app within Eygentic's existing identity. GTM Shortlist remains an open-source core with an Eygentic managed service.

## Define 0 to 1

“1” means an external target customer can sign up, inspect real company research, buy an available research pilot, receive it, and decide whether another list is worth paying for. A working demo is an intermediate milestone. A repeatable hosted side hustle additionally needs positive measured economics and repeat demand.

The immediate task is to prove candidate discovery and research for Eygentic. Building signup before that would give us a polished entrance to an unproven result. Both discovery and signup are required for the intended hosted experience, but the build order follows the useful result.

## Build sequence and acceptance

| Order | Deliverable | Dependency | Acceptance check |
| --- | --- | --- | --- |
| 1 | New repository, licence direction, small schema, provider configuration | This plan | Separate from Week 1; no secrets; real and fixture modes clearly distinguished. |
| 2 | One seller profile and confirmation operation | 1 | Eygentic's services are correct; criteria and exclusions are editable; snapshot persists. |
| 3 | Search adapters and company identity | 1–2 | A run discovers company domains without a supplied list; directories are not mistaken for companies; candidates retain provenance. |
| 4 | Bounded fetching and source snapshots | 3 | Accessible public pages produce dated stored text; blocked pages and unsafe URLs fail honestly. |
| 5 | Gemma extraction and evidence/qualification | 2–4 | Critical claims point to supporting passages; unknown, contradictory, stale, and negated evidence behave correctly. |
| 6 | Saved run, budget ledger, durable worker | 3–5 | Restart resumes progress; duplicate requests share a run; attempts stop at caps; global credits cannot be overspent. |
| 7 | Review and export | 5–6 | Accept/reject/needs-research works; export preserves sources and unknowns; duplicate identities and formula injection are handled. |
| 8 | Hosted account boundary | 6 | Verified external signup; two accounts cannot read/edit/export each other's work; persistent hosted DB. |
| 9 | Guided UI and up-to-three-company demo | 2, 6–8 | New user corrects the target, receives real records, understands partial output, and exports without coaching. |
| 10 | Booking link and minimal operator queue | 9 | Optional call invitation after results; clicks and bookings are distinct; manual review is disclosed. |
| 11 | Deploy, external test, evidence of actual operation | 8–10 | Real account completes a live run; builder captures failures, usage, and feedback honestly. |
| 12 | README, demo recording, DEV submission | 11 | Reproducible setup, actual model/provider use, limitations, and customer evidence are accurately described. |
| 13 | Sell and deliver bounded pilots | Useful research and delivery capacity | Agreed scope/date before payment; source-linked output delivered and reviewed; cost/time recorded. |
| 14 | Test recurring hosted use | Paid pilots and repeat demand | Advertised limits can be met; verified payment and cancellation work; measured margins support operation. |

Do not install Jev/Laya, a workflow platform, contact vendors, or CRM integrations to make the architecture feel complete. Add a component when a demonstrated need earns its operating cost.

## Week 2 schedule

The active [Hacktoberfest Open-Source AI Challenge: Week 2](https://dev.to/challenges/hacktoberfest-week2-2026-10-12) asks for a side hustle built around open-source AI or open-weight models. It closes **18 October 2026 at 23:59 PDT**, which is **19 October at 15:59 JST**. From the 14 October planning date, about five calendar days remain. The canonical DEV challenge details take precedence over an inconsistent MLH event end timestamp.

| Local date, JST | Target | Evidence at end of day |
| --- | --- | --- |
| 14 October | Real Eygentic discovery slice: profile → candidates → pages → Gemma → evidence | One saved run and export with actual source passages; identify model/search coverage failures. |
| 15 October | Durable runs, budgets, hosted schema and authentication; compare UX sketches | Restart and duplicate-command checks; external email delivery works; chosen interface sketch. |
| 16 October | Guided signup/demo/review UI; booking link; first external observed run | Someone outside the builder can reach and review actual records; feedback and rejection reasons. |
| 17 October | Hosted deployment, account isolation, provider comparison, failure fixes | Two-account isolation proof, capped search/model attempts, deployed run with measured usage. |
| 18 October | Freeze working features; prepare README, short demo, write-up and source credits | Reproducible instructions, screenshots of real output, factual customer feedback, ready submission draft. |
| 19 October before 12:00 JST | Publish and verify the required submission links/tag/template | Public repository, demo and post load correctly; roughly four hours of deadline buffer. |

This is a compressed target, not a guarantee that all tasks fit. If the core is still wrong on the 16th, prioritize discovery and evidence over secondary features. Cut name resolution, streaming, extra segments, classifier integrations, and subscription billing first.

If unrestricted hosting is not ready, use a capped invited test with honestly described operator availability and a recorded real run. Do not present a fixture, saved recording, or manually assembled list as a live automated product. The full hosted signup/demo/call journey remains the commercial release target after the challenge; record unfinished pieces in the submission.

Use a new project repository for this week's build. Existing plans and research are inputs; do not relabel the Week 1 app. Credit borrowed code and explain substantive new work. Open-weight inference must perform meaningful seller/company research, rather than appear only in a decorative feature.

## Partner choice

Use partners when they serve the product and are actually implemented:

| Category candidate | Meaningful use | Condition for mentioning it in the submission |
| --- | --- | --- |
| Gemma | Seller understanding and structured company research | Real inference with named checkpoint, source-based outputs, and measured limitations. |
| Render | Hosted application and worker operation | Deployed services demonstrably run the workflow; do not claim a configuration file alone proves hosting. |
| SerpApi | Real company candidate discovery | Actual configured searches used within the measured budget. Supporting an unused adapter is insufficient. |
| Sentry Agent Tracing | Research-stage errors/timing, if implemented | Demonstrate the actual integration without leaking customer content. Plain logs do not become agent tracing. |
| .tech domain | A working product entry point, optional | Domain is actually acquired/configured and used; availability and price remain unverified. |

Do not add all seventeen partner technologies. Tavily can be the better operational default if tests establish that; it need not qualify for a partner prize to be useful. TabPFN and hardware/voice categories are not needed for this product's initial job. Commercial use of any optional partner model needs its actual terms checked before a paid deployment.

Current account checks returned no Week 2 offers or sponsor-agent-skill bundles. Treat any promotional credits as unavailable until an actual claim is confirmed. Do not budget the side hustle on an unclaimed or expired promotion.

## Evaluation that can be rerun

Keep an evaluation dataset and runner in the new repository. It is a product artifact: future contributors can check whether a provider/model change improves research instead of judging prettier prose.

Create at least thirty labelled passage/criterion cases from permitted public material or clearly labelled synthetic edge cases. Include supported facts, explicit contradictions, missing information, negation, old dates, a similar-name wrong company, and a consumer product against a B2B criterion. Preserve source URLs/retrieval dates for real material; never insert private customer notes into public fixtures.

The labelled cases measure evidence classification and grounding. They do not test the whole discovery task. Add five real discovery runs across three seller profiles, one being Eygentic. At least one profile should have a deliberately different offer/market to expose hardcoding.

Compare SerpApi and Tavily with the same three profiles and four bounded search attempts per profile. Review candidate identity, independent fit evidence, duplicates, stale/blocked sources, actual credits, and human review effort. Use the same target snapshots; do not give one provider broader instructions and then compare yields. Those twelve SerpApi comparison attempts plus five four-attempt real runs consume at most 32 of the proposed 50-search evaluation reserve. Additional experiments require remaining allowance, not an assumed free retry.

Compare Gemma candidates on the same saved passages so model evaluation does not repeat search work. Record checkpoint/quantization, inference server, prompt version, schema validity, critical-claim errors, unknown handling, latency, and actual memory/cost. Choose the smallest model that meets the observed quality bar. The plan does not assume either candidate will pass.

Minimum release checks:

- No unsupported critical claim or wrong company identity in the audited release sample; demote uncertain findings to unknown and fix the responsible boundary.
- Negation and stale-date cases do not become positive current signals.
- Two users cannot access each other's run, sources, reviews, or exports.
- Duplicate start/confirm requests and browser reload do not create extra demo grants or jobs.
- Worker restart resumes saved work; lost leases cannot overwrite current state.
- Four search attempts and eight model attempts remain caps under timeout/retry paths; simultaneous reservations honor the provider-wide limit.
- Private network/metadata/redirect fetching is blocked; rendered text and CSV fields are handled safely.
- A new operator reaches an evidence-supported review decision and export without coaching.

Use focused domain and integration tests for these consequential behaviors. Do not inflate the test count with assertions that merely mirror constants or UI text. Run the actual deployed feature as well as automated checks. Passing fixture tests does not establish search coverage or live model quality.

## The first thirty days

**Week 1 after the challenge:** observe five external target buyers using the sample. Ask how they currently build lists, how often they repeat it, what they reject, and whether the research is useful in a real campaign. Test the product's own acquisition workflow manually; do not confuse generated prospect companies with potential app buyers.

**Weeks 2–3:** show usable samples to ten qualified buyers and offer the USD 99 pilot where delivery is feasible. Aim for three paid pilots. Confirm scope, payment, and delivery manually using the operator's existing processes. Limit concurrent orders to measured capacity. Record outreach replies and funnel stages without interpreting a courteous response as buying intent.

**Week 4:** review delivered records with buyers. Measure accepted records, time spent checking, whether they used the list, requests for another campaign, and contribution after review/support time. Ask for a testimonial only about an actual observed outcome; do not publish a customer's information without permission.

If ten relevant buyers receive usable samples but nobody pays, investigate the offer, timing, distribution, and current alternatives before spending another month on integrations. If the sample fails to produce usable research, fix that first rather than treating payment as the only issue.

## Days 31–60: test repetition

Add saved campaign profiles and deduplication against previously reviewed records if customers ask for another list. Decide whether they want recurring new-company discovery, occasional research packs, or a service rather than software. Scheduled refreshing is justified only when customers need it.

Test the proposed USD 49 subscription with a small number of repeat buyers. Before enabling purchases, implement and verify provider-backed payment confirmation, allowance grants, renewal/cancellation, visible usage, data export/deletion, and a restore procedure. Confirm actual hosting, email, inference, support hours, and variable cost. Do not sell four twenty-five-record runs simply because the pricing table contains that number.

Use automatic billing only after the paid offer and scope are concrete. Keep human-reviewed packs as a separate explicitly priced service if they remain valuable.

## Days 61–90: operate a small business

Continue only with repeat usage and positive measured contribution. Build the next feature from repeated observed demand:

- More source coverage when accepted-company yield is the bottleneck.
- Contact enrichment when buyers can use the companies but cannot identify a reachable decision maker.
- Team review when handoff between an agency owner and researcher creates repeated friction.
- Campaign outcome feedback when buyers want to learn which researched companies produced useful responses.

The original Experiment Judge idea belongs to the last case. It requires actual campaigns and outcomes, separate consent/data handling, and its own validation. It is not a dependency for finding companies.

Create a manageable operating routine: inspect failures and provider allowance on workdays, review customer delivery commitments, reconcile usage/revenue weekly, and inspect repeat purchases/cancellations monthly. Automations or monitoring have not been created by this plan. Keep these tasks manual until the relevant volume makes an automation worthwhile.

## Submission outline

The canonical challenge weights writing most heavily and asks for who would pay, a demo, and why open innovation matters. Use the official Side Hustle template and required `hf26challenge` tag. The post should answer:

1. **Who has the problem?** A specific buyer preparing a specific campaign. Describe an observed workflow when available.
2. **What did we build?** Seller website → editable target → discovered company candidates → source-grounded research → human review/export.
3. **Show the real product.** Short recording of signup or local entry, target correction, source inspection, partial-result behavior, and export. State which pieces are live, manual, or unfinished.
4. **Why open innovation?** Actual open-weight model use, interchangeable providers, self-hosted core, inspectable rules/evaluation, and the tradeoff between own inference and managed operation. Do not assert cheaper/private behavior without the relevant measurements and deployment facts.
5. **Would someone pay?** Present an actual paid pilot if one exists; otherwise state the tested offer, sample feedback, and remaining uncertainty. A hypothetical USD 99 price is not revenue.
6. **Technical choices and lessons.** Source validation, durable progress, provider budgets, and real failure examples. Name only partner integrations actually used.
7. **Links and credits.** New public repository, licence, reproducible setup, live demo if working, model/provider details, borrowed-code credits, and limitations.

Saving a session transcript and embedding it is optional. It is not part of this task, and no transcript or post has been published.

## Completion checklist for the commercial product

- A real external buyer completes the signup/sample flow.
- The core independently discovers companies and remains usable with the self-hosted setup.
- Source-supported records, explicit unknowns, and saved review decisions survive a restart.
- Account isolation, safe fetching, and global spend caps pass against the deployed system.
- At least one paid pilot is delivered within its agreed scope, with recorded costs and feedback.
- Repeat demand is tested before presenting subscriptions as a validated business.

The next concrete implementation step is therefore **one real, saved Eygentic discovery run with inspectable evidence**, followed by the durable guided hosted experience. Build and verify that result before expanding the product.
