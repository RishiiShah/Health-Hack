"""G12 surge and G13 coverage projection as exact piecewise-constant intervals. Pure; `now` is injected."""
from dataclasses import dataclass
from datetime import datetime, timedelta
from app.clock import utc
from app.engine.physician import PhysicianView
from app.engine.replay import State
from app.ops.refs import ET, OpsRefs
from app.references import Refs

WINDOW = timedelta(minutes=60)
HORIZON = timedelta(minutes=90)  # Required look-ahead [B p8 #4]
MAX_OUTLOOK = timedelta(hours=6)
LATE_START_GRACE = timedelta(minutes=5)  # [A38]
START_MATCH = timedelta(minutes=30)  # a shift_started this close to the scheduled start confirms it


@dataclass(frozen=True)
class Surge:
    hospital_id: str
    count: int
    p90: float
    until: datetime  # when already-received consults stop keeping the count above p90


@dataclass(frozen=True)
class Gap:
    hospital_id: str
    start: datetime
    end: datetime
    kind: str  # hard | at_risk | unknown
    required: int | None
    confirmed: int
    scheduled: int
    surge: bool
    in_horizon: bool
    causes: tuple[str, ...]

    @property
    def id(self):
        return f"gap:{self.hospital_id}:{self.start.isoformat()}"


@dataclass(frozen=True)
class Supply:
    physician_id: str
    start: datetime
    end: datetime | None  # None: end unknown, counts through the outlook
    confirmed: bool
    hospitals: frozenset[str]
    label: str


def _received(state: State, hospital_id: str, now: datetime):
    return sorted(c.received_at for c in state.consults.values() if c.hospital_id == hospital_id and c.received_at <= now)


def trailing_count(received, at):
    return sum(at - WINDOW < r <= at for r in received)


def surge_at(ops: OpsRefs, hospital_id: str, received, at) -> bool | None:
    p90 = ops.p90(hospital_id, at)
    return None if p90 is None else trailing_count(received, at) > p90


def surges(state: State, refs: Refs, ops: OpsRefs, now: datetime) -> list[Surge]:
    now = utc(now)
    out = []
    for hid in sorted(refs.hospitals):
        received = _received(state, hid, now)
        if not surge_at(ops, hid, received, now):
            continue
        # Observed-only projection: the surge ends when enough consults age out of the window.
        until = next((r + WINDOW for r in received if r + WINDOW > now and not surge_at(ops, hid, received, r + WINDOW)), now + WINDOW)
        out.append(Surge(hid, trailing_count(received, now), ops.p90(hid, now), until))
    return out


@dataclass(frozen=True)
class CurrentCoverage:
    hospital_id: str
    trailing_60m: int
    p90: float | None
    surge: bool | None
    base_requirement: int | None
    required: int | None
    available: tuple[str, ...]  # on shift, credentialed, free by signals [B p3]
    routable: tuple[str, ...]  # also not ringing and out of call cooldown

    @property
    def gap(self):
        return None if self.required is None else max(0, self.required - len(self.available))


SIGNAL_BUSY = {"Video Consult", "Hospital Call", "Temporarily Unavailable", "Camera Active, No Session"}


def current_coverage(state: State, refs: Refs, ops: OpsRefs, views: dict[str, PhysicianView], now: datetime) -> list[CurrentCoverage]:
    now = utc(now)
    out = []
    for hid in sorted(refs.hospitals):
        received = _received(state, hid, now)
        surge = surge_at(ops, hid, received, now)
        base = ops.requirement(hid, now)
        here = [v for pid, v in sorted(views.items()) if hid in v.credentialed_hospitals and "off_shift" not in v.exclusion_reasons]
        out.append(CurrentCoverage(hid, trailing_count(received, now), ops.p90(hid, now), surge, base,
                                   None if base is None or surge is None else base + surge,
                                   tuple(v.physician_id for v in here if v.derived_state not in SIGNAL_BUSY),
                                   tuple(v.physician_id for v in here if v.routable)))
    return out


def supply(state: State, refs: Refs, ops: OpsRefs, views: dict[str, PhysicianView], now: datetime, accepted=()) -> list[Supply]:
    """Who can count toward coverage from when. `accepted` = [(physician_id, start, end, hospitals)] split shifts."""
    out = []
    for pid, physician in sorted(refs.physicians.items()):
        # Schedule ceiling: status (incl. Temporarily Unavailable) is current-coverage signal, not schedule [A37].
        p = state.physicians.get(pid)
        def started(at):
            return p is not None and any(abs(s - at) <= START_MATCH for s in p.shift_starts)
        for shift in physician.shifts:
            if shift.end <= now or shift.start > now + MAX_OUTLOOK:
                continue
            if shift.start <= now and (started(shift.start) or pid not in ops.roster):
                out.append(Supply(pid, shift.start, shift.end, True, refs.credentials[pid], f"{pid} on shift"))
            elif not started(shift.start) and now >= shift.start + LATE_START_GRACE:
                continue  # late starter no longer counts; the gap turns hard [A38]
            else:
                out.append(Supply(pid, shift.start, shift.end, started(shift.start), refs.credentials[pid],
                                  f"{pid} scheduled {shift.start.astimezone(ET):%H:%M}" + ("" if started(shift.start) else " (not yet online)")))
    for pid, entry in sorted(ops.roster.items()):
        start = entry.next_shift_start
        if start is None or start > now + MAX_OUTLOOK or any(s.start == start for s in refs.physicians[pid].shifts):
            continue
        p = state.physicians.get(pid)
        started = p is not None and any(abs(s - start) <= START_MATCH for s in p.shift_starts)
        if not started and now >= start + LATE_START_GRACE:
            continue
        out.append(Supply(pid, start, entry.next_shift_end, started, refs.credentials[pid], f"{pid} scheduled {start.astimezone(ET):%H:%M}" + ("" if started else " (not yet online)")))
    for pid, start, end, hospitals in accepted:
        out.append(Supply(pid, start, end, True, frozenset(hospitals), f"{pid} split shift"))
    return out


