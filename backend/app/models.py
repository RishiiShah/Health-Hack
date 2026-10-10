from datetime import datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict, field_validator
from app.clock import utc

EVENT_TYPES = {
    "consult_received", "consult_triaged", "physician_assigned", "incoming_call_ringing",
    "incoming_call_started", "incoming_call_ended", "outgoing_call_started", "outgoing_call_ended",
    "imaging_requested", "imaging_returned", "video_started", "video_ended", "note_started", "note_signed",
    "routing_attempt_failed", "physician_status_changed", "camera_active", "camera_inactive",
    "agent_heartbeat_lost", "shift_started",
}
PHYSICIAN_ONLY = {"physician_status_changed", "camera_active", "camera_inactive", "agent_heartbeat_lost", "shift_started"}
PHYSICIAN_REQUIRED = PHYSICIAN_ONLY | {"physician_assigned", "incoming_call_ringing", "incoming_call_started", "incoming_call_ended", "outgoing_call_started", "outgoing_call_ended", "video_started", "video_ended", "note_started", "note_signed"}


class Event(BaseModel):
    model_config = ConfigDict(frozen=True)
    event_id: str
    event_time: datetime
    ingested_at: datetime
    event_type: str
    consult_id: str | None = None
    physician_id: str | None = None
    hospital_id: str | None = None
    consult_type: str | None = None
    value: str | None = None
    source: str = "api"
    received_at: datetime
    time_offset: str | None = None
    raw_json: dict
    adapter_version: str = "canonical-v1"

    @field_validator("event_time", "ingested_at", "received_at")
    @classmethod
    def aware_utc(cls, value): return utc(value)


class EventInput(BaseModel):
    event_id: str
    event_time: datetime
    ingested_at: datetime | None = None
    consult_id: str | None = None
    event_type: str
    physician_id: str | None = None
    hospital_id: str | None = None
    consult_type: str | None = None
    value: str | None = None
    source: str = "api"
    adapter_version: str = "canonical-v1"
    raw_json: dict | None = None

    @field_validator("event_time", "ingested_at")
    @classmethod
    def aware(cls, value): return utc(value) if value else value

    def validate_semantics(self):
        if self.event_type not in EVENT_TYPES: raise ValueError("unknown event_type")
        if self.event_type not in PHYSICIAN_ONLY and not self.consult_id: raise ValueError("consult_id is required")
        if self.event_type in PHYSICIAN_ONLY and self.consult_id: raise ValueError("consult_id is not allowed for physician-only events")
        if self.event_type in PHYSICIAN_REQUIRED and not self.physician_id: raise ValueError("physician_id is required")
        if self.event_type == "consult_received" and (not self.hospital_id or self.consult_type not in {"Stroke", "General Neuro"}):
            raise ValueError("consult_received requires hospital_id and a supported consult_type")
        if self.event_type == "physician_status_changed" and self.value not in {"Available", "In Meeting", "Temporarily Unavailable"}: raise ValueError("unsupported physician status")
        if self.event_type in {"incoming_call_ended", "outgoing_call_ended"} and self.value not in {"phone_complete", "continue"}: raise ValueError("call end requires phone_complete or continue")
        if self.event_type == "routing_attempt_failed" and self.value != "retry_in_5m": raise ValueError("routing failure requires retry_in_5m")


class IngestReport(BaseModel):
    accepted: int = 0
    pending_future: int = 0
    duplicates: int = 0
    conflicts: int = 0
    reordered: int = 0
    late: int = 0
    quarantined: list[dict] = []
    revision: int
