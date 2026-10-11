"""G1–G4 and atomic publication; one writer owns all domain mutations."""
from bisect import bisect_right
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import json
from threading import Lock
from types import MappingProxyType
from typing import Mapping
from app.config import DEFAULT_LATE_LAG_S, DEFAULT_ORPHAN_HOLD_S
from app.db import EventDatabase, StaleRevision
from app.models import Event, EventInput
from app.engine.replay import State, replay
from app.clock import AUTO_REPLAY_AFTER_S, Clock, ServerReceiptClock, FixedClock, AnchoredClock, saved_clock, restore_clock
from app.references import Refs
from app.ingest.pipeline import normalize_row

SEMANTIC_FIELDS = ("event_id", "event_time", "event_type", "consult_id", "physician_id", "hospital_id", "consult_type", "value")
EMPTY_STATS = {"accepted": 0, "duplicates": 0, "conflicts": 0, "reordered": 0, "late": 0, "rejected": 0, "expired_orphans": 0, "max_reorder_lag_s": 0.0, "max_delivery_lag_s": 0.0, "history_complete": True, "rows_received": 0, "counts_exact": True}


@dataclass(frozen=True)
class Published:
    state: State
    revision: int
    as_of: datetime
    event_count: int
    held_orphans: int = 0
    stats: Mapping[str, int | float] = field(default_factory=lambda: MappingProxyType({}))
    reference_revision: int = 0
    refs: Refs | None = None
    unresolved_history: tuple[str, ...] = ()


