"""G17/G18: split-shift eligibility for every off-shift physician against one proposal. Pure."""
import csv
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Mapping
from app.clock import utc
from app.ops.coverage import Gap
from app.ops.refs import ET, OpsRefs
from app.references import Refs

MIN_OFFER = timedelta(hours=2)
MIN_REST = timedelta(hours=10)
MAX_WEEK_HOURS = 60
MAX_WEEKLY_OFFERS = 3
LOW_VALUE = timedelta(minutes=60)  # [A39]
OPEN_STATES = {"proposed", "approved", "sent", "pending", "open"}


@dataclass(frozen=True)
class OfferHistory:
    open: frozenset[str] = frozenset()  # physicians with an unresolved offer
    sent_7d: Mapping[str, int] = field(default_factory=dict)
    accepted: Mapping[str, tuple[tuple[datetime, datetime], ...]] = field(default_factory=dict)
    supplied: bool = False  # False: no history file, counts shown as assumed zero


def load_offer_history(path: str | Path, now: datetime) -> OfferHistory:
    """support/offer_history.csv: offer_id, physician_id, sent_at, status."""
    now, sent, open_ = utc(now), {}, set()
    with Path(path).open(newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            at = utc(datetime.fromisoformat(row["sent_at"]))
            if now - timedelta(days=7) <= at <= now:
                sent[row["physician_id"]] = sent.get(row["physician_id"], 0) + 1
            if row["status"].lower() in OPEN_STATES:
                open_.add(row["physician_id"])
    return OfferHistory(frozenset(open_), sent, {}, True)


@dataclass(frozen=True)
class Proposal:
    start: datetime
    end: datetime
    hospitals: tuple[str, ...]


@dataclass(frozen=True)
class Rule:
    key: str
    label: str
    passed: bool
    value: str


@dataclass(frozen=True)
class Candidate:
    physician_id: str
    rules: tuple[Rule, ...]
    proposal: Proposal
    ready_at: datetime
    hospitals: tuple[str, ...]  # proposal hospitals this physician is credentialed at
    covered_minutes: int
    low_value: bool

    @property
    def eligible(self):
        return all(r.passed for r in self.rules)

    @property
    def failed(self):
        return tuple(r.key for r in self.rules if not r.passed)

    @property
    def start(self):
        return self.proposal.start

    @property
    def end(self):
        return self.proposal.end


def proposal_for(gap: Gap, now: datetime) -> Proposal:
    """One gap, one hospital: R2 then asks whether this physician can fix *this* gap. Offers for the
    same physician and window merge later, so one message can still cover several hospitals."""
    start = max(gap.start, now)
    return Proposal(start, max(gap.end, start + MIN_OFFER), (gap.hospital_id,))


def _hm(t):
    return t.astimezone(ET).strftime("%m-%d %H:%M")


def _hours(delta):
    return round(delta.total_seconds() / 3600, 2)


def evaluate_proposal(proposal: Proposal, refs: Refs, ops: OpsRefs, now: datetime, history: OfferHistory = OfferHistory(),
                      gaps: list[Gap] = ()) -> list[Candidate]:
    """Every roster physician against every rule, never short-circuited [B p4, H ch2 #8]."""
    now = utc(now)
    start, end = proposal.start, proposal.end
    nominal = end - start
    out = []
    for pid, r in sorted(ops.roster.items()):
        creds = refs.credentials.get(pid, frozenset())
        sites = tuple(h for h in proposal.hospitals if h in creds)
        ready = max(start, now + timedelta(minutes=r.minutes_to_online))
        useful = end - ready
        shifts = refs.physicians[pid].shifts if pid in refs.physicians else ()
        accepted = history.accepted.get(pid, ())
        on_now = any(s.start <= now < s.end for s in shifts) or any(s <= now < e for s, e in accepted)
        # Accepted obligations count even if an arrival event has not been observed. Use the
        # latest known end before this proposal; future shifts are handled by R5 below.
        prior_ends = [s.end for s in shifts if s.end <= start]
        prior_ends.extend(e for _, e in accepted if e <= start)
        prior_ends.extend(e for e in (r.last_shift_end, r.next_shift_end) if e is not None and e <= start)
        rest = start - max(prior_ends) if prior_ends else None
        accepted_hours = sum((e - s).total_seconds() for s, e in accepted) / 3600
        total = r.hours_last_7d + accepted_hours + nominal.total_seconds() / 3600
        scheduled = {(s.start, s.end) for s in shifts}
        if r.next_shift_start:
            scheduled.add((r.next_shift_start, r.next_shift_end))  # end unknown (None): open-ended
        clashes = [f"scheduled {_hm(s)}" for s, e in sorted(scheduled, key=lambda x: x[0]) if s < end and (e is None or start < e)]
        clashes += [f"split {_hm(s)}-{_hm(e)}" for s, e in accepted if s < end and start < e]
        sent = history.sent_7d.get(pid, 0)
        covered = sum((max(timedelta(0), min(end, g.end) - max(ready, g.start)) for g in gaps if g.kind == "hard" and g.hospital_id in sites), timedelta(0))
        rules = (
            Rule("off_shift_now", "Off shift now", not on_now, "on shift" if on_now else "off shift"),
            Rule("opted_in", "R1 opted in", r.opt_in, "yes" if r.opt_in else "no"),
            Rule("credentialed_at_gap", "R2 credentialed at a gap hospital", bool(sites), ", ".join(sites) or "none of " + ", ".join(proposal.hospitals)),
            Rule("rest_at_start_at_least_10h", "R3 10 h rest at start", rest is not None and rest >= MIN_REST, f"{_hours(rest)} h" if rest is not None else "last shift unknown"),
            Rule("trailing7d_plus_offer_at_most_60h", "R4 7-day hours + offer <= 60", total <= MAX_WEEK_HOURS, f"{r.hours_last_7d:g} + {accepted_hours:g} + {_hours(nominal):g} = {total:g} h"),
            Rule("no_schedule_overlap", "R5 no overlap with a scheduled shift", not clashes, "; ".join(clashes) or "none"),
            Rule("nominal_duration_at_least_2h", "R6 offer at least 2 h", nominal >= MIN_OFFER, f"{_hours(nominal):g} h"),
            Rule("useful_duration_at_least_2h", "R6 at least 2 h after coming online", useful >= MIN_OFFER, f"{_hours(useful):g} h ({r.minutes_to_online} min to online)"),
            Rule("no_open_offer", "R7 no other open offer", pid not in history.open, "open offer" if pid in history.open else "none"),
            Rule("weekly_offer_count_below_3", "R8 under 3 offers this week", sent + 1 <= MAX_WEEKLY_OFFERS, f"{sent} sent" + ("" if history.supplied else " (no history supplied)")),
            Rule("start_not_in_past", "Start not in the past", start >= now, _hm(start)),
        )
        out.append(Candidate(pid, rules, proposal, ready, sites, int(covered.total_seconds() // 60), bool(gaps) and covered < LOW_VALUE))
    return sorted(out, key=lambda c: rank_key(c, ops, history))


def rank_key(c: Candidate, ops: OpsRefs, history: OfferHistory) -> tuple:
    """Eligible first, then covered gap minutes, minutes to online, declines (30 d), hours (7 d), offers this week, ID."""
    r = ops.roster[c.physician_id]
    return (not c.eligible, -c.covered_minutes, r.minutes_to_online, r.declines_30d, r.hours_last_7d, history.sent_7d.get(c.physician_id, 0), c.physician_id)


def ranked_above(a: Candidate, b: Candidate, ops: OpsRefs, history: OfferHistory) -> str:
    """Why `a` ranks above `b`, in words: the first step of rank_key where they differ, so it cannot disagree with the order."""
    ka, kb = rank_key(a, ops, history), rank_key(b, ops, history)
    step = next(i for i in range(len(ka)) if ka[i] != kb[i])
    x, y = ka[step], kb[step]
    return [
        lambda: "is eligible",
        lambda: f"covers {y - x} more gap minutes ({-x} vs {-y})",
        lambda: f"is online {y - x} min sooner ({x} vs {y} min)",
        lambda: f"declined fewer offers in 30 days ({x} vs {y})",
        lambda: f"worked fewer hours in the last 7 days ({x:g} vs {y:g} h)",
        lambda: f"has had fewer offers this week ({x} vs {y})",
        lambda: "ties on every ranking step; the lower physician ID goes first",
    ][step]()


def evaluate(gap: Gap, hard_gaps: list[Gap], refs: Refs, ops: OpsRefs, now: datetime, history: OfferHistory = OfferHistory()) -> list[Candidate]:
    return evaluate_proposal(proposal_for(gap, now), refs, ops, now, history, [*hard_gaps, gap])
