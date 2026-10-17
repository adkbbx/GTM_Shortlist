# GTM Shortlist

Open-source company discovery and research for B2B sellers. Confirm your offer and targeting criteria, discover candidates, inspect dated source passages, and review/export a shortlist. Human acceptance never means buying intent.

Created by Eygentic. Every seller uses the same workflow; Eygentic profiles are optional examples and test inputs, not product defaults.

This is an early local implementation. Hosted accounts, external signup, deployment, real provider benchmarks and observed user testing remain release gates in [the checklist](docs/IMPLEMENTATION.md). [Progress](docs/PROGRESS.md) records what has actually passed.

## Run it on your computer

Once a release is published to PyPI, one command installs and opens the app (Python 3.11 or newer; no Node or build step):

```sh
uvx gtm-shortlist        # or: pipx run gtm-shortlist
```

It starts the API and research worker, opens `http://127.0.0.1:8014`, and keeps research in your user data folder (`%LOCALAPPDATA%\GTM Shortlist` on Windows, `~/Library/Application Support/GTM Shortlist` on macOS, `~/.local/share/gtm-shortlist` on Linux). Use `--port` to change the port or `--no-browser` to skip the tab. The start page then walks through model and search setup, or lets you try the whole flow on sample data first.

**Releasing.** `.github/workflows/package.yml` builds the package with the UI inside and runs it from a fresh install on every push. Pushing a `v*` tag publishes it once PyPI trusted publishing is set up for this repository: project `gtm-shortlist`, workflow `package.yml`, environment `pypi`. To build by hand: `npm ci && npm run build`, `python scripts/package_ui.py`, `python -m build --outdir package-dist`, then `python scripts/package_smoke.py package-dist/*.whl`.

## Local setup for contributors

Python 3.11 or newer:

```sh
python -m venv .venv
# Windows: .venv/Scripts/python.exe; macOS/Linux: .venv/bin/python
python -m pip install -r requirements.lock.txt
python -m pip install -e . --no-deps
cp .env.example .env
shortlist config
```

Run commands inside the activated virtual environment. Configure your own Tavily/SerpApi credentials and a trusted OpenAI-compatible Gemma endpoint in `.env`. Secrets stay on the server. Settings readiness reports booleans, never keys. Search requests use basic depth with at most four attempts per run and the configured global monthly cap, including uncertain outcomes. Gemma uses at most eight attempts. The model's licence is separate from this repository's MIT licence.

```sh
shortlist run examples/eygentic-profile.json --request-key eygentic-first
shortlist worker
shortlist show RUN_ID
shortlist export RUN_ID --format json
shortlist export RUN_ID --format csv --accepted-only
shortlist export RUN_ID --format xlsx --output shortlist.xlsx
```

The example profile is user-supplied planning input, not a fetched seller assessment. Correct it before using it for other offers. Commands with the same request key return the original run; changed input under that key is rejected.

Excel exports have a readable Shortlist sheet and an Evidence sheet with exact passages, open questions, source links and dates. CSV now uses readable columns instead of nested JSON cells; use JSON for the complete technical record and unchanged integration contract. See [customer exports](docs/customer-export.md).

Run `pytest -q` and `ruff check --config pyproject.toml src tests scripts`. Tests use labelled synthetic sources unless explicitly described as live. TLS verification and public-address validation stay enabled; unsafe or unavailable pages produce explicit partial results. The citation gate verifies exact passages and company source identity. Semantic entailment is still a model assessment requiring evaluation and human review.

## Guided local UI

```sh
npm ci
python scripts/export_schema.py
npm run schema
npm run build
shortlist serve --port 8014 --open
```

Open `http://127.0.0.1:8014`. Until a model and search key are set up, the start page shows a two-step setup card. **Try it with sample data** on that card runs the whole flow (offer, market, target, discovery, evidence, review and export) on invented companies from `src/shortlist/sample.py`, with no keys, searches or page fetches. Sample runs are labelled on every screen and in every export, and cannot be reused for real research.

