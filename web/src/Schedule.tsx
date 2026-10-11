import { useState } from "react";
import { unavailableText, useApi } from "./act/hooks.ts";
import { clockPosition, shiftWindow } from "./scheduleTimeline.ts";
import { PageHead } from "./ui/Layout.tsx";
import "./schedule.css";

export type Doctor = { id: string; name: string; group: "On shift" | "Off shift"; status: string; bar: string; tone: "day" | "night" | "unavailable" | "offer" | "off"; detail: string; avatar: string; workload: string; credentialed: string };
export type ScheduleData = { date?: string; date_label: string; now_label: string; alert: { text: string; physician_id: string } | null; filters: { label: string; ids: string[] }[]; doctors: Doctor[] };
const timeMarks = ["00:00", "04:00", "08:00", "12:00", "16:00", "20:00", "24:00"];

// Reloads with each live snapshot so offers and status changes show without a page refresh.
export default function SchedulePage({ reloadKey }: { reloadKey?: unknown }) {
  const { data, error } = useApi<ScheduleData>("/schedule", reloadKey);
  if (!data) return <><PageHead kicker="Staffing & availability" title="Shift schedule" /><p className="unavailable">{error ? unavailableText(error, "GET /schedule") : "Loading schedule…"}</p></>;
  return <Schedule data={data} error={error ? unavailableText(error, "GET /schedule") : null} />;
}

