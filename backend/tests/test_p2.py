"""P2 domain tests use synthetic references; local fixture parity is additional."""
import csv
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
import pytest
from app.clock import FixedClock
from app.coordinator import MutationCoordinator
from app.db import EventDatabase
from app.engine.replay import replay
from app.engine.physician import eligible_for_hospital, fixture_state_label, physician_view
from app.fixture import load_fixture
from app.models import Event, EventInput
from app.references import Hospital, Physician, Refs, Shift, load_refs, local_instant


def at(minutes=0):
    return datetime(2026, 3, 17, 12, tzinfo=timezone.utc) + timedelta(minutes=minutes)


def refs():
    return Refs({"H": Hospital("Hospital", "America/New_York")},
                {pid: Physician(pid, (Shift(at(), at(60)),)) for pid in ("P1", "P2")},
                {"P1": frozenset({"H"}), "P2": frozenset()})


def row(eid, kind="consult_received", minute=0, cid="C", pid=None, **kwargs):
    return EventInput(event_id=eid, event_time=at(minute), ingested_at=at(minute), event_type=kind,
                      consult_id=cid, physician_id=pid, hospital_id="H", consult_type="Stroke", **kwargs)


def replay_rows(*rows):
    return replay(tuple(Event(**{**r.model_dump(), "received_at": at(), "raw_json": r.raw_json or {}}) for r in rows))


def test_orphan_release_converges_across_batch_order_and_restart(db_url, new_db_url):
    clock = FixedClock(at(30))
    server = FixedClock(at())
    db = EventDatabase(db_url)
    coord = MutationCoordinator(db, clock, refs=refs(), receipt_clock=server)
    child, parent = row("child", "consult_triaged", 2), row("parent")
    report = coord.ingest([child])
    assert report["held_orphans"] == 1 and not report["quarantined"]
    deadline = db.holds()["child"][1]
    server.value = at(1)
    assert coord.ingest([child])["duplicates"] == 1
    assert db.holds()["child"][1] == deadline
    db.close()
    reopened = EventDatabase(db_url)
    recovered = MutationCoordinator(reopened, clock, receipt_clock=server)
    report = recovered.ingest([parent])
    assert report["accepted"] == 2 and report["released_orphans"] == 1
    assert report["held_orphans"] == 0
    both = MutationCoordinator(EventDatabase(new_db_url()), clock, refs=refs(), receipt_clock=server)
    both.ingest([parent, child])
    assert recovered.published.state == both.published.state
    assert recovered.refs == both.refs
    reopened.close()


def test_orphan_expiry_uses_server_clock_at_exact_deadline_and_stays_expired(db_url):
    db = EventDatabase(db_url)
    simulation, server = FixedClock(at(30)), FixedClock(at())
    coord = MutationCoordinator(db, simulation, receipt_clock=server)
    child = row("child", "consult_triaged", 1)
    coord.ingest([child])
    server.value = at() + timedelta(seconds=299)
    assert coord.sweep().held_orphans == 1
    server.value = at(5)
    p = coord.sweep()
    assert p.held_orphans == 0 and p.stats["expired_orphans"] == 1
    assert p.as_of == at(30)
    coord.sweep()
    assert coord.published.stats["expired_orphans"] == 1
    db.close()
    reopened = EventDatabase(db_url)
    coord = MutationCoordinator(reopened, simulation, receipt_clock=server)
    report = coord.ingest([row("parent"), child])
    assert report["duplicates"] == 1 and report["accepted"] == 1
    assert coord.published.state.consults["C"].stage == "Received"
    with reopened.pool.connection() as conn:
        assert conn.execute("SELECT COUNT(*) FROM quarantine").fetchone()["count"] == 1
    reopened.close()


def test_reference_activation_releases_known_ids_atomically_and_survives_restart(db_url):
    db = EventDatabase(db_url)
    clock, server = FixedClock(at(30)), FixedClock(at())
    coord = MutationCoordinator(db, clock, refs=refs(), receipt_clock=server)
    unknown = row("unknown", cid="C2").model_copy(update={"hospital_id": "H2"})
    assert coord.ingest([unknown])["held_orphans"] == 1
    current = refs()
    new_refs = Refs({**current.hospitals, "H2": Hospital("Second", "UTC")}, current.physicians, current.credentials)
    report = coord.activate_references(new_refs)
    assert report["accepted"] == 1 and coord.published.reference_revision == 2
    assert coord.published.state.consults["C2"].hospital_id == "H2"
    db.close()
    reopened = EventDatabase(db_url)
    recovered = MutationCoordinator(reopened, clock, receipt_clock=server)
    assert recovered.refs == new_refs
    assert recovered.published == coord.published
    reopened.close()


