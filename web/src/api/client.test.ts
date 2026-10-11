import { beforeEach, afterEach, test } from "node:test";
import assert from "node:assert/strict";
import { api, ApiError, post } from "./client.ts";
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
