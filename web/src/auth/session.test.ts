import { test } from "node:test";
import assert from "node:assert/strict";
import type { Session } from "./session.ts";

const user = { email: "coord@example.test", name: "Coordinator", role: "coordinator" as const, role_label: "Operations coordinator", physician_id: null };
const example = (token = "token"): Session => ({ token, expires_at: Date.now() / 1000 + 600, user });
let id = 0;

async function environment(initial: string | null = null, blocked = false) {
  let stored = initial;
  const target = new EventTarget();
  Object.defineProperty(globalThis, "sessionStorage", { configurable: true, value: {
    getItem: () => { if (blocked) throw new Error("Storage blocked"); return stored; },
    setItem: (_key: string, value: string) => { if (blocked) throw new Error("Storage blocked"); stored = value; },
    removeItem: () => { if (blocked) throw new Error("Storage blocked"); stored = null; },
  } });
  globalThis.dispatchEvent = target.dispatchEvent.bind(target);
  const session = await import(`./session.ts?test=${++id}`) as typeof import("./session.ts");
  return { ...session, target };
}

test("blocked storage still supplies the signed-in token until reload", async () => {
  const session = await environment(null, true);
  session.saveSession(example());
  assert.equal(session.readSession()?.token, "token");
  session.clearSession();
  assert.equal(session.readSession(), null);
});

test("expired and malformed stored sessions do not open the app", async () => {
  for (const value of ["{", JSON.stringify({ ...example(), user: { ...user, role: "admin" } }), JSON.stringify({ ...example(), expires_at: 0 }), JSON.stringify({ ...example(), token: null })]) {
    const session = await environment(value);
    assert.equal(session.readSession(), null);
  }
});

test("a late unauthorized response cannot clear a newer sign-in", async () => {
  const session = await environment();
  let signedOut = 0;
  session.target.addEventListener(session.SIGNED_OUT, () => signedOut++);
  session.saveSession(example("old"));
  session.saveSession(example("new"));
  session.clearSession("old");
  assert.equal(session.readSession()?.token, "new");
  assert.equal(signedOut, 0);
  session.clearSession("new", "Session ended");
  assert.equal(session.readSession(), null);
  assert.equal(signedOut, 1);
});

test("valid stored sessions survive reload with role information", async () => {
  const saved = example();
  const session = await environment(JSON.stringify(saved));
  assert.deepEqual(session.readSession(), saved);
});
