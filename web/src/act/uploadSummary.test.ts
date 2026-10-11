import { test } from "node:test";
import assert from "node:assert/strict";
import { boardOf, uploadSegments } from "./uploadSummary.ts";
import type { IngestReport } from "./types.ts";

const report = (overrides: Partial<IngestReport>): IngestReport => ({
  accepted: 0, duplicates: 0, conflicts: 0, reordered: 0, late: 0, held_orphans: 0,
  quarantined: [], revision: 1, pending_future: 0, ...overrides,
});

test("an upload board keeps its triaged consult and server time when the live board rewinds", () => {
  const snapshot = {
    revision: 1, epoch: "test", clock: { mode: "fixed", now: "2026-03-17T18:27:00-04:00" },
    headline: { open_consults: 1, critical: 1 },
    consults: [{ consult_id: "C", current_stage: "Triaged" }],
  };
  const captured = boardOf(snapshot);
  snapshot.clock.now = "2026-03-17T18:20:00-04:00";
  snapshot.headline.open_consults = 0;
  snapshot.consults[0].current_stage = "Assigned";
  snapshot.consults.length = 0;
  assert.equal(captured.now, Date.parse("2026-03-17T18:27:00-04:00"));
  assert.equal(captured.headline.open_consults, 1);
  assert.equal(captured.consults.get("C")?.current_stage, "Triaged");
});

test("duplicate uploads do not count existing held rows a second time", () => {
  const segments = uploadSegments(report({ duplicates: 9, held_orphans: 3,
    row_results: Array.from({ length: 9 }, (_, i) => ({ row_number: i + 2, event_id: `E${i}`, status: "duplicate", reason: null })),
  }));
  assert.equal(segments.reduce((sum, [, count]) => sum + count, 0), 9);
  assert.equal(segments.find(([, , tone]) => tone === "held")?.[1], 0);
});

test("releasing an earlier hold does not add a row to the current upload summary", () => {
  const segments = uploadSegments(report({ accepted: 2,
    row_results: [{ row_number: 2, event_id: "RECEIPT", status: "accepted", reason: null }],
  }));
  assert.equal(segments.reduce((sum, [, count]) => sum + count, 0), 1);
});

test("JSON reports without per-row results retain their available totals", () => {
  assert.deepEqual(uploadSegments(report({ accepted: 2, pending_future: 1, duplicates: 1 })), [
    ["On the board", 1, "accepted"], ["Waiting for the clock", 1, "waiting"],
    ["Duplicates skipped", 1, "duplicate"], ["Held for missing context", 0, "held"], ["Quarantined", 0, "rejected"],
  ]);
});

test("a released future hold does not make a current accepted row look pending", () => {
  const segments = uploadSegments(report({ accepted: 2, pending_future: 1,
    row_results: [{ row_number: 2, event_id: "CURRENT", status: "accepted", reason: null, pending_future: false }],
  }));
  assert.equal(segments[0][1], 1);
  assert.equal(segments[1][1], 0);
});
