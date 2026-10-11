// Coordinator's command page: headline numbers, then triage, coverage outlook and dispatch, in that order.
import { useEffect, useState } from "react";
import type { Snapshot } from "../api/live.ts";
import { GapPanel } from "../act/GapPanel.tsx";
import { isOpen, stateBadge } from "../act/offerSteps.ts";
import { OfferTracker } from "../act/OfferTracker.tsx";
import { clockTime } from "../act/time.ts";
import type { Offer } from "../act/types.ts";
import { HeadlineNumbers, type DetectSnapshot } from "../detect/index.ts";
import { CoverageGrid } from "../forecast/CoverageGrid.tsx";
import { DemandPanel } from "../forecast/DemandPanel.tsx";
import type { Coverage, Demand } from "../forecast/types.ts";
import { Empty, Fold, PageHead, Section } from "../ui/Layout.tsx";
import { stagger } from "../ui/motion.ts";
import { AttentionQueue } from "./AttentionQueue.tsx";
import { Dossier } from "./Dossier.tsx";
import "./command.css";

export function CommandPage({ snapshot, detect, now, offers, reloadKey, refresh }: {
  snapshot: Snapshot; detect: DetectSnapshot | null; now: number | null; offers: Offer[]; reloadKey: unknown; refresh: () => void;
}) {
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [gapId, setGapId] = useState<string | null>(null);
  const [filter, setFilter] = useState("All");
  useEffect(() => {
    if (gapId) document.getElementById("find-cover")?.scrollIntoView({ behavior: "smooth", block: "start" });
  }, [gapId]);
  const queue = detect?.queue ?? [];
  const shown = queue.filter((q) => filter === "All" || q.level === filter);
  const item = shown.find((entry) => entry.id === selectedId) ?? shown[0] ?? null;
  const critical = queue.filter((q) => q.level === "Critical").length;
  const openOffers = offers.filter(isOpen);
  const closedOffers = offers.filter((o) => !isOpen(o));

  return <>
    <PageHead kicker="Sevaro tele-stroke network" title="Command center"
      note={queue.length ? `${queue.length} items need attention${critical ? `, ${critical} critical` : ""}. Time is brain: work top to bottom.` : "The queue is clear. Coverage and offers are below."} />
    {detect && <HeadlineNumbers headline={detect.headline} />}

    <Section id="triage" index={1} kicker="Triage" title="What needs action now" note="Ranked by the server. Pick an item to see the recommended fix.">
      {detect ? <div className="command-grid">
        <AttentionQueue queue={queue} filter={filter} onFilter={setFilter} selectedId={item?.id ?? null} onSelect={setSelectedId} />
        {item ? <Dossier key={item.id} item={item} total={queue.length} onFindCover={setGapId} onDone={refresh} /> : <Empty>Nothing needs action right now.</Empty>}
      </div> : <Empty>Not available yet: the server doesn't send the attention queue.</Empty>}
    </Section>

    <Section id="coverage" index={2} kicker="Coverage outlook" title="Where staffing runs short" note="Staffed against each hospital's minimum. Select a cell to inspect it.">
      <CoverageGrid coverage={snapshot.coverage as Coverage | undefined} onFindCover={setGapId} />
      {gapId && <div id="find-cover"><GapPanel gapId={gapId} reloadKey={reloadKey} now={now} canPropose onClose={() => setGapId(null)} onProposed={() => { setGapId(null); refresh(); }} /></div>}
      <Fold summary="Demand against the hourly baseline"><DemandPanel demand={snapshot.demand as Demand | undefined} /></Fold>
    </Section>

    <Section id="dispatch" index={3} kicker="Dispatch" title="Coverage offers" note="Every off-shift offer is approved by a clinical lead before the physician is called."
      aside={<><span className="badge amber">{offers.filter((o) => o.state === "Proposed").length} awaiting lead</span><span className="badge teal">{offers.filter((o) => o.state === "Sent").length} awaiting physician</span></>}>
      {openOffers.length
        ? <div className="tracker-list">{openOffers.map((o, i) => <div key={o.offer_id} className="rise" style={stagger(i)}><OfferTracker offer={o} now={now} /></div>)}</div>
        : <Empty>No offers in progress. Use Find cover on a coverage gap to propose one.</Empty>}
      {closedOffers.length > 0 && <Fold summary={`Completed offers · ${offers.filter((o) => o.state === "Accepted").length} accepted of ${closedOffers.length}`}>
        <div className="outcome-list">{closedOffers.map((offer) => <div className="outcome-row" key={offer.offer_id}>
          <div><strong>{offer.physician_name}</strong><p>{offer.hospital_names.join(", ")} · {clockTime(offer.start)}–{clockTime(offer.end)} ET</p>{offer.reject_reason && <small>{offer.reject_reason}</small>}</div>
          <span className={`badge ${stateBadge(offer.state).tone}`}>{stateBadge(offer.state).text}</span>
        </div>)}</div>
        <p className="hint">Full history in <a className="text-link" href="#audit">Audit</a>.</p>
      </Fold>}
    </Section>
  </>;
}
