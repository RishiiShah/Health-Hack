import type { Demand } from "./types.ts";
import "./forecast.css";

export function DemandPanel({ demand }: { demand?: Demand }) {
  return (
    <section className="panel">
      <div className="panel-head">
        <h2>Demand, last 60 minutes</h2>
        <span className="note">consults vs usual peak (p90)</span>
      </div>
      {!demand?.supported || !demand.items ? (
        <p className="unavailable">Not available yet: the server doesn't send demand.</p>
      ) : (
        <div className="table-scroll" tabIndex={0} role="region" aria-label="Scrollable data table"><table className="rows">
          <thead><tr><th>Hospital</th><th className="num">Last 60 min</th><th className="num">Usual peak</th><th /></tr></thead>
          <tbody>
            {demand.items.map((d) => (
              <tr key={d.hospital_id}>
                <td>{d.hospital_name}</td>
                <td className="num">{d.trailing_60m}</td>
                <td className="num">{d.p90 ?? "?"}</td>
                <td>{d.status === "surge" ? <span className="badge amber">Surge</span> : d.status === "unknown" ? <span className="badge neutral">No baseline</span> : null}</td>
              </tr>
            ))}
          </tbody>
        </table></div>
      )}
    </section>
  );
}
