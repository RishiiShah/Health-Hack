// What an upload did, at a glance: where every row went, how far the clock moved and what changed on the board.
import { clockTimeSeconds } from "./time.ts";
import type { IngestReport } from "./types.ts";
import { uploadSegments, type Board } from "./uploadSummary.ts";

export function UploadResult({ report, before, after }: { report: IngestReport; before: Board; after: Board }) {
  const segments = uploadSegments(report);
  const waiting = segments[1][1];
  const total = segments.reduce((sum, [, count]) => sum + count, 0);

  const added = [...after.consults.values()].filter((c) => !before.consults.has(c.consult_id));
  const moved = [...after.consults.values()].filter((c) => {
    const was = before.consults.get(c.consult_id);
    return was && was.current_stage !== c.current_stage;
  });
  const left = [...before.consults.values()].filter((c) => !after.consults.has(c.consult_id));
  const deltas: [string, number | undefined, number | undefined][] = [
    ["Open consults", before.headline.open_consults, after.headline.open_consults],
    ["Critical", before.headline.critical, after.headline.critical],
  ];

  return (
    <div className="upload-result" aria-live="polite">
      <div className="upload-result-head">
        <span className="kicker">Upload result</span>
        <strong>{total} row{total === 1 ? "" : "s"} processed</strong>
      </div>

      <div className="outcome-bar" role="img" aria-label={segments.map(([label, count]) => `${label}: ${count}`).join(", ")}>
        {segments.filter(([, count]) => count > 0).map(([label, count, tone]) =>
          <span key={tone} className={`outcome-seg ${tone}`} style={{ flexGrow: count }} title={`${label}: ${count}`} />)}
      </div>
      <ul className="outcome-legend">
        {segments.map(([label, count, tone]) => <li key={tone} className={count ? "" : "is-zero"}><i className={`outcome-dot ${tone}`} /><b>{count}</b>{label}</li>)}
      </ul>

      {report.clock_advanced_to && (
        <div className="clock-move">
          <span className="kicker">Replay clock</span>
          <span><b>{before.now !== null ? clockTimeSeconds(before.now) : "–"}</b><i aria-hidden="true">→</i><b>{clockTimeSeconds(report.clock_advanced_to)}</b></span>
        </div>
      )}

      <div className="board-delta">
        <span className="kicker">What changed on the board</span>
        <p className="hint">Board captured after this upload at {after.now !== null ? clockTimeSeconds(after.now) : "an unavailable replay time"}. See the Command page for the current board.</p>
        <div className="delta-tiles">
          {deltas.map(([label, was, now]) => {
            const change = was !== undefined && now !== undefined ? now - was : 0;
            return <div key={label} className="delta-tile">
              <span>{label}</span>
              <strong>{now ?? "–"}</strong>
              <em className={change > 0 ? "up" : change < 0 ? "down" : ""}>{change > 0 ? `+${change}` : change < 0 ? `${change}` : "no change"}</em>
            </div>;
          })}
        </div>
        {added.length + moved.length + left.length === 0
          ? <p className="hint">No consult changed stage yet{waiting ? `; ${waiting} event${waiting === 1 ? "" : "s"} will apply when the clock reaches ${waiting === 1 ? "it" : "them"}` : ""}.</p>
          : <ul className="consult-changes">
              {added.map((c) => <li key={`a-${c.consult_id}`}><span className="badge green">New</span><b>{c.consult_id}</b><span>{c.hospital_id}</span><span>{c.current_stage}</span></li>)}
              {moved.map((c) => <li key={`m-${c.consult_id}`}><span className="badge teal">Moved</span><b>{c.consult_id}</b><span>{before.consults.get(c.consult_id)?.current_stage} → {c.current_stage}</span><span>{c.hospital_id}</span></li>)}
              {left.map((c) => <li key={`l-${c.consult_id}`}><span className="badge neutral">Closed</span><b>{c.consult_id}</b><span>{c.hospital_id}</span><span>left the board</span></li>)}
            </ul>}
        <a className="btn" href="#command">See it on the Command page<span aria-hidden="true">→</span></a>
      </div>
    </div>
  );
}
