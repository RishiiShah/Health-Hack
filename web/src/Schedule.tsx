import { useMemo, useState } from "react";
import { unavailableText, useApi } from "./act/hooks.ts";

export type Doctor = { id: string; name: string; group: "On shift" | "Off shift"; status: string; bar: string; tone: "day" | "night" | "unavailable" | "offer" | "off"; detail: string; avatar: string; workload: string; credentialed: string };

export type ScheduleData = {
  date?: string; date_label: string; now_label: string;
  alert: { text: string; physician_id: string } | null;
  filters: { label: string; ids: string[] }[];
  doctors: Doctor[];
};

const timeMarks = ["06:00", "08:00", "10:00", "12:00", "14:00", "16:00", "18:00", "20:00", "22:00", "24:00"];

export default function SchedulePage() {
  const { data, error } = useApi<ScheduleData>("/schedule", undefined, 2000);
  if (!data) return <div className="page"><h1>Schedule</h1><p className="unavailable">{error ? unavailableText(error, "GET /schedule") : "Loading…"}</p></div>;
  return <Schedule data={data} />;
}

function Schedule({ data }: { data: ScheduleData }) {
  const { doctors, filters, alert } = data;
  const [selectedId, setSelectedId] = useState(alert?.physician_id ?? doctors[0]?.id);
  const [filter, setFilter] = useState(filters[0]?.label ?? "");
  const selected = useMemo(() => doctors.find((doctor) => doctor.id === selectedId) ?? doctors[0], [doctors, selectedId]);
  if (!selected) return <div className="page"><h1>Schedule</h1><p>No physicians in the loaded references.</p></div>;
  const shown = new Set(filters.find((f) => f.label === filter)?.ids ?? doctors.map((d) => d.id));
  const visible = doctors.filter((doctor) => shown.has(doctor.id));
  return <div className="schedule-page"><div className="schedule-head"><div className="schedule-day"><button disabled title="Showing the loaded roster only" aria-label="Previous day">‹</button><strong>{data.date_label}</strong><button disabled title="Showing the loaded roster only" aria-label="Next day">›</button></div><div className="schedule-filters">{filters.map(({ label, ids }) => <button className={filter === label ? "active" : ""} key={label} onClick={() => setFilter(label)}>{label} <b>{ids.length}</b></button>)}</div></div>{alert && <div className="schedule-alert"><span>● {alert.text}</span><button onClick={() => setSelectedId(alert.physician_id)}>See the offer →</button></div>}<div className="schedule-layout"><section className="gantt-card"><div className="gantt-top"><div><span className="eyebrow">Roster overview</span><h1>Shift schedule</h1></div><span className="mono muted">{doctors.length} doctors · {data.now_label} ET</span></div><div className="gantt-grid"><div className="gantt-axis"><span />{timeMarks.map((time) => <span key={time}>{time}</span>)}</div><div className="now-line"><b>● {data.now_label} NOW</b></div>{["On shift", "Off shift"].map((group) => <div className="doctor-group" key={group}><div className="group-label"><span>{group}</span><small>{visible.filter((doctor) => doctor.group === group).length} doctors</small></div>{visible.filter((doctor) => doctor.group === group).map((doctor) => <button className={`doctor-row ${selected.id === doctor.id ? "selected" : ""}`} key={doctor.id} onClick={() => setSelectedId(doctor.id)}><span className="doctor-name"><b>{doctor.name}</b><small>{doctor.status}</small></span><span className={`doctor-bar ${doctor.tone}`}><i />{doctor.bar}</span></button>)}</div>)}</div><div className="schedule-legend"><span><i className="legend-day" />Day shift</span><span><i className="legend-night" />Night shift</span><span><i className="legend-unavailable" />Unavailable</span><span><i className="legend-offer" />Offer, not confirmed</span><small><em>*</em> Night shifts run past midnight.</small></div></section><aside className="schedule-side"><Inspector doctor={selected} /><MiniCalendar date={data.date} /></aside></div></div>;
}

function Inspector({ doctor }: { doctor: Doctor }) { return <section className="inspector-card"><div className="inspector-head"><span className="doctor-avatar">{doctor.avatar}</span><div><h2>{doctor.name}</h2><span className="mono">{doctor.id}</span></div></div><span className={`inspector-status ${doctor.tone === "offer" ? "amber" : "neutral"}`}>{doctor.status}</span><dl><dt>Today</dt><dd>{doctor.detail}</dd><dt>Workload</dt><dd>{doctor.workload}</dd><dt>Credentialed at</dt><dd>{doctor.credentialed}</dd></dl><a className="review-offer" href={doctor.tone === "offer" ? "#command" : "#doctors"}>{doctor.tone === "offer" ? "Review offers" : "View doctors"}</a></section>; }
function MiniCalendar({ date }: { date?: string }) {
  if (!date) return <section className="calendar-card"><p>Service date unavailable.</p></section>;
  const [year, month, today] = date.split("-").map(Number);
  const first = new Date(Date.UTC(year, month - 1, 1));
  const count = new Date(Date.UTC(year, month, 0)).getUTCDate();
  const cells = [...Array(first.getUTCDay()).fill(null), ...Array.from({ length: count }, (_, i) => i + 1)];
  const title = first.toLocaleDateString("en-US", { month: "long", year: "numeric", timeZone: "UTC" });
  return <section className="calendar-card"><div className="calendar-title"><h2>{title}</h2></div><div className="calendar-grid">
    {["S", "M", "T", "W", "T", "F", "S"].map((day, index) => <b key={index}>{day}</b>)}
    {cells.map((day, index) => <span className={day === today ? "today" : ""} key={index}>{day}</span>)}
  </div><p>Showing the loaded roster at {date}. Upcoming shifts require complete intervals.</p></section>;
}
