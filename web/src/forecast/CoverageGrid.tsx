import { useState } from "react";
import { clockTime } from "../act/time.ts";
import { cellText, cellTone, stepLabel } from "./cells.ts";
import type { Coverage, CoverageCell } from "./types.ts";
import "./forecast.css";

type Selected = { hospital: string; cell: CoverageCell };

export function CoverageGrid({ coverage, onFindCover }: { coverage?: Coverage; onFindCover: (gapId: string) => void }) {
  const [selected, setSelected] = useState<Selected | null>(null);

  if (!coverage?.supported || !coverage.steps || !coverage.hospitals) {
    return (
      <section className="panel coverage">
        <div className="panel-head"><h2>Coverage, next 90 minutes</h2></div>
        <p className="unavailable">Not available yet: the server doesn't send the coverage forecast.</p>
      </section>
    );
  }

  const hot = coverage.steps.map((_, i) => coverage.hospitals!.some((h) => h.cells[i]?.status === "gap"));

  return (
    <section className="panel coverage">
      <div className="panel-head">
        <h2>Coverage, next 90 minutes</h2>
        <span className="note">staffed / required{coverage.assumption ? ` · ${coverage.assumption}` : ""}</span>
      </div>
      <table>
        <thead>
          <tr>
            <th className="hosp">Hospital</th>
            {coverage.steps.map((at, i) => <th key={at} className={hot[i] ? "hot" : undefined}>{stepLabel(at, i)}</th>)}
          </tr>
        </thead>
        <tbody>
          {coverage.hospitals.map((h) => (
            <tr key={h.hospital_id}>
              <td className="name">
                {h.hospital_name}
                {h.nobody_reachable_now && <span className="bang" title="Nobody reachable now">!</span>}
              </td>
              {h.cells.map((cell) => (
                <td key={cell.at} className="cell">
                  <button
                    className={`${cellTone(cell)}${cell.unverified ? " unverified" : ""}`}
                    aria-pressed={selected?.cell === cell}
                    onClick={() => setSelected(selected?.cell === cell ? null : { hospital: h.hospital_name, cell })}
                  >
                    {cellText(cell)}
                  </button>
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      <div className="legend">
        <span className="key key-above">Above minimum</span>
        <span className="key key-at">At minimum</span>
        <span className="key key-gap">Short</span>
        <span className="key key-maybe">Short unless an unconfirmed shift starts</span>
        <span className="mark"><b>!</b>nobody reachable now</span>
        <span className="mark"><b>°</b>unverified</span>
      </div>
      {selected && <CellDetail {...selected} onFindCover={onFindCover} />}
    </section>
  );
}

function CellDetail({ hospital, cell, onFindCover }: Selected & { onFindCover: (gapId: string) => void }) {
  return (
    <div className="cell-detail">
      <div>
        <p><b>{hospital} at {clockTime(cell.at)}</b>: {cellText(cell)}</p>
        <p className="muted">
          Counted: {cell.physician_ids.length ? cell.physician_ids.join(", ") : "nobody"}
          {cell.incomplete_physician_ids.length > 0 && ` · schedule incomplete for ${cell.incomplete_physician_ids.join(", ")}`}
          {cell.unverified && " · includes an unverified physician"}
        </p>
      </div>
      {cell.gap_id && <button className="btn primary" onClick={() => onFindCover(cell.gap_id!)}>Find cover</button>}
    </div>
  );
}
