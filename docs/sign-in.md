# Hosted sign-in methods

Email and password always work. Two faster methods are offered only after the operator switches them on, because each needs matching Supabase configuration first. Both keep the visitor in the same tab, so a company typed on the landing page carries straight into research after sign-in.

## Email code (recommended)

People type their email, receive a 6-digit code and enter it on the same page. There is no password and no confirmation link to open in another tab; a verified code also confirms the email.

1. **Email template.** In Supabase, open Authentication → Email Templates and add the code to both the **Magic Link** and **Confirm signup** templates, for example `Your GTM Shortlist code is {{ .Token }}`. Keep or remove the link as you prefer; the app only needs the code.
2. **Switch it on.** On the **web service**, set `SHORTLIST_AUTH_EMAIL_CODE=on` and restart.

Supabase rate-limits code emails per address; "Resend code" asks for a new one and the newest code wins.

## Google

1. **Google Cloud.** Create an OAuth client of type *Web application*. Add the authorized redirect URI `https://<your-project>.supabase.co/auth/v1/callback`.
2. **Supabase provider.** In Authentication → Providers → Google, enable it and paste the client ID and secret.
3. **Allowed return address.** In Authentication → URL Configuration, make sure `SHORTLIST_APP_URL` (for example `https://gtm-shortlist.onrender.com/`) is the site URL or in the redirect allow list.
4. **Switch it on.** On the **web service**, set `SHORTLIST_AUTH_GOOGLE=on` and restart.

## Checks

Only the exact value `on` enables a method. `GET /api/auth/setup` reports `email_code` and `google` so you can confirm what visitors will see; it exposes no secrets. Browser tests cover the code flow from the landing page through to the first research run, and the Google button's hand-off to the provider.
