"""Step 8: offer state machine on a tiny synthetic day [doc 6, edge cases in doc 7]. Needs Postgres (conftest)."""
import threading
from dataclasses import replace
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import psycopg
import pytest
from app.act import offers as offers_module
from app.act.offers import Context, OfferDesk, OfferError
from app.decide.interventions import decide
from app.engine.replay import replay
from app.ops.refs import OpsRefs, RosterEntry
from app.references import Hospital, Physician, Refs, Shift

ET = ZoneInfo("America/New_York")


def et(hh, mm=0, ss=0):
    return datetime(2026, 4, 7, hh, mm, ss, tzinfo=ET)  # a Tuesday


class World:
    """Hospital G needs 1 physician all day and nobody is on shift: a hard gap until someone accepts.
    H has no requirement (never short). R1 and R2 are eligible off-shift physicians; R3 has not opted in."""
    def __init__(self):
        self.now = et(18)
        roster = {p: RosterEntry("Day", p != "R3", et(6), None, 20 + n, 10, "sms", 0) for n, p in enumerate(("R1", "R2", "R3"))}
        self.refs = Refs({"G": Hospital("Glen", "America/New_York"), "H": Hospital("Hill", "America/New_York")},
                         {p: Physician(p) for p in roster}, {p: frozenset({"G", "H"}) for p in roster})
        self.ops = OpsRefs({(h, 1, hour): (0.5, 5.0) for h in ("G", "H") for hour in range(24)},
                           {"G": ((0, 0, 1),), "H": ((0, 0, 0),)}, roster)
        self.state = replay(())

    def context(self):
        return Context(self.state, self.refs, self.ops, self.now, 7)


@pytest.fixture
def world():
    return World()


@pytest.fixture
def desk(db_url, world):
    return OfferDesk(db_url, world.context)


def iso(t):
    return t.astimezone(timezone.utc).isoformat()  # payload times are UTC with an explicit offset


def propose(desk, pid="R1", hospitals=("G",), key=None):
    return desk.propose("gap:G", pid, et(18, 30), et(21), hospitals, "coordinator", idempotency_key=key)


def refusal(fn):
    with pytest.raises(OfferError) as exc:
        fn()
    return exc.value.status, exc.value.code


def test_happy_path_propose_approve_send_accept(desk, world):
    o = propose(desk)
    assert o["state"] == "PROPOSED" and o["id"].startswith("OFR-")
    world.now = et(18, 5)
    sent = desk.approve(o["id"], "Dr. Lead")
    assert (sent["state"], sent["approved_by"], sent["expires_at"]) == ("SENT", "Dr. Lead", iso(et(18, 15)))
    (msg,) = desk.outbox()
    assert msg["kind"] == "offer" and "Glen" in msg["body"] and "6:30 PM to 9:00 PM" in msg["body"] and "Expires at 6:15 PM" in msg["body"]
    world.now = et(18, 9)
    assert desk.accept(o["id"], "R1")["state"] == "ACCEPTED"
    assert desk.accepted() == (("R1", et(18, 30), et(21), frozenset({"G"})),)
    trail = [(a["command"], a["from_state"], a["to_state"], a["revision"]) for a in desk.audit("gap:G")]
    assert trail == [("propose", None, "PROPOSED", 7), ("approve", "PROPOSED", "APPROVED", 7), ("send", "APPROVED", "SENT", 7),
                     ("accept", "SENT", "ACCEPTED", 7)]


def test_accepted_shift_feeds_back_into_decisions(desk, world):
    o = propose(desk)
    desk.approve(o["id"], "lead")
    desk.accept(o["id"], "R1")
    d = decide(world.state, world.refs, world.ops, world.now, desk.history(world.now), desk.accepted())
    assert not [g for g in d.gaps if g.hospital_id == "G" and g.kind == "hard" and g.start >= et(18, 30) and g.end <= et(21)]
    assert desk.history(world.now).accepted == {"R1": ((et(18, 30), et(21)),)}  # R4/R5 now see the accepted hours
    # Even without the desk's history, decide() never offers R1 the hours R1 already accepted.
    bare = decide(world.state, world.refs, world.ops, world.now, accepted=desk.accepted())
    assert not [i for i in bare.items if i.fix.kind == "split_shift" and i.fix.physician_id == "R1"]


