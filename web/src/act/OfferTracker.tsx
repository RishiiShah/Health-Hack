import { offerSteps, stateBadge } from "./offerSteps.ts";
import { clockTime, countdown } from "./time.ts";
import type { Offer } from "./types.ts";
import { OfferAudio } from "../api/OfferAudio.tsx";
import "./act.css";

export function OfferTracker({ offer, now }: { offer: Offer; now: number | null }) {
  const badge = stateBadge(offer.state);
  const timeLeft = offer.state === "Sent" && offer.expires_at && now !== null ? countdown(offer.expires_at, now) : null;
  const nextStep = offer.state === "Proposed" ? "Clinical lead to review and approve" : offer.state === "Sent" ? "Physician to accept or decline" : offer.state === "Approved" ? "Approved offer awaiting delivery" : offer.state === "Accepted" ? "Review updated coverage" : "Offer closed";
  return (
    <article className={`tracker tracker-${offer.state.toLowerCase().replaceAll(" ", "-")}`}>
      <div className="panel-head tracker-heading">
        <div><h4>{offer.physician_name}</h4><span className="tracker-reference">Off-shift offer · {offer.offer_id}</span></div>
        <span className={`badge ${badge.tone}`}>{badge.text}</span>
      </div>
      <div className="offer-scope">
        <div><span className="tracker-label">Coverage window</span><strong>{clockTime(offer.start)}–{clockTime(offer.end)} <small>ET</small></strong></div>
        <div><span className="tracker-label">Hospitals · {offer.hospital_names.length}</span><ul>{offer.hospital_names.map(name => <li key={name}>{name}</li>)}</ul></div>
      </div>
      <div className="offer-next-step"><div><span className="tracker-label">Next step</span><strong>{nextStep}</strong></div>{timeLeft && <span className="reply-countdown"><b>{timeLeft}</b> to reply</span>}</div>
      <ol className="steps" aria-label="Offer progress">
        {offerSteps(offer, timeLeft).map((s, i) => (
          <li key={s.label} className={s.status} aria-current={s.status === "current" ? "step" : undefined}><i aria-hidden="true">{s.status === "done" ? "✓" : i + 1}</i><div><b>{s.label}</b><span>{s.detail}</span></div></li>
        ))}
      </ol>
      {offer.reject_reason && <p className="message">Rejected: {offer.reject_reason}</p>}
      {offer.message && offer.sent_at && (
        <details className="offer-message"><summary>View sent message</summary><p className="message">{offer.message}</p><div className="tracker-actions">
          {offer.audio_url && <OfferAudio path={offer.audio_url} />}
          {offer.phone_url && <a href={offer.phone_url} target="_blank" rel="noreferrer">Open the physician's phone view</a>}
        </div></details>
      )}
    </article>
  );
}
