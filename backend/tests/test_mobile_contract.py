"""Real API payloads on a synthetic world shared with the mobile adapter tests.

No challenge CSVs or answer keys are used. Set CC_MOBILE_FIXTURE_OUTPUT to export
the payload bundle when intentionally updating the mobile integration fixture.
"""
import json
import os
from pathlib import Path
from datetime import timedelta
from types import SimpleNamespace
from fastapi.testclient import TestClient
from app.clock import FixedClock
from app.main import create_app
from app.models import EventInput
from conftest import ADMIN, COORD, LEAD, TEST_AUTH
from test_accepted_routing import START, END, event, world


def test_mobile_backend_payload_contract(db_url, tmp_path):
    refs, ops, _ = world()
    speech = SimpleNamespace(available=False, audio=lambda text: None, close=lambda: None)
    app = create_app(db_url, FixedClock(START - timedelta(minutes=20)), auth=TEST_AUTH,
                     references=(refs, ops), history_path=tmp_path / "absent.csv", speech=speech, sweep_s=0)
    bundle = {}
    with TestClient(app) as client:
        def get(path, headers=LEAD):
            response = client.get(path, headers=headers)
            assert response.status_code == 200, response.text
            return response.json()
        token = client.post("/admin/physician-tokens", headers=ADMIN, json={"physician_id": "J"}).json()["token"]
        physician = {"Authorization": f"Bearer {token}"}
        bundle["me_physician"] = get("/me", physician)
        bundle["me_lead"] = get("/me")
        assert bundle["me_physician"]["on_shift"] is False
        assert bundle["me_physician"]["split_shift_opt_in"] is True
        assert bundle["me_physician"]["weekly_offer_limit"] == 3
        assert bundle["me_lead"]["role"] == "lead"
        bundle["shift_off"] = get("/me/shift", physician)
        seed = START - timedelta(minutes=40)
        events = [event("received", "consult_received", seed, cid="OLD", hospital_id="G", consult_type="Stroke"),
                  event("triage", "consult_triaged", seed + timedelta(seconds=1), cid="OLD"),
                  event("assign", "physician_assigned", seed + timedelta(seconds=2), cid="OLD", pid="J"),
                  event("call", "incoming_call_started", seed + timedelta(seconds=3), cid="OLD", pid="J"),
                  event("end", "incoming_call_ended", seed + timedelta(minutes=5), cid="OLD", pid="J", value="phone_complete")]
        payload = [e.model_dump(mode="json", include=set(EventInput.model_fields)) for e in events]
        assert client.post("/events", headers=ADMIN, json=payload).status_code == 200
        proposed = client.post("/offers", headers=COORD, json={"gap_id": "now_gap:G", "physician_id": "J",
                              "start": START.isoformat(), "end": END.isoformat(), "hospitals": ["G"]})
        assert proposed.status_code == 200, proposed.text
        bundle["proposed"] = proposed.json()
        oid = bundle["proposed"]["offer_id"]
        bundle["offers_proposed"] = get("/offers")
        bundle["candidates"] = get("/gaps/now_gap:G/candidates")
        bundle["trap"] = get("/gaps/now_gap:G/trap-check")
        bundle["interventions"] = get("/interventions?state=pending")
        assert {p["physician_id"]: p["name"] for p in get("/snapshot")["physicians"]["items"]} == {
            pid: physician.name for pid, physician in refs.physicians.items()}
        bundle["snapshot_coverage"] = {k: get("/snapshot")[k] for k in ("clock", "coverage")}
        assert bundle["candidates"]["candidates"][0]["eligible"] is True
        assert bundle["trap"]["seed_consults"] is not None
        approved = client.post(f"/offers/{oid}/approve", headers={**LEAD, "Idempotency-Key": "mobile-approve"})
        assert approved.status_code == 200, approved.text
        bundle["sent"] = approved.json()
        assert client.post(f"/offers/{oid}/approve", headers={**LEAD, "Idempotency-Key": "mobile-approve"}).json() == bundle["sent"]
        bundle["my_offers"] = get("/me/offers", physician)
        bundle["offers_sent"] = get("/offers")
        accepted = client.post(f"/offers/{oid}/accept", headers=physician)
        assert accepted.status_code == 200, accepted.text
        bundle["accepted"] = accepted.json()
        bundle["audit"] = get("/audit?gap_id=now_gap:G")
        assert client.post("/admin/clock", headers=ADMIN, json={"at": START.isoformat()}).status_code == 200
        online = event("online", "shift_started", START, pid="J")
        assert client.post("/events", headers=ADMIN, json=online.model_dump(mode="json", include=set(EventInput.model_fields))).status_code == 200
        owned = [event("own_received", "consult_received", START, cid="OWNED", hospital_id="G", consult_type="Stroke"),
                 event("own_triage", "consult_triaged", START + timedelta(seconds=1), cid="OWNED"),
                 event("own_assign", "physician_assigned", START + timedelta(seconds=2), cid="OWNED", pid="J")]
        assert client.post("/events", headers=ADMIN,
                           json=[e.model_dump(mode="json", include=set(EventInput.model_fields)) for e in owned]).status_code == 200
        assert client.post("/admin/clock", headers=ADMIN, json={"at": (START + timedelta(minutes=10)).isoformat()}).status_code == 200
        bundle["shift_on"] = get("/me/shift", physician)
        assert bundle["shift_on"]["on_shift"] is True
        assert bundle["shift_on"]["clock_mode"] == "fixed"
        assert bundle["shift_on"]["consults_this_shift"] == 1 and bundle["shift_on"]["calls_this_shift"] == 0
        assert all("level" in c for c in bundle["shift_on"]["consults"])
    fixture = Path(__file__).parent / "fixtures/mobile_backend.json"
    if output := os.getenv("CC_MOBILE_FIXTURE_OUTPUT"):
        Path(output).write_text(json.dumps(bundle, indent=2, sort_keys=True) + "\n")
    else:
        assert bundle == json.loads(fixture.read_text()), "Update the synthetic contract bundle and rerun mobile adapter tests."
