import type { Snapshot } from "../api/live.ts";
import type { IngestReport } from "./types.ts";

type BoardConsult = { consult_id: string; hospital_id?: string; current_stage?: string; level?: string };
type Headline = { open_consults?: number; critical?: number };
export type Board = { now: number | null; consults: Map<string, BoardConsult>; headline: Headline };

// Capture the server's board once. Later polling and clock controls cannot change this upload's result.
export function boardOf(snapshot: Snapshot): Board {
  const consults = (snapshot.consults as BoardConsult[] | undefined) ?? [];
  const now = Date.parse(snapshot.clock.now);
  return {
    now: Number.isFinite(now) ? now : null,
    consults: new Map(consults.map((c) => [c.consult_id, { ...c }])),
    headline: { ...((snapshot.headline as Headline | undefined) ?? {}) },
  };
}

export function uploadSegments(report: IngestReport): [string, number, string][] {
  const rows = report.row_results;
  const accepted = rows ? rows.filter((r) => r.status === "accepted").length : report.accepted;
  const acceptedRows = rows?.filter((r) => r.status === "accepted");
  const waiting = acceptedRows?.every((r) => r.pending_future !== undefined)
    ? acceptedRows.filter((r) => r.pending_future).length
    : Math.min(accepted, report.pending_future);
  return [
    ["On the board", accepted - waiting, "accepted"],
    ["Waiting for the clock", waiting, "waiting"],
    ["Duplicates skipped", rows ? rows.filter((r) => r.status === "duplicate").length : report.duplicates, "duplicate"],
    ["Held for missing context", rows ? rows.filter((r) => r.status === "held").length : report.held_orphans, "held"],
    ["Quarantined", rows ? rows.filter((r) => r.status === "quarantined" || r.status === "conflict").length : report.quarantined.length, "rejected"],
  ];
}
