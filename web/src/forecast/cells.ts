import { clockTime } from "../act/time.ts";
import type { CoverageCell } from "./types.ts";

// Maps the server's cell status to how it is drawn; the status itself is never recomputed here.
export function cellText(cell: CoverageCell): string {
  return cell.count === null || cell.required === null ? "?" : `${cell.count}/${cell.required}`;
}

export function cellTone(cell: CoverageCell): "gap" | "maybe" | "at" | "above" | "unknown" {
  if (cell.status === "gap") return cell.schedule_incomplete ? "maybe" : "gap";
  if (cell.status === "at_minimum") return "at";
  if (cell.status === "above_minimum") return "above";
  return "unknown";
}

export const stepLabel = (iso: string, index: number) => (index === 0 ? "Now" : clockTime(iso));

// Shift cliffs are interleaved with regular observations; column indices are not durations.
export const elapsedMinutes = (iso: string, start: string) => Math.round((Date.parse(iso) - Date.parse(start)) / 60000);
