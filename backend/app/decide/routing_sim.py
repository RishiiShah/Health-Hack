"""Step 7: deterministic model of the router [B p3] to check that a split shift relieves its gap without the trap. Pure.

We model the production router, we never replace it [B p8]. No randomness: demand is placed where the expected
count crosses each half-integer, and every tie breaks on time, hospital, then id.
"""
import heapq
import statistics
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Mapping
from app.engine.physician import PhysicianView
from app.engine.replay import CALL_ENDS, CALL_STARTS, State
from app.ops.coverage import HORIZON, SIGNAL_BUSY, surges, supply
from app.ops.refs import ET, OpsRefs
from app.references import Refs

NIGHT_START_HOUR = 17  # [A7] on-shift file has no day/night role
LOW_VOLUME = {"day": 6, "night": 4}  # [B p3] rule 3
RETRY = timedelta(minutes=5)  # [B p3] rule 5
COOLDOWN = timedelta(minutes=2)  # [B p3] rule 2
PEER_TOLERANCE = 1  # [A41] counts are discrete: no peer gains, and the joiner exceeds the busiest peer, by more than one
SESSION_ENDS = {"video_ended": "video", **{k: v for k, v in CALL_ENDS.items() if v == "incoming"}}
SESSION_STARTS = {"video_started": "video", **{k: v for k, v in CALL_STARTS.items() if v == "incoming"}}


def threshold(shift_start: datetime) -> int:
    return LOW_VOLUME["night" if shift_start.astimezone(ET).hour >= NIGHT_START_HOUR else "day"]


def route_key(count: int, limit: int, last_answered: datetime | None, physician_id: str):
    """Rules 3-4: low volume first, then fewest consults, then answered least recently, then id."""
    return (count > limit, count, last_answered.timestamp() if last_answered else float("-inf"), physician_id)


def routing_order(views: list[PhysicianView], refs: Refs):
    return sorted(views, key=lambda v: route_key(v.consults_this_shift, threshold(refs.physicians[v.physician_id].shifts[0].start),
                                                 v.last_answered_at, v.physician_id))


def observed_service(events, state: State) -> dict[str, float]:
    """Median minutes a physician is busy per consult (incoming calls + video), by consult type and "*" overall [A40].
    Measured from today's events, so nothing is invented; an end without its start is skipped."""
    open_, busy = {}, {}
    for e in sorted(events, key=lambda e: (e.event_time, e.event_id)):
        if e.event_type in SESSION_STARTS:
            open_[(SESSION_STARTS[e.event_type], e.consult_id, e.physician_id)] = e.event_time
        elif e.event_type in SESSION_ENDS:
            start = open_.pop((SESSION_ENDS[e.event_type], e.consult_id, e.physician_id), None)
            if start is not None and e.consult_id in state.consults:
                busy[e.consult_id] = busy.get(e.consult_id, 0.0) + (e.event_time - start).total_seconds() / 60
    by_type = {}
    for cid, minutes in busy.items():
        by_type.setdefault(state.consults[cid].consult_type, []).append(minutes)
    out = {t: statistics.median(v) for t, v in sorted(by_type.items())}
    if busy:
        out["*"] = statistics.median(busy.values())
    return out


@dataclass(frozen=True)
class Joiner:
    physician_id: str
    ready: datetime  # takes calls from here (start + time to come online)
    end: datetime
    hospitals: frozenset[str]
    seed: int = 0


@dataclass
class _Doc:
    physician_id: str
    start: datetime
    end: datetime
    hospitals: frozenset[str]
    count: int
    limit: int
    last_answered: datetime | None
    free_at: datetime


@dataclass(frozen=True)
class Run:
    name: str
    routed: Mapping[tuple[str, str], int]  # (physician, hospital) -> consults routed in the window
    failures: Mapping[str, int]  # hospital -> failed routing attempts (each 5-minute retry counts)
    unrouted: Mapping[str, int]  # hospital -> consults still unrouted at the window end
    waits: Mapping[str, tuple[float, ...]]  # hospital -> minutes each consult waited to route (unrouted: until window end)

    def load(self, physician_id: str) -> int:
        return sum(n for (pid, _), n in self.routed.items() if pid == physician_id)

    def sites(self, physician_id: str) -> set[str]:
        return {hid for (pid, hid), n in self.routed.items() if pid == physician_id and n}

    def wait(self, hospitals) -> float:
        """Patient minutes spent waiting for a route: the gap's harm in the model."""
        return round(sum(sum(self.waits.get(h, ())) for h in hospitals), 1)

    def delayed(self, hospitals) -> int:
        return sum(1 for h in hospitals for w in self.waits.get(h, ()) if w > 0)


