"""Read-only structural/causal validator for generated and supplied sample CSVs."""
import argparse
import csv
from datetime import date, datetime, time, timedelta, timezone
import hashlib
import json
from pathlib import Path
from zoneinfo import ZoneInfo

try:
    from .schema import DESCRIPTIONS, STAGES, TRANSITIONS, headers
except ImportError:
    from schema import DESCRIPTIONS, STAGES, TRANSITIONS, headers

UTC = timezone.utc
ET = ZoneInfo("America/New_York")


def instant(value):
    parsed = datetime.fromisoformat(value)
    if parsed.utcoffset() is None:
        raise ValueError(f"timestamp needs a UTC offset: {value}")
    return parsed.astimezone(UTC)


def read_csv(path, expected):
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != expected:
            raise ValueError(f"{path.name}: headers differ from sample-csv-v1")
        if any(any(token in name.lower() for token in ("patient", "birth", "mrn", "diagnosis")) for name in expected):
            raise ValueError(f"{path.name}: patient column is forbidden")
        rows = list(reader)
        if any(None in row or None in row.values() for row in rows):
            raise ValueError(f"{path.name}: malformed row")
        return rows


def unique(rows, key):
    result = {}
    for row in rows:
        value = row[key]
        if not value or value in result:
            raise ValueError(f"blank/duplicate {key}: {value}")
        result[value] = row
    return result


