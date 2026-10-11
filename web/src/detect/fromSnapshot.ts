// Maps the server snapshot onto the detect screens. Names and labels only: every level, rank and reason is the server's.
import { clockTime } from "../act/time.ts";
import type { Consult, DetectSnapshot, Physician, QueueItem } from "./types.ts";

type Row = Record<string, unknown>;
const APPROVERS: Record<string, string> = { coordinator: "Coordinator", clinical_lead: "Clinical lead", lead: "Clinical lead", automatic: "Automatic" };
type Section = { supported?: boolean; items?: Row[] };
const list = (value: unknown) => (Array.isArray(value) ? value.map(String) : []);
const num = (value: unknown) => (typeof value === "number" ? value : null);
const str = (value: unknown) => (typeof value === "string" && value ? value : null);

// Turns the server's `why` details into one readable line.
export function describeWhy(why: Row): string {
  const parts: string[] = [];
  const age = num(why.age_min);
  if (str(why.stage) && age !== null) {
    parts.push(`${why.stage} for ${Math.floor(age)} min (warning ${why.warning_min}, critical ${why.critical_min})`);
  }
  if (str(why.owner_state)) parts.push(`Assigned physician is ${String(why.owner_state).toLowerCase()}`);
  if (num(why.routing_failures)) parts.push(`${why.routing_failures} routing failures${str(why.next_retry) ? `, next retry ${clockTime(String(why.next_retry))}` : ""}`);
  if (num(why.required) !== null && Array.isArray(why.available)) parts.push(`Needs ${why.required}, ${why.available.length} free now`);
  if (num(why.count) !== null && num(why.p90) !== null) parts.push(`${why.count} consults in 60 min against a usual peak of ${why.p90}`);
  if (Array.isArray(why.open_notes) && why.open_notes.length) parts.push(`${why.open_notes.length} notes open`);
  if (num(why.minutes_to_shift_end) !== null) parts.push(`shift ends in ${why.minutes_to_shift_end} min`);
  if (Array.isArray(why.windows)) parts.push(list(why.windows).join("; "));
  parts.push(...list(why.causes), ...list(why.free_elsewhere), ...list(why.also));
  return parts.join(". ");
}

export function detectFromSnapshot(snapshot: Row): DetectSnapshot | null {
  const queue = snapshot.queue as Section | undefined;
  const physicians = snapshot.physicians as Section | undefined;
  if (!queue?.supported || !physicians?.supported) return null;
  const hospitals = Object.fromEntries(((snapshot.hospitals as Section)?.items ?? []).map((h) => [h.hospital_id, String(h.name)]));
  const names = Object.fromEntries(((snapshot.workload as Section)?.items ?? []).map((w) => [w.physician_id, String(w.name)]));
  const name = (id: unknown) => names[String(id)] ?? String(id);

  const items: QueueItem[] = (queue.items ?? []).map((item) => {
    const where = (item.where ?? {}) as Row;
    const fix = (item.fix ?? {}) as Row;
    const hospital = str(where.hospital_id) ? hospitals[String(where.hospital_id)] ?? String(where.hospital_id) : null;
    const label = str(where.consult_id) ?? (str(where.physician_id) ? name(where.physician_id) : null) ?? hospital ?? String(item.id);
    return {
      id: String(item.id), label, kind: String(item.id).split(":")[0], level: String(item.severity), rank: Number(item.rank),
      reason: String(item.what),
      where: [hospital, str(where.consult_id), str(where.physician_id) ? name(where.physician_id) : null,
        ...list(where.hospital_ids).map((h) => hospitals[h] ?? h)].filter(Boolean).join(" · "),
      why: describeWhy((item.why ?? {}) as Row),
      fix: String(fix.action ?? ""), fixKind: String(fix.kind ?? ""), fixReason: String(fix.reason ?? ""), alternatives: list(fix.alternatives),
      approver: APPROVERS[String(fix.approver)] ?? String(fix.approver ?? ""),
      physicianId: str(fix.physician_id),
    };
  });

  const byConsult = new Map<string, QueueItem & { raw: Row }>();
  (queue.items ?? []).forEach((raw, i) => {
    const consultId = str((raw.where as Row | undefined)?.consult_id);
    if (consultId && !byConsult.has(consultId)) byConsult.set(consultId, { ...items[i], raw });
  });
  const consults: Consult[] = ((snapshot.consults as Row[]) ?? []).map((c) => {
    const flagged = byConsult.get(String(c.consult_id));
    const why = (flagged?.raw.why ?? {}) as Row;
    return {
      id: String(c.consult_id), hospital: hospitals[String(c.hospital_id)] ?? String(c.hospital_id), type: String(c.consult_type),
      stage: String(c.current_stage), minutesInStage: Number(c.minutes_in_stage), minutesSinceReceived: Number(c.minutes_since_received),
      level: flagged?.level ?? "Normal", limit: num(why.warning_min) !== null ? `${why.warning_min} / ${why.critical_min} min` : "–",
    };
  });

  const onShift = (physicians.items ?? []).filter((p) => !list(p.exclusion_reasons).includes("off_shift"));
  const doctors: Physician[] = onShift.map((p) => ({
    id: String(p.physician_id), name: name(p.physician_id), status: String(p.self_reported_status), derived: String(p.derived_state),
    camera: list(p.flags).includes("external_platform") ? "Active, no session" : "–", helper: String(p.desktop_agent),
    canTakeCalls: Boolean(p.routable), workload: `${p.consults_this_shift} consults · ${p.open_consults} open`,
    reason: list(p.exclusion_reasons).join(", ") || "–",
  }));

  const headline = (snapshot.headline ?? {}) as Row;
  return {
    queue: items, consults, physicians: doctors,
    headline: {
      openConsults: Number(headline.open_consults ?? consults.length), pastCritical: Number(headline.critical ?? 0),
      freePhysicians: doctors.filter((d) => d.canTakeCalls).length, totalPhysicians: doctors.length,
      signalDisagreements: onShift.filter((p) => list(p.flags).length > 0).length,
      shortIn90: Number(headline.hard_gaps_in_horizon ?? 0), waitingOnPerson: Number(snapshot.pending_approvals ?? 0),
    },
  };
}
