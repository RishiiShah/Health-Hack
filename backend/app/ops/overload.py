"""G8b: workload warnings are evidence for review, never routing exclusions."""
from datetime import timedelta
from statistics import median
from app.config import DEFAULT_OVERLOAD


def overloads(state, views, now, policy=DEFAULT_OVERLOAD):
    lower = now - timedelta(minutes=policy.window_minutes)
    on_shift = {pid: v for pid, v in sorted(views.items()) if "off_shift" not in v.exclusion_reasons}
    rates = {pid: sum(any(owner == pid and lower < at <= now for owner, at in c.assignments)
                      for c in state.consults.values()) for pid in on_shift}
    # Without an observed start we cannot claim this physician was observed for the full window.
    complete = {pid for pid, v in on_shift.items() if v.shift and v.shift.start <= lower
                and (p := state.physicians.get(pid)) and any(v.shift.start <= at <= lower for at in p.shift_starts)}
    result = {}
    for pid, v in on_shift.items():
        peers = sorted(complete - {pid})
        mid = median(rates[p] for p in peers) if len(peers) >= policy.minimum_peers else None
        unavailable = ("physician not observed for full window" if pid not in complete else
                       "insufficient peers" if mid is None else "zero peer median" if mid == 0 else None)
        rate_warning = unavailable is None and rates[pid] > policy.rate_multiple * mid
        warning = v.open_consults >= policy.open_warning or rate_warning
        notes = sorted(c.consult_id for c in state.consults.values()
                       if c.owner == pid and c.stage in {"Note Pending", "Documentation"})
        shift_risk = bool(notes) and v.shift is not None and timedelta(0) < v.shift.end - now <= timedelta(minutes=60)
        level = "Critical" if v.open_consults >= policy.open_critical or (warning and shift_risk) else "Warning" if warning else None
        reasons = []
        if v.open_consults >= policy.open_warning:
            reasons.append(f"{v.open_consults} open consults (warning {policy.open_warning}, critical {policy.open_critical})")
        if rate_warning:
            reasons.append(f"{rates[pid]} distinct assignments in {policy.window_minutes} min > {policy.rate_multiple:g} × peer median {mid:g}")
        if warning and shift_risk:
            reasons.append(f"open notes with shift ending in {v.minutes_to_shift_end} min")
        result[pid] = {"level": level, "open_consults": v.open_consults, "assignments_in_window": rates[pid],
                       "window_minutes": policy.window_minutes, "peer_ids": peers, "peer_median": mid,
                       "rate_available": unavailable is None, "rate_unavailable_reason": unavailable,
                       "rate_multiple": policy.rate_multiple, "shift_end_risk": shift_risk, "reasons": reasons}
    return result
