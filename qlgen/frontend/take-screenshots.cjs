const { chromium } = require('playwright');
const path = require('path');

const SCREENSHOTS_DIR = path.join(__dirname, 'screenshots');
const BASE_URL = 'http://localhost:3000';

const ACCESS_TOKEN = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI1MGRkODYyNC05NmJiLTQ1ZGYtODkxOS1hOTJhZDU3ZWY4MDkiLCJlbWFpbCI6InNyZWVqaXRoLmthbGFwdXJha2thbEBnYWRnZW9uLmNvbSIsInJvbGUiOiJzdXBlcl9hZG1pbiIsImV4cCI6MTc3NTUzODA0OSwiaWF0IjoxNzc1NDUxNjQ5fQ.vWvXl5rFK_pge6JkIgN0oVTDF8NP21AKgdyL8-EYdv8';
const REFRESH_TOKEN = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI1MGRkODYyNC05NmJiLTQ1ZGYtODkxOS1hOTJhZDU3ZWY4MDkiLCJ0eXBlIjoicmVmcmVzaCIsImV4cCI6MTc3NjA1NjQ0OSwiaWF0IjoxNzc1NDUxNjQ5fQ.2jGiu_sGASqAYErRczja8Um09REcMoKL_x9JHxQ14Ug';

async function main() {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
    deviceScaleFactor: 2,
  });

  // Set refresh token cookie
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

  // Helper to take screenshot
  async function screenshot(name, opts = {}) {
    const filePath = path.join(SCREENSHOTS_DIR, `${name}.png`);
    await page.screenshot({ path: filePath, fullPage: opts.fullPage || false });
    console.log(`  ✓ ${name}.png`);
    return filePath;
  }

  // Helper to wait for page load
  async function waitForLoad(timeout = 5000) {
    await page.waitForLoadState('networkidle', { timeout }).catch(() => {});
    await page.waitForTimeout(1000);
  }

  try {
    // 1. Welcome Page (unauthenticated)
    console.log('Taking screenshots...\n');

    // Go to welcome first to trigger auth
    await page.goto(`${BASE_URL}/welcome`);
    await waitForLoad();
    // After refresh token sets auth, let it settle
    await page.waitForTimeout(2000);

    // Check if authenticated
    const isAuth = await page.evaluate(() => {
      return document.querySelector('.gnav-links') !== null;
    });
    console.log('Authenticated:', isAuth);

    // 1. Welcome page (authenticated)
    await page.goto(`${BASE_URL}/welcome`);
    await waitForLoad();
    await screenshot('01-welcome-page');

    // 2. Dashboard
    await page.goto(`${BASE_URL}/dashboard`);
    await waitForLoad(10000);
    await page.waitForTimeout(2000);
    await screenshot('02-dashboard');
    await screenshot('02-dashboard-full', { fullPage: true });

    // 3. ICP Config - New (Step 1: Discovery Source)
    await page.goto(`${BASE_URL}/icp/new`);
    await waitForLoad();
    await page.waitForTimeout(1500);
    await screenshot('03-icp-step1-discovery-source');

    // 3b. Select "Sales Navigator Only" mode
    const salesNavRadio = await page.$('input[value="sales_navigator_only"]');
    if (salesNavRadio) {
      await salesNavRadio.click();
      await page.waitForTimeout(500);
    } else {
      // Try clicking the radio label
      const radioLabels = await page.$$('.ant-radio-wrapper');
      for (const label of radioLabels) {
        const text = await label.textContent();
        if (text && text.includes('Sales Navigator Only')) {
          await label.click();
          await page.waitForTimeout(500);
          break;
        }
      }
    }
    await screenshot('03b-icp-step1-sales-nav-selected');

    // 3c. Enter a Sales Nav URL
    const urlInput = await page.$('input[placeholder*="Sales Navigator"]') || await page.$('input[placeholder*="sales"]') || await page.$('textarea[placeholder*="Sales Navigator"]');
    if (urlInput) {
      await urlInput.fill('https://www.linkedin.com/sales/search/company?query=(filters%3AList((type%3AINDUSTRY%2Cvalues%3AList((id%3A43%2Ctext%3AFinancial%20Services)%2C(id%3A41%2Ctext%3ABanking)))%2C(type%3ACOMPANY_HEADCOUNT%2Cvalues%3AList((id%3AC%2Ctext%3A51-200)%2C(id%3AD%2Ctext%3A201-500)))%2C(type%3AREGION%2Cvalues%3AList((id%3A102299470%2Ctext%3AUnited%20Kingdom)%2C(id%3A101165590%2Ctext%3AUnited%20Kingdom)))))');
      await page.waitForTimeout(1500);
      await screenshot('03c-icp-step1-url-parsed');
    }

    // Click Next to go to Step 2: Firmographics
    const nextBtns = await page.$$('button');
    for (const btn of nextBtns) {
      const text = await btn.textContent();
      if (text && text.includes('Next')) {
        await btn.click();
        break;
      }
    }
    await page.waitForTimeout(800);
    await screenshot('04-icp-step2-firmographics');

    // Continue to Step 3: Capability
    for (const btn of await page.$$('button')) {
      const text = await btn.textContent();
      if (text && text.includes('Next')) { await btn.click(); break; }
    }
    await page.waitForTimeout(800);
    await screenshot('05-icp-step3-capability');

    // Step 4: Urgency
    for (const btn of await page.$$('button')) {
      const text = await btn.textContent();
      if (text && text.includes('Next')) { await btn.click(); break; }
    }
    await page.waitForTimeout(800);
    await screenshot('06-icp-step4-urgency');

    // Step 5: Budget
    for (const btn of await page.$$('button')) {
      const text = await btn.textContent();
      if (text && text.includes('Next')) { await btn.click(); break; }
    }
    await page.waitForTimeout(800);
    await screenshot('07-icp-step5-budget');

    // Step 6: Authority
    for (const btn of await page.$$('button')) {
      const text = await btn.textContent();
      if (text && text.includes('Next')) { await btn.click(); break; }
    }
    await page.waitForTimeout(800);
    await screenshot('08-icp-step6-authority');

    // Step 7: Review
    for (const btn of await page.$$('button')) {
      const text = await btn.textContent();
      if (text && text.includes('Next')) { await btn.click(); break; }
    }
    await page.waitForTimeout(800);
    await screenshot('09-icp-step7-review');

    // 4. Saved ICPs page
    await page.goto(`${BASE_URL}/icp`);
    await waitForLoad();
    await page.waitForTimeout(1500);
    await screenshot('10-saved-icps');

    // 5. Find a completed pipeline run
    await page.goto(`${BASE_URL}/dashboard`);
    await waitForLoad(10000);
    await page.waitForTimeout(2000);

    // Try to find a completed run card and click "View Results"
    let completedRunId = null;
    try {
      const viewResultsLinks = await page.$$('text=View Results');
      if (viewResultsLinks.length > 0) {
        const href = await viewResultsLinks[0].getAttribute('href');
        if (href) {
          completedRunId = href.split('/').pop();
        }
        await viewResultsLinks[0].click();
        await waitForLoad(10000);
        await page.waitForTimeout(2000);
      }
    } catch (e) {}

    // Try to get a run ID from the API directly
    if (!completedRunId) {
      const response = await page.evaluate(async (token) => {
        const resp = await fetch('/api/v1/pipeline/history', {
          headers: { 'Authorization': `Bearer ${token}` }
        });
        const data = await resp.json();
        return data;
      }, ACCESS_TOKEN);

      if (response && response.length > 0) {
        const completedRun = response.find(r => r.status === 'completed') || response[0];
        completedRunId = completedRun.id;
      }
    }

    if (completedRunId) {
      // Pipeline progress page
      await page.goto(`${BASE_URL}/pipeline/${completedRunId}`);
      await waitForLoad(10000);
      await page.waitForTimeout(2000);
      await screenshot('11-pipeline-progress');

      // Leads page
      await page.goto(`${BASE_URL}/leads/${completedRunId}`);
      await waitForLoad(10000);
      await page.waitForTimeout(3000);
      await screenshot('12-leads-companies', { fullPage: false });

      // Click on Pipeline Funnel tab if exists
      const tabs = await page.$$('.ant-tabs-tab');
      for (const tab of tabs) {
        const text = await tab.textContent();
        if (text && text.includes('Pipeline Funnel')) {
          await tab.click();
          await page.waitForTimeout(1500);
          await screenshot('13-leads-funnel');
          break;
        }
      }

      // Click on Search Criteria tab
      for (const tab of await page.$$('.ant-tabs-tab')) {
        const text = await tab.textContent();
        if (text && text.includes('Search Criteria')) {
          await tab.click();
          await page.waitForTimeout(1000);
          await screenshot('14-leads-criteria');
          break;
        }
      }

      // Click on Search Summary tab
      for (const tab of await page.$$('.ant-tabs-tab')) {
        const text = await tab.textContent();
        if (text && text.includes('Search Summary') || text && text.includes('Tool')) {
          await tab.click();
          await page.waitForTimeout(1000);
          await screenshot('15-leads-summary');
          break;
        }
      }

      // Click first company for Company Detail
      const companyRows = await page.$$('table tbody tr');
      // First go back to Companies tab
      for (const tab of await page.$$('.ant-tabs-tab')) {
        const text = await tab.textContent();
        if (text && text.includes('Companies')) {
          await tab.click();
          await page.waitForTimeout(1500);
          break;
        }
      }

      const rows = await page.$$('table tbody tr');
      if (rows.length > 0) {
        // Find a clickable company name
        const firstLink = await page.$('table tbody tr td a');
        if (firstLink) {
          await firstLink.click();
          await waitForLoad(10000);
          await page.waitForTimeout(2000);
          await screenshot('16-company-detail', { fullPage: false });
          await screenshot('16b-company-detail-full', { fullPage: true });
        }
      }
    }

    // All Leads page
    await page.goto(`${BASE_URL}/all-leads`);
    await waitForLoad(10000);
    await page.waitForTimeout(2000);
    await screenshot('17-all-leads');

    // Tools page (admin)
    await page.goto(`${BASE_URL}/tools`);
    await waitForLoad(10000);
    await page.waitForTimeout(2000);
    await screenshot('18-tools-registry');
    await screenshot('18b-tools-registry-full', { fullPage: true });

    // Check if there's a Tool Effectiveness tab
    for (const tab of await page.$$('.ant-tabs-tab')) {
      const text = await tab.textContent();
      if (text && text.includes('Effectiveness')) {
        await tab.click();
        await page.waitForTimeout(2000);
        await screenshot('19-tools-effectiveness');
        await screenshot('19b-tools-effectiveness-full', { fullPage: true });
        break;
      }
    }

    // Users page (admin)
    await page.goto(`${BASE_URL}/admin/users`);
    await waitForLoad(10000);
    await page.waitForTimeout(2000);
    await screenshot('20-users-page');

    // Feedback page (admin)
    await page.goto(`${BASE_URL}/admin/feedback`);
    await waitForLoad(10000);
    await page.waitForTimeout(2000);
    await screenshot('21-feedback-page');

    // Help menu - click the ? icon to show the popover
    await page.goto(`${BASE_URL}/dashboard`);
    await waitForLoad(10000);
    await page.waitForTimeout(2000);
    const helpIcon = await page.$('.anticon-question-circle');
    if (helpIcon) {
      await helpIcon.click();
      await page.waitForTimeout(800);
      await screenshot('22-help-menu');
    }

    // Co-pilot - click the floating action button
    const copilotBtn = await page.$('.copilot-fab') || await page.$('[class*="copilot"]') || await page.$('button[class*="float"]');
    if (copilotBtn) {
      await copilotBtn.click();
      await page.waitForTimeout(1500);
      await screenshot('23-copilot-panel');
    }

    // Go back to ICP new to capture the qlgen_only mode (default)
    await page.goto(`${BASE_URL}/icp/new`);
    await waitForLoad();
    await page.waitForTimeout(1500);
    await screenshot('03a-icp-step1-qlgen-mode');

    console.log('\n✅ All screenshots taken!');
  } catch (error) {
    console.error('Error:', error.message);
  } finally {
    await browser.close();
  }
}

main();
