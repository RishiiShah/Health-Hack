"""GET /schedule over the sample rosters at 18:20 ET: reference shifts, open-ended next starts, offers and permissions."""
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
import pytest
from fastapi.testclient import TestClient
from conftest import COORD, LEAD, TEST_AUTH
from app.clock import FixedClock
from app.main import create_app
from app.service import load_references

ET = ZoneInfo("America/New_York")
DATA = Path(__file__).resolve().parents[2] / "data"
pytestmark = pytest.mark.skipif(not (DATA / "event_stream.csv").exists(), reason="source data is gitignored")


@pytest.fixture
def client(db_url):
    api = create_app(db_url, FixedClock(datetime(2026, 3, 17, 18, 20, tzinfo=ET)), auth=TEST_AUTH,
                     references=load_references(DATA, date(2026, 3, 17)), sweep_s=0)
    with TestClient(api) as c:
        r = c.post("/events/csv", content=(DATA / "event_stream.csv").read_bytes(), headers={**COORD, "Content-Type": "text/csv"})
        assert r.status_code == 200, r.text
        yield c


def rows(client, headers=COORD):
    r = client.get("/schedule", headers=headers)
    assert r.status_code == 200, r.text
    body = r.json()
    return body, {d["id"]: d for d in body["doctors"]}


def test_roster_shows_reference_shifts_and_open_ended_next_starts(client):
    body, doctors = rows(client)
    assert body["date_label"] == "Tuesday 17 March" and body["now_label"] == "18:20" and body["alert"] is None
    assert len(doctors) == 14
    assert [f["label"] for f in body["filters"]][:3] == ["Everyone", "On shift", "Off shift"]
    assert set(next(f for f in body["filters"] if f["label"] == "On shift")["ids"]) == {f"PHY-00{n}" for n in range(1, 9)}
    assert doctors["PHY-001"].items() >= {"group": "On shift", "bar": "08:00 to 20:00", "avatar": "MP"}.items()
    assert doctors["PHY-003"]["bar"] == "07:00 to 19:00" and doctors["PHY-003"]["detail"] == "Shift ends in 40 min"
    # The off-shift roster gives a next start but no end: shown open-ended, never with an invented end time.
    assert doctors["PHY-011"].items() >= {"group": "Off shift", "bar": "Night · from 19:00", "tone": "night", "status": "Starts 19:00"}.items()
    assert doctors["PHY-012"]["bar"] == "Night · from 20:00" and doctors["PHY-012"]["detail"] == "Not opted into extra shifts"
    assert doctors["PHY-010"].items() >= {"bar": "Off today", "tone": "off", "status": "Next shift Thu 08:00", "workload": "24 h in last 7 days"}.items()
    assert doctors["PHY-009"]["status"] == "Next shift Wed 19:00"
    assert doctors["PHY-001"]["credentialed"].startswith("7 hospitals: ")


def test_an_open_offer_shows_on_the_roster_with_an_alert(client):
    _, before = rows(client)
    gap = "now_gap:SYN-005"
    start, end = datetime(2026, 3, 17, 18, 21, tzinfo=ET), datetime(2026, 3, 17, 22, tzinfo=ET)
    r = client.post("/offers", json={"gap_id": gap, "physician_id": "PHY-009", "start": start.isoformat(), "end": end.isoformat()}, headers=COORD)
    assert r.status_code == 200, r.text
    body, doctors = rows(client)
    assert doctors["PHY-009"].items() >= {"tone": "offer", "bar": "18:21 to 22:00", "detail": "Waiting for clinical lead approval"}.items()
    assert body["alert"]["physician_id"] == "PHY-009" and "Dr. Grace Okafor" in body["alert"]["text"]
    suncrest = next(f for f in body["filters"] if f["label"] == "Credentialed at Suncrest Medical Pavilion")
    assert "PHY-009" in suncrest["ids"] and before["PHY-009"]["tone"] == "off"


def test_operations_roles_read_the_roster_and_physicians_cannot(client):
    assert client.get("/schedule", headers=LEAD).status_code == 200
    assert client.get("/schedule").status_code == 401
    token = client.app.state.auth.physician_token("PHY-009", datetime.now(ET) + timedelta(hours=1))
    assert client.get("/schedule", headers={"Authorization": f"Bearer {token}"}).status_code == 403
