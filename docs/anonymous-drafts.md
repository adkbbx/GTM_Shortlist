# Drafts before signup (hosted)

A visitor types their website on the landing page and sees their own offer, target and fit checks drafted live, before making an account. **Save and find companies** opens sign-up; once they sign in, the draft becomes their first run, market exploration follows, and they confirm the target as usual.

It is off by default. Turn it on only after the steps below.

## What runs before signup

- **One page read and one model call.** No web search: company-name lookup, market exploration and discovery all wait for an account, so the search budget is untouched.
- **Websites only.** A plain company name (without a Brandfetch suggestion) skips the draft and goes straight to sign-up.
- **No account or credits.** Drafts live in their own table for 24 hours, then disappear. Claiming one counts as the account's normal offer draft and uses the same allowance checks.
- **One browser holds it.** The draft is read and claimed with a random token kept only in that browser.

## Limits

| Limit | How |
|---|---|
| Bot check | Cloudflare Turnstile token, verified server-side before any model call. Invisible unless Cloudflare needs an interaction. |
| Per visitor | One draft per browser and per network address each day. |
| Everyone | `SHORTLIST_ANONYMOUS_DAILY_CAP` drafts per day across all visitors (default 50). |
| Kill switch | `SHORTLIST_ANONYMOUS_DRAFTS=off` (the default) stops new drafts immediately. Drafts already saved can still be read and claimed. |
| Pages | The usual public-address, size and identity checks on the page fetch. |
| Interruptions | A draft whose worker stopped mid-call is marked failed, never sent to the model twice. |

**Privacy.** The database keeps only keyed hashes for the per-visitor limit (HMAC with the Turnstile secret), never a network address or browser ID.

The per-network limit is best-effort: it relies on the header your edge sets. The bot check and the daily cap are the real limits.

## Switch it on

1. **Migrate.** Apply `migrations/011_anonymous_drafts.sql` with the migration credential (`python scripts/migrate_postgres.py`). Restart the worker afterwards; it checks for the table at startup, so deploying the code first is safe.
2. **Turnstile.** In Cloudflare, create a Turnstile widget for your app's hostname (Managed mode). Copy the site key and the secret key.
3. **Web service environment:**
   - `SHORTLIST_ANONYMOUS_DRAFTS=on`
   - `TURNSTILE_SITE_KEY=<site key>` and `TURNSTILE_SECRET_KEY=<secret key>`. The service refuses to start with the switch on and either key missing.
   - Optional `SHORTLIST_ANONYMOUS_DAILY_CAP=50` (1 to 1000).
   - Optional `SHORTLIST_CLIENT_ADDRESS_HEADER`: the header your edge overwrites with the visitor's address, such as `CF-Connecting-IP` or `True-Client-IP`. Without it, the per-network limit uses the connection address, which behind a proxy is the proxy's.
4. **Restart** the web service. `GET /api/auth/setup` then includes `draft_site_key`, and the landing page starts drafting for typed websites.

The worker needs no new settings: it drafts with the same model configuration it uses for research.

## Checks

- `tests/test_anonymous_drafts.py`: the switch and keys, the bot check, website-only input, both limits, claim-token scoping, no stored addresses, and the one-fetch, one-model-call worker step.
- `tests/test_postgres.py::test_anonymous_drafts_are_claim_scoped_limited_and_claimed_once`: the database functions, refusals that mark nothing, the API role's lack of table access, claiming in one transaction (a refused credit check keeps the draft), replay, lapsed leases and expiry.
- `tests/ui/drafts.spec.ts`: the landing-to-run flow on laptop and phone with labelled stand-ins for Turnstile and the draft endpoints, plus the company-name and refused-draft fallbacks.
