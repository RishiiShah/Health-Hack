"""Decision-engine inputs: ops references and replay counters. Pure, no database."""
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
import pytest
from app.engine.replay import replay
from app.models import Event, EventInput
from app.ops.refs import load_ops_refs

ET = ZoneInfo("America/New_York")
DATA = Path(__file__).resolve().parents[2] / "data"
HEADERS = {
    "baseline_hourly_volume.csv": "hospital_id,hospital_name,dow_type,hour_start_et,mean_consults,p90_consults,weeks_sampled",
    "coverage_requirements.csv": "hospital_id,hospital_name,time_block_et,min_available_credentialed_physicians",
    "physicians_off_shift_roster.csv": "physician_id,name,role,split_shift_opt_in,last_shift_end,next_shift_start,hours_worked_last_7d,est_minutes_to_online,preferred_channel,offers_declined_last_30d",
}
ROSTER = "R1,Dr. R,Night,Yes,2026-04-07T07:00:00-04:00,2026-04-07T19:00:00-04:00,48,0,app_push,2"


def write(tmp_path, baseline=("H,H,weekday,18:00,0.4,1,12",), coverage=("H,H,07:00-22:00,1", "H,H,22:00-07:00,2"), roster=(ROSTER,)):
    for name, rows in (("baseline_hourly_volume.csv", baseline), ("coverage_requirements.csv", coverage), ("physicians_off_shift_roster.csv", roster)):
        (tmp_path / name).write_text("\n".join((HEADERS[name], *rows)) + "\n")
    return tmp_path


def load(tmp_path, **kwargs):
    return load_ops_refs(write(tmp_path, **kwargs), {"H": "America/New_York"}, {"R1"})


def et(day, hh, mm=0):
    return datetime(2026, 4, day, hh, mm, tzinfo=ET)


def test_requirement_blocks_are_et_and_cross_midnight(tmp_path):
    ops = load(tmp_path)
    assert ops.requirement("H", et(7, 21, 59)) == 1
    assert ops.requirement("H", et(7, 22)) == 2
    assert ops.requirement("H", et(8, 3)) == 2
    assert ops.requirement("H", et(8, 7)) == 1
    # The same instant expressed in UTC selects the ET block.
    assert ops.requirement("H", et(7, 22).astimezone(timezone.utc)) == 2


def test_missing_block_or_hour_is_unknown_not_zero(tmp_path):
    ops = load(tmp_path, coverage=("H,H,07:00-22:00,1",))
    assert ops.requirement("H", et(7, 23)) is None
    assert ops.p90("H", et(7, 18, 59)) == 1
    assert ops.mean("H", et(7, 18, 30)) == 0.4
    assert ops.p90("H", et(7, 19)) is None


def test_overlapping_blocks_and_duplicate_hours_are_rejected(tmp_path):
    with pytest.raises(ValueError, match="overlap"):
        load(tmp_path, coverage=("H,H,07:00-22:00,1", "H,H,21:00-07:00,1"))
    with pytest.raises(ValueError, match="duplicate"):
        load(tmp_path, baseline=("H,H,weekday,18:00,0.4,1,12", "H,H,weekday,18:00,0.5,1,12"))


def test_unknown_ids_and_bad_values_are_rejected(tmp_path):
    with pytest.raises(ValueError, match="unknown hospital"):
        load(tmp_path, coverage=("X,X,07:00-22:00,1",))
    with pytest.raises(ValueError, match="unknown physician"):
        load(tmp_path, roster=(ROSTER.replace("R1", "R9", 1),))
    with pytest.raises(ValueError, match="opt-in"):
        load(tmp_path, roster=(ROSTER.replace(",Yes,", ",Maybe,"),))
    with pytest.raises(ValueError, match="UTC offset"):
        load(tmp_path, roster=(ROSTER.replace("07:00:00-04:00", "07:00:00"),))
    with pytest.raises(ValueError, match="negative"):
        load(tmp_path, coverage=("H,H,07:00-22:00,-1",))


