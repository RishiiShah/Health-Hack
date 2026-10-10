import { STATIC_OFFERS, STATIC_SNAPSHOT } from "./live.ts";

export const LOCAL_MOCK_MODE = true;

// Local demos stay entirely in memory; no proxy or backend request is needed.
export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

function token(): string | null {
  try {
    return sessionStorage.getItem("cc_token");
  } catch {
    return null;
  }
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  if (LOCAL_MOCK_MODE) {
    if (path === "/snapshot") return STATIC_SNAPSHOT as T;
    if (path === "/offers") return STATIC_OFFERS as T;
    return {} as T;
  }
  const headers = new Headers(init.headers);
  const bearer = token();
  if (bearer) headers.set("Authorization", `Bearer ${bearer}`);
  if (typeof init.body === "string" && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");
  const response = await fetch(path, { ...init, headers });
  const body = response.headers.get("Content-Type")?.includes("json") ? await response.json() : await response.text();
  if (!response.ok) {
    const detail = typeof body === "object" && body && "detail" in body ? body.detail : body;
    throw new ApiError(response.status, typeof detail === "string" && detail ? detail : `Request failed (${response.status})`);
  }
  return body as T;
}

export const post = <T>(path: string, payload?: unknown) =>
  api<T>(path, { method: "POST", body: payload === undefined ? undefined : JSON.stringify(payload) });
