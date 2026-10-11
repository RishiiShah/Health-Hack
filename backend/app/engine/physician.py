"""Pure G6 classification, G7 exclusions and G8 active-shift counters."""
from bisect import bisect_left, bisect_right
from dataclasses import dataclass
from datetime import datetime, timedelta
from app.clock import utc
from app.config import DEFAULT_COOLDOWN_S
from app.engine.replay import PhysicianState, State
from app.references import Refs


@dataclass(frozen=True)
class PhysicianView:
    physician_id: str
    derived_state: str
    self_reported_status: str
    desktop_agent: str
    routable: bool
    exclusion_reasons: tuple[str, ...]
    flags: tuple[str, ...]
    consults_this_shift: int
    calls_this_shift: int
    open_consults: int
    minutes_to_shift_end: int | None
    credentialed_hospitals: frozenset[str]
    last_answered_at: datetime | None


def physician_view(state: State, refs: Refs, physician_id: str, as_of: datetime,
                   cooldown_s: int = DEFAULT_COOLDOWN_S) -> PhysicianView:
    as_of = utc(as_of)
    if cooldown_s < 0: raise ValueError("cooldown must be nonnegative")
    reference = refs.physicians[physician_id]
    p = state.physicians.get(physician_id, PhysicianState(physician_id))
    owned = tuple(c for c in state.consults.values() if c.owner == physician_id and c.stage != "Signed Off")
    flags = set(p.flags)
    if p.agent_online is not True: flags.add("unverified")
    if p.videos: derived, busy = "Video Consult", True
    elif p.calls: derived, busy = "Hospital Call", True
    elif p.status == "Temporarily Unavailable":
        derived, busy = "Temporarily Unavailable", True
        if owned: flags.add("stranded_consults")
    elif p.camera_active and p.status != "In Meeting":
        derived, busy = "Camera Active, No Session", True
        flags.add("external_platform")
    elif p.camera_active and p.status == "In Meeting": derived, busy = "Available (meeting)", False
    elif any(c.stage == "Documentation" for c in owned): derived, busy = "Documentation", False
    else: derived, busy = "Available", False
    shift = next((s for s in reference.shifts if s.start <= as_of < s.end), None)
    reasons = []
    if shift is None: reasons.append("off_shift")
    if busy: reasons.append("unavailable" if derived == "Temporarily Unavailable" else "busy")
    if p.rings: reasons.append("ringing")
    if p.last_call_end is not None and as_of - p.last_call_end < timedelta(seconds=cooldown_s): reasons.append("cooldown")
    assigned = {c.consult_id for c in state.consults.values() if shift and any(pid == physician_id and shift.start <= at < shift.end and at <= as_of for pid, at in c.assignments)}
    calls = 0 if shift is None else bisect_right(p.call_starts, as_of) - bisect_left(p.call_starts, shift.start)
    return PhysicianView(physician_id, derived, p.status,
                         "Online" if p.agent_online is True else "Offline" if p.agent_online is False else "Unknown",
                         not reasons, tuple(reasons), tuple(sorted(flags)), len(assigned), calls,
                         len(owned), int((shift.end - as_of).total_seconds() // 60) if shift else None,
                         refs.credentials[physician_id], p.last_answered_at)


def eligible_for_hospital(view: PhysicianView, hospital_id: str) -> bool:
    return view.routable and hospital_id in view.credentialed_hospitals


def fixture_state_label(p: PhysicianState, view: PhysicianView) -> str:
    """Display-only adapter; canonical state remains stable for the team."""
    if view.derived_state == "Video Consult": return "Video Consult In Progress"
    if view.derived_state == "Hospital Call":
        directions = {direction for _, direction in p.calls}
        if len(directions) == 1: return f"{next(iter(directions)).title()} Hospital Call"
        return "Hospital Call"
    return {"Camera Active, No Session": "Camera Active - No Synapse Session", "Documentation": "Documentation / Note"}.get(view.derived_state, view.derived_state)
