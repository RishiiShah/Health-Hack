// In-memory stand-in for the backend, used only when VITE_DEMO_DATA=1. Its data was captured from the real
// backend at 18:20 on the training day (see data/), so screens show what the server really sends.
import type { AuditEntry, IngestReport, Offer } from "../act/types.ts";
import auditData from "./data/audit.json" with { type: "json" };
import candidatesData from "./data/candidates.json" with { type: "json" };
import offerData from "./data/offer.json" with { type: "json" };
import scheduleData from "./data/schedule.json" with { type: "json" };
import sentData from "./data/sent_message.json" with { type: "json" };
import snapshotData from "./data/snapshot.json" with { type: "json" };
import trapData from "./data/trap_check.json" with { type: "json" };

type Request = { method: string; path: string; body?: string; token?: string | null };
type Role = "coordinator" | "lead" | "physician";
type Account = { email: string; name: string; role: Role; role_label: string; physician_id: string | null };
type Cell = { at: string; count: number | null; required: number | null; status: string; gap_id?: string | null };
type Intervention = { intervention_id: string; kind: string; item_id: string; physician_id: string | null; reason: string; created_at: string; state: string };

const ROLE_LABELS: Record<Role, string> = { coordinator: "Operations coordinator", lead: "Clinical lead", physician: "Physician" };
const account = (email: string, name: string, role: Role, physician_id: string | null = null): Account =>
  ({ email, name, role, role_label: ROLE_LABELS[role], physician_id });
// Any password works for these.
export const DEMO_ACCOUNTS = [
  account("coord@demo.sevaro", "Jordan Ellis", "coordinator"),
  account("lead@demo.sevaro", "Dr. Amara Singh", "lead"),
  account("okafor@demo.sevaro", "Dr. Grace Okafor", "physician", "PHY-009"),
  account("shah@demo.sevaro", "Dr. Priya Shah", "physician", "PHY-005"),
];
const PORTAL_ROLES: Record<string, Role[]> = { operations: ["coordinator", "lead"], physician: ["physician"] };

// Same role table as docs/Web-Joy.md.
function rolesFor(method: string, parts: string[]): Role[] {
  if (parts[0] === "auth") return ["coordinator", "lead", "physician"];
  if (parts[0] === "me") return ["physician"];
  if (method === "POST" && parts[0] === "offers") return parts.length === 1 ? ["coordinator"] : ["lead"];
  if (method === "POST" && parts[0] === "interventions") return parts.length === 1 ? ["coordinator", "lead"] : ["lead"];
  return ["coordinator", "lead"];
}

const cellStatus = (count: number, required: number) => (count < required ? "gap" : count === required ? "at_minimum" : "above_minimum");

