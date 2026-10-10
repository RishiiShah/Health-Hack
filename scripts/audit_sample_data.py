"""Read-only fixture audit; not a backend implementation or latency benchmark.

Run: python3 scripts/audit_sample_data.py --data-dir data
"""

import argparse
import csv
import json
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo


def load(path):
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def timestamp(value):
    result = datetime.fromisoformat(value)
    if result.utcoffset() is None:
        raise ValueError(f"Timestamp has no offset: {value}")
    return result.astimezone(timezone.utc)


def audit(data_dir):
    files = {path.stem: load(path) for path in sorted(data_dir.glob("*.csv"))}
    rows = files["event_stream"]
    newest = max(timestamp(r["event_time"]) for r in rows)
    # Snapshot files specify 18:20 ET; date comes from the supplied event stream.
    now = newest.astimezone(ZoneInfo("America/New_York")).replace(
        hour=18, minute=20, second=0, microsecond=0
    ).astimezone(timezone.utc)
    seen, unique, duplicates, late, delayed = {}, [], [], [], []
    high = None
    for r in rows:
        if r["event_id"] in seen:
            original = seen[r["event_id"]]
            duplicates.append({
                "event_id": r["event_id"],
                "semantic_conflict": any(
                    r[key] != original[key] for key in r if key != "ingested_at"
                ),
            })
            continue
        seen[r["event_id"]] = r
        unique.append(r)
        t = timestamp(r["event_time"])
        delivery_lag = (timestamp(r["ingested_at"]) - t).total_seconds()
        if high is not None and t < high:
            late.append({"event_id": r["event_id"], "reorder_lag_s": (high-t).total_seconds()})
        if delivery_lag > 60:
            delayed.append({"event_id": r["event_id"], "delivery_lag_s": delivery_lag})
        high = max(high, t) if high else t

    ordered = sorted(unique, key=lambda r: (
        timestamp(r["event_time"]), timestamp(r["ingested_at"]), r["event_id"]
    ))
    stage_events = {
        "consult_received": "Received", "consult_triaged": "Triaged",
        "physician_assigned": "Assigned",
        "imaging_requested": "CT/CTA or Imaging Pending",
        "imaging_returned": "Imaging Review",
        "video_started": "Video Consult In Progress", "video_ended": "Note Pending",
        "note_started": "Documentation", "note_signed": "Signed Off",
    }
    stage_order = ["Received", "Triaged", "Assigned", "Provider Contacted",
                   "CT/CTA or Imaging Pending", "Imaging Review",
                   "Video Consult In Progress", "Note Pending", "Documentation", "Signed Off"]
    consults, missing_receipts, backward = {}, [], []
    for r in ordered:
        t = timestamp(r["event_time"])
        if t > now or not r["consult_id"]:
            continue
        cid, kind = r["consult_id"], r["event_type"]
        if kind == "consult_received":
            description = r["description"]
            consult_type = {"Stroke consult request received": "Stroke",
                            "General Neuro consult request received": "General Neuro"}[description]
            if cid in consults:
                raise ValueError(f"Multiple receipt IDs for consult: {cid}")
            consults[cid] = {"hospital_id": r["hospital_id"], "physician_id": "Unassigned",
                             "consult_type": consult_type, "received": t,
                             "current_stage": "Received", "entered": t}
        if cid not in consults:
            missing_receipts.append(r["event_id"])
            continue
        c = consults[cid]
        if kind == "physician_assigned":
            c["physician_id"] = r["physician_id"]
        stage = stage_events.get(kind)
        if kind in {"incoming_call_started", "outgoing_call_started"} and c["current_stage"] == "Assigned":
            stage = "Provider Contacted"
        if kind in {"incoming_call_ended", "outgoing_call_ended"} and r["description"] == "Call ends; phone-only consult (outside treatment window)":
            stage = "Note Pending"
        if stage and stage != c["current_stage"]:
            if stage_order.index(stage) < stage_order.index(c["current_stage"]):
                backward.append(r["event_id"])
            else:
                c["current_stage"], c["entered"] = stage, t

    open_consults = {cid: c for cid, c in consults.items() if c["current_stage"] != "Signed Off"}
    expected = {r["consult_id"]: r for r in files["snapshot_open_consults_1820"]}
    differences = []
    if set(open_consults) != set(expected):
        differences.append({"open_ids_missing": sorted(set(expected)-set(open_consults)),
                            "open_ids_extra": sorted(set(open_consults)-set(expected))})
    for cid in sorted(set(open_consults) & set(expected)):
        c, target = open_consults[cid], expected[cid]
        actual = {key: c[key] for key in ("hospital_id", "physician_id", "consult_type", "current_stage")}
        actual.update(stage_entered_at=c["entered"].astimezone(ZoneInfo("America/New_York")).strftime("%H:%M:%S"),
                      minutes_in_stage=str(int((now-c["entered"]).total_seconds()//60)),
                      minutes_since_received=str(int((now-c["received"]).total_seconds()//60)))
        for key, value in actual.items():
            if value != target[key]:
                differences.append({"consult_id": cid, "field": key, "actual": value, "expected": target[key]})

    physician_counts = []
    for p in files["snapshot_physicians_1820"]:
        pid = p["physician_id"]
        events = [r for r in ordered if r["physician_id"] == pid and timestamp(r["event_time"]) <= now]
        shift_starts = [timestamp(r["event_time"]) for r in events if r["event_type"] == "shift_started"]
        start = max(shift_starts)
        events = [r for r in events if timestamp(r["event_time"]) >= start]
        counts = {"consults_this_shift": sum(r["event_type"] == "physician_assigned" for r in events),
                  "calls_this_shift": sum(r["event_type"] in {"incoming_call_started", "outgoing_call_started"} for r in events),
                  "open_consults": sum(c["physician_id"] == pid for c in open_consults.values())}
        physician_counts.append({"physician_id": pid, **counts,
                                 "matches_snapshot": all(v == int(p[k]) for k, v in counts.items())})

    demand = []
    for h in files["hospitals"]:
        hid = h["hospital_id"]
        count = sum(r["event_type"] == "consult_received" and r["hospital_id"] == hid
                    and now-timedelta(hours=1) < timestamp(r["event_time"]) <= now for r in ordered)
        hour_et = now.astimezone(ZoneInfo("America/New_York")).strftime("%H:00")
        base = next(r for r in files["baseline_hourly_volume"] if r["hospital_id"] == hid and r["hour_start_et"] == hour_et and r["dow_type"] == "weekday")
        demand.append({"hospital_id": hid, "trailing_60m": count, "p90_et": float(base["p90_consults"]),
                       "spike": count > float(base["p90_consults"])})

    credentials = {r["physician_id"]: r for r in files["credentialing_matrix"]}
    hospitals = {r["hospital_id"] for r in files["hospitals"]}
    unknown = [r["event_id"] for r in unique if
               (r["physician_id"] and r["physician_id"] not in credentials) or
               (r["hospital_id"] and r["hospital_id"] not in hospitals)]
    violations = [r["event_id"] for r in unique if r["event_type"] == "physician_assigned"
                  and r["physician_id"] in credentials and r["hospital_id"] in hospitals
                  and credentials[r["physician_id"]][r["hospital_id"]] != "Y"]
    return {"as_of_utc": now.isoformat(), "rows_by_file": {k: len(v) for k, v in files.items()},
            "unique_events": len(unique), "duplicates": duplicates,
            "event_time_offsets": dict(Counter(str(datetime.fromisoformat(r["event_time"]).utcoffset()) for r in rows)),
            "ingest_order_inversions": sum(timestamp(b["ingested_at"]) < timestamp(a["ingested_at"]) for a, b in zip(rows, rows[1:])),
            "reordered_events": len(late), "late_over_60s": [r for r in late if r["reorder_lag_s"] > 60],
            "delivery_lag_over_60s": delayed, "unknown_reference_events": unknown,
            "events_before_receipt": missing_receipts, "backward_stage_events": backward,
            "assignment_credential_conflicts": violations,
            "received_consults": len(consults), "open_consults": len(open_consults),
            "closed_consults": len(consults)-len(open_consults),
            "consult_snapshot_differences": differences, "physician_counts": physician_counts,
            "demand_at_snapshot": demand,
            "missing_live_fixture": not (data_dir / "live_test_events.csv").exists(),
            "limitations": "Checks consult stages, ownership, timestamps and counts. Does not validate derived physician signals, coverage, queue scoring or backend performance."}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=Path(__file__).resolve().parents[1] / "data")
    args = parser.parse_args()
    print(json.dumps(audit(args.data_dir), indent=2))
