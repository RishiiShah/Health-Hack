// Minimal scaffold for Anish: sign-in gate, header, role-filtered hash tabs and page layout. Detect panels slot into the Command page.
import { useEffect, useState, type ReactNode } from "react";
import { api, DEMO } from "./api/client.ts";
import { useSnapshot } from "./api/live.ts";
import { ApprovalBanner } from "./act/ApprovalBanner.tsx";
import { ApprovalsPage } from "./act/ApprovalsPage.tsx";
import { DataPage } from "./act/DataPage.tsx";
import { GapPanel } from "./act/GapPanel.tsx";
import { unavailableText, useApi, useServerNow } from "./act/hooks.ts";
import { isOpen } from "./act/offerSteps.ts";
import { OfferTracker } from "./act/OfferTracker.tsx";
import { clockTime, headerDate } from "./act/time.ts";
import type { Dataset, Offer } from "./act/types.ts";
import { Login } from "./auth/Login.tsx";
import { LandingPage } from "./LandingPage.tsx";
import "./landing.css";
import { PAGES_BY_ROLE, SIGNED_OUT, clearSession, isUser, readSession, saveSession, type Session, type User } from "./auth/session.ts";
import { CoverageGrid } from "./forecast/CoverageGrid.tsx";
import { DemandPanel } from "./forecast/DemandPanel.tsx";
import type { Coverage, Demand, Workload } from "./forecast/types.ts";
import { WorkloadPanel } from "./forecast/WorkloadPanel.tsx";
import { OffersPage } from "./physician/OffersPage.tsx";

const LABELS: Record<string, string> = { command: "Command", schedule: "Schedule", approvals: "Approvals", data: "Data", offers: "Offers" };

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
    return <div className="landing"><LandingPage onEnter={toSignIn} onGoToSignIn={toSignIn} /></div>;
  }
  if (!session) return <Login notice={notice} onSignedIn={(next) => { setNotice(undefined); setChecking(false); setSession(next); }} />;
  if (checking) return <main className="signin-page"><div className="signin-main"><div className="signin">
    <h1>Welcome back</h1>
    <p role="status">{restoreError ?? "Checking your session…"}</p>
    {restoreError && <><button className="submit" onClick={() => setRetry(value => value + 1)}>Try again</button><button className="signout" onClick={() => clearSession()}>Use another account</button></>}
  </div></div></main>;
  return session.user.role === "physician" ? <PhysicianApp session={session} /> : <OperationsApp session={session} />;
}

function TopBar({ session, page, meta, counts = {} }: { session: Session; page: string; meta?: ReactNode; counts?: Record<string, number> }) {
  return (
    <header className="topbar">
      <span className="brand">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M2 12h4l3-7 4 14 3-7h6" /></svg>
        Sevaro Command
      </span>
      {meta}
      {DEMO && <span className="badge amber">Demo data</span>}
      <nav>
        {PAGES_BY_ROLE[session.user.role].map((p) => (
          <a key={p} href={`#${p}`} aria-current={page === p ? "page" : undefined}>
            {LABELS[p]}
            {counts[p] ? <span className="count">{counts[p]}</span> : null}
          </a>
        ))}
        <span className="role" title={session.user.email}>{session.user.name} · {session.user.role_label}</span>
        <button className="signout" onClick={() => clearSession()}>Sign out</button>
      </nav>
    </header>
  );
}

function PhysicianApp({ session }: { session: Session }) {
  const page = useHashPage(PAGES_BY_ROLE.physician);
  return (
    <>
      <TopBar session={session} page={page} />
      <OffersPage />
    </>
  );
}

function OperationsApp({ session }: { session: Session }) {
  const role = session.user.role;
  const page = useHashPage(PAGES_BY_ROLE[role]);
  const [gapId, setGapId] = useState<string | null>(null);
  const live = useSnapshot();
  const now = useServerNow(live.snapshot, live.receivedAt);
  const offers = useApi<{ items: Offer[] }>("/offers", live.receivedAt);
  const offerList = offers.data?.items ?? [];
  const pending = offerList.filter((o) => o.state === "Proposed");
  const s = live.snapshot;

  const meta = s && now !== null && (
    <span className="meta">{headerDate(now)} · {clockTime(new Date(now).toISOString())} ET · {(s.dataset as Dataset | undefined)?.name ?? s.clock.mode}</span>
  );

  return (
    <>
      <TopBar session={session} page={page} meta={meta} counts={role === "lead" ? { approvals: pending.length } : {}} />

      {live.error && !s && <div className="page"><p className="error">Can't reach the server: {live.error}</p></div>}

      {page === "command" && (
        <div className="page">
          {role === "lead" && <ApprovalBanner pending={pending} onReview={() => { location.hash = "approvals"; }} />}
          <CoverageGrid coverage={s?.coverage as Coverage | undefined} onFindCover={setGapId} />
          {gapId && (
            <GapPanel
              gapId={gapId}
              reloadKey={live.receivedAt}
              canPropose={role === "coordinator"}
              onClose={() => setGapId(null)}
              onProposed={() => { setGapId(null); live.refresh(); }}
            />
          )}
          <div style={{ marginTop: 24 }}>
            {offers.error && !offers.data
              ? <p className="unavailable">{unavailableText(offers.error, "GET /offers")}</p>
              : offerList.filter(isOpen).map((o) => <OfferTracker key={o.offer_id} offer={o} now={now} />)}
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(420px, 1fr))", gap: 24, marginTop: 24 }}>
            <DemandPanel demand={s?.demand as Demand | undefined} />
            <WorkloadPanel workload={s?.workload as Workload | undefined} />
          </div>
        </div>
      )}
      {page === "schedule" && <div className="page"><h1>Schedule</h1><p className="unavailable">Not built yet.</p></div>}
      {page === "approvals" && (
        <ApprovalsPage
          offers={offerList}
          offersError={offers.error && !offers.data ? unavailableText(offers.error, "GET /offers") : null}
          now={now}
          reloadKey={live.receivedAt}
          onChanged={live.refresh}
        />
      )}
      {page === "data" && <DataPage snapshot={s} now={now} onChanged={live.refresh} />}
    </>
  );
}
