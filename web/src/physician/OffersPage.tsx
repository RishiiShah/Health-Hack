import { useEffect, useMemo, useState } from "react";
import { post } from "../api/client.ts";
import { unavailableText, useApi } from "../act/hooks.ts";
import { stateBadge } from "../act/offerSteps.ts";
import { clockTime, countdown } from "../act/time.ts";
import type { Offer } from "../act/types.ts";

// A physician's own offers. The server only lists offers a clinical lead has approved and sent to them.
export function OffersPage() {
  const [reloadKey, setReloadKey] = useState(0);
  const [tick, setTick] = useState(0);
  // Re-poll every 5 s; redraw the countdown every second from the server's clock.
  const { data, error } = useApi<{ now: string; items: Offer[] }>("/me/offers", `${reloadKey}:${Math.floor(tick / 5)}`);
  const fetchedAt = useMemo(() => Date.now(), [data]);
  useEffect(() => {
    const timer = setInterval(() => setTick((t) => t + 1), 1000);
    return () => clearInterval(timer);
  }, []);
  const now = data ? Date.parse(data.now) + (Date.now() - fetchedAt) : null;

  return (
    <div className="page" style={{ maxWidth: 760 }}>
      <h1>Your offers</h1>
      <p className="muted" style={{ margin: "6px 0 24px" }}>Offers show the hospital and hours only. No patient details are shared.</p>
      {error && !data ? (
        <p className="unavailable">{unavailableText(error, "GET /me/offers")}</p>
      ) : !data?.items.length ? (
        <p className="unavailable">No offers right now.</p>
      ) : (
        data.items.map((o) => <OfferCard key={o.offer_id} offer={o} now={now} onChanged={() => setReloadKey((k) => k + 1)} />)
      )}
    </div>
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
    <section className="panel" style={{ marginBottom: 16, borderColor: open ? "var(--teal)" : undefined }}>
      <div className="panel-head">
        <h2>{offer.hospital_names.join(", ")} · {clockTime(offer.start)} to {clockTime(offer.end)} ET</h2>
        <span className={`badge ${badge.tone}`}>{open ? "Waiting for you" : badge.text}</span>
      </div>
      {offer.message && <p className="message">{offer.message}</p>}
      {open && offer.expires_at && now !== null && <p className="mono" style={{ margin: "0 0 12px" }}>Reply within {countdown(offer.expires_at, now)}</p>}
      {open && (
        <div style={{ display: "flex", gap: 10 }}>
          <button className="btn primary" onClick={() => answer("accept")}>Accept</button>
          <button className="btn" onClick={() => answer("decline")}>Decline</button>
        </div>
      )}
      {error && <p className="error" role="alert">{error}</p>}
    </section>
  );
}
