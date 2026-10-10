from dataclasses import dataclass
from datetime import datetime
import json
from threading import Lock
from app.db import EventDatabase
from app.models import Event, EventInput
from app.engine.replay import State, replay
from app.clock import Clock, ServerReceiptClock

@dataclass(frozen=True)
class Published:
    state: State
    revision: int
    as_of: datetime
    event_count: int

class MutationCoordinator:
    """Synchronous serialized writer. API callers offload this work from the event loop."""
    def __init__(self, db: EventDatabase, clock: Clock, late_lag_s=60, receipt_clock=None):
        self.db, self.clock, self.late_lag_s = db, clock, late_lag_s
        self.receipt_clock = receipt_clock or ServerReceiptClock()
        self.lock = Lock()
        events = db.events()
        initial_as_of = clock.now()
        visible = tuple(e for e in events if e.event_time <= initial_as_of)
        self._visible_ids = tuple(e.event_id for e in visible)
        self.published = Published(replay(visible), db.revision, initial_as_of, len(events))
        self.watermark = max((e.event_time for e in events), default=None)

    def ingest(self, rows: list[EventInput]) -> dict:
        with self.lock:
            as_of = self.clock.now()
            received_at = self.receipt_clock.now()
            accepted, quarantined = [], []
            stored_events = self.db.events()
            existing = {e.event_id: e for e in stored_events}
            seen: dict[str, Event] = {}
            duplicate = conflicts = 0
            for row in rows:
                try:
                    row.validate_semantics()
                    canonical = row.model_dump(mode="json")
                    canonical["received_at"] = received_at.isoformat()
                    canonical["ingested_at"] = (row.ingested_at or received_at).isoformat()
                    canonical["raw_json"] = row.raw_json or row.model_dump(mode="json")
                    event = Event(**canonical)
                except Exception as exc:
                    quarantined.append((str(exc), row.model_dump_json()))
                    continue
                prior = seen.get(event.event_id) or existing.get(event.event_id)
                if prior:
                    fields = ("event_id", "event_time", "event_type", "consult_id", "physician_id", "hospital_id", "consult_type", "value")
                    if any(getattr(prior, k) != getattr(event, k) for k in fields):
                        conflicts += 1
                        quarantined.append((f"G2 conflicting payload for event_id {event.event_id}", json.dumps(event.raw_json, sort_keys=True)))
                    else:
                        duplicate += 1
                    continue
                seen[event.event_id] = event
                accepted.append(event)
            receipts: dict[str, datetime] = {}
            for e in (*stored_events, *accepted):
                if e.event_type == "consult_received" and e.consult_id:
                    receipts[e.consult_id] = min(receipts.get(e.consult_id, e.event_time), e.event_time)
            unresolved = [e for e in accepted if e.consult_id and e.event_type != "consult_received" and
                          (e.consult_id not in receipts or e.event_time < receipts[e.consult_id])]
            for event in unresolved:
                reason = "G4 event precedes consult receipt" if event.consult_id in receipts else "G4 unresolved consult; orphan holding is not implemented"
                quarantined.append((reason, json.dumps(event.raw_json, sort_keys=True)))
            unresolved_ids = {e.event_id for e in unresolved}
            accepted = [e for e in accepted if e.event_id not in unresolved_ids]
            pending = sum(e.event_time > as_of for e in accepted)
            reordered = late = 0
            watermark = self.watermark
            for event in accepted:
                if watermark and event.event_time < watermark:
                    reordered += 1
                    if (watermark - event.event_time).total_seconds() > self.late_lag_s: late += 1
                watermark = max(watermark, event.event_time) if watermark else event.event_time
            candidate = (*stored_events, *accepted)
            candidate_state = replay(tuple(e for e in candidate if e.event_time <= as_of))
            revision = self.db.commit_batch(accepted, quarantined, received_at.isoformat())
            self.watermark = watermark
            self._visible_ids = tuple(e.event_id for e in sorted(candidate, key=lambda e:(e.event_time,e.ingested_at,e.event_id)) if e.event_time <= as_of)
            self.published = Published(candidate_state, revision, as_of, len(candidate))
            return {"accepted":len(accepted), "pending_future":pending, "duplicates":duplicate, "conflicts":conflicts,
                    "reordered":reordered, "late":late, "unresolved":len(unresolved), "quarantined":[{"reason":r} for r,_ in quarantined], "revision":revision}

    def current_publication(self):
        """Refresh time-dependent state from one clock sample; fixed clocks stay fixed."""
        with self.lock:
            as_of = self.clock.now()
            all_events = self.db.events()
            visible = tuple(e for e in all_events if e.event_time <= as_of)
            visible_ids = tuple(e.event_id for e in visible)
            state = self.published.state if visible_ids == self._visible_ids else replay(visible)
            self._visible_ids = visible_ids
            self.published = Published(state, self.db.revision, as_of, len(all_events))
            return self.published
