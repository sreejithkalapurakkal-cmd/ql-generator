import { type Page, type BrowserContext, expect } from '@playwright/test';

const TEST_USER_ID = 'e7d058ca-fb8f-4d96-afc7-124255d90c43';

// Module-level token cache — survives across page navigations
let _cachedToken: string | null = null;

/**
 * Login and navigate to a protected page.
 */
export async function loginAndNavigate(page: Page, path: string): Promise<void> {
  // Go to the welcome page first so we're on the right domain
  await page.goto('/welcome', { waitUntil: 'domcontentloaded' });

  // Call test-login through the Vite proxy (/api → localhost:8000)
  const token = await page.evaluate(async (userId) => {
    const resp = await fetch('/api/v1/auth/test-login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ user_id: userId }),
      credentials: 'include',
    });
    if (!resp.ok) throw new Error(`Login failed: ${resp.status}`);
    const data = await resp.json();
    return data.access_token as string;
  }, TEST_USER_ID);

  _cachedToken = token;

  // Navigate to the target page
  await page.goto(path, { waitUntil: 'networkidle' });
  await page.waitForSelector('.gnav-logo', { timeout: 15000 });
}

/**
 * Make an authenticated API call from page context.
 * Passes the token as a parameter to avoid window state issues.
 */
export async function apiCall(
  page: Page,
  method: string,
  path: string,
  body?: unknown,
): Promise<{ status: number; data: any }> {
  return page.evaluate(async ({ method, path, body, token }) => {
    const opts: RequestInit = {
      method,
      credentials: 'include',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
    };
    if (body) opts.body = JSON.stringify(body);
    const r = await fetch(`/api/v1${path}`, opts);
    const data = await r.json().catch(() => ({}));
    return { status: r.status, data };
  }, { method, path, body, token: _cachedToken });
}

/** Get the cached access token for custom evaluate calls. */
export function getToken(): string | null {
  return _cachedToken;
}

/** Wait for page to stabilize (no spinners, content loaded). */
export async function waitForStable(page: Page, timeout = 10000): Promise<void> {
  // Wait for any Ant Design spinners to disappear
  await page.waitForFunction(() => {
    const spinners = document.querySelectorAll('.ant-spin-spinning');
    return spinners.length === 0;
  }, { timeout });
}

// Known test data IDs
export const DATA = {
  trackingListId: '55e5b3dc-b1a9-4806-8606-b46b41f00955',
  trackingListName: 'Test Signal List',
  membershipId: 'a0c2e710-5105-46df-a71a-4d33407d47f4',
  companyKbId: '80de0a69-0e19-4f9c-b3b9-09b833727d06',
  companyName: 'datadog.com',
  secondListId: 'c862afbf-da73-4244-b0fe-32ecfad17e0a',
};
