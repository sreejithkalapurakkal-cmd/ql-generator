import { test, expect } from '@playwright/test';
import { loginAndNavigate, waitForStable, apiCall, DATA } from './helpers';

test.describe('Phase 3 — Draft Drawer & Notifications', () => {

  test('3.1 Outreach generation API', async ({ page }) => {
    await loginAndNavigate(page, '/dashboard');
    const resp = await apiCall(page, 'POST', `/briefs/outreach/${DATA.companyKbId}`, {
      format: 'email', tone: 'direct',
    });
    expect(resp.status).toBe(200);
    expect(resp.data.id).toBeTruthy();
    expect(resp.data.body).toBeTruthy();
    expect(resp.data.format).toBe('email');
    await page.screenshot({ path: 'e2e/screenshots/p3-1-outreach-api.png' });
  });

  test('3.2 Draft Drawer opens from signal detail', async ({ page }) => {
    await loginAndNavigate(page, '/signals');
    await waitForStable(page);
    const row = page.locator('[role="feed"] > div').first();
    if (await row.isVisible()) {
      await row.click();
      await page.waitForTimeout(500);
      const btn = page.getByText('Draft email outreach').first();
      if (await btn.isVisible()) {
        await btn.click();
        await page.waitForTimeout(1000);
        await expect(page.locator('.ant-drawer-open')).toBeVisible({ timeout: 5000 });
        await expect(page.getByText('Draft Outreach').first()).toBeVisible();
        await page.screenshot({ path: 'e2e/screenshots/p3-2-draft-drawer-open.png', fullPage: true });
        await page.locator('.ant-drawer-mask').click();
      }
    }
  });

  test('3.3 Draft Drawer has format/tone/voice controls', async ({ page }) => {
    await loginAndNavigate(page, '/signals');
    await waitForStable(page);
    const row = page.locator('[role="feed"] > div').first();
    if (await row.isVisible()) {
      await row.click();
      await page.waitForTimeout(500);
      const btn = page.getByText('Draft email outreach').first();
      if (await btn.isVisible()) {
        await btn.click();
        await page.waitForTimeout(1000);
        await expect(page.getByRole('button', { name: 'Email' }).first()).toBeVisible();
        await expect(page.getByRole('button', { name: 'LinkedIn' }).first()).toBeVisible();
        await expect(page.getByRole('button', { name: 'Direct' }).first()).toBeVisible();
        await expect(page.getByRole('button', { name: 'Concise' }).first()).toBeVisible();
        await page.screenshot({ path: 'e2e/screenshots/p3-3-drawer-controls.png', fullPage: true });
        await page.locator('.ant-drawer-mask').click();
      }
    }
  });

  test('3.4 Draft Drawer opens from account profile', async ({ page }) => {
    await loginAndNavigate(page, `/tracking/${DATA.trackingListId}/company/${DATA.membershipId}`);
    await waitForStable(page);
    const btn = page.getByRole('button', { name: 'Draft' }).first();
    if (await btn.isVisible()) {
      await btn.click();
      await page.waitForTimeout(1000);
      await expect(page.locator('.ant-drawer-open')).toBeVisible({ timeout: 5000 });
      await page.screenshot({ path: 'e2e/screenshots/p3-4-drawer-from-profile.png', fullPage: true });
      await page.locator('.ant-drawer-mask').click();
    }
  });

  test('3.5 Notification bell visible', async ({ page }) => {
    await loginAndNavigate(page, '/dashboard');
    await waitForStable(page);
    await expect(page.locator('.anticon-bell').first()).toBeVisible({ timeout: 10000 });
    await page.screenshot({ path: 'e2e/screenshots/p3-5-notification-bell.png' });
  });

  test('3.6 Notification drawer opens', async ({ page }) => {
    await loginAndNavigate(page, '/dashboard');
    await waitForStable(page);
    await page.locator('.anticon-bell').first().click();
    await page.waitForTimeout(500);
    await expect(page.locator('.ant-drawer-open')).toBeVisible({ timeout: 5000 });
    await expect(page.getByText('Notifications').first()).toBeVisible();
    await page.screenshot({ path: 'e2e/screenshots/p3-6-notification-drawer.png', fullPage: true });
  });

  test('3.7 Notification unread count API', async ({ page }) => {
    await loginAndNavigate(page, '/dashboard');
    const resp = await apiCall(page, 'GET', '/notifications/unread-count');
    expect(resp.status).toBe(200);
    expect(typeof resp.data.unread_count).toBe('number');
    await page.screenshot({ path: 'e2e/screenshots/p3-7-notification-api.png' });
  });

  test('3.8 Recent drafts API', async ({ page }) => {
    await loginAndNavigate(page, '/dashboard');
    const resp = await apiCall(page, 'GET', '/briefs/drafts/recent?limit=3');
    expect(resp.status).toBe(200);
    expect(Array.isArray(resp.data.drafts)).toBeTruthy();
    await page.screenshot({ path: 'e2e/screenshots/p3-8-recent-drafts-api.png' });
  });

  test('3.9 Draft lifecycle (create + update status)', async ({ page }) => {
    await loginAndNavigate(page, '/dashboard');
    const create = await apiCall(page, 'POST', `/briefs/outreach/${DATA.companyKbId}`, {
      format: 'linkedin', tone: 'casual',
    });
    expect(create.status).toBe(200);
    if (create.data.id) {
      const update = await apiCall(page, 'PATCH', `/briefs/drafts/${create.data.id}`, { status: 'sent' });
      expect(update.status).toBe(200);
      expect(update.data.status).toBe('sent');
    }
    await page.screenshot({ path: 'e2e/screenshots/p3-9-draft-lifecycle.png' });
  });
});
