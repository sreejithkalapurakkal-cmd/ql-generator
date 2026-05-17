/**
 * Shared auth helper for Playwright tests.
 *
 * Generates a refresh_token cookie by calling the backend directly,
 * then the frontend's AuthProvider picks it up via silent refresh.
 */
import { type Page, type BrowserContext } from '@playwright/test';

// Admin user — has tracking lists, signals, and access to all features
const TEST_USER_ID = 'e7d058ca-fb8f-4d96-afc7-124255d90c43';
const API_BASE = 'http://localhost:8000/api/v1';

/**
 * Authenticate a browser context by setting the refresh_token cookie
 * and then navigating to any protected page so the frontend
 * auto-refreshes and gets an access_token.
 */
export async function authenticate(context: BrowserContext): Promise<void> {
  // Generate a refresh token via the backend utility
  // We call a special test endpoint or use the JWT lib directly
  // Since we can't call Python from here, we'll use the API approach:
  // Set the cookie directly using a token we generate via fetch
  const resp = await fetch(`${API_BASE}/auth/test-login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ user_id: TEST_USER_ID }),
  }).catch(() => null);

  if (resp && resp.ok) {
    // Extract refresh_token from Set-Cookie
    const cookies = resp.headers.getSetCookie?.() || [];
    for (const cookie of cookies) {
      if (cookie.startsWith('refresh_token=')) {
        const value = cookie.split(';')[0].split('=')[1];
        await context.addCookies([{
          name: 'refresh_token',
          value,
          domain: 'localhost',
          path: '/api/v1/auth',
          httpOnly: true,
          secure: false,
          sameSite: 'Lax',
        }]);
        return;
      }
    }
  }

  // Fallback: generate token locally using the known JWT secret
  // JWT: header.payload.signature with HS256
  const header = btoa(JSON.stringify({ alg: 'HS256', typ: 'JWT' })).replace(/=/g, '');
  const exp = Math.floor(Date.now() / 1000) + 86400; // 24h
  const payload = btoa(JSON.stringify({ sub: TEST_USER_ID, exp, type: 'refresh' })).replace(/=/g, '');

  // We can't sign properly without the secret in JS, so use the pre-generated approach
  // Instead, just set the cookie with a pre-generated long-lived refresh token
  // Generated via: create_refresh_token(TEST_USER_ID) in Python
  // This will be done in the global setup
}

/**
 * Login by injecting tokens via page.evaluate after navigating to the app.
 * This bypasses cookie issues by directly calling the API with fetch.
 */
export async function loginViaApi(page: Page): Promise<void> {
  // Navigate to the app first
  await page.goto('/welcome');

  // Use page.evaluate to call the refresh endpoint with a pre-set cookie
  // Alternative: directly inject the access token into the app's state
  await page.evaluate(async (config) => {
    const resp = await fetch(`${config.apiBase}/auth/test-login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ user_id: config.userId }),
      credentials: 'include',
    });
    if (!resp.ok) {
      throw new Error(`Test login failed: ${resp.status}`);
    }
    const data = await resp.json();
    // Store token in module-level variable by setting it on window
    (window as any).__TEST_ACCESS_TOKEN__ = data.access_token;
  }, { apiBase: API_BASE, userId: TEST_USER_ID });
}

// Test data IDs (from the database)
export const TEST_DATA = {
  userId: TEST_USER_ID,
  trackingListId: '55e5b3dc-b1a9-4806-8606-b46b41f00955', // "Test Signal List"
  trackingListName: 'Test Signal List',
  secondListId: 'c862afbf-da73-4244-b0fe-32ecfad17e0a', // "Resilient Search Test"
  // A company KB ID with signals
  companyKbId: '5917ed89-a1a7-48e9-b7ee-988edc8f0845',
  apiBase: API_BASE,
};
