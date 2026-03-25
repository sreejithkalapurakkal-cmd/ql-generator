/**
 * Playwright screenshot capture for the qlGen User Guide.
 *
 * Prerequisites:
 *   1. Backend + frontend running (make dev)
 *   2. ALLOW_DEV_AUTH=true in .env
 *   3. Seed data loaded (python -m app.scripts.seed_screenshot_data)
 *   4. Global setup has run (authenticates admin + user)
 *
 * Run:
 *   npx playwright test e2e/screenshots.spec.ts
 */
import { test, expect, Page } from '@playwright/test';

const SCREENSHOT_DIR = 'screenshots';
const API = 'http://localhost:8000/api/v1';

// ─── Helpers ───────────────────────────────────────────────────────────────

/** Wait for the page to finish loading data (no spinners, skeleton gone). */
async function waitForPageReady(page: Page, timeout = 15_000) {
  // Wait for any Ant Design spin indicators to disappear
  await page.waitForTimeout(1000);
  try {
    await page.waitForFunction(
      () => document.querySelectorAll('.ant-spin-spinning').length === 0,
      { timeout },
    );
  } catch {
    // Continue even if timeout — some pages may not have spinners
  }
  // Extra settle time for charts / animations
  await page.waitForTimeout(1500);
}

async function screenshot(page: Page, name: string) {
  await page.screenshot({
    path: `${SCREENSHOT_DIR}/${name}`,
    fullPage: true,
  });
}

/** Get a Bearer token via the dev-token endpoint. */
async function getToken(page: Page, email: string): Promise<string> {
  const resp = await page.request.post(`${API}/auth/dev-token`, {
    data: { email },
  });
  const body = await resp.json();
  return body.access_token as string;
}

/** Fetch seeded data IDs from the API using an explicit auth token. */
async function fetchSeededIds(page: Page, email: string) {
  const token = await getToken(page, email);
  const headers = { Authorization: `Bearer ${token}` };

  let completedRunId: string | null = null;
  let firstCompanyId: string | null = null;
  let icpId: string | null = null;

  // Get pipeline run history
  const runsResp = await page.request.get(`${API}/pipeline/history/list`, { headers });

  if (runsResp.ok()) {
    const runs = await runsResp.json();
    const runsList = Array.isArray(runs) ? runs : runs.runs || runs.data || [];
    // Find first completed run
    const completed = runsList.find((r: Record<string, unknown>) => r.status === 'completed');
    if (completed) {
      completedRunId = completed.id as string;
      icpId = completed.icp_config_id as string;
    }
  }

  // If we have a completed run, get the first company
  if (completedRunId) {
    const companiesResp = await page.request.get(
      `${API}/leads/${completedRunId}/companies`,
      { headers },
    );
    if (companiesResp.ok()) {
      const companiesData = await companiesResp.json();
      const companies = Array.isArray(companiesData)
        ? companiesData
        : companiesData.companies || companiesData.data || [];
      if (companies.length > 0) {
        firstCompanyId = companies[0].id;
      }
    }
  }

  // Get ICP ID if not found from runs
  if (!icpId) {
    const icpResp = await page.request.get(`${API}/icp`, { headers });
    if (icpResp.ok()) {
      const icpData = await icpResp.json();
      const icps = Array.isArray(icpData) ? icpData : icpData.data || [];
      if (icps.length > 0) {
        icpId = icps[0].id;
      }
    }
  }

  return { completedRunId, firstCompanyId, icpId };
}

// ─── PUBLIC PAGES ──────────────────────────────────────────────────────────

test.describe('Public pages', () => {
  test('01 - Welcome page', async ({ page }) => {
    await page.goto('/welcome');
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(1000);
    await screenshot(page, '01-welcome.png');
  });
});

// ─── USER VIEW (regular user auth) ────────────────────────────────────────

