import { clockTime } from "./time.ts";
import type { TrapCheck as TrapCheckData } from "./types.ts";
import "./act.css";

const tone = (v: { count: number; required: number }) => (v.count < v.required ? "short" : "met");

// Coverage at the gap hospital without and with the joining physician, as simulated by the server.
export function TrapCheck({ check, title }: { check: TrapCheckData; title: string }) {
  return (
    <section className="panel">
      <div className="panel-head">
        <h2>{title}</h2>
        <span className={`badge ${check.passed ? "green" : "red"}`}>{check.passed ? "Trap check passed" : "Trap check failed"}</span>
      </div>
      <table className="compare">
        <thead><tr><th />{check.steps.map((s) => <th key={s}>{clockTime(s)}</th>)}</tr></thead>
        <tbody>
          <tr><td className="label">Without</td>{check.without.map((v, i) => <td key={i} className={`val ${tone(v)}`}>{v.count}/{v.required}</td>)}</tr>
          <tr><td className="label">With</td>{check.with.map((v, i) => <td key={i} className={`val ${tone(v)}`}>{v.count}/{v.required}</td>)}</tr>
        </tbody>
      </table>
      <p className="footnote">
        {check.assumption} Takes {check.limited_to.map((h) => h.hospital_name).join(", ")} calls only and starts at {check.seed_consults} consults
        (load {check.joiner_load}, busiest peer {check.busiest_peer_load}).
        {check.other_gaps_worsened && " Another hospital's gap gets worse."}
      </p>
      {check.reasons.length > 0 && <ul className="footnote">{check.reasons.map((r) => <li key={r}>{r}</li>)}</ul>}
    </section>
  );
}
