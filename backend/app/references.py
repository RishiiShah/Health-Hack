"""P2 references: explicit CSV normalization, immutable IDs, shifts and credentials."""
import csv
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from pathlib import Path
from types import MappingProxyType
from typing import Mapping
from zoneinfo import ZoneInfo
from app.clock import utc


@dataclass(frozen=True)
class Shift:
    start: datetime
    end: datetime

    def __post_init__(self):
        object.__setattr__(self, "start", utc(self.start))
        object.__setattr__(self, "end", utc(self.end))
        if self.end <= self.start:
            raise ValueError("shift end must follow start")


@dataclass(frozen=True)
class Physician:
    name: str
    shifts: tuple[Shift, ...] = ()


@dataclass(frozen=True)
class Hospital:
    name: str
    timezone: str


@dataclass(frozen=True)
class Refs:
    hospitals: Mapping[str, Hospital]
    physicians: Mapping[str, Physician]
    credentials: Mapping[str, frozenset[str]]

    def __post_init__(self):
        hospitals = dict(self.hospitals)
        physicians = {pid: Physician(p.name, tuple(sorted(p.shifts, key=lambda s: s.start))) for pid, p in self.physicians.items()}
        credentials = {pid: frozenset(sites) for pid, sites in self.credentials.items()}
        if any(not key.strip() for key in (*hospitals, *physicians)):
            raise ValueError("reference IDs must not be blank")
        for hospital in hospitals.values():
            ZoneInfo(hospital.timezone)
        if set(credentials) != set(physicians):
            raise ValueError("credential matrix must cover exactly the physician roster")
        for pid, physician in physicians.items():
            if not credentials[pid] <= hospitals.keys():
                raise ValueError(f"unknown credential hospital for {pid}")
            if any(a.end > b.start for a, b in zip(physician.shifts, physician.shifts[1:])):
                raise ValueError(f"overlapping shifts for {pid}")
        object.__setattr__(self, "hospitals", MappingProxyType(hospitals))
        object.__setattr__(self, "physicians", MappingProxyType(physicians))
        object.__setattr__(self, "credentials", MappingProxyType(credentials))

    def payload(self):
        return {"hospitals": {hid: {"name": h.name, "timezone": h.timezone} for hid, h in self.hospitals.items()},
                "physicians": {pid: {"name": p.name, "shifts": [{"start": s.start.isoformat(), "end": s.end.isoformat()} for s in p.shifts]} for pid, p in self.physicians.items()},
                "credentials": {pid: sorted(sites) for pid, sites in self.credentials.items()}}

    @classmethod
    def from_payload(cls, payload):
        return cls({hid: Hospital(**h) for hid, h in payload["hospitals"].items()},
                   {pid: Physician(p["name"], tuple(Shift(datetime.fromisoformat(s["start"]), datetime.fromisoformat(s["end"])) for s in p["shifts"])) for pid, p in payload["physicians"].items()},
                   {pid: frozenset(sites) for pid, sites in payload["credentials"].items()})


def local_instant(day: date, clock: time, zone: ZoneInfo) -> datetime:
    """Time-only rows cannot choose between DST folds or invent a nonexistent time."""
    naive = datetime.combine(day, clock)
    choices = {utc(naive.replace(tzinfo=zone, fold=fold)) for fold in (0, 1)
               if utc(naive.replace(tzinfo=zone, fold=fold)).astimezone(zone).replace(tzinfo=None) == naive}
    if len(choices) != 1:
        raise ValueError(f"ambiguous/nonexistent local shift time: {naive} {zone.key}")
    return choices.pop()


def _rows(path: Path, required: set[str]):
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        headers = reader.fieldnames or []
        if len(set(headers)) != len(headers) or not required <= set(headers):
            raise ValueError(f"invalid headers: {path.name}")
        for number, row in enumerate(reader, 2):
            if None in row or any(value is None for value in row.values()):
                raise ValueError(f"invalid column count: {path.name}:{number}")
            yield row


def _insert(mapping, key, value):
    if not key.strip() or key in mapping:
        raise ValueError(f"blank/duplicate reference ID: {key!r}")
    mapping[key] = value


