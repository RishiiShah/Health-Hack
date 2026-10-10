import { useState } from "react";
import { post } from "../api/client.ts";
import { unavailableText, useApi } from "./hooks.ts";
import { clockTime, minutesUntil } from "./time.ts";
import { TrapCheck } from "./TrapCheck.tsx";
import type { Candidate, Candidates, Intervention, Offer, TrapCheck as TrapCheckData } from "./types.ts";
import "./act.css";

type Item = { kind: "offer"; offer: Offer } | { kind: "escalation"; intervention: Intervention };

// Clinical lead's queue: proposed offers and escalations. The server enforces who may approve.
export function ApprovalsPage({ offers, offersError, now, reloadKey, onChanged }: {
  offers: Offer[]; offersError: string | null; now: number | null; reloadKey: unknown; onChanged: () => void;
}) {
  const escalations = useApi<{ items: Intervention[] }>("/interventions?state=pending", reloadKey);
  const items: Item[] = [
    ...offers.filter((o) => o.state === "Proposed").map((offer) => ({ kind: "offer" as const, offer })),
    ...(escalations.data?.items ?? []).map((intervention) => ({ kind: "escalation" as const, intervention })),
  ];
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const idOf = (i: Item) => (i.kind === "offer" ? i.offer.offer_id : i.intervention.intervention_id);
  const selected = items.find((i) => idOf(i) === selectedId) ?? items[0];

  if (!items.length) {
    return (
      <div className="page">
        <h1>Approvals</h1>
        <p className="unavailable">{offersError ?? "Nothing is waiting for your approval."}</p>
      </div>
    );
  }

  return (
    <div className="page">
      {items.length > 1 && (
        <div className="queue">
          {items.map((i) => (
            <button key={idOf(i)} aria-pressed={i === selected} onClick={() => setSelectedId(idOf(i))}>
              {i.kind === "offer" ? `Offer · ${i.offer.physician_name} · ${i.offer.hospital_names.join(", ")}` : `Escalation · ${i.intervention.item_id}`}
            </button>
          ))}
        </div>
      )}
      {selected.kind === "offer" ? (
        <OfferApproval key={selected.offer.offer_id} offer={selected.offer} now={now} reloadKey={reloadKey} onChanged={onChanged} />
      ) : (
        <EscalationApproval key={selected.intervention.intervention_id} intervention={selected.intervention} onChanged={onChanged} />
      )}
    </div>
  );
}

function OfferApproval({ offer, now, reloadKey, onChanged }: { offer: Offer; now: number | null; reloadKey: unknown; onChanged: () => void }) {
  const gap = encodeURIComponent(offer.gap_id);
  const candidates = useApi<Candidates>(`/gaps/${gap}/candidates`, reloadKey);
  const trap = useApi<TrapCheckData>(`/gaps/${gap}/trap-check`, reloadKey);
  const startsIn = now !== null && candidates.data ? minutesUntil(candidates.data.gap.start, now) : null;

  return (
    <div className="approval">
      <div>
        <span className="badge amber">Off-shift offer{startsIn !== null && startsIn >= 0 ? ` · gap starts in ${startsIn} min` : ""}</span>
        <h1 style={{ marginTop: 12 }}>
          Bring in {offer.physician_name} for {offer.hospital_names.join(", ")}, {clockTime(offer.start)} to {clockTime(offer.end)}?
        </h1>
        <p className="lede">{candidates.data?.gap.summary}</p>

        {trap.data ? (
          <TrapCheck check={trap.data} title="What changes if they accept" />
        ) : (
          trap.error && <p className="unavailable">{unavailableText(trap.error, "GET /gaps/{gap_id}/trap-check")}</p>
        )}

        <section className="panel">
          <div className="panel-head"><h2>Who else was checked</h2></div>
          {candidates.data ? (
            <ul className="checked">
              {candidates.data.candidates.map((c) => (
                <li key={c.physician_id}>{c.name}<CheckBadge candidate={c} ruleCount={candidates.data!.rules.length} /></li>
              ))}
            </ul>
          ) : (
            candidates.error && <p className="unavailable">{unavailableText(candidates.error, "GET /gaps/{gap_id}/candidates")}</p>
          )}
        </section>
      </div>
      <Decision offer={offer} onChanged={onChanged} />
    </div>
  );
}

function CheckBadge({ candidate, ruleCount }: { candidate: Candidate; ruleCount: number }) {
  if (candidate.eligible) return <span className="badge green">Passes all {ruleCount} rules</span>;
  const failed = candidate.results.some((r) => r.status === "fail");
  return <span className={`badge ${failed ? "red" : "neutral"}`}>{candidate.primary_reason}</span>;
}

function Decision({ offer, onChanged }: { offer: Offer; onChanged: () => void }) {
  const [note, setNote] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const id = encodeURIComponent(offer.offer_id);

  async function act(path: string, payload?: unknown) {
    setBusy(true);
    setError(null);
    try {
      await post(path, payload);
      onChanged();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <aside className="panel decision">
      <h2>Your decision</h2>
      <p style={{ margin: 0, color: "var(--ink-2)", fontSize: 14 }}>
        Approving sends the offer to {offer.physician_name}'s Sevaro app on phone and web.
      </p>
      <span className="label">They will see</span>
      <p className="message">{offer.message ?? "The server writes the message when it sends the offer."}</p>
      <p className="safe">No patient details are shared.</p>
      <label htmlFor="reject-note">Note <span>(required if you reject)</span></label>
      <textarea id="reject-note" value={note} onChange={(e) => setNote(e.target.value)} />
      <button className="btn primary block" disabled={busy} onClick={() => act(`/offers/${id}/approve`)}>Approve and send</button>
      <button className="btn danger block" disabled={busy || !note.trim()} onClick={() => act(`/offers/${id}/reject`, { reason: note.trim() })}>Reject</button>
      {error && <p className="error" role="alert">{error}</p>}
    </aside>
  );
}

function EscalationApproval({ intervention, onChanged }: { intervention: Intervention; onChanged: () => void }) {
  const [error, setError] = useState<string | null>(null);
  async function authorize() {
    try {
      await post(`/interventions/${encodeURIComponent(intervention.intervention_id)}/authorize`);
      onChanged();
    } catch (e) {
      setError((e as Error).message);
    }
  }
  return (
    <div className="approval">
      <div>
        <span className="badge amber">Escalation · {clockTime(intervention.created_at)}</span>
        <h1 style={{ marginTop: 12 }}>{intervention.item_id}</h1>
        <p className="lede">{intervention.reason}</p>
      </div>
      <aside className="panel decision">
        <h2>Your decision</h2>
        <button className="btn primary block" onClick={authorize}>Authorize</button>
        {error && <p className="error" role="alert">{error}</p>}
      </aside>
    </div>
  );
}
