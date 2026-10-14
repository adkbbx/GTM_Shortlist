# Research credits plan

Status: integrated research credits, 14 October 2026. Hosted accounts receive three signup credits once. Confirmed batches reserve 1–3 credits; saved completed research and its debit commit together, and terminal runs return unused holds. Balance, quoted batch cost and per-sheet charges are visible. Paid checkout, activity history, cancellation and larger batches remain unfinished. Local trusted mode has no customer wallet.

## Unit and packages

One GTM Shortlist credit buys one completed company research sheet against a confirmed target. A batch reserves as many credits as the number of companies requested. This unit describes research delivered, not a Tavily query, model request, qualified lead, contact or buying intent.

| Offering | Proposed allowance | Batch behavior |
| --- | --- | --- |
| Verified free signup | 3 credits, granted once | Up to 3 companies total, together or across smaller batches |
| Starter top-up | Illustrative 20 credits | Research batches within the available balance |
| Larger top-up | Illustrative 100 credits | Same research standards and controls |
| Reviewed pilot | Agreed research allowance plus human service | Explicitly list research credits and review/setup deliverables separately |

Package sizes are examples. Dollar prices remain undecided until measured search, fetching, extraction, independent verification, repairs, failed candidates, hosting and payment costs are available. Start with one-time top-ups; consider recurring credit grants only after repeat demand. Proposed first-release credits do not expire or reset monthly; publish final terms before selling. Human review is not silently included in automated research credits.

Interpretation: the existing three-company demo becomes three company credits. If the user instead wants three complete discovery batches at signup, a three-company batch would require nine company credits. Do not silently conflate these allowances.

## Customer flow

1. Verify signup and receive the one-time grant.
2. Enter seller website; review and confirm offer/target.
3. Choose batch size. Show available balance and maximum cost before submission.
4. Reserve credits atomically, then enqueue research.
5. Show actual progress and saved research, alongside credits reserved and used.
6. Settle delivered sheets once and release undelivered reservations.
7. Review, reopen and export saved research without another charge.
8. Buy a top-up when insufficient credits remain. No automatic purchase or surprise overage.

Example: balance20, batch request10 -> available10/reserved10. Eight completed sheets and two failed companies -> charge8, release2, available12/reserved0. No match against the target is a legitimate research conclusion, not a delivery failure.

Suggested confirmation copy: “Research up to 10 companies · Maximum 10 credits. Credits for companies we cannot research are returned.” Show one clear action to start the batch. Failed payment leaves the existing balance unchanged. A successful checkout redirect alone never increases the balance.

## Delivery and failure policy

Charge only when a unique company sheet has readable saved sources, valid structured research and completed required verification processing. A supported assessment must survive both citation and semantic gates. A properly assessed unknown or non-fit result counts; finding a fit is not guaranteed.

Unreadable company pages, exhausted worker/provider budgets, malformed extraction that cannot be repaired, verifier outages and system failures do not consume customer credits for the affected company. A provider-failure fallback record may still be shown as partial research, but must be marked uncharged. Store a typed completion outcome instead of inferring billing from the existing partial/ready label or the user's review decision.

Duplicate companies within one batch are deduplicated and never charged twice. Worker restarts, retries and browser reloads reuse the same reservation/settlement identities. Reopening/exporting/reviewing saved sheets is free. Explicit new research against a changed target or updated sources can cost credits; the UI must quote that before starting.

Cancellation before dispatch releases the hold. After dispatch, stop scheduling further company work, finish/reconcile outstanding outcomes, charge only completed deliverables and release the rest. Never release a running hold on a timer while work can still produce chargeable results. Provider-outcome uncertainty keeps the existing no-redispatch protection; it never authorizes a second customer debit. Customer refunds do not restore provider spending allowances.

Seller profiling has no additional customer debit, but needs its own abuse and provider-attempt limits. Permit only one active draft/batch per free account initially, limit automated re-profiling, and allow manual offer edits. Three credits must not become unlimited free model calls.

## Persistence and ownership

Wallets belong to verified workspaces under the existing row security. Research and credit ownership must use the same verified identity. All quantities are integer credits.

- `credit_entries`: append-only grants, delivery debits and corrective/refund entries; actor/reason, timestamp, policy version and unique business operation key. Never rewrite history to correct a balance.
- `credit_reservations`: requested credits and held/settled/released state, bound to workspace and run; held amounts reduce available credits without being final charges.
- `company_deliveries`: unique run/company identity and completed/failed outcome, source-bearing saved record and billed quantity0or1. Record save, delivery completion and debit commit together.
- `credit_purchases`: server-created order, expected pack/amount/currency, payment reference and pending/paid/reversed state. Price and grant quantity come from the server's versioned catalogue.

Available credits = ledger grants minus settled debits minus active holds. Lock the workspace wallet during reservation and settlement. Insufficient balance rejects the start without creating a research job. Database uniqueness and conditional transitions, not a browser button's disabled state, prevent duplicate grants/debits. Keep network calls outside database transactions.

Grant signup credits once per eligible verified account using a unique grant key. Research deletion must not recreate the grant; design account deletion and anti-abuse retention together with a disclosed minimal retention policy. Do not treat client metadata as proof of payment or entitlement.

