# GTM Shortlist: experience sketches

14 October 2026. Two design sketches for comparison. They have not been tested with users and are not screenshots of a working product.

The user selected Eygentic's existing design principles. Apply [DESIGN.md](DESIGN.md) to these layouts: technical paper, restrained orange, Schibsted Grotesk, ruled research sheets, and inspectable evidence. GTM Shortlist uses an open-source core with an Eygentic managed service.

## The moment to optimize

A new user should be able to answer: “What did the app understand about my offer, why is this company relevant, and would I approach it?” Every initial screen should help them reach that decision.

Do not make them learn a search-query language, configure providers, or understand a model architecture during a hosted demo. A self-hosted operator needs those configuration controls in setup, rather than in every research run.

## Alternative A: a guided first sample

```text
Start your company sample
Email             [                         ]
Company website   [ https://                 ]
[Create account]
Up to 3 researched companies. No card required.

                ↓ verify email and read seller pages

What we understood about your company
You help:   [editable offer summary                     ]
You sell to:[editable buyer description                 ]
Sources:    About · Services · Product

Choose one target for this sample
(●) [Segment 1, buyer role, short rationale]
( ) [Segment 2, buyer role, short rationale]
( ) [Define my own target]
Must match: [2–4 plain-language criteria]
Exclude:   [                                      ]
[Find my sample companies]

                ↓ saved discovery and research

Your company sample
We researched [actual count] companies for [confirmed target].
[Company 1 and evidence]  [Company 2]  [Company 3, if found]
[Export accepted records]       [Book a 15-minute setup call]
```

This design puts the seller's offer and one target in front of the user before spending discovery credits. It fits the signup/demo/call flow. It introduces a short confirmation step and therefore depends on good defaults and concise copy.

## Alternative B: a progressive research workspace

```text
Research workspace
┌────────────────────────┬────────────────────────────────┐
│ Seller website         │ Company list                   │
│ [                      ]│ Empty until a run starts      │
│ Offer [                ]│                                │
│ Target [               ]│ Name   Fit   Evidence  Review │
│ Criteria [             ]│                                │
│ Exclusions [           ]│                                │
│ [Run sample]           │                                │
└────────────────────────┴────────────────────────────────┘
Profile, criteria, status, and results stay on one page.
Expanded rows reveal evidence and unknowns.
```

This design supports repeat operators who already know their criteria. It exposes more controls and an empty table before a new user understands the offer or result. It would also require responsive table and panel behavior immediately.

## Choice and how to check it

Choose **A for the first hosted run**, followed by a simple saved-results workspace. It hides irrelevant controls, makes seller corrections visible, and reaches the three-company sample in fewer decisions. Reuse the same profile and criteria controls for later runs rather than maintaining two separate implementations.

| Criterion | Guided sample | Progressive workspace |
| --- | --- | --- |
| First-time clarity | One decision at a time | Requires understanding several controls at once |
| Preventing wrong offer assumptions | Explicit confirmation before discovery | Confirmation can be easy to miss |
| Repeated campaigns | Needs a short saved-profile shortcut later | Faster for experienced operators |
| Mobile experience | Natural vertical flow | More layout work for panels and table |
| Week 2 scope | Four principal views including progress | More interactions before first useful result |

Before finalizing the UI, show both sketches to three likely operators. Ask them to point out where they would correct the offer, start research, inspect evidence, and reject a company. Record confusion and completion without coaching. Prefer observed comprehension over our preference if the results disagree. This is a lightweight design check, not a demand test.

## Landing and signup

Suggested hero copy:

> Find companies worth researching for your next B2B campaign.
>
> Enter your website. Confirm your target. Review up to three companies with source-linked reasons and clear unknowns.

Primary CTA: **Start my company sample**. Secondary link: **View a recorded example**. The open-source repository link is visible but does not interrupt the primary journey.

The recorded example must show its seller, criteria, research date, and status. It must not simulate a live personalized run. If results were manually reviewed, say so.

Signup asks for email and website, no card, no phone number, no long business questionnaire. Preserve the website when email verification opens another tab. Avoid searching a company until identity is verified and its demo allowance is available.

If a name is accepted instead of a website, show possible domains and ask the user to choose the correct company. This uses the same capped search allowance. Do not infer ownership of a company's domain from the signup email; the app researches public company information and does not require the user to claim they represent that company.

After returning users authenticate, open the saved sample rather than starting another run. Show unavailable signup/demo capacity honestly before consuming work.

## Seller and target confirmation

Title: **What we understood about your company**.

Show the offer in editable plain language, the customer types, the seller sources, and any missing information. For Eygentic, the offer must reflect acquisition audits and experiments. A vague website must lead to a request to write the offer, rather than a confident invented service.

Show at most three segment options. Each contains a buyer type, why the offer might help, and the proposed criteria. Label proposed pains as hypotheses. Keep one segment selected for the initial sample. Allow the user to edit criteria and exclusions directly.

Example Eygentic target, illustrative criteria rather than asserted facts about any company:

```text
Target: Private AI B2B SaaS companies
Must match:
  • Sells an AI product
  • Serves businesses
Exclude:
  • Consumer-only apps
  • Agencies selling services rather than SaaS
Useful context, if available:
  • An active commercial product
  • Public acquisition or expansion activity
Still may be unknown:
  • Budget, pipeline performance, willingness to buy
```

