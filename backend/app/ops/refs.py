"""Decision-engine references: baseline volume, coverage blocks and off-shift roster details.

Two explicit layouts, chosen by header: the sample (`*_et` columns, ET hours) and scenario packs
(`*_local` columns, hospital-local hours, weekday index 0 = Monday). Unknown layouts are rejected.
"""
from dataclasses import dataclass
from datetime import datetime, time
from pathlib import Path
from types import MappingProxyType
from typing import Mapping
from zoneinfo import ZoneInfo
from app.clock import utc
from app.references import _insert, _rows

ET = ZoneInfo("America/New_York")
DAY_MINUTES = 24 * 60
DOW_TYPES = {"weekday": range(0, 5), "weekend": range(5, 7)}


@dataclass(frozen=True)
class RosterEntry:
    role: str
    opt_in: bool
    last_shift_end: datetime | None
    next_shift_start: datetime | None
    hours_last_7d: float
    minutes_to_online: int
    channel: str
    declines_30d: int
    next_shift_end: datetime | None = None


@dataclass(frozen=True)
class OpsRefs:
    baseline: Mapping[tuple[str, int, int], tuple[float, float]]  # (hospital, weekday 0=Mon, hour) -> (mean, p90)
    coverage: Mapping[str, tuple[tuple[int, int, int], ...]]  # hospital -> (start, end, required) minutes; end <= start wraps
    roster: Mapping[str, RosterEntry]
    zones: Mapping[str, str] = MappingProxyType({})  # zone the hours of each hospital are expressed in; default ET

    def payload(self) -> dict:
        """JSON form kept in the database beside the reference tables."""
        when = lambda t: t.isoformat() if t else None
        return {"baseline": sorted([h, day, hour, mean, p90] for (h, day, hour), (mean, p90) in self.baseline.items()),
                "coverage": {h: [list(b) for b in blocks] for h, blocks in sorted(self.coverage.items())},
                "roster": {pid: {"role": r.role, "opt_in": r.opt_in, "last_shift_end": when(r.last_shift_end), "next_shift_start": when(r.next_shift_start),
                                 "next_shift_end": when(r.next_shift_end), "hours_last_7d": r.hours_last_7d, "minutes_to_online": r.minutes_to_online,
                                 "channel": r.channel, "declines_30d": r.declines_30d} for pid, r in sorted(self.roster.items())},
                "zones": dict(sorted(self.zones.items()))}

    @classmethod
    def from_payload(cls, payload: dict) -> "OpsRefs":
        when = lambda t: datetime.fromisoformat(t) if t else None
        times = ("last_shift_end", "next_shift_start", "next_shift_end")
        return cls(MappingProxyType({(h, day, hour): (mean, p90) for h, day, hour, mean, p90 in payload["baseline"]}),
                   MappingProxyType({h: tuple(tuple(b) for b in blocks) for h, blocks in payload["coverage"].items()}),
                   MappingProxyType({pid: RosterEntry(**{**r, **{k: when(r[k]) for k in times}}) for pid, r in payload["roster"].items()}),
                   MappingProxyType(dict(payload["zones"])))

    def local(self, hospital_id: str, at: datetime) -> datetime:
        return utc(at).astimezone(ZoneInfo(self.zones[hospital_id]) if hospital_id in self.zones else ET)

    def _baseline(self, hospital_id, at):
        local = self.local(hospital_id, at)
        return self.baseline.get((hospital_id, local.weekday(), local.hour))

    def mean(self, hospital_id: str, at: datetime) -> float | None:
        row = self._baseline(hospital_id, at)
        return row and row[0]

    def p90(self, hospital_id: str, at: datetime) -> float | None:
        row = self._baseline(hospital_id, at)
        return row and row[1]

    def requirement(self, hospital_id: str, at: datetime) -> int | None:
        """Missing blocks are unknown (None), never zero."""
        local = self.local(hospital_id, at)
        minute = local.hour * 60 + local.minute
        return next((required for start, end, required in self.coverage.get(hospital_id, ())
                     if minute in _span(start, end)), None)


def _span(start, end):
    return range(start, end) if start < end else [*range(start, DAY_MINUTES), *range(0, end)]


def _clock_minutes(value):
    t = time.fromisoformat(value)
    return t.hour * 60 + t.minute


def _hour_minutes(value):
    hour = int(value)
    if not 0 <= hour <= 24:
        raise ValueError(f"hour out of range: {value}")
    return hour * 60


def _number(value, kind, label):
    number = kind(value)
    if number < 0:
        raise ValueError(f"negative {label}: {value}")
    return number


def _instant(value):
    if not value:
        return None
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise ValueError(f"roster timestamp needs a UTC offset: {value}")
    return utc(parsed)


def _flag(value, yes, no):
    if value not in {yes, no}:
        raise ValueError(f"opt-in must be {yes}/{no}: {value}")
    return value == yes