def test_double_accept_first_wins_second_is_told_no_longer_needed(desk, world):
    a, b = propose(desk, "R1"), propose(desk, "R2")
    desk.approve(a["id"], "lead"), desk.approve(b["id"], "lead")
    world.now = et(18, 3)
    assert desk.accept(a["id"], "R1")["state"] == "ACCEPTED"
    assert desk.offer(b["id"]).state == "WITHDRAWN"
    assert [m["kind"] for m in desk.outbox() if m["offer_id"] == b["id"]] == ["offer", "notice"]
    world.now = et(18, 3, 30)
    assert refusal(lambda: desk.accept(b["id"], "R2")) == (409, "already_filled")
    assert desk.audit("gap:G")[-1]["command"] == "accept:refused"  # the late reply is on record


def test_reply_at_exactly_expiry_is_late_and_next_candidate_is_proposed(desk, world):
    o = propose(desk)
    desk.approve(o["id"], "lead")
    world.now = et(18, 10)  # expires_at, half-open [A42]
    assert refusal(lambda: desk.accept(o["id"], "R1")) == (409, "expired")
    assert desk.offer(o["id"]).state == "EXPIRED"
    (nxt,) = [x for x in desk.offers() if x.state == "PROPOSED"]
    assert (nxt.physician_id, nxt.replaces, nxt.proposed_by) == ("R2", o["id"], "system")  # still needs the lead


def test_no_reply_expires_on_sweep_and_next_candidate_is_proposed(desk, world):
    o = propose(desk)
    desk.approve(o["id"], "lead")
    world.now = et(18, 9, 59)
    assert desk.sweep()["changed"] == []
    world.now = et(18, 10)
    assert o["id"] in desk.sweep()["changed"]
    assert {(x.physician_id, x.state) for x in desk.offers()} == {("R1", "EXPIRED"), ("R2", "PROPOSED")}


def test_decline_proposes_the_next_physician_never_the_same_one(desk, world):
    o = propose(desk)
    desk.approve(o["id"], "lead")
    assert desk.decline(o["id"], "R1")["state"] == "DECLINED"
    nxt = next(x for x in desk.offers() if x.state == "PROPOSED")
    desk.approve(nxt.id, "lead")
    desk.decline(nxt.id, "R2")
    # R3 has not opted in and R1/R2 were already asked: nobody left, so nothing is proposed and the audit says escalate.
    assert [x.state for x in desk.offers()] == ["DECLINED", "DECLINED"]
    assert desk.audit("gap:G")[-1]["command"] == "next_candidate:none"


def test_conflicting_and_repeated_replies(desk, world):
    o = propose(desk)
    desk.approve(o["id"], "lead")
    first = desk.accept(o["id"], "R1")
    assert desk.accept(o["id"], "R1") == first  # same reply twice: same answer
    assert refusal(lambda: desk.decline(o["id"], "R1")) == (409, "conflicting_reply")
    assert desk.offer(o["id"]).state == "ACCEPTED"


def test_idempotency_key_replays_the_stored_result(desk, world):
    o = propose(desk, key="k1")
    assert propose(desk, key="k1") == o and len(desk.offers()) == 1
    assert refusal(lambda: desk.propose("gap:G", "R2", et(18, 30), et(21), ("G",), "coordinator", idempotency_key="k1")) == (409, "idempotency_key_reused")
    assert refusal(lambda: desk.accept(o["id"], "R1", idempotency_key="k2")) == (409, "conflicting_reply")
    desk.approve(o["id"], "lead")
    assert refusal(lambda: desk.accept(o["id"], "R1", idempotency_key="k2")) == (409, "conflicting_reply")  # a stored refusal stays a refusal


def test_lead_rejects(desk, world):
    o = propose(desk)
    assert desk.reject(o["id"], "lead", "prefer to escalate")["state"] == "REJECTED"
    assert refusal(lambda: desk.approve(o["id"], "lead")) == (409, "not_proposed")
    assert propose(desk)["state"] == "PROPOSED"  # R7 frees up once the offer is closed


def test_gap_filled_elsewhere_withdraws_sent_and_cancels_pending(desk, world):
    a, b = propose(desk, "R1"), propose(desk, "R2")
    desk.approve(a["id"], "lead")
    # A scheduled physician credentialed at G turns up: the gap closes without our offers.
    world.refs = Refs(world.refs.hospitals, {**world.refs.physicians, "P": Physician("P", (Shift(et(8), et(23)),))},
                      {**world.refs.credentials, "P": frozenset({"G"})})
    world.now = et(18, 2)
    desk.sweep()
    assert {x.physician_id: x.state for x in desk.offers()} == {"R1": "WITHDRAWN", "R2": "CANCELLED"}
    assert refusal(lambda: desk.accept(a["id"], "R1")) == (409, "already_filled")


