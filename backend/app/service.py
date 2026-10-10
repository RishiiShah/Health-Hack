"""Step 9: the engine behind the API. Builds decisions from the live publication and serializes them for clients.

Clients only display what this returns; every level, gap, candidate and fix is computed here [00-Boundaries].
"""
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from app.act.interventions import InterventionLog
from app.act.offers import Context, OfferDesk
from app.decide.eligibility import OfferHistory, load_offer_history
from app.decide.interventions import Decisions, decide
from app.decide.routing_sim import observed_service, trap_check
from app.ops.coverage import current_coverage
from app.ops.refs import OpsRefs, load_ops_refs
from app.references import Refs, load_reference_dir


def load_references(directory: str | Path, service_date: date | None = None) -> tuple[Refs, OpsRefs]:
    refs = load_reference_dir(directory, service_date)
    return refs, load_ops_refs(directory, {h: x.timezone for h, x in refs.hospitals.items()}, set(refs.physicians))


def base_history(path: str | Path | None, now: datetime) -> OfferHistory:
    return load_offer_history(path, now) if path and Path(path).exists() else OfferHistory()


def jsonable(value):
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(k): jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        items = [jsonable(v) for v in value]
        return sorted(items) if isinstance(value, (set, frozenset)) else items
    return value


def candidate_payload(c):
    return {"physician_id": c.physician_id, "eligible": c.eligible, "failed": list(c.failed), "start": c.start.isoformat(), "end": c.end.isoformat(),
            "ready_at": c.ready_at.isoformat(), "hospitals": list(c.hospitals), "covered_minutes": c.covered_minutes, "low_value": c.low_value,
            "rules": [{"key": r.key, "label": r.label, "passed": r.passed, "value": r.value} for r in c.rules]}


def item_payload(rank, item, intervention=None):
    f = item.fix
    return {"rank": rank, "id": item.id, "severity": item.severity, "what": item.what, "where": jsonable(item.where), "why": jsonable(item.why),
            "fix": {"kind": f.kind, "approver": f.approver, "action": f.action, "reason": f.reason, "alternatives": list(f.alternatives),
                    "physician_id": f.physician_id},
            "candidates": len(item.candidates), "intervention": jsonable(intervention) if intervention else None}


