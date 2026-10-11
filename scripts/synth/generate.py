"""Generate reproducible practice CSVs without reading application code or source data.

python scripts/synth/generate.py --seed 7 --date 2026-04-07 --now 18:20 --prefix T --scale 1 --out data/synthetic/practice
python scripts/synth/generate.py --suite --out data/synthetic
"""
import argparse
import csv
from datetime import date, datetime, time, timedelta, timezone
import hashlib
import json
from pathlib import Path
import random
import re
from zoneinfo import ZoneInfo

try:
    from . import scenarios
    from .schema import DESCRIPTIONS, VERSION, ZONES, headers
except ImportError:  # Direct CLI invocation from any working directory.
    import scenarios
    from schema import DESCRIPTIONS, VERSION, ZONES, headers

ET = ZoneInfo("America/New_York")
UTC = timezone.utc
PRESETS = {
    "practice-0407": ("2026-04-07", "18:20", "T", "practice"),
    "dst-1101": ("2026-11-01", "06:20", "D", "dst"),
    "live-0317": ("2026-03-17", "18:30", "L", "live"),
    "splitshift": ("2026-04-07", "18:20", "S", "splitshift"),
    "trap": ("2026-04-07", "18:20", "R", "trap"),
}


class Builder:
    def __init__(self, seed, day, clock, prefix, scale, mode):
        naive = datetime.combine(day, clock)
        choices = {naive.replace(tzinfo=ET, fold=f).astimezone(UTC) for f in (0, 1)
                   if naive.replace(tzinfo=ET, fold=f).astimezone(UTC).astimezone(ET).replace(tzinfo=None) == naive}
        if len(choices) != 1:
            raise ValueError("--now must be an unambiguous, existing Eastern time")
        self.now = choices.pop()
        self.seed, self.prefix, self.scale, self.mode = seed, prefix, scale, mode
        self.random = random.Random(seed)
        self.start = self.now - timedelta(hours=9 if mode == "dst" else 8)
        if mode == "dst":
            earlier = (self.now - timedelta(hours=6)).astimezone(ET)
            later = (self.now - timedelta(hours=5)).astimezone(ET)
            if clock != time(6, 20) or earlier.strftime("%H:%M") != later.strftime("%H:%M") or earlier.utcoffset() == later.utcoffset():
                raise ValueError("--mode dst needs the Eastern fall-back date with --now 06:20")
        self.service_date = self.start.astimezone(ET).date()
        self.ends = [self.now + timedelta(minutes=40 if i < 2 else 480) for i in range(12)]
        for endpoint in (self.start, *self.ends):
            naive_endpoint = endpoint.astimezone(ET).replace(tzinfo=None)
            choices = {naive_endpoint.replace(tzinfo=ET, fold=f).astimezone(UTC) for f in (0, 1)
                       if naive_endpoint.replace(tzinfo=ET, fold=f).astimezone(UTC).astimezone(ET).replace(tzinfo=None) == naive_endpoint}
            if len(choices) != 1:
                raise ValueError("generated time-only shift endpoint is ambiguous/nonexistent; choose another --now")
        self.events, self.consults, self.scenarios, self.duplicates, self.late = [], [], [], [], []
        self.activity, self.status, self.agent = ["Available"] * 12, ["Available"] * 12, ["Online"] * 12
        self.copy = 0
        self.hospitals = [{"hospital_id": self.hid(i), "hospital_name": f"Practice {i + 1:02d} Medical Center", "local_timezone": ZONES[i % 4], "coverage_tier": "Standard"} for i in range(12)]
        self.on_shift = [{"physician_id": self.pid(i), "name": self.name(i), "shift_start_et": self.start.astimezone(ET).strftime("%H:%M"),
            "shift_end_et": self.ends[i].astimezone(ET).strftime("%H:%M"), "split_shift_opt_in": "Yes"} for i in range(12)]
        self.off_shift, self.offer_history = [], []
        for i in range(12, 21):
            next_start = self.now + timedelta(hours=36)
            if i == 17:
                next_start = self.now + timedelta(minutes=30)
            row = {"physician_id": self.pid(i), "name": self.name(i), "role": "Day", "split_shift_opt_in": "No" if i == 13 else "Yes",
                "last_shift_end": self.stamp(-120 if i == 15 else -720), "next_shift_start": next_start.astimezone(ET).isoformat(),
                "hours_worked_last_7d": "59" if i == 16 else "20", "est_minutes_to_online": "15" if i == 18 else "0",
                "preferred_channel": "sms", "offers_declined_last_30d": "0"}
            if mode == "splitshift":
                row.update(next_shift_end=(next_start + timedelta(hours=8)).astimezone(ET).isoformat(),
                    offers_sent_last_7d="3" if i == 20 else "1" if i == 19 else "0", open_offer="Yes" if i == 19 else "No")
            self.off_shift.append(row)
        for i, count, state in ((19, 1, "sent"), (20, 3, "declined")):
            for j in range(count):
                self.offer_history.append({"offer_id": f"OFF-{prefix}-{i}-{j}", "physician_id": self.pid(i), "sent_at": self.stamp(-180 - j), "status": state})
        self.credentials = []
        for i in range(21):
            sites = {self.hid(i)} if i < 12 else {self.hid(j) for j in range(4)}
            if i == 14:
                sites = {self.hid(11)}
            self.credentials.append({"physician_id": self.pid(i), "name": self.name(i), **{self.hid(j): "Y" if self.hid(j) in sites else "" for j in range(12)}})

    def hid(self, i):
        return f"H-{self.prefix}-{i + 1:03d}"

    def pid(self, i):
        return f"PHY-{self.prefix}-{i + 1:03d}"

    def name(self, i):
        return f"Dr. Practice {i + 1:02d}"

    def stamp(self, minutes):
        return (self.now + timedelta(minutes=minutes)).astimezone(ET).isoformat()

    def event(self, kind, minute, cid="", pid="", hid="", description=None, ingested=None):
        row = dict(zip(headers("event_stream"), (f"EVT-{self.prefix}-{len(self.events) + 1:07d}", self.stamp(minute),
            self.stamp(minute if ingested is None else ingested), cid, kind, pid, hid, description or DESCRIPTIONS[kind])))
        self.events.append(row)
        if ingested is not None and ingested != minute:
            self.late.append(row["event_id"])
        return row

    def signal(self, physician, kind, minute, description=None):
        self.event(kind, minute, pid=self.pid(physician), description=description)

    def consult(self, hospital, physician, kind, timeline, final_stage, entered, calls=0):
        cid = f"CON-{self.prefix}-{len(self.consults) + 1:06d}"
        pid = self.pid(physician) if physician is not None else ""
        for entry in timeline:
            minute, event = entry[:2]
            description = entry[2] if len(entry) > 2 else None
            delivery = entry[3] if len(entry) > 3 else None
            if event == "consult_received":
                description = f"{kind} consult request received"
            uses_physician = event not in {"consult_received", "consult_triaged", "routing_attempt_failed", "imaging_requested", "imaging_returned"}
            self.event(event, minute, cid, pid if uses_physician else "", self.hid(hospital), description, delivery)
        self.consults.append({"id": cid, "hospital": hospital, "physician": physician, "type": kind, "stage": final_stage,
            "received": timeline[0][0], "entered": entered, "calls": calls})
        return cid

    def scenario(self, name, ids, expected, details):
        self.scenarios.append({"name": name, "copy": self.copy, "consult_ids": ids, "expected": expected, **details})

    def build(self):
        for i in range(12):
            self.event("shift_started", (self.start - self.now).total_seconds() / 60, pid=self.pid(i))
            self.signal(i, "camera_inactive", -240)
            self.signal(i, "physician_status_changed", -240)
        for copy in range(self.scale):
            self.copy = copy
            scenarios.complete_lifecycle(self)
            for scenario in scenarios.ALL:
                scenario(self)
            if self.mode == "dst":
                scenarios.dst_session(self)
        if self.mode == "trap":
            self.scenario("low_volume_trap", [], "Unguarded joiner spills to three non-gap hospitals; guarded routes remain at the offered hospital", {"physician_id": self.pid(12), "hospital_id": self.hid(0)})
        if self.mode == "live":
            self.live_append()
        # ISO offsets can differ across DST: sort by instants, never by wall-clock strings.
        self.events.sort(key=lambda r: (datetime.fromisoformat(r["ingested_at"]).astimezone(UTC), r["event_id"]))
        files = {"hospitals": self.hospitals, "physicians_on_shift": self.on_shift, "physicians_off_shift_roster": self.off_shift,
            "credentialing_matrix": self.credentials, "event_stream": self.events}
        files["baseline_hourly_volume"] = [{"hospital_id": h["hospital_id"], "hospital_name": h["hospital_name"], "dow_type": "weekday",
            "hour_start_et": f"{hour:02d}:00", "mean_consults": "8" if self.mode == "trap" and 1 <= i <= 3 else "2", "p90_consults": "10" if self.mode == "trap" and 1 <= i <= 3 else "3", "weeks_sampled": "8"}
            for i, h in enumerate(self.hospitals) for hour in range(24)]
        files["coverage_requirements"] = [{"hospital_id": h["hospital_id"], "hospital_name": h["hospital_name"],
            "time_block_et": block, "min_available_credentialed_physicians": "1"} for h in self.hospitals for block in ("00:00-12:00", "12:00-00:00")]
        files["snapshot_open_consults"] = [{"consult_id": c["id"], "hospital_id": self.hid(c["hospital"]), "hospital_name": self.hospitals[c["hospital"]]["hospital_name"],
            "physician_id": self.pid(c["physician"]) if c["physician"] is not None else "Unassigned", "consult_type": c["type"], "current_stage": c["stage"],
            "stage_entered_at": datetime.fromisoformat(self.stamp(c["entered"])).strftime("%H:%M:%S"), "minutes_in_stage": str(-c["entered"]), "minutes_since_received": str(-c["received"])}
            for c in self.consults if c["stage"] != "Signed Off"]
        files["snapshot_physicians"] = [{"physician_id": self.pid(i), "name": self.name(i),
            "shift_et": f"{self.on_shift[i]['shift_start_et']}-{self.on_shift[i]['shift_end_et']}", "self_reported_status": self.status[i], "desktop_agent": self.agent[i],
            "derived_state": self.activity[i], "consults_this_shift": str(sum(c["physician"] == i for c in self.consults)),
            "calls_this_shift": str(sum(c["calls"] for c in self.consults if c["physician"] == i)), "open_consults": str(sum(c["physician"] == i and c["stage"] != "Signed Off" for c in self.consults)),
            "minutes_to_shift_end": str(int((self.ends[i] - self.now).total_seconds() // 60))} for i in range(12)]
        return files

    def live_append(self):
        # Self-contained base plus future append, in an independent namespace.
        # This exercises T23–T27 semantics without extending supplied source files.
        before = len(self.events)
        ids = []
        for i in range(2):
            cid = f"CON-{self.prefix}-APP-{i}"
            self.event("consult_received", 1 + i, cid, hid=self.hid(0))
            self.event("consult_triaged", 1.1 + i, cid, hid=self.hid(0))
            self.event("routing_attempt_failed", 2 + i, cid, hid=self.hid(0))
            if i == 0:
                self.event("consult_received", 3, cid, hid=self.hid(0))
            ids.append(cid)
        note = next(c for c in self.consults if c["stage"] == "Video Consult In Progress")
        self.event("video_ended", 1, note["id"], self.pid(note["physician"]), self.hid(note["hospital"]), ingested=4)
        ringing = next(c for c in self.consults if c["physician"] == 7)
        self.event("incoming_call_started", 2, ringing["id"], self.pid(7), self.hid(7))
        stranded = next(c for c in self.consults if c["physician"] == 2)
        self.signal(2, "physician_status_changed", 2)
        self.event("incoming_call_started", 3, stranded["id"], self.pid(2), self.hid(2))
        self.append = self.events[before:]
        self.events = self.events[:before]
        self.scenario("live_T23_T27", ids, "Append: two distinct receipts, repeat deduplication, event-time video end, cleared ring, stranded owner resumes", {
            "append_as_of": self.stamp(10), "video_consult_id": note["id"], "ringing_consult_id": ringing["id"], "stranded_consult_id": stranded["id"], "distinct_new_consults": 2})


def generate(out, *, seed=7, day=date(2026, 4, 7), clock=time(18, 20), prefix="T", scale=1, mode="practice"):
    if scale not in (1, 10, 100):
        raise ValueError("--scale must be 1, 10 or 100")
    if not re.fullmatch(r"[A-Z][A-Z0-9]{0,15}", prefix):
        raise ValueError("--prefix must be 1–16 uppercase letters/digits, starting with a letter")
    if day == date(2026, 3, 17) and mode != "live":
        raise ValueError("Use a different practice date; March 17 is reserved for --mode live disposable append rehearsal")
    out = Path(out).resolve()
    root_data = Path(__file__).resolve().parents[2] / "data"
    if out == root_data or (root_data in out.parents and not (root_data / "synthetic" in out.parents)):
        raise ValueError("Outputs inside data/ must be under data/synthetic/; supplied files are protected")
    if out.exists() and any(out.iterdir()):
        manifest_path = out / "manifest.json"
        if not manifest_path.is_file() or json.loads(manifest_path.read_text()).get("generator_version") != VERSION:
            raise ValueError("Output directory contains files not owned by this generator")
        previous = json.loads(manifest_path.read_text())
        if previous.get("now") != clock.strftime("%H:%M") or previous.get("mode") != mode:
            raise ValueError("Use a new output directory when changing --now or --mode")
    b = Builder(seed, day, clock, prefix, scale, mode)
    files = b.build()
    out.mkdir(parents=True, exist_ok=True)
    hashes = {}
    for name, rows in files.items():
        filename = f"{name}_{clock:%H%M}.csv" if name.startswith("snapshot_") else f"{name}.csv"
        ordered = rows if name == "event_stream" else sorted(rows, key=lambda r: tuple(str(r.get(k, "")) for k in headers(name, (h['hospital_id'] for h in b.hospitals), mode == "splitshift")))
        write_csv(out / filename, headers(name, (h["hospital_id"] for h in b.hospitals), mode == "splitshift"), ordered)
        hashes[filename] = hashlib.sha256((out / filename).read_bytes()).hexdigest()
    support = out / "support"
    support.mkdir(exist_ok=True)
    write_csv(support / "offer_history.csv", ["offer_id", "physician_id", "sent_at", "status"], b.offer_history)
    hashes["support/offer_history.csv"] = hashlib.sha256((support / "offer_history.csv").read_bytes()).hexdigest()
    if mode == "live":
        write_csv(out / "live_test_events.csv", headers("event_stream"), sorted(b.append, key=lambda r: (r["ingested_at"], r["event_id"])))
        hashes["live_test_events.csv"] = hashlib.sha256((out / "live_test_events.csv").read_bytes()).hexdigest()
    manifest = {"generator_version": VERSION, "seed": seed, "date": str(day), "service_date": str(b.service_date), "now": clock.strftime("%H:%M"),
        "as_of": b.now.astimezone(ET).isoformat(), "prefix": prefix, "scale": scale, "mode": mode, "scenarios": b.scenarios,
        "intentional_duplicate_event_ids": b.duplicates, "late_event_ids": b.late, "sha256": hashes,
        "expected_source": "Authored scenario lifecycles and final outcomes; no application imports", "baseline_missing": "weekend"}
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


def write_csv(path, columns, rows):
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, columns, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--date", type=date.fromisoformat, default=date(2026, 4, 7))
    parser.add_argument("--now", type=time.fromisoformat, default=time(18, 20))
    parser.add_argument("--prefix", default="T")
    parser.add_argument("--scale", type=int, choices=(1, 10, 100), default=1)
    parser.add_argument("--mode", choices=("practice", "dst", "live", "splitshift", "trap"), default="practice")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--suite", action="store_true", help="Generate all five named rehearsal datasets")
    args = parser.parse_args()
    try:
        if args.now.second or args.now.microsecond or args.now.tzinfo:
            raise ValueError("--now must be HH:MM Eastern local time")
        targets = PRESETS.items() if args.suite else [(None, (str(args.date), args.now.strftime("%H:%M"), args.prefix, args.mode))]
        for name, (day, clock, prefix, mode) in targets:
            manifest = generate(args.out / name if name else args.out, seed=args.seed, day=date.fromisoformat(day), clock=time.fromisoformat(clock), prefix=prefix, scale=args.scale, mode=mode)
            print(json.dumps({"dataset": name or mode, "scenarios": len(manifest["scenarios"]), "as_of": manifest["as_of"]}))
    except (ValueError, OSError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
