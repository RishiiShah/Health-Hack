"""Public checks for the approved priority and fallback reservation policy."""
from datetime import datetime, timedelta, timezone

from app.decide.interventions import _merge, _rank_key
from app.engine.physician import PhysicianView
from app.ops.detect import Finding
from app.ops.refs import OpsRefs
from app.references import Hospital, Physician, Refs, Shift


def test_severity_cannot_be_outweighed_by_stroke_repeat_or_age():
    now = datetime(2026, 4, 7, 22, tzinfo=timezone.utc)
    critical = _rank_key("Critical", False, False, False, False, now, 1, "C")
    warning = _rank_key("Warning", True, True, True, True, now - timedelta(hours=3), 100, "W")
    assert critical < warning
    tied = lambda id: _rank_key("Critical", True, True, True, True, now, 1, id)
    assert tied("A") < tied("B")


def test_free_fallback_can_be_another_primary_and_is_explicitly_not_reserved():
    now = datetime(2026, 4, 7, 22, tzinfo=timezone.utc)
    shift = Shift(now - timedelta(hours=8), now + timedelta(hours=8))
    sites = {"H1": Hospital("First", "America/New_York"), "H2": Hospital("Second", "America/New_York")}
    refs = Refs(sites, {pid: Physician(pid, (shift,)) for pid in ("A", "F")}, {"A": frozenset({"H1"}), "F": frozenset(sites)})
    views = {pid: PhysicianView(pid, "Hospital Call" if pid == "A" else "Available", "Available", "Online", pid == "F",
        ("busy",) if pid == "A" else (), (), 0 if pid == "A" else 5, 0, 0, 480, refs.credentials[pid], None, shift) for pid in refs.physicians}
    findings = [Finding("unassigned", "Critical", "First waiting", "H1", "C1", stroke=True, waiting_since=now - timedelta(minutes=20)),
        Finding("unassigned", "Warning", "Second waiting", "H2", "C2", waiting_since=now - timedelta(minutes=10))]
    items = _merge(findings, views, refs, OpsRefs({}, {}, {}), now)
    assert [i.fix.physician_id for i in items] == ["A", "F"]
    assert "F is free now" in items[0].fix.action
    assert "alternatives, not reserved capacity" in items[0].fix.reason
    assert "choose one assignment and refresh" in items[0].fix.reason
