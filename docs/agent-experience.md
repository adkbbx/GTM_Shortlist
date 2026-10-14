# Guided research agent experience

The user's 15 October expansion replaces the earlier restriction on decision-maker research and email drafting. Automated sending and CRM/contact-database integrations remain outside scope. The product remains company-neutral. Eygentic examples are test cases, never defaults or hard-coded preferred sellers.

The requested experience is a continuous, saved six-step investigation. Animated activity must be driven by actual worker state. A checkmark requires a saved result; missing sources, offline workers and provider failures stay visible. Do not display invented completion percentages, competitor counts, headcounts, growth figures, intent scores or contact addresses.

## Acceptance checklist

- [x] Retain bounded search excerpts for candidate prioritization with exact passage, result URL and observed date.
- [x] Prioritize target wording before public-event search clues and preserve stable search ordering on ties; save the explanation before research.
- [x] Explain why each company was researched separately from evidence qualification and human acceptance.
- [x] Show worker-driven source-reading animation and offer summary, with offline/reconnect and reduced-motion states.
- [ ] Research and display a concise seller summary with saved passages; verify multiple real sellers.
- [ ] Discover up to 15 plausible competitors, deduplicate and compare offers with dated sources. Return fewer when evidence is insufficient. Label unverified search candidates separately from substantiated competitors.
- [ ] Propose up to six editable campaigns grounded in the seller's offer, target and competitor observations. Distinguish campaign hypotheses from observed facts. Confirm the selected campaign before prospect discovery.
- [ ] Search for seller-relevant signals, verify ownership and event dates from source pages, and rank the first three using confirmed target and campaign preferences. A public event is a research lead, never proof of buying intent.
- [ ] Show compact company summaries, location/headcount only when sourced, and inspectable reasons for selection. No guessed growth metrics.
- [ ] Find likely decision-makers through public company pages and indexed public professional profiles, retaining source and date. Do not bypass access controls or infer a person from title alone.
- [ ] Add optional configured business-email enrichment and verification. Compare supported providers before selection; do not guess addresses, silently spend on several providers or conflate deliverability with consent.
- [ ] Draft editable emails from verified company/person evidence, label unverified personalization, and retain draft-only behavior.
- [ ] Carry competitor/campaign/person/email outputs through durable checkpoints, retries, stop, quotas, account isolation, export and restart.
- [ ] Verify the whole flow in a real hosted run, plus phone/laptop, keyboard, reduced motion and failure recovery. Re-run provider quality checks across three sellers.

## Implementation order and boundaries

The first change adds auditable prioritization and honest activity feedback. Search excerpts are discovery observations, not verified event evidence. Current matching uses explicit target words and a small public-event lexicon; it does not yet understand campaign relevance, freshness, synonyms or semantic contradictions. Keep that limitation visible and measure the next ranker against labelled cases.

Next, introduce immutable market observations and editable campaign drafts between seller profiling and target confirmation. Use a versioned run experience so old confirmed runs retain their plan and journal operations. Competitor search and campaign generation need independent journal keys and bounded attempts within an explicit per-run spending budget; no hidden budget expansion. Stage state belongs to the worker, not animation timers.

Then verify candidate events against fetched source passages and dates before selection. Finally add owner-scoped decision-maker observations and optional enrichment, with typed provider boundaries, validated provenance and durable dispatch outcomes. Contacts and drafts must remain removable alongside research. The existing first-three credit settlement policy needs an explicit documented extension before charging for additional enrichment.

Design: preserve paper, restrained orange, Schibsted Grotesk and flat research sheets. Use a source-reading motif for the active task, compact saved step summaries, real company domains and text-based identity fallbacks. External favicon loading must not become a new unrestricted fetch path or leak private research without an explicit design decision.
