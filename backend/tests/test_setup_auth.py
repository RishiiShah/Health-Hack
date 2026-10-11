import importlib.util
import json
from pathlib import Path
import stat
import sys

import pytest
from app.auth import Accounts, check_password

spec = importlib.util.spec_from_file_location("setup_auth", Path(__file__).resolve().parents[2] / "scripts" / "setup_auth.py")
setup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(setup)


def prompts(monkeypatch, values, password="localpw8"):
    answers = iter(values)
    monkeypatch.setattr("builtins.input", lambda _: next(answers))
    monkeypatch.setattr(setup.getpass, "getpass", lambda _: password)
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)


def test_first_run_creates_private_config_and_following_run_reuses_it(tmp_path, monkeypatch):
    path = tmp_path / "local" / "auth.json"
    monkeypatch.setattr(setup, "CONFIG", path)
    monkeypatch.setattr(sys, "argv", ["setup_auth.py"])
    prompts(monkeypatch, ["Coord@Example.test", "Coordinator", ""])
    setup.main()
    original = path.read_bytes()
    config = setup.read_config(path)
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert b"localpw8" not in original
    assert check_password("localpw8", config["users"][0]["password_hash"])
    auth = Accounts(json.dumps(config["users"]), config["secret"])
    assert auth.login("coord@example.test", "localpw8")[1].role == "coordinator"
    monkeypatch.setattr("builtins.input", lambda _: pytest.fail("Configured startup must not prompt again"))
    setup.main()
    assert path.read_bytes() == original


def test_adding_account_preserves_existing_key_and_accounts(tmp_path, monkeypatch):
    path = tmp_path / "auth.json"
    monkeypatch.setattr(setup, "CONFIG", path)
    monkeypatch.setattr(sys, "argv", ["setup_auth.py"])
    prompts(monkeypatch, ["coord@example.test", "Coordinator", ""])
    setup.main()
    original = setup.read_config(path)
    monkeypatch.setattr(sys, "argv", ["setup_auth.py", "--add-user"])
    prompts(monkeypatch, ["doc@example.test", "Doctor", "physician", "P1"])
    setup.main()
    updated = setup.read_config(path)
    assert updated["secret"] == original["secret"]
    assert updated["users"][0] == original["users"][0]
    assert updated["users"][1]["physician_id"] == "P1"


def test_setup_requires_terminal_instead_of_creating_default_credentials(tmp_path, monkeypatch):
    path = tmp_path / "auth.json"
    monkeypatch.setattr(setup, "CONFIG", path)
    monkeypatch.setattr(sys, "argv", ["setup_auth.py"])
    monkeypatch.setattr(sys.stdin, "isatty", lambda: False)
    with pytest.raises(SystemExit, match="terminal"):
        setup.main()
    assert not path.exists()
