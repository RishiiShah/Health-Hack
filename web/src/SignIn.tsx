import { useState, type FormEvent } from "react";
import { DEMO, post } from "./api/client.ts";
import { saveSession, type Session } from "./auth/session.ts";

type Role = "coordinator" | "lead" | "physician";
// Demo accounts accept any password; they exist only when VITE_DEMO_DATA=1.
const DEMO_EMAILS: Record<Role, string> = { coordinator: "coord@demo.sevaro", lead: "lead@demo.sevaro", physician: "okafor@demo.sevaro" };

export function SignIn({ onSignedIn, onBackToLanding, notice, initialRole = "coordinator" }: { initialRole?: Role; onSignedIn: (session: Session) => void; onBackToLanding: () => void; notice?: string }) {
  const [selectedRole, setSelectedRole] = useState<Role>(initialRole);
  const [email, setEmail] = useState(DEMO ? DEMO_EMAILS[initialRole] : "");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [forgot, setForgot] = useState(false);
  const selectRole = (role: Role) => { setSelectedRole(role); setError(null); if (DEMO) setEmail(DEMO_EMAILS[role]); };
  const signIn = async (address: string, secret: string, role: Role) => {
    setBusy(true);
    setError(null);
    try {
      // The account decides the role; the portal only lets the server say "sign in as … instead" on a mismatch.
      const session = await post<Session>("/auth/login", { email: address.trim(), password: secret, portal: role === "physician" ? "physician" : "operations" });
      saveSession(session);
      onSignedIn(session);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };
  const handleSubmit = (event: FormEvent) => { event.preventDefault(); if (!busy) void signIn(email, password, selectedRole); };
  const roleTitle = selectedRole === "coordinator" ? "Coordinator" : selectedRole === "lead" ? "Clinical Lead" : "Physician";

  return (
    <div className="min-h-screen bg-[#28323D] text-[#F5F3ED] flex flex-col p-6" style={{ background: "radial-gradient(circle at 50% 25%, #364550 0%, #28323D 75%)" }}>
      {/* Top Header */}
      <div className="max-w-4xl mx-auto w-full flex items-center justify-between pb-6">
        <button onClick={onBackToLanding} className="flex items-center gap-2 text-[#F5F3ED] hover:text-[#B8D8EB] transition">
          <span className="relative block h-5 w-6">
            <i className="absolute left-0 top-0 h-3.5 w-3.5 -skew-x-12 rounded-sm bg-[#B8D8EB]" />
            <i className="absolute left-2.5 top-1.5 h-3.5 w-3.5 -skew-x-12 rounded-sm bg-[#101B2B]" />
          </span>
          <strong className="text-base font-bold tracking-tight text-[#F5F3ED]">overlap</strong>
        </button>
        <button onClick={onBackToLanding} className="text-xs font-medium text-[#BCC9D2] hover:text-[#F5F3ED] transition">
          ← Back to Overview
        </button>
      </div>

      {/* Comfortably Centered Sign-In Box */}
      <div className="flex-1 flex items-center justify-center -mt-8 py-6">
        <div className="max-w-md w-full bg-[#F1F0EC] text-[#101B2B] rounded-3xl p-8 border border-[#E2E0D8] shadow-2xl space-y-6">
          <div>
            <h1 className="text-2xl font-bold font-heading text-[#101B2B]">Sign in</h1>
            <p className="text-xs text-[#5D6D7E] mt-1">Select your operating role to access your dashboard</p>
            {notice && <p role="status" className="text-xs text-[#8A5A00] mt-2 bg-[#FDF6E9] p-2 rounded-lg border border-[#D6A451]/30">{notice}</p>}
          </div>

          <div>
            <label className="block text-xs font-semibold text-[#101B2B] mb-2">I work as</label>
            <div className="grid grid-cols-3 gap-2">
              {([
                ["coordinator", "Coordinator", "Watch network & dispatch"],
                ["lead", "Clinical lead", "Approve offers & escalations"],
                ["physician", "Physician", "Your shifts & consults"],
              ] as const).map(([role, title, description]) => (
                <button
                  type="button"
                  key={role}
                  onClick={() => selectRole(role)}
                  className={`p-3 rounded-2xl text-left border transition-all ${
                    selectedRole === role
                      ? "border-[#B8D8EB] bg-[#E2ECF3] ring-2 ring-[#B8D8EB]/60"
                      : "border-[#E2DFD8] bg-[#FAF9F6] hover:bg-[#E8E6E0]"
                  }`}
                >
                  <div className="text-xs font-bold text-[#101B2B]">{title}</div>
                  <div className="text-[10px] text-[#5D6D7E] mt-1 leading-snug">{description}</div>
                </button>
              ))}
            </div>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-xs font-medium text-[#101B2B] mb-1">Work email</label>
              <input
                type="email"
                required
                autoComplete="username"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                className="w-full text-xs p-3 rounded-xl border border-[#D9D6CE] bg-[#FAF9F6] text-[#101B2B] focus:outline-none focus:ring-2 focus:ring-[#B8D8EB] font-mono"
              />
            </div>
            <div>
              <div className="flex justify-between items-center mb-1">
                <label className="text-xs font-medium text-[#101B2B]">Password</label>
                <button type="button" onClick={() => setForgot(!forgot)} className="text-[11px] text-[#284E67] font-semibold cursor-pointer hover:underline">
                  Forgot it?
                </button>
              </div>
              <input
                type="password"
                required
                autoComplete="current-password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                className="w-full text-xs p-3 rounded-xl border border-[#D9D6CE] bg-[#FAF9F6] text-[#101B2B] focus:outline-none focus:ring-2 focus:ring-[#B8D8EB] font-mono"
              />
              {forgot && <p className="text-[11px] text-[#5D6D7E] mt-1">Ask your Sevaro administrator to reset it.</p>}
            </div>
            <button
              type="submit"
              disabled={busy}
              className="w-full py-3.5 bg-[#B8D8EB] hover:bg-[#A6CAE0] text-[#101B2B] rounded-xl font-bold text-xs shadow-md transition-all hover:scale-[1.01] active:scale-[0.99] disabled:opacity-60 cursor-pointer"
            >
              {busy ? "Signing in…" : `Sign in as ${roleTitle}`}
            </button>
            {error && <p role="alert" className="text-xs text-[#C93B2B] bg-[#FDEEEB] p-2 rounded-lg border border-[#F3C5BF]">{error}</p>}
          </form>

          {DEMO && (
            <div className="pt-4 border-t border-[#E2DFD8] text-center">
              <div className="text-[11px] text-[#5D6D7E] mb-2 font-medium">Or 1-click launch into demo account:</div>
              <div className="flex flex-col gap-1.5 text-xs font-mono">
                {([
                  ["coordinator", DEMO_EMAILS.coordinator, "Coordinator"],
                  ["lead", DEMO_EMAILS.lead, "Lead"],
                  ["physician", DEMO_EMAILS.physician, "Physician"],
                ] as const).map(([role, address, label]) => (
                  <button
                    key={role}
                    disabled={busy}
                    onClick={() => void signIn(address, "demo", role as Role)}
                    className="py-2 px-3 bg-[#E8E6E0] hover:bg-[#DDD9D0] text-[#101B2B] border border-[#D9D6CE] rounded-lg text-left flex justify-between cursor-pointer transition"
                  >
                    <span>{address}</span>
                    <span className="text-[#101B2B] font-sans font-bold">Launch {label} →</span>
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
      <div className="text-center text-[11px] text-[#BCC9D2]">© 2026 Overlap Systems · Sevaro Tele-Stroke Challenge</div>
    </div>
  );
}
