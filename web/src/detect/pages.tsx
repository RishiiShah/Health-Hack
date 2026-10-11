// Consults and Doctors pages: the detection views, one page each.
import type { Snapshot } from "../api/live.ts";
import { WorkloadPanel } from "../forecast/WorkloadPanel.tsx";
import type { Workload } from "../forecast/types.ts";
import { Empty, PageHead } from "../ui/Layout.tsx";
import { ConsultBoard } from "./ConsultBoard.tsx";
import { ConsultQueues, PhysicianActivity, SignalVerification } from "./LiveWorkload.tsx";
import { PhysicianBoard } from "./PhysicianBoard.tsx";
import type { DetectSnapshot } from "./types.ts";
import "./detect.css";

// Bring a consult's row in the lifecycle board into view.
function showConsult(consultId: string) {
  const row = document.getElementById(`consult-${consultId}`);
  row?.scrollIntoView({ behavior: "smooth", block: "center" });
  row?.focus({ preventScroll: true });
}

export function ConsultsPage({ detect }: { detect: DetectSnapshot | null }) {
  return <>
    <PageHead kicker="Detection" title="Consults" note="Every open consult with its stage, timers and priority. Levels come from the server." />
    {detect ? <><ConsultQueues detect={detect} onReview={showConsult} /><ConsultBoard consults={detect.consults} /></> : <Empty>Not available yet: the server doesn't send consults with levels.</Empty>}
  </>;
}

export function DoctorsPage({ detect, snapshot }: { detect: DetectSnapshot | null; snapshot: Snapshot }) {
  return <>
    <PageHead kicker="Detection" title="Doctors" note="What each physician says beside what the system signals show, with workload and shift-end risk." />
    {detect ? <>
      <PhysicianActivity detect={detect} />
      <div className="forecast-panels"><WorkloadPanel workload={snapshot.workload as Workload | undefined} /><SignalVerification detect={detect} /></div>
      <PhysicianBoard physicians={detect.physicians} />
    </> : <Empty>Not available yet: the server doesn't send physician state.</Empty>}
  </>;
}
