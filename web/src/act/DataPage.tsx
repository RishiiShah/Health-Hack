import { useState, type ChangeEvent } from "react";
import { api, post } from "../api/client.ts";
import type { Snapshot } from "../api/live.ts";
import { clockTimeSeconds, duration } from "./time.ts";
import type { DataQuality, Dataset, IngestReport } from "./types.ts";
import "./act.css";

type Mode = "replace" | "append";
type Pending = { name: string; body: string; rows: number };

// Admin: reference data stays loaded in the database; an event stream loaded here drives every decision on the other screens.
export function DataPage({ snapshot, now, onChanged }: { snapshot: Snapshot | null; now: number | null; onChanged: () => void }) {
  const dataset = snapshot?.dataset as Dataset | undefined;
  const quality = snapshot?.data_quality as DataQuality | undefined;

  return (
    <div className="page">
      <h1>Data</h1>
      <p className="intro">
        Reference data (hospitals, rosters, credentials, coverage minimums and demand baselines) is already in the database.
        Load an event stream here and the server recomputes every decision from it.
      </p>
      <div className="data">
        <section className="panel">
          <div className="panel-head"><h2>Reference data</h2></div>
          {dataset ? (
            <div className="dataset"><b>{dataset.name}</b>{dataset.description} · {dataset.reference_files} reference files</div>
          ) : (
            <p className="unavailable">Not available yet: the server doesn't describe the loaded dataset.</p>
          )}
          <h2 style={{ fontSize: 15, margin: "4px 0 8px" }}>Checks on the loaded event stream</h2>
          <Checks quality={quality} />
          <Clear onChanged={onChanged} />
        </section>
        <LoadStream snapshot={snapshot} now={now} onChanged={onChanged} />
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

// The server's reset starts an empty event set and keeps the reference data; offers and interventions are cleared.
function Clear({ onChanged }: { onChanged: () => void }) {
  const [confirming, setConfirming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  async function clear() {
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
          <span style={{ fontSize: 14 }}>Remove every event, offer and intervention? Reference data stays loaded.</span>
          <button className="btn danger" onClick={clear}>Clear event stream</button>
          <button className="btn" onClick={() => setConfirming(false)}>Cancel</button>
        </>
      ) : (
        <button className="btn" onClick={() => setConfirming(true)}>Clear event stream…</button>
      )}
      {error && <p className="error" role="alert">{error}</p>}
    </div>
  );
}

const isJson = (body: string) => body.startsWith("[") || body.startsWith("{");
const rowCount = (body: string) => isJson(body) ? [JSON.parse(body)].flat().length : body.split("\n").filter((l) => l.trim() && !l.startsWith("event_id")).length;

function LoadStream({ snapshot, now, onChanged }: { snapshot: Snapshot | null; now: number | null; onChanged: () => void }) {
  const [mode, setMode] = useState<Mode>("replace");
  const [text, setText] = useState("");
  const [pending, setPending] = useState<Pending | null>(null);
  const [report, setReport] = useState<(IngestReport & { replaced: boolean }) | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const paused = Boolean((snapshot?.clock as { paused?: boolean } | undefined)?.paused);

  async function run(task: () => Promise<unknown>) {
    setBusy(true);
    setError(null);
    try {
      await task();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
      onChanged();
    }
  }

  // JSON goes to POST /events; anything else is sent as CSV rows for the server to parse. Adding moves the clock forward to
  // the file's latest event so later rows show at once. Replacing clears the events first and then sets the clock to the new
  // stream's last event, even when that is earlier than the current clock, so decisions are taken as of the stream's own time.
  const load = (body: string, replace: boolean) =>
    run(async () => {
      if (replace) await post("/admin/reset");
      const result = isJson(body)
        ? await post<IngestReport>("/events", JSON.parse(body))
        : await api<IngestReport>("/events/csv?advance_clock=true", { method: "POST", body, headers: { "Content-Type": "text/csv" } });
      if (replace && result.latest_event_time) await post("/admin/clock", { at: result.latest_event_time });
      setReport({ ...result, replaced: replace });
      setPending(null);
      setText("");
    });

  function stage(name: string, raw: string) {
    const body = raw.trim();
    setReport(null);
    try {
      if (mode === "replace") setPending({ name, body, rows: rowCount(body) });
      else load(body, false);
    } catch {
      setError("This isn't valid JSON. Paste CSV rows, or a JSON event or array.");
    }
  }

  async function upload(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (file) stage(file.name, await file.text());
    event.target.value = "";
  }

  return (
    <section className="panel inject">
      <div className="panel-head"><h2>Load an event stream</h2></div>
      <div className="queue" role="group" aria-label="How to load">
        <button aria-pressed={mode === "replace"} onClick={() => { setMode("replace"); setPending(null); }}>Replace the stream</button>
        <button aria-pressed={mode === "append"} onClick={() => { setMode("append"); setPending(null); }}>Add to the stream</button>
      </div>
      <p className="hint">
        {mode === "replace"
          ? "For a new event stream: current events, offers and interventions are cleared, the file is loaded and decisions are taken as of its last event."
          : "For follow-on events: rows are appended to the current stream and the clock moves forward to the latest one."}
      </p>
      <label className="btn primary block" style={{ display: "block", textAlign: "center" }}>
        Choose a CSV file<input type="file" accept=".csv,text/csv" hidden disabled={busy} onChange={upload} />
      </label>
      <label htmlFor="events" style={{ display: "block", fontWeight: 600, fontSize: 14, marginTop: 16 }}>Or paste rows</label>
      <textarea id="events" value={text} onChange={(e) => setText(e.target.value)} placeholder="event_id,event_time,ingested_at,consult_id,event_type,…" />
      <p className="hint">Same columns as event_stream.csv, or a JSON event or array. Late and repeated rows are handled like any stream.</p>
      <button className="btn block" disabled={busy || !text.trim()} onClick={() => stage("pasted rows", text)}>{mode === "replace" ? "Replace with pasted rows" : "Add pasted rows"}</button>

      {pending && (
        <div className="alert-panel" role="alertdialog" aria-label="Confirm replacing the event stream" style={{ marginTop: 16 }}>
          <p style={{ margin: "0 0 12px", fontSize: 14 }}>
            Replace the current event stream with <b>{pending.name}</b> ({pending.rows} {pending.rows === 1 ? "row" : "rows"})? Current events, offers and
            interventions are cleared. Reference data stays loaded.
          </p>
          <span style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            <button className="btn danger" disabled={busy} onClick={() => load(pending.body, true)}>{busy ? "Loading…" : "Replace stream"}</button>
            <button className="btn" disabled={busy} onClick={() => setPending(null)}>Cancel</button>
          </span>
        </div>
      )}
      {error && <p className="error" role="alert">{error}</p>}
      {report && (
        <p className="report" role="status">
          {report.replaced ? "Stream replaced. " : "Events added. "}
          Accepted <b>{report.accepted}</b> · duplicates <b>{report.duplicates}</b> · quarantined <b>{report.quarantined.length}</b>
          {report.held_orphans > 0 && <> · held <b>{report.held_orphans}</b></>}
          {report.pending_future > 0 && <> · waiting for the clock <b>{report.pending_future}</b></>}
          {report.replaced && report.latest_event_time && <> · decisions as of <b>{clockTimeSeconds(report.latest_event_time)} ET</b></>}
          {!report.replaced && report.clock_advanced_to && <> · clock moved to <b>{clockTimeSeconds(report.clock_advanced_to)}</b></>}
          {report.quarantined.length > 0 && <span className="muted"> ({report.quarantined.map((q) => q.reason).join("; ")})</span>}
        </p>
      )}

      <div className="clock-row" style={{ marginTop: 22, paddingTop: 16, borderTop: "1px solid var(--line)" }}>
        <span><span className="hint" style={{ display: "block", margin: 0 }}>Simulation clock</span><span className="big-clock">{now !== null ? clockTimeSeconds(now) : "--:--:--"}</span></span>
        <span style={{ display: "flex", gap: 8 }}>
          <button className="btn" disabled={busy} onClick={() => run(() => post("/admin/clock", { paused: !paused }))}>{paused ? "Resume" : "Pause"}</button>
          <button className="btn" disabled={busy} onClick={() => run(() => post("/admin/clock", { advance_s: 300 }))}>+5 min</button>
        </span>
      </div>
    </section>
  );
}
