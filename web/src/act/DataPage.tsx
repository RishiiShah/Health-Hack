import { useState, type ChangeEvent } from "react";
import { api, DEMO, post } from "../api/client.ts";
import type { Snapshot } from "../api/live.ts";
import { clockTimeSeconds, duration } from "./time.ts";
import type { DataQuality, Dataset, IngestReport, UploadBatch } from "./types.ts";
import { useApi } from "./hooks.ts";
import "./act.css";

// Admin: what is loaded, the server's data checks, and the live-test controls.
export function DataPage({ snapshot, now, onChanged }: { snapshot: Snapshot | null; now: number | null; onChanged: () => void }) {
  const dataset = snapshot?.dataset as Dataset | undefined;
  const quality = snapshot?.data_quality as DataQuality | undefined;

  return (
    <div className="page">
      <h1>Data</h1>
      <p className="intro">
        Reference data defines the hospitals, physicians, credentials and capacity rules. Uploaded events are appended to
        the current stream, and decisions are recalculated from its full history using the same references.
      </p>
      <div className="data">
        <section className="panel">
          <div className="panel-head"><h2>Reference data</h2></div>
          {dataset ? (
            <div className="dataset"><b>{dataset.name}</b>{dataset.description} · {dataset.reference_files} reference files</div>
          ) : (
            <p className="unavailable">Not available yet: the server doesn't describe the loaded dataset.</p>
          )}
          {!DEMO && <BaselineInventory revision={snapshot?.revision} />}
          <h2 style={{ fontSize: 15, margin: "4px 0 8px" }}>Checks on the event stream</h2>
          <Checks quality={quality} />
          {!DEMO && <Reset onChanged={onChanged} />}
        </section>
        <LiveTest snapshot={snapshot} now={now} onChanged={onChanged} />
      </div>
      {!DEMO && <UploadHistory revision={snapshot?.revision} />}
    </div>
  );
}

function Checks({ quality }: { quality?: DataQuality }) {
  if (!quality?.supported) return <p className="unavailable">Not available yet: the server doesn't send data-quality counts.</p>;
  const rows: [string, string, string][] = [
    ["Rows received", `${quality.events_read ?? "?"}${quality.counts_exact === false ? " (historical estimate)" : ""}`, "neutral"],
    ["Accepted events", `${quality.accepted_events ?? quality.accepted ?? "?"}`, "neutral"],
    ["Duplicates dropped", `${quality.duplicates ?? 0}${quality.duplicate_ids?.length ? ` (${quality.duplicate_ids.join(", ")})` : ""}`, "neutral"],
    ["Conflicting duplicates", `${quality.conflicts ?? 0}`, quality.conflicts ? "red" : "neutral"],
    ["Late events, over 60 s", `${quality.late ?? 0}${quality.max_delivery_lag_s ? ` (${duration(quality.max_delivery_lag_s)})` : ""}`, "neutral"],
    ["Out of order by a few seconds", `${quality.reordered ?? 0}`, "neutral"],
    ["Quarantined rows (includes expired holds)", `${quality.rejected ?? 0}`, quality.rejected ? "red" : "green"],
    ["Held events, awaiting dependencies", `${quality.pending_orphans ?? 0}`, quality.pending_orphans ? "red" : "neutral"],
  ];
  return (
    <ul className="checks">
      {rows.map(([label, value, tone]) => <li key={label}>{label}<span className={`badge ${tone}`}>{value}</span></li>)}
    </ul>
  );
}

