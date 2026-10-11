"""Step 9: the API contract over the scenario packs [00-Boundaries]. Needs Postgres; skipped without the packs."""
import csv
import io
from datetime import datetime, timedelta, timezone
import pytest
from fastapi.testclient import TestClient
from conftest import ADMIN, COORD, LEAD, TEST_AUTH
from test_pack import PACKS, load_pack, state_at
from app.clock import FixedClock
from app.decide.interventions import decide
from app.decide.routing_sim import observed_service
from app.main import create_app
from app.models import Event
from app.service import load_references

pytestmark = pytest.mark.skipif(not PACKS, reason="scenario packs are not committed")
by_pack = pytest.mark.parametrize("path", PACKS, ids=lambda p: p.name)
FIELDS = ["event_id", "event_time", "ingested_at", "consult_id", "event_type", "physician_id", "hospital_id", "description"]


class FakeSpeech:
    """Records what would be spoken; never calls ElevenLabs."""
    available = True

    def __init__(self):
        self.texts, self.conn = [], type("Conn", (), {"close": lambda self: None})()

    def audio(self, text):
        self.texts.append(text)
        return b"ID3-fake"


def raw_rows(path, name):
    with (path / name).open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def as_csv(rows):
    out = io.StringIO()
    writer = csv.DictWriter(out, FIELDS)
    writer.writeheader()
    writer.writerows(rows)
    return out.getvalue().encode()


def at(text):
    return datetime.fromisoformat(text).astimezone(timezone.utc)


def app_for(path, db_url, speech=None):
    pack = load_pack(path)
    clock = FixedClock(pack.time("1820"))
    api = create_app(db_url, clock, auth=TEST_AUTH, references=load_references(path / "inputs"),
                     history_path=path / "support/offer_history.csv", speech=speech or FakeSpeech(), sweep_s=0)
    return pack, api


def post_csv(client, rows):
    r = client.post("/events/csv", content=as_csv(rows), headers={**ADMIN, "Content-Type": "text/csv"})
    assert r.status_code == 200, r.text
    return r.json()


def set_clock(client, now, mode="fixed"):
    assert client.post("/admin/clock", json={"mode": mode, "at": now.isoformat()}, headers=ADMIN).status_code == 200


def expected_queue(pack, now):
    state = state_at(pack.rows, now)
    events = tuple(Event(**{**r.model_dump(), "received_at": r.ingested_at, "raw_json": {}}) for r in pack.rows.values()
                   if r.ingested_at <= now and r.event_time <= now)
    d = decide(state, pack.refs, pack.ops, now, pack.history(now), service=observed_service(events, state))
    return [(i.id, i.severity, i.fix.kind, i.fix.physician_id) for i in d.items]


def served_queue(client):
    return [(i["id"], i["severity"], i["fix"]["kind"], i["fix"]["physician_id"]) for i in client.get("/snapshot", headers=COORD).json()["queue"]["items"]]


@by_pack
def test_live_append_matches_a_full_replay_at_every_checkpoint(path, db_url):
    """The demo: base file at 18:20, then judge events arrive as they are delivered while the clock moves.
    The served queue equals a from-scratch replay of what had arrived, at every checkpoint."""
    pack, api = app_for(path, db_url)
    judge = sorted(raw_rows(path, "live/judge_events.csv"), key=lambda r: at(r["ingested_at"]))  # offsets differ per hospital: compare instants, not strings
    with TestClient(api) as client:
        post_csv(client, raw_rows(path, "inputs/event_stream.csv"))
        sent = 0
        for cp in pack.checkpoints:
            now = pack.time(cp["label"])
            due = [r for r in judge[sent:] if at(r["ingested_at"]) <= now]
            if due:
                post_csv(client, due)
                sent += len(due)
            set_clock(client, now)
            assert served_queue(client) == expected_queue(pack, now), cp["label"]


@by_pack
def test_ingesting_the_same_file_twice_changes_no_decision(path, db_url):
    pack, api = app_for(path, db_url)
    rows = raw_rows(path, "inputs/event_stream.csv")
    with TestClient(api) as client:
        first = post_csv(client, rows)
        before = served_queue(client)
        second = post_csv(client, rows)
        assert second["accepted"] == 0 and second["duplicates"] == first["accepted"] + first["duplicates"]
        assert served_queue(client) == before


