import type { QueueItem } from "./types.ts";

export function ItemDetail({ item }: { item: QueueItem | null }) {
  if (!item) return <section className="panel detail-panel"><h2>Select an item</h2><p className="muted">Choose a row in the attention queue to inspect its decision context.</p></section>;
  return <section className="panel detail-panel"><div className="panel-head"><div><span className={`badge ${item.level === "Critical" ? "red" : "amber"}`}>{item.level}</span><h2>{item.id}</h2></div><span className="badge neutral">{item.uncertainty}</span></div><dl><dt>Where</dt><dd>{item.where}</dd><dt>Why it matters</dt><dd>{item.why}</dd><dt>Suggested fix</dt><dd>{item.fix}</dd><dt>Who approves</dt><dd>{item.approver}</dd></dl><div className="detail-actions"><button className="btn primary">Escalate to clinical lead</button><button className="btn">Reassign</button></div></section>;
}
