// The selected queue item. Buttons appear only for fixes the server says a person can take.
import { useEffect, useState } from "react";
import { post } from "../api/client.ts";
import type { QueueItem } from "../detect/index.ts";
import "./command.css";

export function Dossier({ item, total, onFindCover, onDone }: { item: QueueItem; total: number; onFindCover: (gapId: string) => void; onDone: () => void }) {
  const [message, setMessage] = useState<string | null>(null);
  useEffect(() => setMessage(null), [item.id]);
  const intervene = async (kind: "reassign" | "escalate") => {
    try {
      await post("/interventions", { kind, item_id: item.id, physician_id: kind === "reassign" ? item.physicianId : undefined });
      setMessage(kind === "escalate" ? "Sent to the clinical lead." : "Reassignment recorded.");
      onDone();
    } catch (e) {
      setMessage((e as Error).message);
    }
  };
  const isGap = item.kind === "now_gap" || item.kind === "gap";
  const canReassign = ["reassign", "assign", "handoff"].includes(item.fixKind) && item.physicianId;
  const facts: [string, string][] = [
    [item.watchOnly ? "What to watch" : "Recommended action", item.fix],
    ["Who approves", item.approver],
    ["Consult / site", item.where || "–"],
    ["Why it matters", item.why || "–"],
  ];
  return <section className={`dossier-card severity-${item.level.toLowerCase()}`} aria-live="polite">
    <header className="dossier-head">
      <div><span className="kicker"><b>#{item.rank}</b>of {total} · {item.level}</span><h3>{item.reason}</h3></div>
      {item.level === "Critical" && <span className="critical-mark" aria-hidden="true">!</span>}
    </header>
    <dl className="dossier-grid">{facts.map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{value}</dd></div>)}
      {(item.fixReason || item.alternatives.length > 0) && <div className="dossier-wide"><dt>Why this fix</dt><dd>{item.fixReason}
        {item.alternatives.length > 0 && <details className="decision-alternatives"><summary>Other options and exclusions ({item.alternatives.length})</summary><ul>{item.alternatives.map((a) => <li key={a}>{a}</li>)}</ul></details>}</dd></div>}
    </dl>
    <div className="actions">
      {canReassign && <button className="btn dossier-primary" onClick={() => intervene("reassign")}>{item.fixKind === "handoff" ? "Record handoff" : "Reassign"}<span aria-hidden="true">→</span></button>}
      {isGap && !item.watchOnly && <button className="btn dossier-primary" onClick={() => onFindCover(item.id)}>Find cover<span aria-hidden="true">→</span></button>}
      {item.approver !== "Automatic" && <button className={`btn ${item.fixKind === "escalate" ? "dossier-primary" : ""}`} onClick={() => intervene("escalate")}>Escalate to clinical lead</button>}
    </div>
    {message && <p className="dossier-message" role="status">{message}</p>}
  </section>;
}
