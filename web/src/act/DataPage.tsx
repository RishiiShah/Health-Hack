import { useState, type ChangeEvent } from "react";
import { api, post } from "../api/client.ts";
import type { Snapshot } from "../api/live.ts";
import { clockTimeSeconds, duration } from "./time.ts";
import type { DataQuality, Dataset, IngestReport } from "./types.ts";
import "./act.css";

// Admin: what is loaded, the server's data checks, and the live-test controls.
export function DataPage({ snapshot, now, onChanged }: { snapshot: Snapshot | null; now: number | null; onChanged: () => void }) {
  const dataset = snapshot?.dataset as Dataset | undefined;
  const quality = snapshot?.data_quality as DataQuality | undefined;

  return (
    <div className="page">
      <h1>Data</h1>
      <p className="intro">
        Command runs on whichever dataset is loaded here. Nothing on the other screens is fixed to the training data, so loading
        the test set updates everything.
      </p>
      <div className="data">
        <section className="panel">
          <div className="panel-head"><h2>Dataset</h2></div>
          {dataset ? (
            <div className="dataset"><b>{dataset.name}</b>{dataset.description} · {dataset.reference_files} reference files</div>
          ) : (
            <p className="unavailable">Not available yet: the server doesn't describe the loaded dataset.</p>
          )}
          <h2 style={{ fontSize: 15, margin: "4px 0 8px" }}>Checks on the loaded data</h2>
          <Checks quality={quality} />
          <Reset onChanged={onChanged} />
        </section>
        <LiveTest snapshot={snapshot} now={now} onChanged={onChanged} />
      </div>
    </div>
  );
}

function Checks({ quality }: { quality?: DataQuality }) {
  if (!quality?.supported) return <p className="unavailable">Not available yet: the server doesn't send data-quality counts.</p>;
  const orphaned = (quality.rejected ?? 0) + (quality.pending_orphans ?? 0) + (quality.expired_orphans ?? 0);
  const rows: [string, string, string][] = [
    ["Events read", `${quality.events_read ?? "?"}`, "neutral"],
    ["Duplicates dropped", `${quality.duplicates ?? 0}${quality.duplicate_ids?.length ? ` (${quality.duplicate_ids.join(", ")})` : ""}`, "neutral"],
    ["Conflicting duplicates", `${quality.conflicts ?? 0}`, quality.conflicts ? "red" : "neutral"],
    ["Late events, over 60 s", `${quality.late ?? 0}${quality.max_delivery_lag_s ? ` (${duration(quality.max_delivery_lag_s)})` : ""}`, "neutral"],
    ["Out of order by a few seconds", `${quality.reordered ?? 0}`, "neutral"],
    ["Rejected or orphaned", `${orphaned}`, orphaned ? "red" : "green"],
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
          <span style={{ fontSize: 14 }}>Drop every added event and go back to the base data?</span>
          <button className="btn danger" onClick={reset}>Reset to base</button>
          <button className="btn" onClick={() => setConfirming(false)}>Cancel</button>
        </>
      ) : (
        <button className="btn" onClick={() => setConfirming(true)}>Reset to base…</button>
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

  // JSON goes to POST /events; anything else is sent as CSV rows for the server to parse.
  const send = (body: string) =>
    run(async () => {
      const trimmed = body.trim();
      const result = trimmed.startsWith("[") || trimmed.startsWith("{")
        ? await post<IngestReport>("/events", JSON.parse(trimmed))
        : await api<IngestReport>("/events/csv", { method: "POST", body: trimmed, headers: { "Content-Type": "text/csv" } });
      setReport(result);
    });

  async function upload(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (file) await send(await file.text());
    event.target.value = "";
  }

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
      <p className="hint">One row per line, same columns as event_stream.csv, or a JSON event or array. Late and repeated rows are handled like the base stream.</p>
      <button className="btn primary block" disabled={busy || !text.trim()} onClick={() => send(text)}>Add to stream</button>
      <label className="btn block" style={{ display: "block", textAlign: "center", marginTop: 10 }}>
        Upload a CSV file<input type="file" accept=".csv,text/csv" hidden onChange={upload} />
      </label>
      {error && <p className="error" role="alert">{error}</p>}
      {report && (
        <p className="report">
          Accepted <b>{report.accepted}</b> · duplicates <b>{report.duplicates}</b> · quarantined <b>{report.quarantined.length}</b>
          {report.held_orphans > 0 && <> · held <b>{report.held_orphans}</b></>}
          {report.quarantined.length > 0 && <span className="muted"> ({report.quarantined.map((q) => q.reason).join("; ")})</span>}
        </p>
      )}
    </section>
  );
}
