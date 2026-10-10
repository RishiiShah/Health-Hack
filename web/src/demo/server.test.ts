import { test } from "node:test";
import assert from "node:assert/strict";
import { createDemoServer } from "./server.ts";

const json = (o: unknown) => JSON.stringify(o);
const COORD = "demo.coordinator@demo.sevaro";
const LEAD = "demo.lead@demo.sevaro";
const DOC = "demo.okafor@demo.sevaro";

type Server = ReturnType<typeof createDemoServer>;
const get = <T>(s: Server, path: string, token = LEAD) => s.handle({ method: "GET", path, token }) as T;
const post = <T>(s: Server, path: string, body: unknown, token: string) => s.handle({ method: "POST", path, body: json(body), token }) as T;
const firstOffer = (s: Server) => get<{ items: { offer_id: string; state: string }[] }>(s, "/offers").items[0];

test("sign-in follows the account's role, and the wrong portal names the right one", () => {
  const server = createDemoServer(() => 0);
  const login = (email: string, portal: string) => server.handle({ method: "POST", path: "/auth/login", body: json({ email, password: "x", portal }) });
  assert.equal((login("Lead@demo.sevaro", "operations") as { user: { role: string } }).user.role, "lead");
  assert.throws(() => login("okafor@demo.sevaro", "operations"), { status: 403, detail: /Sign in as Physician/ });
  assert.throws(() => login("nobody@demo.sevaro", "operations"), { status: 401 });
});

test("each route only accepts its roles", () => {
  const server = createDemoServer(() => 0);
  assert.throws(() => server.handle({ method: "GET", path: "/snapshot" }), { status: 401 });
  assert.throws(() => get(server, "/snapshot", DOC), { status: 403 });
  assert.ok(get(server, "/snapshot", COORD));
  const offer = firstOffer(server);
  assert.throws(() => post(server, `/offers/${offer.offer_id}/approve`, {}, COORD), { status: 403 });
  assert.throws(() => post(server, "/offers", { physician_id: "PHY-009" }, LEAD), { status: 403 });
  assert.throws(() => get(server, "/me/offers", LEAD), { status: 403 });
});

test("unified sign-in accepts every account role without selecting a portal", () => {
  const server = createDemoServer();
  for (const [email, role] of [["coordinator@demo.sevaro", "coordinator"], ["lead@demo.sevaro", "lead"], ["okafor@demo.sevaro", "physician"]]) {
    const result = server.handle({ method: "POST", path: "/auth/login", body: json({ email, password: "x" }) }) as { user: { role: string } };
    assert.equal(result.user.role, role);
  }
});

test("full loop: lead approves, the physician sees it and accepts, the gap closes", () => {
  const server = createDemoServer(() => 0);
  const offer = firstOffer(server);
  assert.equal(get<{ items: unknown[] }>(server, "/me/offers", DOC).items.length, 0, "not visible before approval");
  post(server, `/offers/${offer.offer_id}/approve`, {}, LEAD);
  assert.equal(get<{ items: unknown[] }>(server, "/me/offers", DOC).items.length, 1);
  post(server, `/me/offers/${offer.offer_id}/accept`, {}, DOC);
  assert.equal(firstOffer(server).state, "Accepted");
  const snapshot = get<{ coverage: { hospitals: { cells: { count: number; required: number }[] }[] } }>(server, "/snapshot");
  assert.deepEqual(snapshot.coverage.hospitals[0].cells[3], { ...snapshot.coverage.hospitals[0].cells[3], count: 2, required: 2 });
});

test("approve sends with a 10-minute expiry, then expires", () => {
  let local = 0;
  const server = createDemoServer(() => local);
  const sent = post<{ state: string; expires_at: string }>(server, `/offers/${firstOffer(server).offer_id}/approve`, {}, LEAD);
  assert.equal(sent.state, "Sent");
  assert.equal(Date.parse(sent.expires_at) - server.now(), 10 * 60_000);
  local += 10 * 60_000;
  assert.equal(firstOffer(server).state, "Expired");
});

test("demo rejects short offers and ineligible physicians with a server-style error", () => {
  const server = createDemoServer(() => 0);
  const gap = { gap_id: "g", start: "2026-03-17T19:00:00-04:00" };
  assert.throws(() => post(server, "/offers", { ...gap, physician_id: "PHY-009", end: "2026-03-17T20:00:00-04:00" }, COORD), { status: 422 });
  assert.throws(() => post(server, "/offers", { ...gap, physician_id: "PHY-011", end: "2026-03-17T23:00:00-04:00" }, COORD), { status: 422 });
});

test("demo clock pauses and jumps forward", () => {
  let local = 0;
  const server = createDemoServer(() => local);
  const start = server.now();
  post(server, "/admin/clock", { paused: true }, LEAD);
  local += 60_000;
  assert.equal(server.now(), start);
  post(server, "/admin/clock", { advance_s: 300 }, LEAD);
  assert.equal(server.now(), start + 300_000);
});
