/* Run against an empty disposable localhost backend with official references.
 * CC_E2E_URL, CC_E2E_EMAIL, CC_E2E_PASSWORD; optional CC_PLAYWRIGHT_MODULE.
 */
const { chromium } = require(process.env.CC_PLAYWRIGHT_MODULE || 'playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const path = require('node:path');
const os = require('node:os');
const origin = process.env.CC_E2E_URL;
assert.ok(origin && ['localhost', '127.0.0.1'].includes(new URL(origin).hostname), 'Disposable localhost server required');
assert.ok(process.env.CC_E2E_EMAIL && process.env.CC_E2E_PASSWORD, 'Test account required');

(async () => {
  const browser = await chromium.launch({ channel: 'chrome', headless: true, chromiumSandbox: true });
  const output = await fs.mkdtemp(path.join(os.tmpdir(), 'sevaro-upload-summary-'));
  try {
    const page = await browser.newPage({ viewport: { width: 1440, height: 1100 } });
    const errors = [];
    page.on('pageerror', (error) => errors.push(error.message));
    await page.goto(origin + '/#signin');
    await page.getByPlaceholder('name@sevaro.com').fill(process.env.CC_E2E_EMAIL);
    await page.locator('input[type=password]').fill(process.env.CC_E2E_PASSWORD);
    await page.getByRole('button', { name: 'Sign in as Coordinator' }).click();
    await page.getByRole('link', { name: 'Data', exact: true }).click();
    await page.getByRole('heading', { name: 'Upload history', exact: true }).waitFor();
    const session = await page.evaluate(() => JSON.parse(sessionStorage.getItem('cc_session')));
    const headers = { Authorization: 'Bearer ' + session.token };
    const refs = await page.request.get(origin + '/admin/references', { headers });
    assert.equal(refs.status(), 200);
    assert.equal((await refs.json()).event_count, 0, 'Refuse an existing stream');
    const text = 'event_id,event_time,ingested_at,consult_id,event_type,physician_id,hospital_id,description\n' +
      'SUMMARY-1,2026-03-17T18:22:00-04:00,2026-03-17T18:22:01-04:00,SUMMARY-C,consult_received,,SYN-005,Stroke consult request received\n' +
      'SUMMARY-2,2026-03-17T18:23:10-04:00,2026-03-17T18:23:11-04:00,SUMMARY-C,consult_triaged,,SYN-005,Consult triaged\n' +
      'SUMMARY-HOLD,2026-03-17T18:24:00-04:00,2026-03-17T18:24:01-04:00,MISSING-C,consult_triaged,,SYN-005,Consult triaged\n';
    const upload = async () => {
      const response = page.waitForResponse((r) => r.url().includes('/events/csv') && r.request().method() === 'POST');
      await page.locator('input[type=file]').setInputFiles({ name: 'summary-events.csv', mimeType: 'text/csv', buffer: Buffer.from(text) });
      const result = await response;
      assert.equal(result.status(), 200);
      return result.json();
    };
    const result = page.locator('.upload-result');
    assert.equal((await upload()).accepted, 2);
    await result.getByText(/Board captured after this upload at 18:23:10/).waitFor();
    const captured = await result.innerText();
    assert.match(captured, /3 rows processed/);
    assert.match(captured, /Triaged/);
    assert.equal(await result.locator('.delta-tile').first().locator('strong').innerText(), '1');
    await page.getByRole('button', { name: 'Reset to 18:20', exact: true }).click();
    await page.waitForFunction(() => document.querySelector('.big-clock')?.textContent === '18:20:00');
    const current = await page.request.get(origin + '/snapshot', { headers });
    assert.equal((await current.json()).consults.length, 0);
    assert.equal(await result.innerText(), captured, 'Clock rewind must not rewrite upload results');
    for (const [label, viewport] of [['desktop', { width: 1440, height: 1100 }], ['mobile', { width: 390, height: 844 }]]) {
      await page.setViewportSize(viewport);
      await result.scrollIntoViewIfNeeded();
      assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
      await page.screenshot({ path: path.join(output, label + '.png'), fullPage: true });
    }
    const repeated = await upload();
    assert.equal(repeated.duplicates, 3);
    assert.equal(repeated.held_orphans, 1);
    await result.getByText('3 rows processed', { exact: true }).waitFor();
    await result.getByText(/Board captured after this upload at 18:20:00/).waitFor();
    assert.equal(await result.locator('.outcome-legend li').filter({ hasText: 'Held for missing context' }).locator('b').innerText(), '0');

    // A failed post-upload board read must retain the successful receipt and name the failure.
    let failBoard = false;
    await page.route('**/snapshot', (route) => failBoard ? route.abort() : route.continue());
    page.on('response', (response) => {
      if (response.url().includes('/events/csv') && response.status() === 200) failBoard = true;
    });
    await upload();
    await page.getByRole('alert').filter({ hasText: 'Upload saved, but board changes could not be loaded' }).waitFor();
    const receipts = await page.request.get(origin + '/admin/uploads', { headers });
    assert.equal((await receipts.json()).items.length, 3);
    assert.deepEqual(errors, []);
    console.log(JSON.stringify({ output, clockRewindPreservesResult: true, duplicateTotalsExact: true, failedBoardReadPreservesReceipt: true, mobileNoOverflow: true, pageErrors: errors }));
  } finally {
    await browser.close();
  }
})().catch((error) => { console.error(error); process.exit(1); });
