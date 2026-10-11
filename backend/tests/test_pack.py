"""Scenario-pack parity: replay inputs/ + live/judge_events.csv and compare with expected/ at every checkpoint.

Runs on every allowed pack (03 and 04 are held out). expected/ is the answer key and is never read by app code.
Skipped when the (uncommitted) packs are absent.
"""
import csv
import functools
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import pytest
from app.clock import utc
from app.decide.eligibility import Proposal, evaluate_proposal, load_offer_history
from app.decide.interventions import decide
from app.engine.physician import physician_view
from app.engine.replay import replay
from app.fixture import load_fixture
from app.models import Event
from app.ops.coverage import SIGNAL_BUSY, current_coverage, remaining_need
from app.ops.detect import NOTE_STAGES, consult_sla, views_at
from app.ops.refs import load_ops_refs
from app.references import load_reference_dir

ROOT = Path(__file__).resolve().parents[2] / "test_data"
PACKS = [ROOT / n for n in ("01_development", "02_validation_no_candidate", "03_integration_two_candidates", "04_holdout_changed_winner") if (ROOT / n / "manifest.json").exists()]
STAGE_LABEL = {"Imaging Pending": "CT/CTA or Imaging Pending", "Video In Progress": "Video Consult In Progress"}
ACTIVITY = {"Video Consult": "Video Consult In Progress", "Camera Active, No Session": "Camera Active - No Synapse Session",
            "Documentation": "Documentation / Note", "Available (meeting)": "In Meeting - Interruptible"}


@dataclass(frozen=True)
class Pack:
    path: Path
    refs: object
    ops: object
    rows: dict
    checkpoints: tuple
    manifest: dict

    def expected(self, name):
        with (self.path / "expected" / name).open(newline="") as handle:
            return list(csv.DictReader(handle))

    def history(self, now):
        return load_offer_history(self.path / "support/offer_history.csv", now)

    def time(self, label):
        return next(utc(datetime.fromisoformat(cp["as_of"])) for cp in self.checkpoints if cp["label"] == label)


@functools.cache
def load_pack(path: Path) -> Pack:
    refs = load_reference_dir(path / "inputs")
    ops = load_ops_refs(path / "inputs", {h: x.timezone for h, x in refs.hospitals.items()}, set(refs.physicians))
    rows = {}
    for source in (path / "inputs/event_stream.csv", path / "live/judge_events.csv"):
        for r in load_fixture(source):
            rows.setdefault(r.event_id, r)  # exact duplicate deliveries count once
    return Pack(path, refs, ops, rows, tuple(json.loads((path / "expected/checkpoints.json").read_text())),
                json.loads((path / "manifest.json").read_text()))


CASES = [(p, cp) for p in PACKS for cp in load_pack(p).checkpoints]
by_case = pytest.mark.parametrize("path,cp", CASES, ids=lambda x: x.name if isinstance(x, Path) else x["label"])
by_pack = pytest.mark.parametrize("path", PACKS, ids=lambda p: p.name)


def state_at(rows, now):
    """Visible = delivered and happened by `now`; replay orders by event time."""
    return replay(tuple(Event(**{**r.model_dump(), "received_at": r.ingested_at, "raw_json": {}})
                        for r in rows.values() if r.ingested_at <= now and r.event_time <= now))


def iso(t):
    return t.isoformat() if t else ""


def diff(actual, row, key):
    return [(key, f, actual[f], v) for f, v in row.items() if f in actual and actual[f] != v]


def consult_row(c, now):
    level, elapsed = consult_sla(c, now)
    return {"hospital_id": c.hospital_id, "physician_id": "" if c.owner == "Unassigned" else c.owner, "consult_type": c.consult_type,
            "stage": STAGE_LABEL.get(c.stage, c.stage), "received_at": iso(c.received_at), "stage_entered_at": iso(c.entered_at),
            "clinical_end_at": iso(c.note_pending_since), "contact_count": str(c.repeat_contacts + 1), "routing_failures": str(c.routing_failures),
            "note_signed": str(c.stage == "Signed Off"), "first_triaged_at": iso(next((t for s, t in c.history if s == "Triaged"), None)),
            "seconds_in_stage": str(int((now - c.entered_at).total_seconds())), "seconds_since_received": str(int((now - c.received_at).total_seconds())),
            "sla_elapsed_seconds": str(int(elapsed.total_seconds())),
            "severity": "not_applicable" if level is None or c.stage == "Signed Off" else level.lower()}


