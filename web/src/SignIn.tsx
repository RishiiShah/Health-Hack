import { useState, type FormEvent } from "react";
import { DEMO, post } from "./api/client.ts";
import { saveSession, type Session } from "./auth/session.ts";
import { stagger } from "./ui/motion.ts";
import { Pulse } from "./ui/Pulse.tsx";
import { Brand, ThemeToggle } from "./ui/theme.tsx";
import "./auth/auth.css";

type Role = "coordinator" | "lead" | "physician";
// Demo accounts accept any password; they exist only when VITE_DEMO_DATA=1.
const DEMO_EMAILS: Record<Role, string> = { coordinator: "coord@demo.sevaro", lead: "lead@demo.sevaro", physician: "okafor@demo.sevaro" };
const ROLES: [Role, string, string][] = [
  ["coordinator", "Coordinator", "Watch the network and dispatch"],
  ["lead", "Clinical lead", "Approve offers and escalations"],
  ["physician", "Physician", "Your shifts and consults"],
];
const FACTS: [string, string][] = [["90+ min", "coverage forecast"], ["3 roles", "in every offer decision"], ["0", "patient details in offers"]];

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
  const roleTitle = ROLES.find(([role]) => role === selectedRole)![1];

  return <div className="auth">
    <aside className="auth-story">
      <button type="button" className="auth-brand" onClick={onBackToLanding} aria-label="Back to overview"><Brand /></button>
      <div className="auth-pitch">
        <span className="kicker rise"><b>●</b>Sevaro tele-stroke operations</span>
        <h1 className="rise" style={stagger(1)}>Time is brain.<em>Keep every hospital covered.</em></h1>
        <p className="rise" style={stagger(2)}>Ranked triage, a coverage outlook across the network, and lead-approved physician offers, replayed from the Sevaro challenge kit.</p>
        <div className="auth-trace rise" style={stagger(3)}><Pulse /><span>Network monitor · live</span></div>
      </div>
      <dl className="auth-facts">{FACTS.map(([value, label], i) => <div key={label} className="rise" style={stagger(4 + i)}><dt>{value}</dt><dd>{label}</dd></div>)}</dl>
    </aside>

    <main className="auth-panel">
      <div className="auth-top"><button type="button" className="btn ghost" onClick={onBackToLanding}><span aria-hidden="true">←</span> Overview</button><ThemeToggle /></div>
      <section className="auth-form-wrap" aria-labelledby="signin-title">
        <div className="rise" style={stagger(1)}>
          <h2 id="signin-title">Sign in</h2>
          <p className="muted">Choose your role to open your workspace.</p>
          {notice && <p role="status" className="notice">{notice}</p>}
        </div>
        <div role="group" aria-label="Operating role" className="role-picker rise" style={stagger(2)}>
          {ROLES.map(([role, title, description]) => <button type="button" key={role} aria-pressed={selectedRole === role} onClick={() => selectRole(role)}><b>{title}</b><small>{description}</small></button>)}
        </div>
        <form onSubmit={handleSubmit} className="auth-form rise" style={stagger(3)}>
          <label className="field">
            <span className="field-label">Work email</span>
            <input id="signin-email" type="email" required autoComplete="username" placeholder="name@sevaro.com" value={email} onChange={(event) => setEmail(event.target.value)} />
          </label>
          <div className="field">
            <div className="field-label"><label htmlFor="signin-password">Password</label><button type="button" onClick={() => setForgot(!forgot)}>Forgot it?</button></div>
            <input id="signin-password" type="password" required autoComplete="current-password" value={password} onChange={(event) => setPassword(event.target.value)} />
            {forgot && <p className="hint field-hint">Ask your Sevaro administrator to reset it.</p>}
          </div>
          <button type="submit" disabled={busy} className="btn primary block">{busy ? "Signing in…" : `Sign in as ${roleTitle}`}<span aria-hidden="true">→</span></button>
          {error && <p role="alert" className="error auth-error">{error}</p>}
        </form>
        {DEMO && <div className="auth-demo rise" style={stagger(4)}>
          <p>Or open a demo account</p>
          {ROLES.map(([role, title]) => <button key={role} disabled={busy} onClick={() => void signIn(DEMO_EMAILS[role], "demo", role)}><span>{DEMO_EMAILS[role]}</span><b>{title} →</b></button>)}
        </div>}
      </section>
      <p className="auth-foot">© 2026 Overlap Systems · Sevaro Tele-Stroke Challenge</p>
    </main>
  </div>;
}
