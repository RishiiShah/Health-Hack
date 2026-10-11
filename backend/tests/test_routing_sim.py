"""Step 7: routing model [B p3] and split-shift trap check, on small synthetic days (no sample IDs)."""
from dataclasses import replace
from datetime import datetime, timedelta
import pytest
from zoneinfo import ZoneInfo
from app.decide.routing_sim import _Doc, _arrivals, demand_pace, observed_service, route_key, simulate, threshold, trap_check
from app.engine.physician import PhysicianView
from app.engine.replay import replay
from app.models import Event, EventInput
from app.ops.refs import OpsRefs, RosterEntry
from app.references import Hospital, Physician, Refs, Shift

ET = ZoneInfo("America/New_York")


def et(hh, mm=0):
    return datetime(2026, 4, 7, hh, mm, tzinfo=ET)  # a Tuesday


def doc(pid, count=0, hospitals=("G",), answered=None, free_at=None, start=et(17), end=et(23), limit=6):
    return _Doc(pid, start, end, frozenset(hospitals), count, limit, answered, free_at or start)


def test_low_volume_first_then_fewest_then_least_recent_answer():
    assert threshold(et(8)) == 6 and threshold(et(17)) == 4 and threshold(et(16, 59)) == 6
    # 6 on a day shift is still low volume; 5 on a night shift is not.
    assert sorted(["day", "night"], key=lambda p: route_key(6 if p == "day" else 5, 6 if p == "day" else 4, None, p)) == ["day", "night"]
    assert route_key(3, 6, et(18), "B") < route_key(3, 6, et(18, 5), "A")  # answered longer ago wins the tie
    assert route_key(3, 6, None, "B") < route_key(3, 6, et(17), "A")  # never answered counts as longest ago


def test_busy_and_cooldown_exclude_and_failures_retry_every_5_minutes():
    # One physician, two consults one minute apart: the second waits for 6.5 min service + 2 min cooldown.
    run = simulate("x", {"P": doc("P")}, [(et(18), "G", 6.5), (et(18, 1), "G", 6.5)], et(19))
    assert run.load("P") == 2 and run.failures == {"G": 2}  # tried at 18:01 and 18:06, routed at 18:11
    assert run.waits["G"] == (0.0, 10.0)
    # Nobody credentialed: retried until the window ends, then counted as unrouted with its censored wait.
    lost = simulate("x", {"P": doc("P", hospitals=("O",))}, [(et(18), "G", 6.5)], et(18, 20))
    assert lost.failures == {"G": 4} and lost.unrouted == {"G": 1} and lost.waits["G"] == (20.0,)


def test_simulator_carries_existing_call_cooldown_and_ringing():
    from app.decide.routing_sim import _doctors
    from app.ops.detect import views_at
    refs = Refs({"G": Hospital("G", "America/New_York")},
                {"P": Physician("P", (Shift(et(17), et(23)),))}, {"P": frozenset({"G"})})
    ops = OpsRefs({}, {}, {})
    receipt = ev("receive", "consult_received", -2, pid=None, hospital_id="G", consult_type="Stroke")
    for kind, events, available_at, wait in (
        ("cooldown", (receipt, ev("call", "incoming_call_started", -1),
                      ev("end", "incoming_call_ended", -0.5, value="phone_complete")), et(18, 1) + timedelta(seconds=30), 5.0),
        ("ringing", (receipt, ev("ring", "incoming_call_ringing", -0.5)), et(18, 7), 10.0),
    ):
        state = replay(events)
        views = views_at(state, refs, et(18))
        assert not views["P"].routable and kind in views["P"].exclusion_reasons
        docs = _doctors(state, refs, ops, views, et(18), et(19), (), 7, timedelta(minutes=5))
        assert docs["P"].free_at == available_at
        run = simulate(kind, docs, [(et(18), "G", 5.0)], et(19))
        assert run.waits["G"] == (wait,) and run.load("P") == 1


def test_shift_bounds_are_half_open():
    run = simulate("x", {"P": doc("P", end=et(18))}, [(et(18), "G", 1)], et(18, 3))
    assert run.load("P") == 0 and run.unrouted == {"G": 1}