def _arrivals(state: State, ops: OpsRefs, refs: Refs, now: datetime, end: datetime, service, surge_rate: Mapping[str, float]):
    """(time, hospital, minutes busy). Unassigned consults waiting now, then expected demand [A12]."""
    overall = service["*"]
    out = [(now, c.hospital_id, service.get(c.consult_type, overall)) for c in sorted(state.consults.values(), key=lambda c: c.consult_id)
           if c.stage in {"Received", "Triaged"} and c.owner == "Unassigned"]
    unknown = []
    for hid in sorted(refs.hospitals):
        expected, t, next_at = 0.0, now, 0.5
        while t < end:
            hour_end = t.astimezone(ET).replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
            step_end = min(end, hour_end)
            rate = ops.mean(hid, t)
            if rate is None:
                unknown.append(hid)
                break
            rate = max(rate, surge_rate.get(hid, 0.0))
            gained = rate * (step_end - t).total_seconds() / 3600
            while rate > 0 and expected + gained >= next_at:
                out.append((t + timedelta(hours=(next_at - expected) / rate), hid, overall))
                next_at += 1
            expected, t = expected + gained, step_end
    return sorted(out, key=lambda a: (a[0], a[1])), tuple(unknown)


def _doctors(state, refs, ops, views, now, end, accepted, seed, session: timedelta):
    """On-shift and scheduled physicians from the forecast's supply; Temporarily Unavailable stay out [A37]."""
    docs = {}
    for s in supply(state, refs, ops, views, now, accepted):
        v = views.get(s.physician_id)
        if v is not None and v.derived_state == "Temporarily Unavailable" and "off_shift" not in v.exclusion_reasons:
            continue
        joiner = " split shift" in s.label
        on_now = s.start <= now and v is not None and "off_shift" not in v.exclusion_reasons
        busy = on_now and v.derived_state in SIGNAL_BUSY
        docs[s.physician_id] = _Doc(s.physician_id, max(s.start, now), min(s.end or end, end), s.hospitals,
                                    seed if joiner else v.consults_this_shift if on_now else 0,
                                    LOW_VOLUME["day"] if joiner else threshold(s.start),
                                    v.last_answered_at if on_now else None,
                                    now + session if busy else now)  # [A48] a session in progress needs one more median service time
    return docs


def simulate(name, docs: Mapping[str, _Doc], arrivals, end: datetime) -> Run:
    docs = {pid: _Doc(**d.__dict__) for pid, d in docs.items()}  # runs never share mutable state
    routed, failures, unrouted, waits = {}, {}, {}, {}
    queue = [(t, hid, n, t, minutes) for n, (t, hid, minutes) in enumerate(arrivals)]
    heapq.heapify(queue)
    while queue:
        t, hid, n, arrived, minutes = heapq.heappop(queue)
        # Rules 1-2: on shift, credentialed, not busy, not in the 2-minute cooldown (calls are answered at once; no ring time).
        eligible = [d for d in docs.values() if d.start <= t < d.end and hid in d.hospitals and d.free_at <= t]
        if not eligible:
            failures[hid] = failures.get(hid, 0) + 1
            if t + RETRY < end:
                heapq.heappush(queue, (t + RETRY, hid, n, arrived, minutes))
            else:
                unrouted[hid] = unrouted.get(hid, 0) + 1
                waits.setdefault(hid, []).append((end - arrived).total_seconds() / 60)
            continue
        d = min(eligible, key=lambda d: route_key(d.count, d.limit, d.last_answered, d.physician_id))
        d.count += 1
        d.last_answered = t
        d.free_at = t + timedelta(minutes=minutes) + COOLDOWN
        routed[(d.physician_id, hid)] = routed.get((d.physician_id, hid), 0) + 1
        waits.setdefault(hid, []).append((t - arrived).total_seconds() / 60)
    return Run(name, routed, failures, unrouted, {h: tuple(w) for h, w in waits.items()})


@dataclass(frozen=True)
class Criterion:
    key: str
    passed: bool
    value: str


