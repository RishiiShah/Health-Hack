import type { Demand } from "./types.ts";
import "./forecast.css";

// One compact tile per hospital, in the server's order: consults in the last hour against the usual peak.
export function DemandPanel({ demand }: { demand?: Demand }) {
  return (
    <section className="panel">
      <div className="panel-head">
        <div><h3>Demand & hourly baseline</h3><p className="panel-note">Last 60 minutes against the hourly p90. A surge adds one required physician.</p></div>
      </div>
      {demand?.horizon_minutes !== undefined && <p className="hint">Expected arrivals over the next {demand.horizon_minutes} minutes use historical hourly means. This baseline scenario does not predict the probability of a surge.</p>}
      {!demand?.supported || !demand.items ? (
        <p className="unavailable">Not available yet: the server doesn't send demand.</p>
      ) : (
        <ul className="demand-grid" aria-label="Demand by hospital">
          {demand.items.map((d) => (
            <li key={d.hospital_id} className={d.status === "surge" ? "surge" : undefined}>
              <span className="demand-name">{d.hospital_name}</span>
              <span className="demand-count"><strong>{d.trailing_60m}</strong> observed · p90 {d.p90 ?? "unknown"}</span>
              {d.mean_per_hour !== undefined && <span className="demand-baseline">Mean {d.mean_per_hour ?? "unknown"} consults/hour{d.baseline_hour && ` · ${new Intl.DateTimeFormat("en-US", { hour: "2-digit", minute: "2-digit", hourCycle: "h23", timeZone: d.baseline_timezone }).format(new Date(d.baseline_hour))} ${d.baseline_timezone === "America/New_York" ? "ET" : d.baseline_timezone}`}</span>}
              {d.expected_arrivals !== undefined && <span className="demand-baseline">Expected ahead: {d.expected_arrivals === null ? "unknown (missing baseline hours)" : `${d.expected_arrivals.toFixed(2)} consults`}</span>}
              {d.status === "surge" ? <span className="badge amber">Surge</span> : d.status === "unknown" ? <span className="badge neutral">No baseline</span> : null}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
