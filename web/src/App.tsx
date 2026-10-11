// App shell: sign-in gate, Anish's header and pages per role, all fed from the server (or the demo stand-in).
import { useEffect, useState, type ReactNode } from "react";
import { api, DEMO, post } from "./api/client.ts";
import { useSnapshot, type Snapshot } from "./api/live.ts";
import { ApprovalsPage } from "./act/ApprovalsPage.tsx";
import { DataPage } from "./act/DataPage.tsx";
import { GapPanel } from "./act/GapPanel.tsx";
import { unavailableText, useApi, useServerNow } from "./act/hooks.ts";
import { isOpen } from "./act/offerSteps.ts";
import { OfferTracker } from "./act/OfferTracker.tsx";
import { clockTime, clockTimeSeconds, headerDate } from "./act/time.ts";
import type { AuditEntry, Dataset, Offer } from "./act/types.ts";
import { PAGES_BY_ROLE, SIGNED_OUT, clearSession, isUser, readSession, saveSession, type Session, type User } from "./auth/session.ts";
import { ConsultBoard, HeadlineNumbers, PhysicianBoard, detectFromSnapshot, type DetectSnapshot, type QueueItem } from "./detect/index.ts";
import { CoverageGrid } from "./forecast/CoverageGrid.tsx";
import { DemandPanel } from "./forecast/DemandPanel.tsx";
import type { Coverage, Demand, Workload } from "./forecast/types.ts";
import { WorkloadPanel } from "./forecast/WorkloadPanel.tsx";
import { LandingPage } from "./LandingPage.tsx";
import { OffersPage } from "./physician/OffersPage.tsx";
import SchedulePage from "./Schedule.tsx";
import { SignIn } from "./SignIn.tsx";
import "./tailwind.css";

const LABELS: Record<string, string> = {
  command: "Command", consults: "Consults", doctors: "Doctors", schedule: "Schedule", audit: "Audit", data: "Data",
  approvals: "Approvals", shift: "My shift", offers: "Offers", settings: "Settings",
};

function useHashPage(pages: readonly string[]): string {
  const pick = () => (pages.includes(location.hash.slice(1)) ? location.hash.slice(1) : pages[0]);
  const [page, setPage] = useState(pick);
  useEffect(() => {
    const onHash = () => setPage(pick());
    onHash();
    addEventListener("hashchange", onHash);
    return () => removeEventListener("hashchange", onHash);
  }, [pages]);
  return page;
}

export default function App() {
  const [session, setSession] = useState<Session | null>(readSession);
  const [checking, setChecking] = useState(() => readSession() !== null);
  const [restoreError, setRestoreError] = useState<string | null>(null);
  const [retry, setRetry] = useState(0);
  const [notice, setNotice] = useState<string>();
  const [signingIn, setSigningIn] = useState(() => location.hash === "#signin");
  useEffect(() => {
    const onHash = () => setSigningIn(location.hash === "#signin");
    addEventListener("hashchange", onHash);
    return () => removeEventListener("hashchange", onHash);
  }, []);
  useEffect(() => {
    const onSignOut = (event: Event) => {
      setSession(null);
      setChecking(false);
      setRestoreError(null);
      setNotice((event as CustomEvent<string>).detail);
    };
    addEventListener(SIGNED_OUT, onSignOut);
    return () => removeEventListener(SIGNED_OUT, onSignOut);
  }, []);

  useEffect(() => {
    if (!checking || !session) return;
    let cancelled = false;
    setRestoreError(null);
    api<{ user: User | null }>("/auth/me").then(({ user }) => {
      if (cancelled || readSession()?.token !== session.token) return;
      if (!isUser(user)) {
        clearSession(session.token, "Sign-in isn't available on this server. Contact your administrator.");
        return;
      }
      const verified = { ...session, user };
      saveSession(verified);
      setSession(verified);
      setChecking(false);
    }, (error: Error) => {
      if (!cancelled) setRestoreError(error.message);
    });
    return () => { cancelled = true; };
  }, [checking, session, retry]);

  useEffect(() => {
    if (!session) return;
    const expire = () => clearSession(session.token, "Your session has expired. Sign in again to continue.");
    const check = () => { if (session.expires_at * 1000 <= Date.now()) expire(); };
    const timer = setTimeout(expire, Math.max(0, session.expires_at * 1000 - Date.now()));
    addEventListener("focus", check);
    return () => { clearTimeout(timer); removeEventListener("focus", check); };
  }, [session]);

  // Signed-out visitors start on the landing page; its buttons lead to sign-in (#signin). A session-ended notice goes straight to sign-in.
  if (!session && !notice && !signingIn) {
    const toSignIn = () => { location.hash = "signin"; };
    return <div className="tw"><LandingPage onEnter={toSignIn} onGoToSignIn={toSignIn} /></div>;
  }
  if (!session) {
    return <SignIn notice={notice} onBackToLanding={() => { setNotice(undefined); location.hash = ""; }}
      onSignedIn={(next) => { setNotice(undefined); setChecking(false); setSession(next); location.hash = PAGES_BY_ROLE[next.user.role][0]; }} />;
  }
  if (checking) return <main className="signin-page"><div className="signin-main"><div className="signin">
    <h1>Welcome back</h1>
    <p role="status">{restoreError ?? "Checking your session…"}</p>
    {restoreError && <><button className="submit" onClick={() => setRetry(value => value + 1)}>Try again</button><button className="signout" onClick={() => clearSession()}>Use another account</button></>}
  </div></div></main>;
  return session.user.role === "physician" ? <PhysicianApp session={session} /> : <OperationsApp session={session} />;
}

