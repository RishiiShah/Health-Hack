# Fixed-reference CSV audit — 2026-10-11

The reference kit is Sevaro's supplied six files, service date 2026-03-17,
12 hospitals and 14 physicians. Its pinned fingerprint is
`81602969911fe81fc1d5db5a51595fb5124d07ac5f5e97623a21e1232701d72d`.
Event uploads append to the current stream and recompute deterministic decisions
from the combined visible history. They cannot edit references.

## Findings and fixes

| Finding | Reason and resulting behavior | Regression evidence |
| --- | --- | --- |
| References could be replaced or mislabeled | Runtime pins the official fingerprint; changed references receive 409. An identical reference upload verifies without writing or relabeling. Startup refuses a mismatched persisted source. | Reference policy tests failed before the fix and now pass. Synthetic tests override the pin only in process; no environment bypass exists. |
| Invalid or held future events could advance the clock; clock and events committed separately | Only newly accepted events can advance the clock. Events, diagnostics, receipt and clock commit together. Automatic advances over 24 hours are held back pending date review and explicit clock control. These events are accepted into storage but remain outside visible replay. | Rejected/held, mixed future, transaction failure, duplicate and large-jump regressions. |
| Overlapping instances could rewind the clock | A stale write reloads the persisted clock before replay and retry. | Two-instance regression failed with a 20-minute advance overwritten by a 10-minute advance; now passes. |
| Results lacked row IDs and dependency reasons; counts overlapped | Each CSV record has a header-relative record number, event ID, status and reason. Unknown IDs and missing receipt events name the dependency. Rows received, accepted events, duplicates, conflicts, quarantine and active holds remain distinct. Legacy row totals are explicitly estimates. | Mixed conflict/held/quarantined tests verify diagnostics and counts. |
| Upload results vanished on navigation | Durable receipts retain filename, actor, original-byte SHA-256, reference fingerprint, stream generation, mentioned consult IDs, clocks and per-row results. Latest 20 receipts are available at authenticated `GET /admin/uploads` and Data → Upload history. Reports can be downloaded as JSON. | Restart/reset backend tests; browser navigation, reload and report-download checks. |
| Browser decoding changed the file checksum | Uploads send the File bytes directly, preserving BOM and line endings and allowing the server to reject invalid UTF-8. | A BOM/CRLF browser regression failed before the change and passes afterward. |

CSV parsing requires the eight event-stream headers, rejects empty or malformed
files with 422, and enforces 5 MB and the configured row limit. Parsed row failures
are recorded in a receipt; files rejected before parsing have an immediate error
and no receipt. Record numbers count CSV records, including the header as record
1; quoted multiline fields do not create extra record numbers.

Reports describe outcomes at upload time. Held events can later release when
missing event dependencies arrive, or expire using server receipt time. Unknown
hospital/physician IDs cannot be added through an event upload: those IDs must
exist in the fixed kit. Earlier uploads have no retroactive receipts. Empty-stream
reset retains historical event generations and upload receipts.

## Verification

- Backend: **363 passed**, including protected local packs and the new audit regressions.
- Web: **46 passed**; TypeScript and production build passed.
- Computer use and Playwright verified the live Data page using an isolated local
  database seeded with the exact official reference snapshot copied read-only
  from production. Production events and references were not changed.
- Original event file: **1,163 accepted, 1 duplicate**. Compatible unseen events:
  **3 accepted, 1 duplicate**, clock 18:30 ET, new stroke consult ranked Critical,
  Suncrest surge count 6. Re-upload: **0 accepted, 4 duplicates**, unchanged queue.
- Independent database check retained all **1,163 first-seen original event
  payloads**; the served queue matched a full replay of the combined 1,166 events.
- Actual `test_data/01_development/live/judge_events.csv`: **0 accepted, 125 held**.
  This pack uses a different hospital/physician namespace. The UI explains those
  missing IDs; reference identity, clock and queue remain unchanged.
- Desktop and 390 px mobile history/diagnostics were inspected; no horizontal
  overflow or page errors were observed. Backend restart preserved receipts.

`web/scripts/csv-upload.e2e.cjs` is the repeatable browser regression. It requires
an installed Playwright and Chrome; it adds no application dependency. Run it
against an **empty disposable localhost database** seeded with official references,
with a fixed replay clock at 2026-03-17 18:20 ET and a coordinator test account.
It refuses an existing event stream and never resets a database itself:

```sh
CC_E2E_URL=http://127.0.0.1:5183 \
CC_E2E_EMAIL=<test-account> CC_E2E_PASSWORD=<test-password> \
node web/scripts/csv-upload.e2e.cjs
```

Use `CC_PLAYWRIGHT_MODULE` for an existing installation outside Node's normal
module search path. Evidence and screenshots are written to a temporary folder.
The official event file is required locally; the incompatible development-pack
check runs when that gitignored pack is present.

## Hosted verification still pending

A Render application is not deployed or verified. These checks establish local
behavior with the production reference snapshot, not a hosted browser pass.
After deployment, verify `/ready`, reference fingerprint/revision, and receipt
persistence across a service restart. Rehearse event ingestion against a separate
hosted test database so the production day is not altered by test uploads.
