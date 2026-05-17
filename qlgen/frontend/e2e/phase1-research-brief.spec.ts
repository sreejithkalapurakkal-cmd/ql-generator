import { test, expect } from '@playwright/test';
import { loginAndNavigate, waitForStable, apiCall, DATA } from './helpers';

test.describe('Phase 1 — Research Brief & Account Profile', () => {

  test('1.1 API: GET /briefs/{id} returns brief or empty', async ({ page }) => {
    await loginAndNavigate(page, '/dashboard');
    const resp = await apiCall(page, 'GET', `/briefs/${DATA.companyKbId}`);
    expect(resp.status).toBe(200);
    await page.screenshot({ path: 'e2e/screenshots/p1-1-brief-api.png' });
  });

  test('1.2 Account profile page loads with 6 tabs', async ({ page }) => {
    await loginAndNavigate(page, `/tracking/${DATA.trackingListId}/company/${DATA.membershipId}`);
    await waitForStable(page);
    await expect(page.getByRole('heading', { name: /datadog/i }).first()).toBeVisible({ timeout: 10000 });

    for (const label of ['Overview', 'Signals', 'Research brief', 'Drafts', 'Contacts', 'Notes & History']) {
      await expect(page.getByText(label, { exact: true }).first()).toBeVisible();
    }
    await page.screenshot({ path: 'e2e/screenshots/p1-2-account-profile-tabs.png', fullPage: true });
  });

  test('1.3 Signals tab shows signal timeline', async ({ page }) => {
    await loginAndNavigate(page, `/tracking/${DATA.trackingListId}/company/${DATA.membershipId}`);
    await waitForStable(page);
    await page.getByText('Signals', { exact: true }).first().click();
    await waitForStable(page);
    await expect(page.getByText('Signal Timeline').first()).toBeVisible({ timeout: 10000 });
    await page.screenshot({ path: 'e2e/screenshots/p1-3-signals-tab.png', fullPage: true });
  });

  test('1.4 Research brief tab renders', async ({ page }) => {
    await loginAndNavigate(page, `/tracking/${DATA.trackingListId}/company/${DATA.membershipId}`);
    await waitForStable(page);
    await page.getByText('Research brief', { exact: true }).first().click();
    await waitForStable(page);
    // Should show brief content, generate button, or empty state
    const body = await page.textContent('body');
    expect(body!.length).toBeGreaterThan(100);
    await page.screenshot({ path: 'e2e/screenshots/p1-4-brief-tab.png', fullPage: true });
  });

  test('1.5 Drafts tab renders', async ({ page }) => {
    await loginAndNavigate(page, `/tracking/${DATA.trackingListId}/company/${DATA.membershipId}`);
    await waitForStable(page);
    await page.getByText('Drafts', { exact: true }).first().click();
    await waitForStable(page);
    const body = await page.textContent('body');
    expect(body!.length).toBeGreaterThan(100);
    await page.screenshot({ path: 'e2e/screenshots/p1-5-drafts-tab.png', fullPage: true });
  });

  test('1.6 ResearchBriefPage route loads', async ({ page }) => {
    await loginAndNavigate(page, `/tracking/${DATA.trackingListId}/company/${DATA.membershipId}/brief`);
    await page.waitForTimeout(3000);
    const body = await page.textContent('body');
    expect(body!.length).toBeGreaterThan(50);
    await page.screenshot({ path: 'e2e/screenshots/p1-6-research-brief-page.png', fullPage: true });
  });

  test('1.7 Brief versions API returns correctly', async ({ page }) => {
    await loginAndNavigate(page, '/dashboard');
    const resp = await apiCall(page, 'GET', `/briefs/${DATA.companyKbId}/versions`);
    expect(resp.status).toBe(200);
    expect(Array.isArray(resp.data.revisions)).toBeTruthy();
    await page.screenshot({ path: 'e2e/screenshots/p1-7-brief-versions-api.png' });
  });
});
