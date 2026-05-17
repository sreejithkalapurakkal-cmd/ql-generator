import { test, expect } from '@playwright/test';
import { loginAndNavigate, waitForStable, apiCall, DATA } from './helpers';

test.describe('Phase 2 — Signal Feed & Dashboard', () => {

  test('2.1 Signal feed page loads', async ({ page }) => {
    await loginAndNavigate(page, '/signals');
    await waitForStable(page);
    await expect(page.locator('h1:has-text("Signal Feed")')).toBeVisible({ timeout: 10000 });
    await expect(page.getByText('Live').first()).toBeVisible();
    await page.screenshot({ path: 'e2e/screenshots/p2-1-signal-feed.png', fullPage: true });
  });

  test('2.2 Tab filters visible (All, Today, Week, Saved)', async ({ page }) => {
    await loginAndNavigate(page, '/signals');
    await waitForStable(page);
    for (const tab of ['All', 'Today', 'This Week', 'Saved']) {
      await expect(page.getByRole('button', { name: tab, exact: true }).first()).toBeVisible();
    }
    await page.getByRole('button', { name: 'Saved', exact: true }).first().click();
    await waitForStable(page);
    await page.screenshot({ path: 'e2e/screenshots/p2-2-tab-filters.png', fullPage: true });
  });

  test('2.3 Filter dropdowns render', async ({ page }) => {
    await loginAndNavigate(page, '/signals');
    await waitForStable(page);
    const selects = page.locator('.ant-select');
    expect(await selects.count()).toBeGreaterThanOrEqual(2);
    await page.screenshot({ path: 'e2e/screenshots/p2-3-filters.png' });
  });

  test('2.4 Clicking signal opens detail pane', async ({ page }) => {
    await loginAndNavigate(page, '/signals');
    await waitForStable(page);
    const row = page.locator('[role="feed"] > div').first();
    if (await row.isVisible()) {
      await row.click();
      await page.waitForTimeout(500);
      await expect(page.getByText('Signal headline').first()).toBeVisible({ timeout: 5000 });
      await page.screenshot({ path: 'e2e/screenshots/p2-4-detail-pane.png', fullPage: true });
    }
  });

  test('2.5 Feed API returns expected structure', async ({ page }) => {
    await loginAndNavigate(page, '/dashboard');
    const resp = await apiCall(page, 'GET', '/signals/feed?limit=5');
    expect(resp.status).toBe(200);
    expect(Array.isArray(resp.data.signals)).toBeTruthy();
    expect(typeof resp.data.total).toBe('number');
    expect(typeof resp.data.snoozed_returned_count).toBe('number');
    await page.screenshot({ path: 'e2e/screenshots/p2-5-feed-api.png' });
  });

  test('2.6 Save + unsave signal API', async ({ page }) => {
    await loginAndNavigate(page, '/dashboard');
    const feed = await apiCall(page, 'GET', '/signals/feed?limit=1');
    const signalId = feed.data.signals?.[0]?.id;
    if (signalId) {
      const save = await apiCall(page, 'POST', `/signals/${signalId}/save`);
      expect(save.status).toBe(200);
      const unsave = await apiCall(page, 'DELETE', `/signals/${signalId}/save`);
      expect(unsave.status).toBe(200);
    }
    await page.screenshot({ path: 'e2e/screenshots/p2-6-save-api.png' });
  });

  test('2.7 Snooze signal API', async ({ page }) => {
    await loginAndNavigate(page, '/dashboard');
    const feed = await apiCall(page, 'GET', '/signals/feed?limit=1');
    const signalId = feed.data.signals?.[0]?.id;
    if (signalId) {
      const resp = await apiCall(page, 'POST', `/signals/${signalId}/snooze`, { duration_hours: 1 });
      expect(resp.status).toBe(200);
      expect(resp.data.status).toBe('snoozed');
    }
    await page.screenshot({ path: 'e2e/screenshots/p2-7-snooze-api.png' });
  });

  test('2.8 Dashboard shows signal intelligence', async ({ page }) => {
    await loginAndNavigate(page, '/dashboard');
    await waitForStable(page);
    await expect(page.locator('h1:has-text("Dashboard")')).toBeVisible({ timeout: 10000 });
    const hasSection = await page.getByText('Signal Intelligence').count() > 0;
    const hasTile = await page.getByText('Active Signals').count() > 0;
    expect(hasSection || hasTile).toBeTruthy();
    await page.screenshot({ path: 'e2e/screenshots/p2-8-dashboard-signals.png', fullPage: true });
  });

  test('2.9 Dashboard stats API', async ({ page }) => {
    await loginAndNavigate(page, '/dashboard');
    const resp = await apiCall(page, 'GET', '/signals/dashboard-stats');
    expect(resp.status).toBe(200);
    expect(typeof resp.data.total_active).toBe('number');
    expect(typeof resp.data.this_week).toBe('number');
    expect(Array.isArray(resp.data.top_signals)).toBeTruthy();
    await page.screenshot({ path: 'e2e/screenshots/p2-9-dashboard-stats-api.png' });
  });

  test('2.10 PillTabs nav Lists <-> Feed', async ({ page }) => {
    await loginAndNavigate(page, '/signals');
    await waitForStable(page);
    await page.getByText('My Lists', { exact: true }).first().click();
    await page.waitForURL('**/tracking**', { timeout: 5000 });
    await page.screenshot({ path: 'e2e/screenshots/p2-10-pill-tab-nav.png', fullPage: true });
  });
});
