// Minimal scaffold for Anish to replace with the /ws client: polls /snapshot until the WebSocket exists.
import { useCallback, useEffect, useState } from "react";
import { LOCAL_MOCK_MODE } from "./client.ts";

export type Snapshot = {
  revision: number;
  epoch: string;
  clock: { mode: string; now: string };
  [section: string]: unknown;
};

export type DemoOffer = {
  offer_id: string; gap_id: string; physician_id: string; physician_name: string; hospital_names: string[];
  start: string; end: string; state: "Proposed"; checked_count: number; proposed_by: string;
  proposed_at: string; approved_by: string | null; approved_at: string | null; sent_at: string | null;
  expires_at: string; responded_at: string | null; message: string; audio_url: string | null;
  phone_url: string | null; reject_reason: string | null;
};

const consults = [
  ["CON-2102", "Suncrest", "Stroke", "Imaging", 26, 38, "Critical"], ["CON-2105", "Lakeside", "Stroke", "Routing", 21, 34, "Critical"],
  ["CON-2110", "North Valley", "General Neuro", "Physician call", 18, 31, "Critical"], ["CON-2112", "Mercy West", "Stroke", "Note", 17, 29, "Critical"],
  ["CON-2114", "Suncrest", "Stroke", "Physician call", 12, 21, "Warning"], ["CON-2104", "Lakeside", "General Neuro", "Triaged", 10, 18, "Warning"],
  ["CON-2113", "North Valley", "Stroke", "Imaging", 9, 16, "Warning"], ["CON-2108", "Mercy West", "General Neuro", "Routing", 8, 15, "Warning"],
  ...Array.from({ length: 10 }, (_, index) => [`CON-${2115 + index}`, ["Suncrest", "Lakeside", "North Valley", "Mercy West"][index % 4], index % 2 ? "General Neuro" : "Stroke", "Triaged", 4 + (index % 4), 7 + index, "Normal"]),
].map(([id, hospital, type, stage, minutesInStage, minutesSinceCall, level]) => ({ id, hospital, type, stage, minutesInStage, minutesSinceCall, level }));
const forecastTimes = ["2026-03-17T18:20:00-04:00", "2026-03-17T18:30:00-04:00", "2026-03-17T18:40:00-04:00", "2026-03-17T18:50:00-04:00", "2026-03-17T19:00:00-04:00", "2026-03-17T19:10:00-04:00", "2026-03-17T19:20:00-04:00", "2026-03-17T19:30:00-04:00", "2026-03-17T19:40:00-04:00", "2026-03-17T19:50:00-04:00", "2026-03-17T20:00:00-04:00"];

