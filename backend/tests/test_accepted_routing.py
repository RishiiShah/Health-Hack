"""Accepted capacity must become observed operational capacity, with real counters and site limits."""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
import pytest
from app.decide.interventions import decide
from app.engine.replay import replay
from app.models import Event
from app.ops.coverage import SplitShift, current_coverage, remaining_need
from app.ops.refs import OpsRefs, RosterEntry
from app.references import Hospital, Physician, Refs, Shift
from app.service import workload_view

START = datetime(2026, 4, 7, 22, 30, tzinfo=timezone.utc)
END = START + timedelta(hours=2)


def event(eid, kind, at, pid=None, cid=None, **kwargs):
    return Event(event_id=eid, event_type=kind, event_time=at, ingested_at=at, received_at=at,
                 physician_id=pid, consult_id=cid, raw_json={}, **kwargs)


def world(required=1, scheduled=False):
    refs = Refs({h: Hospital(h, "America/New_York") for h in ("G", "H")},
                {"J": Physician("Joiner"), **({"P": Physician("Peer", (Shift(START - timedelta(hours=2), START + timedelta(minutes=30)),))} if scheduled else {})},
                {"J": frozenset({"G", "H"}), **({"P": frozenset({"G"})} if scheduled else {})})
    ops = OpsRefs({(h, 1, hour): (0.5, 100) for h in refs.hospitals for hour in range(24)},
                  {"G": ((0, 0, required),), "H": ((0, 0, 0),)},
                  {"J": RosterEntry("Day", True, START - timedelta(hours=12), None, 20, 10, "app_push", 0)})
    accepted = (SplitShift("J", START, END, frozenset({"G"}), START - timedelta(minutes=20)),)
    return refs, ops, accepted


@pytest.mark.parametrize("now,seen,routable", [
    (START, None, False),  # an estimate alone is not a login
    (START - timedelta(seconds=1), START - timedelta(minutes=5), False),
    (START, START - timedelta(minutes=5), True),
    (START + timedelta(minutes=5), None, False),  # late arrival reopens forecast capacity
    (START + timedelta(minutes=10), START + timedelta(minutes=10), True),
    (END, START, False),  # half-open shift end
])
def test_routing_requires_observed_arrival_within_shift(now, seen, routable):
    refs, ops, accepted = world()
    events = () if seen is None else (event("online", "shift_started", seen, pid="J"),)
    state = replay(events)
    d = decide(state, refs, ops, now, accepted=accepted)
    v = d.views["J"]
    assert v.routable is routable
    coverage = {c.hospital_id: c for c in current_coverage(state, refs, ops, d.views, now)}
    assert coverage["G"].routable == (("J",) if routable else ())
    assert coverage["H"].routable == ()
    assert refs.physicians["J"].shifts == ()  # no mutation of canonical references
    if routable:
        assert v.credentialed_hospitals == frozenset({"G", "H"})
        assert v.allowed_hospitals == frozenset({"G"})


def test_joiner_routes_then_tracks_real_calls_cooldown_and_shift_end():
    refs, ops, accepted = world()
    events = [event("online", "shift_started", START, pid="J"),
              event("receive", "consult_received", START, cid="C", hospital_id="G", consult_type="Stroke"),
              event("triage", "consult_triaged", START, cid="C")]
    d = decide(replay(events), refs, ops, START, accepted=accepted)
    fix = next(i.fix for i in d.items if i.id == "unassigned:C")
    assert (fix.kind, fix.physician_id) == ("assign", "J")
    assert d.views["J"].consults_this_shift == 0  # no modeled seed inserted into observed workload
    events += [event("assign", "physician_assigned", START + timedelta(minutes=1), pid="J", cid="C"),
               event("call", "incoming_call_started", START + timedelta(minutes=2), pid="J", cid="C")]
    busy = decide(replay(events), refs, ops, START + timedelta(minutes=3), accepted=accepted).views["J"]
    assert not busy.routable and busy.consults_this_shift == busy.calls_this_shift == 1
    events.append(event("end", "incoming_call_ended", START + timedelta(minutes=4), pid="J", cid="C", value="phone_complete"))
    assert "cooldown" in decide(replay(events), refs, ops, START + timedelta(minutes=5), accepted=accepted).views["J"].exclusion_reasons
    ready = decide(replay(events), refs, ops, START + timedelta(minutes=6), accepted=accepted)
    assert ready.views["J"].routable
    row = workload_view(SimpleNamespace(state=replay(events), refs=refs, as_of=START + timedelta(minutes=6)), ready)["items"][0]
    assert row["shift_end"] == END.isoformat() and row["consults"] == row["calls"] == 1
    done = decide(replay(events), refs, ops, END, accepted=accepted)
    assert "off_shift" in done.views["J"].exclusion_reasons
    assert any(g.hospital_id == "G" and g.kind == "hard" and g.start == END for g in done.gaps)


