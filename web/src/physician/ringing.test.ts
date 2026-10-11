import assert from "node:assert/strict";
import { test } from "node:test";
import type { Offer } from "../act/types.ts";
import { nextRinging } from "./ringing.ts";

const offer = (offer_id: string, state: Offer["state"], expires_at: string | null = "2026-03-17T18:35:00-04:00") =>
  ({ offer_id, state, expires_at }) as Offer;
const now = Date.parse("2026-03-17T18:25:00-04:00");

test("rings for a sent offer once", () => {
  const items = [offer("OFR-1", "Accepted"), offer("OFR-2", "Sent")];
  assert.equal(nextRinging(items, new Set(), now)?.offer_id, "OFR-2");
  assert.equal(nextRinging(items, new Set(["OFR-2"]), now), null);
});

test("does not ring for an offer past its server expiry", () => {
  assert.equal(nextRinging([offer("OFR-3", "Sent", "2026-03-17T18:20:00-04:00")], new Set(), now), null);
});

test("rings once the lead approves in the demo server, and stops after the reply", async () => {
  const { createDemoServer } = await import("../demo/server.ts");
  const server = createDemoServer(() => 0);
  const doc = "demo.okafor@demo.sevaro";
  const mine = () => server.handle({ method: "GET", path: "/me/offers", token: doc }) as { now: string; items: Offer[] };
  const ring = () => nextRinging(mine().items, new Set(), Date.parse(mine().now));
  const [proposed] = (server.handle({ method: "GET", path: "/offers", token: "demo.lead@demo.sevaro" }) as { items: Offer[] }).items;
  assert.equal(ring(), null, "nothing rings before approval");
  server.handle({ method: "POST", path: `/offers/${proposed.offer_id}/approve`, body: "{}", token: "demo.lead@demo.sevaro" });
  assert.equal(ring()?.offer_id, proposed.offer_id);
  server.handle({ method: "POST", path: `/me/offers/${proposed.offer_id}/decline`, body: "{}", token: doc });
  assert.equal(ring(), null, "a declined offer no longer rings");
});