def test_roles_permissions_and_physician_isolation(db_url):
    path = PACKS[0]
    pack, api = app_for(path, db_url)
    with TestClient(api) as client:
        assert client.get("/snapshot").status_code == 401
        assert client.get("/snapshot", headers={"Authorization": "Bearer wrong"}).status_code == 401
        me = {h["Authorization"]: client.get("/me", headers=h).json() for h in (COORD, LEAD, ADMIN)}
        assert [m["role"] for m in me.values()] == ["coordinator", "lead", "admin"] and me[LEAD["Authorization"]]["display_name"] == "Dr. Lead"
        assert client.post("/events/csv", content=b"", headers=COORD).status_code == 200  # the web Data page: coordinator and lead inject
        assert client.post("/offers/OFR-00001/approve", headers=COORD).status_code == 403
        assert client.post("/offers", json={"gap_id": "x", "physician_id": "y", "start": "2026-01-01T00:00:00Z", "end": "2026-01-01T02:00:00Z"},
                           headers=LEAD).status_code == 403
        pid = next(iter(pack.ops.roster))
        token = client.post("/admin/physician-tokens", json={"physician_id": pid}, headers=ADMIN).json()["token"]
        doc = {"Authorization": f"Bearer {token}"}
        identity = client.get("/me", headers=doc).json()
        assert {k: identity[k] for k in ("role", "display_name", "physician_id", "permissions")} == {
            "role": "physician", "display_name": pid, "physician_id": pid, "permissions": ["offers.view_own", "offers.respond"]}
        assert identity["user_id"] == pid and identity["clock_mode"] == "fixed"
        assert identity["weekly_offer_limit"] == 3 and identity["offers_received_7d"] == 0
        assert client.get("/snapshot", headers=doc).status_code == 403
        assert client.post("/events/csv", content=b"", headers=doc).status_code == 403
        assert client.post("/admin/reset", headers=doc).status_code == 403
        assert client.get("/offers", headers=doc).json() == {"items": []}
        expired = TEST_AUTH.physician_token(pid, datetime.now(timezone.utc) - timedelta(seconds=1))
        assert client.get("/me", headers={"Authorization": f"Bearer {expired}"}).status_code == 401
        assert client.get("/me", headers={"Authorization": f"Bearer {token[:-2]}xx"}).status_code == 401  # tampered signature
        assert client.post("/admin/physician-tokens", json={"physician_id": "NOPE"}, headers=ADMIN).status_code == 404