test.describe('User view', () => {
  test.use({ storageState: 'e2e/.auth/user.json' });

  let completedRunId: string;
  let firstCompanyId: string;
  let icpId: string;

  test.beforeAll(async ({ browser }) => {
    const context = await browser.newContext({
      storageState: 'e2e/.auth/user.json',
    });
    const page = await context.newPage();

    const ids = await fetchSeededIds(page, 'sarah.patel@gadgeon.com');
    completedRunId = ids.completedRunId || '';
    firstCompanyId = ids.firstCompanyId || '';
    icpId = ids.icpId || '';

    console.log('User view IDs:', { completedRunId, firstCompanyId, icpId });
    await context.close();
  });

  test('02 - Dashboard (user)', async ({ page }) => {
    await page.goto('/dashboard');
    await waitForPageReady(page);
    await screenshot(page, '02-dashboard-user.png');
  });

  test('03 - ICP list', async ({ page }) => {
    await page.goto('/icp');
    await waitForPageReady(page);
    await screenshot(page, '03-icp-list.png');
  });

  test('04 - ICP clone menu', async ({ page }) => {
    await page.goto('/icp');
    await waitForPageReady(page);

    // Click the first card's menu toggle (⋯)
    const menuToggle = page.locator('.menu-toggle').first();
    if (await menuToggle.isVisible()) {
      await menuToggle.click();
      await page.waitForTimeout(500);
    }
    await screenshot(page, '04-icp-clone-menu.png');
  });

  test('05 - ICP wizard step 1 (Firmographics)', async ({ page }) => {
    test.skip(!icpId, 'No ICP found');
    await page.goto(`/icp/${icpId}/edit`);
    await waitForPageReady(page);
    await screenshot(page, '05-icp-step1-firmographics.png');
  });

  test('06 - ICP wizard step 2 (Capability)', async ({ page }) => {
    test.skip(!icpId, 'No ICP found');
    await page.goto(`/icp/${icpId}/edit`);
    await waitForPageReady(page);

    const step2 = page.locator('.builder-step-label', { hasText: 'Capability' });
    if (await step2.isVisible()) await step2.click();
    await page.waitForTimeout(500);
    await screenshot(page, '06-icp-step2-capability.png');
  });

  test('07 - ICP wizard step 3 (Urgency)', async ({ page }) => {
    test.skip(!icpId, 'No ICP found');
    await page.goto(`/icp/${icpId}/edit`);
    await waitForPageReady(page);

    const step3 = page.locator('.builder-step-label', { hasText: 'Urgency' });
    if (await step3.isVisible()) await step3.click();
    await page.waitForTimeout(500);
    await screenshot(page, '07-icp-step3-urgency.png');
  });

  test('08 - ICP wizard step 4 (Budget)', async ({ page }) => {
    test.skip(!icpId, 'No ICP found');
    await page.goto(`/icp/${icpId}/edit`);
    await waitForPageReady(page);

    const step4 = page.locator('.builder-step-label', { hasText: 'Budget' });
    if (await step4.isVisible()) await step4.click();
    await page.waitForTimeout(500);
    await screenshot(page, '08-icp-step4-budget.png');
  });

  test('09 - ICP wizard step 5 (Authority)', async ({ page }) => {
    test.skip(!icpId, 'No ICP found');
    await page.goto(`/icp/${icpId}/edit`);
    await waitForPageReady(page);

    const step5 = page.locator('.builder-step-label', { hasText: 'Authority' });
    if (await step5.isVisible()) await step5.click();
    await page.waitForTimeout(500);
    await screenshot(page, '09-icp-step5-authority.png');
  });

  test('10 - ICP wizard step 6 (Review)', async ({ page }) => {
    test.skip(!icpId, 'No ICP found');
    await page.goto(`/icp/${icpId}/edit`);
    await waitForPageReady(page);

    const step6 = page.locator('.builder-step-label', { hasText: 'Review' });
    if (await step6.isVisible()) await step6.click();
    await page.waitForTimeout(500);
    await screenshot(page, '10-icp-step6-review.png');
  });

  test('11 - Leads: Companies tab', async ({ page }) => {
    test.skip(!completedRunId, 'No completed run found');
    await page.goto(`/leads/${completedRunId}`);
    await waitForPageReady(page);
    await screenshot(page, '11-leads-companies.png');
  });

  test('12 - Leads: Pipeline Funnel tab', async ({ page }) => {
    test.skip(!completedRunId, 'No completed run found');
    await page.goto(`/leads/${completedRunId}`);
    await waitForPageReady(page);

    const funnelTab = page.locator('.tab', { hasText: 'Pipeline Funnel' });
    if (await funnelTab.isVisible()) await funnelTab.click();
    await page.waitForTimeout(1000);
    await screenshot(page, '12-leads-funnel.png');
  });

  test('13 - Leads: Funnel expanded', async ({ page }) => {
    test.skip(!completedRunId, 'No completed run found');
    await page.goto(`/leads/${completedRunId}`);
    await waitForPageReady(page);

    const funnelTab = page.locator('.tab', { hasText: 'Pipeline Funnel' });
    if (await funnelTab.isVisible()) await funnelTab.click();
    await page.waitForTimeout(1000);

    // Click the first expandable stage row
    const stageRow = page.locator('.funnel-stage-row, .stage-row, tr').first();
    if (await stageRow.isVisible()) await stageRow.click();
    await page.waitForTimeout(500);
    await screenshot(page, '13-leads-funnel-expanded.png');
  });

  test('14 - Leads: Search Criteria tab', async ({ page }) => {
    test.skip(!completedRunId, 'No completed run found');
    await page.goto(`/leads/${completedRunId}`);
    await waitForPageReady(page);

    const criteriaTab = page.locator('.tab', { hasText: 'Search Criteria' });
    if (await criteriaTab.isVisible()) await criteriaTab.click();
    await page.waitForTimeout(1000);
    await screenshot(page, '14-leads-criteria.png');
  });

  test('15 - Leads: Search Summary tab', async ({ page }) => {
    test.skip(!completedRunId, 'No completed run found');
    await page.goto(`/leads/${completedRunId}`);
    await waitForPageReady(page);

    const summaryTab = page.locator('.tab', { hasText: 'Search Summary' });
    if (await summaryTab.isVisible()) await summaryTab.click();
    await page.waitForTimeout(1000);
    await screenshot(page, '15-leads-summary.png');
  });

  test('16 - Company detail: Overview', async ({ page }) => {
    test.skip(!completedRunId || !firstCompanyId, 'No company found');
    await page.goto(`/leads/${completedRunId}/company/${firstCompanyId}`);
    await waitForPageReady(page);
    await screenshot(page, '16-company-overview.png');
  });

  test('17 - Company detail: Contacts tab', async ({ page }) => {
    test.skip(!completedRunId || !firstCompanyId, 'No company found');
    await page.goto(`/leads/${completedRunId}/company/${firstCompanyId}`);
    await waitForPageReady(page);

    const contactsTab = page.locator('.tab', { hasText: /^Contacts/ });
    if (await contactsTab.isVisible()) await contactsTab.click();
    await page.waitForTimeout(500);
    await screenshot(page, '17-company-contacts.png');
  });

  test('18 - Company detail: Budget Signals tab', async ({ page }) => {
    test.skip(!completedRunId || !firstCompanyId, 'No company found');
    await page.goto(`/leads/${completedRunId}/company/${firstCompanyId}`);
    await waitForPageReady(page);

    const budgetTab = page.locator('.tab', { hasText: 'Budget Signals' });
    if (await budgetTab.isVisible()) await budgetTab.click();
    await page.waitForTimeout(500);
    await screenshot(page, '18-company-budget.png');
  });

  test('19 - Company detail: Urgency Signals tab', async ({ page }) => {
    test.skip(!completedRunId || !firstCompanyId, 'No company found');
    await page.goto(`/leads/${completedRunId}/company/${firstCompanyId}`);
    await waitForPageReady(page);

    const urgencyTab = page.locator('.tab', { hasText: 'Urgency Signals' });
    if (await urgencyTab.isVisible()) await urgencyTab.click();
    await page.waitForTimeout(500);
    await screenshot(page, '19-company-urgency.png');
  });

  test('20 - Company detail: Discover Signals dropdown', async ({ page }) => {
    test.skip(!completedRunId || !firstCompanyId, 'No company found');
    await page.goto(`/leads/${completedRunId}/company/${firstCompanyId}`);
    await waitForPageReady(page);

    // Look for the "Discover Signals" or "On-Demand Discovery" button
    const discoverBtn = page.locator('button', { hasText: /Discover/ }).first();
    if (await discoverBtn.isVisible()) {
      await discoverBtn.click();
      await page.waitForTimeout(500);
    }
    await screenshot(page, '20-company-rediscover.png');
  });

  test('21 - All Leads page', async ({ page }) => {
    await page.goto('/all-leads');
    await waitForPageReady(page);
    await screenshot(page, '21-all-leads.png');
  });

  test('22 - All Leads with filters', async ({ page }) => {
    await page.goto('/all-leads');
    await waitForPageReady(page);

    // Apply industry filter
    const industrySelect = page.locator('.ant-select', { has: page.locator('[title="Industry"], [aria-label="Industry"]') }).first();
    if (await industrySelect.isVisible()) {
      await industrySelect.click();
      await page.waitForTimeout(300);
      // Select first option
      const firstOption = page.locator('.ant-select-item-option').first();
      if (await firstOption.isVisible()) await firstOption.click();
      await page.waitForTimeout(300);
    } else {
      // Try placeholder-based selection
      const industryPlaceholder = page.getByPlaceholder('Industry').first();
      if (await industryPlaceholder.isVisible()) {
        await industryPlaceholder.click();
        await page.waitForTimeout(300);
        const option = page.locator('.ant-select-item-option').first();
        if (await option.isVisible()) await option.click();
      }
    }

    await page.waitForTimeout(500);
    // Click away to close any dropdown
    await page.locator('h1').first().click();
    await page.waitForTimeout(500);
    await screenshot(page, '22-all-leads-filtered.png');
  });

  test('23 - CoPilot panel', async ({ page }) => {
    await page.goto('/dashboard');
    await waitForPageReady(page);

    // Click the FAB to open the co-pilot panel
    const fab = page.locator('.copilot-fab');
    if (await fab.isVisible()) {
      await fab.click();
      await page.waitForTimeout(1000);
    }
    await screenshot(page, '23-copilot-panel.png');
  });
});