// Anish's floating header: brand, live clock line, role tabs, account and sign-out.
function Header({ session, page, clock, counts = {} }: { session: Session; page: string; clock?: string; counts?: Record<string, number> }) {
  return <header className="tw app-header z-50 rounded-2xl border border-slate-200/90 bg-white/90 px-5 py-2.5 backdrop-blur-xl shadow-[0_4px_24px_rgba(0,0,0,0.06)]">
    <div className="header-brand flex items-center gap-3">
      <span className="flex items-center gap-2"><span className="relative block h-5 w-6"><i className="absolute left-0 top-0 h-3 w-3 -skew-x-12 rounded-sm bg-teal-600" /><i className="absolute left-2.5 top-1.5 h-3 w-3 -skew-x-12 rounded-sm bg-[#161E2E]" /></span><strong className="text-sm font-bold tracking-tight text-slate-900">overlap</strong></span>
      {clock && <span className="header-clock items-center gap-1.5 pl-2 font-mono text-[11px] text-slate-500"><span className="h-1.5 w-1.5 animate-pulse rounded-full bg-teal-600" />{clock}</span>}
      {DEMO && <span className="rounded-full bg-amber-100 px-2 py-0.5 text-[11px] font-semibold text-amber-800">Demo data</span>}
    </div>
    <nav aria-label="Workspace" className="header-nav flex items-center gap-1">
      {PAGES_BY_ROLE[session.user.role].map((key) => (
        <a key={key} href={`#${key}`} aria-current={page === key ? "page" : undefined}
          className={`rounded-full px-3 py-1 text-xs font-semibold transition ${page === key ? "bg-[#161E2E] text-white shadow-sm" : "text-slate-600 hover:bg-slate-100/80 hover:text-slate-900"}`}>
          {LABELS[key]}{counts[key] ? ` (${counts[key]})` : ""}
        </a>
      ))}
    </nav>
    <div className="header-account flex items-center gap-2">
      <span className="rounded-full border border-slate-200 bg-slate-50 px-2.5 py-0.5 text-[11px] font-medium text-slate-600" title={session.user.email}>{session.user.name} · {session.user.role_label}</span>
      <button onClick={() => clearSession()} className="rounded-full px-2.5 py-1 text-xs font-medium text-slate-500 transition hover:text-slate-900">Sign out ↗</button>
    </div>
  </header>;
}

const Main = ({ children }: { children: ReactNode }) => <main className="workspace-main">{children}</main>;
const Title = ({ eyebrow, title, note }: { eyebrow: string; title: string; note?: string }) =>
  <div className="workspace-title"><div><span className="eyebrow">{eyebrow}</span><h1>{title}</h1></div>{note && <span className="mono muted">{note}</span>}</div>;
const Unavailable = ({ what }: { what: string }) => <p className="unavailable">Not available yet: the server doesn't send {what}.</p>;

