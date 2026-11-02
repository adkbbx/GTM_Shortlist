# Demo video script (3 minutes)

For the Meta Global AI Developer Hackathon submission. Judging weights: Impact 30, Meta AI tooling 25, Demo 25, Technical depth 20. Show only work built during the event: the agent start page, the live board and the terminal eval. Do not show the classic workspace.

**Before recording**

- Open https://gtmshortlist--gtm-shortlist-agent-web.us-east.modal.run (always on, on Modal) a few minutes before and check `/api/health` says `"investigator_model_available": true`.
- Run one search for `eygentic.com` with 5 companies (about $0.30) and keep its link. Recording a search from scratch takes 2 to 4 minutes, so record the start live and cut to the finished board.
- Every company and quote below comes from the 30 October live runs. If your recording shows different companies, read out what is on screen instead. Never say a quote that is not visible.

| Time | Screen | Say |
|---|---|---|
| 0:00 to 0:15 | The start page, with the replay console playing a real search on the right | "I sell to B2B startups. Every week I spend hours deciding which startups are worth a cold email, and most lead tools just hand me a list of logos with no reason behind them." |
| 0:15 to 0:30 | Type `eygentic.com` into the one field, press start | "GTM Shortlist needs one thing: your website. No forms, no ideal customer profile to fill in. Everything else it works out and shows its work." |
| 0:30 to 0:55 | "What we assumed" panel filling in | "Muse Spark 1.3 reads my site and works out what I sell, who buys it, and the signals that say a company needs it now. Every assumption has a quote from my own pages. If it guessed wrong, I fix it with one click. Here it says any size, but I sell to seed to Series A startups, so I change Company size." |
| 0:55 to 1:15 | Competitors list | "Next it finds my competitors with web search, and it only calls one direct when the competitor's own homepage proves the same job for the same buyer. Direct competitors become disqualifiers." |
| 1:15 to 1:45 | Live board: point at the pinned monitor (step tracker, time, quotes kept, cost) and the live cards of companies being researched | "This bar always shows what the agent is doing right now. Then it finds companies from signals, not a database: job posts and news. Each one gets its own agent loop: up to four searches and six page reads, calling our fetch tool, looking for fit, a current need, and whether they already use a competitor. It even scans each homepage's code for competitor widgets." |
| 1:45 to 2:05 | Open a Shortlisted card and its quote popover, click the source link | "Korevity is Shortlisted. The quote: an SDR role posted 13 October, 'to build US-market pipeline from ground up'. One click opens the exact sentence on their page. Every verdict has a dated quote I can check myself." |
| 2:05 to 2:15 | The "Why now" and "Opening line" box on the same card, press Copy | "And it tells me what to say. The opening line is written only from those quotes, and Muse Spark Open checks every statement against them before it is shown." |
| 2:15 to 2:35 | A Rejected card (Dr. Squatch from the crisp.chat run) | "And this is why it is not just a search wrapper. With crisp.chat as the seller, Dr. Squatch was Rejected: its homepage code loads Gorgias, a direct competitor. A second model, Muse Spark Open on Baseten, never sees the web or the company name. It only judges whether each quote really supports the claim. Plain code makes the verdict, not a model." |
| 2:35 to 2:50 | Telemetry footer, then terminal running `shortlist agent eval` | "Every call is logged with tokens, searches and dollars: about seven cents a company. And I score it against companies I labelled by hand, with precision, recall, cost and latency, plus an ablation without the skeptic." |
| 2:50 to 3:00 | The start page with the URL | "Try it with your own website, link below. Built solo at the Meta hackathon with Muse Spark and Muse Spark Open." |

**Notes**

- Only say eval numbers once the labelled eval has actually run. Until then, say "I score it against companies I labelled by hand" and show the command, not a result.
- Keep the cursor still on quotes long enough to read (about 2 seconds).
- Record at 1366 by 768 or larger; zoom the browser to 110% so quotes are legible in the video.