def test_roster_fields_are_typed(tmp_path):
    r = load(tmp_path).roster["R1"]
    assert (r.role, r.opt_in, r.hours_last_7d, r.minutes_to_online, r.declines_30d) == ("Night", True, 48.0, 0, 2)
    assert r.last_shift_end == et(7, 7) and r.next_shift_start == et(7, 19)
    assert r.last_shift_end.tzinfo == timezone.utc


@pytest.mark.skipif(not (DATA / "baseline_hourly_volume.csv").exists(), reason="source data is gitignored")
def test_sample_ops_refs():
    from app.references import load_refs
    refs = load_refs(DATA, date(2026, 3, 17))
    ops = load_ops_refs(DATA, {h: x.timezone for h, x in refs.hospitals.items()}, set(refs.physicians))
    at = datetime(2026, 3, 17, 18, 20, tzinfo=ET)
    assert ops.p90("SYN-005", at) == 1 and ops.p90("SYN-009", at) == 2
    assert ops.requirement("SYN-008", at) == 2
    assert {pid for pid, r in ops.roster.items() if r.opt_in} == {"PHY-009", "PHY-010", "PHY-011", "PHY-014"}


def at(minutes=0):
    return datetime(2026, 4, 7, 22, tzinfo=timezone.utc) + timedelta(minutes=minutes)


def event(eid, kind, minute, cid="C", pid=None, **kwargs):
    defaults = {"consult_received": {"hospital_id": "H", "consult_type": "Stroke"}, "routing_attempt_failed": {"hospital_id": "H", "value": "retry_in_5m"}}
    row = EventInput(event_id=eid, event_time=at(minute), ingested_at=at(minute), event_type=kind,
                     consult_id=cid, physician_id=pid, **{**defaults.get(kind, {}), **kwargs})
    return Event(**{**row.model_dump(), "received_at": at(), "raw_json": {}})


def test_routing_failures_are_counted_with_last_time():
    events = (event("e1", "consult_received", 0), event("e2", "consult_triaged", 1),
              event("e3", "routing_attempt_failed", 2), event("e4", "routing_attempt_failed", 7))
    c = replay(events).consults["C"]
    assert (c.routing_failures, c.last_routing_failure_at) == (2, at(7))
    assert replay(tuple(reversed(events))).consults["C"] == c


def test_repeat_call_keeps_first_contact_and_counts_once_per_extra_receipt():
    first, repeat = event("e1", "consult_received", 0), event("e2", "consult_received", 7)
    c = replay((repeat, first, event("e3", "consult_triaged", 1))).consults["C"]
    assert c.received_at == at(0) and c.repeat_contacts == 1 and c.stage == "Triaged"
    # A first ring is the original call reaching a physician, not a repeat.
    ring = event("e4", "incoming_call_ringing", 2, pid="P", hospital_id="H")
    assert replay((first, ring)).consults["C"].repeat_contacts == 0


def test_repeat_call_on_another_consult_is_never_merged():
    state = replay((event("e1", "consult_received", 0, cid="A"), event("e2", "consult_received", 1, cid="B")))
    assert {c.repeat_contacts for c in state.consults.values()} == {0} and len(state.consults) == 2


# ---- Decisions against the sample day (skipped when gitignored data is absent) ----
import random
from app.decide.eligibility import evaluate
from app.decide.interventions import decide
from app.ops.coverage import Gap, surge_at
from app.ops.refs import OpsRefs, RosterEntry
from app.references import Hospital, Physician, Refs, Shift
from app.fixture import load_fixture

needs_data = pytest.mark.skipif(not (DATA / "event_stream.csv").exists(), reason="source data is gitignored")