def test_failed_hold_or_reference_commit_does_not_publish(db_url, monkeypatch):
    db = EventDatabase(db_url)
    coord = MutationCoordinator(db, FixedClock(at(30)), refs=refs(), receipt_clock=FixedClock(at()))
    original = coord.published
    def fail(*args, **kwargs): raise RuntimeError("disk failed")
    monkeypatch.setattr(db, "commit_batch", fail)
    with pytest.raises(RuntimeError): coord.ingest([row("orphan", "consult_triaged", 2)])
    assert coord.published is original and coord.current_publication().held_orphans == 0
    new = refs()
    new = Refs(new.hospitals, {**new.physicians, "P3": Physician("Third")}, {**new.credentials, "P3": frozenset()})
    with pytest.raises(RuntimeError): coord.activate_references(new)
    assert "P3" not in coord.refs.physicians
    assert not db.holds()


def test_quality_metrics_persist_and_do_not_recount_on_replay(db_url):
    db = EventDatabase(db_url)
    clock = FixedClock(at(30))
    coord = MutationCoordinator(db, clock)
    coord.ingest([row("latest", minute=10), row("earlier", minute=2, cid="C2"), row("latest", minute=10)])
    expected = dict(coord.published.stats)
    assert expected["accepted"] == 2 and expected["duplicates"] == 1
    assert expected["reordered"] == expected["late"] == 1
    assert expected["max_reorder_lag_s"] == 480
    clock.value = at(3)
    assert dict(coord.current_publication().stats) == expected
    db.close()
    reopened = EventDatabase(db_url)
    recovered = MutationCoordinator(reopened, clock)
    assert dict(recovered.published.stats) == expected
    reopened.close()


def test_matching_sessions_and_rings_do_not_clear_other_consults_or_directions():
    state = replay_rows(row("r1", cid="C1"), row("r2", cid="C2"),
                        row("ring1", "incoming_call_ringing", 1, "C1", "P1"),
                        row("ring2", "incoming_call_ringing", 1, "C2", "P1"),
                        row("start1", "incoming_call_started", 2, "C1", "P1"),
                        row("start2", "outgoing_call_started", 2, "C2", "P1"),
                        row("wrong", "incoming_call_ended", 3, "C2", "P1", value="phone_complete"),
                        row("end1", "incoming_call_ended", 4, "C1", "P1", value="continue"))
    p = state.physicians["P1"]
    assert p.calls == frozenset({("C2", "outgoing")})
    assert p.rings == frozenset({"C2"})
    assert p.last_call_end == at(4) and p.last_answered_at == at(2)
    assert state.consults["C2"].stage == "Received"
    assert "unmatched_session:wrong" in p.flags


def test_same_session_start_is_conflict_and_does_not_inflate_calls():
    state = replay_rows(row("r"), row("s1", "incoming_call_started", 1, pid="P1"), row("s2", "incoming_call_started", 2, pid="P1"))
    assert state.physicians["P1"].call_starts == (at(1),)
    assert "unmatched_session:s2" in state.consults["C"].flags


def test_note_age_reassignment_history_and_backward_flags():
    state = replay_rows(row("r"), row("a1", "physician_assigned", 1, pid="P1"),
                        row("a2", "physician_assigned", 2, pid="P1"),
                        row("video", "video_started", 3, pid="P1"), row("end", "video_ended", 4, pid="P1"),
                        row("note", "note_started", 5, pid="P1"), row("repeat", "note_started", 6, pid="P1"),
                        row("back", "consult_triaged", 7), row("handoff", "physician_assigned", 8, pid="P2"))
    c = state.consults["C"]
    assert c.note_pending_since == at(4) and c.entered_at == at(5)
    assert c.assignments == (("P1", at(1)), ("P2", at(8)))
    assert c.owner == "P2" and c.flags == ("backward_stage:back",)
    assert physician_view(state, refs(), "P1", at(10)).consults_this_shift == 1
    assert physician_view(state, refs(), "P1", at(10)).open_consults == 0
    assert physician_view(state, refs(), "P2", at(10)).open_consults == 1


