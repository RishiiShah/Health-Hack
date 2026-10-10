// Minimal scaffold for Anish: header, hash tabs and page layout. Detect panels slot into the Command page.
import { useEffect, useState } from "react";
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
import { CoverageGrid } from "./forecast/CoverageGrid.tsx";
import { DemandPanel } from "./forecast/DemandPanel.tsx";
import type { Coverage, Demand, Workload } from "./forecast/types.ts";
import { WorkloadPanel } from "./forecast/WorkloadPanel.tsx";

const PAGES = ["command", "schedule", "approvals", "data"] as const;
type Page = (typeof PAGES)[number];
const currentPage = (): Page => (PAGES as readonly string[]).includes(location.hash.slice(1)) ? (location.hash.slice(1) as Page) : "command";

export default function App() {
  const [page, setPage] = useState<Page>(currentPage);
  const [gapId, setGapId] = useState<string | null>(null);
  const live = useSnapshot();
  const now = useServerNow(live.snapshot, live.receivedAt);
  const offers = useApi<{ items: Offer[] }>("/offers", live.receivedAt);
  const offerList = offers.data?.items ?? [];
  const pending = offerList.filter((o) => o.state === "Proposed");
  const s = live.snapshot;

  useEffect(() => {
    const onHash = () => setPage(currentPage());
    addEventListener("hashchange", onHash);
    return () => removeEventListener("hashchange", onHash);
  }, []);

  const go = (to: Page) => { location.hash = to; };

  return (
    <>
      <header className="topbar">
        <span className="brand">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M2 12h4l3-7 4 14 3-7h6" /></svg>
          Sevaro Command
        </span>
        {s && now !== null && (
          <span className="meta">{headerDate(now)} · {clockTime(new Date(now).toISOString())} ET · {(s.dataset as Dataset | undefined)?.name ?? s.clock.mode}</span>
        )}
        <nav>
          {PAGES.map((p) => (
            <a key={p} href={`#${p}`} aria-current={page === p ? "page" : undefined}>
              {p[0].toUpperCase() + p.slice(1)}
              {p === "approvals" && pending.length > 0 && <span className="count">{pending.length}</span>}
            </a>
          ))}
        </nav>
      </header>

      {live.error && !s && <div className="page"><p className="error">Can't reach the server: {live.error}</p></div>}

      {page === "command" && (
        <div className="page">
          <ApprovalBanner pending={pending} onReview={() => go("approvals")} />
          <CoverageGrid coverage={s?.coverage as Coverage | undefined} onFindCover={setGapId} />
          {gapId && <GapPanel gapId={gapId} reloadKey={live.receivedAt} onClose={() => setGapId(null)} onProposed={() => { setGapId(null); live.refresh(); }} />}
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
