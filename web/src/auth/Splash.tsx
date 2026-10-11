// Shown while a saved session is checked with the server, laid out like sign-in.
import { Pulse } from "../ui/Pulse.tsx";
import { Brand } from "../ui/theme.tsx";
import { clearSession } from "./session.ts";
import "./auth.css";

export function Splash({ error, onRetry }: { error: string | null; onRetry: () => void }) {
  return <div className="splash">
    <aside className="splash-side"><Brand /><span className="kicker">Sevaro tele-stroke operations</span></aside>
    <main className="splash-main">
      <Pulse live={!error} />
      <h1 className="rise">Welcome back</h1>
      <p role="status" className={error ? "error" : "muted"}>{error ?? "Checking your session…"}</p>
      {error && <div className="actions"><button className="btn primary" onClick={onRetry}>Try again</button><button className="btn" onClick={() => clearSession()}>Use another account</button></div>}
    </main>
  </div>;
}