Payment provider integration must verify webhook signatures, reconcile expected paid order/workspace/quantity, and grant credits once per purchase even when several payment events reference it. Webhook replay or delivery order cannot create extra credits. Reversals use explicit entries and account restriction/reconciliation; they never erase research or grant history silently. Payment platform selection and credentials are a later setup step.

## Provider budgets and larger batches

Customer credits and internal attempts are separate. Tavily currently charges basic Search requests1APIcredit and advanced requests2; one company may require multiple queries and model calls. See [Tavily credits documentation](https://docs.tavily.com/documentation/api-credits). Do not expose these API units as customer credits or assume one company's cost is fixed.

Current worker has a three-record limit, six candidate attempts, four searches, eight model calls and21fetch attempts. Buying credits must not simply remove those safeguards. Implement larger batches as durable per-company work with explicit aggregate candidate/search/model/fetch/spend caps and bounded concurrency. Benchmark costs before selecting the maximum paid batch size. Start with current three-company processing while wallet accounting is proved, then extend it; target10/20-company controls remain proposed until tested.

## Migration and implementation checklist

- [ ] Model grants, holds, delivery outcomes and versioned pricing separately from provider attempts.
- [ ] Add RLS-protected ledger/reservations/purchases and unique command keys.
- [x] Migrate unused legacy demo entitlement to one3-credit grant. Already-used demos receive a zero signup entry recording that their demo was granted; saved records remain untouched and there are no retroactive charges. Actual migration tested against pre-wallet tables.
- [x] Replace hosted demo_run_id enforcement with credit reservation at confirmed batch submission. Bound free profiling separately.
- [x] Atomically commit company delivery and one debit; return unused credits on terminal ready/partial outcomes. Cancellation remains unfinished.
- [x] Add balance, batch-size/cost confirmation and insufficient-credit states; test phone/laptop, accessibility and actual hosted API settlement.
- [x] Show recent authenticated credit activity with refresh/retry on phone and laptop.
- [x] Add owner-scoped complete activity pagination with stable timestamp/identity ordering and keyboard navigation.
- [ ] Add explicit cancellation.
- [x] Prove simultaneous starts cannot overspend and process death cannot double-charge or lose a committed charge.
- [x] Prove partial results, real unknown/non-fit outcomes, duplicate companies and provider failures settle correctly.
- [ ] Build one-time top-up checkout and verified, replay-safe purchase grants. Validate actual payment test-mode behavior before selling.
- [ ] Expand durable batches and benchmark cost/margin before choosing pack prices.

Accounting acceptance: real PostgreSQL tests prove concurrent reservations cannot overspend, repeated delivery keys debit once, privileged grants replay once and reject changed quantities, runtime logins cannot alter ledger history, another workspace cannot read its entries, failed batches release all holds, transaction rollback restores both debit and hold state, and actual process death before/after commit never double-charges. Actual worker tests additionally prove unknown/non-fit outcomes charge once, extraction/verifier failures are uncharged, mixed batches return unused holds, and record/debit transactions survive process death. Hosted phone/laptop tests use the real API and Postgres with explicitly labelled external-provider fixtures. These checks do not prove live payments or production accounts.

Confirmed batches now replace the one-demo restriction. Previously granted legacy runs remain exempt from new charges. Free seller profiling is limited to three automated drafts per account, with one active draft/batch; operator-granted paid accounts have a ten-profile daily cap. Hosted billing and larger batches remain incomplete.

## Reuse a confirmed offer

A completed or partial confirmed run now offers Reuse this offer. It copies only the saved offer, target, criteria and exclusions into a new editable draft; no website/model profiling, source research or customer review is copied. The draft requires a fresh explicit confirmation and an upfront batch-cost quote. Balance and one-active-run guards still apply; there is no signup grant or research credit bypass. Automated profiling limits do not block this path because it makes no profiling call. Prior run inputs remain immutable. New research may return companies from earlier batches, which the confirmation screen states before charging.

## Recent activity API

GET /api/credits/history returns up to50 committed signup/addition/usage/refund entries for the verified owner, with entry identity, integer amount and timestamp. The next_cursor value can be sent as before to read earlier entries. The server resolves the UUID anchor only inside the verified workspace, compares the immutable timestamp/identity pair, and fetches one extra row to determine whether another page exists. Malformed cursors fail validation; unknown and foreign-owner cursors have identical unavailable-page responses. Local unmetered mode returns an empty list.

Holds and unused returns remain on the run summary; they are not invented ledger refunds. The endpoint does not expose another account, payment secrets, source text or credit command keys. Hosted customers can open Credit activity beside their balance, inspect signed amounts and dates, move earlier/newer, and refresh to the latest page. The client validates responses against the generated server schema. Credits added is deliberately neutral because operator grants do not prove a completed payment. Each page holds at most50rows; no growing client-side ledger copy or total page count is fabricated. Pagination controls remain mounted while loading, and user page navigation focuses the activity heading after resolution.

Pages read committed data, not a persistent transaction snapshot. A newly committed or late transaction may require refreshing and browsing again; this customer reading interface is not a payment reconciliation or change-data-capture feed. Paid checkout and explicit research cancellation remain unfinished.