def sample(now_text, shuffle=None):
    from app.references import load_refs
    now = datetime.fromisoformat(now_text)
    refs = load_refs(DATA, date(2026, 3, 17))
    ops = load_ops_refs(DATA, {h: x.timezone for h, x in refs.hospitals.items()}, set(refs.physicians))
    rows = {}
    for r in load_fixture(DATA / "event_stream.csv"):
        rows.setdefault(r.event_id, r)
    events = [Event(**{**r.model_dump(), "received_at": r.ingested_at, "raw_json": {}}) for r in rows.values() if r.event_time <= now]
    if shuffle is not None:
        random.Random(shuffle).shuffle(events)
    return decide(replay(tuple(events)), refs, ops, now)


def failures(item):
    return {c.physician_id: c.failed for c in item.candidates}


@needs_data
def test_sample_1820_top_problems_and_fixes():
    d = sample("2026-03-17T18:20:00-04:00")
    items = {i.id: i for i in d.items}
    assert [i.id for i in d.items[:2]] == ["stranded:CON-2110", "unassigned:CON-2105"]
    # PHY-002 is in a short video, not absent: CON-2110 is queued for them (lead notified, critical); that
    # reserves PHY-002, so CON-2105 has nobody left and escalates.
    queued = items["stranded:CON-2110"].fix
    assert (queued.kind, queued.physician_id, queued.approver) == ("reassign", "PHY-002", "coordinator") and "notify the clinical lead" in queued.action
    assert (items["unassigned:CON-2105"].fix.kind, items["unassigned:CON-2105"].fix.approver) == ("escalate", "clinical_lead")
    assert (items["handoff_needed:CON-2102"].fix.kind, items["handoff_needed:CON-2102"].fix.physician_id) == ("handoff", "PHY-004")
    assert items["unassigned:CON-2109"].fix.kind == "watch"
    # One item per consult: no duplicate alerts for the same patient.
    consults = [i.where.get("consult_id") for i in d.items if i.where.get("consult_id")]
    assert len(consults) == len(set(consults))
    assert [(s.hospital_id, s.count, s.until.astimezone(ET).strftime("%H:%M:%S")) for s in d.surges] == [("SYN-005", 5, "19:04:30")]


@needs_data
def test_sample_split_shift_exactly_one_eligible_others_fail_one_rule():
    d = sample("2026-03-17T18:20:00-04:00")
    items = {i.id: i for i in d.items}
    watch = next(i for i in d.items if i.id.startswith("watch:PHY-011"))
    assert watch.why["in_horizon"] and watch.fix.kind == "watch"
    assert failures(watch) == {"PHY-009": (), "PHY-010": ("credentialed_at_gap",), "PHY-011": ("no_schedule_overlap",),
                               "PHY-012": ("opted_in", "credentialed_at_gap", "no_schedule_overlap"),
                               "PHY-013": ("opted_in",), "PHY-014": ("trailing7d_plus_offer_at_most_60h",)}
    northfield = next(i for i in d.items if i.fix.kind == "split_shift" and "SYN-008" in (i.where.get("hospital_ids") or [i.where.get("hospital_id")]))
    assert (northfield.fix.kind, northfield.fix.physician_id) == ("split_shift", "PHY-009")
    assert next(i for i in d.items if i.id.startswith("gap:SYN-001")).fix.kind == "escalate"


@needs_data
def test_sample_decisions_ignore_arrival_order():
    base = sample("2026-03-17T18:20:00-04:00")
    shuffled = sample("2026-03-17T18:20:00-04:00", shuffle=7)
    assert [(i.id, i.severity, i.fix) for i in base.items] == [(i.id, i.severity, i.fix) for i in shuffled.items]


@needs_data
def test_sample_late_night_starter_turns_watch_into_one_offer():
    d = sample("2026-03-17T19:10:00-04:00")
    assert not any(i.id.startswith("watch:PHY-011") for i in d.items)
    offers = [i for i in d.items if i.fix.kind == "split_shift" and i.fix.physician_id == "PHY-009"]
    assert len(offers) == 1 and {"SYN-004", "SYN-005", "SYN-008"} <= set(offers[0].where["hospital_ids"])