function OperationsApp({ session }: { session: Session }) {
  const role = session.user.role;
  const page = useHashPage(PAGES_BY_ROLE[role]);
  const live = useSnapshot();
  const now = useServerNow(live.snapshot, live.receivedAt);
  const offers = useApi<{ items: Offer[] }>("/offers", live.receivedAt);
  const s = live.snapshot;
  const detect = s ? detectFromSnapshot(s) : null;
  const workspace = role === "lead" ? "Clinical lead workspace" : "Coordinator workspace";
  const clock = s && now !== null ? `${headerDate(now)} · ${clockTime(new Date(now).toISOString())} ET · ${(s.dataset as Dataset | undefined)?.name ?? s.clock.mode}` : undefined;

  return <div className={`${page === "command" ? "command-shell " : ""}min-h-screen bg-[#FBF9F5] text-slate-900`}>
    <Header session={session} page={page} clock={clock} counts={role === "lead" ? { approvals: Number(s?.pending_approvals ?? 0) } : {}} />
    <Main>
      {live.error && !s && <p className="error">Can't reach the server: {live.error}</p>}
      {page === "command" && s && <CommandPage snapshot={s} detect={detect} now={now} offers={offers.data?.items ?? []} reloadKey={live.receivedAt} refresh={live.refresh} />}
      {page === "consults" && <div className="page"><Title eyebrow={workspace} title="Consults" note="Level from the server" />{detect ? <ConsultBoard consults={detect.consults} /> : <Unavailable what="consults with levels" />}</div>}
      {page === "doctors" && <div className="page"><Title eyebrow={workspace} title="Doctors" note="Self-report beside derived state" />{detect ? <PhysicianBoard physicians={detect.physicians} /> : <Unavailable what="physician state" />}</div>}
      {page === "schedule" && <SchedulePage />}
      {page === "audit" && <AuditPage workspace={workspace} reloadKey={live.receivedAt} />}
      {page === "approvals" && <ApprovalsPage offers={offers.data?.items ?? []} offersError={offers.error && !offers.data ? unavailableText(offers.error, "GET /offers") : null} now={now} reloadKey={live.receivedAt} onChanged={live.refresh} />}
      {page === "data" && <DataPage snapshot={s} now={now} onChanged={live.refresh} />}
    </Main>
  </div>;
}

function CommandPage({ snapshot, detect, now, offers, reloadKey, refresh }: {
  snapshot: Snapshot; detect: DetectSnapshot | null; now: number | null; offers: Offer[]; reloadKey: unknown; refresh: () => void;
}) {
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [gapId, setGapId] = useState<string | null>(null);
  const findCover = (id: string) => { setGapId(id); };
  useEffect(() => {
    if (gapId) document.getElementById("command-cover-action")?.scrollIntoView({ behavior: "smooth", block: "start" });
  }, [gapId]);
  const openOffers = offers.filter(isOpen);
  const item = detect?.queue.find((entry) => entry.id === selectedId) ?? detect?.queue[0] ?? null;
  return <div className="command-page">
    <div className="command-title"><div><span className="eyebrow">Coordinator workspace</span><h1>Command</h1><p className="command-subtitle">Network status, priorities, and coverage in one place.</p></div>{now !== null && <span className="command-clock">{snapshot.clock.mode} · {headerDate(now)} · {clockTime(new Date(now).toISOString())} ET</span>}</div>
    {detect && <HeadlineNumbers headline={detect.headline} />}
    <section className="command-section" aria-labelledby="attention-heading">
      <div className="command-section-head"><div><span className="section-index">01 / Respond</span><h2 id="attention-heading">Needs attention</h2></div><p>Select an item to review the next action.</p></div>
      <div className="command-top">
      <section className="queue-card">
        <div className="queue-card-head"><div><span className="eyebrow">Needs attention</span><h2>Ranked queue</h2></div><span className="mono queue-count">{detect?.queue.length ?? 0} items</span></div>
        {detect ? <div className="dense-queue">{detect.queue.map((entry) => (
          <button className={`dense-queue-row ${entry.id === item?.id ? "active" : ""}`} key={entry.id} onClick={() => setSelectedId(entry.id)}>
            <b className="queue-rank">{String(entry.rank).padStart(2, "0")}</b>
            <span className="queue-label"><strong>{entry.label}</strong><small>{entry.reason}</small></span>
            <span className={`level-chip ${entry.level.toLowerCase()}`}>{entry.level}</span>
          </button>
        ))}</div> : <Unavailable what="the attention queue" />}
      </section>
      {item && <Dossier item={item} total={detect!.queue.length} onFindCover={findCover} onDone={refresh} />}
      </div>
    </section>
    <section className="command-section" aria-labelledby="coverage-heading">
      <div className="command-section-head"><div><span className="section-index">02 / Anticipate</span><h2 id="coverage-heading">Network coverage</h2></div><p>Staffing against demand across every hospital.</p></div>
      <div className="command-coverage">
      <CoverageGrid coverage={snapshot.coverage as Coverage | undefined} onFindCover={setGapId} />
      {gapId && <div id="command-cover-action"><GapPanel gapId={gapId} reloadKey={reloadKey} canPropose onClose={() => setGapId(null)} onProposed={() => { setGapId(null); refresh(); }} /></div>}
      </div>
      <div className="forecast-panels">
        <DemandPanel demand={snapshot.demand as Demand | undefined} />
        <WorkloadPanel workload={snapshot.workload as Workload | undefined} />
      </div>
    </section>
    <section className="command-section" aria-labelledby="coordination-heading">
      <div className="command-section-head"><div><span className="section-index">03 / Coordinate</span><h2 id="coordination-heading">Offers & activity</h2></div><p>Track open offers and recent network actions.</p></div>
      <div className="command-rail">
        <div className="command-offers">{openOffers.length ? openOffers.map((o) => <OfferTracker key={o.offer_id} offer={o} now={now} />) : <section className="panel"><span className="eyebrow">Open offers</span><h2>No offers in progress</h2><p className="muted">New coverage offers will appear here.</p></section>}</div>
        <AutoLog reloadKey={reloadKey} />
      </div>
    </section>
  </div>;
}

// The selected queue item, in Anish's dossier layout. Buttons appear only for fixes the server says a person can take.
function Dossier({ item, total, onFindCover, onDone }: { item: QueueItem; total: number; onFindCover: (gapId: string) => void; onDone: () => void }) {
  const [message, setMessage] = useState<string | null>(null);
  useEffect(() => setMessage(null), [item.id]);
  const intervene = async (kind: "reassign" | "escalate") => {
    try {
      await post("/interventions", { kind, item_id: item.id, physician_id: kind === "reassign" ? item.physicianId : undefined });
      setMessage(kind === "escalate" ? "Sent to the clinical lead." : "Reassignment recorded.");
      onDone();
    } catch (e) {
      setMessage((e as Error).message);
    }
  };
  const isGap = item.kind === "now_gap" || item.kind === "gap";
  const canReassign = ["reassign", "assign", "handoff"].includes(item.fixKind) && item.physicianId;
  return <section className="dossier-card">
    <div className="dossier-head"><div><span className="eyebrow">#{item.rank} of {total} · {item.level}</span><h2>{item.reason}</h2></div>{item.level === "Critical" && <span className="critical-mark">!</span>}</div>
    <div className="dossier-grid">
      <div><b>Where</b><p>{item.where || "–"}</p></div>
      <div><b>Why it matters</b><p>{item.why || "–"}</p></div>
      <div><b>Suggested fix</b><p>{item.fix}</p></div>
      <div><b>Who approves</b><p>{item.approver}</p></div>
      {(item.fixReason || item.alternatives.length > 0) && <div className="dossier-wide"><b>Why this fix</b><p>{item.fixReason}</p>{item.alternatives.length > 0 && <ul>{item.alternatives.map((a) => <li key={a}>{a}</li>)}</ul>}</div>}
    </div>
    <div className="dossier-actions">
      {canReassign && <button className="btn dossier-primary" onClick={() => intervene("reassign")}>{item.fixKind === "handoff" ? "Record handoff" : "Reassign"}</button>}
      {isGap && <button className="btn dossier-primary" onClick={() => onFindCover(item.id)}>Find cover</button>}
      {item.approver !== "Automatic" && <button className={`btn ${item.fixKind === "escalate" ? "dossier-primary" : "dossier-secondary"}`} onClick={() => intervene("escalate")}>Escalate to clinical lead</button>}
    </div>
    {message && <p className="muted" role="status">{message}</p>}
  </section>;
}

function useAudit(reloadKey: unknown) {
  return useApi<{ items: AuditEntry[] }>("/audit", reloadKey);
}

function AutoLog({ reloadKey }: { reloadKey: unknown }) {
  const { data, error } = useAudit(reloadKey);
  const rows = (data?.items ?? []).slice(-5).reverse();
  return <section className="auto-log">
    <div className="rail-heading"><div><span className="eyebrow">Activity</span><h2>Latest actions</h2></div><span className="badge green">{data?.items.length ?? 0} events</span></div>
    {error && !data ? <p className="unavailable">{unavailableText(error, "GET /audit")}</p>
      : rows.map((row, i) => <div className="auto-log-row" key={i}><span className="mono">{clockTimeSeconds(row.at)}</span><div><strong>{row.action}</strong><small>{row.actor}{row.detail ? ` · ${row.detail}` : ""}</small></div></div>)}
  </section>;
}

function AuditPage({ workspace, reloadKey }: { workspace: string; reloadKey: unknown }) {
  const { data, error } = useAudit(reloadKey);
  return <div className="page"><Title eyebrow={workspace} title="Audit" note="Append-only record" />
    <section className="panel audit-list">
      {error && !data ? <p className="unavailable">{unavailableText(error, "GET /audit")}</p>
        : !data?.items.length ? <p className="unavailable">Nothing recorded yet.</p>
          : data.items.slice().reverse().map((row, i) => <div key={i}><span className="mono muted">{clockTimeSeconds(row.at)}</span><b>{row.actor}</b><strong>{row.action}</strong><span>{row.detail}</span></div>)}
    </section>
  </div>;
}

type Shift = { name: string; shift_end: string | null; minutes_to_shift_end: number | null; hospitals: string[]; consults: { consult_id: string; hospital_name: string; consult_type: string; stage: string; minutes_in_stage: number }[] };

function PhysicianApp({ session }: { session: Session }) {
  const page = useHashPage(PAGES_BY_ROLE.physician);
  return <div className="min-h-screen bg-[#FBF9F5] text-slate-900">
    <Header session={session} page={page} />
    <Main>
      {page === "shift" && <MyShift />}
      {page === "offers" && <OffersPage />}
      {page === "settings" && <div className="page"><Title eyebrow="Physician workspace" title="Settings" note={session.user.name} /><section className="panel"><h2>Notifications</h2><p className="muted">Offers arrive in this app and on your phone. They show the hospital and hours only, never patient details.</p></section></div>}
    </Main>
  </div>;
}

function MyShift() {
  const { data, error } = useApi<Shift>("/me/shift", undefined, 2000);
  if (!data) return <div className="page"><Title eyebrow="Physician workspace" title="My shift" />{error ? <p className="unavailable">{unavailableText(error, "GET /me/shift")}</p> : <p className="muted">Loading…</p>}</div>;
  const left = data.minutes_to_shift_end;
  return <div className="page physician-page"><Title eyebrow="Physician workspace" title="My shift" note={data.name} />
    {error && <p className="unavailable">Update failed: {error.message}. Retrying; showing the last received shift.</p>}
    <div className="physician-top">
      <section className="panel shift-clock"><span className="eyebrow">Shift remaining</span><strong>{left === null ? "–" : `${Math.floor(left / 60)} h ${left % 60} min`}</strong><p>{data.shift_end ? `until ${clockTime(data.shift_end)} ET` : "No current shift"}</p></section>
      <section className="panel"><span className="eyebrow">Hospitals covered</span><h2>{data.hospitals.join(" · ") || "–"}</h2><p className="muted">{data.consults.length} active consults</p></section>
    </div>
    <section className="panel"><div className="panel-head"><h2>Active consults</h2><span className="badge teal">{left === null ? "Off shift" : "On shift"}</span></div>
      {data.consults.length ? data.consults.map((c) => <div className="consult-line" key={c.consult_id}><b className="mono">{c.consult_id}</b><span>{c.hospital_name} · {c.consult_type}</span><span className="badge neutral">{c.stage} · {c.minutes_in_stage} min</span></div>) : <p className="muted">No open consults.</p>}
    </section>
  </div>;
}
