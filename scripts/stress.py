"""Concurrent snapshot readers plus an optional steady event writer.

Usage: python scripts/stress.py --url http://127.0.0.1:8000 --seed 2000 --readers 16 --seconds 20 --write-rate 5
The seed and write operations add synthetic consults. Use only a disposable test database.
"""
import argparse
from datetime import datetime, timedelta, timezone
import json
import os
from statistics import quantiles
import threading
import time
from http.client import HTTPConnection
from urllib.parse import urlsplit
from uuid import uuid4


local = threading.local()


# CC_TOKEN signs the requests in when the server has sign-in turned on.
HEADERS = {"Content-Type": "application/json", **({"Authorization": f"Bearer {os.environ['CC_TOKEN']}"} if os.environ.get("CC_TOKEN") else {})}


def call(url, payload=None):
    """One keep-alive connection per thread, as a browser would hold."""
    parts = urlsplit(url)
    if getattr(local, "conn", None) is None:
        local.conn = HTTPConnection(parts.hostname, parts.port or 80, timeout=30)
    data = json.dumps(payload).encode() if payload is not None else None
    start = time.perf_counter()
    try:
        local.conn.request("POST" if data else "GET", parts.path, data, HEADERS)
        response = local.conn.getresponse()
        response.read()
    except OSError:
        local.conn.close()
        local.conn = None
        raise
    if response.status >= 400:
        raise OSError(f"HTTP {response.status}")
    return (time.perf_counter() - start) * 1000


def consults(prefix, start, count):
    at = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
    return [{"event_id": f"{prefix}-E{i}", "event_time": at, "event_type": "consult_received",
             "consult_id": f"{prefix}-C{i}", "hospital_id": "stress-hospital", "consult_type": "Stroke"}
            for i in range(start, start + count)]


def summary(name, samples, errors, seconds):
    if not samples:
        return f"{name}: no successful requests, {errors} errors"
    cuts = quantiles(samples, n=100) if len(samples) > 1 else samples * 99
    return (f"{name}: {len(samples)} ok, {errors} errors, {len(samples) / seconds:.0f}/s, "
            f"p50 {cuts[49]:.1f} ms, p95 {cuts[94]:.1f} ms, p99 {cuts[98]:.1f} ms")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    parser.add_argument("--seed", type=int, default=0, help="open consults to add before measuring")
    parser.add_argument("--readers", type=int, default=16)
    parser.add_argument("--seconds", type=float, default=20)
    parser.add_argument("--write-rate", type=float, default=0, help="single-event POSTs per second during the run")
    args = parser.parse_args()
    url, prefix = args.url.rstrip("/"), f"stress-{uuid4().hex[:8]}"
    for start in range(0, args.seed, 500):
        call(url + "/events", consults(prefix, start, min(500, args.seed - start)))
    stop = time.monotonic() + args.seconds
    results, kinds = {"snapshot": ([], [0]), "ingest": ([], [0])}, {}

    def loop(name, target, pause=0.0):
        samples, errors = results[name]
        i = 0
        while time.monotonic() < stop:
            try:
                samples.append(target(i))
            except OSError as exc:
                errors[0] += 1
                kinds[f"{name}: {exc}"[:90]] = kinds.get(f"{name}: {exc}"[:90], 0) + 1
            i += 1
            time.sleep(pause)

    threads = [threading.Thread(target=loop, args=("snapshot", lambda i: call(url + "/snapshot"))) for _ in range(args.readers)]
    if args.write_rate:
        threads.append(threading.Thread(target=loop, args=("ingest", lambda i: call(url + "/events", consults(prefix + "-w", i, 1)[0]), 1 / args.write_rate)))
    for t in threads: t.start()
    for t in threads: t.join()
    print(f"{args.readers} readers, {args.write_rate}/s writes, {args.seed} seeded consults, {args.seconds:.0f} s")
    for name, (samples, errors) in results.items():
        if name == "snapshot" or args.write_rate:
            print(summary(name, samples, errors[0], args.seconds))
    for kind, count in sorted(kinds.items()):
        print(f"  {count} x {kind}")


if __name__ == "__main__":
    main()