def physician_row(state, refs, pid, now):
    v, p = physician_view(state, refs, pid, now), state.physicians.get(pid)
    owned = [c for c in state.consults.values() if c.owner == pid and c.stage != "Signed Off"]
    on = "off_shift" not in v.exclusion_reasons
    notes = sum(c.stage in NOTE_STAGES for c in owned)
    secs = next((int((s.end - now).total_seconds()) for s in refs.physicians[pid].shifts if s.start <= now < s.end), None)
    return {"on_shift": str(on), "self_reported_status": v.self_reported_status, "agent_online": str(v.desktop_agent != "Offline"),
            "activity": ACTIVITY.get(v.derived_state, v.derived_state), "available_by_signals": str(v.derived_state not in SIGNAL_BUSY),
            "ringing": str(bool(p and p.rings)),
            "flags": "|".join(f for f, hit in (("EXTERNAL_VIDEO_SUSPECTED", "external_platform" in v.flags), ("AGENT_OFFLINE_UNVERIFIED", v.desktop_agent == "Offline")) if hit),
            "consults_this_shift": str(v.consults_this_shift), "calls_this_shift": str(v.calls_this_shift), "open_consults": str(len(owned)),
            "open_notes": str(notes), "seconds_to_shift_end": "" if secs is None else str(secs),
            "shift_end_note_severity": "none" if not on or secs is None or secs > 3600 or not notes else "critical" if notes >= 2 else "warning",
            "last_call_ended": iso(p and p.last_call_end), "last_answered": iso(p and p.last_answered_at)}


def coverage_row(c, ops, now):
    return {"local_hour": str(ops.local(c.hospital_id, now).hour), "trailing60m_unique_consults": str(c.trailing_60m), "p90": f"{c.p90:g}",
            "surge": str(c.surge), "base_requirement": str(c.base_requirement), "adjusted_requirement": str(c.required),
            "available_credentialed_count": str(len(c.available)), "routable_now_count": str(len(c.routable)),
            "coverage_gap": str(c.gap), "available_physicians": "|".join(c.available)}


@by_case
def test_counts_match_checkpoint(path, cp):
    pack = load_pack(path)
    rows = pack.rows
    now = utc(datetime.fromisoformat(cp["as_of"]))
    visible = [r for r in rows.values() if r.ingested_at <= now and r.event_time <= now]
    state = state_at(rows, now)
    assert (len(visible), len(state.consults), sum(c.stage != "Signed Off" for c in state.consults.values())) == \
        (cp["unique_events"], cp["consults"], cp["open_consults"])


@by_case
def test_consults_match_snapshot(path, cp):
    pack = load_pack(path)
    rows = pack.rows
    now = utc(datetime.fromisoformat(cp["as_of"]))
    state = state_at(rows, now)
    misses = []
    for row in pack.expected(f"snapshot_consults_{cp['label']}.csv"):
        misses += diff(consult_row(state.consults[row["consult_id"]], now), row, row["consult_id"])
    assert misses == []


@by_case
def test_physicians_match_snapshot(path, cp):
    pack = load_pack(path)
    refs, rows = pack.refs, pack.rows
    now = utc(datetime.fromisoformat(cp["as_of"]))
    state = state_at(rows, now)
    misses = []
    for row in pack.expected(f"snapshot_physicians_{cp['label']}.csv"):
        misses += diff(physician_row(state, refs, row["physician_id"], now), row, row["physician_id"])
    assert misses == []


@by_case
def test_current_coverage_matches_snapshot(path, cp):
    pack = load_pack(path)
    refs, ops, rows = pack.refs, pack.ops, pack.rows
    now = utc(datetime.fromisoformat(cp["as_of"]))
    state = state_at(rows, now)
    by_id = {c.hospital_id: c for c in current_coverage(state, refs, ops, views_at(state, refs, now), now)}
    misses = []
    for row in pack.expected(f"snapshot_coverage_{cp['label']}.csv"):
        misses += diff(coverage_row(by_id[row["hospital_id"]], ops, now), row, row["hospital_id"])
    assert misses == []


