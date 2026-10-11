import type { Candidate, Candidates as CandidatesData } from "./types.ts";
import "./act.css";

const MARK = { pass: "✓", fail: "✗", unknown: "?" } as const;

// Every off-shift physician against R1 to R8, in the server's order, with the server's explanations.
export function Candidates({ data, onPropose }: { data: CandidatesData; onPropose: ((c: Candidate) => void) | null }) {
  return (
    <>
    <div className="table-scroll" tabIndex={0} role="region" aria-label="Off-shift physician eligibility by rule"><table className="candidates">
      <thead>
        <tr>
          <th>Physician</th>
          {data.rules.map((r) => <th key={r.id} title={r.label}>{r.id}</th>)}
          <th>Rank</th>
          <th title="Gap hospitals · minutes to online · declines in 30 days · hours in 7 days">Ranking factors</th>
          <th className="why">Excluded because</th>
          <th><span className="sr-only">Action</span></th>
        </tr>
      </thead>
      <tbody>
        {data.candidates.map((c) => (
          <tr key={c.physician_id} className={c.eligible ? "eligible" : undefined}>
            <td><b>{c.name}</b></td>
            {data.rules.map((r) => {
              const result = c.results.find((x) => x.rule === r.id);
              return (
                <td key={r.id} className={result?.status ?? "unknown"} title={result?.explanation}>
                  {MARK[result?.status ?? "unknown"]}
                </td>
              );
            })}
            <td className="mono">{c.rank ?? "–"}</td>
            <td className="mono">
              {c.ranking.gap_hospitals} · {c.ranking.minutes_to_online ?? "?"} min · {c.ranking.declines_30d ?? "?"} · {c.ranking.hours_7d ?? "?"} h
            </td>
            <td className="why">{c.primary_reason}</td>
            <td>{c.eligible && onPropose && <button className="btn primary" onClick={() => onPropose(c)}>Propose offer</button>}</td>
          </tr>
        ))}
      </tbody>
    </table></div>
    <details className="eligibility-rules"><summary>Eligibility rules & ranking factors</summary><dl>{data.rules.map((rule) => <div key={rule.id}><dt>{rule.id}</dt><dd>{rule.label}</dd></div>)}</dl><p>Ranking factors: gap hospitals covered · minutes to online · declines in 30 days · hours worked in 7 days. Order and exclusions are supplied by the server.</p></details>
    </>
  );
}
