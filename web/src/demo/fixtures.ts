// Demo data copied from WebDesign.pdf (18:22 ET on the training day). Loaded only when VITE_DEMO_DATA=1.
import type { AuditEntry, Candidates, Offer, TrapCheck } from "../act/types.ts";
import type { Coverage, CoverageCell, Demand, Workload } from "../forecast/types.ts";

export const BASE_NOW = "2026-03-17T18:22:00-04:00";
const at = (hhmm: string) => `2026-03-17T${hhmm}:00-04:00`;
const STEPS = [BASE_NOW, at("18:30"), at("18:45"), at("19:00"), at("19:15"), at("19:30"), at("19:45")];
const ON_SHIFT = ["PHY-001", "PHY-002", "PHY-003", "PHY-004", "PHY-005", "PHY-006", "PHY-007", "PHY-008"];
const GAP_ID = "GAP-SUNCREST-1900";

function cell(i: number, count: number, required: number, extra: Partial<CoverageCell> = {}): CoverageCell {
  return {
    at: STEPS[i], count, required,
    status: count < required ? "gap" : count === required ? "at_minimum" : "above_minimum",
    unverified: false, schedule_incomplete: false, physician_ids: ON_SHIFT.slice(0, count), incomplete_physician_ids: [], gap_id: null,
    ...extra,
  };
}

// [name, nobody reachable now, counts per step, required per step]
const ROWS: [string, boolean, number[], number[]][] = [
  ["Suncrest", true, [3, 3, 3, 1, 1, 1, 1], [2, 2, 2, 2, 1, 1, 1]],
  ["Oak Valley", true, [1, 1, 1, 1, 1, 1, 1], [1, 1, 1, 1, 1, 1, 1]],
  ["Redwood Univ.", false, [2, 2, 2, 2, 2, 2, 2], [2, 2, 2, 2, 2, 2, 2]],
  ["Cedar Ridge", false, [4, 4, 4, 2, 2, 2, 2], [2, 2, 2, 2, 2, 2, 2]],
  ["Northfield", true, [4, 4, 4, 3, 3, 3, 3], [2, 2, 2, 2, 2, 2, 2]],
  ["Lakeview", false, [4, 4, 4, 2, 2, 2, 2], [1, 1, 1, 1, 1, 1, 1]],
  ["Meadowlands", true, [4, 4, 4, 2, 2, 2, 2], [1, 1, 1, 1, 1, 1, 1]],
  ["Harbor Regional", true, [4, 4, 4, 3, 3, 3, 3], [1, 1, 1, 1, 1, 1, 1]],
  ["Highland Valley", false, [3, 3, 3, 2, 2, 2, 2], [1, 1, 1, 1, 1, 1, 1]],
  ["Westbridge", true, [4, 4, 4, 2, 2, 2, 2], [1, 1, 1, 1, 1, 1, 1]],
  ["Bluewater", true, [2, 2, 2, 2, 2, 2, 2], [1, 1, 1, 1, 1, 1, 1]],
  ["Silver Oak", false, [2, 2, 2, 2, 2, 2, 2], [1, 1, 1, 1, 1, 1, 1]],
];

export const coverage = (accepted: boolean): Coverage => ({
  supported: true,
  steps: STEPS,
  assumption: "a surge adds 1",
  hospitals: ROWS.map(([name, bang, counts, required], h) => ({
    hospital_id: `SYN-${String(h + 1).padStart(3, "0")}`,
    hospital_name: name,
    nobody_reachable_now: bang,
    cells: counts.map((count, i) =>
      h === 0 && i === 3
        ? accepted
          ? cell(i, 2, 2, { physician_ids: ["PHY-005", "PHY-009"] })
          : cell(i, 1, 2, { schedule_incomplete: true, physician_ids: ["PHY-005"], incomplete_physician_ids: ["PHY-010"], gap_id: GAP_ID })
        : cell(i, count, required[i], h === 9 ? { unverified: true } : {}),
    ),
  })),
});

