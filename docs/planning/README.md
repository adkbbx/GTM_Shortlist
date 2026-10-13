# GTM Shortlist: product plan

Consolidated plan, 14 October 2026. Status: design ready for implementation. The user selected **GTM Shortlist**, an Eygentic offering with an **open-source core and an Eygentic managed service**. The new product has not been built, deployed, or validated by paying customers.

The product helps a B2B seller discover potential customer companies and understand whether they are worth approaching. A person confirms the seller's offer and target customers, then reviews company research with sources and explicit unknowns.

The hosted journey is **signup → confirm your offer and target → review up to three companies → optionally book a setup call → buy a research pilot**. The full research workflow remains available in the open-source version with the user's own providers.

## Read the plan

| Document | Purpose |
| --- | --- |
| [Implementation handoff](IMPLEMENTATION_HANDOFF.md) | Compact context and twelve manageable implementation chunks for the next agent. |
| [Product context](PRODUCT.md) | Name, users, operating model, constraints, and design authority. |
| [Eygentic design](DESIGN.md) | Existing brand principles and CSS values adapted to the research app. |
| [Product and commercial plan](product-plan.md) | Buyer, problem, scope, open-source model, pricing experiments, acquisition, and success gates. |
| [Experience sketches](experience-sketches.md) | Two onboarding alternatives, chosen screens, sample record structure, and failure states. |
| [Architecture](architecture.md) | Caller contracts, domain types, ownership, durable jobs, provider budgets, account isolation, and deployment. |
| [Delivery plan](delivery-plan.md) | Build sequence, acceptance checks, Week 2 submission, and gated progress toward revenue. |

Start with the product plan. The first implementation milestone is a real run for Eygentic that discovers companies rather than requiring a supplied lead list.

## What is decided and what is proposed

**User decisions:** the name GTM Shortlist; an open-source core with an Eygentic managed service; Eygentic's existing design principles; useful beyond Eygentic; company-first research inspired by Explee; hosted signup before a demo; about three companies in the demo; a setup call after the customer sees value. Eygentic's current prospects are private AI B2B SaaS startups. Its bottleneck is finding suitable companies and researching their relevance.

**Recommendations to test:** start selling to small GTM consultancies and outbound agencies; use a guided first-run experience; offer a USD 99 reviewed research pilot; introduce a USD 49 hosted subscription only after repeat demand; use a modular Python application with a durable worker; bound the free demo to four search attempts. These are decisions for the proposed design, not facts about demand or measured performance.

**Still unresolved through implementation and customer evidence:** the model checkpoint and inference host, the best search provider for actual coverage, real processing time, customer willingness to pay, repeat frequency, and the sustainable price. The plan gives tests and fallback behavior for each.

## Relationship to earlier work

This set consolidates and supersedes architectural and scope choices in the earlier [build plan](../prospect-discovery-build-plan.md) and [revenue plan](../revenue-and-customer-acquisition-plan.md). Their research remains useful context.

The [Explee/Jev/Laya evaluation](../../evaluation/explee/explee-jev-laya-evaluation.md) and [OpenGTM evaluation](../../evaluation/opengtm-evaluation.md) supply verified observations. The earlier Experiment Judge attachment is background for a possible later campaign-feedback feature. Its mailbox and outbound instructions are outside this product's initial scope.

All code paths, API examples, interfaces, milestones, prices, and quotas in this set are proposals unless explicitly identified as verified facts. This set contains no working application code.
