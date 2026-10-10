from datetime import datetime, timezone
from app.clock import FixedClock
from app.coordinator import MutationCoordinator
from app.db import EventDatabase
from app.engine.replay import replay
from app.models import Event, EventInput
from app.fixture import load_fixture
from fastapi.testclient import TestClient
from pathlib import Path
import pytest
from app.main import create_app

def t(value): return datetime.fromisoformat(value).replace(tzinfo=timezone.utc)

def event(eid, kind, time, consult="C1", **kwargs):
    return Event(event_id=eid, event_time=t(time), ingested_at=t(time), received_at=t(time), event_type=kind,
        consult_id=consult, raw_json={}, **kwargs)

def test_replay_stage_is_monotonic_and_assignment_is_current_owner():
    state = replay((event("1","consult_received","2026-03-17T12:00:00", hospital_id="H", consult_type="Stroke"),
        event("2","physician_assigned","2026-03-17T12:01:00", physician_id="P1"),
        event("3","imaging_requested","2026-03-17T12:02:00"), event("4","consult_triaged","2026-03-17T12:03:00")))
    c = state.consults["C1"]
    assert c.stage == "Imaging Pending" and c.owner == "P1"
    assert len(c.history) == 3

def test_coordinator_deduplicates_and_publishes_after_durable_commit(db_url):
    db = EventDatabase(db_url)
    coordinator = MutationCoordinator(db, FixedClock(t("2026-03-17T13:00:00")))
    row = EventInput(event_id="1", event_time=t("2026-03-17T12:00:00"), event_type="consult_received", consult_id="C1", hospital_id="H", consult_type="Stroke")
    report = coordinator.ingest([row, row])
    assert report["accepted"] == 1 and report["duplicates"] == 1
    assert coordinator.published.revision == report["revision"] == db.revision
    assert coordinator.published.state.consults["C1"].stage == "Received"

def test_future_event_is_durable_but_not_replayed_until_clock_reaches_it(db_url):
    db = EventDatabase(db_url)
    coordinator = MutationCoordinator(db, FixedClock(t("2026-03-17T12:00:00")))
    row = EventInput(event_id="f", event_time=t("2026-03-17T12:01:00"), event_type="consult_received", consult_id="C2", hospital_id="H", consult_type="Stroke")
    report = coordinator.ingest([row])
    assert report["pending_future"] == 1
    assert "C2" not in coordinator.published.state.consults
    assert len(db.events()) == 1

@pytest.mark.skipif(not (Path(__file__).resolve().parents[2] / "data" / "event_stream.csv").exists(), reason="local source fixture is not part of the repository")
def test_all_base_fixture_rows_have_explicit_adapter_metadata_and_validate(db_url):
    root = Path(__file__).resolve().parents[2]
    rows = load_fixture(root / "data" / "event_stream.csv")
    assert len(rows) == 1164
    assert all(r.source == "base" and r.adapter_version == "sample-csv-v1" for r in rows)
    assert sum(r.event_id == "EVT-00529" for r in rows) == 2
    db = EventDatabase(db_url)
    coordinator = MutationCoordinator(db, FixedClock(t("2026-03-17T22:20:00")))
    report = coordinator.ingest(rows)
    assert report["accepted"] == 1163 and report["duplicates"] == 1
    assert report["conflicts"] == 0 and report["reordered"] == 23 and report["late"] == 1
    assert len(coordinator.published.state.consults) == 103
    assert sum(c.stage != "Signed Off" for c in coordinator.published.state.consults.values()) == 18

def test_api_contract_reports_incomplete_capabilities(db_url):
    api = create_app(db_url, FixedClock(t("2026-03-17T13:00:00")))
    with TestClient(api) as client:
        ready = client.get("/ready").json()
        snapshot = client.get("/snapshot").json()
    assert ready["capabilities"]["orphan_holding"] is True
    assert snapshot["physicians"]["supported"] is False
    assert snapshot["coverage"]["supported"] is False

def test_failed_commit_keeps_published_state_unchanged(db_url):
    db = EventDatabase(db_url)
    coordinator = MutationCoordinator(db, FixedClock(t("2026-03-17T13:00:00")))
    before = coordinator.published
    def fail(*args, **kwargs): raise RuntimeError("disk unavailable")
    db.commit_batch = fail
    row = EventInput(event_id="1", event_time=t("2026-03-17T12:00:00"), event_type="consult_received", consult_id="C1", hospital_id="H", consult_type="Stroke")
    try:
        coordinator.ingest([row])
    except RuntimeError:
        pass
    assert coordinator.published is before
    assert not coordinator.current_publication().state.consults
    assert db.revision == before.revision

