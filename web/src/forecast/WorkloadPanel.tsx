import type { Level, Workload } from "./types.ts";
import "./forecast.css";

const levelBadge = (level: Level, text: string) =>
  level ? <span className={`badge ${level === "Critical" ? "red" : "amber"}`}>{text} · {level}</span> : null;

export function WorkloadPanel({ workload }: { workload?: Workload }) {
  return (
    <section className="panel">
      <div className="panel-head">
        <h2>Workload and shift-end risk</h2>
        <span className="note">ranked by risk</span>
      </div>
      {!workload?.supported || !workload.items ? (
        <p className="unavailable">Not available yet: the server doesn't send workload.</p>
      ) : (
        <div className="table-scroll" tabIndex={0} role="region" aria-label="Scrollable data table"><table className="rows">
          <thead>
            <tr><th>Physician</th><th className="num">Consults</th><th className="num">Calls</th><th className="num">Open</th><th className="num">Shift ends in</th><th>Risk</th></tr>
          </thead>
          <tbody>
            {workload.items.map((p) => (
              <tr key={p.physician_id}>
                <td>{p.name}<div className="reason">{p.reason}</div></td>
                <td className="num">{p.consults}</td>
                <td className="num">{p.calls}</td>
                <td className="num">{p.open_consults}</td>
                <td className="num">{p.minutes_to_shift_end === null ? "?" : `${p.minutes_to_shift_end} min`}</td>
                <td>
                  {levelBadge(p.overload, "Overload")}{" "}
                  {levelBadge(p.shift_end_risk, `${p.open_notes} notes open`)}
                </td>
              </tr>
            ))}
          </tbody>
        </table></div>
      )}
    </section>
  );
}
