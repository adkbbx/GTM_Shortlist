# Meta Global AI Developer Hackathon: website-only research agent

GTM Shortlist already existed before the event: an open-source tool that researches companies for a B2B seller and keeps the source passage behind every assessment. For the hackathon (Indie track) I built a new agent on top of it. You type your company website and nothing else. The agent works out what you sell and who buys it, proves who your competitors are, finds companies, investigates each one, and sorts them into **Shortlisted**, **Needs a look** and **Rejected**, with the exact quote and source link behind every verdict.

Everything built during the event lives in its own places: `src/shortlist/agent/` (backend), `web/agent/` (UI), `tests/agent/`, `tests/ui/agent.spec.ts` and `tests/ui/agent-public.spec.ts` (tests), and for the public demo `deploy/modal_agent.py`, `docs/agent-public-demo.md` and `scripts/public_demo_test_server.py`. The few wiring edits outside those places are listed below.

Compare the event's work with the baseline: https://github.com/adkbbx/GTM_Shortlist/compare/pre-meta-hackathon...meta-hackathon

## Before and during the event

| | Built before the event (tag `pre-meta-hackathon`, commit `b620235`, 19 October) | Built during the event (branch `meta-hackathon`) |
|---|---|---|
| Input | Company name or website, then a required screen to confirm the offer, target and typed fit criteria | Website only. No confirmation screen. A vague site gets up to three clickable readings, never a required text box. Without a website, three short answers (what you sell, your ideal customer, which markets) stand in for it: every claim about the seller quotes those words, labelled "from your description" |
| Seller understanding | One model call drafts an offer and target from the homepage for the person to edit | Homepage plus up to five chosen pages (pricing, product, customers, about, integrations or the seller's own comparison page). Offer, buyer, existing customers, 2 to 5 fit checks, need and timing signals and any stated size or region, each with quotes |
| Competitors | Same-category companies set aside by a word-overlap rule | Found with web search, then proven from each candidate's own homepage: `direct` needs a quote for the same job and one for the same buyer. Direct competitors become disqualifiers |
| Research | `worker.execute_run`: Tavily or SerpApi search and an OpenAI-compatible Gemma model, one to three companies | An agent loop per company on Muse Spark with built-in `web_search` and a `fetch_page` tool, 10 companies by default (up to 20), five at a time, at most 4 searches, 6 page reads and 8 turns each |
| Competitor use | Not checked | A model-free scan of each fetched page's code (script sources, badges, "powered by" lines, integrations pages), targeted searches, and competitor customer pages that name the company. Every place checked is listed |
| Judging quotes | The same model verifies its own assessments | An independent skeptic (Muse Spark Open on Baseten) with no web access sees only the quote, the check, the source type and dates |
| Verdict | Fits / Needs verification / Does not fit | Plain code: Rejected for a skeptic-supported disqualifier; Shortlisted only with every required fit check, need or timing evidence dated within 180 days and a completed competitor check; otherwise Needs a look with the list of what is missing |
| Hiring signals | Not checked | Discovery searches Lever, Greenhouse and Ashby postings first and confirms each is still listed on a board that names the company. Every investigation reads the company's own job board, found only from links on its own site (`shortlist/agent/jobboards.py`); a posting page that cannot be read is built from the board's own posting text |
| What to say | Not offered | For each Shortlisted company, Muse Spark writes why now and an opening line from the quotes the skeptic supported; Muse Spark Open checks every statement against those quotes, and a note that claims more is rewritten once or dropped (`shortlist/agent/outreach.py`). On request, a short email and a LinkedIn note, held to the same quotes and the same check |
| Cost control | Per-run caps on searches and model calls | Every model call recorded with tokens, searches, latency and estimated dollars; a per-run budget stops new research. Work that finishes companies already researched (the skeptic's checks, a Shortlisted company's opening line, a requested email) may use a small reserve past it: $0.15, never more than a third of the budget |
| Storage | `runs`, `records` and related tables | New `agent_runs` table (id, created_at, status, payload JSON, events JSON) in the same local database |
| Interface | Classic workspace, landing page and demo | New start page with one field, a replay of a real search and a snapshot of a real result; a live board with a pinned monitor, an activity rail, "What we assumed", verdict columns, quote popovers with text-fragment links and a cost footer; a "Your shortlist" page for this browser's Shortlisted companies; a video mode (`?video=1`) that shows every company except the recording seller under an invented `.example` name, with a "company names changed" tag |
| Command line and evaluation | `shortlist run`, `export` and earlier evaluation scripts | `shortlist agent run` and `shortlist agent eval` with agreement, shortlist precision, disqualifier recall, cost per company, p50/p95 latency and a no-skeptic ablation |
| Public access | Hosted accounts with signup credits | A separate public demo app (`shortlist/agent/public.py`) that needs only a website: capped companies per search, an hourly limit per visitor, a cap on searches working at once, a daily dollar cap and optional Turnstile. Shareable read-only links; only the starting browser can correct a search. Runs are JSON files (`shortlist/agent/files.py`). Live at https://gtmshortlist--gtm-shortlist-agent-web.us-east.modal.run (`deploy/modal_agent.py`: one always-on container, searches saved on a Modal Volume so shared links last). Three real finished searches ship as read-only examples, one per seller (vanta.com, crisp.chat, eygentic.com), and finished boards have link previews |
| Tests | 838 backend tests and the existing browser journeys | 146 new backend tests in `tests/agent/` (1,038 in the repo) and 7 browser journeys in `tests/ui/agent.spec.ts` and `tests/ui/agent-public.spec.ts`, each on laptop and phone |

Reused from before the event, unchanged in behaviour: the safe page fetcher in `shortlist/fetch.py` (HTTPS only, public addresses only, pinned TLS, same-site redirects), the quote matching in `relevance.quoted_in` and `relevance.verbatim_quote`, the page-type gates `relevance.company_page_issue` and `relevance.candidate_issue`, `selection.discussion_page`, and the existing design tokens.

## Which Meta model does what

- **Muse Spark 1.3 on the Meta Model API** (`https://api.meta.ai/v1`, Responses endpoint, model from `META_MODEL`, default `muse-spark-1.3`) is the investigator. It reads the seller's pages, searches for competitors and companies with the built-in `web_search` tool, and runs the per-company loop, calling our `fetch_page` function tool. Raw search results are requested with `include: ["web_search_call.results"]`.
- **Muse Spark Open on Baseten** (`meta-models/muse-spark-open-1026`, OpenAI-compatible Chat Completions) is the skeptic. It never sees the web or the company name. For each quote it answers `supports`, `contradicts` or `insufficient`, with a reason, under two written rules: the company's own site can support fit only, never need, and a disqualifier must show current use, not an integration, a comparison or past use. Its JSON is validated strictly with one repair attempt.
- **No model decides a verdict.** `src/shortlist/agent/verdict.py` does, from the skeptic's decisions. The own-site rule is also enforced in code after the skeptic answers.

Every claim shown carries an exact quote found verbatim in a page the agent fetched, with its URL, source type and dates. A claim whose quote is not on the page is dropped and listed in the run's `dropped` log. A model's publication date is kept only when the page states it. The agent qualifies companies only: there are no person, name or role fields anywhere in its data, and it never records, scores or judges people.

## Run it

Install from source as in the [README](README.md). Then:

**Synthetic demo, no keys and no network.** The labelled synthetic world in `src/shortlist/agent/synthetic.py` uses invented companies on reserved `.example` domains and scripted model answers.

```sh
shortlist agent run https://seller.example/ --synthetic --output run.json
shortlist agent eval tests/agent/fixtures/labels.synthetic.csv --run run.json
shortlist agent eval tests/agent/fixtures/labels.synthetic.csv --run run.json --no-skeptic
```

The run gives one Shortlisted company, one Needs a look and one Rejected for using the direct competitor, with the quote "Customer support powered by RivalDesk". The ablation shows the skeptic's job: without it, a company that only integrates with the competitor is wrongly rejected (agreement drops from 100% to 67%).

**Live run.** Put the keys in `.env` (see `.env.example`): `META_MODEL_API_KEY`, `BASETEN_API_KEY`, and optionally `AGENT_RUN_BUDGET_USD` (default 1.00).

```sh
shortlist agent run https://yourcompany.com --companies 3 --output run.json
shortlist agent eval labels.csv --website https://yourcompany.com --output report.json
```

`labels.csv` has the columns `domain, expected_verdict (shortlisted|needs_look|rejected), reason, competitor_used`. With `--website`, eval researches exactly the labelled domains; with `--run`, it scores a saved run without any model call.

**Browser.** `shortlist serve --port 8014 --open`. The start page is now the website-only agent. Saved classic runs still open from their links (`?run=...`), and `/?classic=1` opens the classic workspace.

**Public demo.** See [docs/agent-public-demo.md](docs/agent-public-demo.md) for the limits, a local trial with synthetic data, and deploying on Modal.

**API (local mode).** `POST /api/agent/runs` with `{"website": "...", "overrides": {...}}`, or `{"description": {"offer": "...", "buyer": "...", "markets": "...", "name": "..."}}` for a seller without a website, returns the run id; `GET /api/agent/runs/{id}`; `GET /api/agent/runs/{id}/events` streams progress as Server-Sent Events; `POST /api/agent/runs/{id}/overrides` applies optional corrections. Corrections re-run only the skeptic and the verdict on saved evidence; adding a new fit check is the one change that researches the companies again.

## Wiring edits outside the new folders

This is the complete list.

- `src/shortlist/api.py`: five lines that register the agent routes, in local mode only.
- `src/shortlist/cli.py`: hands `shortlist agent ...` to `shortlist/agent/cli.py`, plus its help entry.
- `src/shortlist/fetch.py`: `fetch_page` is split into `fetch_html` (unchanged) and a new `page_from_html`, so the agent keeps the raw page for its code scan without a second request. `fetch_page` behaves exactly as before and every check stays in `fetch_html`.
- `.env.example`: the agent's settings and the public demo's. They are read in `src/shortlist/agent/settings.py` and `src/shortlist/agent/public.py`, so `config.py` is unchanged.
- `web/main.tsx`: start-page routing. The agent is the default start; `?run=`, `?classic=1` and sign-in links keep the classic workspace, and hosted installations fall back to it. A page marked `agent-only` (the public demo) always shows the agent.
- `playwright.config.ts`: a second test web server on port 8017 for the public demo spec.
- `render.yaml`: a third web service, `gtm-shortlist-agent`, for the public demo on the same image.
- `src/shortlist/container_entrypoint.py`: an `agent` choice that starts the public demo. The `api`, `worker` and `migrate` choices are unchanged.
- `tests/test_render_startup.py`: test ids now use the service name, plus the expected command for the demo service.
- `scripts/export_schema.py`: also exports the agent's JSON schemas.
- `scripts/ui_test_server.py`: the browser test server gives the agent the labelled synthetic providers and keeps the classic start for the existing journeys (the agent spec opens `/?flow=agent`).
- `web/generated/`: regenerated `openapi.json` and `api.d.ts`, plus new `AgentRunView.json`, `AgentRunSummary.json` and `AgentStarted.json`. `SiteIconInfo.json` gains the `placeholder` field below; other existing schemas are unchanged in content.
- `src/shortlist/relevance.py`: a `STAFFING` pattern, so a recruiting or staffing firm's job posts (written for its clients) never count as its own need.
- `src/shortlist/site_icons.py`, the two icon routes in `src/shortlist/api.py`, `web/SiteIcon.tsx` and `web/api.ts`: company icons. A PNG or ICO icon is preferred over an SVG (many turn white in dark mode), a site builder's blank stand-in icon is reported as none so the letter shows, a failed lookup is retried after a minute, and a label that is not a domain is never looked up. Tests in `tests/test_site_icons.py` and `tests/test_sample.py`.
- `web/CompanySearch.tsx`, `web/company-suggestions.ts`, `tests/ui/company-search.spec.ts`: a Brandfetch lettermark counts as no logo, so the icon the website declares shows instead.
- `web/landing/Reveal.tsx`: the word-by-word headline reveal, moved out of `web/landing/PublicLanding.tsx` so the agent's start page can use it too.
- `index.html`, `public/brand/`: the new logo and browser icons.
- `pyproject.toml`: the package includes the shipped example searches (`agent/showcase/`).
- `docs/PROGRESS.md`: dated entries for this work.

One deliberate design departure: DESIGN.md asks not to compress research sheets into three columns. The board uses compact cards in three verdict columns on wide screens, as the hackathon brief asks, stacks them on phones, and keeps the full quotes one click away.

## Limits

- **Live runs so far are spot checks, not an evaluation.** Live runs from 30 October to 2 November for vanta.com, crisp.chat, eygentic.com, usepylon.com and a seller without a website gave Shortlisted companies with dated need quotes, Rejected companies with the quote that ruled them out, and problems we then fixed (each one is in `docs/PROGRESS.md`). Two we found on 2 November: a run that reached its budget lost its opening lines (now kept within a small reserve), and a search without a website Shortlisted a clinic for listing a phone number (need signals must now set likely buyers apart). Tests use synthetic providers and recorded-shape HTTP fakes only.
- Built-in web search runs on the provider's side, so the agent cannot stop a single response from making more searches than asked. It removes the search tool once a company has used four.
- Agent runs are stored in local SQLite, or as JSON files in the public demo. The classic hosted app (accounts and Postgres) does not register the agent routes; the public demo is the hosted way to use the agent.
- The public demo runs on one always-on Modal container with searches on a Modal Volume. Its dollar limits use the agent's own estimates, so provider-side spend limits are still needed.
- The synthetic evaluation proves the plumbing and the rules, not real-world accuracy. A labelled set of real companies is the next step.
