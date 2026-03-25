/**
 * Playwright global setup — authenticates via dev-token endpoint
 * and saves browser state for both admin and regular user.
 */
import { test as setup, expect } from '@playwright/test';

const API_BASE = 'http://localhost:8000/api/v1';
const ADMIN_EMAIL = 'test@gadgeon.com';
const USER_EMAIL = 'sarah.patel@gadgeon.com';

async function authenticateAndSave(
  page: import('@playwright/test').Page,
  email: string,
  storageStatePath: string,
) {
  // Call dev-token endpoint to get tokens + set refresh cookie
  const resp = await page.request.post(`${API_BASE}/auth/dev-token`, {
    data: { email },
  });
  expect(resp.ok()).toBeTruthy();
  const body = await resp.json();
  const accessToken = body.access_token;
  const user = body.user;

  // Navigate to the app so we can set localStorage/sessionStorage
  await page.goto('http://localhost:3000/welcome');

  // The React AuthProvider reads the refresh cookie on mount and gets a new
  // access token via /auth/refresh. The cookie is already set by the dev-token
  // response. We just need to verify the page loads with the cookie present.
  // But to make navigation faster, we also store user info for the test to read.
  await page.evaluate(
    ({ token, user }) => {
      // Store seeded IDs in sessionStorage so screenshot tests can use them
      sessionStorage.setItem('pw_access_token', token);
      sessionStorage.setItem('pw_user', JSON.stringify(user));
    },
    { token: accessToken, user },
  );

  await page.context().storageState({ path: storageStatePath });
}

setup('authenticate admin', async ({ page }) => {
  await authenticateAndSave(page, ADMIN_EMAIL, 'e2e/.auth/admin.json');
});

setup('authenticate user', async ({ page }) => {
  await authenticateAndSave(page, USER_EMAIL, 'e2e/.auth/user.json');
});