// ─── ADMIN VIEW (super_admin auth) ────────────────────────────────────────

test.describe('Admin view', () => {
  test.use({ storageState: 'e2e/.auth/admin.json' });

  let completedRunId: string;

  test.beforeAll(async ({ browser }) => {
    const context = await browser.newContext({
      storageState: 'e2e/.auth/admin.json',
    });
    const page = await context.newPage();

    const ids = await fetchSeededIds(page, 'test@gadgeon.com');
    completedRunId = ids.completedRunId || '';

    console.log('Admin view IDs:', { completedRunId });
    await context.close();
  });

  test('24 - Dashboard (admin) - Users tab', async ({ page }) => {
    await page.goto('/dashboard');
    await waitForPageReady(page);

    // The admin panel should be visible; click Users tab
    const usersTab = page.locator('.tab', { hasText: 'Users' });
    if (await usersTab.isVisible()) await usersTab.click();
    await page.waitForTimeout(500);
    await screenshot(page, '24-dashboard-admin.png');
  });

  test('25 - Dashboard (admin) - Searches tab', async ({ page }) => {
    await page.goto('/dashboard');
    await waitForPageReady(page);

    const searchesTab = page.locator('.tab', { hasText: 'Searches' });
    if (await searchesTab.isVisible()) await searchesTab.click();
    await page.waitForTimeout(500);
    await screenshot(page, '25-dashboard-admin-searches.png');
  });

  test('26 - Tools: Registry tab', async ({ page }) => {
    await page.goto('/tools');
    await waitForPageReady(page);
    await screenshot(page, '26-tools-registry.png');
  });

  test('27 - Tools: Effectiveness tab', async ({ page }) => {
    await page.goto('/tools');
    await waitForPageReady(page);

    const effectivenessTab = page.locator('.tab', { hasText: /Effectiveness/ });
    if (await effectivenessTab.isVisible()) await effectivenessTab.click();
    await page.waitForTimeout(1000);
    await screenshot(page, '27-tools-effectiveness.png');
  });

  test('28 - User Management', async ({ page }) => {
    await page.goto('/admin/users');
    await waitForPageReady(page);
    await screenshot(page, '28-user-management.png');
  });

  test('29 - User Management: Invite modal', async ({ page }) => {
    await page.goto('/admin/users');
    await waitForPageReady(page);

    const inviteBtn = page.locator('button', { hasText: /Invite/ });
    if (await inviteBtn.isVisible()) {
      await inviteBtn.click();
      await page.waitForTimeout(500);
    }
    await screenshot(page, '29-user-invite-modal.png');
  });

  test('30 - Pipeline: Completed run', async ({ page }) => {
    test.skip(!completedRunId, 'No completed run found');
    await page.goto(`/pipeline/${completedRunId}`);
    await waitForPageReady(page);
    await screenshot(page, '30-pipeline-completed.png');
  });
});