@pytest.mark.parametrize("seconds,expected", [(119, False), (120, True), (121, True)])
def test_cooldown_exact_boundary(seconds, expected):
    state = replay_rows(row("r"), row("start", "incoming_call_started", 1, pid="P1"), row("end", "incoming_call_ended", 2, pid="P1", value="continue"), row("camera", "camera_inactive", 3, cid=None, pid="P1"))
    view = physician_view(state, refs(), "P1", at(2) + timedelta(seconds=seconds))
    assert view.routable is expected
    assert eligible_for_hospital(view, "H") is expected
    assert not eligible_for_hospital(view, "unknown")


def test_shift_boundaries_and_distinct_assignment_counters():
    state = replay_rows(row("r"), row("a1", "physician_assigned", 0, pid="P1"), row("a2", "physician_assigned", 1, pid="P1"), row("a3", "physician_assigned", 2, pid="P2"), row("a4", "physician_assigned", 3, pid="P1"))
    assert physician_view(state, refs(), "P1", at()).routable
    assert physician_view(state, refs(), "P1", at(59)).consults_this_shift == 1
    view = physician_view(state, refs(), "P1", at(60))
    assert view.exclusion_reasons == ("off_shift",) and view.consults_this_shift == 0


def test_g6_precedence_and_meeting_routability():
    state = replay_rows(row("r"), row("a", "physician_assigned", 1, pid="P1"),
                        row("meeting", "physician_status_changed", 2, cid=None, pid="P1", value="In Meeting"),
                        row("camera", "camera_active", 2, cid=None, pid="P1"))
    view = physician_view(state, refs(), "P1", at(3))
    assert view.derived_state == "Available (meeting)" and view.routable
    unavailable = row("status", "physician_status_changed", 3, cid=None, pid="P1", value="Temporarily Unavailable")
    state = replay_rows(row("r"), row("a", "physician_assigned", 1, pid="P1"), unavailable,
                        row("video", "video_started", 4, pid="P1"))
    assert physician_view(state, refs(), "P1", at(5)).derived_state == "Video Consult"


def test_offline_agent_does_not_leave_stale_camera_exclusion():
    camera = row("camera", "camera_active", 1, cid=None, pid="P1")
    lost = row("lost", "agent_heartbeat_lost", 2, cid=None, pid="P1")
    before = physician_view(replay_rows(camera), refs(), "P1", at(1))
    assert not before.routable and "external_platform" in before.flags
    offline = physician_view(replay_rows(camera, lost), refs(), "P1", at(3))
    assert offline.routable and offline.derived_state == "Available"
    assert offline.desktop_agent == "Offline" and "unverified" in offline.flags
    assert "external_platform" not in offline.flags
    recovered = row("recovered", "camera_active", 4, cid=None, pid="P1")
    assert not physician_view(replay_rows(camera, lost, recovered), refs(), "P1", at(5)).routable


@pytest.mark.parametrize("kind,value", [("incoming_call_started", None), ("video_started", None), ("physician_status_changed", "Temporarily Unavailable")])
def test_offline_camera_fallback_still_respects_synapse_busy_and_status(kind, value):
    state = replay_rows(row("receive"), row("camera", "camera_active", 1, cid=None, pid="P1"),
                        row("busy", kind, 2, pid="P1", value=value), row("lost", "agent_heartbeat_lost", 3, cid=None, pid="P1"))
    assert not physician_view(state, refs(), "P1", at(4)).routable


@pytest.mark.parametrize("day,clock", [(date(2026, 3, 8), "02:30"), (date(2026, 11, 1), "01:30")])
def test_ambiguous_or_nonexistent_time_only_shifts_are_rejected(day, clock):
    from datetime import time
    with pytest.raises(ValueError, match="ambiguous/nonexistent"):
        local_instant(day, time.fromisoformat(clock), ZoneInfo("America/New_York"))


def test_reference_immutability_overlap_and_unknown_credentials():
    reference = refs()
    with pytest.raises(TypeError): reference.hospitals["other"] = Hospital("Other", "UTC")
    with pytest.raises(ValueError, match="overlapping"):
        Refs(reference.hospitals, {**reference.physicians, "P1": Physician("First", (Shift(at(), at(10)), Shift(at(5), at(20))))}, reference.credentials)
    with pytest.raises(ValueError, match="unknown credential"):
        Refs(reference.hospitals, reference.physicians, {**reference.credentials, "P1": frozenset({"missing"})})


