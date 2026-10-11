"""Launcher for local runs and the container. One process owns the in-memory state."""
import os
from pathlib import Path
import sys

# Local runs read the repository's .env (the production database and accounts). Hosts set real variables instead.
ROOT_ENV = Path(__file__).resolve().parents[2] / ".env"


def load_env_file(path: Path):
    """KEY=VALUE lines, optionally quoted; variables already in the environment win."""
    if not path.is_file():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = (part.strip() for part in line.split("=", 1))
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
            value = value[1:-1]
        os.environ.setdefault(key, value)


def server_port() -> int:
    try:
        port = int(os.environ.get("PORT", "8000"))
    except ValueError as exc:
        raise ValueError("PORT must be an integer between 1 and 65535") from exc
    if not 1 <= port <= 65535:
        raise ValueError("PORT must be an integer between 1 and 65535")
    return port


def main():
    os.execv(sys.executable, [
        sys.executable, "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0",
        "--port", str(server_port()), "--workers", "1",
        "--timeout-graceful-shutdown", "30",
    ])


if __name__ == "__main__":
    load_env_file(ROOT_ENV)
    main()
