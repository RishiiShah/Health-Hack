import { test } from "node:test";
import assert from "node:assert/strict";
import { suggestedOfferWindow } from "./offerWindow.ts";
import { clockTime, etTimeOn } from "./time.ts";

test("a short gap uses the candidate's extended two-hour window", () => {
  const window = suggestedOfferWindow({ start: "2026-04-07T19:00:00-04:00", end: "2026-04-07T21:00:00-04:00" }, Date.parse("2026-04-07T18:00:00-04:00"));
  assert.equal(clockTime(window.end), "21:00");
  assert.equal(Date.parse(window.end) - Date.parse(window.start), 2 * 60 * 60_000);
});

test("rounding a live start preserves the evaluated duration", () => {
  const now = Date.parse("2026-04-07T19:00:37-04:00");
  const window = suggestedOfferWindow({ start: new Date(now).toISOString(), end: new Date(now + 130 * 60_000).toISOString() }, now);
  assert.equal(clockTime(window.start), "19:01");
  assert.equal(Date.parse(window.end) - Date.parse(window.start), 130 * 60_000);
});

test("overnight endpoint edits keep the evaluated end date", () => {
  const window = suggestedOfferWindow({ start: "2026-04-07T23:30:00-04:00", end: "2026-04-08T01:30:00-04:00" }, null);
  assert.equal(etTimeOn(window.end, "01:45"), "2026-04-08T01:45:00-04:00");
});

test("a stale start moved across midnight shifts the end with it", () => {
  const window = suggestedOfferWindow({ start: "2026-04-07T23:59:00-04:00", end: "2026-04-08T01:59:00-04:00" }, Date.parse("2026-04-07T23:59:30-04:00"));
  assert.equal(etTimeOn(window.start, clockTime(window.start)), "2026-04-08T00:00:00-04:00");
  assert.equal(Date.parse(window.end) - Date.parse(window.start), 2 * 60 * 60_000);
});
