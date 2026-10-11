import { test } from "node:test";
import assert from "node:assert/strict";
import snapshot from "../demo/data/snapshot.json" with { type: "json" };
import { detectFromSnapshot } from "./fromSnapshot.ts";
import { activitySummary, elapsed } from "./activity.ts";

const detect = detectFromSnapshot(snapshot)!;

test("workload counts match the reference while preserving physician / consult units", () => {
  assert.deepEqual(activitySummary(detect.physicians, detect.consults), {
    video: 2, calls: 2, documentation: 8, imagingReview: 2, imagingPending: 1,
  });
  const summary = activitySummary(detect.physicians, [...detect.consults, ...detect.consults]);
  assert.equal(summary.video, 2, "additional open consults must not count as additional active physicians");
  assert.equal(summary.calls, 2);
  assert.equal(summary.documentation, 16);
});

test("camera-only activity and ringing are not counted as Synapse sessions", () => {
  const p = detect.physicians[0];
  const summary = activitySummary([{ ...p, derived: "Camera Active, No Session" }, { ...p, derived: "Available", reason: "ringing" }], []);
  assert.equal(summary.video, 0);
  assert.equal(summary.calls, 0);
});

test("stage durations display minutes and seconds without resetting at an hour", () => {
  assert.equal(elapsed(26), "26:00");
  assert.equal(elapsed(12.5), "12:30");
  assert.equal(elapsed(90), "90:00");
});