@pytest.mark.skipif(not PACKS or PACKS[0].name != "01_development", reason="needs the development pack")
def test_offer_loop_over_http(db_url):
    """Detect -> Decide -> Approve -> Act -> Update, through the API exactly as the web and mobile apps call it."""
    path = PACKS[0]
    speech = FakeSpeech()
    pack, api = app_for(path, db_url, speech)
    with TestClient(api) as client:
        post_csv(client, raw_rows(path, "inputs/event_stream.csv"))
        queue = client.get("/snapshot", headers=COORD).json()["queue"]["items"]
        item = next(i for i in queue if i["fix"]["kind"] == "split_shift")
        table = client.get(f"/gaps/{item['id']}/candidates", headers=COORD).json()["candidates"]
        best = next(c for c in table if c["physician_id"] == item["fix"]["physician_id"])
        assert best["eligible"] and best["rank"] == 1 and all(r["status"] == "pass" for r in best["results"])
        trap = client.get(f"/gaps/{item['id']}/trap-check", headers=LEAD).json()
        assert trap["passed"] and trap["seed_consults"] > 0 and [h["hospital_id"] for h in trap["limited_to"]] == best["window"]["hospitals"]
        assert len(trap["steps"]) == len(trap["with"]) >= 7 and set(trap["scenarios"]["baseline"]) == {"no_joiner", "trap", "guarded"}

        body = {"gap_id": item["id"], "physician_id": best["physician_id"], "start": best["window"]["start"], "end": best["window"]["end"]}
        offer = client.post("/offers", json=body, headers={**COORD, "Idempotency-Key": "p1"}).json()
        assert offer["state"] == "Proposed" and offer["hospital_ids"] == best["window"]["hospitals"] and offer["checked_count"] == len(pack.ops.roster)
        assert client.post("/offers", json=body, headers={**COORD, "Idempotency-Key": "p1"}).json() == offer  # a retried click: no second offer
        snap = client.get("/snapshot", headers=LEAD).json()
        assert snap["headline"]["offers_awaiting_approval"] == 1 and snap["pending_approvals"] == 1
        sent = client.post(f"/offers/{offer['offer_id']}/approve", headers=LEAD).json()
        assert sent["state"] == "Sent" and sent["approved_by"] == "Dr. Lead" and "split-shift offer" in sent["message"]
        assert sent["audio_url"] == f"/offers/{offer['offer_id']}/audio"

        token = client.post("/admin/physician-tokens", json={"physician_id": best["physician_id"]}, headers=ADMIN).json()["token"]
        doc = {"Authorization": f"Bearer {token}"}
        other = client.post("/admin/physician-tokens", json={"physician_id": next(p for p in pack.ops.roster if p != best["physician_id"])},
                            headers=ADMIN).json()["token"]
        assert client.get(f"/offers/{offer['offer_id']}", headers={"Authorization": f"Bearer {other}"}).status_code == 404  # not probeable
        mine = client.get("/me/offers", headers=doc).json()
        assert [o["offer_id"] for o in mine["items"]] == [offer["offer_id"]] and mine["now"]
        audio = client.get(f"/offers/{offer['offer_id']}/audio", headers=doc)
        assert audio.status_code == 200 and audio.headers["content-type"] == "audio/mpeg"
        consult_ids = {r.consult_id for r in pack.rows.values() if r.consult_id}
        assert "split-shift offer" in speech.texts[-1]
        critical = next(i for i in queue if i["severity"] == "Critical" and i["where"].get("consult_id"))
        assert client.get(f"/alerts/{critical['id']}/audio", headers=COORD).status_code == 200
        # Neither message can carry consult or patient detail: no consult ID, no consult type.
        assert not [t for t in speech.texts if any(c in t for c in consult_ids) or "Stroke" in t or "Neuro" in t]

        accepted = client.post(f"/me/offers/{offer['offer_id']}/accept", headers=doc).json()
        assert accepted["state"] == "Accepted" and accepted["responded_at"]
        refused = client.post(f"/offers/{offer['offer_id']}/decline", headers=doc).json()
        assert refused["error"]["code"] == "conflicting_reply" and refused["detail"] == "offer is ACCEPTED"
        after = client.get("/snapshot", headers=COORD).json()
        assert not [i for i in after["queue"]["items"] if i["fix"]["kind"] == "split_shift" and i["fix"]["physician_id"] == best["physician_id"]]
        trail = client.get("/audit", params={"gap_id": item["id"]}, headers=LEAD).json()["items"]
        assert any(a["command"] == "recommendation" and a["evidence"]["candidates"] for a in trail)
        trail = [a for a in trail if a["command"] != "recommendation"]
        assert [a["command"] for a in trail] == ["propose", "approve", "send", "accept", "decline:refused"]
        assert trail[1]["actor"] == "Dr. Lead" and trail[0]["action"] == "Proposed offer"


