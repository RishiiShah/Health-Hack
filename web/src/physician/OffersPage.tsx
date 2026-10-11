import { useEffect, useMemo, useState } from "react";
import { post } from "../api/client.ts";
import { unavailableText, useApi } from "../act/hooks.ts";
import { stateBadge } from "../act/offerSteps.ts";
import { clockTime, countdown } from "../act/time.ts";
import type { Offer } from "../act/types.ts";
import { OfferAudio } from "../api/OfferAudio.tsx";
import { serverNow } from "../act/time.ts";
import { PageHead } from "../ui/Layout.tsx";
import { stagger } from "../ui/motion.ts";
import "./physician.css";

// A physician's own offers. The server only lists offers a clinical lead has approved and sent to them.
export function OffersPage() {
  const [reloadKey, setReloadKey] = useState(0);
  const [, setTick] = useState(0);
  // Re-poll every 5 s; redraw the countdown every second from the server's clock.
  const { data, error } = useApi<{ now: string; clock_mode: string; items: Offer[] }>("/me/offers", reloadKey, 5000);
  const fetchedAt = useMemo(() => Date.now(), [data]);
  useEffect(() => {
    const timer = setInterval(() => setTick((t) => t + 1), 1000);
    return () => clearInterval(timer);
  }, []);
  const now = data ? serverNow(data.now, data.clock_mode, fetchedAt, Date.now()) : null;

  return (
    <>
      <PageHead kicker="Physician workspace" title="Your offers" note="Offers show the hospital and hours only. No patient details are shared." />
      {error && !data ? (
        <p className="unavailable">{unavailableText(error, "GET /me/offers")}</p>
      ) : !data?.items.length ? (
        <p className="unavailable">No offers right now.</p>
      ) : (
        <div className="stack">{data.items.map((o, i) => <div key={o.offer_id} className="rise" style={stagger(i)}><OfferCard offer={o} now={now} onChanged={() => setReloadKey((k) => k + 1)} /></div>)}</div>
      )}
    </>
  );
}

function OfferCard({ offer, now, onChanged }: { offer: Offer; now: number | null; onChanged: () => void }) {
  const [error, setError] = useState<string | null>(null);
  const badge = stateBadge(offer.state);
  const open = offer.state === "Sent";

  async function answer(choice: "accept" | "decline") {
    try {
      await post(`/me/offers/${encodeURIComponent(offer.offer_id)}/${choice}`);
      onChanged();
    } catch (e) {
      setError((e as Error).message);
    }
  }

  return (
    <section className={`panel offer-card ${open ? "open" : ""}`}>
      <div className="panel-head">
        <h2>{offer.hospital_names.join(", ")} · {clockTime(offer.start)} to {clockTime(offer.end)} ET</h2>
        <span className={`badge ${badge.tone}`}>{open ? "Waiting for you" : badge.text}</span>
      </div>
      {offer.message && <p className="message">{offer.message}</p>}
      {offer.audio_url && <OfferAudio path={offer.audio_url} />}
      {open && offer.expires_at && now !== null && <p className="reply-within">Reply within {countdown(offer.expires_at, now)}</p>}
      {open && (
        <div className="actions">
          <button className="btn primary" onClick={() => answer("accept")}>Accept</button>
          <button className="btn" onClick={() => answer("decline")}>Decline</button>
        </div>
      )}
      {error && <p className="error" role="alert">{error}</p>}
    </section>
  );
}
