"""Public generated fixtures compared against independently authored snapshots."""
import csv
from datetime import date, datetime, time, timedelta
from pathlib import Path
import sys
from zoneinfo import ZoneInfo

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from scripts.synth.generate import PRESETS, generate
from scripts.synth.schema import DESCRIPTIONS
from scripts.synth.validate import validate
from app.decide.eligibility import Proposal, evaluate_proposal, load_offer_history
from app.decide.routing_sim import observed_service, trap_check
from app.engine.physician import fixture_state_label
from app.engine.replay import replay
from app.fixture import load_fixture
from app.models import EVENT_TYPES, Event
from app.ops.detect import detect, views_at
from app.ops.coverage import surges
from app.ops.refs import load_ops_refs
from app.references import load_reference_dir


def world(path, manifest, append=False):
    now = datetime.fromisoformat(manifest["as_of"])
    refs = load_reference_dir(path, date.fromisoformat(manifest["service_date"]))
    ops = load_ops_refs(path, {hid: h.timezone for hid, h in refs.hospitals.items()}, set(refs.physicians))
    rows = load_fixture(path / "event_stream.csv")
    if append:
        rows += load_fixture(path / "live_test_events.csv")
        now = datetime.fromisoformat(next(s for s in manifest["scenarios"] if s["name"] == "live_T23_T27")["append_as_of"])
    seen = {}
    for row in rows:
        if row.event_time <= now and row.ingested_at <= now:
            seen.setdefault(row.event_id, Event(**{**row.model_dump(), "received_at": row.ingested_at}))
    events = tuple(seen.values())
    state = replay(events)
    return now, refs, ops, events, state, views_at(state, refs, now)


def read(path):
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


@pytest.mark.parametrize("preset,scale", [(preset, 1) for preset in PRESETS] + [("practice-0407", 10), ("practice-0407", 100)])
def test_generated_snapshots_match_replay_and_eligibility(tmp_path, preset, scale):
    day, clock, prefix, mode = PRESETS[preset]
    manifest = generate(tmp_path, day=date.fromisoformat(day), clock=time.fromisoformat(clock), prefix=prefix, mode=mode, scale=scale)
    validate(tmp_path)
    now, refs, ops, events, state, views = world(tmp_path, manifest)
    expected = {r["consult_id"]: r for r in read(tmp_path / f"snapshot_open_consults_{clock.replace(':', '')}.csv")}
    open_ = {cid: c for cid, c in state.consults.items() if c.stage != "Signed Off"}
    assert open_.keys() == expected.keys()
    labels = {"Video In Progress": "Video Consult In Progress", "Imaging Pending": "CT/CTA or Imaging Pending"}
    for cid, c in open_.items():
        row = expected[cid]
        assert (c.hospital_id, c.owner, c.consult_type, labels.get(c.stage, c.stage)) == tuple(row[k] for k in ("hospital_id", "physician_id", "consult_type", "current_stage"))
        assert refs.hospitals[c.hospital_id].name == row["hospital_name"]
        assert c.entered_at.astimezone(now.tzinfo).strftime("%H:%M:%S") == row["stage_entered_at"]
        assert int((now - c.entered_at).total_seconds() // 60) == int(row["minutes_in_stage"])
        assert int((now - c.received_at).total_seconds() // 60) == int(row["minutes_since_received"])
    for row in read(tmp_path / f"snapshot_physicians_{clock.replace(':', '')}.csv"):
        pid = row["physician_id"]
        view = views[pid]
        assert view.self_reported_status == row["self_reported_status"]
        assert view.desktop_agent == row["desktop_agent"]
        assert fixture_state_label(state.physicians[pid], view) == row["derived_state"]
        assert (view.consults_this_shift, view.calls_this_shift, view.open_consults, view.minutes_to_shift_end) == tuple(int(row[k]) for k in ("consults_this_shift", "calls_this_shift", "open_consults", "minutes_to_shift_end"))
        assert refs.physicians[pid].name == row["name"]
        eastern = ZoneInfo("America/New_York")
        assert f"{view.shift.start.astimezone(eastern):%H:%M}-{view.shift.end.astimezone(eastern):%H:%M}" == row["shift_et"]
    assert {e.event_type for e in events} == EVENT_TYPES == DESCRIPTIONS.keys()
    eligibility = next(s for s in manifest["scenarios"] if s["name"] == "only_one_eligible")
    p = eligibility["proposal"]
    candidates = evaluate_proposal(Proposal(datetime.fromisoformat(p["start"]), datetime.fromisoformat(p["end"]), tuple(p["hospitals"])), refs, ops, now, load_offer_history(tmp_path / "support/offer_history.csv", now))
    assert [c.physician_id for c in candidates if c.eligible] == [eligibility["physician_id"]]
    for candidate in candidates:
        if not candidate.eligible:
            assert candidate.failed == (eligibility["failure_by_physician"][candidate.physician_id],)
    found = detect(state, refs, views, now)
    stalled = next(s for s in manifest["scenarios"] if s["name"] == "stalled_stroke")
    assert any(f.consult_id in stalled["consult_ids"] and f.severity == "Critical" for f in found)
    assert any(f.kind == "stranded" for f in found)
    assert any(f.kind == "external_platform" for f in found)
    assert any(f.kind == "agent_offline" for f in found)
    if mode == "dst":
        assert ops.mean(next(iter(refs.hospitals)), now) is None
    if mode == "trap":
        trap = next(s for s in manifest["scenarios"] if s["name"] == "low_volume_trap")
        check = trap_check(state, refs, ops, views, now, trap["physician_id"], now, now.replace(hour=20, minute=20), {trap["hospital_id"]}, observed_service(events, state))
        assert check.trap_shown and check.spill["baseline"] > 0
        assert check.scenarios["baseline"][2].sites(trap["physician_id"]) <= {trap["hospital_id"]}


def test_live_append_replays_T23_to_T27_without_reset(tmp_path):
    manifest = generate(tmp_path, day=date(2026, 3, 17), clock=time(18, 30), prefix="L", mode="live")
    base = world(tmp_path, manifest)
    now, refs, ops, events, state, views = world(tmp_path, manifest, append=True)
    case = next(s for s in manifest["scenarios"] if s["name"] == "live_T23_T27")
    assert len(state.consults) == len(base[4].consults) + case["distinct_new_consults"]
    counts = lambda state, now: {s.hospital_id: s.count for s in surges(state, refs, ops, now)}
    gap = case["consult_ids"][0]
    hospital = state.consults[gap].hospital_id
    assert counts(state, now)[hospital] == counts(base[4], base[0])[hospital] + 2
    findings = detect(state, refs, views, now)
    assert all(any(f.consult_id == cid and f.severity == "Critical" for f in findings) for cid in case["consult_ids"])
    assert state.consults[case["consult_ids"][0]].repeat_contacts == 1
    assert state.consults[case["video_consult_id"]].stage == "Note Pending"
    assert state.consults[case["video_consult_id"]].entered_at == datetime.fromisoformat(manifest["as_of"]) + timedelta(minutes=1)
    ring = state.consults[case["ringing_consult_id"]]
    assert ring.ringing_since is None and views[ring.owner].derived_state == "Hospital Call"
    assert views[ring.owner].calls_this_shift == base[5][ring.owner].calls_this_shift + 1
    stranded = state.consults[case["stranded_consult_id"]]
    assert stranded.stage == "Provider Contacted" and views[stranded.owner].derived_state == "Hospital Call"
    assert not any(f.kind == "stranded" and f.consult_id == stranded.consult_id for f in findings)
