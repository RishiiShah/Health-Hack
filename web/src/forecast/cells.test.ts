import { test } from "node:test";
import assert from "node:assert/strict";
import { cellText, cellTone, stepLabel, elapsedMinutes } from "./cells.ts";
import type { CoverageCell } from "./types.ts";

const cell = (overrides: Partial<CoverageCell>): CoverageCell => ({
  at: "2026-03-17T23:00:00+00:00", count: 1, required: 2, status: "gap", unverified: false,
  schedule_incomplete: false, physician_ids: [], incomplete_physician_ids: [], gap_id: null, ...overrides,
});

test("cell text is count over required, or ? when either is unknown", () => {
  assert.equal(cellText(cell({})), "1/2");
  assert.equal(cellText(cell({ required: null, status: "unknown" })), "?");
});

test("tone follows the server status; an incomplete schedule softens a gap", () => {
  assert.equal(cellTone(cell({})), "gap");
  assert.equal(cellTone(cell({ schedule_incomplete: true })), "maybe");
  assert.equal(cellTone(cell({ status: "at_minimum", count: 2 })), "at");
  assert.equal(cellTone(cell({ status: "above_minimum", count: 3 })), "above");
  assert.equal(cellTone(cell({ status: "unknown" })), "unknown");
});

test("first column is Now, the rest are ET clock times", () => {
  assert.equal(stepLabel("2026-03-17T22:20:00+00:00", 0), "Now");
  assert.equal(stepLabel("2026-03-17T22:30:00+00:00", 1), "18:30");
});


test("exact shift cliffs have elapsed offsets rather than column-index offsets", () => {
  const start = "2026-03-17T22:20:00Z";
  assert.equal(elapsedMinutes("2026-03-17T23:00:00Z", start), 40);
  assert.equal(elapsedMinutes("2026-03-18T00:00:00Z", start), 100);
});