@pytest.mark.skipif(not PACKS or PACKS[0].name != "01_development", reason="needs the development pack")
def test_interventions_recorded_and_escalations_need_the_lead(db_url):
    path = PACKS[0]
    pack, api = app_for(path, db_url)
    with TestClient(api) as client:
        post_csv(client, raw_rows(path, "inputs/event_stream.csv"))
        queue = client.get("/snapshot", headers=COORD).json()["queue"]["items"]
        assign = next(i for i in queue if i["fix"]["kind"] in {"assign", "reassign"})
        done = client.post("/interventions", json={"kind": "reassign", "item_id": assign["id"], "physician_id": assign["fix"]["physician_id"]},
                           headers=COORD).json()
        assert done["state"] == "RECORDED"
        bad = client.post("/interventions", json={"kind": "reassign", "item_id": assign["id"], "physician_id": "PHY-NOPE"}, headers=COORD)
        assert bad.status_code == 422  # the server checks shift and credentials, not the client
        escalation = next(i for i in queue if i["fix"]["kind"] == "escalate")
        req = client.post("/interventions", json={"kind": "escalate", "item_id": escalation["id"]}, headers=COORD).json()
        assert req["state"] == "REQUESTED"
        assert client.post(f"/interventions/{req['id']}/authorize", headers=COORD).status_code == 403
        assert client.post(f"/interventions/{req['id']}/authorize", headers=LEAD).json()["state"] == "AUTHORIZED"
        shown = {i["id"]: i["intervention"] for i in client.get("/snapshot", headers=LEAD).json()["queue"]["items"]}
        assert shown[assign["id"]]["state"] == "RECORDED" and shown[escalation["id"]]["state"] == "AUTHORIZED"


def test_websocket_sends_whole_snapshots_and_refuses_bad_tokens(db_url):
    path = PACKS[0]
    pack, api = app_for(path, db_url)
    with TestClient(api) as client:
        post_csv(client, raw_rows(path, "inputs/event_stream.csv"))
        with client.websocket_connect("/ws?token=coord-token") as ws:
            msg = ws.receive_json()
            assert msg["seq"] == 1 and msg["snapshot"]["queue"]["supported"] and msg["epoch"] == msg["snapshot"]["epoch"]
        with pytest.raises(Exception):
            with client.websocket_connect("/ws?token=wrong") as ws:
                ws.receive_json()


def test_admin_clock_moves_and_reset_starts_clean(db_url):
    path = PACKS[0]
    pack, api = app_for(path, db_url)
    with TestClient(api) as client:
        post_csv(client, raw_rows(path, "inputs/event_stream.csv"))
        set_clock(client, pack.time("1820"), "anchored")
        first = client.get("/snapshot", headers=COORD).json()["clock"]["now"]
        assert datetime.fromisoformat(first) >= pack.time("1820")  # anchored: real time runs forward from 18:20
        assert client.post("/admin/reset", headers=ADMIN).json()["reset"]
        snap = client.get("/snapshot", headers=COORD).json()
        assert snap["consults"] == [] and snap["offers"]["items"] == []
        post_csv(client, raw_rows(path, "inputs/event_stream.csv"))  # the same file is new data in the new generation
        assert client.get("/snapshot", headers=COORD).json()["consults"]


def test_decisions_need_references(db_url):
    api = create_app(db_url, FixedClock(datetime(2026, 3, 17, 22, 20, tzinfo=timezone.utc)), auth=TEST_AUTH, speech=FakeSpeech(), sweep_s=0)
    with TestClient(api) as client:
        assert client.get("/snapshot", headers=COORD).json()["queue"]["supported"] is False
        assert client.get("/gaps/x/candidates", headers=COORD).status_code == 503


def test_password_accounts_reach_the_same_routes(db_url):
    """Web and mobile sign in with an email and password; the token carries the same permissions as the role tokens."""
    import json
    from app.auth import Accounts, Auth
    from app.passwords import hash_password
    path = PACKS[0]
    pack = load_pack(path)
    pid = next(iter(pack.ops.roster))
    h = hash_password("right-password", iterations=1_000)
    users = json.dumps([{"email": "lead@x.test", "name": "Dr. Lead", "role": "lead", "password_hash": h},
                        {"email": "doc@x.test", "name": "Dr. Doc", "role": "physician", "physician_id": pid, "password_hash": h}])
    api = create_app(db_url, FixedClock(pack.time("1820")), auth=Auth(Accounts(users, "s" * 32)), references=load_references(path / "inputs"),
                     speech=FakeSpeech(), sweep_s=0)
    with TestClient(api) as client:
        lead = client.post("/auth/login", json={"email": "lead@x.test", "password": "right-password"}).json()
        doc = client.post("/auth/login", json={"email": "doc@x.test", "password": "right-password"}).json()
        assert lead["user"]["role_label"] == "Clinical lead" and doc["user"]["physician_id"] == pid
        as_lead, as_doc = {"Authorization": f"Bearer {lead['token']}"}, {"Authorization": f"Bearer {doc['token']}"}
        assert client.get("/snapshot", headers=as_lead).status_code == 200
        assert client.get("/me", headers=as_lead).json()["permissions"] == ["ops.view", "approvals.decide", "offers.view_all", "admin.inject"]
        assert client.get("/me/offers", headers=as_doc).json()["items"] == []
        assert client.get("/snapshot", headers=as_doc).status_code == 403
        assert client.post("/offers", json={"gap_id": "x", "physician_id": pid, "start": "2026-03-17T23:00:00Z", "end": "2026-03-18T01:00:00Z"},
                           headers=as_lead).status_code == 403  # only a coordinator proposes


