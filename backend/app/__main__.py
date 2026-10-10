"""Cloud-neutral container launcher. One process owns the in-memory state."""
import os
import sys


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
    main()
