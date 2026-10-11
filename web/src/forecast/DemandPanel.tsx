import type { Demand } from "./types.ts";
import "./forecast.css";

// One compact tile per hospital, in the server's order: consults in the last hour against the usual peak.
export function DemandPanel({ demand }: { demand?: Demand }) {
  return (
    <section className="panel">
      <div className="panel-head">
        <div><h3>Demand, last 60 minutes</h3><p className="panel-note">Consults per hospital against the usual peak (90th percentile)</p></div>
      </div>
      {!demand?.supported || !demand.items ? (
        <p className="unavailable">Not available yet: the server doesn't send demand.</p>
      ) : (
        <ul className="demand-grid" aria-label="Demand by hospital">
          {demand.items.map((d) => (
            <li key={d.hospital_id} className={d.status === "surge" ? "surge" : undefined}>
              <span className="demand-name">{d.hospital_name}</span>
              <span className="demand-count"><strong>{d.trailing_60m}</strong> / {d.p90 ?? "?"} usual</span>
              {d.status === "surge" ? <span className="badge amber">Surge</span> : d.status === "unknown" ? <span className="badge neutral">No baseline</span> : null}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
