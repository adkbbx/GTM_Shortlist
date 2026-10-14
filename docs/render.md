# Render with Supabase

Preparation only: no Render resources have been created or paid services activated. Review compute charges in Render before applying the Blueprint. The API uses the free demo instance, which sleeps on idle; the worker uses paid 0.5c-512mb compute. Both use the repository's existing non-root Docker image. Upgrade the web instance for an always-on public service. Automatic deployments are off during setup; applying a Blueprint can still create and initially deploy services and start billing.

The root render.yaml uses JSON syntax, a YAML subset. Run npm ci and node scripts/validate_render_blueprint.mjs to check it against Render's published schema. Schema validation is not proof of live service/database/email behavior. The image entrypoint takes api or worker as its CMD argument. PORT is8000, matching the image; health is /api/health. No customer project, private key, database password, calendar or domain is committed.

## Startup URL configuration failure

If the Docker build succeeds but startup says Hosted auth and app URLs must be HTTPS origins, check SUPABASE_URL and SHORTLIST_APP_URL in that service's Environment page. Each must be a plain HTTPS origin, without Markdown brackets, a page path, credentials or a query string. The first is the Supabase project URL; the second is the actual public Render web-service URL, not the dashboard URL or localhost. Set both on API and worker. Save and deploy after correcting them. Current startup diagnostics name the exact offending environment variable without printing its value. This fixes this configuration gate only; it does not provision database roles/tables or prove email delivery.

## First: private database setup

The Supabase URL/publishable key identify the project but cannot create the app's database schema. In Supabase, open Connect and choose Session pooler if an IPv4 connection is needed; use its actual hostname/port instead of inventing a database hostname. The direct connection also works where IPv6 is reachable. Use a connection string with TLS (sslmode=require). The existing adapter opens normal sessions and uses session role setup; session pooling is the documented deployment choice here, rather than an unverified transaction pooler.

For the one-time operator migration, enter SHORTLIST_MIGRATION_DATABASE_URL in the ignored local deploy/secrets/migrate.env file, never chat, Git or the public app. The migration script reads the operator variable from its process environment; it does not automatically load this file. Use a private operator session to load it, run python scripts/migrate_postgres.py, and provision separate restricted API/worker logins as described in postgres.md. Generate/store their passwords privately. Do not run the web service with postgres/admin credentials: the adapter rejects superusers, bypass-RLS roles and API accounts with worker membership. Do not put the operator connection into Render's API or worker environments.

After migrations, scripts/provision_hosted.py can prepare the two restricted runtime logins and private Render environment files. It reads deploy/secrets/migrate.env plus deploy/secrets/supabase-public.env (SUPABASE_URL, SUPABASE_PUBLISHABLE_KEY, SHORTLIST_APP_URL). It checks project routing, enforces client TLS, creates separate non-superuser/no-bypass-RLS login roles and refuses an API login with worker membership. Generated passwords are retained in ignored runtime-logins.json before role creation, so replay does not rotate them after a partial run. Existing login roles without the original private state require operator review. It authenticates each runtime role through the actual Postgres adapter before atomically writing api.env and worker.env. The worker retains its privately configured Gemma settings and gets local search credentials; the API never receives those provider secrets. The script does not run a migration, create user accounts, trigger research, upload secrets or deploy Render resources.

Import the contents of deploy/secrets/api.env through Render web service → Environment → Add from .env, and worker.env through the worker's corresponding page. Do not import migrate.env or runtime-logins.json into either service. These files are local operator inputs; creating them does not configure Render automatically. Provisioning normally follows an operator-reviewed migration and should be run by one setup operator.

## Then: create the Render services

After database setup and review of costs, sign in to Render with GitHub, choose New → Blueprint and select this repository. Review both resources and enter the prompted environment variables. Applying the Blueprint is an external paid-resource action, not part of local preparation.

Both services receive SUPABASE_URL, SUPABASE_PUBLISHABLE_KEY and SHORTLIST_APP_URL. Set the app URL to the exact HTTPS onrender.com origin for the web service initially. The API receives its restricted login in SHORTLIST_DATABASE_URL. The worker receives only its worker login in both SHORTLIST_DATABASE_URL and SHORTLIST_WORKER_DATABASE_URL. Only the worker receives Tavily/Gemma secrets. Public configuration saved locally is not automatically copied to Render. No Supabase admin secret is needed for normal signup/research; managed account deletion has its own separate operator configuration.

The worker initially retains the configured Tavily provider. To benchmark or switch to SerpApi, add SERPAPI_API_KEY privately on the worker and set SHORTLIST_SEARCH_PROVIDER=serpapi. No automatic paid fallback or provider comparison is implied. Existing DigitalOcean Gemma endpoint/model/key can be copied through private environment settings; no GPU instance is created.

## Email, domain and release checks

In Supabase Auth, keep email confirmation enabled. Configure external SMTP for public signups: the default service is limited to project-team addresses. Set Site URL and allowed redirect URL to the app origin and trailing slash as described in postgres.md. A personal Gmail address can be an admin/test recipient; entering an address alone does not configure outbound mail.

Initially test on Render's assigned URL. After claiming a domain, add it in Render, configure DNS/TLS, and update SHORTLIST_APP_URL on both services and Supabase Site URL/redirects together. The API's allowed Host is that configured origin; Render health checks use a custom domain when verified, otherwise its assigned hostname. Avoid a mismatched origin during rollout.

Before public release, verify real signup/confirmation/recovery, two-account isolation, durable worker checkpoints, a real saved provider run, owner-scoped exports, restart persistence and phone/laptop email flows. A successful /auth/v1/settings response only proves that a project's public key is accepted; it does not prove table setup, restricted roles, email delivery or a deployed app. Payment and real customer validation gates remain separate.

References: [Render Blueprint spec](https://render.com/docs/blueprint-spec), [Render free limitations](https://render.com/docs/free), [Supabase database connections](https://supabase.com/docs/guides/database/connecting-to-postgres), [Supabase SMTP](https://supabase.com/docs/guides/auth/auth-smtp).
