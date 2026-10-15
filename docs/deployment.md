# Hosted image and deployment preparation

Status: the image and disposable container smoke are verified in GitHub Checks for c68e7d1 (run38520391013). Real image build, migrations/replay, restricted schema access, private Postgres, non-root API/worker, built assets, unauthorized401 and restart checks passed. Compose syntax passed; public Caddy TLS and live hosting are still unverified. Local Docker is unavailable. No real Supabase/email/provider/payment test is claimed.

## Image

Build from a reviewed commit:

```sh
docker build -t gtm-shortlist:COMMIT .
```

Node22 and Python3.12 base images are pinned by registry digests verified14October2026. The build uses npm's lock and a Python runtime subset of requirements.lock.txt; when changing pins, update that subset too. Runtime excludes Node, test/lint packages, fixtures, local data and secrets. An allowlist dockerignore prevents unrelated workspace files entering the context. The application runs as UID10001. The built UI is served by the API from the same image; Supabase public configuration comes from the server, not build-time frontend secrets.

The image entry point accepts api, worker or migrate. API/worker require hosted mode; it refuses a publicly bound local SQLite service. API and worker are separate processes/containers. The image includes the checksummed migration script but never applies migrations during API/worker startup.

## Database and secrets

Provision a persistent PostgreSQL database, then use a dedicated operator credential to apply migrations and create restricted API/worker login roles as described in postgres.md. Runtime logins must not be superusers or bypass row security. Keep the shortlist schema outside exposed PostgREST schemas. Use TLS for external database connections.

Run migrations before services using a temporary server-only environment file containing SHORTLIST_MIGRATION_DATABASE_URL:

Email drafting requires migration `010_email_drafts.sql` before deploying the updated API/worker. It adds a nullable artifact column to records; existing research JSON and old services remain compatible. The hosted production database has not been migrated as part of the offline draft implementation. Keep the operator credential out of runtime services.

```sh
docker run --rm --env-file deploy/secrets/migrate.env gtm-shortlist:COMMIT migrate
```

Repeat is safe; changed applied migration files are rejected. Keep the operator file away from the API/worker and remove it from their deployment environment. Do not print credential files or resolved Compose configurations.

Create deploy/secrets/api.env and worker.env from their adjacent .example files and fill real values on the deployment host. That directory is ignored by Git and excluded from the image. API receives only its restricted API database login and public Supabase/app configuration. Worker receives its own login, public configuration and research-provider secrets. Because settings are shared, set SHORTLIST_DATABASE_URL to the worker login also in the worker file; it never needs the API login. These are runtime environment files, not secret storage guarantees; protect host permissions and use the hosting platform's secret manager where available. No keys are built into the image.

## HTTPS edge

Set SHORTLIST_IMAGE to the reviewed image tag and SHORTLIST_HOST to the public hostname. The app origin in both service files must be https:// plus that same hostname. Point DNS and configure Supabase Site URL/allowed redirects and external SMTP before exposing the flow.

```sh
docker compose -f deploy/compose.yaml config --quiet
docker compose -f deploy/compose.yaml up -d
```

Only the Caddy edge publishes80/443. API and worker have no published ports; the database is external and must not gain a public development port. Caddy's certificate/configuration volumes persist across recreation. API/worker run with read-only filesystems, temporary /tmp, dropped capabilities and no-new-privileges. Configure server firewall, outbound provider access, encrypted backups and retention before release. This configuration does not provision a VPS, database, DNS, email or billing account.

API image health is process liveness at /api/health using the configured Host header. Worker health checks a recent shared durable heartbeat and database access; it is not a per-instance completion guarantee. Compose starts API after a healthy worker and edge after a healthy API. Provider-key readiness is configuration only, not proof the credentials work. Public hosted health deliberately does not expose actual worker availability; authenticated research progress does.

## Evidence and rollout

GitHub Checks builds the actual image after core/database/browser/Windows checks pass. scripts/container_smoke.py validates Compose syntax, starts uniquely named isolated containers/network, migrates twice, creates restricted fixture logins, runs actual API and worker, checks non-root runtime, private database, correct schema access, built assets and unauthorized401, then restarts both. It removes only resources it created. All credentials and Supabase origins are labelled fixtures; no external providers or real accounts are contacted.

Before launch, prove real Supabase signup/confirmation/recovery and two-account isolation, external SMTP and phone/laptop email flow; a real provider-backed saved discovery; payment test-mode accounting if selling credits; account closure/backup deletion replay; public HTTPS health and persistent data across restart; and observed external users across the intended seller types. Keep prior image/database backups for rollback. Take a database backup before new migrations; test restore and replay rather than assuming a reverse migration is safe.