DATA = Path(__file__).resolve().parents[2] / "data"
@pytest.mark.skipif(not (DATA / "event_stream.csv").exists(), reason="local source data is deliberately not committed")
def test_full_local_fixture_parity_all_physician_and_consult_fields(db_url):
    reference = load_refs(DATA, date(2026, 3, 17))
    now = datetime.fromisoformat("2026-03-17T18:20:00-04:00")
    coord = MutationCoordinator(EventDatabase(db_url), FixedClock(now), refs=reference)
    report = coord.ingest(load_fixture(DATA / "event_stream.csv"))
    assert report["accepted"] == 1163 and report["duplicates"] == 1
    assert report["held_orphans"] == 0 and not report["quarantined"]
    assert coord.published.stats["max_reorder_lag_s"] == 355
    assert coord.published.stats["max_delivery_lag_s"] == 405
    state = coord.published.state
    with (DATA / "snapshot_physicians_1820.csv").open(newline="") as handle:
        expected = list(csv.DictReader(handle))
    for r in expected:
        pid = r["physician_id"]
        view = physician_view(state, reference, pid, now)
        shift = reference.physicians[pid].shifts[0]
        actual = {key: str(getattr(view, key)) for key in ("self_reported_status", "desktop_agent", "consults_this_shift", "calls_this_shift", "open_consults", "minutes_to_shift_end")}
        actual.update(physician_id=pid, name=reference.physicians[pid].name,
                      shift_et=f'{shift.start.astimezone(ZoneInfo("America/New_York")):%H:%M}-{shift.end.astimezone(ZoneInfo("America/New_York")):%H:%M}',
                      derived_state=fixture_state_label(state.physicians[pid], view))
        assert actual == r
    with (DATA / "snapshot_open_consults_1820.csv").open(newline="") as handle:
        expected = {r["consult_id"]: r for r in csv.DictReader(handle)}
    opened = {cid: c for cid, c in state.consults.items() if c.stage != "Signed Off"}
    assert set(opened) == set(expected)
    labels = {"Imaging Pending": "CT/CTA or Imaging Pending", "Video In Progress": "Video Consult In Progress"}
    for cid, c in opened.items():
        actual = {"consult_id": cid, "hospital_id": c.hospital_id, "hospital_name": reference.hospitals[c.hospital_id].name,
                  "physician_id": c.owner, "consult_type": c.consult_type, "current_stage": labels.get(c.stage, c.stage),
                  "stage_entered_at": c.entered_at.astimezone(ZoneInfo("America/New_York")).strftime("%H:%M:%S"),
                  "minutes_in_stage": str(int((now - c.entered_at).total_seconds() // 60)),
                  "minutes_since_received": str(int((now - c.received_at).total_seconds() // 60))}
        assert actual == expected[cid]
    p7 = physician_view(state, reference, "PHY-007", now)
    assert p7.derived_state == "Available" and p7.exclusion_reasons == ("ringing",)
    assert len(p7.credentialed_hospitals) == 2 and "unverified" in p7.flags
    assert not reference.physicians["PHY-011"].shifts


def test_unknown_physician_and_removed_reference_history_are_explicit(db_url):
    coord = MutationCoordinator(EventDatabase(db_url), FixedClock(at(30)), refs=refs(), receipt_clock=FixedClock(at()))
    coord.ingest([row("received"), row("unknown", "physician_assigned", 1, pid="not_in_roster")])
    assert coord.published.held_orphans == 1
    assert coord.published.state.consults["C"].owner == "Unassigned"
    changed = refs()
    changed = Refs(changed.hospitals, {**changed.physicians, "not_in_roster": Physician("New")}, {**changed.credentials, "not_in_roster": frozenset()})
    coord.activate_references(changed)
    assert coord.published.state.consults["C"].owner == "not_in_roster"
    coord.activate_references(refs())
    assert coord.published.unresolved_history == ("unknown",)
    assert coord.published.refs == refs()
    assert "not_in_roster" in coord.published.state.physicians


def test_stale_ring_and_unverified_agent_keep_all_routing_exclusions():
    state = replay_rows(row("r"), row("camera", "camera_inactive", 1, cid=None, pid="P1"),
                        row("lost", "agent_heartbeat_lost", 2, cid=None, pid="P1"),
                        row("ring", "incoming_call_ringing", 3, pid="P1"))
    view = physician_view(state, refs(), "P1", at(70))
    assert view.derived_state == "Available" and "unverified" in view.flags
    assert view.exclusion_reasons == ("off_shift", "ringing")
    assert state.physicians["P1"].rings == frozenset({"C"})


def test_reference_csv_overnight_and_invalid_duplicates(tmp_path):
    (tmp_path / "hospitals.csv").write_text("hospital_id,hospital_name,local_timezone\nH,Hospital,America/Chicago\n")
    (tmp_path / "physicians_on_shift.csv").write_text("physician_id,name,shift_start_et,shift_end_et\nP1,First,22:00,06:00\n")
    (tmp_path / "physicians_off_shift_roster.csv").write_text("physician_id,name,next_shift_start\nP2,Second,2026-03-17T19:00:00-04:00\n")
    matrix = tmp_path / "credentialing_matrix.csv"
    matrix.write_text("physician_id,name,H\nP1,First,Y\nP2,Second,\n")
    loaded = load_refs(tmp_path, date(2026, 3, 17))
    shift = loaded.physicians["P1"].shifts[0]
    assert shift.start == datetime.fromisoformat("2026-03-18T02:00:00+00:00")
    assert shift.end == datetime.fromisoformat("2026-03-18T10:00:00+00:00")
    assert not loaded.physicians["P2"].shifts
    matrix.write_text("physician_id,name,H\nP1,First,Y\nP1,First,Y\nP2,Second,\n")
    with pytest.raises(ValueError, match="duplicate reference"):
        load_refs(tmp_path, date(2026, 3, 17))
    matrix.write_text("physician_id,name,H\nP1,First,Yes\nP2,Second,\n")
    with pytest.raises(ValueError, match="credential cells"):
        load_refs(tmp_path, date(2026, 3, 17))


def test_raw_g1_rows_quarantine_individually_without_losing_valid_rows(db_url):
    coord = MutationCoordinator(EventDatabase(db_url), FixedClock(at(30)))
    valid = row("valid").model_dump(mode="json")
    invalid = {**valid, "event_id": "bad", "event_time": "2026-03-17T12:00:00"}
    report = coord.ingest_raw([invalid, valid, {"unexpected": "fields"}])
    assert report["accepted"] == 1 and len(report["quarantined"]) == 2
    assert coord.published.stats["rejected"] == 2
    with coord.db.pool.connection() as conn:
        assert conn.execute("SELECT COUNT(*) FROM quarantine").fetchone()["count"] == 2


def test_sample_adapter_unknown_description_is_quarantined_and_raw_is_preserved(db_url):
    coord = MutationCoordinator(EventDatabase(db_url), FixedClock(at(30)))
    raw = {"event_id": "good", "event_time": at().isoformat(), "ingested_at": at().isoformat(),
           "event_type": "consult_received", "consult_id": "C", "hospital_id": "H", "physician_id": "",
           "description": "Stroke consult request received"}
    report = coord.ingest_raw([raw, {**raw, "event_id": "bad", "description": "Guess this"}], "sample-csv-v1")
    assert report["accepted"] == 1 and len(report["quarantined"]) == 1
    event = coord.db.events()[0]
    assert event.raw_json == raw and event.adapter_version == "sample-csv-v1"
    assert event.consult_type == "Stroke" and event.physician_id is None


def test_legacy_event_log_reports_incomplete_quality_history(db_url):
    db = EventDatabase(db_url)
    source = row("legacy")
    db.commit_batch([Event(**{**source.model_dump(), "received_at": at(), "raw_json": {}})], [])
    coord = MutationCoordinator(db, FixedClock(at(30)))
    assert coord.published.stats["accepted"] == 1
    assert coord.published.stats["history_complete"] is False
    coord.ingest([row("new", cid="C2")])
    restarted = MutationCoordinator(db, FixedClock(at(30)))
    assert restarted.published.stats["accepted"] == 2
    assert restarted.published.stats["history_complete"] is False


def test_late_session_start_repairs_prior_unmatched_end_by_replay(db_url):
    coord = MutationCoordinator(EventDatabase(db_url), FixedClock(at(30)), refs=refs())
    coord.ingest([row("r"), row("end", "incoming_call_ended", 3, pid="P1", value="phone_complete")])
    assert "unmatched_session:end" in coord.published.state.consults["C"].flags
    coord.ingest([row("start", "incoming_call_started", 1, pid="P1")])
    c = coord.published.state.consults["C"]
    assert not c.flags and c.stage == "Note Pending" and c.note_pending_since == at(3)
    p = coord.published.state.physicians["P1"]
    assert not p.calls and p.call_starts == (at(1),) and p.last_call_end == at(3)


@pytest.mark.parametrize("service_date", [date(2026, 4, 7), date(2026, 11, 2)])
def test_independent_day_and_id_prefix_are_not_bound_to_original_fixture(db_url, service_date):
    start = datetime.combine(service_date, datetime.min.time(), tzinfo=timezone.utc) + timedelta(hours=12)
    reference = Refs({"H-T0001": Hospital("Practice Hospital", "America/New_York")},
                     {"PHY-T0001": Physician("Practice Physician", (Shift(start, start + timedelta(hours=1)),))},
                     {"PHY-T0001": frozenset({"H-T0001"})})
    coord = MutationCoordinator(EventDatabase(db_url), FixedClock(start + timedelta(minutes=10)), refs=reference)
    events = []
    for i, (kind, value) in enumerate((("consult_received", None), ("physician_assigned", None),
                                       ("incoming_call_started", None), ("incoming_call_ended", "phone_complete"))):
        events.append({"event_id": f"EVT-T{i + 1:04d}", "event_time": (start + timedelta(minutes=i)).isoformat(),
                       "event_type": kind, "consult_id": "CON-T0001", "hospital_id": "H-T0001", "consult_type": "Stroke",
                       "physician_id": "PHY-T0001" if i else None, "value": value})
    report = coord.ingest_raw(events)
    assert report["accepted"] == 4 and not report["held_orphans"] and not report["quarantined"]
    bundle = coord.current_publication()
    c = bundle.state.consults["CON-T0001"]
    assert c.stage == "Note Pending" and c.note_pending_since == start + timedelta(minutes=3)
    view = physician_view(bundle.state, bundle.refs, "PHY-T0001", bundle.as_of)
    assert (view.consults_this_shift, view.calls_this_shift, view.open_consults) == (1, 1, 1)
    assert eligible_for_hospital(view, "H-T0001")


def test_march17_judging_extension_appends_without_reset_and_respects_clock(db_url):
    clock = FixedClock(at(10))
    coord = MutationCoordinator(EventDatabase(db_url), clock, refs=refs())
    coord.ingest([row("base-receipt"), row("base-assignment", "physician_assigned", 1, pid="P1")])
    old_consult = coord.published.state.consults["C"]
    extension = [row("EVT-J0001", minute=10, cid="CON-J0001"),
                 row("EVT-J0002", "physician_assigned", 11, "CON-J0001", "P2"),
                 row("EVT-J0003", "incoming_call_started", 12, "CON-J0001", "P2")]
    report = coord.ingest(extension)
    assert report["accepted"] == 3 and report["pending_future"] == 2
    assert coord.published.state.consults["CON-J0001"].stage == "Received"
    clock.value = at(14)
    bundle = coord.current_publication()
    assert bundle.event_count == 5 and bundle.state.consults["C"] == old_consult
    assert bundle.state.consults["CON-J0001"].stage == "Provider Contacted"
    view = physician_view(bundle.state, bundle.refs, "P2", bundle.as_of)
    assert view.derived_state == "Hospital Call" and view.calls_this_shift == 1
    assert coord.ingest(extension)["duplicates"] == 3
    assert coord.current_publication().event_count == 5


def test_new_wording_is_read_by_keyword_and_unreadable_rows_are_rejected():
    """The judges' file may phrase events differently; known wordings keep their exact meaning."""
    import pytest
    from app.ingest.adapters import DESCRIPTION, STATUS, _by_keyword, adapt_fixture
    for (kind, desc), (consult_type, value) in DESCRIPTION.items():
        assert _by_keyword(kind, desc) == (consult_type, value), desc  # the fallback agrees with every known wording
    for desc, status in STATUS.items():
        assert _by_keyword("physician_status_changed", desc) == (None, status)
    row = lambda kind, desc: adapt_fixture({"event_type": kind, "description": desc})
    assert row("consult_received", "Acute stroke consult requested")["consult_type"] == "Stroke"
    assert row("consult_received", "General neurology consult received")["consult_type"] == "General Neuro"
    assert row("incoming_call_ended", "Call ended (phone only, no video needed)")["value"] == "phone_complete"
    assert row("incoming_call_ended", "Call ended")["value"] == "continue"
    assert row("routing_attempt_failed", "Routing failed")["value"] == "retry_in_5m"
    assert row("physician_status_changed", "Status set: In Meeting")["value"] == "In Meeting"
    assert row("physician_status_changed", "Status: not available")["value"] == "Temporarily Unavailable"
    with pytest.raises(ValueError, match="receipt"):
        row("consult_received", "Consult request received")  # no type: rejected and reported, not guessed
    with pytest.raises(ValueError, match="status"):
        row("physician_status_changed", "Status changed")