@dataclass
class Engine:
    """Decisions for the current publication, cached until the revision, the clock second or an offer changes."""
    coordinator: object
    ops: OpsRefs | None
    desk: OfferDesk
    interventions: InterventionLog

    def __post_init__(self):
        self._key, self._value = None, None

    @property
    def ready(self) -> bool:
        return self.ops is not None and self.coordinator.refs is not None

    def context(self) -> Context:
        p = self.coordinator.current_publication()
        return Context(p.state, p.refs, self.ops, p.as_of, p.revision)

    def decisions(self) -> tuple[object, Decisions | None]:
        p = self.coordinator.current_publication()
        key = (p.revision, id(p.state), p.as_of.replace(microsecond=0), self.desk.version)
        if self._key == key:
            return self._value
        decisions = None
        if self.ready:
            service = observed_service(self.coordinator.visible_events(), p.state)
            decisions = decide(p.state, p.refs, self.ops, p.as_of, self.desk.history(p.as_of), self.desk.accepted(), service=service)
        self._key, self._value = key, (p, decisions)
        return self._value

    def item(self, item_id: str):
        _, d = self.decisions()
        return next((i for i in d.items if i.id == item_id), None) if d else None

    def trap(self, item):
        """Full simulator output for the item's offer: the trap guard verdict plus each run's loads."""
        p, d = self.decisions()
        best = next(c for c in item.candidates if c.physician_id == item.fix.physician_id)
        check = trap_check(p.state, p.refs, self.ops, d.views, p.as_of, best.physician_id, best.ready_at, best.end, best.hospitals,
                           observed_service(self.coordinator.visible_events(), p.state), self.desk.accepted())
        if check is None:
            return {"modeled": False, "reason": "no service time observed yet"}
        hospitals = sorted(check.joiner.hospitals)
        return {"modeled": True, "physician_id": best.physician_id, "restrict_to": hospitals, "seed": check.seed, "passed": check.passed,
                "trap_shown_unguarded": check.trap_shown, "wait_minutes_removed": dict(check.relief), "unguarded_spill": dict(check.spill),
                "criteria": [{"key": c.key, "passed": c.passed, "value": c.value} for c in check.criteria],
                "scenarios": {name: {run.name: {"loads": {pid: run.load(pid) for pid in sorted({pid for pid, _ in run.routed})},
                                                "joiner_sites": sorted(run.sites(best.physician_id)), "gap_wait_minutes": run.wait(hospitals),
                                                "gap_delayed": run.delayed(hospitals), "failed_attempts": sum(run.failures.values()),
                                                "unrouted": sum(run.unrouted.values())} for run in runs}
                              for name, runs in check.scenarios.items()}}

    def snapshot(self, epoch: str, clock_mode: str) -> dict:
        p, d = self.decisions()
        consults = [{"consult_id": c.consult_id, "hospital_id": c.hospital_id, "consult_type": c.consult_type, "physician_id": c.owner,
                     "current_stage": c.stage, "stage_entered_at": c.entered_at.isoformat(),
                     "minutes_in_stage": max(0, int((p.as_of - c.entered_at).total_seconds() // 60)),
                     "minutes_since_received": max(0, int((p.as_of - c.received_at).total_seconds() // 60)),
                     "repeat_contacts": c.repeat_contacts, "routing_failures": c.routing_failures}
                    for c in p.state.consults.values() if c.stage != "Signed Off"]
        body = {"revision": p.revision, "reference_revision": p.reference_revision, "clock_revision": 0, "epoch": epoch, "sequence": p.revision,
                "clock": {"mode": clock_mode, "now": p.as_of.isoformat()}, "consults": consults,
                "data_quality": {"supported": True, "accepted_events": p.event_count, "held_orphans": p.held_orphans, **dict(p.stats)},
                "capabilities": {"orphan_holding": True, "reference_validation": p.refs is not None, "physician_state": d is not None, "detection": d is not None}}
        if d is None:
            return {**body, "headline": {"open_consults": len(consults)}, "physicians": {"supported": False, "items": []},
                    "hospitals": {"supported": False, "items": []}, "queue": {"supported": False, "items": []}, "coverage": {"supported": False},
                    "offers": {"supported": False, "items": []}}
        done = self.interventions.latest()
        offers = self.desk.offers()
        coverage = current_coverage(p.state, p.refs, self.ops, d.views, p.as_of)
        return {**body,
                "headline": {"open_consults": len(consults), "critical": sum(i.severity == "Critical" for i in d.items),
                             "hard_gaps_in_horizon": sum(g.kind == "hard" and g.in_horizon for g in d.gaps),
                             "offers_awaiting_approval": sum(o.state == "PROPOSED" for o in offers), "offers_out": sum(o.state == "SENT" for o in offers)},
                "queue": {"supported": True, "items": [item_payload(n, i, done.get(i.id)) for n, i in enumerate(d.items, 1)]},
                "physicians": {"supported": True, "items": [{"physician_id": v.physician_id, "derived_state": v.derived_state,
                                                             "self_reported_status": v.self_reported_status, "desktop_agent": v.desktop_agent,
                                                             "routable": v.routable, "exclusion_reasons": list(v.exclusion_reasons), "flags": list(v.flags),
                                                             "consults_this_shift": v.consults_this_shift, "open_consults": v.open_consults,
                                                             "minutes_to_shift_end": v.minutes_to_shift_end,
                                                             "credentialed_hospitals": sorted(v.credentialed_hospitals)} for v in d.views.values()]},
                "hospitals": {"supported": True, "items": [{"hospital_id": c.hospital_id, "name": p.refs.hospitals[c.hospital_id].name,
                                                            "required": c.required, "base_requirement": c.base_requirement, "surge": c.surge,
                                                            "trailing_60m": c.trailing_60m, "p90": c.p90, "available": list(c.available),
                                                            "routable": list(c.routable), "gap": c.gap} for c in coverage]},
                "coverage": {"supported": True, "gaps": [{"id": g.id, "hospital_id": g.hospital_id, "kind": g.kind, "start": g.start.isoformat(),
                                                          "end": g.end.isoformat(), "required": g.required, "confirmed": g.confirmed,
                                                          "scheduled": g.scheduled, "surge": g.surge, "in_horizon": g.in_horizon,
                                                          "causes": list(g.causes)} for g in d.gaps],
                             "surges": [{"hospital_id": s.hospital_id, "count": s.count, "p90": s.p90, "until": s.until.isoformat()} for s in d.surges]},
                "offers": {"supported": True, "items": [o.payload() for o in offers]}}
