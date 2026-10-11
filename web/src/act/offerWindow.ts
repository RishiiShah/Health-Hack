import { nextMinute } from "./time.ts";

// Preserve the candidate's evaluated duration when rounding a live start to an
// editable minute. ISO references retain each endpoint's date across midnight.
export function suggestedOfferWindow(window: { start: string; end: string }, now: number | null) {
  const original = Date.parse(window.start);
  const start = nextMinute(Math.max(original - 1, now ?? 0));
  const moved = Date.parse(start) - original;
  const end = nextMinute(Date.parse(window.end) + moved - 1);
  return { start, end };
}