export const demand: Demand = {
  supported: true,
  items: [
    { hospital_id: "SYN-001", hospital_name: "Suncrest", trailing_60m: 5, p90: 1, status: "surge" },
    { hospital_id: "SYN-006", hospital_name: "Lakeview", trailing_60m: 1, p90: 2, status: "normal" },
    { hospital_id: "SYN-002", hospital_name: "Oak Valley", trailing_60m: 2, p90: 2, status: "normal" },
    { hospital_id: "SYN-008", hospital_name: "Harbor Regional", trailing_60m: 1, p90: 2, status: "normal" },
    { hospital_id: "SYN-012", hospital_name: "Silver Oak", trailing_60m: 0, p90: null, status: "unknown" },
  ],
};

export const workload: Workload = {
  supported: true,
  items: [
    { physician_id: "PHY-003", name: "Dr. Sofia Ramirez", consults: 14, calls: 17, open_consults: 3, shift_end: at("19:00"), minutes_to_shift_end: 38, overload: "Critical", shift_end_risk: "Critical", open_notes: 2, reason: "2 notes open, leaves in 38 min" },
    { physician_id: "PHY-006", name: "Dr. Marcus Lee", consults: 12, calls: 15, open_consults: 3, shift_end: at("19:00"), minutes_to_shift_end: 38, overload: "Critical", shift_end_risk: "Warning", open_notes: 1, reason: "3 open consults, leaves in 38 min" },
    { physician_id: "PHY-002", name: "Dr. Daniel Kim", consults: 13, calls: 14, open_consults: 3, shift_end: at("20:00"), minutes_to_shift_end: 98, overload: "Warning", shift_end_risk: null, open_notes: 0, reason: "3 open consults" },
    { physician_id: "PHY-005", name: "Dr. Priya Shah", consults: 15, calls: 18, open_consults: 2, shift_end: at("20:00"), minutes_to_shift_end: 98, overload: null, shift_end_risk: null, open_notes: 1, reason: "On a call" },
    { physician_id: "PHY-004", name: "Dr. Ethan Brooks", consults: 9, calls: 11, open_consults: 1, shift_end: at("21:00"), minutes_to_shift_end: 158, overload: null, shift_end_risk: null, open_notes: 1, reason: "Writing a note" },
  ],
};

export const dataQuality = {
  supported: true, events_read: 1164, accepted: 1163, duplicates: 1, duplicate_ids: ["EVT-00529"], conflicts: 0,
  reordered: 23, late: 1, max_reorder_lag_s: 355, max_delivery_lag_s: 405, rejected: 0, pending_orphans: 0, expired_orphans: 0,
};

export const dataset = { name: "training data", description: "Tue 17 Mar, 07:00 to 18:20 ET · 1,164 events", reference_files: 7 };

const RULES = [
  ["R1", "Opted in to extra shifts"], ["R2", "Credentialed at a gap hospital"], ["R3", "10 h rest since last shift"],
  ["R4", "7-day hours plus offer at most 60"], ["R5", "No overlap with a scheduled shift"], ["R6", "At least 2 h and can come online"],
  ["R7", "No other open offer"], ["R8", "Under 3 offers in 7 days"],
].map(([id, label]) => ({ id, label }));

function results(failed: string | null, explanation: string, status: "fail" | "unknown" = "fail") {
  return RULES.map((r) => (r.id === failed ? { rule: r.id, status, explanation } : { rule: r.id, status: "pass" as const, explanation: "Meets the rule" }));
}