def tiny(last_end, hours, next_start=None, online=0):
    refs = Refs({"H": Hospital("H", "America/New_York")}, {"P": Physician("P", (Shift(et(7, 8), et(7, 20)),)), "R": Physician("R")},
                {"P": frozenset({"H"}), "R": frozenset({"H"})})
    ops = OpsRefs({}, {"H": ((0, 0, 1),)}, {"R": RosterEntry("Day", True, last_end, next_start, hours, online, "sms", 0)})
    gap = Gap("H", et(7, 20), et(7, 22), "hard", 1, 0, 0, False, True, ())
    return evaluate(gap, [gap], refs, ops, et(7, 18))[0]


def test_rest_and_hours_boundaries_pass_exactly():
    assert tiny(et(7, 10), 58).eligible  # exactly 10 h rest, exactly 60 h
    assert tiny(et(7, 10, 1), 58).failed == ("rest_at_start_at_least_10h",)
    assert tiny(et(7, 10), 58.5).failed == ("trailing7d_plus_offer_at_most_60h",)
    assert tiny(et(7, 0), 0, next_start=et(7, 22)).eligible  # ending exactly at the next shift is not an overlap
    assert tiny(et(7, 0), 0, next_start=et(7, 21, 59)).failed == ("no_schedule_overlap",)


def test_online_time_counts_against_an_immediate_offer():
    refs = Refs({"H": Hospital("H", "America/New_York")}, {"R": Physician("R")}, {"R": frozenset({"H"})})
    ops = OpsRefs({}, {}, {"R": RosterEntry("Day", True, et(6, 0), None, 0, 15, "sms", 0)})
    now_gap = Gap("H", et(7, 18), et(7, 19), "hard", 1, 0, 0, False, True, ())
    assert evaluate(now_gap, [now_gap], refs, ops, et(7, 18))[0].failed == ("useful_duration_at_least_2h",)


def test_surge_requires_strictly_more_than_p90():
    ops = OpsRefs({("H", 1, 18): (0.4, 2.0)}, {}, {})  # 2026-04-07 is a Tuesday
    received = [et(7, 18, 0), et(7, 18, 10)]
    assert surge_at(ops, "H", received, et(7, 18, 30)) is False
    assert surge_at(ops, "H", [*received, et(7, 18, 20)], et(7, 18, 30)) is True
    assert surge_at(ops, "H", received, et(7, 19, 30)) is None  # no baseline row: unknown, not zero


def two_candidates(a=None, b=None):
    """Hospital H needs 1 physician and nobody is on shift; A and B are both fully eligible off-shift physicians."""
    base = dict(role="Day", opt_in=True, last_shift_end=et(7, 0), next_shift_start=None, hours_last_7d=20, minutes_to_online=0, channel="sms", declines_30d=0)
    roster = {"A": RosterEntry(**{**base, **(a or {})}), "B": RosterEntry(**{**base, **(b or {})})}
    refs = Refs({"H": Hospital("H", "America/New_York")}, {p: Physician(p) for p in roster}, {p: frozenset({"H"}) for p in roster})
    ops = OpsRefs({("H", 1, h): (0.5, 5.0) for h in range(24)}, {"H": ((0, 0, 1),)}, roster)
    return decide(replay(()), refs, ops, et(7, 18))


def offer_for(d):
    return next(i for i in d.items if i.fix.kind == "split_shift")