def test_demand_is_deterministic_and_missing_baseline_is_unknown():
    refs = Refs({"G": Hospital("G", "America/New_York"), "U": Hospital("U", "America/New_York")}, {}, {})
    ops = OpsRefs({("G", 1, 18): (2.0, 3.0)}, {}, {})
    arrivals, unknown = _arrivals(replay(()), ops, refs, et(18), et(19), {"*": 5.0}, {})
    assert [(t.astimezone(ET).strftime("%H:%M"), h) for t, h, _ in arrivals] == [("18:15", "G"), ("18:45", "G")]
    assert unknown == ("U",)
    surged, _ = _arrivals(replay(()), ops, refs, et(18), et(19), {"*": 5.0}, {"G": 4.0})
    assert len(surged) == 4  # the surge scenario continues the observed trailing rate
    quiet, _ = _arrivals(replay(()), ops, refs, et(18), et(19), {"*": 5.0}, {}, pace=0.5)
    assert [t.astimezone(ET).strftime("%H:%M") for t, _, _ in quiet] == ["18:30"]  # today's pace halves expected demand


def test_todays_pace_is_observed_over_usual_and_pulled_toward_a_usual_day():
    """[A51] Last two hours: 8 consults where the baseline expects 4 per hour, with 5 consults of usual day on both sides."""
    refs = Refs({"G": Hospital("G", "America/New_York")}, {}, {})
    ops = OpsRefs({("G", 1, h): (4.0, 6.0) for h in range(24)}, {}, {})
    received = lambda n: replay(tuple(ev(f"E{i}", "consult_received", -i * 10, pid=None, cid=f"C{i}", hospital_id="G", consult_type="Stroke") for i in range(n)))
    assert demand_pace(received(8), refs, ops, et(18)) == 1.0  # (8 + 5) / (8 + 5): a usual day
    assert demand_pace(received(2), refs, ops, et(18)) == 7 / 13  # quiet: the simulator also runs at about half
    assert demand_pace(received(0), refs, OpsRefs({}, {}, {}), et(18)) is None  # no baseline: no pace, no extra scenario


def ev(eid, kind, minute, pid="P", cid="C", **kw):
    row = EventInput(event_id=eid, event_time=et(18) + timedelta(minutes=minute), ingested_at=et(18) + timedelta(minutes=minute),
                     event_type=kind, consult_id=cid, physician_id=pid, **kw)
    return Event(**{**row.model_dump(), "received_at": row.ingested_at, "raw_json": {}})


def test_service_time_is_measured_from_calls_and_video():
    events = (ev("1", "consult_received", 0, pid=None, hospital_id="G", consult_type="Stroke"),
              ev("2", "incoming_call_started", 1), ev("3", "incoming_call_ended", 3),
              ev("4", "video_started", 10), ev("5", "video_ended", 15),
              ev("6", "video_ended", 30, cid="C"))  # an end without its start is skipped, not guessed
    assert observed_service(events, replay(events)) == {"Stroke": 7.0, "*": 7.0}
    assert observed_service((), replay(())) == {}


def view(pid, count, hospitals, state="Available"):
    return PhysicianView(pid, state, "Available", "Online", state == "Available", () if state == "Available" else ("busy",), (),
                         count, count, 0, 300, frozenset(hospitals), None)


def trap_day():
    """Gap hospital G and a busy other hospital O. The joiner J is credentialed at both, the trap's precondition."""
    refs = Refs({"G": Hospital("G", "America/New_York"), "O": Hospital("O", "America/New_York")},
                {"P1": Physician("P1", (Shift(et(8), et(23)),)), "P2": Physician("P2", (Shift(et(8), et(23)),)), "J": Physician("J")},
                {"P1": frozenset({"G", "O"}), "P2": frozenset({"O"}), "J": frozenset({"G", "O"})})
    baseline = {(h, 1, hour): (mean, mean) for h, mean in (("G", 4.0), ("O", 6.0)) for hour in (18, 19)}
    ops = OpsRefs(baseline, {}, {"J": RosterEntry("Day", True, et(0), None, 20, 0, "sms", 0)})
    views = {"P1": view("P1", 10, {"G", "O"}), "P2": view("P2", 12, {"O"})}
    return refs, ops, views


