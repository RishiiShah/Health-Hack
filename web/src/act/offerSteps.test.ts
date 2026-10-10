import { test } from "node:test";
import assert from "node:assert/strict";
import { isOpen, offerSteps, stateBadge } from "./offerSteps.ts";
import type { Offer } from "./types.ts";

const offer = (overrides: Partial<Offer>): Offer => ({
  offer_id: "OFF-1", gap_id: "GAP-1", physician_id: "PHY-X", physician_name: "Dr. Test", hospital_names: ["Test Hospital"],
  start: "2026-03-17T19:00:00-04:00", end: "2026-03-17T23:00:00-04:00", state: "Proposed", checked_count: 6,
  proposed_by: "System", proposed_at: "2026-03-17T18:20:00-04:00", approved_by: null, approved_at: null, sent_at: null,
  expires_at: null, responded_at: null, message: null, audio_url: null, phone_url: null, reject_reason: null, ...overrides,
});

test("a proposed offer waits on the lead's decision", () => {
  const steps = offerSteps(offer({}), null);
  assert.deepEqual(steps.map((s) => s.status), ["done", "done", "current", "todo", "todo"]);
  assert.equal(steps[0].detail, "System · 18:20");
  assert.equal(steps[1].label, "Checked 6 people");
  assert.equal(stateBadge("Proposed").text, "Waiting for you");
});

test("a sent offer shows the reply countdown", () => {
  const steps = offerSteps(offer({ state: "Sent", approved_by: "Lead" }), "9:41");
  assert.equal(steps[2].detail, "Approved by Lead");
  assert.equal(steps[3].status, "current");
  assert.equal(steps[3].detail, "9:41 to reply");
});

test("answered and rejected offers are closed", () => {
  for (const state of ["Accepted", "Declined", "Expired", "Withdrawn", "Rejected"] as const) assert.equal(isOpen(offer({ state })), false);
  assert.equal(isOpen(offer({ state: "Sent" })), true);
  assert.equal(offerSteps(offer({ state: "Expired" }), null)[3].detail, "Expired");
});