export const STATIC_SNAPSHOT: Snapshot = {
  revision: 18, epoch: "demo-2026-03-17", clock: { mode: "replay", now: "2026-03-17T18:20:00-04:00" },
  dataset: { name: "Tuesday 17 March", description: "Static 18:20 coordinator demo", reference_files: 0 },
  consults,
  coverage: {
    supported: true,
    steps: forecastTimes,
    assumption: "scheduled and confirmed coverage",
    hospitals: [
      { hospital_id: "H-SUN", hospital_name: "Suncrest Medical Pavilion", nobody_reachable_now: false, cells: ["at_minimum", "at_minimum", "at_minimum", "at_minimum", "gap", "gap", "gap", "gap", "gap", "gap", "gap"].map((status, index) => ({ at: forecastTimes[index], count: status === "gap" ? 0 : 1, required: 1, status, unverified: false, schedule_incomplete: false, physician_ids: status === "gap" ? [] : ["PHY-002"], incomplete_physician_ids: [], gap_id: status === "gap" && index === 4 ? "GAP-SUNCREST-1900" : null })) },
      { hospital_id: "H-LAKE", hospital_name: "Lakeside Medical Center", nobody_reachable_now: false, cells: forecastTimes.map((at) => ({ at, count: 2, required: 1, status: "above_minimum", unverified: false, schedule_incomplete: false, physician_ids: ["PHY-004", "PHY-008"], incomplete_physician_ids: [], gap_id: null })) },
      { hospital_id: "H-NORTH", hospital_name: "North Valley", nobody_reachable_now: false, cells: forecastTimes.map((at) => ({ at, count: 1, required: 1, status: "at_minimum", unverified: false, schedule_incomplete: false, physician_ids: ["PHY-003"], incomplete_physician_ids: [], gap_id: null })) },
      { hospital_id: "H-MERCY", hospital_name: "Mercy West", nobody_reachable_now: false, cells: forecastTimes.map((at) => ({ at, count: 1, required: 1, status: "at_minimum", unverified: false, schedule_incomplete: false, physician_ids: ["PHY-005"], incomplete_physician_ids: [], gap_id: null })) },
    ],
  },
  demand: { supported: true, items: [{ hospital_id: "H-SUN", hospital_name: "Suncrest Medical Pavilion", trailing_60m: 6, p90: 4, status: "surge" }, { hospital_id: "H-LAKE", hospital_name: "Lakeside Medical Center", trailing_60m: 4, p90: 5, status: "normal" }, { hospital_id: "H-NORTH", hospital_name: "North Valley", trailing_60m: 3, p90: 4, status: "normal" }, { hospital_id: "H-MERCY", hospital_name: "Mercy West", trailing_60m: 5, p90: 5, status: "normal" }] },
  workload: { supported: true, items: [{ physician_id: "PHY-001", name: "Dr. Patel", consults: 2, calls: 1, open_consults: 0, shift_end: "2026-03-17T20:00:00-04:00", minutes_to_shift_end: 100, overload: null, shift_end_risk: null, open_notes: 0, reason: "Signal needs verification" }, { physician_id: "PHY-002", name: "Dr. Brooks", consults: 0, calls: 0, open_consults: 0, shift_end: "2026-03-17T20:00:00-04:00", minutes_to_shift_end: 100, overload: null, shift_end_risk: null, open_notes: 0, reason: "Free to take a call" }, { physician_id: "PHY-006", name: "Dr. Okafor", consults: 1, calls: 1, open_consults: 1, shift_end: "2026-03-17T23:00:00-04:00", minutes_to_shift_end: 280, overload: null, shift_end_risk: null, open_notes: 1, reason: "Pending Suncrest offer" }, { physician_id: "PHY-004", name: "Dr. Davis", consults: 4, calls: 3, open_consults: 2, shift_end: "2026-03-17T20:00:00-04:00", minutes_to_shift_end: 100, overload: "Warning", shift_end_risk: null, open_notes: 1, reason: "At workload limit" }] },
  headline: { openConsults: 18, pastCritical: 4, freePhysicians: 1, totalPhysicians: 8, signalDisagreements: 2, shortIn90: 1, waitingOnPerson: 1 },
  queue: [
    { id: "CON-2105", kind: "consult", level: "Critical", score: 160, reason: "Routing has failed three times", uncertainty: "Verified", where: "Lakeside Medical Center", why: "No eligible physician has accepted the call", fix: "Escalate to the clinical lead and reassign", approver: "Clinical lead" },
    { id: "Suncrest 19:00", kind: "gap", level: "Warning", score: 147, reason: "Coverage gap opens in 40 minutes", uncertainty: "Verified", where: "Suncrest Medical Pavilion", why: "One stroke line will be uncovered at 19:00", fix: "Review Dr. Okafor's pending offer", approver: "Coordinator" },
    { id: "CON-2102", kind: "consult", level: "Critical", score: 142, reason: "Past critical imaging limit", uncertainty: "Verified", where: "Suncrest Medical Pavilion", why: "26 minutes in imaging", fix: "Escalate to the clinical lead", approver: "Clinical lead" },
    { id: "PHY-001", kind: "signal", level: "Warning", score: 126, reason: "Camera active but no Synapse video", uncertainty: "Unverified", where: "Dr. Patel", why: "Self-report and derived signal disagree", fix: "Confirm availability by phone", approver: "Coordinator" },
    { id: "CON-2110", kind: "consult", level: "Critical", score: 119, reason: "Physician call has not connected", uncertainty: "Verified", where: "North Valley", why: "Call is approaching its critical limit", fix: "Reassign to an eligible physician", approver: "Coordinator" },
    { id: "PHY-007", kind: "signal", level: "Warning", score: 108, reason: "Helper app offline while phone rings", uncertainty: "Unverified", where: "Dr. Torres", why: "Routing cannot verify availability", fix: "Call the physician and mark unavailable", approver: "Coordinator" },
    { id: "CON-2112", kind: "consult", level: "Warning", score: 101, reason: "Note remains unsigned", uncertainty: "Verified", where: "Mercy West", why: "Documentation is blocking completion", fix: "Remind assigned physician", approver: "Coordinator" },
    { id: "CON-2114", kind: "consult", level: "Warning", score: 94, reason: "Open consult waiting on a person", uncertainty: "Verified", where: "Suncrest Medical Pavilion", why: "Awaiting physician response", fix: "Reassign if no response", approver: "Coordinator" },
  ],
  physicians: [
    { id: "PHY-001", name: "Dr. Patel", status: "Available", synapse: "No video", camera: "On", helper: "Online", canTakeCalls: false, workload: "0 active", reason: "camera active, no session" }, { id: "PHY-002", name: "Dr. Brooks", status: "Available", synapse: "Ready", camera: "Off", helper: "Online", canTakeCalls: true, workload: "0 active", reason: "Available" },
    { id: "PHY-003", name: "Dr. Chen", status: "In Meeting", synapse: "In call", camera: "On", helper: "Online", canTakeCalls: false, workload: "1 active", reason: "In meeting" }, { id: "PHY-004", name: "Dr. Davis", status: "Available", synapse: "Ready", camera: "Off", helper: "Online", canTakeCalls: false, workload: "2 active", reason: "At workload limit" },
    { id: "PHY-005", name: "Dr. Evans", status: "Temporarily Unavailable", synapse: "Quiet", camera: "Off", helper: "Online", canTakeCalls: false, workload: "0 active", reason: "Self-reported unavailable" }, { id: "PHY-006", name: "Dr. Okafor", status: "Available", synapse: "Ready", camera: "Off", helper: "Online", canTakeCalls: false, workload: "1 active", reason: "Assigned to current gap" },
    { id: "PHY-007", name: "Dr. Torres", status: "Available", synapse: "Ready", camera: "On", helper: "Offline", canTakeCalls: false, workload: "0 active", reason: "Helper app offline" }, { id: "PHY-008", name: "Dr. Singh", status: "Available", synapse: "Ready", camera: "Off", helper: "Online", canTakeCalls: false, workload: "2 active", reason: "At workload limit" },
  ],
  stuck: [{ id: "CON-2105", failures: 3, retryAt: "18:25 ET", eligible: ["Dr. Brooks"], excluded: ["Dr. Chen: in meeting", "Dr. Torres: helper app offline"] }, { id: "CON-2110", failures: 2, retryAt: "18:25 ET", eligible: [], excluded: ["All credentialed physicians excluded"] }],
  signals: [{ physician: "Dr. Patel", detail: "Camera on, no Synapse video", tone: "warning" }, { physician: "Dr. Torres", detail: "Helper app offline", tone: "warning" }],
};

