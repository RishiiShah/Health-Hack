"""G9-G11, G14: consult and physician findings from published state. Pure; `now` is injected."""
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from statistics import median
from app.clock import utc
from app.engine.physician import PhysicianView, physician_view
from app.engine.replay import State
from app.references import Refs

SEVERITY = ("Critical", "Warning", "Info")
# Stage -> consult type -> (warning, critical) minutes [B p3]. "All" applies to both types.
STAGE_LIMITS = {
    "Triaged": {"All": (5, 10)},
    "Assigned": {"Stroke": (3, 8)},
    "Imaging Pending": {"Stroke": (12, 20)},
    "Imaging Review": {"Stroke": (6, 12)},
}
NOTE_LIMITS = {"Stroke": (30, 45), "General Neuro": (45, 90)}
NOTE_STAGES = {"Note Pending", "Documentation"}
PRE_NOTE_STAGES = {"Assigned", "Provider Contacted", "Imaging Pending", "Imaging Review"}
UNASSIGNED_STAGES = {"Received", "Triaged"}
SHIFT_END_WINDOW = timedelta(minutes=60)
RING_WARNING = timedelta(minutes=2)  # [A36]


@dataclass(frozen=True)
class Finding:
    kind: str
    severity: str
    what: str
    hospital_id: str | None = None
    consult_id: str | None = None
    physician_id: str | None = None
    stroke: bool = False
    waiting_since: datetime | None = None  # first contact; repeat calls never restart it
    repeat_contacts: int = 0
    why: dict = field(default_factory=dict)

    @property
    def id(self):
        return f"{self.kind}:{self.consult_id or self.physician_id or self.hospital_id}"


def consult_sla(c, now: datetime) -> tuple[str | None, timedelta]:
    """Level against the stage standard and the elapsed time it is measured on. None: no standard applies."""
    if c.stage in NOTE_STAGES and c.note_pending_since:
        return _level(now - c.note_pending_since, NOTE_LIMITS[c.consult_type]) or "none", now - c.note_pending_since
    limits = STAGE_LIMITS.get(c.stage, {})
    limit = limits.get("All") or limits.get(c.consult_type)
    return (_level(now - c.entered_at, limit) or "none") if limit else None, now - c.entered_at


def views_at(state: State, refs: Refs, now: datetime) -> dict[str, PhysicianView]:
    return {pid: physician_view(state, refs, pid, now) for pid in sorted(refs.physicians)}


def _level(age: timedelta, limits) -> str | None:
    warning, critical = limits
    if age >= timedelta(minutes=critical): return "Critical"
    if age >= timedelta(minutes=warning): return "Warning"
    return None


def _minutes(delta: timedelta) -> float:
    return round(delta.total_seconds() / 60, 1)


def owner_can_act(view: PhysicianView | None) -> bool:
    return view is not None and "off_shift" not in view.exclusion_reasons and view.derived_state not in {"Temporarily Unavailable", "Camera Active, No Session"}