This command starts and supervises the API and durable worker together. If either exits, both stop; restarting preserves saved jobs and uncertain-dispatch protection. The API serves the built UI. `npm run dev` starts the frontend dev server on port 5174 with an API proxy. Use the project virtual environment for Python commands.

`npx playwright install chromium` then `npm run test:ui` exercises the production build at 1366px laptop and 390px phone, plus 320px and 200% text sizing. It uses the actual API, worker, SQLite, review and download code with explicitly labelled synthetic providers. The test server is not a real discovery service. Screenshots are saved under `.impeccable/review/`. Generated TypeScript and runtime JSON validation schemas come from the Python API contracts.

The research view shows persisted, timestamped checkpoints, actual saved page/company counts, source reuse, repairs and failures. Worker availability is heartbeat-based; an offline worker produces a clear waiting state. Requests poll serially, so slow responses cannot overwrite newer progress. No fabricated percentage or ETA is shown. Completed activity remains in the saved history. Older runs without events are labelled accordingly.

Enter a company name, bare domain or full HTTPS URL. All company names use the same bounded website lookup; confirm a suggested website or enter one manually before offer drafting. Bare domains and HTTPS URLs go directly to website profiling. Matches are suggestions and can refer to another company. Offer and target confirmation still precede prospect discovery. See [company input](docs/company-name-input.md).

### Enable optional company autocomplete

