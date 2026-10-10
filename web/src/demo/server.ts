// In-memory stand-in for the backend, used only when VITE_DEMO_DATA=1. Mirrors the routes in docs/Web-Joy.md.
import type { AuditEntry, IngestReport, Offer } from "../act/types.ts";
import * as fx from "./fixtures.ts";

type Request = { method: string; path: string; body?: string; token?: string | null };
type Role = "coordinator" | "lead" | "physician";
type Account = { email: string; name: string; role: Role; role_label: string; physician_id: string | null };

const ROLE_LABELS: Record<Role, string> = { coordinator: "Operations coordinator", lead: "Clinical lead", physician: "Physician" };
const account = (email: string, name: string, role: Role, physician_id: string | null = null): Account =>
  ({ email, name, role, role_label: ROLE_LABELS[role], physician_id });
// Any password works for these, as the design's demo note says.
export const DEMO_ACCOUNTS = [
  account("coordinator@demo.sevaro", "Jordan Ellis", "coordinator"),
  account("lead@demo.sevaro", "Dr. Amara Singh", "lead"),
  account("okafor@demo.sevaro", "Dr. Grace Okafor", "physician", "PHY-009"),
  account("shah@demo.sevaro", "Dr. Priya Shah", "physician", "PHY-005"),
];
const PORTAL_ROLES: Record<string, Role[]> = { operations: ["coordinator", "lead"], physician: ["physician"] };

// Same role table as the proposal in docs/Web-Joy.md.
function rolesFor(method: string, parts: string[]): Role[] {
  if (parts[0] === "auth") return ["coordinator", "lead", "physician"];
  if (parts[0] === "me") return ["physician"];
  if (method === "POST" && parts[0] === "offers") return parts.length === 1 ? ["coordinator"] : ["lead"];
  if (method === "POST" && parts[0] === "interventions") return ["lead"];
  return ["coordinator", "lead"];
}

