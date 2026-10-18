# Backlog

Agreed ideas not yet scheduled. Each needs the user's go-ahead before work starts.

## StartupWho as an optional discovery source (added 18 October)

**Why.** For broad targets such as "B2B and SaaS companies", web search returned articles, lists and consultants who sell to that market (the hosted eygentic.com run found one company, a marketing consultant). A curated list of real startups with their own websites is a better starting point, and reading it spends no search credits.

**What was checked (18 October).** https://www.startupwho.com/startups returns HTTP 200 and calls itself "The Open Startup Database ... 3,000+ startups from YC, Techstars, Seedcamp, Antler, a16z ... Free, open, no paywall". Listings link to each company's own website and to founders' LinkedIn profiles. Filters: `?vertical=B2B` (also Fintech, Healthcare, Consumer) and `?source=yc` (also techstars, seedcamp, antler). There is no robots.txt and no terms page (both 404), so automated use is neither allowed nor forbidden in writing.

**Proposed shape.**
- Discovery only: read a filtered listing page, take company names and websites as candidates, then research each company on its own website exactly as today. The directory is never evidence (it stays in `DIRECTORIES`).
- Directory tags such as "B2B" are search clues, never proof of fit.
- No people data from the directory; people still come only from the company's own pages.
- Polite access: identify the app in the User-Agent, read a few pages per run, cache them, show "found via StartupWho" in the shortlist.
- Map a confirmed target to filters (for example B2B software targets to `vertical=B2B`), within the run's fetch cap, journaled like other fetches.

**Before building.** Ask StartupWho for permission or published terms for automated use, and decide whether hosted mode may use it.

## Own company index for instant discovery (added 18 October)

**Why.** Every run discovers companies by web search while the user waits, and search returns pages about companies rather than prospects. The 18 October Tavily check for private AI B2B SaaS startups returned list articles, the YC directory, BCG, SaaStr and Salesforce (`data/evaluations/discovery-policy2-2026-10-18.json`). The 18 October research runs then assessed large enterprises such as nice.com, hitachienergy.com and lumen.com one at a time: about a minute per run for 3 or 4 companies, 8 to 23 seconds per Gemma assessment, and 4 of 16 Gemma calls failed (`data/evaluations/research-run-2026-10-18.sqlite3`). The time goes into finding and discarding poor candidates, not into research.

**What was checked (18 October).** Explee's public API specification (https://api.explee.com/public/api/openapi.json) shows why it answers in seconds: one query against its own prebuilt company index (its pricing page claims 105M companies and 536M people). Its "intent" is stored, filterable fields: currently hiring and for which titles, last funding within 6 or 12 months, employee and traffic growth, technologies, advertising pixels, and startup, SaaS, AI and B2B flags. AI runs only after filtering: a free natural-language-to-filters call, then optional 0 to 5 scoring per criterion on the filtered companies. The API allows 150 concurrent requests and up to 1,000 companies per page. These are Explee's own descriptions, not independently verified. Its research is not deeper than ours (the 15 October preview described stripe.com as "Stripe It Now Inc" with five employees), so the gap is discovery, not research quality.

**Proposed shape.**
- A shared company index in Postgres: `companies` (domain, name, description, country, size estimate, category flags, first seen, last checked), `signals` (one dated, sourced statement per row, such as hiring for a named title, a funding filing or a launch) and description embeddings with pgvector. Signals stay source claims, never intent scores, as in `signals.py`.
- Fill it in the background, never while a user waits:
  1. Companies that runs already fetch (`source_cache`), with `company_signals()` applied at index time. Only facts from public pages are shared; another account's targets, review decisions and exports stay private.
  2. Bulk seed sources for one segment first, for example private AI B2B SaaS: SEC Form D filings (recent private fundraising; they give names, not websites, so each domain match needs verification), public Greenhouse, Lever and Ashby job-board JSON reached through the company's own careers link rather than guessed board names, StartupWho listings (entry above), and a public popularity ranking such as Tranco or the Chrome UX Report rank as a liveness and traffic proxy.
  3. Each company's own home, pricing, careers and about pages for the description, category flags and detectable tools and advertising pixels.
- Refresh on a schedule: job boards weekly, funding filings as published, pages and liveness monthly.
- At search time, Gemma converts the confirmed target into filters once, one query combines those filters with embedding similarity and returns hundreds of candidates, Gemma scores the top 20 to 50 in parallel, and the existing evidence and review flow runs on the best few. Web search remains the fallback when the index has too few matches.
- Plugs in behind the `Search` protocol in `providers.py`, which would need to accept structured filters as well as a query string.
- No people or email data in the shared index. People still come only from each company's own pages, and any contact lookup stays per account with the user's own provider.
- The code that builds the index can be open source; the populated, refreshed index belongs to the hosted service. Each row records its source and licence so exports respect source terms.
- Building and refreshing the index uses no SerpApi or Tavily calls.

**Before building.** Confirm terms for automated use of each source (StartupWho publishes none). Start by indexing companies from existing saved runs, which needs no provider spend, and compare accepted-company yield with web-search discovery on the labelled targets. Rough estimate for one segment of about 50,000 companies: around a day of polite page fetching on one worker; at the measured Gemma speed, extraction on a single instance would take about a week, so apply cheap filters first or run inference in parallel.
