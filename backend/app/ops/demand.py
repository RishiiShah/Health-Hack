"""Deterministic expected arrivals from hourly reference means, independent of live receipts."""
from datetime import datetime, timedelta
from math import fsum
from app.clock import utc
from app.ops.refs import OpsRefs


def expected_arrivals(ops: OpsRefs, hospital_id: str, start: datetime, end: datetime) -> float | None:
    """Integrate [start,end) in elapsed UTC time. Any missing hour makes the total unknown.

    Minute boundaries respect modern IANA offsets and DST transitions, including repeated hours.
    Partial endpoint minutes retain their exact duration; no arrivals are injected into replay.
    """
    cursor, end = utc(start), utc(end)
    if end < cursor:
        raise ValueError("demand horizon ends before it starts")
    terms = []
    while cursor < end:
        stop = min(cursor.replace(second=0, microsecond=0) + timedelta(minutes=1), end)
        mean = ops.mean(hospital_id, cursor)
        if mean is None:
            return None
        terms.append(mean * (stop - cursor).total_seconds() / 3600)
        cursor = stop
    return fsum(terms)