def test_judge_file_on_the_original_kit_updates_without_restart(db_url):
    """Chapter 4: one CSV in event_stream format, new wording included, dropped into the running tool."""
    from datetime import date
    from pathlib import Path
    kit = Path(__file__).resolve().parents[2] / "data"
    if not (kit / "event_stream.csv").exists():
        pytest.skip("source data is gitignored")
    api = create_app(db_url, FixedClock(datetime.fromisoformat("2026-03-17T18:20:00-04:00")), auth=TEST_AUTH,
                     references=load_references(kit, date(2026, 3, 17)), speech=FakeSpeech(), sweep_s=0)
    judge = (b"event_id,event_time,ingested_at,consult_id,event_type,physician_id,hospital_id,description\n"
             b"EVT-J001,2026-03-17T18:21:00-04:00,2026-03-17T18:21:02-04:00,CON-J01,consult_received,,SYN-005,Acute stroke consult requested\n"
             b"EVT-J002,2026-03-17T18:21:40-04:00,2026-03-17T18:21:41-04:00,CON-J01,consult_triaged,,SYN-005,Consult triaged\n"
             b"EVT-J001,2026-03-17T18:21:00-04:00,2026-03-17T18:21:02-04:00,CON-J01,consult_received,,SYN-005,Acute stroke consult requested\n"
             b"EVT-J003,2026-03-17T18:30:00-04:00,2026-03-17T18:30:01-04:00,CON-J01,consult_received,,SYN-005,Stroke consult request received\n")
    with TestClient(api) as client:
        base = post_csv(client, raw_rows(kit, "event_stream.csv"))
        assert (base["accepted"], base["duplicates"], base["reordered"], base["late"]) == (1163, 1, 23, 1)
        r = client.post("/events/csv", params={"advance_clock": "true"}, content=judge, headers={**ADMIN, "Content-Type": "text/csv"}).json()
        assert (r["accepted"], r["duplicates"], r["quarantined"], r["pending_future"]) == (3, 1, [], 0)
        assert r["clock_advanced_to"] == r["latest_event_time"] == datetime.fromisoformat("2026-03-17T18:30:00-04:00").astimezone(timezone.utc).isoformat()
        snap = client.get("/snapshot", headers=COORD).json()
        new = next(c for c in snap["consults"] if c["consult_id"] == "CON-J01")
        assert (new["consult_type"], new["repeat_contacts"], new["minutes_since_received"]) == ("Stroke", 1, 9)  # one patient, first clock
        assert any("CON-J01" in (i["where"].get("consult_id") or "") for i in snap["queue"]["items"] if i["severity"] == "Critical")
        assert next(s for s in snap["forecast"]["surges"] if s["hospital_id"] == "SYN-005")["count"] == 6  # repeat call is not new demand


