import { offerSteps, stateBadge } from "./offerSteps.ts";
import { clockTime, countdown } from "./time.ts";
import type { Offer } from "./types.ts";
import { OfferAudio } from "../api/OfferAudio.tsx";
import "./act.css";

export function OfferTracker({ offer, now }: { offer: Offer; now: number | null }) {
  const badge = stateBadge(offer.state);
  const timeLeft = offer.state === "Sent" && offer.expires_at && now !== null ? countdown(offer.expires_at, now) : null;
  return (
    <section className="panel tracker">
      <div className="panel-head">
        <h2>Off-shift offer · {offer.hospital_names.join(", ")} {clockTime(offer.start)} to {clockTime(offer.end)}</h2>
        <span className={`badge ${badge.tone}`}>{badge.text}</span>
      </div>
      <ol className="steps">
        {offerSteps(offer, timeLeft).map((s) => (
          <li key={s.label} className={s.status}><b>{s.label}</b><span>{s.detail}</span></li>
        ))}
      </ol>
      {offer.reject_reason && <p className="message">Rejected: {offer.reject_reason}</p>}
      {offer.message && offer.sent_at && (
        <>
          <p className="message">{offer.message}</p>
          <div className="tracker-actions">
            {offer.audio_url && <OfferAudio path={offer.audio_url} />}
            {offer.phone_url && <a href={offer.phone_url} target="_blank" rel="noreferrer">Open the physician's phone view</a>}
          </div>
        </>
      )}
    </section>
  );
}
