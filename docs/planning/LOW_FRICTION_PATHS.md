# Lowest-friction paths: hosted and local

17 October 2026. Request: the shortest possible path to value for a hosted visitor and for someone who wants to run GTM Shortlist on their own machine.

**Status, 18 October:** built on `claude/signal-landing`; see the checklist. Items marked *You* need a setting only the owner can make. Drafts before signup and the newer sign-in methods stay off until switched on.

Measure for both paths: **time to the first useful screen**. That is the visitor's own drafted offer, target and fit checks, plus the number of decisions and installs before it.

## Where things stand

| | Hosted | Local |
|---|---|---|
| Before value | Landing → sign up (email + password) → inbox → open link (often a new tab or device) → research starts → wait | Install Python 3.11 and Node → about 10 commands (venv, pip twice, `npm ci`, schema export, UI build, `shortlist serve`) → add search keys and a model endpoint → start |
| Decisions before value | Account, password | Search provider, model, where to run it |
| Already fixed today | One press: research starts after sign-in, with no second Start research (`3410754`). Review-first confirmation (`2cbad35`). | One press from `?landing=1` starts the run |

## Hosted: try first, sign up when it is worth it

```
Landing ─► Draft appears live ─► Review your target ─► Save + find companies ─► Results
type        reads your site and   the "you understood     sign up inline: Google    discovery runs;
company     drafts the offer,     my business" moment;    or a 6-digit email code   price shown
+ Start     target, fit checks    edit if needed          in the same tab           before confirm
            (about 30 s, no account)
```

**What runs before signup:** only the cheap step, one page fetch and one model call that draft the offer, target and fit checks.
- No web search. Company-name lookup, market exploration and discovery all use search, so they wait for an account and the 250-a-month SerpApi budget is untouched.
- A plain company name without a website therefore needs a Brandfetch suggestion (which carries the domain) or a typed website. "Pick your company from the list or enter its website" is the only prompt.

**Anonymous draft (new):**
- **Endpoint (built):**
  - `POST /api/drafts` takes `{ website, browser_id, turnstile_token }` and returns `{ id, claim_token }`.
  - `GET /api/drafts/{id}` takes the claim token in an `X-Draft-Claim` header and returns status, progress events and, when ready, the draft.
- **Storage:** a separate `anonymous_drafts` table holding the website, saved page snapshot, draft and events. It has no workspace and no credits, and expires after 24 hours.
- **Claiming (built):** after sign-in, `POST /api/drafts/{id}/claim` turns the draft into the account's run at the offer stage, with the saved page and draft, then deletes the anonymous copy in the same transaction. The worker explores the market (no second fetch or model call) and the run then waits for target confirmation.
- **Browser state:** the claim token stays in this browser only (local storage, 24 hours), next to the kept company that exists today.

**Abuse limits** (required before launch):
- **Bot check:** Cloudflare Turnstile on the anonymous Start, invisible in most cases.
- **Per-visitor cap:** one anonymous draft per browser and IP per day.
- **Global cap:** a daily ceiling on anonymous model calls, plus a kill switch (`SHORTLIST_ANONYMOUS_DRAFTS=off`).
- **Network:** the existing public-address and size limits on page fetches apply unchanged.

**Sign-in without leaving the page:**
- **Methods:** Supabase email OTP (a 6-digit code entered in the same panel) and Google sign-in. Password signup stays available for people who prefer it.
- **No inbox detour:** there is no confirmation link to open, so nobody switches tab or device and the draft is never orphaned.

**Price before commitment:**
- **On the landing page:** a line beside Start research reads "First 3 companies free · no card", using the existing three-credit allowance.
- **Before confirming:** the batch cost appears in the review card before Confirm, as it does today.

**Honesty rules** (unchanged):
- The draft is labelled as drafted from their site, and editable.
- Nothing is searched before signup.
- Fit is never described as buying intent.

## Local: one command, then two clicks

```
uvx gtm-shortlist ─► browser opens ─► Setup (2 steps) ─► Start research
(or docker run)      on the landing   model, search       same review-first flow
                     in local mode    or: Try with sample data
```

**Install with no Node and no build:**
- **Python package:** publish to PyPI with the built UI included (`dist/` inside the wheel). `uvx gtm-shortlist` or `pipx run gtm-shortlist` starts the API and worker together, as `shortlist serve` does, and opens the browser.
- **Docker alternative:** a local-mode image (`SHORTLIST_MODE=local`, SQLite on a volume): `docker run -p 8014:8014 -v gtm:/data ghcr.io/adkbbx/gtm-shortlist:local`. The existing image and compose file are hosted-mode only.
- **Contributors:** keep the current clone and `npm run build` path for people changing the code.

**First run is a two-step setup card,** replacing the need to edit `.env`:
1. **Model:** one-click presets, "Ollama on this computer", "LM Studio on this computer" and "OpenAI-compatible URL + key", each with a Test button.
   - It keeps the current rule of no automatic connection attempts: the person clicks the preset, then it tests.
