# GTM Shortlist

Eygentic's open-source company discovery and research core. Confirm a seller's offer and targeting criteria, discover candidates, inspect dated source passages, and review/export a shortlist. Human acceptance never means buying intent.

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
```

The example profile is user-supplied planning input, not a fetched seller assessment. Correct it before using it for other offers. Commands with the same request key return the original run; changed input under that key is rejected.

Run `pytest -q` and `ruff check --isolated src tests scripts`. Tests use labelled synthetic sources unless explicitly described as live. TLS verification and public-address validation stay enabled; unsafe or unavailable pages produce explicit partial results. The citation gate verifies exact passages and company source identity. Semantic entailment is still a model assessment requiring evaluation and human review.

## Boundaries

The local SQLite app is for one trusted operator and must bind to loopback. Do not expose it publicly. Postgres workspace isolation, verified signup, shared demo grants, external SMTP and actual deployment tests are required before hosted release.

No automated outreach, personal contact database, CRM integration or Experiment Judge. Proposed managed-service pricing is an unvalidated $99 reviewed pilot, with a $49 subscription considered only after repeat demand.

See [architecture](docs/planning/architecture.md), [design](DESIGN.md), and [implementation handoff](docs/planning/IMPLEMENTATION_HANDOFF.md).
