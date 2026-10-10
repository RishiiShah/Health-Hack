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