export function createDemoServer(localNow: () => number = Date.now) {
  const startedAt = localNow();
  const baseNow = Date.parse(snapshotData.clock.now);
  let advancedMs = 0;
  let pausedAt: number | null = null;
  let revision = snapshotData.revision;
  let offers: Offer[] = [];
  let audit: AuditEntry[] = [];
  let interventions: Intervention[] = [];
  const reset = () => {
    advancedMs = 0; pausedAt = null; revision += 1;
    offers = [structuredClone(offerData) as Offer];
    audit = structuredClone(auditData.items) as AuditEntry[];
    interventions = [];
  };
  reset();

  const now = () => baseNow + advancedMs + ((pausedAt ?? localNow()) - startedAt);
  const iso = () => new Date(now()).toISOString();
  const log = (actor: string, action: string, detail: string) => audit.push({ at: iso(), actor, action, detail });

  function expire() {
    for (const o of offers) {
      if (o.state === "Sent" && o.expires_at && Date.parse(o.expires_at) <= now()) {
        o.state = "Expired";
        log("System", "Offer expired", `${o.physician_name} did not reply in time`);
      }
    }
  }

  // An accepted offer adds the physician to its hospitals for its hours, as the server's re-check would.
  function snapshot() {
    const s = structuredClone(snapshotData);
    for (const o of offers.filter((x) => x.state === "Accepted")) {
      const hospitals = (o as Offer & { hospital_ids?: string[] }).hospital_ids ?? [];
      for (const h of s.coverage.hospitals.filter((x) => hospitals.includes(x.hospital_id))) {
        for (const c of h.cells as Cell[]) {
          if (c.count === null || c.required === null || Date.parse(c.at) < Date.parse(o.start) || Date.parse(c.at) >= Date.parse(o.end)) continue;
          c.count += 1;
          c.status = cellStatus(c.count, c.required);
          if (c.status !== "gap") c.gap_id = null;
        }
      }
    }
    const proposed = offers.filter((o) => o.state === "Proposed").length;
    return {
      ...s, revision, sequence: revision,
      clock: { mode: pausedAt !== null ? "fixed" : "demo", now: iso(), paused: pausedAt !== null },
      headline: { ...s.headline, offers_awaiting_approval: proposed, offers_out: offers.filter((o) => o.state === "Sent").length },
      offers: { supported: true, items: offers },
      pending_approvals: proposed + interventions.filter((i) => i.state === "pending").length,
    };
  }

  function myShift(physicianId: string) {
    const s = snapshotData;
    const names = Object.fromEntries(s.hospitals.items.map((h) => [h.hospital_id, h.name]));
    const work = s.workload.items.find((w) => w.physician_id === physicianId);
    const me = s.physicians.items.find((p) => p.physician_id === physicianId);
    return {
      name: work?.name ?? physicianId, shift_end: work?.shift_end ?? null, minutes_to_shift_end: work?.minutes_to_shift_end ?? null,
      hospitals: (me?.credentialed_hospitals ?? []).map((h) => names[h] ?? h),
      consults: s.consults.filter((c) => c.physician_id === physicianId).map((c) => ({
        consult_id: c.consult_id, hospital_name: names[c.hospital_id] ?? c.hospital_id, consult_type: c.consult_type,
        stage: c.current_stage, minutes_in_stage: c.minutes_in_stage,
      })),
    };
  }

  function handle({ method, path, body, token }: Request): unknown {
    expire();
    const url = new URL(path, "http://demo");
    const parts = url.pathname.split("/").filter(Boolean).map(decodeURIComponent);
    // CSV uploads send plain text; every other body is JSON.
    const json = body && url.pathname !== "/events/csv" ? JSON.parse(body) : {};

    if (method === "POST" && url.pathname === "/auth/login") {
      const user = DEMO_ACCOUNTS.find((a) => a.email === String(json.email).trim().toLowerCase());
      if (!user || !json.password) throw { status: 401, detail: "Email or password is incorrect." };
      if (json.portal && !PORTAL_ROLES[json.portal]?.includes(user.role)) {
        const right = user.role === "physician" ? "Physician" : "Operations";
        throw { status: 403, detail: `This is a ${user.role_label.toLowerCase()} account. Sign in as ${right} instead.` };
      }
      return { token: `demo.${user.email}`, expires_at: Math.floor(Date.now() / 1000) + 12 * 3600, user };
    }
    const user = DEMO_ACCOUNTS.find((a) => token === `demo.${a.email}`);
    if (!user) throw { status: 401, detail: "Sign in to continue." };
    if (!rolesFor(method, parts).includes(user.role)) throw { status: 403, detail: `A ${user.role_label.toLowerCase()} can't do this.` };

    if (url.pathname === "/auth/me") return { user };
    if (url.pathname === "/me/shift") return myShift(user.physician_id!);
    if (parts[0] === "me" && parts[1] === "offers") {
      // Physicians only ever see offers a lead has approved and sent to them.
      const mine = offers.filter((o) => o.physician_id === user.physician_id && !["Proposed", "Approved", "Rejected"].includes(o.state));
      if (method === "GET") return { now: iso(), items: mine };
      const offer = mine.find((o) => o.offer_id === parts[2]);
      if (!offer) throw { status: 404, detail: "offer not found" };
      if (offer.state !== "Sent") throw { status: 409, detail: `This offer is ${offer.state.toLowerCase()}.` };
      const accepted = parts[3] === "accept";
      Object.assign(offer, { state: accepted ? "Accepted" : "Declined", responded_at: iso() });
      if (accepted) for (const other of offers) if (other !== offer && other.gap_id === offer.gap_id && ["Proposed", "Sent"].includes(other.state)) other.state = "Withdrawn";
      log(user.name, accepted ? "Accepted offer" : "Declined offer", offer.hospital_names.join(", "));
      revision += 1;
      return offer;
    }

    if (method === "GET") {
      if (url.pathname === "/snapshot") return snapshot();
      if (url.pathname === "/offers") return { items: offers };
      if (url.pathname === "/audit") return { items: audit };
      if (url.pathname === "/schedule") return scheduleData;
      if (url.pathname === "/interventions") {
        const state = url.searchParams.get("state");
        return { items: interventions.filter((i) => !state || i.state === state) };
      }
      if (parts[0] === "gaps") {
        if (parts[1] !== candidatesData.gap.gap_id) throw { status: 404, detail: "The demo only has decision data for the Suncrest gap." };
        if (parts[2] === "candidates") return candidatesData;
        if (parts[2] === "trap-check") return trapData;
      }
    }

    if (method === "POST") {
      if (parts[0] === "offers" && parts.length === 3) {
        const offer = offers.find((o) => o.offer_id === parts[1]);
        if (!offer) throw { status: 404, detail: "offer not found" };
        if (offer.state !== "Proposed") throw { status: 409, detail: `offer is ${offer.state}` };
        if (parts[2] === "approve") {
          Object.assign(offer, {
            state: "Sent", approved_by: user.name, approved_at: iso(), sent_at: iso(),
            expires_at: new Date(now() + 10 * 60_000).toISOString(), message: sentData.message,
            // Recorded once by the backend's ElevenLabs voice from sentData.message; the browser never holds the key.
            audio_url: new URL("./offer-call.mp3", import.meta.url).href,
          });
          log(user.name, "Approved offer", offer.physician_name);
          log("System", "Sent offer", offer.physician_name);
        } else {
          Object.assign(offer, { state: "Rejected", reject_reason: json.reason });
          log(user.name, "Rejected offer", json.reason);
        }
        revision += 1;
        return offer;
      }
      if (url.pathname === "/offers") {
        const candidate = candidatesData.candidates.find((c) => c.physician_id === json.physician_id);
        if (json.gap_id !== candidatesData.gap.gap_id || !candidate?.eligible) {
          throw { status: 422, detail: `${candidate?.name ?? "This physician"} is not a candidate for this gap: ${candidate?.primary_reason ?? "not in the current queue"}` };
        }
        if ((Date.parse(json.end) - Date.parse(json.start)) / 3_600_000 < 2) throw { status: 422, detail: "R6 offer of at least 2 h: shorter than 2 hours" };
        if (offers.some((o) => o.gap_id === json.gap_id && ["Proposed", "Sent"].includes(o.state))) throw { status: 409, detail: "This gap already has an open offer." };
        const offer = {
          ...(structuredClone(offerData) as Offer), offer_id: `OFR-${String(offers.length + 1).padStart(5, "0")}`,
          start: json.start, end: json.end, proposed_by: user.name, proposed_at: iso(),
        };
        offers.push(offer);
        log(user.name, "Proposed offer", offer.physician_name);
        return offer;
      }
      if (url.pathname === "/interventions") {
        const record: Intervention = {
          intervention_id: `INT-${interventions.length + 1}`, kind: json.kind, item_id: json.item_id, physician_id: json.physician_id ?? null,
          reason: `${json.kind} requested by ${user.name}`, created_at: iso(), state: json.kind === "escalate" ? "pending" : "recorded",
        };
        interventions.push(record);
        log(user.name, json.kind === "escalate" ? "Escalation requested" : "Reassignment recorded", json.item_id);
        return record;
      }
      if (parts[0] === "interventions" && parts[2] === "authorize") {
        const record = interventions.find((i) => i.intervention_id === parts[1]);
        if (!record) throw { status: 404, detail: "intervention not found" };
        record.state = "authorized";
        log(user.name, "Escalation authorized", record.item_id);
        return record;
      }
      if (url.pathname === "/events" || url.pathname === "/events/csv") {
        const lines = url.pathname === "/events" ? [] : (body ?? "").trim().split("\n").filter((l) => l && !l.startsWith("event_id"));
        const rows = url.pathname === "/events" ? [json].flat().length : lines.length;
        const times = lines.map((l) => Date.parse(l.split(",")[1])).filter((t) => !Number.isNaN(t));
        revision += 1;
        return { accepted: rows, duplicates: 0, conflicts: 0, reordered: 0, late: 0, held_orphans: 0, quarantined: [], revision, pending_future: 0,
          latest_event_time: times.length ? new Date(Math.max(...times)).toISOString() : null } satisfies IngestReport;
      }
      if (url.pathname === "/admin/clock") {
        if (json.at) advancedMs += Date.parse(json.at) - now();
        if (json.advance_s) advancedMs += json.advance_s * 1000;
        if (json.paused === true && pausedAt === null) pausedAt = localNow();
        if (json.paused === false && pausedAt !== null) { advancedMs -= localNow() - pausedAt; pausedAt = null; }
        return { mode: "demo", now: iso() };
      }
      if (url.pathname === "/admin/reset") { reset(); return { revision }; }
    }
    throw { status: 404, detail: "Not Found" };
  }

  return { handle, now };
}
