// App entry: landing, sign-in and session check, then each role's pages inside the shell. Data comes from the server (or the demo stand-in).
import { useEffect, useState } from "react";
import { api } from "./api/client.ts";
import { useSnapshot } from "./api/live.ts";
import { ApprovalsPage } from "./act/ApprovalsPage.tsx";
import { AuditPage } from "./act/AuditPage.tsx";
import { DataPage } from "./act/DataPage.tsx";
import { unavailableText, useApi, useServerNow } from "./act/hooks.ts";
import { clockTime, headerDate } from "./act/time.ts";
import type { Dataset, Offer } from "./act/types.ts";
import { PAGES_BY_ROLE, SIGNED_OUT, clearSession, isUser, readSession, saveSession, type Session, type User } from "./auth/session.ts";
import { Splash } from "./auth/Splash.tsx";
import { CommandPage } from "./command/CommandPage.tsx";
import { detectFromSnapshot } from "./detect/index.ts";
import { ConsultsPage, DoctorsPage } from "./detect/pages.tsx";
import { LandingPage } from "./LandingPage.tsx";
import { IncomingCall } from "./physician/IncomingCall.tsx";
import { MyShift } from "./physician/MyShift.tsx";
import { OffersPage } from "./physician/OffersPage.tsx";
import SchedulePage from "./Schedule.tsx";
import { Shell } from "./shell/Shell.tsx";
import { SignIn } from "./SignIn.tsx";
import { PageHead, Panel } from "./ui/Layout.tsx";
import { useSmoothScroll } from "./ui/smoothScroll.ts";

function useHashPage(pages: readonly string[]): string {
  const pick = () => (pages.includes(location.hash.slice(1)) ? location.hash.slice(1) : pages[0]);
  const [page, setPage] = useState(pick);
  useEffect(() => {
    // Hashes that aren't pages (#coverage, #dispatch) are in-page anchors: keep the current page.
    const onHash = () => { if (pages.includes(location.hash.slice(1))) setPage(pick()); };
    addEventListener("hashchange", onHash);
    return () => removeEventListener("hashchange", onHash);
  }, [pages]);
  return page;
}

export default function App() {
  useSmoothScroll();
  const [session, setSession] = useState<Session | null>(readSession);
  const [checking, setChecking] = useState(() => readSession() !== null);
  const [restoreError, setRestoreError] = useState<string | null>(null);
  const [retry, setRetry] = useState(0);
  const [notice, setNotice] = useState<string>();
  const [targetRole, setTargetRole] = useState<"coordinator" | "lead" | "physician">("coordinator");
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
    return <LandingPage onGoToSignIn={(role = "coordinator") => { setTargetRole(role); location.hash = "signin"; }} />;
  }
  if (!session) {
    return <SignIn key={targetRole} initialRole={targetRole} notice={notice} onBackToLanding={() => { setNotice(undefined); location.hash = ""; }}
      onSignedIn={(next) => { setNotice(undefined); setChecking(false); setSession(next); location.hash = PAGES_BY_ROLE[next.user.role][0]; }} />;
  }
  if (checking) return <Splash error={restoreError} onRetry={() => setRetry((value) => value + 1)} />;
  return session.user.role === "physician" ? <PhysicianApp session={session} /> : <OperationsApp session={session} />;
}

function OperationsApp({ session }: { session: Session }) {
  const role = session.user.role;
  const page = useHashPage(PAGES_BY_ROLE[role]);
  const live = useSnapshot();
  const now = useServerNow(live.snapshot, live.receivedAt);
  const offers = useApi<{ items: Offer[] }>("/offers", live.receivedAt);
  const s = live.snapshot;
  const detect = s ? detectFromSnapshot(s) : null;
  const paused = Boolean((s?.clock as { paused?: boolean } | undefined)?.paused) || s?.clock.mode === "fixed";
  const clock = s && now !== null ? { text: `${headerDate(now)} · ${clockTime(new Date(now).toISOString())} ET`, live: !paused, dataset: (s.dataset as Dataset | undefined)?.name } : undefined;
  const counts: Record<string, number> = role === "lead" ? { approvals: Number(s?.pending_approvals ?? 0) } : { command: detect?.queue.filter((q) => q.level === "Critical").length ?? 0 };

  return <Shell session={session} page={page} clock={clock} counts={counts}>
    {live.error && <p className="notice" role="status">{s ? "Updates interrupted. Showing the last snapshot. " : "Can't reach the server. "}{live.error}</p>}
    {!s && !live.error && <p className="muted" role="status">Loading the live snapshot…</p>}
    {page === "command" && s && <CommandPage snapshot={s} detect={detect} now={now} offers={offers.data?.items ?? []} reloadKey={live.receivedAt} refresh={live.refresh} />}
    {page === "consults" && s && <ConsultsPage detect={detect} />}
    {page === "doctors" && s && <DoctorsPage detect={detect} snapshot={s} />}
    {page === "schedule" && <SchedulePage reloadKey={live.receivedAt} />}
    {page === "audit" && <AuditPage reloadKey={live.receivedAt} />}
    {page === "approvals" && <ApprovalsPage offers={offers.data?.items ?? []} offersError={offers.error && !offers.data ? unavailableText(offers.error, "GET /offers") : null} now={now} reloadKey={live.receivedAt} onChanged={live.refresh} />}
    {page === "data" && <DataPage snapshot={s} now={now} onChanged={live.refresh} />}
  </Shell>;
}

function PhysicianApp({ session }: { session: Session }) {
  const page = useHashPage(PAGES_BY_ROLE.physician);
  return <Shell session={session} page={page}>
    <IncomingCall />
    {page === "shift" && <MyShift />}
    {page === "offers" && <OffersPage />}
    {page === "settings" && <><PageHead kicker="Physician workspace" title="Settings" note={session.user.name} />
      <Panel title="Notifications"><p className="muted">Offers arrive in this app and on your phone. They show the hospital and hours only, never patient details.</p></Panel></>}
  </Shell>;
}
