// Minimal scaffold for Anish to replace: fetch wrapper with the bearer token and typed errors.
import { clearSession, readSession } from "../auth/session.ts";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

// VITE_DEMO_DATA=1 answers every call from in-memory demo data; otherwise the demo code isn't bundled at all.
export const DEMO = import.meta.env?.VITE_DEMO_DATA === "1";
let demo: Promise<ReturnType<typeof import("../demo/server.ts").createDemoServer>> | null = null;

async function send<T>(path: string, init: RequestInit, token: string | null): Promise<T> {
  if (DEMO) {
    demo ??= import("../demo/server.ts").then((m) => m.createDemoServer());
    try {
      return (await demo).handle({ method: init.method ?? "GET", path, body: init.body as string | undefined, token }) as T;
    } catch (e) {
      const { status, detail } = e as { status: number; detail: string };
      throw new ApiError(status, detail);
    }
  }
  const headers = new Headers(init.headers);
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (typeof init.body === "string" && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");
  let response: Response;
  try {
    const timeout = AbortSignal.timeout(15_000);
    const signal = init.signal ? AbortSignal.any([init.signal, timeout]) : timeout;
    response = await fetch(path, { ...init, headers, signal });
  } catch (error) {
    if (error instanceof Error && error.name === "AbortError") throw error;
    if (error instanceof Error && error.name === "TimeoutError") throw new Error("The server took too long to respond. Try again.");
    throw new Error("Can't reach the server. Check your connection and try again.");
  }
  const type = response.headers.get("Content-Type") ?? "";
  // A path the backend doesn't serve can come back as the web server's index.html; treat it as the missing route it is.
  if (response.ok && type.includes("text/html")) throw new ApiError(404, "Not Found");
  const body = type.includes("json") ? await response.json() : await response.text();
  if (!response.ok) {
    const detail = typeof body === "object" && body && "detail" in body ? body.detail : body;
    const message = typeof detail === "string" ? detail : Array.isArray(detail) ? detail.map((d) => d.msg).join("; ") : "";
    throw new ApiError(response.status, message || `Request failed (${response.status})`);
  }
  return body as T;
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const token = path === "/auth/login" ? null : readSession()?.token ?? null;
  try {
    return await send<T>(path, init, token);
  } catch (e) {
    // An expired or revoked token sends the user back to sign-in; a failed sign-in itself does not.
    if (e instanceof ApiError && e.status === 401 && token) {
      clearSession(token, "Your session has ended. Sign in again to continue.");
    }
    throw e;
  }
}

export const post = <T>(path: string, payload?: unknown) =>
  api<T>(path, { method: "POST", body: payload === undefined ? undefined : JSON.stringify(payload) });

// Audio endpoints need the bearer token, which a bare `new Audio(url)` can't send.
export async function playAudio(path: string): Promise<HTMLAudioElement> {
  const token = readSession()?.token;
  const response = await fetch(path, { headers: token ? { Authorization: `Bearer ${token}` } : {} });
  if (!response.ok) throw new ApiError(response.status, "Audio unavailable");
  const audio = new Audio(URL.createObjectURL(await response.blob()));
  await audio.play();
  return audio;
}
