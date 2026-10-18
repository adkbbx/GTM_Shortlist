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
