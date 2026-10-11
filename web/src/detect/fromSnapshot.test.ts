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
