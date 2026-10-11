import json
import base64
import hashlib
import hmac
import pytest
from fastapi.testclient import TestClient
from app.auth import Accounts, Auth, check_password, hash_password
from app.clock import FixedClock
from app.main import create_app
from datetime import datetime

SECRET = "s" * 32
NO_TOKENS = {"coordinator_token": None, "lead_token": None, "admin_token": None, "lead_name": "Lead", "token_secret": None}
HASH = hash_password("right-password", iterations=1_000)
USERS = json.dumps([
    {"email": "Coord@Example.test", "name": "Coordinator", "role": "coordinator", "password_hash": HASH},
    {"email": "lead@example.test", "name": "Lead", "role": "lead", "password_hash": HASH},
    {"email": "doc@example.test", "name": "Dr. Doc", "role": "physician", "physician_id": "P1", "password_hash": HASH},
])


@pytest.fixture
def client(db_url):
    clock = FixedClock(datetime.fromisoformat("2026-03-17T13:00:00-04:00"))
    with TestClient(create_app(db_url, clock, auth=Auth(Accounts(USERS, SECRET)), sweep_s=0)) as c:
        yield c


def sign_in(client, email, portal="operations", password="right-password"):
    return client.post("/auth/login", json={"email": email, "password": password, "portal": portal})


def test_password_hashes_verify_only_the_original():
    stored = hash_password("pw", iterations=1_000)
    assert check_password("pw", stored) and not check_password("PW", stored)
    assert not check_password("pw", "plain-text") and stored != hash_password("pw", iterations=1_000)


def test_login_returns_a_token_and_the_account_role(client):
    response = sign_in(client, " COORD@example.test ")
    assert response.status_code == 200
    body = response.json()
    assert body["user"] == {"email": "coord@example.test", "name": "Coordinator", "role": "coordinator",
                            "role_label": "Operations coordinator", "physician_id": None}
    me = client.get("/auth/me", headers={"Authorization": f"Bearer {body['token']}"})
    assert me.json()["user"]["role"] == "coordinator"
    assert response.headers["cache-control"] == "no-store"
    assert me.headers["cache-control"] == "no-store"


@pytest.mark.parametrize("email, role", [("coord@example.test", "coordinator"), ("lead@example.test", "lead"), ("doc@example.test", "physician")])
def test_login_without_portal_routes_by_account(client, email, role):
    response = client.post("/auth/login", json={"email": email, "password": "right-password"})
    assert response.status_code == 200
    assert response.json()["user"]["role"] == role


@pytest.mark.parametrize("stored", ["pbkdf2_sha256$bad$ff$ff", "pbkdf2_sha256$-1$00$00", "pbkdf2_sha256$1000$not-hex$00", None])
def test_malformed_password_hashes_fail_closed(stored):
    assert not check_password("pw", stored)
    rows = json.loads(USERS)
    rows[0]["password_hash"] = stored
    with pytest.raises(ValueError, match="password hash"):
        Accounts(json.dumps(rows), SECRET)


@pytest.mark.parametrize("claims", [None, [], {}, {"sub": [], "exp": 5000}, {"sub": "lead@example.test", "exp": "later"}])
def test_malformed_signed_claims_are_rejected_without_server_errors(claims):
    auth = Accounts(USERS, SECRET, now=lambda: 1000)
    body = base64.urlsafe_b64encode(json.dumps(claims).encode()).rstrip(b"=").decode()
    sig = base64.urlsafe_b64encode(hmac.new(SECRET.encode(), body.encode(), hashlib.sha256).digest()).rstrip(b"=").decode()
    assert auth.verify(f"{body}.{sig}") is None


@pytest.mark.parametrize("environment_users", ["", "stale-or-interpolated-accounts"])
def test_local_config_loads_real_auth_without_disabling_roles(tmp_path, monkeypatch, environment_users):
    from types import SimpleNamespace
    import app.main as main
    config = tmp_path / "auth.json"
    config.write_text(json.dumps({"users": json.loads(USERS), "secret": SECRET}))
    monkeypatch.setattr(main, "settings", SimpleNamespace(users=environment_users, auth_secret="", auth_config=str(config), **NO_TOKENS))
    auth = main.auth_from_settings()
    token, _, _ = auth.accounts.login("doc@example.test", "right-password")
    assert auth.identify(token, datetime.now().astimezone()).role == "physician"


def test_auth_never_silently_disables_when_config_is_missing(monkeypatch):
    from types import SimpleNamespace
    import app.main as main
    monkeypatch.setattr(main, "settings", SimpleNamespace(users="", auth_secret="", auth_config=None, **NO_TOKENS))
    with pytest.raises(RuntimeError, match="make backend"):
        main.auth_from_settings()


def test_wrong_password_and_unknown_email_look_the_same(client):
    assert sign_in(client, "lead@example.test", password="nope").json() == sign_in(client, "who@example.test").json()
    assert sign_in(client, "who@example.test").status_code == 401


def test_wrong_portal_says_which_one_to_use(client):
    response = sign_in(client, "doc@example.test", portal="operations")
    assert response.status_code == 403 and "Sign in as Physician" in response.json()["detail"]
    assert "Sign in as Operations" in sign_in(client, "lead@example.test", portal="physician").json()["detail"]


def test_operations_routes_need_an_operations_role(client):
    assert client.get("/snapshot").status_code == 401
    assert client.get("/snapshot", headers={"Authorization": "Bearer forged.token"}).status_code == 401
    doc = sign_in(client, "doc@example.test", portal="physician").json()["token"]
    assert client.get("/snapshot", headers={"Authorization": f"Bearer {doc}"}).status_code == 403
    for email in ("coord@example.test", "lead@example.test"):
        token = sign_in(client, email).json()["token"]
        assert client.get("/snapshot", headers={"Authorization": f"Bearer {token}"}).status_code == 200
    assert client.get("/ready").json()["capabilities"]["authentication"] is True


def test_tokens_expire_and_tampering_is_rejected():
    now = [1_000.0]
    auth = Accounts(USERS, SECRET, now=lambda: now[0])
    token, _, _ = auth.login("lead@example.test", "right-password", "operations")
    newer, _, _ = auth.login("lead@example.test", "right-password", "operations")
    assert newer != token  # A late 401 for the previous login cannot identify this session.
    assert auth.verify(token).role == "lead"
    body, _, signature = token.partition(".")
    assert auth.verify(body + "x." + signature) is None
    assert auth.verify(token + "ü") is None
    now[0] += 12 * 3600
    assert auth.verify(token) is None


@pytest.mark.parametrize("users, secret", [
    (USERS, "short"),
    (json.dumps([{"email": "a@x", "name": "A", "role": "admin", "password_hash": HASH}]), SECRET),
    (json.dumps([{"email": "a@x", "name": "A", "role": "physician", "password_hash": HASH}]), SECRET),
    ("[]", SECRET),
])
def test_bad_account_config_fails_at_startup(users, secret):
    with pytest.raises(ValueError):
        Accounts(users, secret)
