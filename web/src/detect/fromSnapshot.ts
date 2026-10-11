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
  return [...new Set(parts.filter(Boolean))].join(". ");
}

export function detectFromSnapshot(snapshot: Row): DetectSnapshot | null {
  const queue = snapshot.queue as Section | undefined;
  const physicians = snapshot.physicians as Section | undefined;
  if (!queue?.supported || !physicians?.supported) return null;
  const hospitals = Object.fromEntries(((snapshot.hospitals as Section)?.items ?? []).map((h) => [h.hospital_id, String(h.name)]));
  const workload = new Map(((snapshot.workload as Section)?.items ?? []).map((w) => [String(w.physician_id), w]));
  const names = Object.fromEntries([...(physicians.items ?? []), ...((snapshot.workload as Section)?.items ?? [])]
    .filter((p) => str(p.name)).map((p) => [p.physician_id, String(p.name)]));
  const name = (id: unknown) => names[String(id)] ?? String(id);
  // Replace whole identifiers only; keep unknown identifiers and command IDs intact.
  const displayNames = (value: unknown) => String(value ?? "").replace(
    /[A-Za-z0-9_-]+/g, (word) => names[word] ?? hospitals[word] ?? word,
  );

  const items: QueueItem[] = (queue.items ?? []).map((item) => {
    const where = (item.where ?? {}) as Row;
    const fix = (item.fix ?? {}) as Row;
    const hospital = str(where.hospital_id) ? hospitals[String(where.hospital_id)] ?? String(where.hospital_id) : null;
    const sites = list(where.hospital_ids).map((h) => hospitals[h] ?? h);
    const label = str(where.consult_id)
      ? `${where.consult_id}${hospital ? ` · ${hospital}` : ""}`
      : (str(where.physician_id) ? name(where.physician_id) : null) ?? hospital ?? (sites.length ? sites.join(", ") : String(item.what));
    return {
      id: String(item.id), label, kind: String(item.id).split(":")[0], level: String(item.severity), rank: Number(item.rank),
      reason: displayNames(item.what),
      watchOnly: fix.kind === "watch",
      where: [hospital, str(where.consult_id), str(where.physician_id) ? name(where.physician_id) : null,
        ...list(where.hospital_ids).map((h) => hospitals[h] ?? h)].filter(Boolean).join(" · "),
      why: displayNames(describeWhy((item.why ?? {}) as Row)),
      fix: displayNames(fix.action), fixKind: String(fix.kind ?? ""), fixReason: displayNames(fix.reason), alternatives: list(fix.alternatives).map(displayNames),
      approver: APPROVERS[String(fix.approver)] ?? String(fix.approver ?? ""),
      physicianId: str(fix.physician_id),
    };
  });

  const byConsult = new Map<string, QueueItem & { raw: Row }>();
  (queue.items ?? []).forEach((raw, i) => {
    const consultId = str((raw.where as Row | undefined)?.consult_id);
    if (consultId && !byConsult.has(consultId)) byConsult.set(consultId, { ...items[i], raw });
  });
  const publishedAt = Date.parse(String((snapshot.clock as Row | undefined)?.now));
  const stageMinutes = (at: unknown, fallback: unknown) => {
    const enteredAt = Date.parse(String(at));
    return Number.isFinite(publishedAt) && Number.isFinite(enteredAt)
      ? Math.max(0, (publishedAt - enteredAt) / 60_000) : Number(fallback);
  };
  const consults: Consult[] = ((snapshot.consults as Row[]) ?? []).map((c) => {
    const flagged = byConsult.get(String(c.consult_id));
    const why = (flagged?.raw.why ?? {}) as Row;
    return {
      id: String(c.consult_id), hospital: hospitals[String(c.hospital_id)] ?? String(c.hospital_id), type: String(c.consult_type),
      stage: String(c.current_stage), minutesInStage: stageMinutes(c.stage_entered_at, c.minutes_in_stage), minutesSinceReceived: Number(c.minutes_since_received),
      physicianId: str(c.physician_id) && c.physician_id !== "Unassigned" ? String(c.physician_id) : null,
      physicianName: str(c.physician_id) && c.physician_id !== "Unassigned" ? name(c.physician_id) : null,
      routingFailures: num(c.routing_failures) ?? 0,
      warningMinutes: num(why.warning_min), criticalMinutes: num(why.critical_min), standardAge: num(why.age_min),
      standardClock: str(why.interaction_ended) ? "Since interaction ended" : "Time in stage",
      // The server's own level per consult; "none" = within the standard, null = no standard for this stage.
      level: str(c.level) && c.level !== "none" ? String(c.level) : flagged?.level ?? "Normal",
      limit: Array.isArray(c.limit_min) ? `${c.limit_min[0]} / ${c.limit_min[1]} min`
        : num(why.warning_min) !== null ? `${why.warning_min} / ${why.critical_min} min` : "–",
    };
  });

  const onShift = (physicians.items ?? []).filter((p) => !list(p.exclusion_reasons).includes("off_shift"));
  const doctors: Physician[] = onShift.map((p) => {
    const work = workload.get(String(p.physician_id));
    return {
      id: String(p.physician_id), name: name(p.physician_id), status: String(p.self_reported_status), derived: String(p.derived_state),
      camera: list(p.flags).includes("external_platform") ? "Active, no session" : "–", helper: String(p.desktop_agent),
      canTakeCalls: Boolean(p.routable), workload: `${p.consults_this_shift} consults · ${p.open_consults} open`,
      reason: list(p.exclusion_reasons).join(", ") || "–", flags: list(p.flags),
      calls: num(p.calls_this_shift) ?? num(work?.calls), consults: num(p.consults_this_shift), openConsults: num(p.open_consults),
      pendingNotes: consults.filter((c) => c.physicianId === p.physician_id && ["Note Pending", "Documentation"].includes(c.stage)).length,
      minutesToShiftEnd: num(p.minutes_to_shift_end),
      hospitals: list(p.credentialed_hospitals).map((id) => ({ id, name: hospitals[id] ?? id })),
    };
  });

  const headline = (snapshot.headline ?? {}) as Row;
  return {
    queue: items, consults, physicians: doctors,
    headline: {
      openConsults: Number(headline.open_consults ?? consults.length), pastCritical: Number(headline.consults_past_critical ?? headline.critical ?? 0),
      freePhysicians: doctors.filter((d) => d.canTakeCalls).length, totalPhysicians: doctors.length,
      signalDisagreements: onShift.filter((p) => list(p.flags).length > 0).length,
      shortIn90: Number(headline.hospitals_short_in_horizon ?? headline.hard_gaps_in_horizon ?? 0), waitingOnPerson: Number(snapshot.pending_approvals ?? 0),
      overloadedPhysicians: Number(headline.overloaded_physicians ?? 0), forecastHorizonMinutes: Number(headline.forecast_horizon_minutes ?? 90),
    },
  };
}