def load_refs(directory: str | Path, service_date: date) -> Refs:
    directory = Path(directory)
    hospitals, physicians, credentials = {}, {}, {}
    for row in _rows(directory / "hospitals.csv", {"hospital_id", "hospital_name", "local_timezone"}):
        _insert(hospitals, row["hospital_id"], Hospital(row["hospital_name"], row["local_timezone"]))
    zone = ZoneInfo("America/New_York")  # Declared by the sample's *_et columns.
    for row in _rows(directory / "physicians_on_shift.csv", {"physician_id", "name", "shift_start_et", "shift_end_et"}):
        start, end = time.fromisoformat(row["shift_start_et"]), time.fromisoformat(row["shift_end_et"])
        if start.tzinfo or end.tzinfo or start == end:
            raise ValueError("time-only shift needs distinct unambiguous local endpoints")
        end_day = service_date + timedelta(days=end < start)
        shift = Shift(local_instant(service_date, start, zone), local_instant(end_day, end, zone))
        _insert(physicians, row["physician_id"], Physician(row["name"], (shift,)))
    for row in _rows(directory / "physicians_off_shift_roster.csv", {"physician_id", "name"}):
        # A next start without an end is not a complete shift.
        _insert(physicians, row["physician_id"], Physician(row["name"]))
    for row in _rows(directory / "credentialing_matrix.csv", {"physician_id", "name", *hospitals}):
        if set(row) != {"physician_id", "name", *hospitals} or any(row[hid] not in {"Y", ""} for hid in hospitals):
            raise ValueError("credential cells must be Y/blank with known hospital columns")
        _insert(credentials, row["physician_id"], frozenset(hid for hid in hospitals if row[hid] == "Y"))
    if not hospitals or not physicians:
        raise ValueError("reference tables must not be empty")
    return Refs(hospitals, physicians, credentials)


def _aware(value):
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise ValueError(f"timestamp needs a UTC offset: {value}")
    return parsed


def load_pack_refs(directory: str | Path) -> Refs:
    """Scenario-pack format: full timestamps, `timezone`, Y/N credentials, roster next shift with an end."""
    directory = Path(directory)
    hospitals, physicians, credentials = {}, {}, {}
    for row in _rows(directory / "hospitals.csv", {"hospital_id", "hospital_name", "timezone"}):
        _insert(hospitals, row["hospital_id"], Hospital(row["hospital_name"], row["timezone"]))
    for row in _rows(directory / "physicians_on_shift.csv", {"physician_id", "physician_name", "shift_start", "shift_end"}):
        _insert(physicians, row["physician_id"], Physician(row["physician_name"], (Shift(_aware(row["shift_start"]), _aware(row["shift_end"])),)))
    for row in _rows(directory / "physicians_off_shift_roster.csv", {"physician_id", "physician_name", "next_shift_start", "next_shift_end"}):
        shifts = (Shift(_aware(row["next_shift_start"]), _aware(row["next_shift_end"])),) if row["next_shift_start"] and row["next_shift_end"] else ()
        _insert(physicians, row["physician_id"], Physician(row["physician_name"], shifts))
    for row in _rows(directory / "credentialing_matrix.csv", {"physician_id", *hospitals}):
        if set(row) != {"physician_id", *hospitals} or any(row[hid] not in {"Y", "N"} for hid in hospitals):
            raise ValueError("credential cells must be Y/N with known hospital columns")
        _insert(credentials, row["physician_id"], frozenset(hid for hid in hospitals if row[hid] == "Y"))
    if not hospitals or not physicians:
        raise ValueError("reference tables must not be empty")
    return Refs(hospitals, physicians, credentials)


def load_reference_dir(directory: str | Path, service_date: date | None = None) -> Refs:
    """Pick the loader from the hospitals.csv header; unknown layouts are rejected, never guessed."""
    with (Path(directory) / "hospitals.csv").open(newline="", encoding="utf-8-sig") as handle:
        headers = set(next(csv.reader(handle), []))
    if "local_timezone" in headers:
        if service_date is None:
            raise ValueError("the time-only sample format needs an explicit service date")
        return load_refs(directory, service_date)
    if "timezone" in headers:
        return load_pack_refs(directory)
    raise ValueError("unrecognized reference layout")
