from datetime import datetime, timezone, timedelta
from typing import Protocol
from time import monotonic


def utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamp must include a UTC offset")
    return value.astimezone(timezone.utc)


class Clock(Protocol):
    mode: str
    def now(self) -> datetime: ...


class WallClock:
    mode = "wall"
    def now(self) -> datetime:
        return datetime.now(timezone.utc)


class ServerReceiptClock:
    """Independent wall clock for receipt/hold deadlines, never simulation time."""
    def now(self) -> datetime:
        return datetime.now(timezone.utc)


class FixedClock:
    mode = "fixed"
    def __init__(self, value: datetime): self.value = utc(value)
    def now(self) -> datetime: return self.value


class AnchoredClock:
    mode = "anchored"
    def __init__(self, anchor: datetime): self.anchor, self.started = utc(anchor), monotonic()
    def now(self) -> datetime: return self.anchor + timedelta(seconds=monotonic() - self.started)


def make_clock(mode: str, fixed: datetime | None = None, newest_event_time: datetime | None = None) -> Clock:
    if mode == "fixed":
        if fixed is None: raise ValueError("fixed clock requires a timestamp")
        return FixedClock(fixed)
    if mode == "anchored": return AnchoredClock(fixed or newest_event_time or WallClock().now())
    if mode == "wall": return WallClock()
    if mode != "auto": raise ValueError(f"unknown clock mode: {mode}")
    wall = WallClock().now()
    if newest_event_time and abs((wall - utc(newest_event_time)).total_seconds()) > 900:
        return AnchoredClock(newest_event_time)
    return WallClock()
