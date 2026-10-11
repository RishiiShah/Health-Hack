import { test } from "node:test";
import assert from "node:assert/strict";
import snapshot from "../demo/data/snapshot.json" with { type: "json" };
import { describeWhy, detectFromSnapshot } from "./fromSnapshot.ts";

const detect = detectFromSnapshot(snapshot)!;

test("the queue keeps the server's order, rank and severity", () => {
  assert.deepEqual(detect.queue.map((i) => i.rank), snapshot.queue.items.map((i) => i.rank));
  assert.deepEqual(detect.queue.map((i) => i.level), snapshot.queue.items.map((i) => i.severity));
  const first = detect.queue[0];
  assert.equal(first.label, snapshot.queue.items[0].where.consult_id);
  assert.match(first.where, /Harbor Regional/, "hospital IDs are shown by name");
});

test("consults take their level from the queue, or Normal when nothing is flagged", () => {
  assert.equal(detect.consults.length, snapshot.consults.length);
  const flagged = detect.consults.find((c) => c.id === "CON-2110")!;
  assert.equal(flagged.level, "Critical");
  assert.equal(flagged.limit, "3 / 8 min");
  assert.ok(detect.consults.some((c) => c.level === "Normal" && c.limit === "–"));
});

test("only on-shift physicians are on the board; headline counts come from server fields", () => {
  assert.ok(detect.physicians.every((p) => !p.reason.includes("off_shift")));
  assert.equal(detect.headline.openConsults, snapshot.headline.open_consults);
  assert.equal(detect.headline.pastCritical, snapshot.headline.critical);
  assert.equal(detect.headline.totalPhysicians, detect.physicians.length);
});

test("why reads as a sentence and never invents numbers", () => {
  assert.equal(describeWhy({ stage: "Imaging Pending", age_min: 26.0, warning_min: 12, critical_min: 20 }), "Imaging Pending for 26 min (warning 12, critical 20)");
  assert.equal(describeWhy({ count: 5, p90: 1 }), "5 consults in 60 min against a usual peak of 1");
  assert.equal(describeWhy({}), "");
});

test("an unsupported snapshot gives no detect data", () => {
  assert.equal(detectFromSnapshot({ queue: { supported: false }, physicians: { supported: false } }), null);
});

test("live workload keeps current activity, shift totals and consult ownership separate", () => {
  const kim = detect.physicians.find((p) => p.id === "PHY-002")!;
  assert.equal(kim.derived, "Video Consult");
  assert.equal(kim.calls, 16);
  assert.equal(kim.consults, 14);
  assert.equal(kim.openConsults, 3);
  assert.equal(kim.pendingNotes, 1);
  assert.equal(detect.consults.find((c) => c.id === "CON-2117")!.physicianName, kim.name);
  assert.equal(detect.consults.find((c) => c.id === "CON-2105")!.physicianName, null);
  assert.ok(kim.hospitals.some((h) => h.name === "Northfield Medical"));
});

test("missing call totals remain unknown instead of becoming zero", () => {
  const copy = structuredClone(snapshot);
  const p = copy.physicians.items.find((p) => p.physician_id === "PHY-002")!;
  copy.workload.items = copy.workload.items.filter((w) => w.physician_id !== p.physician_id);
  assert.equal(detectFromSnapshot(copy)!.physicians.find((d) => d.id === p.physician_id)!.calls, null);
});

test("documentation flags retain the cumulative interaction clock, separate from stage time", () => {
  const result = detectFromSnapshot({
    queue: { supported: true, items: [{ id: "note_overdue:C1", rank: 1, severity: "Critical", what: "Overdue note", where: { consult_id: "C1" },
      why: { age_min: 51, warning_min: 30, critical_min: 45, interaction_ended: "2026-03-17T17:00:00-04:00" } }] },
    physicians: { supported: true, items: [] },
    consults: [{ consult_id: "C1", current_stage: "Documentation", minutes_in_stage: 9, minutes_since_received: 70, consult_type: "Stroke" }],
  })!;
  assert.equal(result.consults[0].minutesInStage, 9);
  assert.equal(result.consults[0].standardAge, 51);
  assert.equal(result.consults[0].standardClock, "Since interaction ended");
});

test("stage timers use publication timestamps without inventing seconds for rounded totals", () => {
  const copy = structuredClone(snapshot);
  copy.clock.now = "2026-03-17T22:20:30+00:00";
  const c = detectFromSnapshot(copy)!.consults.find((c) => c.id === "CON-2102")!;
  assert.equal(c.minutesInStage, 26.5);
  assert.equal(c.minutesSinceReceived, 36);
});
