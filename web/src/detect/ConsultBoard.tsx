import { useState } from "react";
import { elapsed } from "./activity.ts";
import type { Consult } from "./types.ts";

export function ConsultBoard({ consults }: { consults: Consult[] }) {
  const [query, setQuery] = useState("");
  const [priority, setPriority] = useState("All");
  const priorityOrder: Record<string, number> = { Critical: 0, Warning: 1, Info: 2, Normal: 3 };
  const ordered = [...consults].sort((a, b) => (priorityOrder[a.level] ?? 3) - (priorityOrder[b.level] ?? 3) || (a.id < b.id ? -1 : a.id > b.id ? 1 : 0));
  const shown = ordered.filter((c) => (priority === "All" || c.level === priority)
    && [c.id, c.hospital, c.physicianName ?? "Unassigned", c.type, c.stage].some((s) => s.toLowerCase().includes(query.toLowerCase())));
  return <section className="panel table-panel consult-lifecycle">
    <div className="panel-head"><div><h3>Consult lifecycle</h3><p className="panel-note">{consults.length} open consults · independent of physician activity</p></div>
      <div className="board-controls"><label><span className="sr-only">Search consults</span><input type="search" placeholder="Search consult, hospital, physician…" value={query} onChange={(e) => setQuery(e.target.value)} /></label>
        <label><span className="sr-only">Consult priority</span><select value={priority} onChange={(e) => setPriority(e.target.value)}>{["All", "Critical", "Warning", "Info", "Normal"].map((p) => <option key={p} value={p}>{p === "All" ? "All priorities" : p === "Normal" ? "Routine" : p}</option>)}</select></label></div>
    </div>
    <div className="table-scroll" tabIndex={0} role="region" aria-label="Consult lifecycle and stage timers"><table>
      <thead><tr><th scope="col">Consult / hospital</th><th scope="col">Type</th><th scope="col">Assigned physician</th><th scope="col">Current stage</th><th scope="col">Time in stage<small className="table-sub block font-normal text-[10px] text-[#526579]">mm:ss</small></th><th scope="col">Total elapsed</th><th scope="col">Flag thresholds</th><th scope="col">Priority</th></tr></thead>
      <tbody>{shown.map((c) => {
        const isCritical = c.level === "Critical";
        const isWarning = c.level === "Warning";
        const rowClass = isCritical ? "row-critical" : isWarning ? "row-warning" : "row-normal";
        return (
          <tr key={c.id} id={`consult-${c.id}`} className={rowClass} tabIndex={-1}>
            <td><strong className="mono">{c.id}</strong><small className="table-sub">{c.hospital}</small></td>
            <td><span className={`consult-type ${c.type === "Stroke" ? "stroke" : ""}`}>{c.type}</span></td>
            <td>{c.physicianName ?? <span className="unassigned-label">Unassigned</span>}{c.routingFailures > 0 && <small className="table-sub risk-number">{c.routingFailures} routing failures</small>}</td>
            <td><span className="stage-label">{c.stage}</span></td>
            <td className="mono">{elapsed(c.minutesInStage)}</td>
            <td className="mono">{c.minutesSinceReceived} min</td>
            <td>{c.warningMinutes !== null ? <><span className="mono">{c.limit}</span><small className="table-sub">Warning &nbsp; Critical</small></> : <span className="muted">—</span>}</td>
            <td><span className={`badge ${isCritical ? "red" : isWarning ? "amber" : "neutral"}`}>{c.level === "Normal" ? "Routine" : c.level}</span></td>
          </tr>
        );
      })}</tbody>
    </table>{!shown.length && <p className="empty-state">No consults match this search.</p>}</div>
    <p className="data-caption">Stage timers use mm:ss. Total elapsed is shown in minutes.</p>
  </section>;
}