Local users can configure a [Brandfetch public client ID](https://developers.brandfetch.com/register) in **Settings → Brandfetch**. Click **Not configured** or **Configured**, paste the public ID and save. It takes effect immediately without editing files, rebuilding or restarting the app. This preference stays in this browser for the local workspace. **Turn off Brandfetch** disables suggestions and its icon fallback, including an installation default. Other browsers need their own preference or the installation setting below. Manual company-name and website entry always remain available.

Installation operators can set `SHORTLIST_BRANDFETCH_CLIENT_ID=your_public_client_id` in the web server's environment. The server places this public value in the page at runtime; no frontend rebuild is needed. It applies after a normal server restart. Hosted users share this installation setting and do not configure individual IDs. For Render instructions, see [optional Brandfetch configuration](docs/render.md#optional-brandfetch-configuration).

The older `VITE_BRANDFETCH_CLIENT_ID` build setting remains available for frontend-only development. Runtime configuration takes precedence, followed by the build setting. A local browser preference overrides both. Use a public client ID, never a secret API key. The repository ships no shared developer ID.

Autocomplete calls the [Brand Search API](https://docs.brandfetch.com/brand-search-api/overview) directly from the browser after a short typing delay. Saved-run and result icons read the site's declared favicon from its homepage, then try `/favicon.ico` and the configured [Logo API](https://docs.brandfetch.com/logo-api/overview). Relative favicon paths and public HTTPS CDN icons are supported. Homepage lookups are bounded, cached and restricted to sites in an accessible saved run. No research provider is used to read these declarations. Brandfetch receives the domain and browser origin for logo requests, without the page's run/query URL. Missing icons retain initials inside the same rounded container. Directory and logo APIs have free allowances and rate limits separate from paid enrichment. Review current guidelines and monitor usage in the Brandfetch dashboard. Suggestions are transient UI metadata, not research evidence. Saving the ID or selecting a suggestion starts no research and calls no Tavily, SerpApi or inference provider. The design-only preview on port8018 disables Brandfetch search and logo fallback.

New browser runs also collect up to 15 potential competitor websites and propose up to six editable campaign hypotheses. Search observations do not establish competitor similarity. Confirm your offer, observable criteria, search keywords and selected campaign before discovery starts. CLI and older saved runs retain their original flow.

Selection reads a bounded pool of six company primary pages and, when observed, one same-company activity page each. Dated first-party statements can affect which companies receive the three research slots. Missing dates remain unknown; an announcement does not establish buying intent. The [agent experience checklist](docs/agent-experience.md) describes current coverage and unfinished quality checks.

Compare compact company rows, then open one research sheet to inspect saved passages, sourced company facts and named current team-role observations. Unknown facts and employment remain explicit. Switching sheets preserves unsaved notes and draft edits. You can create and edit a starting email template using the confirmed offer and saved evidence, then export drafts in Excel or JSON. Drafting makes no inference request and sends no email. Indexed professional-profile discovery and business-email enrichment remain unfinished.

## Boundaries

The local SQLite app is for one trusted operator and must bind to loopback. Do not expose it publicly. Hosted mode has verified-user API boundaries, Postgres workspace isolation, account UI and research-credit accounting (three signup credits; batches of 1–3). Optional switches shorten the hosted path: [email-code and Google sign-in](docs/sign-in.md), and [drafts before signup](docs/anonymous-drafts.md), which spend one page read and one model call per visitor behind Turnstile and daily caps, and never search. Real Supabase accounts, external SMTP, paid checkout and actual deployment tests remain required before hosted release.

The [Postgres setup](docs/postgres.md) documents tested migrations, runtime roles, verified-user API access and hosted worker configuration. Signup/login and recovery are implemented with the Supabase browser SDK; real accounts, email and deployment validation remain unfinished.

For Render, use the reviewed [Blueprint and setup guide](docs/render.md). It defines a web service and a paid background worker; review costs before applying it. Private credentials are entered through Render, not committed to the repository.

No automated outreach, personal contact database, CRM integration or Experiment Judge. Proposed managed-service pricing is an unvalidated $99 reviewed pilot, with a $49 subscription considered only after repeat demand.

See [architecture](docs/planning/architecture.md), [design](DESIGN.md), and [implementation handoff](docs/planning/IMPLEMENTATION_HANDOFF.md).

On Windows, the local supervisor owns its API/worker descendants through a native job object; exiting or losing either child stops the service and releases its port. Restart with the same `shortlist serve` command. The dedicated Windows lifecycle checks reproduce and prevent orphaned launcher/runtime processes.

In the local workspace, open **Settings** and click the **Not configured** or **Configured** status beside **Company search** to enter a masked Tavily key. **Research model** guides you through a model on this computer or a hosted provider, with setup links, preset server addresses and an explicit **Find available models** action. Choose a returned model ID or use advanced custom/manual setup. Model lookup reads metadata only; saving performs no provider request. Neither starts research. The private provider database is ignored by Git, protected with current-user DPAPI on Windows and owner-only permissions on POSIX. Saved keys are never loaded into the UI. Starting research automatically starts local background processing after the run is saved. Paused local runs offer **Resume research**. See [local provider setup](docs/local-provider-setup.md). This loopback address belongs to the computer running the app; a phone needs a properly configured hosted service rather than a publicly exposed local workspace.

**Stop this run** preserves completed research and reviews, returns unused credit holds and prevents the previous worker from saving another sheet. A remote request already underway may finish. Review/export remain free; completed usable company research remains charged. See [research stop](docs/research-stop.md) and [credits](docs/credits.md). Hosted credit activity has owner-scoped earlier/newer pages. Independent service-review notes appear separately from the customer's decision.

## Landing-page example

The starting page offers equally prominent Play example and Research my website actions. The example demonstrates six stages with synthetic companies and passages, pauses for target confirmation and source inspection, and ends with a sample review and editable draft. It does not create a research run or call a provider. Reduce motion switches to a static result; the system motion preference is also respected.

For an isolated local UI preview, build the frontend and run `python scripts/landing_demo_preview.py` from the repository root with the project environment active. Open http://127.0.0.1:8018. This uses a temporary database with no providers or worker. Use the normal configured application server for real research. `node --experimental-strip-types scripts/check_landing_demo.mjs` checks playback transitions; browser regressions live in `tests/ui/landing-demo.spec.ts`.