function Schedule({ data, error }: { data: ScheduleData; error: string | null }) {
  const { doctors, filters, alert } = data;
  const [selectedId, setSelectedId] = useState(alert?.physician_id ?? doctors[0]?.id);
  const [filter, setFilter] = useState(filters[0]?.label ?? "");
  const [query, setQuery] = useState("");
  const shown = new Set(filters.find(f => f.label === filter)?.ids ?? doctors.map(d => d.id));
  const visible = doctors.filter(d => shown.has(d.id) && `${d.name} ${d.id}`.toLowerCase().includes(query.trim().toLowerCase()));
  const selected = visible.find(d => d.id === selectedId) ?? visible[0];
  const now = clockPosition(data.now_label);
  const select = (id: string) => { setSelectedId(id); if (matchMedia("(max-width: 69em)").matches) requestAnimationFrame(() => document.getElementById("schedule-inspector")?.scrollIntoView({ behavior: "smooth", block: "start" })); };
  return <div className="schedule-page roster-page">
    <PageHead kicker="Staffing & availability" title="Shift schedule" note="See who is scheduled, review availability, and follow up on coverage."><div className="roster-date"><strong>{data.date_label}</strong><span>Roster time · {data.now_label} ET</span></div></PageHead>
    {error && <p className="unavailable" role="status">Schedule updates interrupted. {error}</p>}
    <div className="roster-summary"><div><strong>{doctors.filter(d => d.group === "On shift").length}</strong><span>On shift now</span></div><div><strong>{doctors.filter(d => d.group === "Off shift").length}</strong><span>Off shift now</span></div><div><strong>{doctors.filter(d => d.tone === "offer").length}</strong><span>Unconfirmed offers</span></div></div>
    {alert && <div className="roster-alert"><div><span className="roster-alert-label">Coverage follow-up</span><p>{alert.text}</p></div><button onClick={() => { setFilter(filters[0]?.label ?? ""); setQuery(""); select(alert.physician_id); }}>Inspect physician <span aria-hidden="true">→</span></button></div>}
    <div className="schedule-layout roster-layout"><section className="roster-card" aria-label="Shift timeline">
      <div className="roster-card-head"><div><h2>Daily roster</h2><p>{visible.length} of {doctors.length} physicians · All times Eastern</p></div><label className="roster-search"><span className="sr-only">Search scheduled physicians</span><input type="search" placeholder="Search name or ID" value={query} onChange={e => setQuery(e.target.value)} /></label></div>
      <div className="roster-filters" role="group" aria-label="Filter roster">{filters.map(({ label, ids }) => <button aria-pressed={filter === label} key={label} onClick={() => setFilter(label)}>{label} <span>{ids.length}</span></button>)}</div>
      <p className="roster-scroll-hint">Scroll across to view the full day. Select a physician for details.</p>
      <div className="roster-scroll" tabIndex={0} role="region" aria-label="Physician shifts from midnight to midnight">
        <div className="roster-timeline">
          <div className="roster-axis"><span>Physician / current status</span><div>{timeMarks.map((time, i) => <span key={time} style={{ left: `${i / 6 * 100}%` }}>{time}</span>)}</div></div>
          {now !== null && <div className="roster-now" style={{ left: `calc(var(--roster-name) + (100% - var(--roster-name) - var(--roster-pad)) * ${now / 100})` }}><span>{data.now_label} now</span></div>}
          {(["On shift", "Off shift"] as const).map(group => {
            const members = visible.filter(d => d.group === group);
            return members.length > 0 && <div className="roster-group" key={group}><div className="roster-group-label"><strong>{group}</strong><span>{members.length} physicians</span></div>{members.map(d => {
              const window = shiftWindow(d.bar);
              return <button className={`roster-row ${selected?.id === d.id ? "selected" : ""}`} aria-pressed={selected?.id === d.id} key={d.id} onClick={() => select(d.id)}><span className="roster-physician"><strong>{d.name}</strong><small>{d.status}</small><span className="roster-mobile-hours">{d.bar}</span></span><span className="roster-track">{window ? <span className={`roster-shift shift-${d.tone}`} style={{ left: `${window.start / 1440 * 100}%`, width: `${(window.end - window.start) / 1440 * 100}%` }}>{d.bar}{window.continues && <span aria-hidden="true"> →</span>}</span> : <span className="roster-off-label">{d.bar}</span>}</span></button>;
            })}</div>;
          })}
          {!visible.length && <p className="empty-state">No physicians match this search and filter.</p>}
        </div>
      </div>
      <div className="roster-legend"><span><i className="day" />Day shift</span><span><i className="night" />Night shift</span><span><i className="unavailable" />Unavailable</span><span><i className="offer" />Unconfirmed offer</span></div>
      <p className="roster-footnote">Offers are separate from confirmed shifts. Arrows mark shifts continuing beyond the displayed day or with no end time supplied.</p>
    </section><aside className="schedule-side roster-side" id="schedule-inspector" aria-label="Selected physician details">{selected ? <Inspector doctor={selected} /> : <section className="roster-inspector"><h2>Physician details</h2><p className="empty-state">Select a physician from the roster.</p></section>}<section className="roster-context"><h3>About this roster</h3><p>{data.date_label} · {data.now_label} ET</p><p>Current activity and scheduled hours are shown separately. Off-shift status does not establish eligibility for extra coverage.</p></section></aside></div>
  </div>;
}

function Inspector({ doctor }: { doctor: Doctor }) {
  return <section className="roster-inspector"><span className="eyebrow">Selected physician</span><div className="roster-inspector-head"><span className="roster-avatar" aria-hidden="true">{doctor.avatar}</span><div><h2>{doctor.name}</h2><span>{doctor.id}</span></div></div><span className={`roster-status status-${doctor.tone}`}>{doctor.tone === "offer" ? "Offer pending · not confirmed" : doctor.group}</span><dl><div><dt>Shift / offer hours</dt><dd>{doctor.bar}</dd></div><div><dt>Current activity</dt><dd>{doctor.status}</dd></div><div><dt>Details</dt><dd>{doctor.detail}</dd></div><div><dt>Workload</dt><dd>{doctor.workload}</dd></div><div><dt>Credentials</dt><dd>{doctor.credentialed}</dd></div></dl><a className="roster-inspector-action" href={doctor.tone === "offer" ? "#command-actions" : "#doctors"}>{doctor.tone === "offer" ? "Review offers & outcomes" : "View physician roster"}<span aria-hidden="true">→</span></a></section>;
}
