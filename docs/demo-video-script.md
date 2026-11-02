# Demo video script (3 minutes)

For the Meta Global AI Developer Hackathon submission. Judging weights: Impact 30, Meta AI tooling 25, Demo 25, Technical depth 20. The video is the main thing judged. Show only work built during the event (the agent start page, the live board, the examples, the Your shortlist page), never the classic workspace.

The story is a real user: you, running Eygentic, finding startups that need you this week. Every quote below is on screen in the shipped eygentic.com example (31 October, five companies, $0.42). Say only what is visible.

## Before recording

- Open https://gtmshortlist--gtm-shortlist-agent-web.us-east.modal.run a few minutes early. Check `/api/health` shows `"investigator_model_available": true`.
- Record at 1440 by 900 or larger, browser zoom 110%, cursor still for about 2 seconds on every quote.
- Shot A (live search): type `eygentic.com`, choose 3, press Find. Record the first minute live: "What we assumed" filling in, competitors, then companies being researched. You do not need to wait for it to finish (it takes 2 to 4 minutes and about $0.40).
- Shot B (finished board): the eygentic.com example under "Explore a finished search" (ThriveCart Shortlisted, Storable Rejected).
- Shot C: the start page, "I don't have a website", the popup filled in (do not submit).
- If shot A's live search finds something better than the example, you may use it instead, but read out only what is on that screen.

## Script (about 410 words)

| Time | Screen | Say |
|---|---|---|
| 0:00 to 0:12 | The start page, the lines flowing into the search box | "I run a small growth agency for B2B startups. The work isn't the hard part. Knowing which startups need it *this week* is." |
| 0:12 to 0:22 | Shot A: type `eygentic.com`, pick 3, press Find | "GTM Shortlist needs one thing: my website. No filters. No ideal customer profile to fill in." |
| 0:22 to 0:45 | Shot A: "What we assumed" filling in, then the competitors | "Muse Spark 1.3 reads my site and writes down what I sell, who buys it, and what would make a company need me now, and every assumption carries a quote from my own pages. It finds my competitors with web search, and only calls one direct when that company's own homepage proves it." |
| 0:45 to 1:08 | Shot A: companies being researched, the activity rail | "Then it hunts for signals, not a database: open job posts on Lever, Greenhouse and Ashby first, then news. Each company gets its own agent loop on Muse Spark, with web search and our fetch tool. It reads their site, their job board, even their homepage code, looking for a competitor's widget." |
| 1:08 to 1:32 | Shot B: ThriveCart card, open its quote, click through to the Greenhouse post | "Here's a search I ran last week. ThriveCart is Shortlisted. Why? Their open job post: 'As one of the first three SDRs in this enterprise initiative'. One click opens that exact sentence. They're building outbound from scratch, which is exactly who I help." |
| 1:32 to 1:48 | Shot B: ThriveCart's opening line | "It writes the first line of my email from those quotes only. Then Muse Spark Open, a second model on Baseten with no web access, checks every statement. Anything it can't match is rewritten or dropped." |
| 1:48 to 2:08 | Shot B: Storable in Rejected, its quote | "Storable looked like a fit, but it's Rejected, and it says why: 'Storable proudly employs over 800 employees'. I told it once that I sell to seed to Series A startups. The models gather and judge the evidence; plain code makes the verdict." |
| 2:08 to 2:24 | Shot B: the Needs a look column | "Everything else is Needs a look, with exactly what's missing. A chatbot will give you reasons too. Nothing makes them true. Here, a claim only appears if its exact sentence is on a page it fetched." |
| 2:24 to 2:36 | Shot C: "I don't have a website", the three questions | "No website yet? Describe what you sell and who buys it. Every claim about you then quotes your own words." |
| 2:36 to 2:48 | Shot B: the board's footer (time, searches, cost) | "Every model call is logged with tokens and dollars. That search: five companies, forty-two cents." |
| 2:48 to 3:00 | The start page with the URL on screen | "Built solo for the Meta hackathon on Muse Spark and Muse Spark Open. Try it on your own website. Link below." |

## Optional swaps

- **Accuracy (use only once the review sheet is labelled):** replace the 2:08 line's last two sentences with "I checked it against [N] companies I reviewed by hand: it agreed with me on [X] of them." Never say a number that has not been measured.
- **Comparison (use only after you run it):** if ChatGPT or Claude was asked the same question and some of its claims could not be found on the linked page, replace "A chatbot will give you reasons too. Nothing makes them true." with "I asked a chatbot the same question: [X] of its [Y] claims weren't on the page it linked."

## Notes

- Keep it under 3:00. If long, cut the 0:45 line to "Each company gets its own agent loop on Muse Spark: its site, its job board, even its homepage code."
- Name the Meta models out loud (Muse Spark 1.3, Muse Spark Open on Baseten); they are a quarter of the score.
- Do not show anyone's personal name, home location or email address on screen.
