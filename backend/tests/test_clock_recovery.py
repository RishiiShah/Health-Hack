"""Clock overrides survive application restarts and are not published after failed commits."""
from datetime import datetime, timedelta, timezone
from dataclasses import replace
from types import SimpleNamespace
import pytest
from fastapi.testclient import TestClient
from conftest import ADMIN, COORD, TEST_AUTH
from app.clock import AnchoredClock, FixedClock, restore_clock, saved_clock
from app.coordinator import MutationCoordinator
from app.db import EventDatabase
from app.main import create_app
from app.config import settings

AT = datetime(2026, 4, 7, 22, 20, tzinfo=timezone.utc)


def test_running_clock_recovers_elapsed_time_without_rewinding(monkeypatch):
    monkeypatch.setattr("app.clock.monotonic", lambda: 100.0)
    clock = AnchoredClock(AT)
    saved = saved_clock(clock, AT)
    assert restore_clock(saved, AT + timedelta(minutes=10)).now() == AT + timedelta(minutes=10)
    assert restore_clock(saved, AT - timedelta(minutes=10)).now() == AT
    assert restore_clock(saved_clock(FixedClock(AT), AT), AT + timedelta(days=1)).now() == AT


@pytest.mark.parametrize("csv_advance", [False, True])
def test_override_and_csv_advance_survive_restart(db_url, monkeypatch, csv_advance):
    monkeypatch.setattr("app.main.settings", replace(settings, clock_mode="fixed", clock_fixed=AT.isoformat(), reference_dir=None))
    later = AT + timedelta(minutes=20)
    def hosted():
        speech = SimpleNamespace(available=False, conn=SimpleNamespace(close=lambda: None))
        return create_app(db_url, auth=TEST_AUTH, speech=speech, sweep_s=0)
    with TestClient(hosted()) as client:
        if csv_advance:
            body = ("event_id,event_time,ingested_at,consult_id,event_type,physician_id,hospital_id,description\n"
                    f"R,{later.isoformat()},{later.isoformat()},C,consult_received,,H,Stroke consult request received\n")
            response = client.post("/events/csv?advance_clock=true", content=body, headers=ADMIN)
        else:
            response = client.post("/events", headers=ADMIN, json={"event_id": "R", "event_time": later.isoformat(),
                                   "event_type": "consult_received", "consult_id": "C", "hospital_id": "H", "consult_type": "Stroke"})
            assert response.status_code == 200
            response = client.post("/admin/clock", headers=ADMIN, json={"at": later.isoformat(), "paused": True})
        assert response.status_code == 200, response.text
        first = client.get("/snapshot", headers=COORD).json()
        assert first["clock"]["now"] == later.isoformat()
        assert len(first["consults"]) == 1
    with TestClient(hosted()) as client:
        recovered = client.get("/snapshot", headers=COORD).json()
        assert recovered["clock"]["now"] == later.isoformat()
        assert recovered["clock"]["mode"] == "fixed"
        assert len(recovered["consults"]) == 1


def test_failed_clock_commit_keeps_previous_clock(db_url, monkeypatch):
    db = EventDatabase(db_url)
    coordinator = MutationCoordinator(db, FixedClock(AT))
    def fail(*args, **kwargs):
        raise RuntimeError("commit failed")
    monkeypatch.setattr(db, "commit_batch", fail)
    with pytest.raises(RuntimeError, match="commit failed"):
        coordinator.set_clock(FixedClock(AT + timedelta(hours=1)))
    assert coordinator.current_publication().as_of == AT
    assert db.metadata("clock") is None
    db.conn.close()


def test_running_override_survives_restart_with_downtime(db_url, monkeypatch):
    monkeypatch.setattr("app.main.settings", replace(settings, clock_mode="fixed", clock_fixed=AT.isoformat(), reference_dir=None))
    monkeypatch.setattr("app.clock.monotonic", lambda: 100.0)
    receipt = [AT]
    monkeypatch.setattr("app.clock.ServerReceiptClock.now", lambda self: receipt[0])
    later = AT + timedelta(hours=1)
    def hosted():
        speech = SimpleNamespace(available=False, conn=SimpleNamespace(close=lambda: None))
        return create_app(db_url, auth=TEST_AUTH, speech=speech, sweep_s=0)
    with TestClient(hosted()) as client:
        response = client.post("/admin/clock", headers=ADMIN, json={"at": later.isoformat(), "paused": False})
        assert response.status_code == 200 and response.json()["mode"] == "anchored"
    receipt[0] += timedelta(minutes=10)
    with TestClient(hosted()) as client:
        clock = client.get("/snapshot", headers=COORD).json()["clock"]
        assert clock["mode"] == "anchored"
        assert clock["now"] == (later + timedelta(minutes=10)).isoformat()