@by_pack
def test_candidate_table_matches_answer_key(path):
    pack = load_pack(path)
    refs, ops, rows = pack.refs, pack.ops, pack.rows
    key = json.loads((path / "expected/candidate_checks_1820.json").read_text())
    now = utc(datetime.fromisoformat(key["now"]))
    proposal = Proposal(utc(datetime.fromisoformat(key["proposal"]["start"])), utc(datetime.fromisoformat(key["proposal"]["end"])), tuple(key["proposal"]["hospitals"]))
    got = {c.physician_id: c for c in evaluate_proposal(proposal, refs, ops, now, pack.history(now))}
    for want in key["candidates"]:
        c = got[want["physician_id"]]
        assert {r.key: r.passed for r in c.rules} == want["rules"], want["physician_id"]
        assert (c.eligible, list(c.failed), c.ready_at) == (want["eligible"], want["failed_rules"], utc(datetime.fromisoformat(want["ready_at"])))
        assert ((c.end - c.start).total_seconds() / 3600, (c.end - c.ready_at).total_seconds() / 3600) == (want["nominal_hours"], want["useful_hours"])
    assert sum(c.eligible for c in got.values()) == key["eligible_count"]


@by_pack
def test_hand_authored_assertions(path):
    pack = load_pack(path)
    rows = pack.rows
    for case in json.loads((path / "expected/hand_authored_assertions.json").read_text()):
        now = pack.time(case["checkpoint"])
        c = state_at(rows, now).consults[case["consult_id"]]
        level, _ = consult_sla(c, now)
        actual = {"stage": STAGE_LABEL.get(c.stage, c.stage), "stage_entered_at": iso(c.entered_at), "contact_count": c.repeat_contacts + 1,
                  "received_at": iso(c.received_at), "severity": "not_applicable" if level is None or c.stage == "Signed Off" else level.lower()}
        assert {k: actual[k] for k in case["expected"]} == case["expected"], case["case"]


@by_case
def test_decisions_run_at_every_checkpoint(path, cp):
    pack = load_pack(path)
    """Not only 18:20: the queue is well-formed at each checkpoint, with one item per consult."""
    refs, ops, rows = pack.refs, pack.ops, pack.rows
    now = utc(datetime.fromisoformat(cp["as_of"]))
    d = decide(state_at(rows, now), refs, ops, now, pack.history(now))
    consults = [i.where.get("consult_id") for i in d.items if i.where.get("consult_id")]
    assert len(consults) == len(set(consults))
    assert all(i.fix.approver in {"automatic", "coordinator", "clinical_lead"} for i in d.items)
    assert [i.rank_key for i in d.items] == sorted(i.rank_key for i in d.items)


@by_pack
def test_forecast_ceiling_matches_answer_key(path):
    pack = load_pack(path)
    """Schedule ceiling counts scheduled physicians regardless of status; night starters count from their start."""
    from app.ops.coverage import supply
    refs, ops, rows = pack.refs, pack.ops, pack.rows
    now = pack.time("1820")
    state = state_at(rows, now)
    items = supply(state, refs, ops, views_at(state, refs, now), now)
    misses = []
    for row in pack.expected("forecast_schedule_bounds_1820.csv"):
        t, h = utc(datetime.fromisoformat(row["forecast_at"])), row["hospital_id"]
        ceiling = sum(1 for s in items if h in s.hospitals and s.start <= t and (s.end is None or t < s.end))
        base = ops.requirement(h, t)
        actual = {"base_requirement": str(base), "scheduled_capacity_ceiling": str(ceiling), "guaranteed_baseline_gap": str(max(0, base - ceiling))}
        misses += diff(actual, row, (h, row["forecast_at"]))
    assert misses == []


@by_case
def test_safety_and_capacity_invariants(path, cp):
    pack = load_pack(path)
    refs, ops, rows = pack.refs, pack.ops, pack.rows
    now = utc(datetime.fromisoformat(cp["as_of"]))
    state = state_at(rows, now)
    d = decide(state, refs, ops, now, pack.history(now))
    off_shift = {pid for pid, v in d.views.items() if "off_shift" in v.exclusion_reasons}
    # Nothing automatic is aimed at an off-shift physician; offers always need the clinical lead.
    assert not [i.id for i in d.items if i.fix.approver == "automatic" and i.where.get("physician_id") in off_shift]
    assert all(i.fix.approver == "clinical_lead" for i in d.items if i.fix.kind == "split_shift")
    # One new consult per physician per pass.
    targets = [i.fix.physician_id for i in d.items if i.fix.kind in {"assign", "reassign"}]
    assert len(targets) == len(set(targets))
    # Offers name gap hospitals only (trap guard).
    gap_sites = {g.hospital_id for g in d.gaps if g.kind == "hard"} | {c.hospital_id for c in current_coverage(state, refs, ops, d.views, now) if c.gap}
    for i in d.items:
        if i.fix.kind == "split_shift":
            assert set(i.where.get("hospital_ids") or [i.where["hospital_id"]]) <= gap_sites


