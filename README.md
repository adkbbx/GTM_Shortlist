# GTM Shortlist

Open-source company discovery and research for B2B sellers. Confirm your offer and targeting criteria, discover candidates, inspect dated source passages, and review/export a shortlist. Human acceptance never means buying intent.

Created by Eygentic. Every seller uses the same workflow; Eygentic profiles are optional examples and test inputs, not product defaults.

This is an early local implementation. Hosted accounts, external signup, deployment, real provider benchmarks and observed user testing remain release gates in [the checklist](docs/IMPLEMENTATION.md). [Progress](docs/PROGRESS.md) records what has actually passed.

## Try it with sample data

No provider keys are needed. Install from source below, open the local app, and choose **Try it with sample data** on the setup card. Confirm the sample target, inspect the three invented companies and their evidence, accept or reject a result, and export CSV, JSON or Excel. Every screen and export labels the sample data. Sample source links are plain text because the invented pages do not exist online.

## Install from source today

Install Git, Python 3.11 or newer, and Node.js 22.12 or newer with npm. Run these commands in a terminal:

```sh
git clone --branch claude/signal-landing https://github.com/adkbbx/GTM_Shortlist.git
cd GTM_Shortlist
```

Windows PowerShell:

```powershell
py -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.lock.txt
.venv/Scripts/python.exe -m pip install -e . --no-deps
npm ci
npm run build
.venv/Scripts/python.exe -m shortlist.cli serve --port 8014 --open
```

macOS or Linux:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.lock.txt
.venv/bin/python -m pip install -e . --no-deps
npm ci
npm run build
.venv/bin/python -m shortlist.cli serve --port 8014 --open
```

Keep the terminal open. The app opens at http://127.0.0.1:8014 and starts its API and research worker together. If the browser does not open, visit that address manually. Stop with Ctrl+C. Source installs save research in `data/shortlist.sqlite3` inside the checkout. No environment activation or `.env` file is needed for the sample path. On Linux, your distribution may require its Python venv package before creating the environment.

The install commands download dependencies. They do not make research-provider requests. The source path includes the UI build; installing only the editable Python package does not build the UI.

## Install a published package

The PyPI release is still a release gate. Use the source instructions above today. After the maintainer publishes `gtm-shortlist`, Python 3.11 or newer plus [uv](https://docs.astral.sh/uv/getting-started/installation/) can run it without Node or a UI build:

```sh
uvx gtm-shortlist
```

Alternatively, with [pipx](https://pipx.pypa.io/stable/installation/) installed:

```sh
pipx run gtm-shortlist
```

The package starts the API and worker, opens http://127.0.0.1:8014, and stores research in your user data folder: `%LOCALAPPDATA%\GTM Shortlist` on Windows, `~/Library/Application Support/GTM Shortlist` on macOS, or `~/.local/share/gtm-shortlist` on Linux. Use `--port` to change the port or `--no-browser` to skip the tab. The package workflow builds and smoke-tests the bundled UI before publishing. See [release steps](docs/planning/LOW_FRICTION_PATHS.md).

## Connect your own providers

Real research needs **both a search provider and a research model**. A hosted model key alone does not enable company search.

1. In **Settings → Company search**, enter your own [Tavily key](https://app.tavily.com/). Saving does not test the key or run a search. For SerpApi instead, copy the search settings from [.env.example](.env.example) into a local `.env`: set `SHORTLIST_SEARCH_PROVIDER=serpapi` and `SERPAPI_API_KEY`, then restart the app. The search-key form supports Tavily only. A Tavily key already saved in Settings takes precedence over `.env`; to switch to SerpApi without changing that workspace, set `SHORTLIST_DB=data/serpapi-shortlist.sqlite3` in `.env` as well. Existing research remains in the original database.
2. In **Settings → Research model**, choose **On this computer** or **Hosted provider**. For Ollama, install it, download a Gemma model that fits your hardware, and keep its server running. Select Ollama in the app. For a hosted provider, enter its key and review its pricing. **Find available models** reads the server's catalog only. Choose the exact model ID, or enter it manually, then save. Availability does not prove structured-output support or research quality. See [model connection details](docs/local-provider-setup.md#guided-model-connection).
3. Return to the start page and enter your company website. Review and edit the drafted offer, target and observable fit checks before confirming discovery. A company-name lookup or website profiling can already use search, page reads and model calls before confirmation. If setup fails, reopen Settings to correct the key, server address or model ID. Paused runs offer **Resume research**; starting a new run can incur new costs.

Keys saved through Settings stay in the local private provider database, beside the research database with `.providers` appended to its filename. Windows uses current-user encryption; macOS and Linux use owner-only file permissions. Saved keys are never loaded back into the form or included in exports. Saving makes no provider request. Model catalog lookup requires your explicit click.

## Review evidence and limits

Open a company row to see criterion-level assessments, exact saved passages, source-page links and retrieval dates. For new real research, **Fits** requires every required check to be supported and independently model-verified, with exclusions ruled out; **Needs verification** preserves missing or uncertain checks. The citation gate checks the passage against the saved company page. Semantic entailment remains a model judgment, not independent real-world confirmation. Your accept or reject decision is separate and never establishes buying intent.

New qualification policies from 18 October use the search result's found page within the existing page cap, prevent a hedged claim from establishing an unhedged check, and allow one bounded verification follow-up for omitted judgments. Unsupported quotes remain diagnostics instead of customer evidence. Excerpt-gap recovery keeps a verbatim fragment from a saved page; that fragment still needs independent verification. In the saved comparison, the quotes run established 4 of 6 required checks across three records, compared with 2 of 4 in the first run. The subsets differ; this is not a controlled accuracy benchmark. The later menus run still left one required check unknown. See [the measured results and limits](docs/PROGRESS.md).

Export the full shortlist or accepted results in CSV, JSON or Excel. Excel includes a Shortlist sheet and an Evidence sheet with passages, source links, dates and open questions. JSON keeps the complete technical record. See [customer exports](docs/customer-export.md).

Real runs can return fewer than three usable companies. Search and model providers may charge for failed requests as well as successful ones. Runs share bounded attempts, including repairs: at most four searches and eight model calls, with at most three saved pages per company. The default monthly search cap is 200 attempts in this database. It does not track your provider account's allowance across other databases or services. Check your account's quota and pricing before research. Local model inference uses your own hardware; model licences are separate from this repository's MIT licence.

Local research, reviews, source snapshots and diagnostic model output stay in the configured SQLite database. Backups and exports can contain business research. Real research sends queries to your search provider, page requests to source sites, and supplied page excerpts and targeting criteria to the selected model server. A hosted model receives those inputs outside your computer. Optional Brandfetch sends typed company searches and domain requests from the browser when configured. Sample data makes no provider requests. The local app trusts one operator on loopback; do not expose it publicly.

## Contributor checks

See [CONTRIBUTING.md](CONTRIBUTING.md) for the backend, Ruff and browser checks. [Checks](https://github.com/adkbbx/GTM_Shortlist/actions/workflows/checks.yml) and [Package](https://github.com/adkbbx/GTM_Shortlist/actions/workflows/package.yml) show actual CI results. A workflow link is not a claim that the current revision passed. Report vulnerabilities through [SECURITY.md](SECURITY.md). The open-source core uses the [MIT licence](LICENSE); hosted operations and provider licences are separate.

## Guided local UI

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
