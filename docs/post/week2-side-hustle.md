*This is a submission for the [Hacktoberfest Open-Source AI Challenge Week 2: Side Hustle](https://dev.to/challenges/hacktoberfest-week2-2026-10-12)*

![The GTM Shortlist landing page at eygentic.tech: "Find who fits. Check why." Candidates flow through Offer, Target and Evidence into an illustrative shortlist, then the page scrolls to "Every row opens to its sources"](https://raw.githubusercontent.com/adkbbx/GTM_Shortlist/worktree-week2-post/docs/post/landing-v2.gif)

*GTM Shortlist, live at [eygentic.tech](https://eygentic.tech).*

AI has made building software cheap and fast, and you can see it in the numbers:

- In 2025, Apple received about [557,000 new app submissions](https://thenextweb.com/news/vibe-coding-apple-app-store-surge-crackdown), the most since 2016.
- In December 2025, new iPhone apps were [up 60% on a year earlier](https://the-decoder.com/vibe-coding-may-be-behind-a-60-percent-spike-in-new-ios-apps/), after three years of flat numbers (a16z's analysis, which also says this doesn't prove AI coding tools are the cause).
- On GitHub, developers created [more than 230 new projects every minute](https://github.blog/news-insights/octoverse/octoverse-a-new-developer-joins-github-every-second-as-ai-leads-typescript-to-1/), and over 36 million new developers joined in a year.

Customers didn't multiply the same way. When CB Insights looked at [431 venture-backed startups that shut down since 2023](https://www.cbinsights.com/research/startup-failure-reasons-top/), the most common underlying problem was poor product-market fit, in 43% of the cases they could explain. In plain words, the product got built, and not enough of the right people bought it.

I've felt this myself. This month I shipped an app every week for these challenges, with two coding agents doing most of the typing. Building isn't the hard part anymore. The hard part starts the day after you ship: who do you sell it to?

I'm building [Eygentic](https://eygentic.com), a company that runs customer-acquisition experiments for B2B and SaaS teams: it tests which customers, messages and channels actually work before anyone spends money on growth. Every one of those experiments starts with the same boring thing, a list of companies that might buy. Most prospecting tools I looked at sell you access to a big database of companies and contacts, and you have to trust that each row is right. That's fine if you already have a sales budget. A two-person AI startup that just shipped usually doesn't.

If finding customers is now the hard part of starting a software company, I don't think it should only be possible for companies that can already afford a sales team. So I built the tool I wanted for my own first list, made it open source, and put it online. It's not complete yet, but this challenge gave me the motivation to finally get started on it.

## What I Built

**GTM Shortlist.** GTM means "go to market", the work of getting a product in front of people who will buy it. You give the app your company's website, and it:

1. **Reads your website** and writes a short description of what you sell and who might buy it. You fix anything it got wrong.
2. **Searches Google** for companies that match. Nothing is searched until you've confirmed who you're looking for.
3. **Visits each company's own website** and looks for proof that it matches, like a sentence on its product page.
4. **Gives you a short list.** Next to each company it shows the exact sentence from that company's site that backs up the match. If it can't find proof, it says "unknown" instead of guessing.
5. **Lets you decide.** You mark each company yes or no, download the list as a spreadsheet, and can start a first email that points to what you found. It never sends anything for you.

![The demo at eygentic.tech/?demo=1, with invented companies: the app understands the offer, explores the market, waits for the target to be confirmed, checks candidates, shows the exact passage behind a match, and ends with accept or reject](https://raw.githubusercontent.com/adkbbx/GTM_Shortlist/worktree-week2-post/docs/post/workflow-v2.gif)

*Every step, using the demo on eygentic.tech. The companies and sentences are made up for the demo, so you can try it without an account or spending anything.*

A company is only marked as a fit when every must-have is backed by a sentence found word for word on its own site, and a second check by the model agrees that the sentence really says that. Your yes or no is kept separate from the app's opinion, and a fit never means "this company wants to buy".

**Who would pay for this?** Founders of small B2B software and AI companies who do their own sales, and the consultants and agencies who build a new list of target companies for every campaign. The hosted version gives you your first three companies free, with no card. After that, research runs on credits, one per company researched, and paying for more credits isn't built yet. If you run it yourself, it's free apart from your own search and AI costs.

## The first real run, and what it got wrong

On 16 October I tried the hosted app on my own website, [eygentic.com](https://eygentic.com), looking for "B2B AI SaaS companies". To find companies, the app runs a few Google searches one after another. The first search worked and found 8 companies, but the next one failed. The app had a rule that every search had to work before it used any of the results, so it threw away all 8 and stopped with nothing. It gave my three credits back, but I still had no list.

So I changed the rule: if one search fails, the app now keeps the companies the other searches already found and carries on. I picked the same run back up from where it stopped, and it researched three of the 8 companies it had saved, without searching again. That gave me my first real shortlist.

![Review your shortlist: three researched companies. NachoNacho needs verification, builtin.com has no company description established, and DealHub fits the required criteria. A notice says discovery was incomplete](https://raw.githubusercontent.com/adkbbx/GTM_Shortlist/worktree-week2-post/docs/post/first-hosted-run.png)

*The first real shortlist. DealHub matched. NachoNacho needs more checking. builtin.com isn't a company I could sell to at all: it's a website that writes lists of other companies, and it used up one of my three research slots.*

The app didn't make anything up about Built In. It just said "unknown" for everything. But I'd still spent a credit researching a website that was never a customer. So I looked back at every test run I had saved, without paying for any new searches:

- 18 test runs had researched 19 companies, and **not one of them came out as a real match**.
- My searches were bad. I was searching Google for my whole target sentence, and Google mostly returned how-to guides, "top 10" lists, reviews, YouTube videos, job ads and dictionary pages, not companies.
- I was asking for things websites don't say. Whether a company is privately owned, how much funding it has, or what its internal problems are is almost never on its own website, so those answers were always "unknown".

So I changed four things:

- **Search for companies, not articles.** It now searches with a short phrase like "B2B SaaS", plus words you only find on a company's own site, like "official website" or "pricing".
- **Skip pages that aren't companies before opening them.** Videos, job boards, review sites, directories and "top 10" lists are dropped straight from the search results.
- **Warn me when I ask for something a website won't say,** and let me turn it into a nice-to-have with one click.
- **Never research the same company twice** for the same business.

To check the search fix, I took real search results that my earlier test runs had saved, marked each one as either a company's own website or something else by looking at its address and title, and ran them through the old version and the new one:

- **Real company websites:** there were 21. The old version let 16 of them through to research. The new one lets all 21 through.
- **Pages that weren't companies** (job boards, directories, review sites and so on): there were 46. The old version let 5 of them slip through. The new one lets 2 through.
- **Pages opened for nothing:** the old version opened 39 pages only to throw them away afterwards. The new one throws them away before opening them, so it wastes none.

Running my old research through the new rules, 18 of the 22 companies I had already researched would have been skipped: 6 because they weren't companies at all, and 12 because they were the same company researched again.

## Real websites are messy

Testing on more real websites turned up more problems, each with its own fix:

- **Invisible characters.** One site hides invisible spaces between its words, so a sentence the model copied didn't look like the same sentence to the app. Now the app ignores invisible characters, but every real word still has to match.
- **Menus instead of content.** On some pages, most of the text was the list of countries and languages, so the model quoted the menu as proof. Long menus are now removed before the model reads the page.
- **A menu link isn't proof.** One company counted as a match because of a single link in its menu. One or two words from a menu no longer count.
- **"Suggests" isn't proof.** When the model says a page "suggests" or "may" show something, that no longer counts as a yes.
- **Pages it couldn't open.** Some homepages send you on to another address, and some are very large. Both used to be skipped, and both can be read now.
- **The best page was ignored.** Search often finds the exact page that proves the point, but research used to start from the homepage instead. Now it reads the page search found as well.

## A small model on my laptop vs a big one on DigitalOcean

After all those fixes, I wanted to know whether the list was finally useful for my own business. I took the 12 companies a saved web search had found for Eygentic on 13 October, looking for private AI software startups that sell to businesses, and researched them again with no new searches.

First I used small open models on my laptop: Gemma 4 E2B and Qwen 3.5 4B. With the fixes in, they stopped wasting money on pages that were never going to work, but they rarely copied the proof from a page, so **none of the product companies came out as a match**.

Then I used Gemma 4 31B, the bigger version of Gemma, on DigitalOcean. It took 18 AI calls for all 12:

- **DelegateZero: a match.** Its own site says "DelegateZero - AI Decision Proxy for B2B SaaS Founders", and its pricing page lists monthly plans.
- **Prismatic: a match** ("Embedded iPaaS for B2B Software Companies"), after one more fix. The model sometimes answered a check with a word like "cleared" instead of yes or no, and the app threw the whole company away. It now reads those words properly, and re-reading the answer the model had already given turns Prismatic into a match.
- **Smeron and BackOfficeBoss: set aside.** They build custom software for clients rather than selling a product, so they aren't buyers for me.
- **Six others: need more checking.** The app couldn't find enough proof on their own websites, so it says so instead of guessing.
- **Two: refused.** The app couldn't confirm who owns the website.

So 2 of the 12 are real leads for Eygentic. It's a short list, but every name on it comes with its proof, and the small models couldn't get there at all.

## Demo

**[eygentic.tech](https://eygentic.tech)**: type your company's website or name. Your first three companies are free and no card is needed.

If you'd rather not sign up, tap **Try the demo** on the start page, the walkthrough in the GIF above. You can also install it from the code and choose **Try it with sample data**, which runs the whole thing on three made-up companies with no accounts or keys.

## How I Built It

![Architecture: your browser, a Render web service at eygentic.tech serving the API and UI, Supabase for sign-in and Postgres, a Render background worker, and the worker's calls to SerpApi, the companies' own websites and Gemma 4 31B on DigitalOcean. The same code runs on a laptop with SQLite and Ollama](https://raw.githubusercontent.com/adkbbx/GTM_Shortlist/worktree-week2-post/docs/post/architecture.png)

The app is a website (React) with a Python server behind it, plus a separate background worker that does the slow research. Before the worker does anything that costs money, like a search, a page visit or a call to the AI model, it writes it down first. If the server restarts halfway through, it carries on from its notes instead of paying for the same thing twice, and if it can't tell whether a request went through, it stops and tells you instead of trying again. Every run has hard limits: at most 4 searches, 8 AI calls and 3 pages per company.

{% details SerpApi: the Google search %}

SerpApi gives the app Google search results, at most 4 searches per run. My first real search took about 29 seconds and timed out, so the app now waits up to 60 seconds, and a search that times out is never retried automatically, because it may already count against my monthly limit.

I'm on SerpApi's free plan, 250 searches a month, so my coding agents had to ask me before spending any. While building, the app used saved search results instead of new ones, and SerpApi's free account check confirms the key works without using up a search. On 16 October I still had 236 of my 250 searches left.

{% enddetails %}

{% details Gemma on DigitalOcean: the AI model %}

The hosted app uses Gemma 4 31B, an open model from Google, on DigitalOcean's hosted AI service, so I don't run any servers for it. It does four jobs: describing your business from your homepage, suggesting campaign ideas, finding quotes on each company's site, and double-checking each quote. On 30 test cases for that double-check (29 written for the test, 1 from a real website) it got all 30 right. That's a check of one job, not an independent benchmark.

On my laptop, the first runs gave useless answers. The program running the model was quietly cutting my instructions short, keeping about 2,000 pieces of text out of 6,000 to 12,800, so the model never saw what I'd asked for. Shorter instructions and a bigger limit fixed it.

The model never has the last word. Ordinary code checks that each quote really is on the page, that the page belongs to that company and that every must-have is covered, and it decides the order of the list.

{% enddetails %}

{% details Render: running the app online %}

Render runs two pieces from the same code: the website and the background worker. Passwords and keys live in Render's dashboard, never in the code. I only release a version after the automatic tests pass. During the first real run I released an update halfway through, and the new worker picked up exactly where the old one stopped, without searching again. Afterwards I restarted everything on purpose, and the exported results were exactly the same.

{% enddetails %}

{% details eygentic.tech: the web address %}

[eygentic.com](https://eygentic.com) is the company. [eygentic.tech](https://eygentic.tech) is the tool, open for anyone to use. When I first connected the domain to Render, the app refused it with "400 Invalid host header", because it only trusted its original Render address. Now it accepts a fixed list of addresses, each with its own sign-in link, and still refuses anything else.

{% enddetails %}

## Why Does Open Innovation Matter?

Finding customers is becoming the expensive part of starting a software company, and right now the answer is mostly rented: you pay for access to someone else's database, every month. I want the method to be something anyone can read, run and change.

| Piece | What it does | Open? | If you don't want it |
| --- | --- | --- | --- |
| GTM Shortlist | the whole app | open source (MIT licence) | |
| Gemma 4 | reads websites, writes, double-checks | open model | |
| DigitalOcean | runs Gemma online | paid service running an open model | run Gemma on your own computer |
| SerpApi | Google search results | paid service with a free plan | Tavily, or saved search results |
| Render | runs the app online | paid service | any server, or your own computer |
| Supabase | sign-in and database | open source | a simple file on your computer |

Here's what being open actually changed for me.

**Your list stays yours.** Who you're trying to sell to is private business information. If you run it yourself with a local model, your research stays in a file on your own computer. The only things that leave it are the searches and the visits to the companies' own websites.

**It's cheap enough for one person.** Run it yourself and you only pay for searches and the model. At 4 searches a run, SerpApi's free plan covers dozens of lists a month. That's what "accessible to everyone" means to me.

**I could check its work.** Every problem above was found by reading the saved pages and the model's saved answers, not by guessing. Because the model is open, I could try the small version on my laptop and the big version online on exactly the same pages, and see for myself that this job needs the big one.

**The rules are visible.** What counts as a match, which pages get skipped and how quotes are checked are all in the code, so you can disagree with them and change them.

## What it can't do yet

- **It doesn't find email addresses** or contact details. It finds companies and the proof that they fit. Reaching out is still up to you.
- **Some things stay unknown.** Funding, ownership and budgets are rarely on a company's own website, so the app leaves them as "unknown" instead of guessing.
- **Small models aren't good enough yet.** On my laptop they couldn't produce a single real match for my own business. Research needs a bigger model, which means a hosted service or a powerful computer.
- **Runs are small.** Up to three companies at a time, so it's a shortlist, not a database.
- **You can't buy more credits yet.** The free three work, but paying for more isn't built.

## My First User

The first user is me. The first real shortlist was for Eygentic, the company I'm building, and DealHub was the first company that matched what I was looking for. The bigger model later added DelegateZero and Prismatic. I haven't sold GTM Shortlist to anyone yet. What I want to find out next is whether a founder who has just launched will trust a list that says "unknown" a lot, instead of one that gives every company a confident score.

## Code

{% embed https://github.com/adkbbx/GTM_Shortlist %}

Open source under the MIT licence and built during the challenge: the first commit was on 14 October, and there are 188 so far. 838 automated tests on the server side and 173 browser tests at phone and laptop sizes pass, and every real test I ran with paid services is written down in `docs/PROGRESS.md`, including the ones that failed.

Claude Code wrote the plans, reviewed the changes and ran the tests on my machine, and Codex wrote much of the code from those plans. The project's rules say no paid search or AI call without my approval for that specific test, which is why so many of the fixes above came from re-checking saved runs instead of paying for new searches.

## Prize Categories

**Best Use of SerpApi.** SerpApi is how the hosted app finds companies at all. The app sends short Google searches aimed at companies' own websites, skips results that aren't companies before opening them, and keeps every run to 4 searches. Each search is written down before it's sent, a slow search gets up to 60 seconds, and a failed one is never retried automatically, so the free plan's 250 searches a month go a long way.

**Best Use of DigitalOcean.** Every AI call the hosted app makes goes to Gemma 4 31B (`gemma-4-31B-it`) on DigitalOcean's hosted AI service: describing the business, suggesting campaign ideas, finding quotes and double-checking each one. On the same 12 saved companies for my own business, the small models on my laptop found no product company that matched, and Gemma 4 31B on DigitalOcean found two, each with proof from its own website, in 18 AI calls.

**Best Use of Gemma.** Gemma does every AI job in the hosted app: it reads your homepage and drafts your offer and must-haves, suggests campaign ideas, finds quotes on each company's own site, and double-checks every quote. The same code runs Gemma 4 31B on DigitalOcean or Gemma 4 E2B on a laptop through Ollama, and running both on the same 12 companies showed this job needs the bigger one: two real matches with proof, against none.

**Best Use of Render.** Render runs the website and the background research worker from the same code, with passwords kept in the dashboard. When I released an update in the middle of a real run, the worker carried on from its notes with no repeated searches and no double charge, and restarting both afterwards left the results exactly the same.

**Best Use of a .tech Domain.** The app is live at [eygentic.tech](https://eygentic.tech), the .tech domain I claimed through Hacktoberfest, running on Render. eygentic.com is the company and eygentic.tech is the open tool, and both GIFs in this post were recorded on the live domain. Getting there meant fixing a real "400 Invalid host header" error: the app now accepts a fixed list of addresses, gives each its own sign-in link, and still refuses anything else.

Built solo.

If you've shipped something and don't know who to sell it to, put your website into [eygentic.tech](https://eygentic.tech) and tell me in the comments which company it got wrong.
