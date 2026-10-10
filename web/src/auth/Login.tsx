import { useState, type FormEvent } from "react";
import { DEMO, post } from "../api/client.ts";
import { saveSession, type Session } from "./session.ts";
import "./auth.css";

export function Login({ onSignedIn, notice }: { onSignedIn: (s: Session) => void; notice?: string }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [forgot, setForgot] = useState(false);
  const [showPassword, setShowPassword] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (busy) return;
    setBusy(true);
    setError(null);
    try {
      const session = await post<Session>("/auth/login", { email: email.trim(), password });
      saveSession(session);
      onSignedIn(session);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="signin-page">
      <header className="signin-brand">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M2 12h4l3-7 4 14 3-7h6" /></svg>
        Sevaro Command
      </header>
      <main className="signin-main">
        <form className="signin" onSubmit={submit} aria-busy={busy}>
          <h1>Sign in</h1>
          <p className="signin-intro">Use your work account. We'll open the right workspace for you.</p>
          {notice && <p className="small" role="status">{notice}</p>}
          <label className="field-label" htmlFor="email">Work email</label>
          <input id="email" name="username" type="email" autoComplete="username" autoCapitalize="none" spellCheck={false} placeholder="name@sevaro.com" required disabled={busy} value={email} onChange={(e) => setEmail(e.target.value)} />
          <div className="field-label">
            <label htmlFor="password">Password</label>
            <button type="button" onClick={() => setForgot(!forgot)}>Forgot it?</button>
          </div>
          <div className="password-field"><input id="password" name="password" type={showPassword ? "text" : "password"} autoComplete="current-password" required disabled={busy} value={password} onChange={(e) => setPassword(e.target.value)} /><button type="button" aria-label={showPassword ? "Hide password" : "Show password"} aria-pressed={showPassword} onClick={() => setShowPassword(!showPassword)}>{showPassword ? "Hide" : "Show"}</button></div>
          {forgot && <p className="hint">Ask your Sevaro administrator to reset it.</p>}
          <button className="submit" disabled={busy}>{busy ? "Signing in…" : "Sign in"}</button>
          {error && <p className="error" role="alert">{error}</p>}
          <hr />
          <p className="small">Access is based on your account's role.</p>
          {DEMO && (
            <p className="small">
              Demo accounts: <code>coordinator@demo.sevaro</code>, <code>lead@demo.sevaro</code> and <code>okafor@demo.sevaro</code>, any password.
            </p>
          )}
        </form>
      </main>
      <footer className="signin-footer">Demo build. Synthetic data, no patient information.</footer>
    </div>
  );
}
