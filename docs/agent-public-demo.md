# Public agent demo

A separate app for letting anyone try the website-only agent from a public link: `src/shortlist/agent/public.py`. It serves only the agent's start page and board, never the classic workspace, accounts or credits, and it shares nothing with the local or hosted GTM Shortlist apps.

## What it enforces

| Limit | Setting | Default |
|---|---|---|
| Companies per search | `AGENT_PUBLIC_MAX_COMPANIES` | 5 |
| Searches per visitor per hour (address hashed with the secret, never stored raw) | `AGENT_PUBLIC_RUNS_PER_HOUR` | 3 |
| Searches working at once | `AGENT_PUBLIC_MAX_ACTIVE` | 3 |
| Estimated dollars per day across all visitors, resets 00:00 UTC | `AGENT_PUBLIC_DAILY_USD` | 10 |
| Estimated dollars per search | `AGENT_RUN_BUDGET_USD` | 1.00 (0.50 suggested here) |
| Cloudflare Turnstile before a search starts | `AGENT_PUBLIC_TURNSTILE_SITE_KEY` + `AGENT_PUBLIC_TURNSTILE_SECRET` | off |

A new search is refused when the daily estimate plus a full budget for every working search would pass the daily cap. Estimates come from the agent's own telemetry (published token and search prices), not the providers' bills, so also set spend limits on the Meta billing page and in Baseten.

A search page is readable by anyone with its link; ids are random 128-bit hex. There is no list of searches. Only the browser that started a search holds its edit token (in that browser's local storage), so only it can correct the assumptions; everyone else sees a read-only shortlist. Requests from other origins and other host names are refused. A search left working by a restart is marked failed with a note to start again.

## Try it locally with synthetic data

No keys, no network, no spending. From the repository root after `npm run build`:

```powershell
$env:AGENT_PUBLIC_URL="http://127.0.0.1:8020"
$env:AGENT_PUBLIC_SECRET=(python -c "import secrets; print(secrets.token_hex(32))")
$env:AGENT_PUBLIC_SYNTHETIC="on"
.venv\Scripts\python.exe -m uvicorn --factory shortlist.agent.public:create_public_app --host 127.0.0.1 --port 8020
```

Open http://127.0.0.1:8020 and search for `seller.example`. Remove `AGENT_PUBLIC_SYNTHETIC` and put `META_MODEL_API_KEY` and `BASETEN_API_KEY` in `.env` to run live locally.

## Deploy on Render (for now)

The demo runs from the same Docker image as the `gtm-shortlist` web service, started with `python -m shortlist.container_entrypoint agent`. `render.yaml` defines it as `gtm-shortlist-agent`. Until this branch is merged, create it by hand so the existing Blueprint, which follows `main`, is not involved.

1. Render dashboard → **New → Web Service** → the GTM_Shortlist repository.
2. **Name** `gtm-shortlist-agent`, **Branch** `meta-hackathon`, **Language** Docker, **Dockerfile path** `./Dockerfile`, **Docker Command** `python -m shortlist.container_entrypoint agent`, **Instance** Free.
3. **Advanced:** Health Check Path `/api/health`. Auto-Deploy Off matches the other services.
4. **Environment → Add from .env:** paste the contents of the private, git-ignored `deploy/secrets/agent-demo.env`. It holds the Meta and Baseten keys, a generated `AGENT_PUBLIC_SECRET`, `AGENT_PUBLIC_URL=https://gtm-shortlist-agent.onrender.com` and the limits. Never commit it or paste it in chat.
5. **Create Web Service** and wait for the Docker build.
6. If Render assigns a different URL, set `AGENT_PUBLIC_URL` to that exact origin, then save and deploy. Until they match, every request is refused with "Invalid host header".
7. Open the URL and run one search for your own website (about $0.30). Check the cost in the board's footer, and set spend limits on the Meta billing page and in Baseten.

On the free instance, search pages are files in `/tmp`. A restart, a redeploy, or sleep after about 15 idle minutes loses them, so shared links do not last, and the first visit after sleep takes about a minute. For lasting links, use a paid instance with a persistent disk and set `AGENT_PUBLIC_DATA` to a folder on that disk (check it is writable by the image's non-root user), or move to Modal below.

## Deploy on Modal

1. Install the Modal CLI and sign in once: `pip install modal`, then `modal setup`.
2. Build the UI: `npm ci`, then `npm run build`.
3. Create the secret. The URL is `https://<your-modal-workspace>--gtm-shortlist-agent-web.modal.run`; if the first deploy prints a different one, recreate the secret with that URL and deploy again.

   ```powershell
   modal secret create gtm-shortlist-agent `
     META_MODEL_API_KEY=... BASETEN_API_KEY=... `
     AGENT_PUBLIC_URL=https://<your-modal-workspace>--gtm-shortlist-agent-web.modal.run `
     AGENT_PUBLIC_SECRET=<64 random hex characters> `
     AGENT_RUN_BUDGET_USD=0.50 AGENT_PUBLIC_DAILY_USD=10
   ```

   To change a value later, run the same command with `--force`, then deploy again.
4. Deploy: `modal deploy deploy/modal_agent.py`.
5. Check it: open the URL, confirm the page says "Public demo: up to 5 companies per search", run one search for your own website, and watch the cost in the board's footer.

The deployment keeps one small CPU container running (`min_containers=1`, `max_containers=1`), so the per-visitor limits and the working searches stay in one process. Searches are JSON files on the Modal Volume `gtm-shortlist-agent-runs`, committed every few seconds. To stop the demo, run `modal app stop gtm-shortlist-agent`.

## Checks

- `pytest tests/agent/test_public_demo.py`: limits, edit tokens, Turnstile, origin and host checks, run-id validation, the file store and restart recovery.
- `npx playwright test tests/ui/agent-public.spec.ts`: the public start page and a shared read-only link at 1366px and 390px, served by `scripts/public_demo_test_server.py` with synthetic providers.
- `deploy/modal_agent.py` has not been deployed from this repository yet. Its first deploy is the check.
