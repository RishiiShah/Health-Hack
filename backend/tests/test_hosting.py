from unittest.mock import patch
import sys
import pytest
from app.__main__ import main, server_port


def test_launcher_honors_cloud_port_and_preserves_one_worker(monkeypatch):
    monkeypatch.setenv("PORT", "10000")
    monkeypatch.setenv("WEB_CONCURRENCY", "4")
    with patch("app.__main__.os.execv") as execute:
        main()
    executable, args = execute.call_args.args
    assert executable == sys.executable
    assert args[:3] == [sys.executable, "-m", "uvicorn"]
    assert args[args.index("--port") + 1] == "10000"
    assert args[args.index("--host") + 1] == "0.0.0.0"
    assert args[args.index("--workers") + 1] == "1"


@pytest.mark.parametrize("port", ["0", "65536", "invalid"])
def test_invalid_host_port_fails_before_server_start(monkeypatch, port):
    monkeypatch.setenv("PORT", port)
    with pytest.raises(ValueError, match="PORT"):
        server_port()


def test_built_web_app_is_served_beside_the_api(db_url, monkeypatch, tmp_path):
    from dataclasses import replace
    from types import SimpleNamespace
    from fastapi.testclient import TestClient
    from conftest import COORD, TEST_AUTH
    from app.config import settings
    from app.main import create_app
    (tmp_path / "index.html").write_text("<!doctype html><title>web</title>")
    monkeypatch.setattr("app.main.settings", replace(settings, reference_fingerprint=None, reference_dir=None, web_dir=str(tmp_path)))
    speech = SimpleNamespace(available=False, conn=SimpleNamespace(close=lambda: None))
    with TestClient(create_app(db_url, auth=TEST_AUTH, speech=speech, sweep_s=0)) as client:
        assert "<title>web</title>" in client.get("/").text
        assert client.get("/snapshot", headers=COORD).json()["clock"]
        assert client.get("/ready").json()["ready"] is True


def test_local_env_file_fills_only_missing_variables(tmp_path, monkeypatch):
    from app.__main__ import load_env_file
    env = tmp_path / ".env"
    env.write_text("# comment\n\nCC_A=plain\nCC_B='quoted $with$dollars'\nCC_C=\"double\"\nCC_KEEP=from-file\n")
    monkeypatch.setenv("CC_KEEP", "from-environment")
    for key in ("CC_A", "CC_B", "CC_C"):
        monkeypatch.delenv(key, raising=False)
    load_env_file(env)
    import os
    assert (os.environ["CC_A"], os.environ["CC_B"], os.environ["CC_C"]) == ("plain", "quoted $with$dollars", "double")
    assert os.environ["CC_KEEP"] == "from-environment"
    load_env_file(tmp_path / "missing.env")  # no file (Render, Docker): nothing happens


def test_database_url_falls_back_to_the_image_ca_bundle(tmp_path, monkeypatch):
    from psycopg.conninfo import conninfo_to_dict
    from app import db
    bundle = tmp_path / "rds-global-bundle.pem"
    bundle.write_text("certificate")
    monkeypatch.setattr(db, "IMAGE_CA", str(bundle))
    laptop = "postgresql://u:p@db.example:5432/cc?sslmode=verify-full&sslrootcert=/Users/someone/rds-global-bundle.pem"
    fixed = conninfo_to_dict(db.usable_ca(laptop))
    assert (fixed["sslrootcert"], fixed["sslmode"], fixed["dbname"]) == (str(bundle), "verify-full", "cc")
    present = f"postgresql://u:p@db.example/cc?sslrootcert={bundle}"
    assert db.usable_ca(present) == present  # an existing file is kept as given
    assert db.usable_ca("postgresql://u:p@db.example/cc?sslrootcert=system").endswith("sslrootcert=system")


def test_server_connections_bound_lock_waits_and_idle_transactions(db_url):
    """A session stuck holding the offer lock must not hang other instances forever."""
    from app.db import connect
    with connect(db_url) as conn:
        settings = {k: conn.execute(f"SHOW {k}").fetchone()[k] for k in ("lock_timeout", "idle_in_transaction_session_timeout", "TimeZone")}
    assert settings == {"lock_timeout": "15s", "idle_in_transaction_session_timeout": "1min", "TimeZone": "UTC"}
