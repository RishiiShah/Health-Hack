// The signed-in account, kept for this browser tab only. The server decides every permission; this only picks screens.
export type Role = "coordinator" | "lead" | "physician";
export type User = { email: string; name: string; role: Role; role_label: string; physician_id: string | null };
export type Session = { token: string; expires_at: number; user: User };

const KEY = "cc_session";
export const SIGNED_OUT = "cc:signed-out";
let memory: Session | null | undefined;

export function isUser(value: unknown): value is User {
  if (!value || typeof value !== "object") return false;
  const user = value as User;
  return typeof user.email === "string" && typeof user.name === "string"
    && typeof user.role_label === "string" && ["coordinator", "lead", "physician"].includes(user.role)
    && (user.role === "physician" ? typeof user.physician_id === "string" && !!user.physician_id : user.physician_id === null);
}

function storedSession(): Session | null {
  if (memory !== undefined) return memory;
  try {
    const value = JSON.parse(sessionStorage.getItem(KEY) ?? "null");
    memory = value && typeof value.token === "string" && value.token.length > 0
      && typeof value.expires_at === "number" && Number.isFinite(value.expires_at) && isUser(value.user) ? value : null;
  } catch {
    memory = null;
  }
  return memory ?? null;
}

export function readSession(): Session | null {
  const session = storedSession();
  return session && session.expires_at * 1000 > Date.now() ? session : null;
}

export function saveSession(session: Session) {
  memory = session;
  try {
    sessionStorage.setItem(KEY, JSON.stringify(session));
  } catch {
    // Private mode without storage: the session lasts until reload.
  }
}

export function clearSession(expectedToken?: string, message?: string) {
  // Requests sent before a new login must not sign out the newer account.
  if (expectedToken !== undefined && storedSession()?.token !== expectedToken) return;
  memory = null;
  try {
    sessionStorage.removeItem(KEY);
  } catch {
    // Nothing stored.
  }
  dispatchEvent(new CustomEvent(SIGNED_OUT, { detail: message }));
}

// Which top-level screens each role sees.
export const PAGES_BY_ROLE: Record<Role, readonly string[]> = {
  coordinator: ["command", "consults", "doctors", "schedule", "audit", "data"],
  lead: ["approvals", "audit", "consults", "data"],
  physician: ["shift", "offers", "settings"],
};
