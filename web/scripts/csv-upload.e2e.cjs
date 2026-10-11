/* Run only against an empty disposable server seeded with the official persisted Sevaro references.
 * Requires an installed Playwright and Chrome; see docs/CSV-Ingestion-Audit.md.
 */
const { chromium } = require(process.env.CC_PLAYWRIGHT_MODULE || 'playwright');
const fs = require('node:fs/promises');
const path = require('node:path');
const os = require('node:os');
const { createHash } = require('node:crypto');
const assert = require('node:assert/strict');
const root = path.resolve(__dirname, '../..');
const origin = process.env.CC_E2E_URL;
assert.ok(origin && ['localhost', '127.0.0.1'].includes(new URL(origin).hostname), 'Disposable localhost server required');
assert.ok(process.env.CC_E2E_EMAIL && process.env.CC_E2E_PASSWORD, 'Test account required');
(async () => {
  const browser = await chromium.launch({ channel: 'chrome', headless: true, chromiumSandbox: true });
  const output = await fs.mkdtemp(path.join(os.tmpdir(), 'sevaro-csv-e2e-'));
  try {
    const page = await browser.newPage({ viewport: { width: 1440, height: 1100 } });
    const errors = [];
    page.on('pageerror', e => errors.push(e.message));
    await page.goto(origin + '/#signin');
    await page.getByPlaceholder('name@sevaro.com').fill(process.env.CC_E2E_EMAIL);
    await page.locator('input[type=password]').fill(process.env.CC_E2E_PASSWORD);
    await page.getByRole('button', { name: 'Sign in as Coordinator' }).click();
    await page.getByRole('link', { name: 'Data', exact: true }).click();
    await page.getByRole('heading', { name: 'Upload history', exact: true }).waitFor();
    const session = await page.evaluate(() => JSON.parse(sessionStorage.getItem('cc_session')));
    const headers = { Authorization: 'Bearer ' + session.token };
    const get = async route => {
      const response = await page.request.get(origin + route, { headers });
      assert.equal(response.status(), 200);
      return response.json();
    };
    const refs = await get('/admin/references');
    assert.equal(refs.manifest.fingerprint, '81602969911fe81fc1d5db5a51595fb5124d07ac5f5e97623a21e1232701d72d');
    assert.equal(refs.event_count, 0, 'Refuse to write into an existing event stream');
    assert.equal(refs.operational_data.baseline_source_rows, 288);
    assert.equal(refs.operational_data.baseline_lookup_entries, 1440);
    assert.deepEqual(refs.operational_data.weeks_sampled, [12]);
    for (const h of refs.operational_data.hospitals) assert.deepEqual(h.hours_by_weekday, [24,24,24,24,24,0,0]);
    await page.getByRole('heading', { name: 'Hourly baseline coverage' }).waitFor();
    const initialBatchIds = new Set((await get('/admin/uploads')).items.map(b => b.batch_id));
    const upload = async file => {
      const previous = new Set((await get('/admin/uploads')).items.map(b => b.batch_id));
      const pending = page.waitForResponse(r => r.url().includes('/events/csv') && r.request().method() === 'POST');
      await page.locator('input[type=file]').setInputFiles(file);
      const response = await pending;
      assert.equal(response.status(), 200);
      const batch = (await get('/admin/uploads')).items.find(b => !previous.has(b.batch_id));
      assert.ok(batch, 'The parsed upload must have a saved receipt');
      return batch.report;
    };
    const base = await upload(path.join(root, 'data/event_stream.csv'));
    assert.equal(base.accepted, 1163);
    assert.equal(base.duplicates, 1);
    const before = await get('/snapshot');
    const oldHistories = {};
    for (const c of before.consults) oldHistories[c.consult_id] = await get('/consults/' + c.consult_id);
    const file = path.join(output, 'official-reference-unseen.csv');
    await fs.writeFile(file, '\ufeffevent_id,event_time,ingested_at,consult_id,event_type,physician_id,hospital_id,description\n' +
      'EVT-J001,2026-03-17T18:21:00-04:00,2026-03-17T18:21:02-04:00,CON-J01,consult_received,,SYN-005,Acute stroke consult requested\n' +
      'EVT-J002,2026-03-17T18:21:40-04:00,2026-03-17T18:21:41-04:00,CON-J01,consult_triaged,,SYN-005,Consult triaged\n' +
      'EVT-J001,2026-03-17T18:21:00-04:00,2026-03-17T18:21:02-04:00,CON-J01,consult_received,,SYN-005,Acute stroke consult requested\n' +
      'EVT-J003,2026-03-17T18:30:00-04:00,2026-03-17T18:30:01-04:00,CON-J01,consult_received,,SYN-005,Stroke consult request received\n');
    const report = await upload(file);
    assert.equal(report.accepted, 3);
    assert.equal(report.duplicates, 1);
    assert.equal(report.pending_future, 0);
    const after = await get('/snapshot');
    const currentRefs = await get('/admin/references');
    for (const key of ['dataset', 'reference_revision', 'manifest', 'hospitals', 'physicians', 'operational_data']) assert.deepEqual(currentRefs[key], refs[key]);
    assert.equal(currentRefs.event_count, 1166);
    const consult = after.consults.find(c => c.consult_id === 'CON-J01');
    assert.equal(consult.consult_type, 'Stroke');
    assert.equal(consult.repeat_contacts, 1);
    assert.ok(after.queue.items.some(i => i.severity === 'Critical' && i.where.consult_id === 'CON-J01'));
    assert.equal(after.forecast.surges.find(s => s.hospital_id === 'SYN-005').count, 6);
    for (const [id, old] of Object.entries(oldHistories)) {
      const current = await get('/consults/' + id);
      for (const entry of old.history) assert.ok(current.history.some(e => e.stage === entry.stage && e.at === entry.at));
    }
    await page.getByRole('link', { name: 'Command', exact: true }).click();
    await page.getByRole('heading', { name: 'Attention queue', exact: true }).waitFor();
    assert.equal(after.demand.horizon_end, after.coverage.horizon_end);
    assert.equal(after.demand.horizon_minutes, 90);
    assert.equal(after.demand.items.find(h => h.hospital_id === 'SYN-005').trailing_60m, 6);
    await page.getByRole('heading', { name: 'Demand & hourly baseline' }).scrollIntoViewIfNeeded();
    await page.getByText(/Expected arrivals over the next 90 minutes/).waitFor();
    await page.screenshot({ path: path.join(output, 'baseline-desktop.png') });
    await page.setViewportSize({ width: 390, height: 844 });
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth));
    await page.getByRole('heading', { name: 'Demand & hourly baseline' }).scrollIntoViewIfNeeded();
    await page.screenshot({ path: path.join(output, 'baseline-mobile.png') });
    await page.setViewportSize({ width: 1440, height: 1100 });
    await page.getByRole('link', { name: 'Data', exact: true }).click();
    await page.reload();
    const receipt = page.locator('details').filter({ hasText: 'official-reference-unseen.csv' });
    await receipt.locator('summary').click();
    await receipt.getByRole('button', { name: 'Download report' }).waitFor();
    const downloadPromise = page.waitForEvent('download');
    await receipt.getByRole('button', { name: 'Download report' }).click();
    const downloaded = await downloadPromise;
    const saved = JSON.parse(await fs.readFile(await downloaded.path(), 'utf8'));
    assert.equal(saved.batch_id, report.batch_id);
    assert.equal(saved.filename, 'official-reference-unseen.csv');
    assert.equal(saved.report.row_results.length, 4);
    assert.equal(saved.sha256, createHash('sha256').update(await fs.readFile(file)).digest('hex'));
    const duplicate = await upload(file);
    assert.equal(duplicate.accepted, 0);
    assert.equal(duplicate.duplicates, 4);
    assert.deepEqual((await get('/snapshot')).queue, after.queue);
    const invalidResponse = page.waitForResponse(r => r.url().includes('/events/csv') && r.request().method() === 'POST');
    await page.locator('input[type=file]').setInputFiles({ name: 'invalid-utf8.csv', mimeType: 'text/csv', buffer: Buffer.from([255]) });
    assert.equal((await invalidResponse).status(), 422);
    await page.getByRole('alert').filter({ hasText: 'CSV must use UTF-8 encoding' }).waitFor();
    const bad = path.join(output, 'missing-dependencies.csv');
    await fs.writeFile(bad, 'event_id,event_time,ingested_at,consult_id,event_type,physician_id,hospital_id,description\n' +
      'UNKNOWN,2026-06-17T18:31:00-04:00,2026-06-17T18:31:00-04:00,UNKNOWN-C,consult_received,,UNKNOWN-H,Stroke consult requested\n' +
      'INVALID,2026-06-17T18:31:00-04:00,2026-06-17T18:31:00-04:00,UNKNOWN-C,unsupported_event,,SYN-005,Invalid\n');
    const rejected = await upload(bad);
    assert.equal(rejected.accepted, 0);
    assert.deepEqual(rejected.row_results.map(r => r.status), ['held', 'quarantined']);
    assert.equal((await get('/snapshot')).clock.now, after.clock.now);
    await page.getByText('Unknown hospital UNKNOWN-H in the fixed reference kit', { exact: true }).waitFor();
    await page.getByRole('heading', { name: 'Upload history', exact: true }).scrollIntoViewIfNeeded();
    await page.screenshot({ path: path.join(output, 'uploads-desktop.png') });
    await page.setViewportSize({ width: 390, height: 844 });
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth));
    await page.getByRole('heading', { name: 'Upload history', exact: true }).scrollIntoViewIfNeeded();
    await page.screenshot({ path: path.join(output, 'uploads-mobile.png') });
    assert.deepEqual(errors, []);
    const batches = (await get('/admin/uploads')).items.filter(b => !initialBatchIds.has(b.batch_id));
    assert.equal(batches.length, 4);
    const testPackFile = path.join(root, 'test_data/01_development/live/judge_events.csv');
    let testPack = null;
    if (await fs.access(testPackFile).then(() => true, () => false)) {
      testPack = await upload(testPackFile);
      assert.equal(testPack.accepted, 0);
      assert.equal(testPack.row_results.filter(r => r.status === 'held').length, 125);
      assert.equal((await get('/snapshot')).clock.now, after.clock.now);
      assert.deepEqual((await get('/snapshot')).queue, after.queue);
      const packRefs = await get('/admin/references');
      for (const key of ['dataset', 'reference_revision', 'manifest', 'hospitals', 'physicians', 'event_count']) assert.deepEqual(packRefs[key], currentRefs[key]);
    }
    await fs.writeFile(path.join(output, 'evidence.json'), JSON.stringify({ base, report, duplicate, rejected, testPack, before, after, references: currentRefs, retainedHistories: Object.keys(oldHistories).length, batches: batches.map(b => ({ batch_id: b.batch_id, filename: b.filename })), pageErrors: errors }, null, 2));
    console.log(JSON.stringify({ output, accepted: report.accepted, duplicateRows: report.duplicates, events: currentRefs.event_count, retainedHistories: Object.keys(oldHistories).length, referencesUnchanged: true, downloadedReport: true, historyAfterReload: true, originalByteChecksum: true, invalidEncodingRejected: true, testPackHeld: testPack?.row_results.filter(r => r.status === 'held').length ?? null, mobileNoOverflow: true, pageErrors: errors }, null, 2));
  } finally { await browser.close(); }
})().catch(e => { console.error(e); process.exit(1); });