export const STATIC_OFFERS: { items: DemoOffer[] } = { items: [{ offer_id: "OFF-1900-SUNCREST", gap_id: "GAP-SUNCREST-1900", physician_id: "PHY-006", physician_name: "Dr. Okafor", hospital_names: ["Suncrest Medical Pavilion"], start: "2026-03-17T19:00:00-04:00", end: "2026-03-17T23:00:00-04:00", state: "Proposed", checked_count: 1, proposed_by: "Coordinator", proposed_at: "2026-03-17T18:20:00-04:00", approved_by: null, approved_at: null, sent_at: null, expires_at: "2026-03-17T18:30:00-04:00", responded_at: null, message: "Suncrest needs neuro coverage from 19:00 to 23:00 ET.", audio_url: null, phone_url: null, reject_reason: null }] };

function isNetworkFailure(error: unknown): boolean {
  if (!(error instanceof Error)) return false;
  return error.name === "TypeError" || /network|failed to fetch|econnrefused/i.test(error.message);
}

export type Live = { snapshot: Snapshot | null; receivedAt: number; error: string | null; refresh: () => void };

export function useSnapshot(intervalMs = 2000): Live {
  const [state, setState] = useState<Omit<Live, "refresh">>({ snapshot: null, receivedAt: 0, error: null });

  const refresh = useCallback(() => {
    if (LOCAL_MOCK_MODE) {
      setState({ snapshot: STATIC_SNAPSHOT, receivedAt: Date.now(), error: null });
      return;
    }
    /* istanbul ignore next */
    Promise.reject(new Error("Live snapshot transport is disabled in local mode")).catch((error: unknown) => {
      if (isNetworkFailure(error) || error instanceof Error) return STATIC_SNAPSHOT;
      return STATIC_SNAPSHOT;
    }).then(
      (snapshot) => setState({ snapshot, receivedAt: Date.now(), error: null }),
      (error: Error) => setState((prev) => ({ ...prev, error: error.message })),
    );
  }, []);

  useEffect(() => {
    refresh();
    const timer = setInterval(refresh, intervalMs);
    return () => clearInterval(timer);
  }, [refresh, intervalMs]);

  return { ...state, refresh };
}
