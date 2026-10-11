import { test } from "node:test";
import assert from "node:assert/strict";
import snapshot from "../demo/data/snapshot.json" with { type: "json" };
import { describeWhy, detectFromSnapshot } from "./fromSnapshot.ts";

const detect = detectFromSnapshot(snapshot)!;

test("the queue keeps the server's order, rank and severity", () => {
  assert.deepEqual(detect.queue.map((i) => i.rank), snapshot.queue.items.map((i) => i.rank));
  assert.deepEqual(detect.queue.map((i) => i.level), snapshot.queue.items.map((i) => i.severity));
  const first = detect.queue[0];
  assert.ok(first.label.startsWith(snapshot.queue.items[0].where.consult_id));
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
  assert.equal(describeWhy({ causes: ["Physician busy"], free_elsewhere: ["Physician busy"] }), "Physician busy");
});

test("an unsupported snapshot gives no detect data", () => {
  assert.equal(detectFromSnapshot({ queue: { supported: false }, physicians: { supported: false } }), null);
});

test("display names cover combined gaps and advice without changing command IDs", () => {
  const result = detectFromSnapshot({
    physicians: { supported: true, items: [{ physician_id: "P-2", name: "Dr. Offshift", exclusion_reasons: ["off_shift"] }] },
    hospitals: { items: [{ hospital_id: "H-A", name: "Harbor" }, { hospital_id: "H-B", name: "North" }] },
    workload: { items: [{ physician_id: "P-1", name: "Dr. Lane" }] },
    queue: { supported: true, items: [{ id: "now_gap:H-A", severity: "Warning", rank: 7,
      where: { hospital_ids: ["H-A", "H-B"] }, what: "P-1 unavailable",
      why: { causes: ["P-1 busy at H-A; unknown P-10"] },
      fix: { kind: "watch", action: "Watch H-A", reason: "P-1 returns", alternatives: ["P-1: ready", "P-2: eligible"], physician_id: "P-1" },
    }] },
  })!;
  const item = result.queue[0];
  assert.equal(item.label, "Harbor, North");
  assert.equal(item.id, "now_gap:H-A");
  assert.equal(item.physicianId, "P-1");
  assert.equal(item.rank, 7);
  assert.equal(item.level, "Warning");
  assert.equal(item.watchOnly, true);
  assert.equal(item.reason, "Dr. Lane unavailable");
  assert.equal(item.fix, "Watch Harbor");
  assert.equal(item.fixReason, "Dr. Lane returns");
  assert.deepEqual(item.alternatives, ["Dr. Lane: ready", "Dr. Offshift: eligible"]);
  assert.equal(item.why, "Dr. Lane busy at Harbor; unknown P-10");
});

test("live workload keeps activity, shift totals and consult ownership separate", () => {
  const result = detectFromSnapshot({
    queue: { supported: true, items: [] },
    physicians: { supported: true, items: [{ physician_id: "P", name: "Dr. Test", derived_state: "Video Consult", calls_this_shift: 16, consults_this_shift: 14, open_consults: 3, exclusion_reasons: [], credentialed_hospitals: ["H"] }] },
    hospitals: { items: [{ hospital_id: "H", name: "Test Hospital" }] },
    consults: [{ consult_id: "C", physician_id: "P", current_stage: "Documentation" }, { consult_id: "U", physician_id: "Unassigned", current_stage: "Received" }],
  })!;
  const physician = result.physicians[0];
  assert.equal(physician.derived, "Video Consult");
  assert.equal(physician.calls, 16);
  assert.equal(physician.consults, 14);
  assert.equal(physician.openConsults, 3);
  assert.equal(physician.pendingNotes, 1);
  assert.equal(result.consults[0].physicianName, physician.name);
  assert.equal(result.consults[1].physicianName, null);
  assert.deepEqual(physician.hospitals, [{ id: "H", name: "Test Hospital" }]);
});

test("missing call totals remain unknown instead of becoming zero", () => {
  const result = detectFromSnapshot({ queue: { supported: true, items: [] }, physicians: { supported: true, items: [{ physician_id: "P", exclusion_reasons: [] }] } })!;
  assert.equal(result.physicians[0].calls, null);
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
  const input = { ...copy, consults: copy.consults.map(c => c.consult_id === "CON-2102" ? { ...c, stage_entered_at: "2026-03-17T21:54:00+00:00" } : c) };
  const c = detectFromSnapshot(input)!.consults.find((c) => c.id === "CON-2102")!;
  assert.equal(c.minutesInStage, 26.5);
  assert.equal(c.minutesSinceReceived, 10);
});