“Find my sample companies” creates a confirmed snapshot. Later edits do not silently change evidence in the existing run. Show which target produced the saved result. A subsequent new run requires an available allowance.

## Progress and returning to work

Show actual stages: **Understanding your offer → Finding company websites → Checking evidence → Preparing your sample**. Include truthful counts when known, such as “Checked 2 of 4 selected websites.” Do not animate an invented percentage.

Say “You can leave this page and return to your saved sample.” The worker, rather than the browser tab, owns execution. If operator review is enabled, show “Your sample is queued for review” with an estimate only when operations can meet it.

Use polling of saved state initially. Streaming output and background emails are unnecessary to the first result. Do not notify by email until the user has been told what notifications they will receive and delivery is configured.

## Results and evidence

Use a vertically stacked list of up to three cards. A complete card should be useful on its own, without forcing a sales call.

The following is a **fictional format example**, not a discovered company or live result:

```text
[Example company]                     [company.example]
What it sells: [short supported product description]
Research: Partial · Retrieved [date/time]

Why it matches your target
✓ AI product: [observed statement]          [source, excerpt]
✓ Business buyers: [observed statement]     [source, excerpt]
? Private company status: Not established in fetched pages

Relevant context
[Dated observed change, if one exists]      [source, excerpt]

Possible acquisition question · Hypothesis
[One question connecting your offer to the observed context]

Still unknown
Acquisition performance · budget · buying intent
Likely role to approach: [role, or unknown]

[Worth approaching] [Not suitable] [Need more research]
[View sources]
```

Open sources inline or in a side panel with the exact short excerpt and retrieval date. Links still work without that panel. Use standard browser behavior for opening the original website. Sources must be keyboard accessible.

Keep the company description concise. Put source details and longer notes behind disclosure controls. Label partial research at the card level; the whole sample can be ready while a record has unknown criteria.

Acceptance records the user's judgment. It does not change an unknown fact to supported. Ask for a short rejection reason using optional choices: wrong target, wrong company, insufficient evidence, already known, or not relevant now. Preserve free text for more precise feedback.

After a user accepts a record, show the export action clearly. Export the criteria, observations, source links, unknowns, and user decision along with the company identity. CSV safety and deduplication belong to the export implementation.

The next-step panel says:

> Want a campaign list for this target? Book a 15-minute setup call to agree the criteria and a reviewed pilot.

The sample stays available if the user ignores the panel. If no useful records were found, prioritize correcting the target and explaining limited coverage; do not sell a twenty-record outcome that the sample failed to demonstrate.

## Empty and failure states

| Situation | User sees | Recovery |
| --- | --- | --- |
| Seller page inaccessible | “We couldn't read this website. Describe your offer to continue.” | Enter the offer manually or correct the URL. |
| Ambiguous company name | A domain choice with distinguishing details | Confirm the identity; do not run against a guessed domain. |
| Unclear target | “Choose or describe one customer group for this sample.” | Edit the target before discovery. |
| No useful candidates | Criteria and sources searched, with coverage explanation | Save the outcome; offer a target correction or operator help. No fabricated results. |
| One or two records | Actual result count and why the run stopped | Review available evidence; keep the sample useful. |
| A company page is blocked | Partial record and unavailable-source note | Use accessible sources within the budget; do not bypass access controls. |
| Provider unavailable | Saved stage and truthful retry state | Bounded retry if allowance remains; otherwise return partial or a retryable failure. |
| Demo capacity exhausted | “New demos are temporarily unavailable. Your saved results are still here.” | Offer open-source setup or an explicitly optional waitlist. |
| Browser reload or worker restart | Same saved run and progress | Resume stages; no duplicate free grant or unbounded provider calls. |
| Signed out | Sign-in prompt, then saved sample | No lost work or automatic repeat run. |
| User rejects every record | Acknowledgment and editable feedback | Use reasons to investigate targeting/coverage; do not assume the buyer lacks demand. |

## Operator and maintainer experience

An initial internal page needs only: run/account reference, stage, confirmed target, stop reason, source/evidence inspector, consumed budget, and review controls. Operators can mark review complete, correct unsupported claims, or authorize a recorded reset. Corrections retain provenance and an audit entry.

Operators must not silently generate an entirely manual sample and present it as automated discovery. Developer setup should offer a fixture mode clearly labelled as fixtures, provider capability checks, and a local real-run command. One application core supplies both UI and CLI behavior.

## Interaction quality and accessibility

Use semantic forms, visible labels, keyboard-operable controls, clear focus, and status announcements. Do not rely only on color for supported/contradicted/unknown. Keep reduced-motion preferences, readable text, and mobile layouts in the first release.

Provide an explicit saved state after target confirmation and each review action. Prevent repeated submissions while a command is pending, while server idempotency handles retries. Preserve edits if validation fails. Confirm irreversible account deletion; ordinary review changes remain reversible.

The UI acceptance check is practical: a new operator can confirm the offer, inspect a claim's supporting passage, reject a record, accept another, and export it without the builder explaining the interface.
