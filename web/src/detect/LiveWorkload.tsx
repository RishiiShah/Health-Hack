import { activitySummary, elapsed } from "./activity.ts";
import type { Consult, DetectSnapshot } from "./types.ts";

const activityLabel = (state: string) => ({
  "Video Consult": "On video", "Video Consult In Progress": "On video", "Hospital Call": "On hospital call",
  "Camera Active, No Session": "External camera activity", "Documentation": "Documentation",
}[state] ?? state);
const reasonLabel = (reason: string) => reason.split(", ").map((r) => ({ busy: "Busy", ringing: "Call ringing", cooldown: "Call cooldown", unavailable: "Unavailable" }[r] ?? r)).join(" · ");

export function LiveWorkload({ detect, onReview }: { detect: DetectSnapshot; onReview: (consultId: string) => void }) {
  const stats = activitySummary(detect.physicians, detect.consults);
  const metrics = [
    [stats.video, "Video in progress", "physicians in Synapse"], [stats.calls, "Calls in progress", "physicians on hospital calls"],
    [stats.documentation, "Documentation open", "consults pending or being written"], [stats.imagingReview, "Imaging review", "consults awaiting next step"],
    [stats.imagingPending, "CT / CTA pending", "consults awaiting imaging"],
  ];
  return <>
    <div className="activity-metrics" aria-label="Current workload counts">{metrics.map(([value, label, note]) => <article key={label}><strong>{value}</strong><div><span>{label}</span><small>{note}</small></div></article>)}</div>
    <div className="live-workload-grid">
      <section className="panel physician-workload">
        <div className="panel-head"><div><h3>Physician activity</h3><p className="panel-note">{detect.physicians.length} on shift · activity inferred from system signals</p></div><a className="text-link" href="#doctors">Full physician board ↗</a></div>
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
      <aside className="waiting-stack">
        <WaitingList title="CT / CTA return pending" subtitle="Imaging has been requested" consults={detect.consults.filter((c) => ["Imaging Pending", "CT/CTA or Imaging Pending"].includes(c.stage))} onReview={onReview} />
        <WaitingList title="Imaging review / video pending" subtitle="Imaging returned; next step pending" consults={detect.consults.filter((c) => c.stage === "Imaging Review")} onReview={onReview} />
        <section className="panel signal-watch"><div className="panel-head"><h3>Signal verification</h3><span className="badge amber">{detect.physicians.filter((p) => p.flags.length > 0).length} flagged</span></div>
          {detect.physicians.filter((p) => p.flags.length > 0).map((p) => <div className="verification-row" key={p.id}><strong>{p.name}</strong><p>{p.flags.map((f) => ({ external_platform: "Camera active without a Synapse video session", unverified: "Agent offline or unknown; camera state unverified", stranded_consults: "Unavailable with open consults" }[f] ?? f.replaceAll("_", " "))).join(". ")}</p></div>)}
          {!detect.physicians.some((p) => p.flags.length > 0) && <p className="muted">No physician signal flags.</p>}
        </section>
      </aside>
    </div>
  </>;
}

function WaitingList({ title, subtitle, consults, onReview }: { title: string; subtitle: string; consults: Consult[]; onReview: (id: string) => void }) {
  return <section className="panel waiting-panel"><div className="panel-head"><div><h3>{title}</h3><p className="panel-note">{subtitle}</p></div><span className="waiting-count">{consults.length}</span></div>
    {consults.length ? consults.map((c) => <button className="waiting-consult" key={c.id} onClick={() => onReview(c.id)}><span><strong>{c.hospital}</strong><small>{c.id} · {c.type}</small></span><span className={`stage-timer ${c.warningMinutes !== null ? c.level.toLowerCase() : ""}`}>{elapsed(c.minutesInStage)}<small>in stage</small></span></button>) : <p className="muted">No consults waiting.</p>}
  </section>;
}