@dataclass(frozen=True)
class TrapCheck:
    joiner: Joiner
    seed: int
    scenarios: Mapping[str, tuple[Run, Run, Run]]  # demand scenario -> (no joiner, trap: unrestricted unseeded, guarded)
    criteria: tuple[Criterion, ...]
    trap_shown: bool
    relief: Mapping[str, float]  # scenario -> patient wait minutes at gap hospitals removed by the guarded joiner
    spill: Mapping[str, int]  # scenario -> consults the unguarded joiner takes at hospitals outside the offer
    unknown_demand: tuple[str, ...] = field(default=())

    @property
    def passed(self) -> bool:
        return all(c.passed for c in self.criteria)


def guard_seed(views: Mapping[str, PhysicianView], hospitals) -> int:
    """[A26] seed = max(day threshold + 1, fewest consults among on-shift peers credentialed at the gap hospitals),
    so the joiner is never 'low volume' and only takes calls once the least-loaded peer there is busy or level."""
    peers = [v.consults_this_shift for v in views.values() if "off_shift" not in v.exclusion_reasons
             and v.derived_state != "Temporarily Unavailable" and v.credentialed_hospitals & set(hospitals)]  # TU peers take no calls
    return max(LOW_VOLUME["day"] + 1, min(peers, default=0))


def trap_check(state: State, refs: Refs, ops: OpsRefs, views: Mapping[str, PhysicianView], now: datetime, physician_id: str,
               ready: datetime, end: datetime, hospitals, service: Mapping[str, float], accepted=()) -> TrapCheck | None:
    """Three runs per demand scenario [doc 5.4]: (a) no joiner, (b) joiner unrestricted and unseeded, (c) restricted and seeded.
    Returns None when no service time was observed (nothing to model honestly)."""
    if "*" not in service:
        return None
    window_end = max(end, now + HORIZON)
    hospitals = frozenset(hospitals)
    seed = guard_seed(views, hospitals)
    base = _doctors(state, refs, ops, views, now, window_end, accepted, seed, timedelta(minutes=service["*"]))
    base.pop(physician_id, None)
    creds = refs.credentials[physician_id]
    joiner = Joiner(physician_id, ready, end, hospitals, seed)

    def with_joiner(sites, count):
        return {**base, physician_id: _Doc(physician_id, ready, end, frozenset(sites), count, LOW_VOLUME["day"], None, ready)}

    surge_rate = {s.hospital_id: float(s.count) for s in surges(state, refs, ops, now)}
    demands = {"baseline": {}, **({"surge_continues": surge_rate} if surge_rate else {})}
    scenarios, relief, spill, criteria, trap_shown, unknown = {}, {}, {}, [], False, ()
    for label, rates in demands.items():
        arrivals, unknown = _arrivals(state, ops, refs, now, window_end, service, rates)
        runs = (simulate("no_joiner", base, arrivals, window_end), simulate("trap", with_joiner(creds, 0), arrivals, window_end),
                simulate("guarded", with_joiner(hospitals, seed), arrivals, window_end))
        scenarios[label] = runs
        a, b, c = runs
        peers = list(base)
        busiest = max((c.load(p) for p in peers), default=0)
        outside_b = sorted(b.sites(physician_id) - hospitals)
        trap_shown |= bool(outside_b) or b.load(physician_id) > max((b.load(p) for p in peers), default=0)
        outside_c = sorted(c.sites(physician_id) - hospitals)
        rises = {p: c.load(p) - a.load(p) for p in peers if c.load(p) - a.load(p) > PEER_TOLERANCE}
        relief[label] = round(a.wait(hospitals) - c.wait(hospitals), 1)
        spill[label] = sum(n for (pid, hid), n in b.routed.items() if pid == physician_id and hid not in hospitals)
        criteria += [
            Criterion(f"{label}:joiner_only_at_gap_hospitals", not outside_c, ", ".join(outside_c) or "gap hospitals only"),
            Criterion(f"{label}:gap_wait_not_worse", c.wait(hospitals) <= a.wait(hospitals),
                      f"{a.wait(hospitals):g} -> {c.wait(hospitals):g} patient-min, delayed {a.delayed(hospitals)} -> {c.delayed(hospitals)}"),
            Criterion(f"{label}:joiner_not_above_busiest_peer", c.load(physician_id) <= busiest + PEER_TOLERANCE, f"{c.load(physician_id)} vs {busiest}"),
            Criterion(f"{label}:peers_within_tolerance", not rises, ", ".join(f"{p} +{n}" for p, n in sorted(rises.items())) or f"none above +{PEER_TOLERANCE}"),
        ]
    return TrapCheck(joiner, seed, scenarios, tuple(criteria), trap_shown, relief, spill, unknown)