def test_future_event_becomes_visible_when_simulation_clock_advances(db_url):
    class MutableClock:
        mode = "fixed"
        value = t("2026-03-17T12:00:00")
        def now(self): return self.value
    clock = MutableClock()
    db = EventDatabase(db_url)
    coordinator = MutationCoordinator(db, clock)
    row = EventInput(event_id="future", event_time=t("2026-03-17T12:01:00"), event_type="consult_received", consult_id="C3", hospital_id="H", consult_type="Stroke")
    assert coordinator.ingest([row])["pending_future"] == 1
    clock.value = t("2026-03-17T12:02:00")
    assert "C3" in coordinator.current_publication().state.consults

def test_duplicate_source_and_ingestion_metadata_do_not_create_semantic_conflict(db_url):
    db = EventDatabase(db_url)
    coordinator = MutationCoordinator(db, FixedClock(t("2026-03-17T13:00:00")))
    first = EventInput(event_id="same", event_time=t("2026-03-17T12:00:00"), ingested_at=t("2026-03-17T12:00:01"), event_type="consult_received", consult_id="C4", hospital_id="H", consult_type="Stroke", source="base", adapter_version="sample-csv-v1", raw_json={"description":"fixture"})
    second = first.model_copy(update={"ingested_at":t("2026-03-17T12:00:05"), "source":"api", "raw_json":{"different_delivery":True}})
    report = coordinator.ingest([first, second])
    assert report["accepted"] == 1 and report["duplicates"] == 1 and report["conflicts"] == 0

def test_held_orphan_timestamp_does_not_advance_event_watermark(db_url):
    db = EventDatabase(db_url)
    coordinator = MutationCoordinator(db, FixedClock(t("2026-03-17T15:00:00")))
    orphan = EventInput(event_id="orphan", event_time=t("2026-03-17T14:00:00"), event_type="consult_triaged", consult_id="missing")
    report = coordinator.ingest([orphan])
    assert report["accepted"] == 0 and report["held_orphans"] == 1
    assert not report["quarantined"]
    receipt = EventInput(event_id="receipt", event_time=t("2026-03-17T13:00:00"), event_type="consult_received", consult_id="missing", hospital_id="H", consult_type="Stroke")
    assert coordinator.ingest([receipt])["reordered"] == 0

def test_event_before_receipt_is_causally_quarantined(db_url):
    db = EventDatabase(db_url)
    coordinator = MutationCoordinator(db, FixedClock(t("2026-03-17T15:00:00")))
    child = EventInput(event_id="child", event_time=t("2026-03-17T12:00:00"), event_type="consult_triaged", consult_id="C5")
    parent = EventInput(event_id="receipt", event_time=t("2026-03-17T12:01:00"), event_type="consult_received", consult_id="C5", hospital_id="H", consult_type="Stroke")
    report = coordinator.ingest([child, parent])
    assert report["accepted"] == 1 and report["unresolved"] == 1
    assert "C5" in coordinator.published.state.consults
    assert coordinator.published.state.consults["C5"].stage == "Received"

def test_database_order_preserves_fractional_seconds(db_url):
    db = EventDatabase(db_url)
    early = event("early", "consult_received", "2026-03-17T12:00:00", hospital_id="H", consult_type="Stroke")
    later = early.model_copy(update={"event_id":"later", "consult_id":"C2", "event_time":early.event_time.replace(microsecond=100000)})
    db.commit_batch([later, early], [])
    assert [e.event_id for e in db.events()] == ["early", "later"]
    stored = db.conn.execute("SELECT event_time FROM events ORDER BY event_time").fetchall()
    assert [r["event_time"] for r in stored] == [early.event_time, later.event_time]
    assert stored[1]["event_time"].microsecond == 100000

def test_conflicting_duplicate_is_durably_quarantined(db_url):
    db = EventDatabase(db_url)
    coord = MutationCoordinator(db, FixedClock(t("2026-03-17T13:00:00")))
    first = EventInput(event_id="same", event_time=t("2026-03-17T12:00:00"), event_type="consult_received", consult_id="C", hospital_id="H", consult_type="Stroke")
    report = coord.ingest([first, first.model_copy(update={"consult_type":"General Neuro"})])
    assert report["accepted"] == 1 and report["conflicts"] == 1 and report["duplicates"] == 0
    assert coord.published.state.consults["C"].consult_type == "Stroke"
    rejected = db.conn.execute("SELECT reason, received_at FROM quarantine").fetchone()
    assert "G2 conflicting payload" in rejected["reason"]
    assert rejected["received_at"].utcoffset().total_seconds() == 0

