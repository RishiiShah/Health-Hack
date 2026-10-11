import { useState, type FormEvent } from "react";
import { post } from "../api/client.ts";
import { clockTime, etTimeOn, headerDate } from "./time.ts";
import { suggestedOfferWindow } from "./offerWindow.ts";
import type { Candidate, Gap, Offer } from "./types.ts";
import "./act.css";

// Coordinator's proposal. Physician and hospitals are fixed; the server validates every rule on submit.
// Use the candidate's evaluated offer window, which can extend beyond the gap.
export function OfferForm({ gap, candidate, now, onProposed }: { gap: Gap; candidate: Candidate; now: number | null; onProposed: (o: Offer) => void }) {
  const [window, setWindow] = useState(() => suggestedOfferWindow(candidate.window, now));
  const [start, setStart] = useState(() => clockTime(window.start));
  const [end, setEnd] = useState(() => clockTime(window.end));
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    const submitted = { start: etTimeOn(window.start, start), end: etTimeOn(window.end, end) };
    try {
      onProposed(await post<Offer>("/offers", {
        gap_id: gap.gap_id, physician_id: candidate.physician_id, ...submitted, hospitals: candidate.window.hospitals,
      }));
    } catch (e) {
      // The clock keeps running while the form is open: when the chosen start has passed, offer the next minute.
      const moved = now !== null && Date.parse(submitted.start) <= now ? suggestedOfferWindow(submitted, now) : null;
      if (moved) {
        setWindow(moved);
        setStart(clockTime(moved.start));
        setEnd(clockTime(moved.end));
      }
      setError(`${(e as Error).message}${moved ? `. Window moved to start at ${clockTime(moved.start)} ET; check it and send again.` : ""}`);
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="offer-form" onSubmit={submit}>
      <label>Physician<input readOnly value={candidate.name} /></label>
      <label>Hospitals<input readOnly value={candidate.window.hospitals.map((h) => gap.hospital_names[gap.hospital_ids.indexOf(h)] ?? h).join(", ")} /></label>
      <label>Start (ET, {headerDate(window.start)})<input type="time" value={start} onChange={(e) => setStart(e.target.value)} required /></label>
      <label>End (ET, {headerDate(window.end)})<input type="time" value={end} onChange={(e) => setEnd(e.target.value)} required /></label>
      <button className="btn primary" disabled={busy}>Send to clinical lead</button>
      {error && <p className="error" role="alert">{error}</p>}
    </form>
  );
}
