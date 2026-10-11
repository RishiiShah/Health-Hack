// The server's ranked attention queue, filterable by level. Selecting a row shows its detail beside it.
import type { QueueItem } from "../detect/index.ts";
import { Empty } from "../ui/Layout.tsx";
import "./command.css";

const LEVELS = ["All", "Critical", "Warning", "Info"] as const;

export function AttentionQueue({ queue, filter, onFilter, selectedId, onSelect }: {
  queue: QueueItem[]; filter: string; onFilter: (level: string) => void; selectedId: string | null; onSelect: (id: string) => void;
}) {
  const shown = queue.filter((q) => filter === "All" || q.level === filter);
  return <section className="queue-card rise" aria-label="Ranked attention queue">
    <div className="queue-card-head"><h3>Attention queue</h3><span className="queue-count">{queue.length} items</span></div>
    <div className="queue-filters" role="group" aria-label="Filter attention queue">{LEVELS.map((level) =>
      <button key={level} aria-pressed={filter === level} onClick={() => onFilter(level)}>{level}<span>{level === "All" ? queue.length : queue.filter((q) => q.level === level).length}</span></button>)}
    </div>
    <div className="dense-queue" key={filter}>{shown.map((entry) => (
      <button className={`dense-queue-row level-${entry.level.toLowerCase()} ${entry.id === selectedId ? "active" : ""}`} key={entry.id} aria-pressed={entry.id === selectedId} onClick={() => onSelect(entry.id)}>
        <b className="queue-rank">{String(entry.rank).padStart(2, "0")}</b>
        <span className="queue-label"><strong>{entry.watchOnly ? "Watch · " : ""}{entry.label}</strong><small>{entry.watchOnly && entry.kind === "now_gap" ? "No consult waiting · " : ""}{entry.reason}</small></span>
        <span className={`level-chip ${entry.level.toLowerCase()}`}>{entry.level}</span>
      </button>
    ))}{!shown.length && <Empty>No {filter === "All" ? "attention" : filter.toLowerCase()} items.</Empty>}</div>
  </section>;
}