def test_two_eligible_candidates_rank_by_the_stated_order_and_the_winner_changes_with_the_data():
    # Equal on everything: the stable tie-breaker is the physician ID.
    item = offer_for(two_candidates())
    assert item.fix.physician_id == "A" and [c.physician_id for c in item.candidates if c.eligible] == ["A", "B"]
    assert any("B: eligible, ranked lower" in alt for alt in item.fix.alternatives)  # the runner-up is shown, not hidden
    assert "chosen over B because A ties on every ranking step; the lower physician ID goes first" in item.fix.reason
    # Each ranking component, in order, flips the winner on its own [doc 5.2], and the reason names that component.
    assert offer_for(two_candidates(a={"minutes_to_online": 30})).fix.physician_id == "B"  # here A then fails R6 outright
    flips = {"declines_30d": (2, "declined fewer offers in 30 days (0 vs 2)"),
             "hours_last_7d": (40, "worked fewer hours in the last 7 days")}
    for field, (value, words) in flips.items():
        fix = offer_for(two_candidates(a={field: value})).fix
        assert fix.physician_id == "B" and f"chosen over A because B {words}" in fix.reason, (field, fix.reason)
    # A rule failure removes a candidate entirely; ranking never overrides a rule.
    assert offer_for(two_candidates(a={"opt_in": False}, b={"declines_30d": 9})).fix.physician_id == "B"


@pytest.mark.parametrize("hour,mean,p90", [
    ("18:30", "1", "2"), ("18:00:01", "1", "2"), ("18:00+04:00", "1", "2"),
    ("18:00", "nan", "2"), ("18:00", "1", "inf"),
])
def test_baseline_rejects_silent_hour_truncation_and_nonfinite_values(tmp_path, hour, mean, p90):
    with pytest.raises(ValueError):
        load(tmp_path, baseline=(f"H,H,weekday,{hour},{mean},{p90},12",))


@pytest.mark.parametrize("day,hour", [(7, 18), (0, 24), (-1, 18)])
def test_local_baseline_rejects_unreachable_keys(tmp_path, day, hour):
    write(tmp_path)
    (tmp_path / "baseline_hourly_volume.csv").write_text(
        f"hospital_id,weekday,hour_local,mean_consults,p90_consults\nH,{day},{hour},1,2\n")
    (tmp_path / "coverage_requirements.csv").write_text("hospital_id,start_hour_local,end_hour_local,minimum_available\n")
    (tmp_path / "physicians_off_shift_roster.csv").write_text("physician_id,role,opted_in,last_shift_ended,next_shift_start,next_shift_end,hours_worked_7d,minutes_to_online,preferred_channel,declined_offers_30d\n")
    with pytest.raises(ValueError, match="out of range"):
        load_ops_refs(tmp_path, {"H": "America/New_York"}, {"R1"})


def test_baseline_expected_arrivals_weights_partial_hours_and_missing_weekends(tmp_path):
    from app.ops.demand import expected_arrivals
    ops = load(tmp_path, baseline=("H,H,weekday,18:00,6,9,12", "H,H,weekday,19:00,12,15,12"))
    assert expected_arrivals(ops, "H", et(7,18,20), et(7,20)) == pytest.approx(16)
    assert expected_arrivals(ops, "H", et(7,18,20), et(7,20,1)) is None
    assert expected_arrivals(ops, "H", et(11,18,20), et(11,20)) is None
    assert expected_arrivals(ops, "H", et(7,18,20), et(7,18,20)) == 0


@pytest.mark.parametrize("start,end,hours", [
    ("2026-11-01T05:30:00+00:00", "2026-11-01T07:30:00+00:00", {1: 6, 2: 12}),
    ("2026-03-08T06:30:00+00:00", "2026-03-08T07:30:00+00:00", {1: 6, 3: 12}),
])
def test_baseline_expected_arrivals_integrates_elapsed_time_across_dst(start, end, hours):
    from app.ops.demand import expected_arrivals
    from app.ops.refs import OpsRefs
    ops = OpsRefs({("H",6,h): (mean,20) for h,mean in hours.items()}, {}, {})
    expected = 15 if len(hours) == 2 and 2 in hours else 9
    assert expected_arrivals(ops,"H",datetime.fromisoformat(start),datetime.fromisoformat(end)) == pytest.approx(expected)
