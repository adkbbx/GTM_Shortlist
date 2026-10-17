import type { Page } from '@playwright/test';

export const authOrigin = 'https://shortlist-auth.example';
export const userId = 'b9999999-1111-4444-8888-333333333333';

/** Hosted mode with a labelled fake auth service; the research API stays the local fixture server.
    `setup` adds operator switches such as email_code or draft_site_key to the public auth setup. */
export async function hosted(page: Page, setup: { [name: string]: unknown } = {}) {
  const expiry = Math.floor(Date.now() / 1000) + 3600;
  const token = `${Buffer.from(JSON.stringify({ alg: 'HS256', typ: 'JWT' })).toString('base64url')}.${Buffer.from(JSON.stringify({ sub: userId, exp: expiry, role: 'authenticated' })).toString('base64url')}.labelled-landing-fixture`;
  await page.route('**/api/auth/setup', route => route.fulfill({ json: { mode: 'hosted', supabase_url: authOrigin, publishable_key: 'sb_publishable_fixture', redirect_url: 'http://127.0.0.1:8015/', ...setup } }));
  await page.route(`${authOrigin}/auth/v1/**`, route => {
    const headers = { 'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Headers': '*', 'Access-Control-Allow-Methods': '*' };
    if (route.request().method() === 'OPTIONS') return route.fulfill({ status: 204, headers });
    return route.fulfill({ headers, json: { access_token: token, token_type: 'bearer', expires_in: 3600, expires_at: expiry, refresh_token: 'labelled-refresh',
      user: { id: userId, aud: 'authenticated', role: 'authenticated', email: 'landing@example.test', email_confirmed_at: '2026-10-14T00:00:00Z', app_metadata: {}, user_metadata: {}, identities: [], created_at: '2026-10-14T00:00:00Z' } } });
  });
  await page.route('**/api/runs', route => route.request().method() === 'GET' ? route.fulfill({ json: [] }) : route.fallback());
}
