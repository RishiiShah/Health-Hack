import { DEMO } from "../api/client.ts";
import type { Snapshot } from "../api/live.ts";
import { EventStream } from "./EventStream.tsx";
import { PageHead } from "../ui/Layout.tsx";
import type { Dataset } from "./types.ts";
import { useApi } from "./hooks.ts";
import "./act.css";

type StoredKit = { fingerprint: string; name: string; service_date: string | null; hospitals: number; physicians: number; active: boolean };

// Admin: add events, the checks on the stream, and the reference data the server holds.
export function DataPage({ snapshot, now, onChanged }: { snapshot: Snapshot | null; now: number | null; onChanged: () => void }) {
  const dataset = snapshot?.dataset as Dataset | undefined;

  return (
    <>
      <PageHead kicker="Operations data" title="Data" note="Add events to the stream and review the reference kit. Decisions are recalculated from the stream's full history using the active kit." />
      {snapshot && <EventStream snapshot={snapshot} now={now} onChanged={onChanged} />}
      <div className="data-grid">
      <section className="panel">
        <div className="panel-head"><h2>Active reference kit</h2></div>
        {dataset ? (
          <div className="dataset"><b>{dataset.name}</b>{dataset.description} · {dataset.reference_files} reference files</div>
        ) : (
          <p className="unavailable">Not available yet: the server doesn't describe the loaded dataset.</p>
        )}
        {!DEMO && <BaselineInventory revision={snapshot?.revision} />}
      </section>
      {!DEMO && <StoredKits revision={snapshot?.revision} />}
      </div>
    </>
  );
}

function StoredKits({ revision }: { revision?: unknown }) {
  const { data, error } = useApi<{ kits?: StoredKit[] }>("/admin/references", revision);
  return <section className="panel upload-history" aria-labelledby="kits-heading">
    <div className="panel-head"><h2 id="kits-heading">Stored reference kits</h2></div>
    <p className="hint">An events CSV whose hospitals and physicians all belong to one of these kits switches to it with a fresh event stream. A stored kit never changes.</p>
    {error && <p className="error" role="alert">Could not load reference kits: {error.message}</p>}
    {!data && !error && <p role="status">Loading reference kits…</p>}
    {data?.kits && <ul className="checks">{data.kits.map(kit => <li key={kit.fingerprint}>
      <span><b>{kit.name}</b> · {kit.hospitals} hospitals · {kit.physicians} physicians{kit.service_date ? ` · ${kit.service_date}` : ""}</span>
      <span className={`badge ${kit.active ? "green" : "neutral"}`}>{kit.active ? "Active" : "Stored"}</span>
    </li>)}</ul>}
  </section>;
}


type OperationalData = {
  baseline_source_rows: number; baseline_lookup_entries: number; weeks_sampled: number[];
  coverage_blocks: number; off_shift_roster_entries: number;
  hospitals: { hospital_id: string; hospital_name: string; baseline_timezone: string; hours_by_weekday: number[] }[];
};

function BaselineInventory({ revision }: { revision?: unknown }) {
  const { data, error } = useApi<{ operational_data: OperationalData | null }>("/admin/references", revision);
  const baseline = data?.operational_data;
  const days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
  if (error) return <p className="error" role="alert">Could not load baseline coverage: {error.message}</p>;
  if (!data) return <p role="status">Loading baseline coverage…</p>;
  if (!baseline) return <p className="unavailable">No hourly baseline loaded.</p>;
  const missingDays = days.filter((_, i) => baseline.hospitals.length > 0 && baseline.hospitals.every(h => h.hours_by_weekday[i] === 0));
  return <div className="baseline-inventory">
    <h3>Hourly baseline coverage</h3>
    <p>{baseline.baseline_source_rows} source rows · {baseline.baseline_lookup_entries} day/hour lookups{baseline.weeks_sampled.length > 0 && ` · ${baseline.weeks_sampled.join(", ")} weeks sampled`}</p>
    <p>{baseline.coverage_blocks} staffing requirement blocks · {baseline.off_shift_roster_entries} off-shift roster entries. Missing baseline hours stay unknown.</p>
    {missingDays.length > 0 && <p>No baseline supplied for {missingDays.join(", ")}.</p>}
    <details><summary>See baseline hours by hospital</summary>
      <ul>{baseline.hospitals.map(h => <li key={h.hospital_id}><b>{h.hospital_name}</b><p>{days.map((day, i) => `${day}: ${h.hours_by_weekday[i]}/24`).join(" · ")} · {h.baseline_timezone}</p></li>)}</ul>
    </details>
  </div>;
}
