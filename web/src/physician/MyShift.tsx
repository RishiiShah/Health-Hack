// A physician's current shift: time left, hospitals covered and active consults.
import { unavailableText, useApi } from "../act/hooks.ts";
import { clockTime } from "../act/time.ts";
import { Empty, PageHead, Panel } from "../ui/Layout.tsx";
import { useCountUp } from "../ui/motion.ts";
import "./physician.css";

type Shift = { on_shift?: boolean; name: string; shift_end: string | null; minutes_to_shift_end: number | null; hospitals: string[]; consults: { consult_id: string; hospital_name: string; consult_type: string; stage: string; minutes_in_stage: number }[] };

export function MyShift() {
  const { data, error } = useApi<Shift>("/me/shift", undefined, 2000);
  const minutes = useCountUp(data?.minutes_to_shift_end ?? 0);
  if (!data) return <><PageHead kicker="Physician workspace" title="My shift" />{error ? <p className="unavailable">{unavailableText(error, "GET /me/shift")}</p> : <p className="muted">Loading…</p>}</>;
  const left = data.minutes_to_shift_end;
  const active = data.on_shift ?? (left !== null);
  return <>
    <PageHead kicker="Physician workspace" title="My shift" note={data.name}>
      <span className={`badge ${active ? "green" : "neutral"}`}>{active ? "On shift" : data.shift_end ? "Awaiting arrival" : "Off shift"}</span>
    </PageHead>
    {error && <p className="notice">Update failed: {error.message}. Retrying; showing the last received shift.</p>}
    <div className="physician-top">
      <Panel className="shift-clock" order={0}><span className="kicker">{active ? "Shift remaining" : "Scheduled window"}</span>
        {left === null ? <span className="shift-none">Not on shift</span> : <strong>{`${Math.floor(minutes / 60)}h ${String(minutes % 60).padStart(2, "0")}m`}</strong>}
        <p>{data.shift_end ? `${active ? "Until" : "Scheduled until"} ${clockTime(data.shift_end)} ET` : "No current shift"}</p>
      </Panel>
      <Panel className="hospitals-card" order={1}><span className="kicker">Hospitals covered</span><h2>{data.hospitals.join(" · ") || "–"}</h2><p>{data.consults.length} active consults</p></Panel>
    </div>
    <Panel title="Active consults" order={2}>
      {data.consults.length ? data.consults.map((c) => <div className="consult-line" key={c.consult_id}><b className="mono">{c.consult_id}</b><span>{c.hospital_name} · {c.consult_type}</span><span className="badge neutral">{c.stage} · {c.minutes_in_stage} min</span></div>) : <Empty>No open consults.</Empty>}
    </Panel>
  </>;
}
