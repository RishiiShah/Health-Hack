"""Probe a disposable deployment and verify data after container replacement.

Usage: python scripts/hosting_smoke.py seed|verify --url http://127.0.0.1:8000
The seed operation writes synthetic test data. Use only a disposable test database.
Tokens come from CC_ADMIN_TOKEN (seed) and CC_COORDINATOR_TOKEN (snapshot), the same variables the server reads.
"""
import argparse
import json
import os
import time
from urllib.error import URLError
from urllib.request import Request, urlopen


def request(url, payload=None, token=None):
    data = json.dumps(payload).encode() if payload is not None else None
    headers = {"Content-Type":"application/json", **({"Authorization": f"Bearer {token}"} if token else {})}
    req = Request(url, data=data, headers=headers)
    with urlopen(req, timeout=3) as response:
        return json.load(response)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("seed", "verify"))
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    args = parser.parse_args()
    url = args.url.rstrip("/")
    deadline = time.monotonic() + 45
    while True:
        try:
            if request(url + "/ready").get("ready") is True:
                break
        except (URLError, TimeoutError, OSError):
            pass
        if time.monotonic() >= deadline:
            raise SystemExit("Deployment did not become ready within 45 seconds")
        time.sleep(0.5)
    snapshot = request(url + "/snapshot", token=os.environ.get("CC_COORDINATOR_TOKEN"))
    existing = next((c for c in snapshot["consults"] if c["consult_id"] == "hosting-smoke-consult"), None)
    if args.operation == "seed" and existing is None:
        # A paused rehearsal uses simulation time; wall time can leave the event outside replay.
        at = snapshot["clock"]["now"]
        known = sorted(h["hospital_id"] for h in snapshot.get("hospitals", {}).get("items", []))
        hospital = known[0] if known else "hosting-smoke-hospital"  # storage-only check when decisions are unavailable
        report = request(url + "/events", {
            "event_id":"hosting-smoke-event", "consult_id":"hosting-smoke-consult",
            "event_time":at, "ingested_at":at, "event_type":"consult_received",
            "hospital_id":hospital, "consult_type":"General Neuro",
        }, os.environ.get("CC_ADMIN_TOKEN"))
        if report["accepted"] != 1:
            raise SystemExit(f"Synthetic event was not accepted: {report}")
    snapshot = request(url + "/snapshot", token=os.environ.get("CC_COORDINATOR_TOKEN"))
    if not any(c["consult_id"] == "hosting-smoke-consult" for c in snapshot["consults"]):
        raise SystemExit("Published snapshot did not contain the committed synthetic event")
    print(f"PASS: {args.operation}, ready service and persisted consult; decisions available: {snapshot.get('capabilities', {}).get('detection', False)}")


if __name__ == "__main__":
    main()
