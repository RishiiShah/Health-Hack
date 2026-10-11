import { useState, type FormEvent } from "react";
import { post } from "../api/client.ts";
import { clockTime, etTimeOn, nextMinute } from "./time.ts";
import type { Candidate, Gap, Offer } from "./types.ts";
import "./act.css";

// Coordinator's proposal. Physician and hospitals are fixed; the server validates every rule on submit.
// A gap already under way starts at the current second, so the suggested start is the next whole minute after both
// the gap start and the server's clock (`now`); otherwise the HH:MM field would already lie in the past.
export function OfferForm({ gap, candidate, now, onProposed }: { gap: Gap; candidate: Candidate; now: number | null; onProposed: (o: Offer) => void }) {
  const [start, setStart] = useState(() => clockTime(nextMinute(Math.max(Date.parse(gap.start) - 1, now ?? 0))));
  const [end, setEnd] = useState(clockTime(gap.end));
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    const startAt = etTimeOn(gap.start, start);
    try {
      onProposed(await post<Offer>("/offers", {
        gap_id: gap.gap_id, physician_id: candidate.physician_id, start: startAt, end: etTimeOn(gap.end, end),
      }));
    } catch (e) {
      // The clock keeps running while the form is open: when the chosen start has passed, offer the next minute.
      const moved = now !== null && Date.parse(startAt) <= now ? clockTime(nextMinute(now)) : null;
      if (moved) setStart(moved);
      setError(`${(e as Error).message}${moved ? `. Start moved to ${moved} ET; check it and send again.` : ""}`);
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="offer-form" onSubmit={submit}>
      <label>Physician<input readOnly value={candidate.name} /></label>
      <label>Hospitals<input readOnly value={gap.hospital_names.join(", ")} /></label>
      <label>Start (ET)<input type="time" value={start} onChange={(e) => setStart(e.target.value)} required /></label>
      <label>End (ET)<input type="time" value={end} onChange={(e) => setEnd(e.target.value)} required /></label>
      <button className="btn primary" disabled={busy}>Send to clinical lead</button>
      {error && <p className="error" role="alert">{error}</p>}
    </form>
  );
}
