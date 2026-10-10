from dataclasses import dataclass
from datetime import datetime
from types import MappingProxyType
from typing import Mapping
from app.models import Event

STAGES = ["Received", "Triaged", "Assigned", "Provider Contacted", "Imaging Pending", "Imaging Review", "Video In Progress", "Note Pending", "Documentation", "Signed Off"]

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

@dataclass(frozen=True)
class State:
    consults: Mapping[str, ConsultState]


def replay(events: tuple[Event, ...]) -> State:
    consults: dict[str, dict] = {}
    transitions = {"consult_received":"Received", "consult_triaged":"Triaged", "physician_assigned":"Assigned", "imaging_requested":"Imaging Pending", "imaging_returned":"Imaging Review", "video_started":"Video In Progress", "video_ended":"Note Pending", "note_started":"Documentation", "note_signed":"Signed Off"}
    ordered = sorted(events, key=lambda e: (e.event_time, e.ingested_at, e.event_id))
    for e in ordered:
        if not e.consult_id: continue
        c = consults.get(e.consult_id)
        if e.event_type == "consult_received":
            if c is None:
                consults[e.consult_id] = {"hospital_id":e.hospital_id or "", "consult_type":e.consult_type or "", "owner":"Unassigned", "stage":"Received", "received_at":e.event_time, "entered_at":e.event_time, "history":[("Received", e.event_time)]}
            continue
        if c is None or c["stage"] == "Signed Off": continue
        if e.event_type == "physician_assigned" and e.physician_id: c["owner"] = e.physician_id
        stage = transitions.get(e.event_type)
        if e.event_type in {"incoming_call_started", "outgoing_call_started"} and c["stage"] == "Assigned": stage = "Provider Contacted"
        if e.event_type in {"incoming_call_ended", "outgoing_call_ended"} and e.value == "phone_complete": stage = "Note Pending"
        if stage and STAGES.index(stage) > STAGES.index(c["stage"]):
            c["stage"], c["entered_at"] = stage, e.event_time
            c["history"].append((stage, e.event_time))
    result = {key: ConsultState(consult_id=key, **{**value, "history":tuple(value["history"])}) for key,value in consults.items()}
    return State(MappingProxyType(result))