export const candidates: Candidates = {
  revision: 2,
  rules: RULES,
  gap: {
    gap_id: GAP_ID, hospital_ids: ["SYN-001"], hospital_names: ["Suncrest Medical Pavilion"], start: at("19:00"), end: at("23:00"), required: 2, count: 1,
    summary: "Suncrest has had 5 consults in the last hour, against a usual peak of 1, so it needs 2 physicians. Dr. Ramirez and Dr. Lee leave at 19:00. Dr. Cho's night shift should start then, but Dr. Cho hasn't logged on, which leaves Dr. Shah alone.",
  },
  candidates: [
    { physician_id: "PHY-009", name: "Grace Okafor", eligible: true, rank: 1, primary_reason: null, results: results(null, ""), ranking: { gap_hospitals: 1, minutes_to_online: 15, declines_30d: 0, hours_7d: 36 } },
    { physician_id: "PHY-011", name: "Ben Alvarez", eligible: false, rank: null, primary_reason: "Not credentialed at Suncrest", results: results("R2", "Not credentialed at Suncrest"), ranking: { gap_hospitals: 0, minutes_to_online: 20, declines_30d: 1, hours_7d: 30 } },
    { physician_id: "PHY-010", name: "Hannah Cho", eligible: false, rank: null, primary_reason: "Already scheduled from 19:00", results: results("R5", "Night shift starts 19:00; end time not in the roster", "unknown"), ranking: { gap_hospitals: 1, minutes_to_online: null, declines_30d: 0, hours_7d: 24 } },
    { physician_id: "PHY-012", name: "Omar Haddad", eligible: false, rank: null, primary_reason: "Not opted in, shift at 20:00", results: results("R1", "Not opted in to extra shifts"), ranking: { gap_hospitals: 1, minutes_to_online: 10, declines_30d: 2, hours_7d: 40 } },
    { physician_id: "PHY-013", name: "Lucy Brennan", eligible: false, rank: null, primary_reason: "Not opted in", results: results("R1", "Not opted in to extra shifts"), ranking: { gap_hospitals: 1, minutes_to_online: 25, declines_30d: 0, hours_7d: 20 } },
    { physician_id: "PHY-014", name: "Ravi Menon", eligible: false, rank: null, primary_reason: "Would reach 63 hours this week", results: results("R4", "59 h in 7 days plus a 4 h offer is 63 h"), ranking: { gap_hospitals: 1, minutes_to_online: 12, declines_30d: 0, hours_7d: 59 } },
  ],
};

export const trapCheck: TrapCheck = {
  gap_id: GAP_ID, physician_id: "PHY-009", passed: true, reasons: [],
  seed_consults: 15, limited_to: [{ hospital_id: "SYN-001", hospital_name: "Suncrest" }],
  steps: [at("19:00"), at("19:15"), at("19:30"), at("19:45")],
  without: Array(4).fill({ count: 1, required: 2 }), with: Array(4).fill({ count: 2, required: 2 }),
  joiner_load: 15, busiest_peer_load: 15, other_gaps_worsened: false,
  assumption: "Simulated with routing rules and baseline demand, assuming the surge continues.",
};

export const offer = (): Offer => ({
  offer_id: "OFFER-1", gap_id: GAP_ID, physician_id: "PHY-009", physician_name: "Dr. Grace Okafor",
  hospital_names: ["Suncrest Medical Pavilion"], start: at("19:00"), end: at("23:00"), state: "Proposed", checked_count: 6,
  proposed_by: "System", proposed_at: at("18:20"), approved_by: null, approved_at: null, sent_at: null, expires_at: null, responded_at: null,
  message: "Coverage request: Suncrest Medical Pavilion, 19:00 to 23:00 ET tonight. You're credentialed there and eligible. Reply within 10 minutes.",
  audio_url: null, phone_url: null, reject_reason: null,
});

export const audit = (): AuditEntry[] => [
  { at: at("18:20"), actor: "System", action: "Found gap", detail: "Suncrest 19:00, 1 of 2" },
  { at: "2026-03-17T18:20:02-04:00", actor: "System", action: "Checked 6 off-shift physicians", detail: "1 eligible" },
  { at: "2026-03-17T18:20:03-04:00", actor: "System", action: "Proposed offer", detail: "Dr. Grace Okafor, 19:00 to 23:00" },
];
