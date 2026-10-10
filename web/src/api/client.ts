// Minimal scaffold for Anish to replace: fetch wrapper with the bearer token and typed errors.
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
