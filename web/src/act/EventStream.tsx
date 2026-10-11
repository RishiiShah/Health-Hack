import { useState, type ChangeEvent } from "react";
import { api, DEMO, post } from "../api/client.ts";
import type { Snapshot } from "../api/live.ts";
import { clockTimeSeconds, duration } from "./time.ts";
import type { DataQuality, IngestReport, UploadBatch } from "./types.ts";
import { UploadResult } from "./UploadResult.tsx";
import { boardOf, type Board } from "./uploadSummary.ts";
import { useApi } from "./hooks.ts";
import "./act.css";

// Data page: add events, the server's checks on the stream, a fresh-stream reset and the saved upload receipts.
export function EventStream({ snapshot, now, onChanged }: { snapshot: Snapshot; now: number | null; onChanged: () => void }) {
  return <>
    <div className="data-grid">
      <LiveTest snapshot={snapshot} now={now} onChanged={onChanged} />
      <section className="panel">
        <div className="panel-head"><h2>Checks on the event stream</h2></div>
        <Checks quality={snapshot.data_quality as DataQuality | undefined} />
        {!DEMO && <Reset onChanged={onChanged} />}
      </section>
    </div>
    {!DEMO && <UploadHistory revision={snapshot.revision} />}
  </>;
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
    <div className="reset-row">
      {confirming ? (
        <>
          <span>Start an empty event stream with the same references? Current consults, offers and interventions will be cleared.</span>
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

function LiveTest({ snapshot, now, onChanged }: { snapshot: Snapshot; now: number | null; onChanged: () => void }) {
  const [text, setText] = useState("");
  const [report, setReport] = useState<IngestReport | null>(null);
  const [before, setBefore] = useState<Board | null>(null);
  const [after, setAfter] = useState<Board | null>(null);
  const [boardError, setBoardError] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const paused = Boolean((snapshot.clock as { paused?: boolean } | undefined)?.paused);

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
      setReport(null);
      setBefore(null);
      setAfter(null);
      setBoardError(null);
      setBefore(boardOf(await api<Snapshot>("/snapshot")));
      const trimmed = typeof body === "string" ? body.trim() : "";
      const result = trimmed.startsWith("[") || trimmed.startsWith("{")
        ? await post<IngestReport>("/events", JSON.parse(trimmed))
        : await api<IngestReport>("/events/csv?advance_clock=true", { method: "POST", body, headers: { "Content-Type": "text/csv", "X-Upload-Filename": encodeURIComponent(filename) } });
      setReport(result);
      try {
        const uploaded = await api<Snapshot>("/snapshot");
        if (uploaded.revision < result.revision) throw new Error("The server returned a board from before this upload");
        setAfter(boardOf(uploaded));
      } catch (e) {
        setBoardError(`Upload saved, but board changes could not be loaded: ${(e as Error).message}. See the Command page for the current board.`);
      }
    });

  async function upload(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (file) await send(file);
    event.target.value = "";
  }

  if (DEMO) return (
    <section className="panel inject">
      <div className="panel-head"><h2>Upload events</h2></div>
      <p className="unavailable">Event testing requires the live backend. This presentation demo shows fixed example decisions and cannot process uploaded events.</p>
    </section>
  );

  return (
    <section className="panel inject">
      <div className="panel-head"><h2>Upload events</h2></div>
      <div className="clock-row">
        <span className="big-clock">{now !== null ? clockTimeSeconds(now) : "--:--:--"}</span>
        <span className="actions">
          <button className="btn" disabled={busy} onClick={() => run(() => post("/admin/clock", { paused: !paused }))}>{paused ? "Resume" : "Pause"}</button>
          <button className="btn" disabled={busy} onClick={() => run(() => post("/admin/clock", { advance_s: 300 }))}>+5 min</button>
          <button className="btn" disabled={busy} onClick={() => run(() => post("/admin/clock", { to_start: true }))}>Reset to 18:20</button>
        </span>
      </div>
      <label className="btn primary block">
        Upload an events CSV<input type="file" accept=".csv,text/csv" hidden disabled={busy} onChange={upload} />
      </label>
      <p className="hint">Use the columns from event_stream.csv. Events append to the current stream and the Command page updates. A file whose hospitals and physicians belong to another stored reference kit starts a fresh stream on that kit. Newly accepted events can move the clock forward by up to 24 hours.</p>
      <details>
        <summary>Paste events instead</summary>
        <textarea id="events" aria-label="Events to add" value={text} onChange={(e) => setText(e.target.value)} placeholder="event_id,event_time,ingested_at,consult_id,event_type,…" />
        <button className="btn block" disabled={busy || !text.trim()} onClick={() => send(text)}>Add to stream</button>
      </details>
      {error && <p className="error" role="alert">{error}</p>}
      {report && (
        <div aria-live="polite">
          {report.dataset_switched_to && <p className="report">Switched to <b>{report.dataset_switched_to.name}</b> and started a fresh event stream.</p>}
          {before && after && <UploadResult report={report} before={before} after={after} />}
          {!after && !boardError && <p role="status">Loading board changes after the upload…</p>}
          {boardError && <p className="error" role="alert">{boardError}</p>}
          {report.quarantined.length > 0 && <p className="report muted">Quarantined: {report.quarantined.map((q) => q.reason).join("; ")}</p>}
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
    {data?.items.length === 0 && <p>No CSV uploads recorded yet. Upload a file above to add to the event stream.</p>}
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