def test_uploaded_references_turn_decisions_on_and_survive_a_restart(db_url, monkeypatch):
    """A host has no CC_DATA_DIR: decisions are off until the reference CSVs are uploaded; the database keeps them."""
    from dataclasses import replace
    from app import main
    from app.service import REFERENCE_FILES
    monkeypatch.setattr(main, "settings", replace(main.settings, reference_dir=None))
    path = PACKS[0]
    pack = load_pack(path)
    files = {name: (path / "inputs" / name).read_text(encoding="utf-8-sig") for name in REFERENCE_FILES}
    hosted = lambda: create_app(db_url, FixedClock(pack.time("1820")), auth=TEST_AUTH, speech=FakeSpeech(), sweep_s=0)
    with TestClient(hosted()) as client:
        assert client.get("/ready").json()["capabilities"]["detection"] is False
        assert client.get("/gaps/x/candidates", headers=COORD).status_code == 503
        missing = {k: v for k, v in files.items() if k != "coverage_requirements.csv"}
        assert client.post("/admin/references", json={"files": missing}, headers=ADMIN).status_code == 422
        bad = {**files, "hospitals.csv": files["hospitals.csv"].replace("America/", "Nowhere/", 1)}
        assert client.post("/admin/references", json={"files": bad}, headers=ADMIN).status_code == 422
        assert client.post("/admin/references", json={"files": files}, headers={**ADMIN, "Authorization": "Bearer wrong"}).status_code == 401
        r = client.post("/admin/references", json={"files": files, "name": "pack 01"}, headers=COORD)
        assert r.status_code == 200 and r.json()["hospitals"] == len(pack.refs.hospitals) and r.json()["physicians"] == len(pack.refs.physicians)
        assert client.get("/ready").json()["capabilities"]["detection"] is True
        post_csv(client, raw_rows(path, "inputs/event_stream.csv"))
        assert served_queue(client) == expected_queue(pack, pack.time("1820"))
    with TestClient(hosted()) as client:  # restart: nothing on disk, references come back from the database
        assert client.get("/ready").json()["capabilities"]["detection"] is True
        assert client.get("/snapshot", headers=COORD).json()["dataset"]["name"] == "pack 01"
        assert served_queue(client) == expected_queue(pack, pack.time("1820"))


def test_sample_layout_upload_needs_its_service_date(db_url, monkeypatch):
    from dataclasses import replace
    from pathlib import Path
    from app import main
    from app.service import REFERENCE_FILES
    kit = Path(__file__).resolve().parents[2] / "data"
    if not (kit / "hospitals.csv").exists():
        pytest.skip("source data is gitignored")
    monkeypatch.setattr(main, "settings", replace(main.settings, reference_dir=None))
    files = {name: (kit / name).read_text(encoding="utf-8-sig") for name in REFERENCE_FILES}
    with TestClient(create_app(db_url, FixedClock(datetime.fromisoformat("2026-03-17T18:20:00-04:00")), auth=TEST_AUTH,
                               speech=FakeSpeech(), sweep_s=0)) as client:
        assert client.post("/admin/references", json={"files": files}, headers=ADMIN).status_code == 422
        assert client.post("/admin/references", json={"files": files, "service_date": "2026-03-17"}, headers=ADMIN).status_code == 200
        assert client.get("/ready").json()["capabilities"]["detection"] is True


@by_pack
def test_my_shift_shows_a_physician_only_their_own_shift_and_consults(path, db_url):
    pack, api = app_for(path, db_url)
    now = pack.time("1820")
    state = state_at(pack.rows, now)
    token = lambda pid: {"Authorization": f"Bearer {TEST_AUTH.physician_token(pid, datetime.now(timezone.utc) + timedelta(hours=1))}"}
    on_shift = next(pid for pid, p in sorted(pack.refs.physicians.items()) if any(s.start <= now < s.end for s in p.shifts)
                    and any(c.owner == pid and c.stage != "Signed Off" for c in state.consults.values()))
    with TestClient(api) as client:
        post_csv(client, raw_rows(path, "inputs/event_stream.csv"))
        me = client.get("/me/shift", headers=token(on_shift)).json()
        shift = next(s for s in pack.refs.physicians[on_shift].shifts if s.start <= now < s.end)
        assert me["minutes_to_shift_end"] == int((shift.end - now).total_seconds() // 60) and at(me["shift_end"]) == shift.end
        assert {c["consult_id"] for c in me["consults"]} == {c.consult_id for c in state.consults.values() if c.owner == on_shift and c.stage != "Signed Off"}
        off = client.get("/me/shift", headers=token(next(iter(pack.ops.roster)))).json()
        assert off["shift_end"] is None and off["hospitals"] == [] and off["consults"] == []
        assert client.get("/me/shift", headers=COORD).status_code == 403
