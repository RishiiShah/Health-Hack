import { useState, type FormEvent } from "react";
import { post } from "../api/client.ts";
import { clockTime, etTimeOn } from "./time.ts";
import type { Candidate, Gap, Offer } from "./types.ts";
import "./act.css";

// Coordinator's proposal. Physician and hospitals are fixed; the server validates every rule on submit.
export function OfferForm({ gap, candidate, onProposed }: { gap: Gap; candidate: Candidate; onProposed: (o: Offer) => void }) {
  const [start, setStart] = useState(clockTime(gap.start));
  const [end, setEnd] = useState(clockTime(gap.end));
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      onProposed(await post<Offer>("/offers", {
        gap_id: gap.gap_id, physician_id: candidate.physician_id, start: etTimeOn(gap.start, start), end: etTimeOn(gap.end, end),
      }));
    } catch (e) {
      setError((e as Error).message);
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
