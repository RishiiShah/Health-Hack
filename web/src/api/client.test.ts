import { beforeEach, afterEach, test } from "node:test";
import assert from "node:assert/strict";
import { api, apiBlob, ApiError, post } from "./client.ts";
import { clearSession, readSession, saveSession, type Session } from "../auth/session.ts";

const originalFetch = globalThis.fetch;
const session = (token: string): Session => ({ token, expires_at: Date.now() / 1000 + 600,
  user: { email: "c@x.test", name: "C", role: "coordinator", role_label: "Operations coordinator", physician_id: null } });
const response = (status: number, detail = "Denied") => new Response(JSON.stringify({ detail }), { status, headers: { "Content-Type": "application/json" } });

beforeEach(() => {
  const target = new EventTarget();
  globalThis.dispatchEvent = target.dispatchEvent.bind(target);
  // No browser storage is available: this also exercises the in-memory fallback.
  clearSession();
});
afterEach(() => { globalThis.fetch = originalFetch; });

test("requests attach the current token but never attach it to login", async () => {
  saveSession(session("current"));
  const tokens: (string | null)[] = [];
  globalThis.fetch = async (_input, init) => { tokens.push(new Headers(init?.headers).get("Authorization")); return response(200); };
  await api("/snapshot");
  await post("/auth/login", { email: "c@x.test", password: "password" });
  assert.deepEqual(tokens, ["Bearer current", null]);
});

test("failed login and forbidden actions preserve the session", async () => {
  saveSession(session("current"));
  globalThis.fetch = async () => response(401);
  await assert.rejects(post("/auth/login", {}), ApiError);
  assert.equal(readSession()?.token, "current");
  globalThis.fetch = async () => response(403);
  await assert.rejects(api("/snapshot"), ApiError);
  assert.equal(readSession()?.token, "current");
});

test("only a 401 for the active token signs out", async () => {
  saveSession(session("old"));
  let finish!: (response: Response) => void;
  globalThis.fetch = () => new Promise(resolve => { finish = resolve; });
  const pending = api("/snapshot");
  saveSession(session("new"));
  finish(response(401));
  await assert.rejects(pending, ApiError);
  assert.equal(readSession()?.token, "new");
  globalThis.fetch = async () => response(401);
  await assert.rejects(api("/snapshot"), ApiError);
  assert.equal(readSession(), null);
});

test("network failures are retryable without discarding the session", async () => {
  saveSession(session("current"));
  globalThis.fetch = async () => { throw new TypeError("Failed to fetch"); };
  await assert.rejects(api("/auth/me"), /Can't reach the server/);
  assert.equal(readSession()?.token, "current");
});

test("protected media receives bearer authentication and returns binary audio", async () => {
  saveSession(session("audio-token"));
  globalThis.fetch = async (path, init) => {
    assert.equal(path, "/offers/example/audio");
    assert.equal(new Headers(init?.headers).get("Authorization"), "Bearer audio-token");
    return new Response(new Uint8Array([73, 68, 51]), { headers: { "Content-Type": "audio/mpeg" } });
  };
  const blob = await apiBlob("/offers/example/audio");
  assert.equal(blob.type, "audio/mpeg");
  assert.deepEqual([...new Uint8Array(await blob.arrayBuffer())], [73, 68, 51]);
});

test("media errors surface the server detail and expired authentication signs out", async () => {
  saveSession(session("audio-token"));
  globalThis.fetch = async () => response(503, "Speech is not configured.");
  await assert.rejects(apiBlob("/alerts/example/audio"), /Speech is not configured/);
  assert.equal(readSession()?.token, "audio-token");
  globalThis.fetch = async () => new Response(JSON.stringify({ error: { code: "speech_unavailable", message: "text-to-speech unavailable" } }),
    { status: 503, headers: { "Content-Type": "application/json" } });
  await assert.rejects(apiBlob("/alerts/example/audio"), /text-to-speech unavailable/);
  globalThis.fetch = async () => response(401);
  await assert.rejects(apiBlob("/alerts/example/audio"), ApiError);
  assert.equal(readSession(), null);
});

test("media never sends the session token to a foreign host", () => {
  globalThis.fetch = async () => { assert.fail("foreign media must not be fetched"); };
  for (const path of ["https://other.example/audio", "//other.example/audio", "/\\other.example/audio"])
    assert.throws(() => apiBlob(path), /Audio must come from this application/);
});

test("an empty gateway error says the server isn't responding", async () => {
  globalThis.fetch = async () => new Response("", { status: 502 });
  await assert.rejects(post("/auth/login", {}), { status: 502, message: "The server isn't responding. Check that the backend is running, then try again." });
});
