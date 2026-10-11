"""Upload a folder's six reference CSVs to a running backend (POST /admin/references).

Usage: python scripts/upload_references.py data --url https://<host> --service-date 2026-03-17
       python scripts/upload_references.py test_data/01_development/inputs --url http://127.0.0.1:8000
--service-date is needed only for the kit's sample layout (shift times without a date).
Signs in with CC_API_TOKEN if set (an account or admin token), otherwise asks for an account email and password.
"""
import argparse
import getpass
import json
import os
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

FILES = ("hospitals.csv", "physicians_on_shift.csv", "physicians_off_shift_roster.csv", "credentialing_matrix.csv",
         "baseline_hourly_volume.csv", "coverage_requirements.csv")


def post(url, payload, token=None):
    headers = {"Content-Type": "application/json", **({"Authorization": f"Bearer {token}"} if token else {})}
    try:
        with urlopen(Request(url, json.dumps(payload).encode(), headers), timeout=60) as response:
            return json.load(response)
    except HTTPError as error:
        raise SystemExit(f"{error.code}: {error.read().decode(errors='replace')}") from None


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("folder", type=Path)
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    parser.add_argument("--service-date")
    parser.add_argument("--name", help="dataset name shown in the apps (default: the folder name)")
    args = parser.parse_args()
    folder = args.folder.resolve()
    missing = [name for name in FILES if not (folder / name).exists()]
    if missing:
        raise SystemExit(f"missing in {folder}: {', '.join(missing)}")
    url = args.url.rstrip("/")
    token = os.environ.get("CC_API_TOKEN")
    if not token:
        token = post(f"{url}/auth/login", {"email": input("Account email: "), "password": getpass.getpass()})["token"]
    name = args.name or (folder.parent.name if folder.name == "inputs" else folder.name)
    payload = {"files": {n: (folder / n).read_text(encoding="utf-8-sig") for n in FILES}, "name": name,
               **({"service_date": args.service_date} if args.service_date else {})}
    result = post(f"{url}/admin/references", payload, token)
    print(f"Loaded {result['dataset']['name']}: {result['hospitals']} hospitals, {result['physicians']} physicians. "
          "Decisions are on; POST /admin/reset to start this dataset with an empty event stream.")


if __name__ == "__main__":
    main()
