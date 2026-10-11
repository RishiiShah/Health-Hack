"""Real server process checks using the same launcher as the Docker image."""
import os
from pathlib import Path
import socket
import signal
import subprocess
import sys


def test_cloud_launcher_and_database_recovery_across_process_replacement(tmp_path, db_url):
    backend = Path(__file__).resolve().parents[1]
    smoke = backend.parent / "scripts" / "hosting_smoke.py"
    env = {**os.environ, "CC_DATABASE_URL": db_url,
           "CC_CLOCK_MODE": "wall", "CC_CLOCK_FIXED": "", "CC_ADMIN_TOKEN": "smoke-admin", "CC_COORDINATOR_TOKEN": "smoke-coord"}
    for operation in ("seed", "verify"):
        with socket.socket() as socket_probe:
            socket_probe.bind(("127.0.0.1", 0))
            port = socket_probe.getsockname()[1]
        env["PORT"] = str(port)
        with (tmp_path / f"{operation}.log").open("w") as log:
            server = subprocess.Popen([sys.executable, "-m", "app"], cwd=backend,
                                      env=env, stdout=log, stderr=subprocess.STDOUT)
            try:
                probe = subprocess.run([sys.executable, str(smoke), operation,
                                        "--url", f"http://127.0.0.1:{port}"],
                                       capture_output=True, text=True, timeout=50, env=env)
                assert probe.returncode == 0, probe.stderr + probe.stdout
            finally:
                server.terminate()
                try:
                    server.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    server.kill()
                    server.wait()
            shutdown_log = (tmp_path / f"{operation}.log").read_text()
            # Uvicorn re-raises the original SIGTERM after completing shutdown.
            assert server.returncode in (0, -signal.SIGTERM), shutdown_log
            assert "Application shutdown complete." in shutdown_log, shutdown_log
