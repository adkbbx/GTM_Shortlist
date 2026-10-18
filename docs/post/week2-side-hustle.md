*This is a submission for the [Hacktoberfest Open-Source AI Challenge Week 2: Side Hustle](https://dev.to/challenges/hacktoberfest-week2-2026-10-12)*

![The GTM Shortlist landing page at eygentic.tech: "Find who fits. Check why." A company box on the left, a funnel of candidates narrowing through Offer, Target and Evidence, and an illustrative shortlist on the right](https://raw.githubusercontent.com/adkbbx/GTM_Shortlist/worktree-week2-post/docs/post/landing.png)

This month I've shipped an app every week for these challenges, with two coding agents doing most of the typing. Building software isn't the hard part anymore. The hard part starts the day after you ship it: who do you sell it to?

I run Eygentic, which runs customer-acquisition experiments for B2B and SaaS teams: which customers, messages and channels actually work, before anyone spends money on growth. Every one of those experiments starts with the same boring thing, a list of companies that might buy. Most prospecting tools I looked at sell you access to a big pre-built database of companies and contacts, and you trust that each row is right. That works if you already have a sales budget. A two-person AI startup that just shipped usually doesn't.

If distribution is now the hard part of starting a software company, I don't think it should only be available to companies that can already afford a sales stack. So I built the tool I wanted for my own first list, made it open source, and put it online.

## What I Built

**GTM Shortlist.** You type your company's website. It reads your homepage, works out what you sell and who should buy it, finds companies that match, reads their own websites, and gives you a short list where every claim points to the exact words on that company's site. Things it can't find stay marked as unknown instead of being guessed.

| Step | What happens | Who decides |
| --- | --- | --- |
| Your offer | Gemma reads your homepage once and drafts what you sell and who to look for | you edit it |
| Your target | the draft becomes fit checks a company's own site can show, plus exclusions. Nothing is searched until you confirm | you |
| Discovery | SerpApi Google searches, built from a short company phrase, not your whole sentence | code filters the results |
| Research | up to three saved pages per company. Gemma proposes findings with quotes | code checks every quote is on the page |
| Verification | a second Gemma call judges whether each quote really supports the check | the model, and it can say no |
| Shortlist | Fits, Needs verification or Does not fit, ranked by how many required checks are supported | code |
| Review | accept or reject, export Excel, CSV or JSON with an Evidence sheet, draft a first email that cites the source | you |

"Fits" only shows up when every required check is supported by a quote that was found word for word on the company's site and then verified. Your accept or reject is stored separately from the model's opinion, and nothing in the app treats a fit as buying intent. It never sends an email for you.

![Confirm your target: the offer GTM Shortlist drafted from eygentic.com ("Focused customer-acquisition experiments for B2B and SaaS teams...") and the target "B2B AI SaaS companies", both editable, with discovery waiting for confirmation](https://raw.githubusercontent.com/adkbbx/GTM_Shortlist/worktree-week2-post/docs/post/confirm-target.png)

*The confirmation step on my own website. Gemma drafted the offer from eygentic.com. Nothing is searched until I confirm it.*

**Who would pay for this?** Founders of small B2B software and AI companies doing their own sales, and the GTM consultants and outbound agencies who build a new list for a new campaign every week. The hosted version gives you your first three companies free with no card. Research there runs on credits, one per researched company, and paid checkout isn't built yet. Self-hosting is free apart from your own search and model costs. The managed version I'm testing through Eygentic is a $99 reviewed pilot shortlist. Nobody has paid that yet, so treat it as a price I'm testing, not a business.

## The first real run, and what it got wrong

On 16 October I ran the hosted app on my own website with the target "B2B AI SaaS companies". Three SerpApi searches, eight Gemma calls, 17 page reads. Two of the searches failed. The first time, the whole run stopped with nothing, because discovery wanted every query to succeed before it used any candidates, and all three credits came back. I changed that so a failed query is saved and the run carries on with the candidates it already has. The same run then finished from its saved candidates without searching again.

![Review your shortlist: three researched companies. NachoNacho needs verification, builtin.com has no company description established, and DealHub fits the required criteria. A notice says discovery was incomplete](https://raw.githubusercontent.com/adkbbx/GTM_Shortlist/worktree-week2-post/docs/post/first-hosted-run.png)

*The first hosted shortlist. DealHub met the required checks. builtin.com is a publisher that lists other companies, and it used up one of my three research slots.*

The app didn't invent anything about Built In. It said every check was unknown. But I'd still paid to research a website that was never a customer. So I went back over every run I had saved, without making any new provider calls:

- 18 local runs had saved 19 company records from 74 provider calls, and **none of them qualified as a fit**.
- Searching my confirmed target sentence word for word mostly returned guides, list articles, Gartner reviews, YouTube videos, job posts and glossaries. In two of the runs, 12 of 12 results were the wrong kind of page.
- Some required checks were things a company's website never says. Private ownership came back unknown 16 times out of 16, funding stage 3 out of 3, internal pain points 15 out of 15.

So the fixes went in the order that cost me the most:

- **Search like a person looking for a company.** Queries now use a short phrase ("B2B SaaS", "channel partner programs") anchored on a company's own pages, like "software company official website" or "startup platform pricing".
- **Refuse the wrong pages before paying to read them.** Video, social, job, review and market-research sites, list articles, glossaries, directories and filtered listing pages are dropped before any fetch.
- **Warn about checks a website can't answer.** Confirmation now flags things like ownership, funding stage and budgets, with one click to make them "nice to have".
- **Never research the same company twice for the same seller.** Five of my saved runs had researched the same companies again.

I measured it on 104 real saved search results that I labelled by hand:

| | Before | After |
| --- | --- | --- |
| Real company pages reaching research | 16 of 21 | 21 of 21 |
| Other pages reaching research | 5 of 46 | 2 of 46 |
| Page reads spent on pages refused after download | 39 | 0 |

Replaying all 22 saved records through the new rules, 18 research credits wouldn't have been spent: 6 on pages that weren't companies and 12 on researching the same company again.

## Testing it on a target that isn't mine

To check it wasn't just tuned to my own offer, I pointed it at Unifyr's website. Unifyr sells channel-partner software, so its campaign needs companies that run partner programs. A live search found six real ones: Channel Institute, Channeltivity, Front, Hitachi Energy, Lumen and NICE. (That check ran through Tavily, the other search provider the adapter supports.) Then I ran the research on my laptop with Gemma 4 E2B through Ollama, at most six model calls a run and no searches. The first run qualified one of them. Each failure after that was a different, very specific problem:

**Invisible characters.** NICE's page puts zero-width spaces between words, so a quote that looked identical didn't match. Quote matching now ignores spacing, invisible characters and the style of quote marks and dashes. Every visible word and its capitalisation still has to match.

**The excerpts were mostly menus.** Hitachi Energy's research got 1,719 characters of page text, and most of it was a list of countries and languages. Gemma quoted the region menu as evidence. Long runs of short menu lines are now dropped before the model sees the page.

**A menu label isn't evidence.** Front came back as a fit, and the fit rested on a navigation link that said "Channel Partnerships". A quote that is only a one or two word label no longer counts.

**Hedged claims.** Gemma's own wording said the page "suggests" a partner program. A claim with "suggests", "may" or "likely" no longer establishes a check.

**Redirects and big pages.** Lumen's homepage redirects to a locale page, which the identity check didn't accept as a homepage. Front's homepage was over 1 MB and was refused outright. Both are read now.

**The page search found was thrown away.** Search had found each company's English partner-program page, and research started from the homepage instead. Now it reads the page search found as well, within the same three-page limit.

After those fixes, **4 of the 6 qualify**, each with verified quotes from its own site for both required checks: Channel Institute, NICE, Lumen and Hitachi Energy. NICE's evidence is its own partner page: "Our partners, including referral and resale partner, come from leading Carriers, UCaaS, CRM, VAR and System Integrators..." Channeltivity still needs verification, and Front doesn't qualify on a menu label. All of that ran on a 4.6B open model on my own GPU.

## Demo

**[eygentic.tech](https://eygentic.tech)**: enter your company website or name. Your first three companies are free and no card is needed.

If you'd rather not sign up, the source install has **Try it with sample data**. It runs the whole flow (confirm the target, open the evidence, accept or reject, export) on three invented companies with no keys, and every screen labels it as sample data.

## How I Built It

![Architecture: your browser, a Render web service at eygentic.tech serving the API and UI, Supabase for sign-in and Postgres, a Render background worker, and the worker's calls to SerpApi, the companies' own websites and Gemma 4 31B on DigitalOcean. The same code runs on a laptop with SQLite and Ollama](https://raw.githubusercontent.com/adkbbx/GTM_Shortlist/worktree-week2-post/docs/post/architecture.png)

The core is Python and FastAPI, the UI is React and TypeScript, and research runs in a separate worker process. Every search, page read and model call is reserved in a journal before it's sent, so if the worker restarts in the middle of a run it picks up from the journal instead of paying for the same call again. If it can't tell whether a call went through, it stops and says so rather than retrying. Each run has hard caps: four searches, eight model calls and three saved pages per company.

{% details Finding companies with SerpApi %}

Discovery calls SerpApi's Google engine and reads the organic results. A run gets at most four searches. A third discovery query only runs when the first two left fewer than six unique companies.

SerpApi's synchronous search can take longer than a short web request. My first hosted search failure took about 29 seconds against a 25-second timeout, so SerpApi now gets a 60-second read window. A timed-out search is never retried automatically, because it may still count against my allowance. Timeouts, connection errors, HTTP errors and malformed results each get their own message, without the key or the response body in the logs.

I'm on the free plan, 250 searches a month, so my coding agents weren't allowed to spend a search without asking me first. Development uses fixtures and saved responses, and the free Account API checks the key without spending a search. On 16 October the account still had 236 of its 250 searches left.

{% enddetails %}

{% details Gemma 4 on DigitalOcean: one model, four jobs %}

The hosted worker calls Gemma 4 31B (`gemma-4-31B-it`) on DigitalOcean's serverless inference through its OpenAI-compatible endpoint. It does four jobs: drafting your offer and fit checks from your homepage, proposing campaign ideas, proposing findings with quotes from each company's pages, and independently verifying whether each quote supports the check.

The offer draft first used JSON mode, which guarantees valid JSON but not the right fields. It now asks for a named function call with a fixed schema. On 30 labelled verification cases (29 written examples and one real excerpt), Gemma 4 31B got all 30 right. That's a check of the verifier, not an independent benchmark.

Running locally, the first Ollama runs failed in a quiet way. Ollama's server log said "truncating input prompt limit=2051" on every call, and my prompts were 6,044 to 12,813 tokens, so the instructions and schema were cut off and Gemma returned free-form summaries. A compact prompt profile and an 8,192-token context fixed it.

The model never decides on its own. Code checks that each quote is on the saved page, that the page belongs to the company, that every required check is supported, and how the shortlist is ranked.

{% enddetails %}

{% details Render: a web service and a worker that survive restarts %}

`render.yaml` defines two Docker services from the same image: the web service (FastAPI serving the React build and the API, with a health check at `/api/health`) and a background worker on 0.5 CPU and 512 MB. Keys are `sync: false`, so they live in the Render dashboard and never in the repo. The container runs as a non-root user.

I deploy exact commits with auto-deploy turned off, after GitHub Checks passes core tests, real Postgres tests, Windows tests, the browser suite and a container start-and-restart smoke test. During the first hosted run, a new deploy replaced the worker partway through. The new worker continued only from the saved candidates without repeating a search. After the run I restarted both services on purpose, and the JSON export I downloaded afterwards was identical to the one from before the restart.

{% enddetails %}

{% details eygentic.tech: one app, two hostnames %}

The app lives at `eygentic.tech`, with the `onrender.com` address kept as an alias. The domain reached Render fine, and the app answered `400 Invalid host header`, because it only trusted its one configured origin. Now each extra hostname has to be listed explicitly, and each gets its own Supabase sign-in callback. Unlisted hosts, foreign origins, wildcards and forwarded-host redirect tricks are still refused. Both hostnames answer the landing page with 200, unauthenticated research with 401 and requests from a foreign origin with 403.

{% enddetails %}

## Why Does Open Innovation Matter?

Finding customers is turning into the expensive part of starting a software company, and right now the answer is mostly rented: a database, a seat, a monthly plan. I want the method to be something anyone can read, run and change.

| Piece | What it does | Open? | Without it |
| --- | --- | --- | --- |
| GTM Shortlist (FastAPI, React, worker) | the whole workflow, evidence checks, exports | MIT | no app |
| Gemma 4 31B / E2B | drafts the offer, reads pages, quotes, verifies | open weights | no app |
| DigitalOcean | hosts Gemma 4 31B | hosted service, open model | Gemma 4 through Ollama on your laptop |
| SerpApi | Google results for discovery | hosted service | Tavily, or a saved search capture |
| Render | runs the web service and worker | hosted service | any Docker host, or `shortlist serve` |
| Supabase | sign-in and Postgres | open source, hosted | SQLite in local mode |

Here's what open actually changed for me.

**Your target list stays yours.** Who you're trying to sell to is about as private as business information gets. Self-hosted, research lives in your own SQLite file, and with a local model the only things that leave your machine are search queries and page requests to the companies' own websites.

**It's cheap enough to run for one founder.** Self-hosted with a local model, you pay for your own searches and nothing else, and at four searches a run, SerpApi's free plan covers dozens of shortlists a month. That's the "accessible to everyone" part.

**I could check the model's work.** Every failure above was found by reading saved pages and saved model output, not by guessing. Because the model is open, the same family runs on DigitalOcean and on my laptop, and the channel-partner results came from a 4.6B model on my own GPU.

**The rules are visible.** What counts as a fit, which pages get refused and how a quote is matched are all in the code, and you can disagree with them and change them.

## My First User

The first user is me. The first hosted shortlist was for my own offer at Eygentic, and DealHub is the first company that met my required checks. I haven't sold GTM Shortlist to anyone yet. What I want to find out next is whether a founder who has just shipped will trust a list where most of the checks say "unknown" instead of a confident score.

## Code

{% embed https://github.com/adkbbx/GTM_Shortlist %}

MIT licensed and built during the challenge, starting 14 October, 181 commits so far. The latest full check run had 782 backend tests passing (48 skipped, most of them Postgres-only) and 165 Playwright cases at phone and laptop size, covering the sample flow, confirmation, review, exports, reloads and keyboard use. Every live provider evaluation is recorded in `docs/PROGRESS.md`, including the ones that failed.

## How I built it with two agents

Same setup as last week. Claude Code wrote the plans and goal briefs, reviewed the diffs and reran the tests on my machine. Codex implemented much of it from those briefs, each with a list of what is true now, what should be true after, and a verification gate it had to pass before coming back. The repository's agent instructions say no live search, model or enrichment call without my explicit approval for that specific evaluation, which is why so many of the fixes above were found by replaying saved runs instead of spending new searches.

## Prize Categories

**Best Use of SerpApi.** SerpApi is how the hosted app finds companies at all. The worker sends compact Google queries anchored on a company's own pages, reads the organic results, and refuses non-company pages before reading them. Every search is journaled before it's sent and capped at four per run. It gets a 60-second read window with no automatic retry, and the free Account API checks the key without spending a search. On the free plan's 250 searches a month, development ran on saved responses.

**Best Use of DigitalOcean.** Every model call the hosted app makes goes to Gemma 4 31B (`gemma-4-31B-it`) on DigitalOcean's serverless inference, through its OpenAI-compatible endpoint: drafting the seller's offer and fit checks, campaign ideas, quoted findings and the independent verification of each finding. It scored 30 of 30 on my labelled verification cases. The same code switches to Ollama on a laptop by changing the model setting.

**Best Use of Render.** One Blueprint, two Docker services from the same image: the web service for the API and UI and a background worker for research. Secrets live in the dashboard and deploys are exact commits after CI passes. When a deploy replaced the worker in the middle of a real run, it carried on from the journal with no repeated search and no double charge, and restarting both services afterwards left the export identical.

**Best Use of a .tech Domain.** The app is live at [eygentic.tech](https://eygentic.tech), the .tech domain I claimed through Hacktoberfest, served by Render. Getting there meant fixing a real `400 Invalid host header`: the app now accepts an explicit list of hostnames, gives each its own Supabase sign-in callback, and still refuses unlisted hosts, foreign origins and forwarded-host redirects.

Built solo.

If you've shipped something and don't know who to sell it to, put your website into [eygentic.tech](https://eygentic.tech) and tell me in the comments which company it got wrong.
