"""Upload a folder's six reference CSVs to a running backend (POST /admin/references).

Usage: python scripts/upload_references.py data --url https://<host> --service-date 2026-03-17
       python scripts/upload_references.py test_data/01_development/inputs --url http://127.0.0.1:8000
--service-date is needed only for the kit's sample layout (shift times without a date).
Signs in with CC_API_TOKEN if set (an account or admin token), otherwise asks for an account email and password.
"""
import argparse
import getpass
import hashlib
import json
import os
from pathlib import Path
from urllib.error import HTTPError
from http.client import HTTPException
from urllib.request import Request, urlopen

FILES = ("hospitals.csv", "physicians_on_shift.csv", "physicians_off_shift_roster.csv", "credentialing_matrix.csv",
         "baseline_hourly_volume.csv", "coverage_requirements.csv")


def request(url, payload=None, token=None):
    headers = {"Content-Type": "application/json", **({"Authorization": f"Bearer {token}"} if token else {})}
    try:
        with urlopen(Request(url, json.dumps(payload).encode() if payload is not None else None, headers), timeout=60) as response:
            return json.load(response)
    except HTTPError as error:
        raise SystemExit(f"{error.code}: {error.read().decode(errors='replace')}") from None
    except (OSError, HTTPException) as error:
        raise SystemExit(f"could not reach the API: {getattr(error, 'reason', str(error))}") from None


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("folder", type=Path)
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    parser.add_argument("--service-date")
    parser.add_argument("--name", help="dataset name shown in the apps (default: the folder name)")
    parser.add_argument("--check", action="store_true", help="verify persisted references match this folder without changing anything")
    parser.add_argument("--replace", action="store_true", help="replace a different persisted reference version (events and offers remain)")
    args = parser.parse_args()
    folder = args.folder.resolve()
    missing = [name for name in FILES if not (folder / name).exists()]
    if missing:
        raise SystemExit(f"missing in {folder}: {', '.join(missing)}")
    url = args.url.rstrip("/")
    token = os.environ.get("CC_API_TOKEN")
    if not token:
        token = request(f"{url}/auth/login", {"email": input("Account email: "), "password": getpass.getpass()})["token"]
    name = args.name or (folder.parent.name if folder.name == "inputs" else folder.name)
    payload = {"files": {n: (folder / n).read_text(encoding="utf-8-sig") for n in FILES}, "name": name,
               **({"service_date": args.service_date} if args.service_date else {})}
    content = {"files": payload["files"], "service_date": args.service_date}
    fingerprint = hashlib.sha256(json.dumps(content, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")).hexdigest()
    status = request(f"{url}/admin/references", token=token)
    matching = status["persisted"] and status["manifest"]["fingerprint"] == fingerprint
    if args.check or matching:
        if not matching:
            raise SystemExit("Reference check failed: the database does not contain this reference version.")
        print(f"Verified {status['dataset']['name']}: {status['hospitals']} hospitals, {status['physicians']} physicians. "
              f"SHA-256 {fingerprint}. No changes made.")
        return
    if status["persisted"] and not args.replace:
        raise SystemExit("A different reference version is persisted. Use --replace to switch intentionally; existing events and offers remain.")
    result = request(f"{url}/admin/references", payload, token)
    stored = request(f"{url}/admin/references", token=token)
    if not stored["persisted"] or stored["manifest"]["fingerprint"] != fingerprint:
        raise SystemExit("Upload finished, but the stored reference fingerprint did not match.")
    print(f"Loaded {result['dataset']['name']}: {result['hospitals']} hospitals, {result['physicians']} physicians. "
          f"SHA-256 {fingerprint}. Stored in PostgreSQL; existing events and offers retained.")


if __name__ == "__main__":
    main()
