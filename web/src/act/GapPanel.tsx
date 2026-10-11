import { useState } from "react";
import { AuditLog } from "./AuditLog.tsx";
import { Candidates } from "./Candidates.tsx";
import { unavailableText, useApi } from "./hooks.ts";
import { OfferForm } from "./OfferForm.tsx";
import { clockTime } from "./time.ts";
import { TrapCheck } from "./TrapCheck.tsx";
import type { Candidate, Candidates as CandidatesData, Offer, TrapCheck as TrapCheckData } from "./types.ts";
import "./act.css";

// Coordinator view of one gap: who was checked, the trap check, the proposal form and the audit trail.
export function GapPanel({ gapId, reloadKey, now, canPropose, onClose, onProposed }: {
  gapId: string; reloadKey: unknown; now: number | null; canPropose: boolean; onClose: () => void; onProposed: (o: Offer) => void;
}) {
  const id = encodeURIComponent(gapId);
  const candidates = useApi<CandidatesData>(`/gaps/${id}/candidates`, reloadKey);
  const trap = useApi<TrapCheckData>(`/gaps/${id}/trap-check`, reloadKey);
  const [proposing, setProposing] = useState<Candidate | null>(null);
  const gap = candidates.data?.gap;

  return (
    <section className="panel gap-panel">
      <div className="panel-head">
        <h2>{gap ? `Find cover · ${gap.hospital_names.join(", ")}, ${clockTime(gap.start)} to ${clockTime(gap.end)}` : "Find cover"}</h2>
        <button className="btn" onClick={onClose}>Close</button>
      </div>
      {gap && <p className="muted" style={{ margin: 0 }}>{gap.summary}</p>}

      <section>
        <h2>Off-shift physicians</h2>
        {candidates.data ? (
          <Candidates data={candidates.data} onPropose={canPropose ? setProposing : null} />
        ) : (
          candidates.error && <p className="unavailable">{unavailableText(candidates.error, "GET /gaps/{gap_id}/candidates")}</p>
        )}
      </section>

      {proposing && gap && (
        <section>
          <h2>Propose an offer</h2>
          <OfferForm gap={gap} candidate={proposing} now={now} onProposed={(o) => { setProposing(null); onProposed(o); }} />
        </section>
      )}

      {trap.data ? (
        <TrapCheck check={trap.data} title="Split-shift trap check" />
      ) : (
        trap.error && <p className="unavailable">{unavailableText(trap.error, "GET /gaps/{gap_id}/trap-check")}</p>
      )}

      <AuditLog gapId={gapId} reloadKey={reloadKey} />
    </section>
  );
}
