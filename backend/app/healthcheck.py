"""Container readiness probe; uses only the Python standard library."""
import json
from urllib.request import urlopen
from app.__main__ import server_port


def main():
    with urlopen(f"http://127.0.0.1:{server_port()}/ready", timeout=3) as response:
        if response.status != 200 or json.load(response).get("ready") is not True:
            raise SystemExit(1)


if __name__ == "__main__":
    main()