def test_restart_restores_committed_consult_state(db_url):
    clock = FixedClock(t("2026-03-17T13:00:00"))
    db = EventDatabase(db_url)
    original = MutationCoordinator(db, clock)
    row = EventInput(event_id="r", event_time=t("2026-03-17T12:00:00"), event_type="consult_received", consult_id="C", hospital_id="H", consult_type="Stroke")
    original.ingest([row])
    expected = original.published
    db.conn.close()
    reopened = EventDatabase(db_url)
    recovered = MutationCoordinator(reopened, clock).published
    assert recovered == expected
    reopened.conn.close()

def test_snapshot_reuses_state_when_only_time_changes(db_url):
    db = EventDatabase(db_url)
    coord = MutationCoordinator(db, FixedClock(t("2026-03-17T13:00:00")))
    row = EventInput(event_id="r", event_time=t("2026-03-17T12:00:00"), event_type="consult_received", consult_id="C", hospital_id="H", consult_type="Stroke")
    coord.ingest([row])
    state = coord.published.state
    coord.clock.value = t("2026-03-17T13:05:00")
    assert coord.current_publication().state is state

def test_invalid_routing_retry_is_quarantined(db_url):
    db = EventDatabase(db_url)
    coord = MutationCoordinator(db, FixedClock(t("2026-03-17T13:00:00")))
    row = EventInput(event_id="bad", event_time=t("2026-03-17T12:00:00"), event_type="routing_attempt_failed", consult_id="C", value="unsupported")
    report = coord.ingest([row])
    assert report["accepted"] == 0
    assert "routing failure requires retry_in_5m" in report["quarantined"][0]["reason"]


def test_signed_off_consult_is_unchanged_by_later_events():
    closed = (event("1", "consult_received", "2026-03-17T12:00:00", hospital_id="H", consult_type="Stroke"),
              event("2", "physician_assigned", "2026-03-17T12:01:00", physician_id="P1"),
              event("3", "note_signed", "2026-03-17T12:02:00", physician_id="P1"))
    late_assignment = event("4", "physician_assigned", "2026-03-17T12:03:00", physician_id="P2")
    assert replay(closed + (late_assignment,)) == replay(closed)


@pytest.mark.parametrize("field", ["event_id", "consult_id", "physician_id", "hospital_id"])
def test_api_rejects_blank_identifiers_without_mutation(db_url, field):
    api = create_app(db_url, FixedClock(t("2026-03-17T13:00:00")))
    row = {"event_id": "r", "event_time": "2026-03-17T12:00:00Z",
           "event_type": "consult_received", "consult_id": "C", "hospital_id": "H", "consult_type": "Stroke"}
    row[field] = "   "
    with TestClient(api) as client:
        assert client.post("/events", json=row).status_code == 422
        assert client.get("/ready").json()["event_count"] == 0


def test_api_rejects_unknown_fields_instead_of_silently_ignoring_them(db_url):
    api = create_app(db_url, FixedClock(t("2026-03-17T13:00:00")))
    row = {"event_id": "r", "event_time": "2026-03-17T12:00:00Z",
           "event_type": "consult_received", "consult_id": "C", "hospital_id": "H",
           "consult_type": "Stroke", "physican_id": "P1"}
    with TestClient(api) as client:
        assert client.post("/events", json=row).status_code == 422
        assert client.get("/ready").json()["event_count"] == 0


def test_clock_rewind_and_late_insert_rebuild_the_correct_visible_prefix(db_url):
    db = EventDatabase(db_url)
    clock = FixedClock(t("2026-03-17T12:00:00"))
    coord = MutationCoordinator(db, clock)
    receipt = EventInput(event_id="r", event_time=t("2026-03-17T12:00:00"), event_type="consult_received", consult_id="C", hospital_id="H", consult_type="Stroke")
    assigned = EventInput(event_id="a", event_time=t("2026-03-17T12:02:00"), event_type="physician_assigned", consult_id="C", physician_id="P1")
    coord.ingest([assigned, receipt])
    assert coord.current_publication().state.consults["C"].stage == "Received"
    clock.value = t("2026-03-17T12:03:00")
    assert coord.current_publication().state.consults["C"].stage == "Assigned"
    triaged = EventInput(event_id="t", event_time=t("2026-03-17T12:01:00"), event_type="consult_triaged", consult_id="C")
    coord.ingest([triaged])
    clock.value = t("2026-03-17T12:01:30")
    c = coord.current_publication().state.consults["C"]
    assert c.stage == "Triaged" and c.owner == "Unassigned"
    clock.value = t("2026-03-17T11:59:00")
    assert not coord.current_publication().state.consults


