"""Pure G5/G6 replay. Time-dependent G7/G8 views live in physician.py."""
from dataclasses import dataclass, field
from datetime import datetime
from types import MappingProxyType
from typing import Mapping
from app.models import Event

STAGES = ("Received", "Triaged", "Assigned", "Provider Contacted", "Imaging Pending", "Imaging Review", "Video In Progress", "Note Pending", "Documentation", "Signed Off")
STAGE_RANK = {stage: rank for rank, stage in enumerate(STAGES)}
TRANSITIONS = {"consult_received": "Received", "consult_triaged": "Triaged", "physician_assigned": "Assigned", "imaging_requested": "Imaging Pending", "imaging_returned": "Imaging Review", "video_started": "Video In Progress", "video_ended": "Note Pending", "note_started": "Documentation", "note_signed": "Signed Off"}
CALL_STARTS = {"incoming_call_started": "incoming", "outgoing_call_started": "outgoing"}
CALL_ENDS = {"incoming_call_ended": "incoming", "outgoing_call_ended": "outgoing"}


@dataclass(frozen=True)
class ConsultState:
    consult_id: str
    hospital_id: str
    consult_type: str
    owner: str
    stage: str
    received_at: datetime
    entered_at: datetime
    history: tuple[tuple[str, datetime], ...]
    assignments: tuple[tuple[str, datetime], ...] = ()
    note_pending_since: datetime | None = None
    flags: tuple[str, ...] = ()


@dataclass(frozen=True)
class PhysicianState:
    physician_id: str
    status: str = "Available"
    camera_active: bool = False
    agent_online: bool | None = None
    calls: frozenset[tuple[str, str]] = frozenset()
    videos: frozenset[str] = frozenset()
    rings: frozenset[str] = frozenset()
    call_starts: tuple[datetime, ...] = ()
    shift_starts: tuple[datetime, ...] = ()
    last_call_end: datetime | None = None
    last_answered_at: datetime | None = None
    flags: tuple[str, ...] = ()


@dataclass(frozen=True)
class State:
    consults: Mapping[str, ConsultState]
    physicians: Mapping[str, PhysicianState] = field(default_factory=lambda: MappingProxyType({}))


def replay(events: tuple[Event, ...]) -> State:
    consults, physicians = {}, {}
    for e in sorted(events, key=lambda event: (event.event_time, event.ingested_at, event.event_id)):
        kind, cid, pid = e.event_type, e.consult_id, e.physician_id
        c = consults.get(cid)
        if kind == "consult_received":
            if c is None:
                consults[cid] = {"hospital_id": e.hospital_id or "", "consult_type": e.consult_type or "", "owner": "Unassigned", "stage": "Received", "received_at": e.event_time, "entered_at": e.event_time, "history": [("Received", e.event_time)], "assignments": [], "note_pending_since": None, "flags": set()}
            else:
                c["flags"].add("multiple_receipts")
            continue
        # Closed consults never acquire another owner or new sessions/work.
        if c and c["stage"] == "Signed Off" and kind not in {*CALL_ENDS, "video_ended"}:
            continue
        p = None
        if pid:
            p = physicians.setdefault(pid, {"status": "Available", "camera_active": False, "agent_online": None, "calls": set(), "videos": set(), "rings": set(), "call_starts": [], "shift_starts": [], "last_call_end": None, "last_answered_at": None, "flags": set()})
        session_valid = True
        if p:
            if kind == "physician_status_changed": p["status"] = e.value
            elif kind in {"camera_active", "camera_inactive"}:
                p["camera_active"] = kind == "camera_active"
                p["agent_online"] = True
            elif kind == "agent_heartbeat_lost": p["agent_online"] = False
            elif kind == "shift_started": p["shift_starts"].append(e.event_time)
            elif c:
                if kind == "incoming_call_ringing": p["rings"].add(cid)
                elif kind in CALL_STARTS:
                    key = (cid, CALL_STARTS[kind])
                    if key in p["calls"]: session_valid = False
                    else:
                        p["calls"].add(key)
                        p["call_starts"].append(e.event_time)
                        p["last_answered_at"] = e.event_time
                        if kind == "incoming_call_started": p["rings"].discard(cid)
                elif kind in CALL_ENDS:
                    key = (cid, CALL_ENDS[kind])
                    if key not in p["calls"]: session_valid = False
                    else:
                        p["calls"].remove(key)
                        p["last_call_end"] = e.event_time
                elif kind == "video_started":
                    if cid in p["videos"]: session_valid = False
                    else: p["videos"].add(cid)
                elif kind == "video_ended":
                    if cid not in p["videos"]: session_valid = False
                    else: p["videos"].remove(cid)
                if not session_valid:
                    reason = f"unmatched_session:{e.event_id}"
                    p["flags"].add(reason)
                    c["flags"].add(reason)
        if c is None or c["stage"] == "Signed Off": continue
        if kind == "physician_assigned" and pid and c["owner"] != pid:
            c["owner"] = pid
            c["assignments"].append((pid, e.event_time))
        stage = TRANSITIONS.get(kind)
        if kind in CALL_STARTS and c["stage"] == "Assigned": stage = "Provider Contacted"
        if kind in CALL_ENDS and e.value == "phone_complete": stage = "Note Pending"
        if not session_valid: stage = None
        if stage:
            if STAGE_RANK[stage] < STAGE_RANK[c["stage"]]:
                # Reassignment and follow-up sessions affect activity, not stage.
                if kind not in {"physician_assigned", *CALL_STARTS, *CALL_ENDS, "video_started", "video_ended"}:
                    c["flags"].add(f"backward_stage:{e.event_id}")
            elif stage != c["stage"]:
                c["stage"], c["entered_at"] = stage, e.event_time
                c["history"].append((stage, e.event_time))
                if stage in {"Note Pending", "Documentation"} and c["note_pending_since"] is None:
                    c["note_pending_since"] = e.event_time
    frozen_consults = {cid: ConsultState(consult_id=cid, **{**c, "history": tuple(c["history"]), "assignments": tuple(c["assignments"]), "flags": tuple(sorted(c["flags"]))}) for cid, c in consults.items()}
    frozen_physicians = {pid: PhysicianState(physician_id=pid, **{**p, "calls": frozenset(p["calls"]), "videos": frozenset(p["videos"]), "rings": frozenset(p["rings"]), "call_starts": tuple(p["call_starts"]), "shift_starts": tuple(p["shift_starts"]), "flags": tuple(sorted(p["flags"]))}) for pid, p in physicians.items()}
    return State(MappingProxyType(frozen_consults), MappingProxyType(frozen_physicians))