def _headers(path):
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return set(handle.readline().strip().split(","))


def load_ops_refs(directory: str | Path, hospital_zones: Mapping[str, str], physicians: set[str]) -> OpsRefs:
    """`hospital_zones`: hospital id -> IANA zone from hospitals.csv (used for local-hour layouts)."""
    directory = Path(directory)
    baseline, coverage, roster = {}, {}, {}
    pack = "hour_local" in _headers(directory / "baseline_hourly_volume.csv")

    def known_hospital(hid):
        if hid not in hospital_zones:
            raise ValueError(f"unknown hospital: {hid}")
        return hid

    def add_baseline(hid, day, hour, mean, p90):
        key = (known_hospital(hid), day, hour)
        if key in baseline:
            raise ValueError(f"duplicate baseline hour: {key}")
        baseline[key] = (_number(mean, float, "mean"), _number(p90, float, "p90"))

    def add_block(hid, start, end, required, label):
        if start == end:
            raise ValueError(f"empty coverage block: {label}")
        blocks = coverage.setdefault(known_hospital(hid), [])
        if any(set(_span(start, end)) & set(_span(s, e)) for s, e, _ in blocks):
            raise ValueError(f"coverage blocks overlap: {hid} {label}")
        blocks.append((start, end % DAY_MINUTES, _number(required, int, "requirement")))

    if pack:
        for row in _rows(directory / "baseline_hourly_volume.csv", {"hospital_id", "weekday", "hour_local", "mean_consults", "p90_consults"}):
            add_baseline(row["hospital_id"], int(row["weekday"]), int(row["hour_local"]), row["mean_consults"], row["p90_consults"])
        for row in _rows(directory / "coverage_requirements.csv", {"hospital_id", "start_hour_local", "end_hour_local", "minimum_available"}):
            add_block(row["hospital_id"], _hour_minutes(row["start_hour_local"]), _hour_minutes(row["end_hour_local"]), row["minimum_available"],
                      f"{row['start_hour_local']}-{row['end_hour_local']}")
        for row in _rows(directory / "physicians_off_shift_roster.csv", {"physician_id", "role", "opted_in", "last_shift_ended", "next_shift_start", "next_shift_end", "hours_worked_7d", "minutes_to_online", "preferred_channel", "declined_offers_30d"}):
            if row["physician_id"] not in physicians:
                raise ValueError(f"unknown physician: {row['physician_id']}")
            _insert(roster, row["physician_id"], RosterEntry(
                row["role"], _flag(row["opted_in"], "True", "False"), _instant(row["last_shift_ended"]), _instant(row["next_shift_start"]),
                _number(row["hours_worked_7d"], float, "hours"), _number(row["minutes_to_online"], int, "minutes to online"),
                row["preferred_channel"], _number(row["declined_offers_30d"], int, "declines"), _instant(row["next_shift_end"])))
        zones = MappingProxyType(dict(hospital_zones))
    else:
        for row in _rows(directory / "baseline_hourly_volume.csv", {"hospital_id", "dow_type", "hour_start_et", "mean_consults", "p90_consults"}):
            if row["dow_type"] not in DOW_TYPES:
                raise ValueError(f"unknown dow_type: {row['dow_type']}")
            for day in DOW_TYPES[row["dow_type"]]:
                add_baseline(row["hospital_id"], day, _clock_minutes(row["hour_start_et"]) // 60, row["mean_consults"], row["p90_consults"])
        for row in _rows(directory / "coverage_requirements.csv", {"hospital_id", "time_block_et", "min_available_credentialed_physicians"}):
            start, end = map(_clock_minutes, row["time_block_et"].split("-"))
            add_block(row["hospital_id"], start, end, row["min_available_credentialed_physicians"], row["time_block_et"])
        for row in _rows(directory / "physicians_off_shift_roster.csv", {"physician_id", "role", "split_shift_opt_in", "last_shift_end", "next_shift_start", "hours_worked_last_7d", "est_minutes_to_online", "preferred_channel", "offers_declined_last_30d"}):
            if row["physician_id"] not in physicians:
                raise ValueError(f"unknown physician: {row['physician_id']}")
            _insert(roster, row["physician_id"], RosterEntry(
                row["role"], _flag(row["split_shift_opt_in"], "Yes", "No"), _instant(row["last_shift_end"]), _instant(row["next_shift_start"]),
                _number(row["hours_worked_last_7d"], float, "hours"), _number(row["est_minutes_to_online"], int, "minutes to online"),
                row["preferred_channel"], _number(row["offers_declined_last_30d"], int, "declines")))
        zones = MappingProxyType({})  # *_et columns: every hospital's hours are ET

    return OpsRefs(MappingProxyType(baseline), MappingProxyType({h: tuple(b) for h, b in coverage.items()}), MappingProxyType(roster), zones)