def validate(directory):
    directory = Path(directory)
    manifest_path = directory / "manifest.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else None
    hospitals = unique(read_csv(directory / "hospitals.csv", headers("hospitals")), "hospital_id")
    for row in hospitals.values():
        ZoneInfo(row["local_timezone"])
    on = read_csv(directory / "physicians_on_shift.csv", headers("physicians_on_shift"))
    extended = bool(manifest and manifest["mode"] == "splitshift")
    off = read_csv(directory / "physicians_off_shift_roster.csv", headers("physicians_off_shift_roster", extended=extended))
    physicians = unique([*on, *off], "physician_id")
    creds = unique(read_csv(directory / "credentialing_matrix.csv", headers("credentialing_matrix", hospitals)), "physician_id")
    if creds.keys() != physicians.keys() or not hospitals or not physicians:
        raise ValueError("credentials must cover exactly the nonempty physician roster")
    for row in creds.values():
        if any(row[hid] not in {"Y", ""} for hid in hospitals):
            raise ValueError("credential cells must be Y/blank")
    event_rows = read_csv(directory / "event_stream.csv", headers("event_stream"))
    live_path = directory / "live_test_events.csv"
    append = read_csv(live_path, headers("event_stream")) if live_path.exists() else []
    allowed_duplicates = set(manifest["intentional_duplicate_event_ids"]) if manifest else None
    seen, duplicates = {}, set()
    for batch in (event_rows, append):
        previous = None
        for row in batch:
            at, delivered = instant(row["event_time"]), instant(row["ingested_at"])
            if delivered < at:
                raise ValueError(f"delivery before event: {row['event_id']}")
            if previous is not None and delivered < previous:
                raise ValueError("events must be sorted by ingested_at")
            previous = delivered
            eid = row["event_id"]
            if not eid:
                raise ValueError("event ID must not be empty")
            if eid in seen:
                if any(row[k] != seen[eid][k] for k in row if k != "ingested_at"):
                    raise ValueError(f"conflicting duplicate: {eid}")
                if allowed_duplicates is not None and eid not in allowed_duplicates:
                    raise ValueError(f"unlisted duplicate: {eid}")
                duplicates.add(eid)
            else:
                seen[eid] = row
            if row["event_type"] not in DESCRIPTIONS:
                raise ValueError(f"unknown event type: {row['event_type']}")
            if row["physician_id"] and row["physician_id"] not in physicians:
                raise ValueError(f"unknown physician: {row['physician_id']}")
            if row["hospital_id"] and row["hospital_id"] not in hospitals:
                raise ValueError(f"unknown hospital: {row['hospital_id']}")
    if allowed_duplicates is not None and duplicates != allowed_duplicates:
        raise ValueError("manifest duplicate list differs from rows")
    consults, sessions = {}, set()
    for row in sorted(seen.values(), key=lambda r: (instant(r["event_time"]), instant(r["ingested_at"]), r["event_id"])):
        cid, kind = row["consult_id"], row["event_type"]
        if not cid:
            if kind not in {"camera_active", "camera_inactive", "agent_heartbeat_lost", "physician_status_changed", "shift_started"}:
                raise ValueError("consult event requires consult ID")
            continue
        if kind == "consult_received":
            consults.setdefault(cid, "Received")
        if cid not in consults:
            raise ValueError(f"event before consult receipt: {row['event_id']}")
        if kind in {"incoming_call_started", "outgoing_call_started", "video_started", "incoming_call_ended", "outgoing_call_ended", "video_ended"}:
            session = (cid, row["physician_id"], kind.rsplit("_", 1)[0])
            if not row["physician_id"]:
                raise ValueError("call/video event requires physician ID")
            if kind.endswith("_started"):
                if session in sessions:
                    raise ValueError("session starts twice")
                sessions.add(session)
            else:
                if session not in sessions:
                    raise ValueError(f"session end has no matching physician/start: {row['event_id']}")
                sessions.remove(session)
        stage = TRANSITIONS.get(kind)
        if kind in {"incoming_call_started", "outgoing_call_started"} and consults[cid] == "Assigned":
            stage = "Provider Contacted"
        if kind == "incoming_call_ended" and "phone-only" in row["description"]:
            stage = "Note Pending"
        if stage and STAGES.index(stage) < STAGES.index(consults[cid]):
            if kind not in {"consult_received", "physician_assigned", "incoming_call_started", "outgoing_call_started", "incoming_call_ended", "outgoing_call_ended", "video_started", "video_ended"}:
                raise ValueError(f"backward lifecycle stage: {row['event_id']}")
        elif stage:
            consults[cid] = stage
        if kind == "physician_assigned" and creds[row["physician_id"]][row["hospital_id"]] != "Y":
            raise ValueError(f"assignment violates credentials: {row['event_id']}")
    service_date = date.fromisoformat(manifest["service_date"]) if manifest else max(instant(r["event_time"]) for r in event_rows).astimezone(ET).date()
    for row in on:
        start, end = time.fromisoformat(row["shift_start_et"]), time.fromisoformat(row["shift_end_et"])
        if start == end or start.tzinfo or end.tzinfo:
            raise ValueError("invalid time-only shift interval")
        for day, clock in ((service_date, start), (service_date + timedelta(days=end < start), end)):
            naive = datetime.combine(day, clock)
            choices = {naive.replace(tzinfo=ET, fold=f).astimezone(UTC) for f in (0, 1)
                       if naive.replace(tzinfo=ET, fold=f).astimezone(UTC).astimezone(ET).replace(tzinfo=None) == naive}
            if len(choices) != 1:
                raise ValueError("ambiguous/nonexistent shift endpoint")
    for row in off:
        for key in ("last_shift_end", "next_shift_start", *(["next_shift_end"] if extended else [])):
            if row[key]:
                instant(row[key])
        if row["split_shift_opt_in"] not in {"Yes", "No"}:
            raise ValueError("opt-in must be Yes/No")
        if extended and instant(row["next_shift_end"]) <= instant(row["next_shift_start"]):
            raise ValueError("next shift must have a positive interval")
        if any(float(row[key]) < 0 for key in ("hours_worked_last_7d", "est_minutes_to_online", "offers_declined_last_30d")):
            raise ValueError("negative roster number")
    baseline = read_csv(directory / "baseline_hourly_volume.csv", headers("baseline_hourly_volume"))
    baseline_keys = set()
    for row in baseline:
        key = (row["hospital_id"], row["dow_type"], row["hour_start_et"])
        if key in baseline_keys or row["hospital_id"] not in hospitals or row["dow_type"] not in {"weekday", "weekend"}:
            raise ValueError("invalid/duplicate baseline hour")
        baseline_keys.add(key)
        if time.fromisoformat(row["hour_start_et"]).minute or min(float(row["mean_consults"]), float(row["p90_consults"])) < 0:
            raise ValueError("invalid baseline clock or demand")
    if any(sum(h == hid and d == "weekday" for h, d, _ in baseline_keys) != 24 for hid in hospitals):
        raise ValueError("weekday baseline must cover 24 hours")
    blocks = read_csv(directory / "coverage_requirements.csv", headers("coverage_requirements"))
    minutes = {hid: set() for hid in hospitals}
    for row in blocks:
        hid = row["hospital_id"]
        if hid not in minutes or int(row["min_available_credentialed_physicians"]) < 0:
            raise ValueError("invalid coverage hospital or requirement")
        start, end = (time.fromisoformat(v) for v in row["time_block_et"].split("-"))
        s, e = start.hour * 60 + start.minute, end.hour * 60 + end.minute
        if s == e:
            raise ValueError("empty coverage block")
        covered = set(range(s, e)) if s < e else {*range(s, 1440), *range(e)}
        if minutes[hid] & covered:
            raise ValueError(f"overlapping coverage blocks: {hid}")
        minutes[hid].update(covered)
    if any(len(m) != 1440 for m in minutes.values()):
        raise ValueError("coverage must cover 24 hours per hospital")
    for name in ("snapshot_physicians", "snapshot_open_consults"):
        paths = list(directory.glob(name + "_*.csv"))
        if len(paths) != 1:
            raise ValueError(f"expected exactly one {name} snapshot")
        rows = read_csv(paths[0], headers(name))
        unique(rows, "physician_id" if name == "snapshot_physicians" else "consult_id")
        for row in rows:
            if row["physician_id"] not in physicians and row["physician_id"] != "Unassigned":
                raise ValueError("unknown physician in snapshot")
            if name == "snapshot_open_consults" and (row["hospital_id"] not in hospitals or row["consult_id"] not in consults):
                raise ValueError("unknown consult/hospital in snapshot")
    if manifest:
        history = read_csv(directory / "support/offer_history.csv", ["offer_id", "physician_id", "sent_at", "status"])
        unique(history, "offer_id")
        for row in history:
            if row["physician_id"] not in physicians:
                raise ValueError("unknown physician in offer history")
            instant(row["sent_at"])
        for scenario in manifest["scenarios"]:
            if not set(scenario["consult_ids"]) <= consults.keys():
                raise ValueError("unknown consult in scenario manifest")
        for filename, digest in manifest["sha256"].items():
            relative = Path(filename)
            if relative.is_absolute() or ".." in relative.parts or hashlib.sha256((directory / relative).read_bytes()).hexdigest() != digest:
                raise ValueError(f"manifest hash differs: {filename}")
        if not set(manifest["late_event_ids"]) <= seen.keys():
            raise ValueError("unknown late event in manifest")
    return {"events": len(event_rows), "unique_events": len(seen), "consults": len(consults), "hospitals": len(hospitals),
        "physicians": len(physicians), "duplicates": len(duplicates), "append_events": len(append)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    try:
        print(json.dumps(validate(args.directory), sort_keys=True))
    except (ValueError, OSError, KeyError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
