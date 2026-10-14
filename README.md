# GTM Shortlist

Open-source company discovery and research for B2B sellers. Confirm your offer and targeting criteria, discover candidates, inspect dated source passages, and review/export a shortlist. Human acceptance never means buying intent.

Created by Eygentic. Every seller uses the same workflow; Eygentic profiles are optional examples and test inputs, not product defaults.

This is an early local implementation. Hosted accounts, external signup, deployment, real provider benchmarks and observed user testing remain release gates in [the checklist](docs/IMPLEMENTATION.md). [Progress](docs/PROGRESS.md) records what has actually passed.

## Local setup

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
shortlist serve --port 8014
```

Open `http://127.0.0.1:8014`. This command starts and supervises the API and durable worker together. If either exits, both stop; restarting preserves saved jobs and uncertain-dispatch protection. The API serves the built UI. `npm run dev` starts the frontend dev server on port 5174 with an API proxy. Use the project virtual environment for Python commands.

`npx playwright install chromium` then `npm run test:ui` exercises the production build at 1366px laptop and 390px phone, plus 320px and 200% text sizing. It uses the actual API, worker, SQLite, review and download code with explicitly labelled synthetic providers. The test server is not a real discovery service. Screenshots are saved under `.impeccable/review/`. Generated TypeScript and runtime JSON validation schemas come from the Python API contracts.

The research view shows persisted, timestamped checkpoints, actual saved page/company counts, source reuse, repairs and failures. Worker availability is heartbeat-based; an offline worker produces a clear waiting state. Requests poll serially, so slow responses cannot overwrite newer progress. No fabricated percentage or ETA is shown. Completed activity remains in the saved history. Older runs without events are labelled accordingly.

Enter a company name, bare domain or full HTTPS URL. All company names use the same bounded website lookup; confirm a suggested website or enter one manually before offer drafting. Bare domains and HTTPS URLs go directly to website profiling. Matches are suggestions and can refer to another company. Offer and target confirmation still precede prospect discovery. See [company input](docs/company-name-input.md).

## Boundaries

The local SQLite app is for one trusted operator and must bind to loopback. Do not expose it publicly. Hosted mode has verified-user API boundaries, Postgres workspace isolation, account UI and research-credit accounting (three signup credits; batches of 1–3). Real Supabase accounts, external SMTP, paid checkout and actual deployment tests remain required before hosted release.

The [Postgres setup](docs/postgres.md) documents tested migrations, runtime roles, verified-user API access and hosted worker configuration. Signup/login and recovery are implemented with the Supabase browser SDK; real accounts, email and deployment validation remain unfinished.

No automated outreach, personal contact database, CRM integration or Experiment Judge. Proposed managed-service pricing is an unvalidated $99 reviewed pilot, with a $49 subscription considered only after repeat demand.

See [architecture](docs/planning/architecture.md), [design](DESIGN.md), and [implementation handoff](docs/planning/IMPLEMENTATION_HANDOFF.md).

On Windows, the local supervisor owns its API/worker descendants through a native job object; exiting or losing either child stops the service and releases its port. Restart with the same `shortlist serve` command. The dedicated Windows lifecycle checks reproduce and prevent orphaned launcher/runtime processes.

In the local workspace, open **Connect Tavily** to paste a masked API key. Saving performs no search; the next confirmed run uses the saved key without a worker restart. The private provider database is ignored by Git, protected with current-user DPAPI on Windows and owner-only permissions on POSIX. The UI never retrieves the saved key. See [local provider setup](docs/local-provider-setup.md). This loopback address belongs to the computer running the app; a phone needs a properly configured hosted service rather than a publicly exposed local workspace.

**Stop this run** preserves completed research and reviews, returns unused credit holds and prevents the previous worker from saving another sheet. A remote request already underway may finish. Review/export remain free; completed usable company research remains charged. See [research stop](docs/research-stop.md) and [credits](docs/credits.md). Hosted credit activity has owner-scoped earlier/newer pages. Independent service-review notes appear separately from the customer's decision.