2. **Search:** paste a Tavily key, which has a free tier, with SerpApi as the alternative. Again with a Test button.
   - Keys are stored server-side as today; readiness only ever reports true or false.

**Try it with sample data** (built): runs the whole flow with a packaged sample provider, separate from the test fixtures.
- A first-time user sees offer, target, discovery, evidence and review before getting any keys.
- Every screen in this mode is labelled "Sample data" and nothing is exported as real research.

## Shared by both

- Landing → one-press start → live draft → review-first confirmation → progress → results.
- The same review card, status colours and progress view in both paths. Hosted adds only the inline sign-in panel and the price line.

## Build checklist

Ticked items are built, tested and pushed on `claude/signal-landing`; items marked *you* need an account setting only the owner can make.

**Phase 1** (small)
- [x] Hosted landing note shows "First 3 companies free · no card needed"; local and preview keep "Discovery waits until you confirm the target".
- [x] The landing page no longer links to the demo; "While it runs" points to the company field. The workspace start page keeps "Try the demo".
- [x] `shortlist serve --open` opens the browser once the API answers (`open_when_ready`, unit-tested).
- [x] Local first-run setup card: "Research model" and "Company search" steps with status marks; each button opens Settings at its section. Replaces the "Open Settings" prompt.

**Phase 2** (medium)
- [x] Email code sign-in (6 digits, same tab) on the account form, behind `SHORTLIST_AUTH_EMAIL_CODE=on`; pasted codes keep only digits. *You:* add `{{ .Token }}` to the Supabase Magic Link and Confirm signup templates (docs/sign-in.md).
- [x] Google sign-in button behind `SHORTLIST_AUTH_GOOGLE=on`, using Supabase OAuth with the existing PKCE return. *You:* create a Google OAuth client and enable the provider in Supabase (docs/sign-in.md).
- [x] Local "Try it with sample data" on the setup card: `POST /api/samples` (local only) creates a flagged run; the worker swaps in `shortlist.sample` (invented companies on reserved `.example` domains, no network) for every step. A banner labels every screen. Domains read as company names, sample links are plain text, and the demo link is hidden while the card shows. JSON, CSV and Excel exports carry the label, and reuse is blocked.

**Phase 3** (medium to large)
- [x] Anonymous draft-only runs: no search, page fetch and model call only; 24-hour expiry. Migration 011 adds three tables the API role cannot touch, only three claim-hash-scoped functions. The worker drafts queued rows and never re-dispatches a lapsed lease. The landing page shows the draft live at `?draft=1`. *You:* apply migration 011.
- [x] Claim on sign-in: removing the draft and creating the run share one transaction, so a refused credit check keeps the draft. The run starts at the offer stage with the saved page and draft, so market exploration follows with no second fetch or model call. The workspace retries while the draft is still being written.
- [x] Abuse limits: Turnstile verified server-side before any model call; one draft per browser and per network address each day, kept only as keyed hashes; a global daily cap (`SHORTLIST_ANONYMOUS_DAILY_CAP`); and the kill switch `SHORTLIST_ANONYMOUS_DRAFTS` (off by default). *You:* Cloudflare Turnstile site and secret keys, then switch it on (docs/anonymous-drafts.md).
- [x] PyPI package with the built UI and a console entry that opens the browser. `gtm-shortlist` (name free on PyPI as of 18 October) runs API and worker locally, opens the browser and keeps research in the user data folder. `package.yml` builds and smoke-tests a fresh install on every push and publishes on `v*` tags. *You:* add a trusted publisher on PyPI (project `gtm-shortlist`, workflow `package.yml`, environment `pypi`), create the `pypi` environment in GitHub, then push a `v0.1.0` tag.
- [x] ~~Local-mode Docker image published to GHCR.~~ Decided against (18 October). Local mode has no sign-in: its trust boundary is that requests come from this computer's loopback address, and `container_entrypoint` refuses local mode for that reason. In a container every request arrives from the Docker gateway, and on Docker Desktop LAN traffic does too, so key setup and saved research could be reached from the network. Host Ollama would also need a non-loopback HTTP exception. `uvx gtm-shortlist` already gives a one-command install with no Node or build.

Phase 3 changes auth and data storage. It needs its own tests for expiry, claiming, abuse caps and the kill switch, plus Postgres migrations.

## Open decisions

1. Are anonymous drafts acceptable at all? They spend model calls before an account exists. Built behind a default-off switch, bounded by Turnstile, per-visitor and global caps, and no search; the owner decides when to switch it on.
2. Should sign-in be OTP code only, or OTP plus Google? Google needs an OAuth client in Google Cloud and Supabase.
3. ~~PyPI package name and whether to publish a local Docker image.~~ `gtm-shortlist`; no local image (see the checklist).
4. Should sample-data mode be offered on the hosted site too, for visitors who will not type their company? Not built: hosted runs belong to an account and spend credits, so `/api/samples` answers 404 there.