function Reset({ onChanged }: { onChanged: () => void }) {
  const [confirming, setConfirming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  async function reset() {
    try {
      await post("/admin/reset");
      setConfirming(false);
      onChanged();
    } catch (e) {
      setError((e as Error).message);
    }
  }
  return (
    <div style={{ marginTop: 18, display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
      {confirming ? (
        <>
          <span style={{ fontSize: 14 }}>Start an empty event stream with the same references? Current consults, offers and interventions will be cleared.</span>
          <button className="btn danger" onClick={reset}>Start empty stream</button>
          <button className="btn" onClick={() => setConfirming(false)}>Cancel</button>
        </>
      ) : (
        <button className="btn" onClick={() => setConfirming(true)}>Start empty stream…</button>
      )}
      {error && <p className="error" role="alert">{error}</p>}
    </div>
  );
}

function LiveTest({ snapshot, now, onChanged }: { snapshot: Snapshot | null; now: number | null; onChanged: () => void }) {
  const [text, setText] = useState("");
  const [report, setReport] = useState<IngestReport | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const paused = Boolean((snapshot?.clock as { paused?: boolean } | undefined)?.paused);

  async function run(task: () => Promise<unknown>) {
    setBusy(true);
    setError(null);
    try {
      await task();
      onChanged();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  // A parsed CSV has a durable receipt; only newly accepted events can advance the clock.
  const send = (body: string | File, filename = typeof body === "string" ? "pasted-events.csv" : body.name) =>
    run(async () => {
      const trimmed = typeof body === "string" ? body.trim() : "";
      const result = trimmed.startsWith("[") || trimmed.startsWith("{")
        ? await post<IngestReport>("/events", JSON.parse(trimmed))
        : await api<IngestReport>("/events/csv?advance_clock=true", { method: "POST", body, headers: { "Content-Type": "text/csv", "X-Upload-Filename": encodeURIComponent(filename) } });
      setReport(result);
    });

  async function upload(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (file) await send(file);
    event.target.value = "";
  }

  if (DEMO) return (
    <section className="panel inject">
      <div className="panel-head"><h2>Live test</h2></div>
      <p className="unavailable">Event testing requires the live backend. This presentation demo shows fixed example decisions and cannot process uploaded events.</p>
    </section>
  );

  return (
    <section className="panel inject">
      <div className="panel-head"><h2>Live test</h2></div>
      <div className="clock-row">
        <span className="big-clock">{now !== null ? clockTimeSeconds(now) : "--:--:--"}</span>
        <span style={{ display: "flex", gap: 8 }}>
          <button className="btn" disabled={busy} onClick={() => run(() => post("/admin/clock", { paused: !paused }))}>{paused ? "Resume" : "Pause"}</button>
          <button className="btn" disabled={busy} onClick={() => run(() => post("/admin/clock", { advance_s: 300 }))}>+5 min</button>
        </span>
      </div>
      <label htmlFor="events" style={{ fontWeight: 600, fontSize: 14 }}>Add events</label>
      <textarea id="events" value={text} onChange={(e) => setText(e.target.value)} placeholder="event_id,event_time,ingested_at,consult_id,event_type,…" />
      <p className="hint">Use the columns from event_stream.csv, or a JSON event or array. Events append to the history using the fixed Sevaro references. Newly accepted CSV events can move the test clock forward by up to 24 hours. Larger jumps stay pending until you check the dates and explicitly advance the clock. Check the row results when the queue is unchanged.</p>
      <button className="btn primary block" disabled={busy || !text.trim()} onClick={() => send(text)}>Add to stream</button>
      <label className="btn block" style={{ display: "block", textAlign: "center", marginTop: 10 }}>
        Upload a CSV file<input type="file" accept=".csv,text/csv" hidden disabled={busy} onChange={upload} />
      </label>
      {error && <p className="error" role="alert">{error}</p>}
      {report && (
        <div aria-live="polite"><p className="report">
          Accepted <b>{report.accepted}</b> · duplicates <b>{report.duplicates}</b> · quarantined <b>{report.quarantined.length}</b>
          {report.held_orphans > 0 && <> · held <b>{report.held_orphans}</b></>}
          {report.pending_future > 0 && <> · waiting for the clock <b>{report.pending_future}</b></>}
          {report.clock_advanced_to && <> · clock moved to <b>{clockTimeSeconds(report.clock_advanced_to)}</b></>}
          {report.quarantined.length > 0 && <span className="muted"> ({report.quarantined.map((q) => q.reason).join("; ")})</span>}
        </p>
        {report.clock_warning && <p className="error" role="alert">{report.clock_warning}</p>}
        <RowResults report={report} />
        </div>
      )}
    </section>
  );
}

function RowResults({ report }: { report: IngestReport }) {
  const issues = report.row_results?.filter(row => row.status !== "accepted" && row.status !== "duplicate") ?? [];
  if (!issues.length) return null;
  return <div className="upload-issues">
    <p className="hint">{issues.length} rows need attention. Results describe the time of upload; held events may be released when their dependencies arrive.</p>
    <ul>{issues.slice(0, 50).map(row => <li key={row.row_number}>
      <b>Row {row.row_number} · {row.event_id || "missing event ID"} · {row.status}</b>
      <span>{row.reason || "Dependency unavailable"}</span>
      {row.expires_at && <span>Hold expires {new Date(row.expires_at).toLocaleString()}</span>}
    </li>)}</ul>
    {issues.length > 50 && <p className="hint">Showing the first 50 rows. Download the saved report for all results.</p>}
  </div>;
}

function downloadReport(batch: UploadBatch) {
  const url = URL.createObjectURL(new Blob([JSON.stringify(batch, null, 2)], { type: "application/json" }));
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `${batch.filename}.report.json`;
  anchor.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function UploadHistory({ revision }: { revision?: unknown }) {
  const { data, error } = useApi<{ items: UploadBatch[] }>("/admin/uploads", revision);
  return <section className="panel upload-history" aria-labelledby="uploads-heading">
    <div className="panel-head"><h2 id="uploads-heading">Upload history</h2></div>
    <p className="hint">Latest 20 CSV receipts, saved across navigation, restarts and empty-stream resets. Each report records results at upload time. Earlier uploads made before this feature have no receipt.</p>
    {error && <p className="error" role="alert">Could not load upload history: {error.message}</p>}
    {!data && !error && <p role="status">Loading upload history…</p>}
    {data?.items.length === 0 && <p>No CSV uploads recorded yet. Upload a file above to test the combined event stream.</p>}
    {data?.items.map(batch => <details key={batch.batch_id}>
      <summary><b>{batch.filename}</b> · {new Date(batch.received_at).toLocaleString()}<span>
        {batch.report.accepted} accepted · {batch.report.duplicates} duplicates · {batch.report.quarantined.length} quarantined · {batch.report.row_results?.filter(row => row.status === "held").length ?? 0} held rows
      </span></summary>
      <p>Uploaded by {batch.actor} · stream generation {batch.dataset_generation}</p>
      <p>Consults mentioned: {batch.consult_ids.join(", ") || "none"}</p>
      <p>Replay clock: {batch.clock_before} → {batch.clock_after}</p>
      {batch.report.pending_future > 0 && <p>{batch.report.pending_future} accepted events were waiting for the clock.</p>}
      {batch.report.clock_warning && <p className="error">{batch.report.clock_warning}</p>}
      <RowResults report={batch.report} />
      <button className="btn" onClick={() => downloadReport(batch)}>Download report</button>
    </details>)}
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
