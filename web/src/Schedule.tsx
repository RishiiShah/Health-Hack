import { useMemo, useState } from "react";
import { unavailableText, useApi } from "./act/hooks.ts";

export type Doctor = { id: string; name: string; group: "On shift" | "Off shift"; status: string; bar: string; tone: "day" | "night" | "unavailable" | "offer" | "off"; detail: string; avatar: string; workload: string; credentialed: string };

export type ScheduleData = {
  date_label: string; now_label: string;
  alert: { text: string; physician_id: string } | null;
  filters: { label: string; ids: string[] }[];
  doctors: Doctor[];
};

const timeMarks = ["06:00", "08:00", "10:00", "12:00", "14:00", "16:00", "18:00", "20:00", "22:00", "24:00"];

export default function SchedulePage() {
  const { data, error } = useApi<ScheduleData>("/schedule");
  if (!data) return <div className="page"><h1>Schedule</h1><p className="unavailable">{error ? unavailableText(error, "GET /schedule") : "Loading…"}</p></div>;
  return <Schedule data={data} />;
}

function Schedule({ data }: { data: ScheduleData }) {
  const { doctors, filters, alert } = data;
  const [selectedId, setSelectedId] = useState(alert?.physician_id ?? doctors[0]?.id);
  const [filter, setFilter] = useState(filters[0]?.label ?? "");
  const selected = useMemo(() => doctors.find((doctor) => doctor.id === selectedId) ?? doctors[0], [doctors, selectedId]);
  const shown = new Set(filters.find((f) => f.label === filter)?.ids ?? doctors.map((d) => d.id));
  const visible = doctors.filter((doctor) => shown.has(doctor.id));
  return <div className="schedule-page"><div className="schedule-head"><div className="schedule-day"><button aria-label="Previous day">‹</button><strong>{data.date_label}</strong><button aria-label="Next day">›</button></div><div className="schedule-filters">{filters.map(({ label, ids }) => <button className={filter === label ? "active" : ""} key={label} onClick={() => setFilter(label)}>{label} <b>{ids.length}</b></button>)}</div></div>{alert && <div className="schedule-alert"><span>● {alert.text}</span><button onClick={() => setSelectedId(alert.physician_id)}>See the offer →</button></div>}<div className="schedule-layout"><section className="gantt-card"><div className="gantt-top"><div><span className="eyebrow">Roster overview</span><h1>Shift schedule</h1></div><span className="mono muted">{doctors.length} doctors · {data.now_label} ET</span></div><div className="gantt-grid"><div className="gantt-axis"><span />{timeMarks.map((time) => <span key={time}>{time}</span>)}</div><div className="now-line"><b>● {data.now_label} NOW</b></div>{["On shift", "Off shift"].map((group) => <div className="doctor-group" key={group}><div className="group-label"><span>{group}</span><small>{visible.filter((doctor) => doctor.group === group).length} doctors</small></div>{visible.filter((doctor) => doctor.group === group).map((doctor) => <button className={`doctor-row ${selected.id === doctor.id ? "selected" : ""}`} key={doctor.id} onClick={() => setSelectedId(doctor.id)}><span className="doctor-name"><b>{doctor.name}</b><small>{doctor.status}</small></span><span className={`doctor-bar ${doctor.tone}`}><i />{doctor.bar}</span></button>)}</div>)}</div><div className="schedule-legend"><span><i className="legend-day" />Day shift</span><span><i className="legend-night" />Night shift</span><span><i className="legend-unavailable" />Unavailable</span><span><i className="legend-offer" />Offer, not confirmed</span><small><em>*</em> Night shifts run past midnight.</small></div></section><aside className="schedule-side"><Inspector doctor={selected} /><MiniCalendar /></aside></div></div>;
}

function Inspector({ doctor }: { doctor: Doctor }) { return <section className="inspector-card"><div className="inspector-head"><span className="doctor-avatar">{doctor.avatar}</span><div><h2>{doctor.name}</h2><span className="mono">{doctor.id}</span></div></div><span className={`inspector-status ${doctor.tone === "offer" ? "amber" : "neutral"}`}>{doctor.tone === "offer" ? "Off shift, offer pending" : doctor.status}</span><dl><dt>Today</dt><dd>{doctor.detail}</dd><dt>Workload</dt><dd>{doctor.workload}</dd><dt>Credentialed at</dt><dd>{doctor.credentialed}</dd></dl><button className="review-offer">{doctor.tone === "offer" ? "Review offer" : "View doctor"}</button></section>; }
function MiniCalendar() { const days = ["S", "M", "T", "W", "T", "F", "S"]; const cells = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31]; return <section className="calendar-card"><div className="calendar-title"><h2>March 2026</h2><span>‹ ›</span></div><div className="calendar-grid">{days.map((day, index) => <b key={`${day}-${index}`}>{day}</b>)}{cells.map((day) => <span className={day === 17 ? "today" : ""} key={day}>{day}</span>)}</div><p><em>Only 17 March is in the training data.</em> Other days fill in when a roster covers them.</p></section>; }
