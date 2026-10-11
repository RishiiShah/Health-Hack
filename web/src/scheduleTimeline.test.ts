import assert from "node:assert/strict";
import test from "node:test";
import { clockPosition, shiftWindow } from "./scheduleTimeline.ts";

test("shift positions preserve different start times and durations", () => {
  assert.deepEqual(shiftWindow("08:00 to 20:00"), { start: 480, end: 1200, continues: false });
  assert.deepEqual(shiftWindow("19:00 to 23:00"), { start: 1140, end: 1380, continues: false });
});
test("overnight and open-ended shifts stop at the visible day without inventing an end", () => {
  assert.deepEqual(shiftWindow("Night · from 19:00"), { start: 1140, end: 1440, continues: true });
  assert.deepEqual(shiftWindow("20:00 to 08:00"), { start: 1200, end: 1440, continues: true });
  assert.equal(shiftWindow("Off today"), null);
  assert.equal(shiftWindow("08:99 to 20:00"), null);
});
test("current time marker follows the supplied roster clock", () => {
  assert.equal(clockPosition("12:00"), 50);
  assert.equal(clockPosition("18:00"), 75);
  assert.equal(clockPosition("24:00"), null);
});
