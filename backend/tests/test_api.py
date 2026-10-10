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
    judge = sorted(raw_rows(path, "live/judge_events.csv"), key=lambda r: r["ingested_at"])
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
        assert client.post("/events/csv", content=b"", headers=COORD).status_code == 403
        assert client.post("/offers/OFR-00001/approve", headers=COORD).status_code == 403
        assert client.post("/offers", json={"gap_id": "x", "physician_id": "y", "start": "2026-01-01T00:00:00Z", "end": "2026-01-01T02:00:00Z"},
                           headers=LEAD).status_code == 403
        pid = next(iter(pack.ops.roster))
        token = client.post("/admin/physician-tokens", json={"physician_id": pid}, headers=ADMIN).json()["token"]
        doc = {"Authorization": f"Bearer {token}"}
        assert client.get("/me", headers=doc).json() == {"role": "physician", "display_name": pid, "physician_id": pid,
                                                        "permissions": ["offers.view_own", "offers.respond"]}
        assert client.get("/snapshot", headers=doc).status_code == 403
        assert client.get("/offers", headers=doc).json() == []
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
        assert best["eligible"] and all(r["passed"] for r in best["rules"])
        trap = client.get(f"/gaps/{item['id']}/trap-check", headers=LEAD).json()
        assert trap["passed"] and trap["trap_shown_unguarded"] and set(trap["scenarios"]["baseline"]) == {"no_joiner", "trap", "guarded"}

        offer = client.post("/offers", json={"gap_id": item["id"], "physician_id": best["physician_id"], "start": best["start"], "end": best["end"]},
                            headers={**COORD, "Idempotency-Key": "p1"}).json()
        assert offer["state"] == "PROPOSED" and offer["hospitals"] == best["hospitals"]
        again = client.post("/offers", json={"gap_id": item["id"], "physician_id": best["physician_id"], "start": best["start"], "end": best["end"]},
                            headers={**COORD, "Idempotency-Key": "p1"}).json()
        assert again == offer  # a retried click does not create a second offer
        assert client.get("/snapshot", headers=LEAD).json()["headline"]["offers_awaiting_approval"] == 1
        sent = client.post(f"/offers/{offer['id']}/approve", headers=LEAD).json()
        assert sent["state"] == "SENT" and sent["approved_by"] == "Dr. Lead"

        token = client.post("/admin/physician-tokens", json={"physician_id": best["physician_id"]}, headers=ADMIN).json()["token"]
        doc = {"Authorization": f"Bearer {token}"}
        other = client.post("/admin/physician-tokens", json={"physician_id": next(p for p in pack.ops.roster if p != best["physician_id"])},
                            headers=ADMIN).json()["token"]
        assert client.get(f"/offers/{offer['id']}", headers={"Authorization": f"Bearer {other}"}).status_code == 404  # not probeable
        assert [o["id"] for o in client.get("/offers", headers=doc).json()] == [offer["id"]]
        audio = client.get(f"/offers/{offer['id']}/audio", headers=doc)
        assert audio.status_code == 200 and audio.headers["content-type"] == "audio/mpeg"
        consult_ids = {r.consult_id for r in pack.rows.values() if r.consult_id}
        assert "split-shift offer" in speech.texts[-1]
        critical = next(i for i in queue if i["severity"] == "Critical" and i["where"].get("consult_id"))
        assert client.get(f"/alerts/{critical['id']}/audio", headers=COORD).status_code == 200
        # Neither message can carry consult or patient detail: no consult ID, no consult type.
        assert not [t for t in speech.texts if any(c in t for c in consult_ids) or "Stroke" in t or "Neuro" in t]

        accepted = client.post(f"/offers/{offer['id']}/accept", headers=doc).json()
        assert accepted["state"] == "ACCEPTED"
        assert client.post(f"/offers/{offer['id']}/decline", headers=doc).json()["error"]["code"] == "conflicting_reply"
        after = client.get("/snapshot", headers=COORD).json()
        assert not [i for i in after["queue"]["items"] if i["fix"]["kind"] == "split_shift" and i["fix"]["physician_id"] == best["physician_id"]]
        trail = client.get("/audit", params={"gap_id": item["id"]}, headers=LEAD).json()
        assert [a["command"] for a in trail] == ["propose", "approve", "send", "accept", "decline:refused"]
        assert trail[1]["actor"] == "Dr. Lead"


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