def detect(state: State, refs: Refs, views: dict[str, PhysicianView], now: datetime) -> list[Finding]:
    now = utc(now)
    found = []
    open_consults = sorted((c for c in state.consults.values() if c.stage != "Signed Off"), key=lambda c: c.consult_id)
    for c in open_consults:
        stroke = c.consult_type == "Stroke"
        base = dict(hospital_id=c.hospital_id, consult_id=c.consult_id, stroke=stroke, waiting_since=c.received_at, repeat_contacts=c.repeat_contacts)
        owner = None if c.owner == "Unassigned" else c.owner
        limits = STAGE_LIMITS.get(c.stage, {})
        limit = limits.get("All") or limits.get(c.consult_type)
        if limit and (level := _level(now - c.entered_at, limit)):
            found.append(Finding("stage_breach", level, f"{c.consult_type} consult {c.stage.lower()} for {_minutes(now - c.entered_at)} min",
                                 physician_id=owner, why={"stage": c.stage, "age_min": _minutes(now - c.entered_at), "warning_min": limit[0], "critical_min": limit[1], "stage_started": c.entered_at}, **base))
        if c.stage in NOTE_STAGES and c.note_pending_since and (level := _level(now - c.note_pending_since, NOTE_LIMITS[c.consult_type])):
            limit = NOTE_LIMITS[c.consult_type]
            found.append(Finding("note_overdue", level, f"{c.consult_type} note open {_minutes(now - c.note_pending_since)} min after the call or video ended",
                                 physician_id=owner, why={"stage": c.stage, "age_min": _minutes(now - c.note_pending_since), "warning_min": limit[0], "critical_min": limit[1], "interaction_ended": c.note_pending_since}, **base))
        if owner is None and c.stage in UNASSIGNED_STAGES:
            # Severity follows the stage clock; a failed route or a repeat call raises it one level.
            level = _level(now - c.entered_at, STAGE_LIMITS["Triaged"]["All"]) if c.stage == "Triaged" else None
            index = SEVERITY.index(level or "Info") - bool(c.routing_failures or c.repeat_contacts)
            severity = SEVERITY[max(index, 0)]
            found.append(Finding("unassigned", severity, f"{c.consult_type} consult has no physician" + (f"; routing failed {c.routing_failures}x" if c.routing_failures else ""),
                                 why={"stage": c.stage, "routing_failures": c.routing_failures, "next_retry": c.last_routing_failure_at + timedelta(minutes=5) if c.last_routing_failure_at else None,
                                      "waited_min": _minutes(now - c.received_at)}, **base))
        if owner and c.stage in PRE_NOTE_STAGES and not owner_can_act(views.get(owner)):
            view = views.get(owner)
            state_label = "unknown physician" if view is None else "off shift" if "off_shift" in view.exclusion_reasons else view.derived_state
            found.append(Finding("stranded", "Critical" if stroke else "Warning", f"{c.consult_type} consult held by a physician who cannot act ({state_label})",
                                 physician_id=owner, why={"stage": c.stage, "owner_state": state_label, "waited_min": _minutes(now - c.received_at)}, **base))
        if c.ringing_since and now - c.ringing_since >= RING_WARNING:
            found.append(Finding("unanswered_ring", "Warning", f"Hospital call ringing unanswered for {_minutes(now - c.ringing_since)} min",
                                 why={"ringing_since": c.ringing_since}, **base))

    by_owner = {}
    for c in open_consults:
        by_owner.setdefault(c.owner, []).append(c)
    for pid, view in views.items():
        if view.minutes_to_shift_end is None:
            continue
        owned = by_owner.get(pid, [])
        if view.minutes_to_shift_end <= SHIFT_END_WINDOW.total_seconds() // 60 and owned:
            notes = [c.consult_id for c in owned if c.stage in NOTE_STAGES]
            work = [c.consult_id for c in owned if c.stage not in NOTE_STAGES]
            if notes:
                found.append(Finding("notes_at_shift_end", "Critical" if len(notes) >= 2 else "Warning",
                                     f"{len(notes)} open note(s), shift ends in {view.minutes_to_shift_end} min", physician_id=pid,
                                     why={"open_notes": notes, "other_open_consults": work, "minutes_to_shift_end": view.minutes_to_shift_end}))
            for c in owned:
                if c.stage in PRE_NOTE_STAGES:
                    found.append(Finding("handoff_needed", "Warning",
                                         f"Owner's shift ends in {view.minutes_to_shift_end} min with this consult at {c.stage.lower()}",
                                         hospital_id=c.hospital_id, consult_id=c.consult_id, physician_id=pid, stroke=c.consult_type == "Stroke",
                                         waiting_since=c.received_at, why={"stage": c.stage, "minutes_to_shift_end": view.minutes_to_shift_end}))
        if "off_shift" in view.exclusion_reasons:
            continue
        if "external_platform" in view.flags:
            found.append(Finding("external_platform", "Warning", "Camera active with no Synapse session: probably on another video platform",
                                 physician_id=pid, why={"self_reported": view.self_reported_status}))
        if view.desktop_agent == "Offline":
            found.append(Finding("agent_offline", "Warning" if view.routable or "ringing" in view.exclusion_reasons else "Info",
                                 "Desktop agent offline: routing assumes available, but camera state is unknown", physician_id=pid,
                                 why={"self_reported": view.self_reported_status, "derived": view.derived_state}))

    on_shift = [v for v in views.values() if "off_shift" not in v.exclusion_reasons]
    if len(on_shift) >= 3:
        mid_load = median(v.consults_this_shift for v in on_shift)
        mid_sites = median(len(v.credentialed_hospitals) for v in on_shift)
        for v in on_shift:
            # Credential-driven imbalance: light load explained by few credentialed sites, not effort.
            if v.consults_this_shift <= mid_load / 2 and len(v.credentialed_hospitals) <= mid_sites / 2:
                found.append(Finding("credential_imbalance", "Info", f"{v.consults_this_shift} consults vs median {mid_load:g}; credentialed at {len(v.credentialed_hospitals)} hospitals vs median {mid_sites:g}",
                                     physician_id=v.physician_id, why={"consults": v.consults_this_shift, "median_consults": mid_load, "sites": sorted(v.credentialed_hospitals)}))
    return found