def test_arrived_joiner_is_not_counted_twice_or_routed_outside_offer():
    refs, ops, accepted = world(required=2)
    state = replay((event("online", "shift_started", START, pid="J"),
                    event("g", "consult_received", START, cid="CG", hospital_id="G", consult_type="Stroke"),
                    event("h", "consult_received", START, cid="CH", hospital_id="H", consult_type="Stroke")))
    d = decide(state, refs, ops, START, accepted=accepted)
    assert any(i.id == "now_gap:G" for i in d.items)
    assert remaining_need(state, refs, ops, d.views, START, accepted, ("G",), START, END) == {"G": 1}
    assert next(i.fix for i in d.items if i.id == "unassigned:CH").physician_id is None


def test_handoff_to_and_from_joiner_uses_effective_shift_bounds():
    refs, ops, accepted = world(scheduled=True)
    events = (event("online", "shift_started", START, pid="J"),
              event("receive", "consult_received", START, cid="C", hospital_id="G", consult_type="Stroke"),
              event("assign", "physician_assigned", START + timedelta(minutes=1), pid="P", cid="C"))
    d = decide(replay(events), refs, ops, START + timedelta(minutes=1), accepted=accepted)
    fix = next(i.fix for i in d.items if i.id == "handoff_needed:C")
    assert (fix.kind, fix.physician_id) == ("handoff", "J")
    owned = (*events, event("transfer", "physician_assigned", START + timedelta(minutes=2), pid="J", cid="C"))
    d = decide(replay(owned), refs, ops, END - timedelta(minutes=30), accepted=accepted)
    assert next(i.fix for i in d.items if i.id == "handoff_needed:C").kind == "escalate"


def test_api_accept_arrive_snapshot_and_shift_end(db_url, tmp_path):
    from fastapi.testclient import TestClient
    from conftest import ADMIN, COORD, LEAD, TEST_AUTH
    from app.clock import FixedClock
    from app.main import create_app
    from app.models import EventInput
    refs, ops, _ = world()
    speech = SimpleNamespace(available=False, audio=lambda text: None, conn=SimpleNamespace(close=lambda: None))
    api = create_app(db_url, FixedClock(START - timedelta(minutes=20)), auth=TEST_AUTH,
                     references=(refs, ops), history_path=tmp_path / "absent.csv", speech=speech, sweep_s=0)
    with TestClient(api) as client:
        proposed = client.post("/offers", headers=COORD, json={"gap_id": "gap:G", "physician_id": "J",
                              "start": START.isoformat(), "end": END.isoformat(), "hospitals": ["G"]})
        assert proposed.status_code == 200, proposed.text
        oid = proposed.json()["offer_id"]
        assert client.post(f"/offers/{oid}/approve", headers=LEAD).status_code == 200
        token = client.post("/admin/physician-tokens", headers=ADMIN, json={"physician_id": "J"}).json()["token"]
        doc = {"Authorization": f"Bearer {token}"}
        assert client.post(f"/me/offers/{oid}/accept", headers=doc).json()["state"] == "Accepted"
        assert client.post("/admin/clock", headers=ADMIN, json={"at": START.isoformat()}).status_code == 200
        snap = client.get("/snapshot", headers=COORD).json()
        assert not snap["physicians"]["items"][0]["routable"]
        events = [event("online", "shift_started", START, pid="J"),
                  event("receive", "consult_received", START, cid="C", hospital_id="G", consult_type="Stroke")]
        rows = [e.model_dump(mode="json", include=set(EventInput.model_fields)) for e in events]
        assert client.post("/events", headers=ADMIN, json=rows).status_code == 200
        snap = client.get("/snapshot", headers=COORD).json()
        assert snap["physicians"]["items"][0]["routable"]
        assert snap["physicians"]["items"][0]["routing_hospitals"] == ["G"]
        assert snap["coverage"]["hospitals"][0]["cells"][0]["physician_ids"] == ["J"]
        assert snap["workload"]["items"][0]["shift_end"] == END.isoformat()
        assert snap["headline"]["hospitals_short_now"] == 0
        fix = next(i["fix"] for i in snap["queue"]["items"] if i["id"] == "unassigned:C")
        assert (fix["kind"], fix["physician_id"]) == ("assign", "J")
        assert client.get("/me/shift", headers=doc).json()["shift_end"] == END.isoformat()
        outside = event("outside", "consult_received", START, cid="CH", hospital_id="H", consult_type="Stroke")
        assert client.post("/events", headers=ADMIN, json=outside.model_dump(mode="json", include=set(EventInput.model_fields))).status_code == 200
        refused = client.post("/interventions", headers=COORD,
                              json={"kind": "reassign", "item_id": "unassigned:CH", "physician_id": "J"})
        assert refused.status_code == 422 and refused.json()["error"]["code"] == "not_eligible"
        assert client.post("/admin/clock", headers=ADMIN, json={"at": END.isoformat()}).status_code == 200
        snap = client.get("/snapshot", headers=COORD).json()
        assert "off_shift" in snap["physicians"]["items"][0]["exclusion_reasons"]
        assert snap["coverage"]["hospitals"][0]["cells"][0]["physician_ids"] == []
