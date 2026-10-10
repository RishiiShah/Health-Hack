import { test } from "node:test";
import assert from "node:assert/strict";
import { clockTime, clockTimeSeconds, countdown, duration, etTimeOn, headerDate, minutesUntil, serverNow } from "./time.ts";

test("edited ET times keep the reference's ET date and offset", () => {
  assert.equal(etTimeOn("2026-03-17T23:00:00+00:00", "19:30"), "2026-03-17T19:30:00-04:00");
  assert.equal(etTimeOn("2026-03-18T03:30:00+00:00", "23:00"), "2026-03-17T23:00:00-04:00");
  assert.equal(etTimeOn("2026-01-10T15:00:00Z", "08:00"), "2026-01-10T08:00:00-05:00");
});

test("durations read as minutes and seconds", () => {
  assert.equal(duration(405), "6 min 45 s");
  assert.equal(duration(42), "42 s");
});

test("formats instants in Eastern time whatever the offset", () => {
  assert.equal(clockTime("2026-03-17T22:20:00+00:00"), "18:20");
  assert.equal(clockTime("2026-03-17T19:00:00-04:00"), "19:00");
  assert.equal(clockTimeSeconds("2026-03-17T22:22:19Z"), "18:22:19");
  assert.equal(headerDate("2026-03-17T22:22:00Z"), "Tue 17 Mar");
});

test("countdown floors at zero and pads seconds", () => {
  const now = Date.parse("2026-03-17T18:20:00-04:00");
  assert.equal(countdown("2026-03-17T18:30:00-04:00", now), "10:00");
  assert.equal(countdown("2026-03-17T18:20:05-04:00", now), "0:05");
  assert.equal(countdown("2026-03-17T18:19:00-04:00", now), "0:00");
});

test("minutes until a time can be negative once it has passed", () => {
  const now = Date.parse("2026-03-17T18:22:00-04:00");
  assert.equal(minutesUntil("2026-03-17T19:00:00-04:00", now), 38);
  assert.equal(minutesUntil("2026-03-17T18:21:00-04:00", now), -1);
});

test("a fixed clock does not advance between snapshots", () => {
  const at = "2026-03-17T22:20:00+00:00";
  assert.equal(serverNow(at, "fixed", 1_000, 61_000), Date.parse(at));
  assert.equal(serverNow(at, "anchored", 1_000, 61_000), Date.parse(at) + 60_000);
});
