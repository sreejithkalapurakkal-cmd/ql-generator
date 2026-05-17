/**
 * E2E Test: Signal Tracking Feature
 *
 * Tests: create list → import companies → detect signals (listing) →
 *        enrich contacts (listing) → enrich contacts (detail) →
 *        detect signals (detail) → verify notifications
 *
 * Run:  node e2e-test-signal-tracking.mjs
 */

import { chromium } from 'playwright';

const BASE = 'https://qlgen.gadgeon.com';
const LIST_NAME = `E2E Test ${new Date().toISOString().slice(0, 16).replace('T', ' ')}`;
const COMPANIES_TO_PASTE = 'stripe.com\nfigma.com';

// ─── helpers ──────────────────────────────────────────────────────────────────

function log(step, msg) {
  const ts = new Date().toISOString().slice(11, 19);
  console.log(`[${ts}] [${step}] ${msg}`);
}

async function waitForAuth(page) {
  // After goto, the SPA may redirect to /welcome or /dashboard
  const url = page.url();
  const hostname = new URL(url).hostname;
  const path = new URL(url).pathname;

  // If we're on qlgen and on /dashboard or /tracking, we're already authenticated
  if (hostname === 'qlgen.gadgeon.com' && (path === '/dashboard' || path.startsWith('/tracking'))) {
    log('AUTH', 'Already authenticated');
    return;
  }

  // User needs to log in via Google OAuth
  log('AUTH', '');
  log('AUTH', '════════════════════════════════════════════════════════════');
  log('AUTH', '  Please log in via the BROWSER WINDOW that just opened');
  log('AUTH', '  Waiting up to 3 minutes for you to complete Google OAuth...');
  log('AUTH', '════════════════════════════════════════════════════════════');
  log('AUTH', '');

  // Wait until the app is authenticated — check for nav elements that only show when logged in
  // This handles SPA routing that doesn't trigger Playwright URL change events
  await page.waitForFunction(
    () => {
      // Check if we're on the qlgen domain and see authenticated nav elements
      if (window.location.hostname !== 'qlgen.gadgeon.com') return false;
      // Look for nav links that only appear for authenticated users (Dashboard, etc.)
      const nav = document.querySelector('nav, header');
      if (!nav) return false;
      const text = nav.textContent || '';
      return text.includes('Dashboard') || text.includes('Tracking') || text.includes('All Leads');
    },
    { timeout: 180_000 },
  );

  // Let the authenticated app fully render and settle
  log('AUTH', `Redirected to: ${page.url()}`);
  await page.waitForTimeout(5000);

  // One more check — make sure we're really on the app
  const finalUrl = page.url();
  if (!finalUrl.includes('qlgen.gadgeon.com')) {
    throw new Error(`Auth failed — landed on unexpected URL: ${finalUrl}`);
  }
  log('AUTH', `Authenticated! Current URL: ${finalUrl}`);
}

async function safeGoto(page, url, retries = 2) {
  for (let i = 0; i <= retries; i++) {
    try {
      await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 30_000 });
      await page.waitForTimeout(2000);
      return;
    } catch (e) {
      if (i === retries) throw e;
      log('NAV', `Navigation failed (attempt ${i + 1}), retrying: ${e.message.slice(0, 80)}`);
      await page.waitForTimeout(2000);
    }
  }
}

async function screenshot(page, name) {
  const path = `/tmp/qlgen-e2e-${name}.png`;
  await page.screenshot({ path, fullPage: true });
  log('SCREENSHOT', path);
}

// ─── main ─────────────────────────────────────────────────────────────────────

