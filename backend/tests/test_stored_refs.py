"""Operational references (baselines, coverage minimums, off-shift roster) are stored in the database like the reference tables."""
from dataclasses import replace
from datetime import datetime, timezone
from types import MappingProxyType
import pytest
from app.db import EventDatabase
from app.ops.refs import OpsRefs, RosterEntry
from app.service import stored_operations


def ops(minimum=2):
    roster = {"P2": RosterEntry("Night", True, datetime(2026, 3, 17, 11, tzinfo=timezone.utc), datetime(2026, 3, 17, 23, tzinfo=timezone.utc),
                                22.5, 15, "SMS", 1),
              "P3": RosterEntry("Day", False, None, None, 0.0, 30, "Push", 0)}
    return OpsRefs(MappingProxyType({("H", 1, 18): (0.4, 1.0), ("H", 5, 9): (1.25, 3.0)}),
                   MappingProxyType({"H": ((420, 1320, 1), (1320, 420, minimum))}), MappingProxyType(roster), MappingProxyType({"H": "America/Chicago"}))


def test_payload_round_trips_every_field():
    original = ops()
    restored = OpsRefs.from_payload(original.payload())
    assert restored.payload() == original.payload()
    assert restored.roster["P2"] == original.roster["P2"] and restored.roster["P3"].last_shift_end is None
    at = datetime(2026, 3, 17, 23, 30, tzinfo=timezone.utc)  # Tuesday 18:30 in Chicago
    assert (restored.p90("H", at), restored.requirement("H", at)) == (original.p90("H", at), original.requirement("H", at))


def test_first_start_stores_the_files_and_later_starts_use_the_stored_copy(db_url):
    db = EventDatabase(db_url)
    assert db.metadata("operations_references") is None
    first = stored_operations(db, ops())
    assert db.metadata("operations_references")["payload"] == ops().payload() and first.payload() == ops().payload()
    # Without the files the server still has them, from the database.
    assert stored_operations(db, None).payload() == ops().payload()
    # The same files again are accepted.
    assert stored_operations(db, ops()).payload() == ops().payload()


def test_changed_files_are_refused_once_stored(db_url):
    db = EventDatabase(db_url)
    stored_operations(db, ops())
    with pytest.raises(ValueError, match="differ from the copy in the database"):
        stored_operations(db, ops(minimum=3))
    changed_roster = replace(ops(), roster=MappingProxyType({**ops().roster, "P3": replace(ops().roster["P3"], opt_in=True)}))
    with pytest.raises(ValueError, match="differ from the copy in the database"):
        stored_operations(db, changed_roster)


def test_nothing_stored_and_no_files_means_no_operational_references(db_url):
    assert stored_operations(EventDatabase(db_url), None) is None