@by_pack
def test_example_offer_goes_to_an_answer_key_eligible_physician_or_escalates(path):
    """At 18:20 the example gap is offered only to a physician the answer key marks eligible; with none
    (validation pack) it escalates with every off-shift physician and the rule each fails, and no rule is bent."""
    pack = load_pack(path)
    key = json.loads((path / "expected/candidate_checks_1820.json").read_text())
    eligible = {c["physician_id"] for c in key["candidates"] if c["eligible"]}
    now = pack.time("1820")
    d = decide(state_at(pack.rows, now), pack.refs, pack.ops, now, pack.history(now))
    hospitals = set(key["proposal"]["hospitals"])
    items = [i for i in d.items if hospitals & set(i.where.get("hospital_ids") or [i.where.get("hospital_id")]) and i.candidates
             and not i.id.startswith("watch:")]
    assert items
    for i in items:
        if i.fix.kind == "split_shift":
            assert i.fix.physician_id in eligible
            assert {c.physician_id for c in i.candidates if c.eligible} >= eligible  # the runner-up is shown too
            if len([c for c in i.candidates if c.eligible]) > 1:
                assert "chosen over" in i.fix.reason  # and the reason it lost is stated
        else:
            assert not eligible and i.fix.kind in {"escalate", "watch"}
            if i.fix.kind == "escalate":
                assert {a.split(":")[0] for a in i.fix.alternatives} >= set(pack.ops.roster)
    assert any(i.fix.kind == "split_shift" for i in items) == bool(eligible)


@by_pack
def test_engine_offer_runs_end_to_end_through_the_desk(path, db_url):
    """The engine's own recommendation goes through propose -> approve/send -> accept, and then stops being recommended.
    With no eligible physician (validation pack) the desk refuses every one of them for the example gap."""
    from app.act.offers import Context, OfferDesk, OfferError
    pack = load_pack(path)
    now = pack.time("1820")
    state = state_at(pack.rows, now)
    desk = OfferDesk(db_url, lambda: Context(state, pack.refs, pack.ops, now), pack.history(now))
    d = decide(state, pack.refs, pack.ops, now, desk.history(now), desk.accepted())
    offers = [i for i in d.items if i.fix.kind == "split_shift"]
    if not pack.manifest["eligible_candidates_for_example_offer"]:
        key = json.loads((path / "expected/candidate_checks_1820.json").read_text())
        p = key["proposal"]
        for pid in pack.ops.roster:
            with pytest.raises(OfferError) as exc:
                desk.propose("example", pid, datetime.fromisoformat(p["start"]), datetime.fromisoformat(p["end"]), p["hospitals"], "coordinator")
            assert exc.value.status == 422
        assert desk.offers() == [] and desk.outbox() == []
        return
    item = offers[0]
    best = next(c for c in item.candidates if c.physician_id == item.fix.physician_id)
    o = desk.propose(item.id, best.physician_id, best.start, best.end, best.hospitals, "coordinator")
    assert desk.approve(o["id"], "lead")["state"] == "SENT"
    assert desk.accept(o["id"], best.physician_id)["state"] == "ACCEPTED"
    after = decide(state, pack.refs, pack.ops, now, desk.history(now), desk.accepted())
    assert not [i for i in after.items if i.fix.kind == "split_shift" and i.fix.physician_id == best.physician_id]
    # One joiner may not fill a hospital that needs several (two-candidate pack): a further offer there is only
    # made while the need, with the accepted joiner counted, is still above zero.
    for i in after.items:
        if i.fix.kind == "split_shift":
            c = next(c for c in i.candidates if c.physician_id == i.fix.physician_id)
            need = remaining_need(state, pack.refs, pack.ops, after.views, now, desk.accepted(), c.hospitals, c.start, c.end)
            assert any(need.values()), (i.id, need)
