// The frame around every signed-in page: sidebar navigation, a top bar with the live clock, and the page itself.
import { Component, useLayoutEffect, type ReactNode } from "react";
import { DEMO } from "../api/client.ts";
import { PAGES_BY_ROLE, clearSession, type Session } from "../auth/session.ts";
import { Pulse } from "../ui/Pulse.tsx";
import { Brand, ThemeToggle } from "../ui/theme.tsx";
import { stagger } from "../ui/motion.ts";
import "./shell.css";

export const PAGES: Record<string, { label: string; about: string }> = {
  command: { label: "Command", about: "Triage, coverage outlook and dispatch" },
  consults: { label: "Consults", about: "Every open consult, its stage and timers" },
  doctors: { label: "Doctors", about: "Who is free, who is busy, whose signals disagree" },
  schedule: { label: "Schedule", about: "Today's roster and pending offers" },
  audit: { label: "Audit", about: "Append-only record of every decision" },
  data: { label: "Data", about: "Event stream, checks and reference kits" },
  approvals: { label: "Approvals", about: "Offers and escalations waiting for you" },
  shift: { label: "My shift", about: "Your hospitals, consults and time left" },
  offers: { label: "Offers", about: "Coverage offers sent to you" },
  settings: { label: "Settings", about: "Notifications and privacy" },
};

export type Clock = { text: string; live: boolean; dataset?: string };

export function Shell({ session, page, clock, counts = {}, children }: { session: Session; page: string; clock?: Clock; counts?: Record<string, number>; children: ReactNode }) {
  const info = PAGES[page];
  useLayoutEffect(() => {
    window.scrollTo({ top: 0, left: 0, behavior: "instant" });
  }, [page]);
  return <div className="app">
    <aside className="sidebar">
      <Brand />
      <nav className="side-nav" aria-label="Workspace">
        <span className="side-nav-label">{session.user.role_label}</span>
        {PAGES_BY_ROLE[session.user.role].map((key, i) => (
          <a key={key} href={`#${key}`} aria-current={page === key ? "page" : undefined} style={stagger(i)}>
            <span>{PAGES[key].label}</span>{counts[key] ? <span className="nav-count">{counts[key]}</span> : null}
          </a>
        ))}
      </nav>
      <div className="side-foot">
        <div className="side-user"><strong title={session.user.email}>{session.user.name}</strong><span>{session.user.email}</span></div>
        <button className="btn" onClick={() => clearSession()}>Sign out</button>
      </div>
    </aside>
    <div className="workspace">
      <header className="topbar">
        <div className="topbar-title" key={page}><strong>{info.label}</strong><span>{info.about}</span></div>
        <div className="topbar-meta">
          {DEMO && <span className="pill demo">Demo data</span>}
          {clock?.dataset && <span className="pill dataset" title="Active reference kit">{clock.dataset}</span>}
          {clock && <span className={`pill clock ${clock.live ? "live" : "paused"}`}>
            <Pulse live={clock.live} label={clock.live ? "Clock running" : "Clock paused"} />{clock.text}
          </span>}
          <ThemeToggle />
        </div>
      </header>
      <main className="workspace-main page-enter" key={page}><PageBoundary>{children}</PageBoundary></main>
    </div>
  </div>;
}

// A crash inside one page shows an error there instead of unmounting the whole app; changing page starts afresh.
class PageBoundary extends Component<{ children: ReactNode }, { error: Error | null }> {
  state = { error: null as Error | null };
  static getDerivedStateFromError(error: Error) { return { error }; }
  render() {
    return this.state.error
      ? <p className="error" role="alert">This page couldn't be displayed ({this.state.error.message}). The other pages still work; reload to try again.</p>
      : this.props.children;
  }
}
