import { stagger } from "./ui/motion.ts";
import { Pulse } from "./ui/Pulse.tsx";
import { Brand, ThemeToggle } from "./ui/theme.tsx";
import "./landing.css";

type Role = "coordinator" | "lead" | "physician";

const STEPS: [string, string, string][] = [
  ["Detect", "Consults, stage timers and physician signals are replayed from the event stream and ranked by severity.", "Ranked triage"],
  ["Forecast", "Each hospital's staffing is checked against its minimum across the next 90+ minutes, shift changes included.", "Coverage outlook"],
  ["Decide", "Every off-shift physician is checked against the eligibility rules; the trap check shows what changes if they join.", "Explained candidates"],
  ["Dispatch", "A clinical lead approves the offer, the physician gets a call, and coverage is re-checked on arrival.", "Closed loop"],
];

const ROLE_CARDS: [Role, string, string, string[]][] = [
  ["coordinator", "Coordinator", "Run the network: triage the queue, read the coverage outlook and propose offers.", ["Severity-first attention queue", "Find cover with explained candidates", "Event stream and replay checks"]],
  ["lead", "Clinical lead", "Approve or reject offers and escalations, with the trap check beside every decision.", ["Who else was checked, and why not", "What changes if they accept", "Nothing reaches a physician without you"]],
  ["physician", "Physician", "Answer coverage calls on phone or web. Offers carry hospital names and hours only.", ["Simulated coverage call", "Accept or decline in one tap", "Routing starts on observed arrival"]],
];

const FACTS: [string, string, string][] = [
  ["12", "Reference hospitals", "Official Sevaro kit"],
  ["14", "Reference physicians", "Supplied roster and credentials"],
  ["24 h", "Weekday baselines", "Weekend data not supplied"],
  ["0", "Patient details in offers", "Hospital names and hours only"],
];

export function LandingPage({ onGoToSignIn }: { onGoToSignIn: (role?: Role) => void }) {
  return <div className="landing">
    <header className="landing-bar">
      <Brand />
      <nav aria-label="Overview"><a href="#how">How it works</a><a href="#roles">Workspaces</a><a href="#scope">Scope</a></nav>
      <div className="actions"><ThemeToggle /><button className="btn primary" onClick={() => onGoToSignIn("coordinator")}>Sign in<span aria-hidden="true">→</span></button></div>
    </header>

    <section className="hero">
      <div className="hero-copy">
        <span className="kicker rise"><b>●</b>Tele-neurology command center</span>
        <h1 className="rise" style={stagger(1)}>Time is brain.<em>See the coverage gap before the shift changes.</em></h1>
        <p className="rise" style={stagger(2)}>Cerevia gives Sevaro's operations team one deterministic view of the stroke network: what needs action now, where staffing runs short, and which physician can cover, approved by a clinical lead before anyone is called.</p>
        <div className="actions rise" style={stagger(3)}>
          <button className="btn primary" onClick={() => onGoToSignIn("coordinator")}>Open the command center<span aria-hidden="true">→</span></button>
          <button className="btn" onClick={() => onGoToSignIn("physician")}>Sign in as physician</button>
        </div>
      </div>
      <figure className="plate rise" style={stagger(2)}>
        <div className="plate-frame"><img src="/us_network_map.jpg" alt="Illustrative US network map; not the official hospital locations" /></div>
        <figcaption><span className="kicker">Plate I · Network</span>Illustrative map; locations are not live hospital data.</figcaption>
        <div className="plate-monitor" aria-hidden="true"><Pulse /><span>Network monitor</span></div>
      </figure>
    </section>

    <section id="how" className="landing-section">
      <header className="landing-head"><span className="kicker"><b>01</b>How it works</span><h2>One loop, from signal to covered shift.</h2></header>
      <ol className="steps-row">{STEPS.map(([title, text, tag], i) => <li key={title} className="rise" style={stagger(i)}>
        <span className="step-index">{String(i + 1).padStart(2, "0")}</span><h3>{title}</h3><p>{text}</p><span className="badge teal">{tag}</span>
      </li>)}</ol>
    </section>

    <section id="roles" className="landing-section">
      <header className="landing-head"><span className="kicker"><b>02</b>Workspaces</span><h2>Three roles, one record.</h2></header>
      <div className="role-columns">{ROLE_CARDS.map(([role, title, text, points], i) => <article key={role} className="role-column rise" style={stagger(i)}>
        <span className="kicker">{role === "physician" ? "Phone and web" : "Desktop web"}</span>
        <h3>{title}</h3><p>{text}</p>
        <ul>{points.map((point) => <li key={point}>{point}</li>)}</ul>
        <button className="btn" onClick={() => onGoToSignIn(role)}>Sign in as {title.toLowerCase()}<span aria-hidden="true">→</span></button>
      </article>)}</div>
    </section>

    <section id="scope" className="landing-section">
      <header className="landing-head"><span className="kicker"><b>03</b>Prototype scope</span><h2>Decision support, honestly scoped.</h2>
        <p>Replays the supplied challenge data and supports reviewed staffing decisions. Clinical outcomes and production compliance have not been validated.</p></header>
      <dl className="facts-row">{FACTS.map(([value, label, note], i) => <div key={label} className="rise" style={stagger(i)}><dt>{value}</dt><dd><b>{label}</b>{note}</dd></div>)}</dl>
    </section>

    <footer className="colophon">
      <div><Brand /><p>Deterministic rules, explained decisions, a clinical lead in the loop.</p></div>
      <div><span className="kicker">Built for</span><p>Sevaro Tele-Stroke Challenge</p></div>
      <div><span className="kicker">Status</span><p>Decision support prototype · © 2026 Cerevia Systems</p></div>
    </footer>
  </div>;
}
