import { useState } from "react";
import { DEMO, post } from "../api/client.ts";
import { Modal } from "../ui/Modal.tsx";
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
  const [reload, setReload] = useState(0);
  const [adding, setAdding] = useState(false);
  const { data, error } = useApi<{ kits?: StoredKit[] }>("/admin/references", `${revision}:${reload}`);
  return <section className="panel upload-history" aria-labelledby="kits-heading">
    <div className="panel-head"><h2 id="kits-heading">Stored reference kits</h2><button className="btn primary" onClick={() => setAdding(true)}>Add reference kit<span aria-hidden="true">+</span></button></div>
    <AddKit open={adding} onClose={() => setAdding(false)} onAdded={() => setReload((n) => n + 1)} />
    <p className="hint">An events CSV whose hospitals and physicians all belong to one of these kits switches to it with a fresh event stream. A stored kit never changes.</p>
    {error && <p className="error" role="alert">Could not load reference kits: {error.message}</p>}
    {!data && !error && <p role="status">Loading reference kits…</p>}
    {data?.kits && <ul className="checks">{data.kits.map(kit => <li key={kit.fingerprint}>
      <span><b>{kit.name}</b> · {kit.hospitals} hospitals · {kit.physicians} physicians{kit.service_date ? ` · ${kit.service_date}` : ""}</span>
      <span className={`badge ${kit.active ? "green" : "neutral"}`}>{kit.active ? "Active" : "Stored"}</span>
    </li>)}</ul>}
  </section>;
}


const KIT_FILES = ["hospitals.csv", "physicians_on_shift.csv", "physicians_off_shift_roster.csv", "credentialing_matrix.csv",
  "baseline_hourly_volume.csv", "coverage_requirements.csv"];
type KitResult = { activated: boolean; unchanged: boolean; stored: boolean; hospitals: number; physicians: number; manifest?: { fingerprint?: string } };

// Upload a reference kit: the six CSVs, a name, and the service date that the sample layout's undated shift times need.
function AddKit({ open, onClose, onAdded }: { open: boolean; onClose: () => void; onAdded: () => void }) {
  const [name, setName] = useState("");
  const [serviceDate, setServiceDate] = useState("");
  const [files, setFiles] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<KitResult | null>(null);
  const missing = KIT_FILES.filter((f) => !(f in files));

  async function pick(list: FileList | null) {
    // One multi-select fills every slot whose file name matches; anything else is ignored.
    const read = await Promise.all([...(list ?? [])].filter((f) => KIT_FILES.includes(f.name)).map(async (f) => [f.name, await f.text()] as const));
    setFiles((prev) => ({ ...prev, ...Object.fromEntries(read) }));
  }
  function close() { setName(""); setServiceDate(""); setFiles({}); setError(null); setResult(null); onClose(); }
  async function submit() {
    setBusy(true); setError(null);
    try {
      setResult(await post<KitResult>("/admin/references", { files, name: name.trim() || "uploaded references", ...(serviceDate ? { service_date: serviceDate } : {}) }));
      onAdded();
    } catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  }

  return <Modal open={open} kicker="Reference data" title="Add a reference kit" onClose={close}>
    {result ? <>
      <p className="notice">{result.unchanged ? "This kit is already stored; nothing changed." : result.activated ? "Kit stored and made active." : "Kit stored beside the active one."} {result.hospitals} hospitals · {result.physicians} physicians.</p>
      <p className="hint">An events CSV whose hospitals and physicians belong to this kit switches to it with a fresh event stream.</p>
      <div className="modal-actions"><button className="btn primary" onClick={close}>Done</button></div>
    </> : <>
      <p className="hint">Choose all six CSVs at once (they are matched by file name). A stored kit never changes; the first kit must be the official Sevaro kit.</p>
      <label className="btn block">Choose kit files<input type="file" accept=".csv,text/csv" multiple hidden onChange={(e) => { void pick(e.target.files); e.target.value = ""; }} /></label>
      <ul className="modal-list">{KIT_FILES.map((f) => <li key={f}><span className="mono">{f}</span><span className={`badge ${f in files ? "green" : "neutral"}`}>{f in files ? "ready" : "missing"}</span></li>)}</ul>
      <div className="kit-fields">
        <label>Kit name<input type="text" value={name} onChange={(e) => setName(e.target.value)} placeholder="uploaded references" /></label>
        <label>Service date<input type="date" value={serviceDate} onChange={(e) => setServiceDate(e.target.value)} /><small className="hint">Only for the sample layout, whose shift times have no date.</small></label>
      </div>
      {error && <p className="error" role="alert">{error}</p>}
      <div className="modal-actions">
        <button className="btn" onClick={close}>Cancel</button>
        <button className="btn primary" disabled={busy || missing.length > 0} onClick={submit}>{busy ? "Uploading…" : missing.length ? `${missing.length} file${missing.length === 1 ? "" : "s"} missing` : "Add kit"}</button>
      </div>
    </>}
  </Modal>;
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
