import { useState } from "react";
import type { QueueItem } from "./types.ts";

// The server orders the queue; rank and reasons are shown as sent.
export function AttentionQueue({ items, selected, onSelect }: { items: QueueItem[]; selected: string; onSelect: (item: QueueItem) => void }) {
  const [expanded, setExpanded] = useState<string | null>(null);
  return <section className="panel detect-panel"><div className="panel-head"><div><h2>Attention queue</h2><span className="panel-note">Ranked by the server</span></div><span className="mono panel-note">{items.length} items</span></div><div className="queue-list">{items.map((item) => <div className={`queue-item ${selected === item.id ? "selected" : ""}`} key={item.id}><button className="queue-main" onClick={() => onSelect(item)}><b className="rank">#{item.rank}</b><span><strong>{item.watchOnly ? "Watch · " : ""}{item.label}</strong><small>{item.watchOnly && item.kind === "now_gap" ? "No consult waiting · " : ""}{item.reason}</small></span><span className={`badge ${item.level === "Critical" ? "red" : item.level === "Warning" ? "amber" : "neutral"}`}>{item.level}</span></button><button className="breakdown-toggle" onClick={() => setExpanded(expanded === item.id ? null : item.id)}>{expanded === item.id ? "Hide why" : "Why"}</button>{expanded === item.id && <div className="score-breakdown"><span>{item.why}</span></div>}</div>)}</div></section>;
}
