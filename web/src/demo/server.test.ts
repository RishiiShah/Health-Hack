import { test } from "node:test";
import assert from "node:assert/strict";
import { createDemoServer } from "./server.ts";

const json = (o: unknown) => JSON.stringify(o);
const COORD = "demo.coord@demo.sevaro";
const LEAD = "demo.lead@demo.sevaro";
const DOC = "demo.okafor@demo.sevaro";
const GAP = "now_gap:SYN-005";

type Server = ReturnType<typeof createDemoServer>;
type Cell = { at: string; count: number; required: number; status: string };
const get = <T>(s: Server, path: string, token = LEAD) => s.handle({ method: "GET", path, token }) as T;
const post = <T>(s: Server, path: string, body: unknown, token: string) => s.handle({ method: "POST", path, body: json(body), token }) as T;
const firstOffer = (s: Server) => get<{ items: { offer_id: string; state: string; start: string; end: string }[] }>(s, "/offers").items[0];
const cells = (s: Server, hospitalId: string) =>
  get<{ coverage: { hospitals: { hospital_id: string; cells: Cell[] }[] } }>(s, "/snapshot").coverage.hospitals.find((h) => h.hospital_id === hospitalId)!.cells;

test("sign-in follows the account's role, and the wrong portal names the right one", () => {
  const server = createDemoServer(() => 0);
  const login = (email: string, portal?: string) => server.handle({ method: "POST", path: "/auth/login", body: json({ email, password: "x", portal }) }) as { user: { role: string } };
  assert.equal(login("Lead@demo.sevaro", "operations").user.role, "lead");
  for (const [email, role] of [["coord@demo.sevaro", "coordinator"], ["lead@demo.sevaro", "lead"], ["okafor@demo.sevaro", "physician"]]) {
    assert.equal(login(email).user.role, role, "no portal: the account decides");
  }
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
  assert.throws(() => get(server, "/schedule", DOC), { status: 403 });
});

test("full loop: lead approves, the physician sees it and accepts, Suncrest gains a physician", () => {
  const server = createDemoServer(() => 0);
  const offer = firstOffer(server);
  const before = cells(server, "SYN-005")[0];
  assert.equal(before.status, "gap", "Suncrest is short at 18:20 in the captured data");
  assert.equal(get<{ items: unknown[] }>(server, "/me/offers", DOC).items.length, 0, "not visible before approval");
  post(server, `/offers/${offer.offer_id}/approve`, {}, LEAD);
  const [sent] = get<{ items: { message: string }[] }>(server, "/me/offers", DOC).items;
  assert.match(sent.message, /Suncrest Medical Pavilion/);
  assert.doesNotMatch(sent.message, /CON-\d/, "offers never carry consult details");
  post(server, `/me/offers/${offer.offer_id}/accept`, {}, DOC);
  assert.equal(firstOffer(server).state, "Accepted");
  const after = cells(server, "SYN-005")[0];
  assert.equal(after.count, before.count + 1, "the accepted physician is counted for the offer's hours");
  assert.equal(after.status, after.count < after.required ? "gap" : "at_minimum");
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

test("demo rejects ineligible physicians, short offers and a second open offer", () => {
  const server = createDemoServer(() => 0);
  const start = "2026-03-17T22:20:00+00:00";
  assert.throws(() => post(server, "/offers", { gap_id: GAP, physician_id: "PHY-010", start, end: "2026-03-18T02:00:00+00:00" }, COORD), { status: 422 });
  assert.throws(() => post(server, "/offers", { gap_id: GAP, physician_id: "PHY-009", start, end: "2026-03-17T23:00:00+00:00" }, COORD), { status: 422 });
  assert.throws(() => post(server, "/offers", { gap_id: GAP, physician_id: "PHY-009", start, end: "2026-03-18T02:00:00+00:00" }, COORD), { status: 409 });
  assert.throws(() => get(server, "/gaps/gap:unknown/candidates"), { status: 404 });
});

test("escalations wait for the lead, who authorizes them", () => {
  const server = createDemoServer(() => 0);
  const record = post<{ intervention_id: string; state: string }>(server, "/interventions", { kind: "escalate", item_id: "unassigned:CON-2105" }, COORD);
  assert.equal(record.state, "pending");
  assert.equal(get<{ pending_approvals: number }>(server, "/snapshot").pending_approvals, 2, "the proposed offer plus the escalation");
  assert.throws(() => post(server, `/interventions/${record.intervention_id}/authorize`, {}, COORD), { status: 403 });
  assert.equal(post<{ state: string }>(server, `/interventions/${record.intervention_id}/authorize`, {}, LEAD).state, "authorized");
});

test("a physician's shift lists only their own consults", () => {
  const server = createDemoServer(() => 0);
  const shift = get<{ name: string; consults: { consult_id: string }[]; hospitals: string[] }>(server, "/me/shift", "demo.shah@demo.sevaro");
  assert.equal(shift.name, "Dr. Priya Shah");
  assert.ok(shift.hospitals.length > 0);
  const all = get<{ consults: { consult_id: string; physician_id: string }[] }>(server, "/snapshot").consults;
  assert.deepEqual(shift.consults.map((c) => c.consult_id), all.filter((c) => c.physician_id === "PHY-005").map((c) => c.consult_id));
});

test("demo clock pauses and jumps forward", () => {
  let local = 0;
  const server = createDemoServer(() => local);
  const start = server.now();
  post(server, "/admin/clock", { paused: true }, LEAD);
  assert.equal(get<{ clock_mode: string }>(server, "/me/offers", DOC).clock_mode, "fixed");
  local += 60_000;
  assert.equal(server.now(), start);
  post(server, "/admin/clock", { advance_s: 300 }, LEAD);
  assert.equal(server.now(), start + 300_000);
});

test("presentation demo rejects event uploads instead of reporting simulated acceptance", () => {
  const server = createDemoServer(() => 0);
  const before = get(server, "/snapshot");
  assert.throws(() => server.handle({
    method: "POST", path: "/events/csv?advance_clock=true", token: COORD,
    body: "event_id,event_time,ingested_at,consult_id,event_type,physician_id,hospital_id,description\nNEW,2026-03-17T18:21:00-04:00,2026-03-17T18:21:00-04:00,C,consult_received,,SYN-005,Stroke consult request received\n",
  }), { status: 503, detail: /requires the live backend/ });
  assert.throws(() => post(server, "/events", { event_id: "NEW" }, COORD), { status: 503, detail: /requires the live backend/ });
  assert.deepEqual(get(server, "/snapshot"), before);
});
