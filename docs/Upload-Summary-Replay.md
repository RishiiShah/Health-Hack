# Upload summary and 18:27 replay — 2026-10-11

The upload result now captures fresh server snapshots before and after an upload.
Polling, clock rewinds and later uploads cannot rewrite that result. The result
names its replay capture time and directs readers to Command for the live board.
A failed post-upload snapshot preserves the successful receipt and explains that
the board comparison could not be loaded. A snapshot older than the upload's
revision is refused for the comparison.

CSV outcome segments count the current receipt's row results. Existing held
events and events released from earlier uploads no longer inflate the current
file's processed-row count. Accepted row results include `pending_future`,
computed by the server against its injected replay clock, so a released future
hold cannot mislabel a current row as waiting. Older receipts and JSON reports
retain their available aggregate fallback.

## Reported replay

Verified with Python 3.14.7 and a disposable localhost PostgreSQL database,
using the unchanged official baseline and the eight unique events from the
reported append. The production database was not used for tests.

- Baseline: 1,163 accepted events, one duplicate, no holds; 18 open consults at
  18:20 Eastern on 2026-03-17.
- Append: all eight unique events accepted, no holds; the last event is 18:26:55.
- At exactly 18:27, paused: 19 open consults. CON-2120 is Triaged and unassigned;
  CON-2105 is assigned to PHY-008 and Provider Contacted.
- CON-2120's queue item is Warning with one failed routing attempt. Its proposed
  action is assignment to PHY-003 when their hospital call ends.
- Re-uploading those eight events yields eight duplicates and the same board.
- Rewinding to 18:20 hides future CON-2120 from the live board as expected.

This append contains one new stroke consult, CON-2120, received at 18:22. The
other affected stroke consult, CON-2105, was received at 18:07:30 in the baseline
(EVT-01142). Two distinct new stroke consults would require a second new
`consult_received` event; one was not present in the reported append.

To repeat the baseline-backed rehearsal, first upload the official
`event_stream.csv`, then the append, and pause at 18:27 using the existing
`POST /admin/clock` with `{"to_start":true,"advance_s":420}`. Resetting only the
clock retains events; starting an empty stream requires loading the baseline
again before uploading excerpts that depend on existing consults.

## Requested production cleanup

The user explicitly authorized permanent removal of all event generations and
upload history, retaining the reference kits. The serving process was reset
through Render's API before database deletion, then reset again afterward.
The deletion transaction locked stream metadata and refused to proceed if a new
active event had arrived. Reference metadata was compared byte-for-byte before
and after deletion; API manifests and kit inventories also matched afterward.

Removed 7,781 accepted events across generations, 1,760 held-event records,
3,332 quarantine rows and 12 upload receipts. All seven stored reference kits
remain, with the official kit active. Render was verified with zero events,
zero open consults, no upload receipts, and its clock paused at 18:20 Eastern on
2026-03-17. Offers and interventions were cleared by the normal reset; the
separate operations audit was retained. Supplied local source CSVs were unchanged.

## Verification

- Backend: 425 passed on disposable localhost databases.
- Web: 71 passed; TypeScript and production build passed.
- Chrome desktop and 390 px mobile: clock rewind preserves the captured result,
  duplicate totals exclude existing holds, failed board reads preserve receipts,
  no page errors or horizontal overflow.
- Mechanical design scan of the changed UI: no findings.

The browser regression is `web/scripts/upload-summary.e2e.cjs`. It requires an
empty disposable localhost backend with official references and test accounts,
and refuses an existing stream. Configure `CC_E2E_URL`, `CC_E2E_EMAIL`,
`CC_E2E_PASSWORD`, and optionally `CC_PLAYWRIGHT_MODULE` to an existing Playwright
installation. It adds no application dependency.