def test_physician_who_becomes_ineligible_before_send_is_cancelled_with_the_rule(desk, world):
    o = propose(desk)
    world.ops = replace(world.ops, roster={**world.ops.roster, "R1": replace(world.ops.roster["R1"], hours_last_7d=59)})
    sent = desk.approve(o["id"], "lead")
    assert sent["state"] == "CANCELLED" and "trailing7d_plus_offer_at_most_60h" in sent["reason"]
    assert desk.outbox() == []  # nothing reached the physician


def test_rules_are_never_bent_and_refusals_are_audited(desk, world):
    assert refusal(lambda: propose(desk, "R3")) == (422, "ineligible")  # not opted in
    assert refusal(lambda: propose(desk, "R1", ("G", "H"))) == (422, "non_gap_hospital")  # trap guard: gap hospitals only
    assert refusal(lambda: desk.propose("gap:G", "R1", et(17), et(21), ("G",), "coordinator")) == (422, "start_in_past")
    propose(desk, "R1")
    assert refusal(lambda: propose(desk, "R1")) == (422, "ineligible")  # R7: one open offer
    assert [a["command"] for a in desk.audit()].count("propose:refused") == 4


def test_another_physicians_offer_looks_like_no_offer(desk, world):
    o = propose(desk)
    desk.approve(o["id"], "lead")
    assert refusal(lambda: desk.accept(o["id"], "R2")) == (404, "not_found")
    assert refusal(lambda: desk.offer(o["id"], physician_id="R2")) == (404, "not_found")
    assert desk.offers("R2") == []


def test_clock_moved_back_is_refused(desk, world):
    o = propose(desk)
    world.now = et(17, 59)
    assert refusal(lambda: desk.approve(o["id"], "lead")) == (409, "clock_rewound")
    assert desk.offer(o["id"]).state == "PROPOSED"


def test_late_approval_starts_the_offer_now(desk, world):
    o = propose(desk)
    world.now = et(18, 40)
    sent = desk.approve(o["id"], "lead")
    assert (sent["state"], sent["start"]) == ("SENT", iso(et(18, 40)))


def test_a_failure_mid_command_leaves_nothing_behind(desk, world, monkeypatch):
    o = propose(desk)
    audit_rows = len(desk.audit())
    monkeypatch.setattr(offers_module, "message", lambda *a: (_ for _ in ()).throw(RuntimeError("outbox down")))
    with pytest.raises(RuntimeError):
        desk.approve(o["id"], "lead")
    # Approve and send are one transaction: no half-approved offer, no audit row, no message.
    assert desk.offer(o["id"]).state == "PROPOSED" and len(desk.audit()) == audit_rows and desk.outbox() == []


def test_schema_backstops(desk, db_url):
    o = propose(desk)
    with psycopg.connect(db_url, autocommit=True) as conn:
        with pytest.raises(psycopg.errors.RaiseException):
            conn.execute("UPDATE offers SET state='ACCEPTED' WHERE id=%s", (o["id"],))  # PROPOSED -> ACCEPTED skips approval
        with pytest.raises(psycopg.errors.UniqueViolation):
            conn.execute("""INSERT INTO offers(gap_id,physician_id,hospitals,start_at,end_at,state,created_at,updated_at,proposed_by)
                            VALUES('g','R1','[]',now(),now()+interval '2 hours','SENT',now(),now(),'x')""")  # R7


def test_concurrent_commands_from_two_instances_serialize(db_url, world):
    desks = [OfferDesk(db_url, world.context), OfferDesk(db_url, world.context)]
    a, b = propose(desks[0], "R1"), propose(desks[0], "R2")
    desks[0].approve(a["id"], "lead"), desks[0].approve(b["id"], "lead")
    results = {}

    def accept(desk, offer, pid):
        try:
            results[pid] = desk.accept(offer["id"], pid)["state"]
        except OfferError as exc:
            results[pid] = exc.code

    threads = [threading.Thread(target=accept, args=(d, o, p)) for d, o, p in ((desks[0], a, "R1"), (desks[1], b, "R2"))]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    # Need is 1: exactly one acceptance, whichever committed first; the other is told the gap is filled.
    assert sorted(results.values()) == ["ACCEPTED", "already_filled"]
    assert sum(x.state == "ACCEPTED" for x in desks[1].offers()) == 1
