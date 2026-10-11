import type { ReactNode } from "react";
import { activitySummary, elapsed } from "./activity.ts";
import type { Consult, DetectSnapshot } from "./types.ts";

const activityLabel = (state: string) => ({
  "Video Consult": "On video", "Video Consult In Progress": "On video", "Hospital Call": "On hospital call",
  "Camera Active, No Session": "External camera activity", "Documentation": "Documentation",
}[state] ?? state);
const reasonLabel = (reason: string) => reason.split(", ").map((r) => ({ busy: "Busy", ringing: "Call ringing", cooldown: "Call cooldown", unavailable: "Unavailable" }[r] ?? r)).join(" · ");
const flagLabel = (flag: string) => ({ external_platform: "Camera active without a Synapse video session", unverified: "Agent offline or unknown; camera state unverified", stranded_consults: "Unavailable with open consults" }[flag] ?? flag.replaceAll("_", " "));

function Metrics({ label, items }: { label: string; items: [ReactNode, string, string][] }) {
  return <div className="activity-metrics" aria-label={label}>{items.map(([value, name, note]) => <article key={name}><strong>{value}</strong><div><span>{name}</span><small>{note}</small></div></article>)}</div>;
}

// Consults page: stage counts and the two imaging queues. Selecting a waiting consult jumps to its row in the board.
export function ConsultQueues({ detect, onReview }: { detect: DetectSnapshot; onReview: (consultId: string) => void }) {
  const stats = activitySummary(detect.physicians, detect.consults);
  return <>
    <Metrics label="Consult stage counts" items={[
      [detect.consults.length, "Open consults", "active across the network"], [stats.documentation, "Documentation open", "consults pending or being written"],
      [stats.imagingPending, "CT / CTA pending", "consults awaiting imaging"], [stats.imagingReview, "Imaging review", "consults awaiting next step"],
    ]} />
    <div className="waiting-stack">
      <WaitingList title="CT / CTA return pending" subtitle="Imaging has been requested" consults={detect.consults.filter((c) => ["Imaging Pending", "CT/CTA or Imaging Pending"].includes(c.stage))} onReview={onReview} />
      <WaitingList title="Imaging review / video pending" subtitle="Imaging returned; next step pending" consults={detect.consults.filter((c) => c.stage === "Imaging Review")} onReview={onReview} />
    </div>
  </>;
}

// Doctors page: what each physician is doing now, with self-report beside system activity, and signal flags.
export function PhysicianActivity({ detect }: { detect: DetectSnapshot }) {
  const stats = activitySummary(detect.physicians, detect.consults);
  const flagged = detect.physicians.filter((p) => p.flags.length > 0);
  return <>
    <Metrics label="Physician activity counts" items={[
      [`${detect.physicians.filter((p) => p.canTakeCalls).length} of ${detect.physicians.length}`, "Ready for calls", "physicians who can take a call"],
      [stats.video, "Video in progress", "physicians in Synapse"], [stats.calls, "Calls in progress", "physicians on hospital calls"],
      [flagged.length, "Signal flags", "physicians needing verification"],
    ]} />
    <section className="panel physician-workload">
      <div className="panel-head"><div><h3>Physician activity</h3><p className="panel-note">{detect.physicians.length} on shift · activity inferred from system signals</p></div></div>
      <div className="table-scroll" tabIndex={0} role="region" aria-label="Physician activity and shift counts">
        <table><thead><tr><th scope="col">Physician</th><th scope="col">Current activity</th><th scope="col">Sites covering</th><th scope="col" className="num">Calls</th><th scope="col" className="num">Consults</th><th scope="col" className="num">Open docs</th><th scope="col">Shift ends in</th></tr></thead>
        <tbody>{detect.physicians.map((p) => <tr key={p.id}>
          <td><strong>{p.name}</strong><small className="table-sub mono">{p.id}</small></td>
          <td><span className={`activity-state ${p.canTakeCalls ? "available" : "busy"}`}><i />{activityLabel(p.derived)}</span><small className="table-sub">Self-report: {p.status}</small><small className={`routing-state ${p.canTakeCalls ? "available" : ""}`}>{p.canTakeCalls ? "Can take calls" : reasonLabel(p.reason)}{p.helper !== "Online" ? ` · Agent ${p.helper.toLowerCase()}` : ""}</small></td>
          <td><details className="site-list"><summary>{p.hospitals.length} hospitals</summary><ul>{p.hospitals.map((h) => <li key={h.id}>{h.name}<small className="mono">{h.id}</small></li>)}</ul></details></td>
          <td className="num">{p.calls ?? "—"}</td><td className="num">{p.consults ?? "—"}</td><td className={`num ${p.pendingNotes > 0 && p.minutesToShiftEnd !== null && p.minutesToShiftEnd <= 60 ? "risk-number" : ""}`}>{p.pendingNotes}</td>
          <td><span className={p.minutesToShiftEnd !== null && p.minutesToShiftEnd <= 60 ? "shift-ending" : ""}>{p.minutesToShiftEnd === null ? "—" : `${p.minutesToShiftEnd} min`}</span></td>
        </tr>)}</tbody></table>
      </div>
      <p className="data-caption">Calls and consults are shift totals. Open docs includes Note Pending and Documentation. Expand sites to see credentials.</p>
    </section>
  </>;
}

export function SignalVerification({ detect }: { detect: DetectSnapshot }) {
  const flagged = detect.physicians.filter((p) => p.flags.length > 0);
  return <section className="panel signal-watch"><div className="panel-head"><div><h3>Signal verification</h3><p className="panel-note">Physicians whose system signals disagree or can't be confirmed</p></div><span className="badge amber">{flagged.length} flagged</span></div>
    {flagged.map((p) => <div className="verification-row" key={p.id}><strong>{p.name}</strong><p>{p.flags.map(flagLabel).join(". ")}</p></div>)}
    {!flagged.length && <p className="muted">No physician signal flags.</p>}
  </section>;
}

function WaitingList({ title, subtitle, consults, onReview }: { title: string; subtitle: string; consults: Consult[]; onReview: (id: string) => void }) {
  return <section className="panel waiting-panel"><div className="panel-head"><div><h3>{title}</h3><p className="panel-note">{subtitle}</p></div><span className="waiting-count">{consults.length}</span></div>
    {consults.length ? consults.map((c) => <button className="waiting-consult" key={c.id} onClick={() => onReview(c.id)}><span><strong>{c.hospital}</strong><small>{c.id} · {c.type}</small></span><span className={`stage-timer ${c.warningMinutes !== null ? c.level.toLowerCase() : ""}`}>{elapsed(c.minutesInStage)}<small>in stage</small></span></button>) : <p className="muted">No consults waiting.</p>}
  </section>;
}
