# Winning plan: Meta hackathon, Indie track

**Goal:** a judge scores GTM Shortlist at least 8.5 on every criterion (Impact 30%, Meta AI tooling 25%, Demo 25%, Technical depth 20%), on work we control. Real users are a separate effort and are not in this plan.

**Deadline:** Wed 4 Nov, 9:00 PM ET (Thu 5 Nov, 11:00 JST). **We submit by 4 Nov, 5:00 PM ET** (5 Nov, 07:00 JST), with four hours of buffer.

**Budget:** live model spending stays inside the approved ledger ($4.37 left on 2 Nov). Planned: about $2.50; everything else reuses saved runs.

**The one sentence every piece must support:** "Put in your website. It tells you which companies need what you sell right now, and why, in their own words, and a second Meta model throws out anything it can't back up."

## Workstreams

### 1. Measure what the second model is worth (Meta tooling, Depth)

- **Build:** run the existing no-skeptic comparison (`shortlist/agent/evaluation.py`) over every saved live search. Same evidence, same verdict code, with and without Muse Spark Open's decisions. A script in `scripts/`, so anyone can repeat it.
- **Done when:** a table in HACKATHON.md and one line for the video: "Without Muse Spark Open, N companies would have been Shortlisted on quotes it rejected, out of M." Plus 2 or 3 real examples of quotes it rejected, with its reason.
- **Cost:** $0, no new model calls. **Owner:** me. **When:** 2 Nov.

### 2. One accuracy number (Impact, Depth)

- **Build:** refresh the review sheet with every company from today's live searches (the vanta.com, crisp.chat and eygentic.com examples, and the dental test), each with its key quotes and our verdict.
- **You:** mark each company "would contact / would not" (about 20 minutes).
- **Done when:** "It agreed with my judgement on X of Y companies; of those it Shortlisted, Z I'd actually email." In HACKATHON.md and the video.
- **Cost:** $0. **Owner:** sheet by me on 2 Nov, labels by you on 3 Nov.

### 3. Show the second model's reasoning (Meta tooling, Demo)

- **Build:**
  - each rejected or weak quote shows "Muse Spark Open threw this out" with its reason;
  - the board shows "Muse Spark Open kept 16 of 21 quotes";
  - new searches also keep a short excerpt of its reasoning (the provider change), shown under "How it decided".
- **Done when:** a judge can see, on any finished board, which claims the second model rejected and why, on phone and laptop, covered by browser tests.
- **Cost:** $0 to build. **Owner:** me. **When:** 3 Nov.

### 4. A clean live re-test and a fourth example (Demo, Impact)

- **Build:** one full live search without a website, under today's need-signal rule. If its evidence is strong, ship it as the fourth example, showing "no website".
- **Done when:** the evidence for each Shortlisted company is a real buying signal, not a phone number; or we learn it isn't and fix it.
- **Cost:** about $0.50. **Owner:** me. **When:** 2 to 3 Nov.

### 5. The video (Demo, which colours everything)

- **Build:** the animated scenes in Remotion, in brand fonts and colours: the opening type, the logo wall, the model badges, the filter motif, the counters, the REJECTED stamp, word-by-word captions and the end card. Then assemble the 2:00 cut and the 30-second vertical cut around your recordings and voice.
- **You:** record five screens in video mode (`?video=1`) and the narration, following `docs/demo-video-script.md`.
- **Done when:** a 1080p MP4 under 2:10 with no real company names, every number on screen measured (from workstreams 1 and 2), and captions on every word.
- **Cost:** $0. **Owner:** scenes by me on 3 Nov, recording by you on 3 Nov evening or 4 Nov morning, final assembly by me on 4 Nov.

### 6. Write-up, repo and post (Depth, Impact, bonuses)

- **Build:**
  - HACKATHON.md: Modal hosting, today's features, the two numbers, which model does what, honest limits;
  - a 200-word submission text;
  - a README section a judge can follow in 2 minutes;
  - the X post for the vertical cut.
- **Done when:** a judge who reads only the submission text knows what it does, which Meta models do what, the two numbers, and the link.
- **Owner:** me, on 4 Nov. **You:** post on X after submitting. Votes count through 8 Nov.

### 7. Stretch, only if 1 to 6 are done by 3 Nov evening: Muse Wonder for pages we can't read

- **Why:** 5 sites were skipped in one search alone because our fetcher couldn't read them. Muse Wonder can open a page the way a person would. That would be a genuinely unexpected use of a Meta model.
- **Limits:** at most 4 hours and $2. Keep it only if it reads at least half the pages that failed before.

### 8. Live-final readiness

- **Build:** a 1-company search that finishes in about a minute, a checklist (health, budget caps, a finished example open in a second tab), and a backup screen recording.
- **When:** 4 Nov.

## Order

| When | Me | You |
|---|---|---|
| 2 Nov | 1 (the comparison), 2 (the sheet), 4 (live re-test) | Post the Discord rules question |
| 3 Nov | 3 (the reasoning view), 5 (the Remotion scenes); 7 only if ahead | Label the sheet (20 min); record screens and narration |
| 4 Nov | Assemble the video, 6 (write-up), 8; submit by 5 PM ET | Watch the cut; post on X after submitting |

## Not doing

New features beyond these, real-user outreach (handled separately), an MCP server (it goes in the write-up as the next step).