def test_unguarded_joiner_floods_other_hospitals_and_guard_contains_it():
    refs, ops, views = trap_day()
    check = trap_check(replay(()), refs, ops, views, et(18), "J", et(18), et(20), {"G"}, {"*": 6.5})
    none, trap, guarded = check.scenarios["baseline"]
    assert check.trap_shown and check.spill["baseline"] > 0 and "O" in trap.sites("J")
    assert check.seed == 10  # max(day threshold + 1, fewest consults among peers at the gap hospital)
    assert guarded.sites("J") == {"G"} and check.passed, [c for c in check.criteria if not c.passed]
    assert guarded.wait({"G"}) <= none.wait({"G"}) and check.relief["baseline"] >= 0
    assert check == trap_check(replay(()), refs, ops, views, et(18), "J", et(18), et(20), {"G"}, {"*": 6.5})  # deterministic


def test_trap_check_needs_observed_service_time():
    refs, ops, views = trap_day()
    assert trap_check(replay(()), refs, ops, views, et(18), "J", et(18), et(20), {"G"}, {}) is None


@pytest.mark.parametrize("missing_hour", [None, 19])
def test_incomplete_demand_cannot_pass_trap_even_when_partial_constraints_pass(missing_hour):
    refs, ops, views = trap_day()
    ops = replace(ops, baseline={k: v for k, v in ops.baseline.items() if k[0] != "O" or (missing_hour is not None and k[2] != missing_hour)})
    check = trap_check(replay(()), refs, ops, views, et(18), "J", et(18), et(20), {"G"}, {"*": 6.5})
    assert check.unknown_demand == ("O",) and not check.passed
    assert all(c.passed for c in check.criteria)  # incomplete data must be distinguished from a failed constraint
    assert check.scenarios["baseline"][2].sites("J") <= {"G"}


def test_missing_demand_is_retained_when_later_surge_scenario_has_a_rate(monkeypatch):
    import app.decide.routing_sim as sim
    from app.ops.coverage import Surge
    refs, ops, views = trap_day()
    ops = replace(ops, baseline={k: v for k, v in ops.baseline.items() if k[0] != "O"})
    monkeypatch.setattr(sim, "surges", lambda *args: [Surge("O", 6, 1, et(19))])
    check = trap_check(replay(()), refs, ops, views, et(18), "J", et(18), et(20), {"G"}, {"*": 6.5})
    assert "surge_continues" in check.scenarios
    assert check.unknown_demand == ("O",) and not check.passed


def test_temporarily_unavailable_physician_takes_no_simulated_calls():
    refs, ops, views = trap_day()
    views["P1"] = view("P1", 3, {"G", "O"}, state="Temporarily Unavailable")
    check = trap_check(replay(()), refs, ops, views, et(18), "J", et(18), et(20), {"G"}, {"*": 6.5})
    assert all(run.load("P1") == 0 for run in check.scenarios["baseline"])
    assert check.seed == 7  # an unavailable peer's low count does not lower the joiner's seed


def test_peer_load_bound_applies_only_to_baseline_but_all_scenarios_keep_other_constraints(monkeypatch):
    """A concentrated forecast surge can legitimately make the joiner busier than peers."""
    import app.decide.routing_sim as sim
    from app.ops.coverage import Surge
    refs, ops, views = trap_day()
    views["P1"] = view("P1", 10, {"G", "O"}, state="Temporarily Unavailable")
    monkeypatch.setattr(sim, "surges", lambda *args: [Surge("G", 40, 4, et(19))])
    monkeypatch.setattr(sim, "demand_pace", lambda *args: 2.0)
    check = trap_check(replay(()), refs, ops, views, et(18), "J", et(18), et(20), {"G"}, {"*": 1.0})
    assert set(check.scenarios) == {"baseline", "todays_pace", "surge_continues"}
    keys = {c.key for c in check.criteria}
    assert {k for k in keys if k.endswith(":joiner_not_above_busiest_peer")} == {"baseline:joiner_not_above_busiest_peer"}
    for scenario in check.scenarios:
        assert {f"{scenario}:{key}" for key in ("joiner_only_at_gap_hospitals", "gap_wait_not_worse", "peers_within_tolerance")} <= keys
    guarded = check.scenarios["surge_continues"][2]
    assert guarded.load("J") > max(guarded.load("P1"), guarded.load("P2")) + 1
    assert check.passed
