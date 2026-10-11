import { useState } from "react";
import { clockTime } from "../act/time.ts";
import { cellText, cellTone, stepLabel } from "./cells.ts";
import type { Coverage, CoverageCell } from "./types.ts";
import "./forecast.css";

type Selected = { hospital: string; cell: CoverageCell };

function statusLabel(cell: CoverageCell): string {
  if (cell.status === "unknown") return "Unknown";
  if (cell.status === "gap") return cell.schedule_incomplete ? "Shift unconfirmed" : "Below minimum";
  return cell.status === "at_minimum" ? "At minimum" : "Above minimum";
}

export function CoverageGrid({ coverage, onFindCover }: { coverage?: Coverage; onFindCover: (gapId: string) => void }) {
  const [selection, setSelection] = useState<{ hospitalId: string; at: string } | null>(null);
  const [attentionOnly, setAttentionOnly] = useState(false);

  if (!coverage?.supported || !coverage.steps || !coverage.hospitals) {
    return (
      <section className="panel coverage">
        <div className="panel-head"><h2>Coverage, next 90 minutes</h2></div>
        <p className="unavailable">Not available yet: the server doesn't send the coverage forecast.</p>
      </section>
    );
  }

  const hospitals = coverage.hospitals;
  const needsAttention = (h: typeof hospitals[number]) => h.nobody_reachable_now || h.cells.some(c => c.status === "gap" || c.status === "unknown" || c.unverified);
  const visible = attentionOnly ? hospitals.filter(needsAttention) : hospitals;
  const selectedHospital = visible.find(h => h.hospital_id === selection?.hospitalId) ?? visible.find(h => h.cells.some(c => c.status === "gap")) ?? visible[0];
  const selectedCell = selectedHospital?.cells.find(c => c.at === selection?.at) ?? selectedHospital?.cells.find(c => c.status === "gap") ?? selectedHospital?.cells[0];
  const gapsNow = hospitals.filter(h => h.cells[0]?.status === "gap").length;
  const atMinimum = hospitals.filter(h => h.cells[0]?.status === "at_minimum").length;
  const futureGaps = hospitals.filter(h => h.cells.slice(1).some(c => c.status === "gap")).length;

  return (
    <section className="panel coverage">
      <div className="panel-head coverage-heading">
        <div><span className="coverage-eyebrow">Staffing outlook</span><h2>Coverage, next 90 minutes</h2><p>Compare staffing with the minimum at each hospital. Select a time to review coverage.</p></div>
        <span className="coverage-horizon">15-minute intervals</span>
      </div>
      <div className="coverage-summary">
        <div className={gapsNow ? "summary-risk" : ""}><strong>{gapsNow}</strong><span>Below minimum now<small>Hospitals needing coverage</small></span></div>
        <div><strong>{atMinimum}</strong><span>At minimum now<small>No staffing buffer</small></span></div>
        <div className={futureGaps ? "summary-risk" : ""}><strong>{futureGaps}</strong><span>Upcoming gaps<small>Hospitals short in a future interval</small></span></div>
      </div>
      <div className="coverage-toolbar">
        <div className="coverage-filters" role="group" aria-label="Coverage hospitals">
          <button aria-pressed={!attentionOnly} onClick={() => setAttentionOnly(false)}>All hospitals <span>{hospitals.length}</span></button>
          <button aria-pressed={attentionOnly} onClick={() => setAttentionOnly(true)}>Needs attention <span>{hospitals.filter(needsAttention).length}</span></button>
        </div>
        <span className="coverage-count-hint">Each cell: <b>staffed / minimum</b></span>
      </div>
      <div className="coverage-workspace">
        <div className="coverage-matrix">
          <p className="coverage-scroll-hint">Scroll across to see all forecast intervals →</p>
          <div className="table-wrap" tabIndex={0} role="region" aria-label="Hospital coverage over the next 90 minutes">
            <table>
              <thead><tr><th className="hosp">Hospital</th>{coverage.steps.map((at, i) => <th key={at} className={i === 0 ? "current-time" : undefined}>{stepLabel(at, i)}<small>{i === 0 ? "Current" : `+${i * 15} min`}</small></th>)}</tr></thead>
              <tbody>
                {visible.map(h => (
                  <tr key={h.hospital_id}>
                    <th scope="row" className="name">{h.hospital_name}{h.nobody_reachable_now && <span className="reachability-label">No one reachable now</span>}</th>
                    {h.cells.map((cell, i) => (
                      <td key={cell.at} className="cell">
                        <button className={cellTone(cell)} aria-pressed={selectedHospital?.hospital_id === h.hospital_id && selectedCell?.at === cell.at}
                          aria-label={`${h.hospital_name}, ${stepLabel(cell.at, i)}: ${cellText(cell)}, ${statusLabel(cell)}${cell.unverified ? ", unverified" : ""}${cell.gap_id ? ", coverage action available" : ""}`}
                          onClick={() => setSelection({ hospitalId: h.hospital_id, at: cell.at })}>
                          <strong>{cellText(cell)}</strong><small>{cell.unverified ? "Unverified" : cell.status === "gap" ? cell.schedule_incomplete ? "Check shift" : "Short" : cell.status === "at_minimum" ? "At min" : cell.status === "above_minimum" ? "Buffer" : "Unknown"}</small>
                        </button>
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
            {!visible.length && <p className="empty-state">No hospitals need attention in this forecast.</p>}
          </div>
          <div className="legend">
            <span className="key key-gap">Below minimum</span><span className="key key-at">At minimum</span><span className="key key-above">Above minimum</span><span className="key key-maybe">Unconfirmed shift</span>
          </div>
        </div>
        {selectedHospital && selectedCell && <CellDetail hospital={selectedHospital.hospital_name} cell={selectedCell} onFindCover={onFindCover} />}
      </div>
      {coverage.assumption && <details className="forecast-assumption"><summary>How this forecast is calculated</summary><p>{coverage.assumption}</p></details>}
    </section>
  );
}

function CellDetail({ hospital, cell, onFindCover }: Selected & { onFindCover: (gapId: string) => void }) {
  return (
    <aside className={`cell-detail detail-${cellTone(cell)}`} aria-label="Selected coverage details" aria-live="polite">
      <span className="coverage-eyebrow">Selected interval · {clockTime(cell.at)}</span>
      <h3>{hospital}</h3>
      <span className={`coverage-status ${cellTone(cell)}`}>{statusLabel(cell)}</span>
      <div className="coverage-detail-counts"><div><strong>{cell.count ?? "—"}</strong><span>Staffed</span></div><div><strong>{cell.required ?? "—"}</strong><span>Minimum</span></div></div>
      <div className="coverage-physicians"><h4>Counted physicians</h4><p>{cell.physician_ids.length ? cell.physician_ids.join(", ") : "No physicians counted"}</p></div>
      {cell.incomplete_physician_ids.length > 0 && <p className="coverage-caution">Incomplete schedule: {cell.incomplete_physician_ids.join(", ")}</p>}
      {cell.unverified && <p className="coverage-caution">Includes an unverified physician. Confirm availability before relying on this coverage.</p>}
      {cell.gap_id ? <button className="btn primary" onClick={() => onFindCover(cell.gap_id!)}>Find cover <span aria-hidden="true">→</span></button> : <p className="coverage-detail-note">{cell.status === "unknown" ? "Coverage cannot be verified for this interval." : cell.status === "gap" ? "No coverage action is available for this interval." : "Minimum staffing is met for this interval."}</p>}
    </aside>
  );
}
