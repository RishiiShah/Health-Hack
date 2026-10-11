import { test } from "node:test";
import assert from "node:assert/strict";
import snapshot from "../demo/data/snapshot.json" with { type: "json" };
import { detectFromSnapshot } from "./fromSnapshot.ts";
import { activitySummary, elapsed } from "./activity.ts";

const detect = detectFromSnapshot(snapshot)!;

test("activity counts preserve physician and consult units", () => {
  const physician = detect.physicians[0];
  const consult = detect.consults[0];
  const physicians = [{ ...physician, derived: "Video Consult" }, { ...physician, id: "P2", derived: "Hospital Call" }];
  const consults = [{ ...consult, stage: "Documentation" }, { ...consult, id: "C2", stage: "Imaging Review" }, { ...consult, id: "C3", stage: "Imaging Pending" }];
  assert.deepEqual(activitySummary(physicians, consults), { video: 1, calls: 1, documentation: 1, imagingReview: 1, imagingPending: 1 });
  const summary = activitySummary(physicians, [...consults, ...consults]);
  assert.equal(summary.video, 1, "additional consults must not count as additional active physicians");
  assert.equal(summary.calls, 1);
  assert.equal(summary.documentation, 2);
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