class MutationCoordinator:
    """Synchronous domain work. P1 schedules sweep() using server time."""
    def __init__(self, db: EventDatabase, clock: Clock, late_lag_s=DEFAULT_LATE_LAG_S, receipt_clock=None, *, refs: Refs | None = None, orphan_hold_s=DEFAULT_ORPHAN_HOLD_S, reference_source=None, references_locked=False, auto_clock=False):
        if late_lag_s < 0 or orphan_hold_s <= 0: raise ValueError("invalid ingest thresholds")
        self.db, self.clock, self.late_lag_s = db, clock, late_lag_s
        self.auto_clock = auto_clock
        self.orphan_hold_s = orphan_hold_s
        self.receipt_clock = receipt_clock or ServerReceiptClock()
        self.lock = Lock()
        self.references_locked = references_locked
        self._load(refs, reference_source)

    def _load(self, refs=None, reference_source=None):
        db, clock = self.db, self.clock
        saved_refs = db.metadata("references")
        if saved_refs:
            self.refs = Refs.from_payload(saved_refs["payload"])
            if refs is not None and refs.payload() != self.refs.payload():
                raise ValueError("activate changed references through the coordinator")
            self.reference_revision = saved_refs["revision"]
            if reference_source and not saved_refs.get("source"):
                db.commit_batch([], [], references={**saved_refs, "source": reference_source})
        else:
            self.refs, self.reference_revision = refs, int(refs is not None)
            if refs is not None:
                db.commit_batch([], [], references={"revision": self.reference_revision, "payload": refs.payload(),
                                                    **({"source": reference_source} if reference_source else {})})
        events = db.events()
        self._holds = db.holds()
        stored_stats = db.metadata("ingest_stats", {})
        self._stats = {**EMPTY_STATS, **stored_stats}
        if "rows_received" not in stored_stats and (stored_stats or events or self._holds):
            self._stats["rows_received"] = stored_stats.get("accepted", len(events)) + stored_stats.get("duplicates", 0) + stored_stats.get("rejected", 0) + sum(not expired for _, _, expired in self._holds.values())
            self._stats["counts_exact"] = False
        # Earlier foundation databases did not persist quality metrics.
        if db.metadata("ingest_stats") is None:
            self._stats["accepted"] = len(events)
            self._stats["history_complete"] = not events
        as_of = clock.now()
        self._events = events
        self._unresolved_history = self._unknown_history(events, self.refs)
        self._visible_count = bisect_right(events, as_of, key=lambda e: e.event_time)
        self.published = self._publication(replay(events[:self._visible_count]), db.revision, as_of)
        self.watermark = max((e.event_time for e in events), default=None)

    def _publication(self, state, revision, as_of):
        return Published(state, revision, as_of, len(self._events), sum(not expired for _, _, expired in self._holds.values()), MappingProxyType(dict(self._stats)), self.reference_revision, self.refs, self._unresolved_history)

    def _known(self, event, refs):
        return refs is None or ((not event.physician_id or event.physician_id in refs.physicians) and (not event.hospital_id or event.hospital_id in refs.hospitals))

    def _unknown_history(self, events, refs):
        return tuple(e.event_id for e in events if not self._known(e, refs))

    def ingest(self, rows: list[EventInput]) -> dict:
        with self.lock:
            return self._mutate(rows)

    def ingest_raw(self, rows: list[dict], adapter: str = "canonical-v1", *, advance_clock=False, upload=None, refs=None, source=None) -> dict:
        """Normalize each row independently; G1 rejects share the durable transaction. With `refs`, the rows start a
        fresh dataset generation on that reference kit instead of appending: the switch and the events commit together."""
        if adapter not in {"canonical-v1", "sample-csv-v1"}:
            raise ValueError(f"unsupported adapter: {adapter}")
        with self.lock:
            normalized, rejected, records = [], [], []
            for index, raw in enumerate(rows, 2):
                result = {"row_number": index, "event_id": raw.get("event_id"), "status": "pending", "reason": None}
                records.append(result)
                try:
                    normalized.append(normalize_row(raw, adapter))
                except ValueError as exc:
                    result.update(status="quarantined", reason=str(exc))
                    rejected.append((str(exc), json.dumps(raw, sort_keys=True)))
            return self._mutate(normalized, refs, rejected, source, records=records, advance_clock=advance_clock, upload=upload, fresh=refs is not None)

    def activate_references(self, refs: Refs, source: dict | None = None) -> dict:
        """P1 activation hook: validated reference snapshot and releases commit together. `source` (the uploaded
        files and service date) is stored in the same transaction so a restart can rebuild the operational tables."""
        with self.lock:
            return self._mutate([], refs, source=source)

    def _mutate(self, rows, refs=None, rejected=(), source=None, *, records=(), advance_clock=False, upload=None, fresh=False):
        try:
            return self._mutate_once(rows, refs, rejected, source, records=records, advance_clock=advance_clock, upload=upload, fresh=fresh)
        except StaleRevision:
            # Another instance wrote (e.g. a deploy overlap): reload the durable log, then retry once.
            stored_clock = self.db.metadata("clock")
            if stored_clock:
                self.clock = restore_clock(stored_clock, self.receipt_clock.now())
            self._load()
            return self._mutate_once(rows, refs, rejected, source, records=records, advance_clock=advance_clock, upload=upload, fresh=fresh)

    def _mutate_once(self, rows, refs=None, rejected=(), source=None, *, records=(), advance_clock=False, upload=None, fresh=False):
        if refs is not None and self.references_locked and self.refs is not None and not fresh:
            previous = (self.db.metadata("references") or {}).get("source")
            if refs.payload() != self.refs.payload() or (previous and (not source or
                    (previous["files"], previous.get("service_date")) != (source["files"], source.get("service_date")))):
                raise ValueError("Reference data is fixed; replacement is not permitted")
        as_of, received_at = self.clock.now(), self.receipt_clock.now()
        clock_before = as_of
        results = [dict(r) for r in records]
        normalized_results = [r for r in results if r["status"] == "pending"] if records else [{} for _ in rows]
        active_refs = refs if refs is not None else self.refs
        stored = () if fresh else self._events  # a kit switch starts an empty stream
        holds, stats = ({}, dict(EMPTY_STATS)) if fresh else (dict(self._holds), dict(self._stats))
        prior_hold_ids = set(holds)
        quarantined, new_events = list(rejected), []
        duplicate = conflicts = expired_count = 0
        seen = {e.event_id: e for e in stored}
        seen.update({eid: e for eid, (e, _, _) in holds.items()})
        for row, result in zip(rows, normalized_results):
            try:
                row.validate_semantics()
                canonical = row.model_dump(mode="json")
                canonical.update(received_at=received_at.isoformat(), ingested_at=(row.ingested_at or received_at).isoformat(), raw_json=row.raw_json if row.raw_json is not None else row.model_dump(mode="json"))
                if upload:
                    canonical["source"] = "upload:" + upload["batch_id"]
                event = Event(**canonical)
            except ValueError as exc:
                result.update(status="quarantined", reason=str(exc))
                quarantined.append((str(exc), row.model_dump_json()))
                continue
            prior = seen.get(event.event_id)
            if prior:
                if any(getattr(prior, k) != getattr(event, k) for k in SEMANTIC_FIELDS):
                    conflicts += 1
                    result.update(status="conflict", reason=f"G2 conflicting payload for event_id {event.event_id}")
                    quarantined.append((f"G2 conflicting payload for event_id {event.event_id}", json.dumps(event.raw_json, sort_keys=True)))
                else:
                    duplicate += 1
                    result.update(status="duplicate", reason="Event already recorded with the same payload")
                continue
            seen[event.event_id] = event
            new_events.append(event)
        for eid, (event, deadline, expired) in tuple(holds.items()):
            if not expired and received_at >= deadline:
                holds[eid] = (event, deadline, True)
                expired_count += 1
                quarantined.append((f"G4 expired orphan {eid}", json.dumps(event.raw_json, sort_keys=True)))
        released_candidates = sorted((e for e, _, expired in holds.values() if not expired), key=lambda e: (e.received_at, e.event_time, e.event_id))
        candidates = new_events + released_candidates
        receipts = {}
        for e in (*stored, *candidates):
            if e.event_type == "consult_received" and self._known(e, active_refs):
                receipts[e.consult_id] = min(receipts.get(e.consult_id, e.event_time), e.event_time)
        accepted, causal = [], 0
        pending_results = {r["event_id"]: r for r in results if r["status"] == "pending"}
        for e in candidates:
            if e.consult_id and e.event_type != "consult_received" and e.consult_id in receipts and e.event_time < receipts[e.consult_id]:
                causal += 1
                holds.pop(e.event_id, None)
                quarantined.append((f"G4 event precedes consult receipt: {e.event_id}", json.dumps(e.raw_json, sort_keys=True)))
                if e.event_id in pending_results:
                    pending_results[e.event_id].update(status="quarantined", reason=f"Event precedes consult_received for {e.consult_id}")
            elif not self._known(e, active_refs) or (e.consult_id and e.event_type != "consult_received" and e.consult_id not in receipts):
                holds.setdefault(e.event_id, (e, received_at + timedelta(seconds=self.orphan_hold_s), False))
                if e.event_id in pending_results:
                    missing = []
                    if active_refs and e.hospital_id and e.hospital_id not in active_refs.hospitals:
                        missing.append(f"Unknown hospital {e.hospital_id} in the fixed reference kit")
                    if active_refs and e.physician_id and e.physician_id not in active_refs.physicians:
                        missing.append(f"Unknown physician {e.physician_id} in the fixed reference kit")
                    if e.consult_id and e.event_type != "consult_received" and e.consult_id not in receipts:
                        missing.append(f"Missing consult_received for {e.consult_id}")
                    pending_results[e.event_id].update(status="held", reason="; ".join(missing), expires_at=holds[e.event_id][1].isoformat())
            else:
                accepted.append(e)
                holds.pop(e.event_id, None)
                if e.event_id in pending_results:
                    pending_results[e.event_id].update(status="accepted")
        latest = max((e.event_time for e in accepted), default=None)
        next_clock, clock_payload, clock_warning = self.clock, None, None
        # Auto mode on an empty stream chose wall time without data; old data now picks its replay clock, as at startup.
        auto_replay = (self.auto_clock and self.clock.mode == "wall" and not stored and latest
                       and abs((latest - as_of).total_seconds()) > AUTO_REPLAY_AFTER_S)
        if (fresh or auto_replay) and latest:  # a new dataset's clock starts at its latest event, in either direction
            next_clock = FixedClock(latest) if self.clock.mode == "fixed" else AnchoredClock(latest)
            as_of = next_clock.now()
            clock_payload = saved_clock(next_clock, received_at)
        elif advance_clock and latest and latest > as_of:
            if latest - as_of > timedelta(hours=24):
                clock_warning = "Accepted events are more than 24 hours ahead. Check their dates before explicitly advancing the test clock; these events remain pending."
            else:
                next_clock = FixedClock(latest) if self.clock.mode == "fixed" else AnchoredClock(latest)
                as_of = next_clock.now()
                clock_payload = saved_clock(next_clock, received_at)
        reordered = late = 0
        watermark = None if fresh else self.watermark
        for event in accepted:
            lag = max(0.0, (watermark - event.event_time).total_seconds()) if watermark else 0.0
            if lag:
                reordered += 1
                late += lag > self.late_lag_s
            stats["max_reorder_lag_s"] = max(stats["max_reorder_lag_s"], lag)
            stats["max_delivery_lag_s"] = max(stats["max_delivery_lag_s"], (event.ingested_at - event.event_time).total_seconds())
            watermark = max(watermark, event.event_time) if watermark else event.event_time
        for key, count in (("accepted", len(accepted)), ("duplicates", duplicate), ("conflicts", conflicts), ("reordered", reordered), ("late", late), ("rejected", len(quarantined)), ("expired_orphans", expired_count)):
            stats[key] += count
        stats["rows_received"] += len(rows) + len(rejected)
        candidate = tuple(sorted((*stored, *accepted), key=lambda e: (e.event_time, e.ingested_at, e.event_id)))
        visible_count = bisect_right(candidate, as_of, key=lambda e: e.event_time)
        state = replay(candidate[:visible_count]) if accepted or fresh or visible_count != self._visible_count else self.published.state
        unresolved_history = self._unknown_history(candidate, active_refs) if refs is not None else self._unresolved_history
        ref_revision = self.reference_revision + int(refs is not None and (self.refs is None or refs.payload() != self.refs.payload()))
        saved_refs = {"revision": ref_revision, "payload": active_refs.payload(), **({"source": source} if source else {})} if refs is not None else None
        held_count = sum(not expired for _, _, expired in holds.values())
        report = {"accepted": len(accepted), "released_orphans": sum(e.event_id in prior_hold_ids for e in accepted),
                  "held_orphans": held_count, "expired_orphans": expired_count,
                  "pending_future": sum(e.event_time > as_of for e in accepted), "duplicates": duplicate, "conflicts": conflicts,
                  "reordered": reordered, "late": late, "unresolved": held_count + causal,
                  "quarantined": [{"reason": reason} for reason, _ in quarantined], "revision": self.published.revision + 1,
                  "row_results": results, "latest_event_time": latest.isoformat() if latest else None}
        if clock_payload:
            report["clock_advanced_to"] = as_of.isoformat()
        if clock_warning:
            report["clock_warning"] = clock_warning
        if upload:
            report["batch_id"] = upload["batch_id"]
            upload = {**upload, "received_at": received_at.isoformat(), "clock_before": clock_before.isoformat(),
                      "clock_after": as_of.isoformat(), "consult_ids": sorted({r.consult_id for r in rows if r.consult_id}), "report": report}
        revision = self.db.commit_batch(accepted, quarantined, received_at, holds=holds, stats=stats, references=saved_refs, clock=clock_payload,
                                        upload=upload, expected_revision=self.published.revision, new_generation=fresh)
        self._events, self._holds, self._stats = candidate, holds, stats
        self._visible_count, self.watermark = visible_count, watermark
        self.refs, self.reference_revision = active_refs, ref_revision
        self._unresolved_history = unresolved_history
        self.clock = next_clock
        self.published = self._publication(state, revision, as_of)
        return report

    def _sweep_due(self):
        now = self.receipt_clock.now()
        if any(not expired and now >= deadline for _, deadline, expired in self._holds.values()):
            self._mutate([])

    def sweep(self):
        with self.lock:
            self._sweep_due()
            return self.published

    def current_publication(self):
        with self.lock:
            self._sweep_due()
            as_of = self.clock.now()
            visible_count = bisect_right(self._events, as_of, key=lambda e: e.event_time)
            state = self.published.state if visible_count == self._visible_count else replay(self._events[:visible_count])
            self._visible_count = visible_count
            self.published = self._publication(state, self.published.revision, as_of)
            return self.published

    def visible_events(self):
        """Events at or before the clock, as of the latest publication (the input of observed service times)."""
        with self.lock:
            return self._events[:self._visible_count]

    def set_clock(self, clock: Clock):
        """Commit the override before replacing the serving clock. Offers still refuse rewound commands."""
        with self.lock:
            payload = saved_clock(clock, self.receipt_clock.now())
            try:
                revision = self.db.commit_batch([], [], clock=payload, expected_revision=self.published.revision)
            except StaleRevision:
                self._load()
                revision = self.db.commit_batch([], [], clock=payload, expected_revision=self.published.revision)
            self.clock = clock
            self.published = self._publication(self.published.state, revision, self.published.as_of)

    def reset(self):
        """Admin reset: a new, empty dataset generation (old generations stay in the database), same references."""
        with self.lock:
            self.db.reset()
            self._load()
