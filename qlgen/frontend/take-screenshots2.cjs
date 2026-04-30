const { chromium } = require('playwright');
const path = require('path');

const SCREENSHOTS_DIR = path.join(__dirname, 'screenshots');
const BASE_URL = 'http://localhost:3000';
const RUN_ID = '8ed1f995-6ff7-4568-8d4d-63ce0d69dcb0';
const REFRESH_TOKEN = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI1MGRkODYyNC05NmJiLTQ1ZGYtODkxOS1hOTJhZDU3ZWY4MDkiLCJ0eXBlIjoicmVmcmVzaCIsImV4cCI6MTc3NjA1NjY3MH0.zha9hfxPtV1e25j_O3pCMiqwMAdFmi51t3nWIlDz0zM';

async function main() {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
    deviceScaleFactor: 2,
  });

  await context.addCookies([{
    name: 'refresh_token',
    value: REFRESH_TOKEN,
    domain: 'localhost',
    path: '/',
    httpOnly: true,
    secure: false,
    sameSite: 'Lax',
  }]);

  const page = await context.newPage();

  async function screenshot(name, opts = {}) {
    const filePath = path.join(SCREENSHOTS_DIR, `${name}.png`);
    await page.screenshot({ path: filePath, fullPage: opts.fullPage || false });
    console.log(`  ✓ ${name}.png`);
  }

  async function waitForLoad(timeout = 8000) {
    await page.waitForLoadState('networkidle', { timeout }).catch(() => {});
    await page.waitForTimeout(1500);
  }

  try {
    // Auth
    await page.goto(`${BASE_URL}/welcome`);
    await waitForLoad();
    await page.waitForTimeout(2000);

    // Pipeline page
    await page.goto(`${BASE_URL}/pipeline/${RUN_ID}`);
    await waitForLoad(15000);
    await page.waitForTimeout(3000);
    await screenshot('11-pipeline-progress');

    // Leads page - Companies tab
    await page.goto(`${BASE_URL}/leads/${RUN_ID}`);
    await waitForLoad(15000);
    await page.waitForTimeout(3000);
    await screenshot('12-leads-companies');

    // Pipeline Funnel tab
    for (const tab of await page.$$('.ant-tabs-tab')) {
      const text = await tab.textContent();
      if (text && text.includes('Funnel')) { await tab.click(); await page.waitForTimeout(2000); break; }
    }
    await screenshot('13-leads-funnel');

    // Search Criteria tab
    for (const tab of await page.$$('.ant-tabs-tab')) {
      const text = await tab.textContent();
      if (text && text.includes('Criteria')) { await tab.click(); await page.waitForTimeout(1500); break; }
    }
    await screenshot('14-leads-criteria');

    // Search Summary / Tool Attribution tab
    for (const tab of await page.$$('.ant-tabs-tab')) {
      const text = await tab.textContent();
      if (text && (text.includes('Summary') || text.includes('Tool'))) { await tab.click(); await page.waitForTimeout(1500); break; }
    }
    await screenshot('15-leads-summary');

    // Company detail - go back to companies and click first
    for (const tab of await page.$$('.ant-tabs-tab')) {
      const text = await tab.textContent();
      if (text && text.includes('Companies')) { await tab.click(); await page.waitForTimeout(2000); break; }
    }

    // Find company link
    const links = await page.$$('a[href*="company"]');
    if (links.length > 0) {
      await links[0].click();
      await waitForLoad(10000);
      await page.waitForTimeout(2000);
      await screenshot('16-company-detail');
      await screenshot('16b-company-detail-full', { fullPage: true });
    } else {
      // Try clicking table row
      const rows = await page.$$('table tbody tr');
      if (rows.length > 0) {
        await rows[0].click();
        await waitForLoad(10000);
        await page.waitForTimeout(2000);
        await screenshot('16-company-detail');
      }
    }

    console.log('\n✅ Pipeline/leads screenshots done!');
  } catch (error) {
    console.error('Error:', error.message);
  } finally {
    await browser.close();
  }
}

main();
