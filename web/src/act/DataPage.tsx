import { DEMO } from "../api/client.ts";
import type { Snapshot } from "../api/live.ts";
import type { Dataset } from "./types.ts";
import { useApi } from "./hooks.ts";
import "./act.css";

type StoredKit = { fingerprint: string; name: string; service_date: string | null; hospitals: number; physicians: number; active: boolean };

// Admin: the reference data the server holds. Events are added from the Command page.
export function DataPage({ snapshot }: { snapshot: Snapshot | null }) {
  const dataset = snapshot?.dataset as Dataset | undefined;

  return (
    <div className="page">
      <h1>Data</h1>
      <p className="intro">
        Reference data defines the hospitals, physicians, credentials and capacity rules. Events are added on the
        Command page; decisions are recalculated from the stream's full history using the active reference kit.
      </p>
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
