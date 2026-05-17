import { test, expect } from '@playwright/test';
import { loginAndNavigate, waitForStable, apiCall, DATA } from './helpers';

test.describe('Phase 4 — Custom Rules, Correlation & Monitoring', () => {

  test('4.1 Custom signal rules page loads', async ({ page }) => {
    await loginAndNavigate(page, '/signals/rules');
    await waitForStable(page);
    await expect(page.locator('h1:has-text("Custom Signal Rules")')).toBeVisible({ timeout: 10000 });
    await expect(page.getByRole('button', { name: 'New Rule' })).toBeVisible();
    await page.screenshot({ path: 'e2e/screenshots/p4-1-rules-page.png', fullPage: true });
  });

  test('4.2 PillTabs nav Feed <-> Rules', async ({ page }) => {
    await loginAndNavigate(page, '/signals/rules');
    await waitForStable(page);
    await page.getByText('Signal Feed', { exact: true }).first().click();
    await page.waitForURL('**/signals', { timeout: 5000 });
    await expect(page.locator('h1:has-text("Signal Feed")')).toBeVisible();
    await page.getByText('Signal Rules', { exact: true }).first().click();
    await page.waitForURL('**/signals/rules', { timeout: 5000 });
    await page.screenshot({ path: 'e2e/screenshots/p4-2-pill-nav.png', fullPage: true });
  });

  test('4.3 Create keyword rule via API', async ({ page }) => {
    await loginAndNavigate(page, '/dashboard');
    const resp = await apiCall(page, 'POST', '/signal-rules/', {
      name: 'E2E Test — Cloud Keywords',
      description: 'Playwright test rule',
      rule_type: 'keyword',
      rule_config: { keywords: ['cloud migration', 'AWS', 'Azure'], match_any: true },
      signal_type_output: 'tech_adoption',
      priority_output: 'high',
    });
    expect(resp.status).toBe(200);
    expect(resp.data.id).toBeTruthy();
    expect(resp.data.name).toBe('E2E Test — Cloud Keywords');
    await page.screenshot({ path: 'e2e/screenshots/p4-3-create-rule.png' });
  });

  test('4.4 List rules via API', async ({ page }) => {
    await loginAndNavigate(page, '/dashboard');
    const resp = await apiCall(page, 'GET', '/signal-rules/');
    expect(resp.status).toBe(200);
    expect(resp.data.total).toBeGreaterThanOrEqual(1);
    const testRule = resp.data.rules.find((r: any) => r.name.includes('E2E Test'));
    expect(testRule).toBeTruthy();
    await page.screenshot({ path: 'e2e/screenshots/p4-4-list-rules.png' });
  });

  test('4.5 Toggle rule active/inactive', async ({ page }) => {
    await loginAndNavigate(page, '/dashboard');
    const list = await apiCall(page, 'GET', '/signal-rules/');
    const rule = list.data.rules.find((r: any) => r.name.includes('E2E Test'));
    if (rule) {
      const toggle1 = await apiCall(page, 'POST', `/signal-rules/${rule.id}/toggle`);
      expect(toggle1.status).toBe(200);
      expect(toggle1.data.is_active).toBe(false);
      const toggle2 = await apiCall(page, 'POST', `/signal-rules/${rule.id}/toggle`);
      expect(toggle2.data.is_active).toBe(true);
    }
    await page.screenshot({ path: 'e2e/screenshots/p4-5-toggle-rule.png' });
  });

  test('4.6 Create composite rule', async ({ page }) => {
    await loginAndNavigate(page, '/dashboard');
    const resp = await apiCall(page, 'POST', '/signal-rules/', {
      name: 'E2E Test — Funding+Hiring',
      rule_type: 'composite',
      rule_config: {
        conditions: [
          { signal_type: 'funding', min_count: 1, within_days: 90 },
          { signal_type: 'hiring_surge', min_count: 1, within_days: 90 },
        ],
        operator: 'all',
      },
      priority_output: 'critical',
    });
    expect(resp.status).toBe(200);
    expect(resp.data.rule_type).toBe('composite');
    await page.screenshot({ path: 'e2e/screenshots/p4-6-composite-rule.png' });
  });

  test('4.7 Monitoring check (dry run)', async ({ page }) => {
    await loginAndNavigate(page, '/dashboard');
    const resp = await apiCall(page, 'POST', '/signals/monitoring/check?dry_run=true');
    expect(resp.status).toBe(200);
    expect(typeof resp.data.triggered).toBe('number');
    expect(typeof resp.data.skipped).toBe('number');
    await page.screenshot({ path: 'e2e/screenshots/p4-7-monitoring-check.png' });
  });

  test('4.8 Configure monitoring', async ({ page }) => {
    await loginAndNavigate(page, '/dashboard');
    const resp = await apiCall(page, 'PUT', `/signals/monitoring/${DATA.trackingListId}`, {
      enabled: true, frequency_days: 7, alert_threshold: 'high',
    });
    expect(resp.status).toBe(200);
    expect(resp.data.monitoring_config?.enabled).toBe(true);
    await page.screenshot({ path: 'e2e/screenshots/p4-8-monitoring-configure.png' });
  });

  test('4.9 Rules page shows created rules', async ({ page }) => {
    await loginAndNavigate(page, '/signals/rules');
    await waitForStable(page);
    await expect(page.getByText('E2E Test').first()).toBeVisible({ timeout: 10000 });
    await page.screenshot({ path: 'e2e/screenshots/p4-9-rules-displayed.png', fullPage: true });
  });

  test('4.10 Cleanup test rules', async ({ page }) => {
    await loginAndNavigate(page, '/dashboard');
    const list = await apiCall(page, 'GET', '/signal-rules/');
    const testRules = list.data.rules.filter((r: any) => r.name.includes('E2E Test'));
    for (const rule of testRules) {
      await apiCall(page, 'DELETE', `/signal-rules/${rule.id}`);
    }
    expect(testRules.length).toBeGreaterThanOrEqual(1);
    await page.screenshot({ path: 'e2e/screenshots/p4-10-cleanup.png' });
  });
});
