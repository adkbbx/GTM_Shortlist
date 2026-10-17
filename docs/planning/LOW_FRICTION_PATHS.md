# Lowest-friction paths: hosted and local

17 October 2026. Request: the shortest possible path to value for a hosted visitor and for someone who wants to run GTM Shortlist on their own machine. This is a plan; nothing here is built yet except where marked.

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
- **Endpoint:** `POST /api/drafts` takes `{ website, turnstile_token }` and returns `{ draft_id, claim_token }`. `GET /api/drafts/{id}` takes the claim token as a bearer and streams the same progress events as a run.
- **Storage:** a separate `anonymous_drafts` table holding the website, saved page snapshot, draft and events. It has no workspace and no credits, and expires after 24 hours.
- **Claiming:** after sign-in, `POST /api/drafts/{id}/claim` copies the draft into a normal run in `awaiting_confirmation`, then deletes the anonymous copy. Market exploration starts in the background after the claim; campaign ideas appear in the review card when ready and never block confirmation.
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

**Try with sample data:** runs the whole flow with the labelled synthetic providers the UI tests already use.
- A first-time user sees offer, target, discovery, evidence and review before getting any keys.
- Every screen in this mode is labelled "Sample data" and nothing is exported as real research.

## Shared by both

- Landing → one-press start → live draft → review-first confirmation → progress → results.
- The same review card, status colours and progress view in both paths. Hosted adds only the inline sign-in panel and the price line.

## Build order

| Phase | Hosted | Local | Size |
|---|---|---|---|
| 1 | Price line on the landing page, drop the demo link | `shortlist serve --open` opens the browser; first-run setup card using the existing settings APIs | Small |
| 2 | Email OTP and Google sign-in panel (Supabase settings + UI) | Try with sample data | Medium |
| 3 | Anonymous drafts, claim on sign-in, Turnstile and caps | PyPI package with the UI included; local Docker image | Medium–large |

Phase 3 changes auth and data storage. It needs its own tests for expiry, claiming, abuse caps and the kill switch, plus Postgres migrations.

## Open decisions

1. Are anonymous drafts acceptable at all? They spend model calls before an account exists. This plan bounds them with Turnstile, per-visitor and global caps, and no search.
2. Should sign-in be OTP code only, or OTP plus Google? Google needs an OAuth client in Google Cloud and Supabase.
3. PyPI package name (`gtm-shortlist` if available) and whether to publish a local Docker image.
4. Should sample-data mode be offered on the hosted site too, for visitors who will not type their company?