def outlook_end(refs: Refs, now: datetime) -> datetime:
    ends = [s.end for p in refs.physicians.values() for s in p.shifts if now < s.end <= now + MAX_OUTLOOK]
    return max([now + HORIZON, *ends])


def _change_points(state, refs, ops, items, now, end):
    points = {now, now + HORIZON, end}
    for s in items:
        points.update(t for t in (s.start, s.end) if t and now < t < end)
    hour = now.astimezone(ET).replace(minute=0, second=0, microsecond=0)
    while hour < end:
        hour += timedelta(hours=1)  # p90 hour and coverage-block boundaries (blocks start on the hour or half hour)
        points.update(t for t in (hour - timedelta(minutes=30), hour) if now < t < end)
    for c in state.consults.values():
        if now - WINDOW < c.received_at <= now:
            points.add(c.received_at + WINDOW)
    return sorted(p for p in points if now <= p <= end)


def project(state: State, refs: Refs, ops: OpsRefs, views: dict[str, PhysicianView], now: datetime, accepted=()) -> list[Gap]:
    now = utc(now)
    end = outlook_end(refs, now)
    items = supply(state, refs, ops, views, now, accepted)
    points = _change_points(state, refs, ops, items, now, end)
    gaps = []
    for hid in sorted(refs.hospitals):
        received = _received(state, hid, now)
        segments = []
        for a, b in zip(points, points[1:]):
            here = [s for s in items if hid in s.hospitals and s.start <= a and (s.end is None or a < s.end)]
            confirmed = sum(s.confirmed for s in here)
            scheduled = len(here) - confirmed
            base = ops.requirement(hid, a)
            surge = surge_at(ops, hid, received, a)
            if base is None or surge is None:
                kind, required = "unknown", None
            else:
                required = base + surge
                kind = None if confirmed >= required else "at_risk" if confirmed + scheduled >= required else "hard"
            if kind:
                segments.append((a, b, kind, required, confirmed, scheduled, bool(surge), here))
        for seg in segments:
            a, b, kind, required, confirmed, scheduled, surge, here = seg
            last = gaps[-1] if gaps else None
            if last and last.hospital_id == hid and last.kind == kind and last.end == a and last.required == required:
                gaps[-1] = Gap(hid, last.start, b, kind, required, min(last.confirmed, confirmed), min(last.scheduled, scheduled), last.surge or surge, last.in_horizon, last.causes)
                continue
            gaps.append(Gap(hid, a, b, kind, required, confirmed, scheduled, surge, a < now + HORIZON, _causes(refs, ops, views, hid, a, surge, received, here, now)))
    return gaps


def _causes(refs, ops, views, hid, at, surge, received, here, now):
    causes = [f"{pid} shift ends {s.end.astimezone(ET):%H:%M}" for pid, p in sorted(refs.physicians.items()) for s in p.shifts
              if hid in refs.credentials[pid] and now < s.end <= at]
    causes += [f"{pid} temporarily unavailable" for pid, v in sorted(views.items())
               if v.derived_state == "Temporarily Unavailable" and hid in v.credentialed_hospitals and "off_shift" not in v.exclusion_reasons]
    if surge:
        causes.append(f"surge: {trailing_count(received, at)} consults in 60 min vs p90 {ops.p90(hid, at):g} (+1 required)")
    causes += [f"relies on {s.label}" for s in here if not s.confirmed]
    return tuple(causes)


UNASSIGNED = {"Received", "Triaged"}


def joiners_now(accepted, hospital_id: str, now: datetime) -> int:
    """Accepted split shifts at this hospital that start within the horizon: they are the fix for a current gap."""
    return sum(1 for _, start, end, hospitals in accepted if hospital_id in hospitals and start < now + HORIZON and now < end)


def remaining_need(state: State, refs: Refs, ops: OpsRefs, views: dict[str, PhysicianView], now: datetime, accepted,
                   hospitals, start: datetime, end: datetime) -> dict[str, int]:
    """Physicians still missing per hospital during [start, end), accepted joiners counted. The forecast's hard
    shortfall, or with consults waiting now the current shortfall. 0 everywhere means the gap is filled."""
    now = utc(now)
    gaps = project(state, refs, ops, views, now, accepted)
    current = {c.hospital_id: c for c in current_coverage(state, refs, ops, views, now)}
    waiting = {c.hospital_id for c in state.consults.values() if c.stage in UNASSIGNED and c.owner == "Unassigned"}
    out = {}
    for h in hospitals:
        short = max((g.required - g.confirmed - g.scheduled for g in gaps
                     if g.hospital_id == h and g.kind == "hard" and g.start < end and start < g.end), default=0)
        c = current.get(h)
        if c is not None and c.gap and h in waiting and start < now + HORIZON:
            short = max(short, c.required - len(c.available) - joiners_now(accepted, h, now))
        out[h] = max(0, short)
    return out