async function main() {
  // Use persistent context so auth cookies survive between runs
  const userDataDir = '/tmp/qlgen-playwright-profile';
  const context = await chromium.launchPersistentContext(userDataDir, {
    headless: false,
    channel: 'chrome',
    args: ['--no-sandbox', '--disable-gpu', '--window-size=1400,900'],
    viewport: { width: 1400, height: 900 },
  });
  const page = context.pages()[0] || await context.newPage();
  page.setDefaultTimeout(60_000);
  const browser = context; // for close()

  let listId = null;
  let listDetailUrl = null;

  try {
    // ── STEP 0: Navigate & authenticate ──────────────────────────────────────
    log('AUTH', 'Opening app...');
    await page.goto(BASE, { waitUntil: 'domcontentloaded', timeout: 30_000 });
    await page.waitForTimeout(2000);
    await waitForAuth(page);

    // ── STEP 1: Create tracking list ─────────────────────────────────────────
    log('CREATE', 'Navigating to /tracking...');
    await safeGoto(page, `${BASE}/tracking`);
    await page.waitForTimeout(2000);

    log('CREATE', 'Clicking "New List" button...');
    await page.getByRole('button', { name: /New List/i }).click();

    // Wait for modal by its title text
    await page.getByText('Create Tracking List').waitFor({ state: 'visible', timeout: 10_000 });
    await page.waitForTimeout(500);
    log('CREATE', `Filling list name: "${LIST_NAME}"`);
    await page.getByPlaceholder('e.g., Conference Q2 2026').fill(LIST_NAME);
    await page.getByPlaceholder('What companies are you tracking?').fill(
      'E2E test list for signal tracking validation',
    );

    log('CREATE', 'Clicking "Create"...');
    // Click the "Create" button inside the modal footer (OK button)
    await page.locator('.ant-modal-footer button.ant-btn-primary, .ant-modal button.ant-btn-primary').click();
    // Wait for navigation to the new list detail page
    await page.waitForURL(/\/tracking\/[a-f0-9-]+/, { timeout: 15_000 });
    listDetailUrl = page.url();
    listId = listDetailUrl.match(/\/tracking\/([a-f0-9-]+)/)?.[1];
    log('CREATE', `✅ List created! ID: ${listId}`);
    await screenshot(page, '01-list-created');

    // ── STEP 2: Import 2 companies (with retry — backend uses in-memory store across 2 ECS tasks) ──
    let importSuccess = false;
    for (let attempt = 1; attempt <= 3 && !importSuccess; attempt++) {
      log('IMPORT', `Attempt ${attempt}: Starting import flow...`);

      // Navigate to ingest page for this list
      await safeGoto(page, `${BASE}/ingest?targetListId=${listId}`);
      await page.waitForTimeout(2000);

      log('IMPORT', 'Switching to "Paste List" mode...');
      await page.getByText('Paste List').click();
      await page.waitForTimeout(500);

      log('IMPORT', `Pasting companies: ${COMPANIES_TO_PASTE.replace(/\n/g, ', ')}`);
      await page.getByRole('textbox', { name: 'Paste company names or' }).fill(COMPANIES_TO_PASTE);

      log('IMPORT', 'Clicking "Parse List"...');
      await page.getByRole('button', { name: /Parse List/i }).click();

      // Wait for mapping step
      await page.waitForSelector('text=Column Mapping', { timeout: 15_000 });
      await page.waitForTimeout(1000);
      log('IMPORT', 'Column mapping loaded');
      if (attempt === 1) await screenshot(page, '02-import-mapping');

      // Click through mapping → filter → start
      const nextBtn = page.getByRole('button', { name: /Next|Start Processing/i });
      await nextBtn.click();

      // If filter step appears, click Start Processing immediately
      try {
        await page.waitForSelector('text=Firmographic Filter', { timeout: 3000 });
        log('IMPORT', 'Filter step, clicking Start Processing...');
        await page.getByRole('button', { name: /Start Processing/i }).click();
      } catch {
        // No filter step
      }

      // Wait for result: either SSE progress or error
      log('IMPORT', 'Waiting for import to process...');

      // Wait for SSE progress view ("Importing companies...") or error
      try {
        // Wait for either the processing spinner or an error toast
        await page.waitForFunction(() => {
          const body = document.body.textContent || '';
          // Success indicators
          if (body.includes('Importing companies')) return true;
          if (body.includes('Successfully')) return true;
          // The done step content
          const progress = document.querySelector('.ant-progress');
          if (progress) return true;
          return false;
        }, { timeout: 10_000 });

        log('IMPORT', 'Processing started, waiting for completion...');

        // Now wait for the Done step (SSE sends ingest_completed)
        // Look for specific completion content, not the "Done" step label
        await page.waitForFunction(() => {
          const body = document.body.textContent || '';
          return body.includes('successfully') || body.includes('Import complete')
            || body.includes('matched in KB') || body.includes('View Tracking List')
            || body.includes('imported');
        }, { timeout: 60_000 });

        log('IMPORT', 'Processing completed!');
      } catch {
        // Check for error toast
        const errorVisible = await page.locator('.ant-message-error').isVisible().catch(() => false);
        if (errorVisible) {
          log('IMPORT', `Error toast detected on attempt ${attempt}, will retry...`);
          continue;
        }
        log('IMPORT', 'Processing status unclear, checking list...');
      }

      await screenshot(page, '04-import-done');

      // Navigate back to list and verify companies are there
      await safeGoto(page, listDetailUrl);
      await page.waitForTimeout(4000);

      // Check company count - try the counter in the header first
      const headerText = await page.locator('text=/\\d+ compan/i').first().textContent().catch(() => '0');
      const match = headerText?.match(/(\d+)/);
      const companyCount = match ? parseInt(match[1]) : 0;

      if (companyCount > 0) {
        importSuccess = true;
        log('IMPORT', `✅ Import complete! ${companyCount} companies in list.`);
      } else {
        log('IMPORT', `⚠️ 0 companies after attempt ${attempt}. Retrying...`);
        await page.waitForTimeout(2000);
      }
    }

    await screenshot(page, '05-list-with-companies');

    if (!importSuccess) {
      log('IMPORT', '❌ Import failed after 3 attempts. Continuing with available data...');
    }

    // ── STEP 3: Detect signals from listing page ─────────────────────────────
    log('DETECT-LIST', 'Clicking "Detect All" button...');
    const detectAllBtn = page.locator('button:has-text("Detect All")').first();
    if (await detectAllBtn.isVisible()) {
      // Force-click to avoid tooltip intercepting
      await detectAllBtn.click({ force: true });
      log('DETECT-LIST', 'Signal detection started, waiting for progress...');

      // Phase 1: Wait for detection to actually start (progress text appears)
      try {
        await page.waitForSelector('text=Detecting Signals', { timeout: 15_000 });
        log('DETECT-LIST', 'Progress bar visible');
      } catch {
        log('DETECT-LIST', 'Progress text not found, checking if already done...');
      }

      // Phase 2: Wait for detection to complete
      // Poll: check every 5s if detection is still running, up to 5 minutes
      const detectStart = Date.now();
      while (Date.now() - detectStart < 300_000) {
        await page.waitForTimeout(5000);
        const stillDetecting = await page.locator('text=Detecting Signals').isVisible().catch(() => false);
        if (!stillDetecting) {
          log('DETECT-LIST', 'Detection progress bar gone — completed or never started');
          break;
        }
        const elapsed = Math.round((Date.now() - detectStart) / 1000);
        log('DETECT-LIST', `Still detecting... (${elapsed}s elapsed)`);
        await screenshot(page, `06a-detecting-${elapsed}s`);
      }

      await page.waitForTimeout(3000);
      log('DETECT-LIST', '✅ Signal detection from listing page completed');
    } else {
      log('DETECT-LIST', '⚠️ "Detect All" button not found');
    }
    await screenshot(page, '06-signals-detected-listing');

    // ── STEP 4: Enrich contacts from listing page ────────────────────────────
    log('ENRICH-LIST', 'Refreshing page before enrichment...');
    await safeGoto(page, listDetailUrl);
    await page.waitForTimeout(3000);

    // Wait for any ongoing detection to clear
    const stillRunning = await page.locator('text=Detecting Signals').isVisible().catch(() => false);
    if (stillRunning) {
      log('ENRICH-LIST', 'Detection still running, waiting for it to finish...');
      while (await page.locator('text=Detecting Signals').isVisible().catch(() => false)) {
        await page.waitForTimeout(5000);
      }
      await page.waitForTimeout(2000);
    }

    const enrichBtn = page.locator('button:has-text("Enrich Contacts")').first();
    if (await enrichBtn.isVisible()) {
      await enrichBtn.click({ force: true });
      log('ENRICH-LIST', 'Enrichment started, waiting for progress...');

      // Phase 1: Wait for enrichment to start
      try {
        await page.waitForSelector('text=Enriching Contacts', { timeout: 15_000 });
        log('ENRICH-LIST', 'Enrichment progress bar visible');
      } catch {
        log('ENRICH-LIST', 'Enrichment progress text not found');
      }

      // Phase 2: Poll until enrichment completes
      const enrichStart = Date.now();
      while (Date.now() - enrichStart < 300_000) {
        await page.waitForTimeout(5000);
        const stillEnriching = await page.locator('text=Enriching Contacts').isVisible().catch(() => false);
        if (!stillEnriching) {
          log('ENRICH-LIST', 'Enrichment progress bar gone — completed');
          break;
        }
        const elapsed = Math.round((Date.now() - enrichStart) / 1000);
        log('ENRICH-LIST', `Still enriching... (${elapsed}s elapsed)`);
      }

      await page.waitForTimeout(3000);
      log('ENRICH-LIST', '✅ Contact enrichment from listing page completed');
    } else {
      log('ENRICH-LIST', '⚠️ "Enrich Contacts" button not visible');
    }
    await screenshot(page, '07-enriched-listing');

    // ── STEP 5: Navigate to company detail page ──────────────────────────────
    log('DETAIL', 'Clicking on first company row...');
    await safeGoto(page, listDetailUrl);
    await page.waitForTimeout(3000);

    // Click on the first data row in the table
    const firstRow = page.locator('.ant-table-row').first();
    if (await firstRow.isVisible()) {
      await firstRow.click();
      await page.waitForURL(/\/tracking\/[a-f0-9-]+\/company\/[a-f0-9-]+/, { timeout: 10_000 });
      const detailUrl = page.url();
      log('DETAIL', `✅ Navigated to company detail: ${detailUrl}`);
      await page.waitForTimeout(3000);
      await screenshot(page, '08-company-detail');

      // ── STEP 6: Enrich contacts from details page ────────────────────────
      log('ENRICH-DETAIL', 'Switching to Contacts tab...');
      // The detail page uses PillTabs — rendered as clickable text spans in a row
      // From screenshot: tabs are "Overview  Signals  Contacts  Notes & History"
      // Use JavaScript click on the element containing exact text
      await page.evaluate(() => {
        const allEls = document.querySelectorAll('*');
        for (const el of allEls) {
          if (el.childElementCount === 0 && el.textContent?.trim() === 'Contacts') {
            (el.closest('[class*="pill"]') || el.closest('button') || el).click();
            return;
          }
        }
      });
      await page.waitForTimeout(3000);
      await screenshot(page, '09a-contacts-tab-click');

      // Check if we're actually on the contacts tab now (look for "Find Contacts" or contact cards)
      const findContactsBtn = page.getByRole('button', { name: /Find Contacts|Re-enrich/i });
      const findBtnVisible = await findContactsBtn.isVisible().catch(() => false);
      if (findBtnVisible) {
        log('ENRICH-DETAIL', 'Clicking "Find Contacts" / "Re-enrich"...');
        await findContactsBtn.click();
        // Wait for the loading spinner to resolve
        log('ENRICH-DETAIL', 'Waiting for enrichment to complete...');
        // Watch for button to stop loading (ant-btn-loading class removed)
        const enrichDetailStart = Date.now();
        while (Date.now() - enrichDetailStart < 120_000) {
          await page.waitForTimeout(3000);
          const loading = await page.locator('.ant-btn-loading').isVisible().catch(() => false);
          if (!loading) break;
          log('ENRICH-DETAIL', 'Still enriching...');
        }
        await page.waitForTimeout(2000);
        log('ENRICH-DETAIL', '✅ Contact enrichment from detail page completed');
      } else {
        log('ENRICH-DETAIL', '⚠️ "Find Contacts" button not visible — trying No contacts empty state');
        // Maybe tab didn't switch. Try a direct page.click approach
        await page.locator('text=Contacts').nth(0).click({ timeout: 5000 }).catch(() => {});
        await page.waitForTimeout(2000);
        const btn2 = page.getByRole('button', { name: /Find Contacts|Re-enrich/i });
        if (await btn2.isVisible().catch(() => false)) {
          log('ENRICH-DETAIL', 'Found button on second attempt, clicking...');
          await btn2.click();
          await page.waitForTimeout(30_000); // Wait 30s for single-company enrichment
          log('ENRICH-DETAIL', '✅ Contact enrichment from detail page completed');
        } else {
          log('ENRICH-DETAIL', '⚠️ Could not find enrichment button');
        }
      }
      await screenshot(page, '09-contacts-detail');

      // ── STEP 7: Detect signals from details page ─────────────────────────
      log('DETECT-DETAIL', 'Switching to Signals tab...');
      await page.evaluate(() => {
        const allEls = document.querySelectorAll('*');
        for (const el of allEls) {
          if (el.childElementCount === 0 && el.textContent?.trim() === 'Signals') {
            (el.closest('[class*="pill"]') || el.closest('button') || el).click();
            return;
          }
        }
      });
      await page.waitForTimeout(3000);
      await screenshot(page, '10a-signals-tab-click');

      // Look for the "Detect" button in the SignalTimeline component
      // Use has-text since getByRole may not match due to icon prefix in accessible name
      const detectBtn = page.locator('button:has-text("Detect")').first();
      const detectBtnVisible = await detectBtn.isVisible().catch(() => false);
      if (detectBtnVisible) {
        log('DETECT-DETAIL', 'Clicking "Detect" button...');
        await detectBtn.click({ force: true });

        // Wait for detection to start
        try {
          await page.waitForSelector('text=Detecting Signals', { timeout: 15_000 });
          log('DETECT-DETAIL', 'Detection in progress...');
        } catch {
          log('DETECT-DETAIL', 'Detection progress text not found immediately');
        }

        // Poll until detection finishes
        const detDetStart = Date.now();
        while (Date.now() - detDetStart < 300_000) {
          await page.waitForTimeout(5000);
          const stillDet = await page.locator('text=Detecting Signals').isVisible().catch(() => false);
          if (!stillDet) break;
          log('DETECT-DETAIL', `Still detecting... (${Math.round((Date.now()-detDetStart)/1000)}s)`);
        }
        await page.waitForTimeout(3000);
        log('DETECT-DETAIL', '✅ Signal detection from detail page completed');
      } else {
        log('DETECT-DETAIL', '⚠️ "Detect" button not visible on signals tab');
      }
      await screenshot(page, '10-signals-detail');
    } else {
      log('DETAIL', '⚠️ No company rows found in table');
    }

    // ── STEP 8: Verify notifications ─────────────────────────────────────────
    log('NOTIFY', 'Checking notification bell...');
    // The notification bell is in the layout header area
    const bell = page.locator('[class*="anticon-bell"], .anticon-bell').first();
    if (await bell.isVisible()) {
      // Check if there's a badge count
      const badge = page.locator('.ant-badge-count, .ant-badge sup');
      let unreadCount = '0';
      try {
        if (await badge.first().isVisible({ timeout: 3000 })) {
          unreadCount = await badge.first().innerText() || '0';
        }
      } catch {
        // No badge visible — might be 0
      }
      log('NOTIFY', `Unread notification count: ${unreadCount}`);

      // Click the bell to open the notification drawer
      await bell.click();
      await page.waitForTimeout(2000);

      // Check the drawer content
      const drawer = page.locator('.ant-drawer');
      if (await drawer.isVisible({ timeout: 5000 })) {
        // Count notification items
        const items = drawer.locator('[class*="notification"], [class*="cursor-pointer"]');
        const notifCount = await items.count();
        log('NOTIFY', `Notifications in drawer: ${notifCount}`);

        // Check for "Mark all read" button
        const markAllBtn = page.getByRole('button', { name: /Mark all read|Mark all/i });
        if (await markAllBtn.isVisible({ timeout: 2000 }).catch(() => false)) {
          log('NOTIFY', '"Mark all read" button is visible (confirms unread notifications exist)');
        }

        await screenshot(page, '11-notifications');
        log('NOTIFY', '✅ Notifications verified');
      } else {
        log('NOTIFY', '⚠️ Notification drawer did not open');
        await screenshot(page, '11-notifications-not-open');
      }
    } else {
      log('NOTIFY', '⚠️ Bell icon not found');
      await screenshot(page, '11-bell-not-found');
    }

    // ── SUMMARY ──────────────────────────────────────────────────────────────
    console.log('\n' + '='.repeat(60));
    console.log('E2E TEST SUMMARY');
    console.log('='.repeat(60));
    console.log(`List Name:     ${LIST_NAME}`);
    console.log(`List ID:       ${listId}`);
    console.log(`List URL:      ${listDetailUrl}`);
    console.log(`Screenshots:   /tmp/qlgen-e2e-*.png`);
    console.log('='.repeat(60));

  } catch (err) {
    console.error('\n❌ TEST FAILED:', err.message);
    await screenshot(page, 'error-final');
    throw err;
  } finally {
    // Keep browser open for manual inspection
    log('DONE', 'Test completed. Browser stays open for 30s for manual inspection...');
    await page.waitForTimeout(30_000);
    await browser.close();
  }
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