export function createDemoServer(localNow: () => number = Date.now) {
  const startedAt = localNow();
  let advancedMs = 0;
  let pausedAt: number | null = null;
  let revision = 2;
  let offers: Offer[] = [fx.offer()];
  let audit: AuditEntry[] = fx.audit();

  const now = () => Date.parse(fx.BASE_NOW) + advancedMs + ((pausedAt ?? localNow()) - startedAt);
  const iso = () => new Date(now()).toISOString();
  const log = (actor: string, action: string, detail: string) => audit.push({ at: iso(), actor, action, detail });
  const reset = () => { advancedMs = 0; pausedAt = null; offers = [fx.offer()]; audit = fx.audit(); revision += 1; };

  function expire() {
    for (const o of offers) {
      if (o.state === "Sent" && o.expires_at && Date.parse(o.expires_at) <= now()) {
        o.state = "Expired";
        log("System", "Offer expired", `${o.physician_name} did not reply in time`);
      }
    }
  }

  function handle({ method, path, body, token }: Request): unknown {
    expire();
    const url = new URL(path, "http://demo");
    const parts = url.pathname.split("/").filter(Boolean);
    const json = body ? JSON.parse(body) : {};

    if (method === "POST" && url.pathname === "/auth/login") {
      const user = DEMO_ACCOUNTS.find((a) => a.email === String(json.email).trim().toLowerCase());
      if (!user || !json.password) throw { status: 401, detail: "Email or password is incorrect." };
      if (json.portal != null && !PORTAL_ROLES[json.portal]?.includes(user.role)) {
        const right = user.role === "physician" ? "Physician" : "Operations";
        throw { status: 403, detail: `This is a ${user.role_label.toLowerCase()} account. Sign in as ${right} instead.` };
      }
      return { token: `demo.${user.email}`, expires_at: Math.floor(Date.now() / 1000) + 12 * 3600, user };
    }
    const user = DEMO_ACCOUNTS.find((a) => token === `demo.${a.email}`);
    if (!user) throw { status: 401, detail: "Sign in to continue." };
    if (!rolesFor(method, parts).includes(user.role)) throw { status: 403, detail: `A ${user.role_label.toLowerCase()} can't do this.` };

    if (url.pathname === "/auth/me") return { user };
    if (parts[0] === "me" && parts[1] === "offers") {
      // Physicians only ever see offers a lead has approved and sent to them.
      const mine = offers.filter((o) => o.physician_id === user.physician_id && !["Proposed", "Approved", "Rejected"].includes(o.state));
      if (method === "GET") return { now: iso(), items: mine };
      const offer = mine.find((o) => o.offer_id === parts[2]);
      if (!offer) throw { status: 404, detail: "offer not found" };
      if (offer.state !== "Sent") throw { status: 409, detail: `This offer is ${offer.state.toLowerCase()}.` };
      if (parts[3] === "accept") {
        Object.assign(offer, { state: "Accepted", responded_at: iso() });
        for (const other of offers) if (other !== offer && other.gap_id === offer.gap_id && ["Proposed", "Sent"].includes(other.state)) other.state = "Withdrawn";
        log(user.name, "Accepted offer", "Suncrest 19:00 now 2 of 2");
      } else {
        Object.assign(offer, { state: "Declined", responded_at: iso() });
        log(user.name, "Declined offer", "Gap returns to the coordinator");
      }
      revision += 1;
      return offer;
    }

    if (method === "GET") {
      if (url.pathname === "/snapshot") {
        const accepted = offers.some((o) => o.state === "Accepted");
        return {
          revision, epoch: "demo", sequence: revision,
          clock: { mode: pausedAt !== null ? "fixed" : "demo", now: iso(), paused: pausedAt !== null },
          headline: { open_consults: 18 }, consults: [],
          coverage: fx.coverage(accepted), demand: fx.demand, workload: fx.workload,
          data_quality: fx.dataQuality, dataset: fx.dataset,
          pending_approvals: offers.filter((o) => o.state === "Proposed").length,
        };
      }
      if (url.pathname === "/offers") return { items: offers };
      if (url.pathname === "/audit") return { items: audit };
      if (url.pathname === "/interventions") return { items: [] };
      if (parts[0] === "gaps" && parts[2] === "candidates") return fx.candidates;
      if (parts[0] === "gaps" && parts[2] === "trap-check") return fx.trapCheck;
    }

    if (method === "POST") {
      if (parts[0] === "offers" && parts.length === 3) {
        const offer = offers.find((o) => o.offer_id === parts[1]);
        if (!offer) throw { status: 404, detail: "offer not found" };
        if (offer.state !== "Proposed") throw { status: 409, detail: `offer is ${offer.state}` };
        if (parts[2] === "approve") {
          Object.assign(offer, {
            state: "Sent", approved_by: user.name, approved_at: iso(), sent_at: iso(),
            expires_at: new Date(now() + 10 * 60_000).toISOString(), phone_url: "#demo-phone",
          });
          log(user.name, "Approved and sent offer", offer.physician_name);
        } else {
          Object.assign(offer, { state: "Rejected", reject_reason: json.reason });
          log(user.name, "Rejected offer", json.reason);
        }
        revision += 1;
        return offer;
      }
      if (url.pathname === "/offers") {
        const candidate = fx.candidates.candidates.find((c) => c.physician_id === json.physician_id);
        if (!candidate?.eligible) throw { status: 422, detail: `${candidate?.name ?? "This physician"} is not eligible: ${candidate?.primary_reason ?? "unknown"}` };
        if ((Date.parse(json.end) - Date.parse(json.start)) / 3_600_000 < 2) throw { status: 422, detail: "R6: an offer must be at least 2 hours" };
        const offer = { ...fx.offer(), offer_id: `OFFER-${offers.length + 1}`, start: json.start, end: json.end, proposed_by: user.name, proposed_at: iso() };
        offers.push(offer);
        log(user.name, "Proposed offer", offer.physician_name);
        return offer;
      }
      if (url.pathname === "/events" || url.pathname === "/events/csv") {
        const rows = url.pathname === "/events" ? [json].flat().length : (body ?? "").trim().split("\n").filter((l) => l && !l.startsWith("event_id")).length;
        revision += 1;
        return { accepted: rows, duplicates: 0, conflicts: 0, reordered: 0, late: 0, held_orphans: 0, quarantined: [], revision } satisfies IngestReport;
      }
      if (url.pathname === "/admin/clock") {
        if (json.advance_s) advancedMs += json.advance_s * 1000;
        if (json.paused === true && pausedAt === null) pausedAt = localNow();
        if (json.paused === false && pausedAt !== null) { advancedMs -= localNow() - pausedAt; pausedAt = null; }
        return { mode: "demo", now: iso() };
      }
      if (url.pathname === "/admin/reset") { reset(); return { revision }; }
      if (parts[0] === "interventions") return {};
    }
    throw { status: 404, detail: "Not Found" };
  }

  return { handle, now };
}