def test_concurrent_ingest_and_snapshots_preserve_committed_state(db_url):
    from concurrent.futures import ThreadPoolExecutor
    db = EventDatabase(db_url)
    coord = MutationCoordinator(db, FixedClock(t("2026-03-17T13:00:00")))
    def write(i):
        row = EventInput(event_id=str(i), event_time=t("2026-03-17T12:00:00"), event_type="consult_received", consult_id=f"C{i}", hospital_id="H", consult_type="Stroke")
        report = coord.ingest([row])
        p = coord.current_publication()
        assert p.revision >= report["revision"]
        assert f"C{i}" in p.state.consults
    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(write, range(24)))
    p = coord.current_publication()
    assert p.revision == 24 and p.event_count == 24
    assert set(p.state.consults) == {f"C{i}" for i in range(24)}
    assert len(db.events()) == 24


def test_batch_row_limit_rejects_entire_request(db_url, monkeypatch):
    from dataclasses import replace
    from importlib import import_module
    main = import_module("app.main")
    monkeypatch.setattr(main, "settings", replace(main.settings, max_batch_rows=1))
    api = create_app(db_url, FixedClock(t("2026-03-17T13:00:00")))
    row = {"event_id": "r", "event_time": "2026-03-17T12:00:00Z", "event_type": "consult_received",
           "consult_id": "C", "hospital_id": "H", "consult_type": "Stroke"}
    with TestClient(api) as client:
        assert client.post("/events", json=[row, {**row, "event_id": "r2"}]).status_code == 413
        assert client.get("/ready").json()["event_count"] == 0


def test_failed_startup_closes_database(db_url, monkeypatch):
    import psycopg
    from dataclasses import replace
    from importlib import import_module
    main = import_module("app.main")
    db = EventDatabase(db_url)
    monkeypatch.setattr(main, "EventDatabase", lambda url: db)
    monkeypatch.setattr(main, "settings", replace(main.settings, clock_mode="fixed", clock_fixed=None))
    with pytest.raises(ValueError, match="fixed clock requires"):
        with TestClient(create_app()):
            pass
    with pytest.raises(psycopg.OperationalError, match="closed"):
        db.conn.execute("SELECT 1")


def test_snapshot_cache_reuses_bytes_within_a_second_but_never_hides_new_events(db_url):
    clock = FixedClock(t("2026-03-17T13:00:00"))
    api = create_app(db_url, clock)
    row = {"event_id": "r", "event_time": "2026-03-17T12:00:00Z", "event_type": "consult_received",
           "consult_id": "C", "hospital_id": "H", "consult_type": "Stroke"}
    with TestClient(api) as client:
        first = client.get("/snapshot").content
        clock.value = t("2026-03-17T13:00:00.900000")
        assert client.get("/snapshot").content == first
        client.post("/events", json=row)
        assert client.get("/snapshot").json()["headline"]["open_consults"] == 1
        clock.value = t("2026-03-17T13:01:00")
        assert client.get("/snapshot").json()["consults"][0]["minutes_in_stage"] == 61


def test_second_writer_reloads_committed_log_instead_of_overwriting_it(db_url):
    clock = FixedClock(t("2026-03-17T13:00:00"))
    old, new = MutationCoordinator(EventDatabase(db_url), clock), MutationCoordinator(EventDatabase(db_url), clock)
    receipt = lambda cid: EventInput(event_id=cid, event_time=t("2026-03-17T12:00:00"), event_type="consult_received", consult_id=cid, hospital_id="H", consult_type="Stroke")
    old.ingest([receipt("from-old")])
    report = new.ingest([receipt("from-new"), receipt("from-old")])
    assert report["accepted"] == 1 and report["duplicates"] == 1 and report["revision"] == 2
    assert set(new.published.state.consults) == {"from-old", "from-new"}
