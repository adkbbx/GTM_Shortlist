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
- [x] Propose up to six editable campaigns grounded in the seller's offer, target and competitor observations. Distinguish campaign hypotheses from observed facts. Confirm the selected campaign before prospect discovery.
- [x] Version new browser runs, journal bounded competitor search and campaign planning, and expose partial market observations during planning without altering old confirmed runs.
- [x] Preserve market/campaign context in owner-scoped API, technical JSON and a readable Market research workbook sheet; prove restart, stop and actual Postgres isolation.
- [x] Separate editable observable search keywords from campaign hypotheses; guard known private-performance criteria and preserve confirmed keywords immutably.
- [ ] Search for seller-relevant signals, verify ownership and event dates from source pages, and rank the first three using confirmed target and campaign preferences. A public event is a research lead, never proof of buying intent.
- [x] For newly confirmed version2 runs, read up to six primary company pages before selecting the three research slots; retain exact dated first-party statements and reuse those pages without extra model/search calls.
- [x] Show compact company summaries, location/headcount only when sourced, and inspectable reasons for selection. No guessed growth metrics. Native exclusive disclosures preserve unsaved notes/drafts while switching sheets; completed checkpoints and offer controls follow the shortlist.
- [x] Add optional description, location and employee-count assessments to existing extraction/verifier calls; require same-company exact passages and entailed judgments, preserve dated scope, save/export them and show explicit missing-source states. Offline fixtures verify mechanics; real cross-seller quality remains open.
- [ ] Find likely decision-makers through public company pages and indexed public professional profiles, retaining source and date. Do not bypass access controls or infer a person from title alone.
- [x] Extract up to three named current team roles from saved company pages, require name/title in exact owned-source passages and separate employment verification, preserve IDs through crash recovery and expose roles/evidence/dates on phone/laptop and exports. Indexed professional profiles, actual buying responsibility and live quality validation remain open.
- [ ] Add optional configured business-email enrichment and verification. Compare supported providers before selection; do not guess addresses, silently spend on several providers or conflate deliverability with consent.
- [ ] Draft editable emails from verified company/person evidence, label unverified personalization, and retain draft-only behavior.
- [x] Provide a zero-inference starting template using the confirmed offer and exact saved company passages, selectable saved person, editable subject/body, immutable starting-source context, revision-safe persistence and Excel/JSON draft export. This is one draft per company, not generated-email quality validation or email enrichment.
- [ ] Carry competitor/campaign/person/email outputs through durable checkpoints, retries, stop, quotas, account isolation, export and restart.
- [ ] Verify the whole flow in a real hosted run, plus phone/laptop, keyboard, reduced motion and failure recovery. Re-run provider quality checks across three sellers.

## Implementation order and boundaries

Search excerpts remain discovery observations, not verified event evidence. New selection policy2 reads six primary pages, matches confirmed search keywords, and uses distinct dated first-party activity types that match the selected campaign as a tie-breaker after sufficient keyword overlap. Statements need an explicit ISO or full English calendar date in the same sentence, same company URL/domain, first-person phrasing, no obvious negation/attribution, and an event date within180 days before confirmation. Fetch dates, publication dates, copyright years, future dates and stale dates never substitute for an event date. This conservative English parser has low recall and does not establish semantic relevance, continuing job availability, independent truth or buying intent. The real8-page saved corpus produced0 eligible statements; that is missing evidence, not negative buying intent. The broader signal gate stays open until real cross-seller coverage and semantic evaluation pass.

Version2 browser runs now introduce immutable market observations and editable campaign drafts between seller profiling and target confirmation. Existing API clients default to version1; the browser explicitly requests version2, so old confirmed runs retain their plan and journal operations. Market search and campaign generation use independent journal keys within unchanged caps of4 search,8 model and21 fetch attempts. Company-name lookup1 + market search1 + prospect discovery2 fits the search cap. Nominal seller/market planning2 + three research/verifier pairs6 fits the model cap; repairs can exhaust it and must remain honest partial results. No automatic provider fallback or extra charge has been added.

One live evaluation reused a real saved seller page and called actual SerpApi/Gemma:9 raw search observations and5 campaign proposals. Review found one forum URL and private-performance conditions. Current deterministic policies retain8 company search observations and4 usable campaign hypotheses from that saved case, moving2 conditions out of required criteria. Original observations remain immutable. These filters address observed cases; they do not establish semantic correctness, freshness, fit or buying intent. Verified offer comparisons and cross-seller campaign/target quality remain open.

Next verify competitor offers and candidate events against fetched source passages and dates before selection. Add campaign-relevant semantic ranking and measure failures across sellers. Then add owner-scoped decision-maker observations and optional enrichment, with typed provider boundaries, validated provenance and durable dispatch outcomes. Contacts and drafts must remain removable alongside research. The existing first-three credit settlement policy needs an explicit documented extension before charging for additional enrichment.

Design: preserve paper, restrained orange, Schibsted Grotesk and flat research sheets. Use a source-reading motif for the active task, compact saved step summaries, real company domains and text-based identity fallbacks. External favicon loading must not become a new unrestricted fetch path or leak private research without an explicit design decision.
