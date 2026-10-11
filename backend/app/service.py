"""Step 9: the engine behind the API. Builds decisions from the live publication and serializes them for clients.

Clients only display what this returns; every level, gap, candidate and fix is computed here [00-Boundaries].
"""
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Lock
from app.act.interventions import InterventionLog
from app.act.offers import OPEN, Context, OfferDesk
from app.decide.eligibility import OfferHistory, Proposal, evaluate, evaluate_proposal, load_offer_history
from app.decide.interventions import Decisions, decide
from app.decide.routing_sim import observed_service, trap_check
from app.ops.coverage import HORIZON, current_coverage, outlook_end, supply, surge_at, _received
from app.ops.detect import NOTE_STAGES
from app.ops.refs import OpsRefs, load_ops_refs
from app.references import Refs, load_reference_dir


def load_references(directory: str | Path, service_date: date | None = None) -> tuple[Refs, OpsRefs]:
    refs = load_reference_dir(directory, service_date)
    return refs, load_ops_refs(directory, {h: x.timezone for h, x in refs.hospitals.items()}, set(refs.physicians))


REFERENCE_FILES = ("hospitals.csv", "physicians_on_shift.csv", "physicians_off_shift_roster.csv", "credentialing_matrix.csv",
                   "baseline_hourly_volume.csv", "coverage_requirements.csv")


def references_from_files(files: dict[str, str], service_date: date | None = None) -> tuple[Refs, OpsRefs]:
    """Uploaded reference CSVs (file name -> text), checked by the same loaders as a CC_DATA_DIR folder."""
    if set(files) != set(REFERENCE_FILES):
        raise ValueError(f"expected exactly these files: {', '.join(REFERENCE_FILES)}")
    with TemporaryDirectory() as directory:
        for name, text in files.items():
            (Path(directory) / name).write_text(text, encoding="utf-8")
        return load_references(directory, service_date)


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


def runs_view(check, physician_id):
    """Each simulator run per demand scenario: loads per physician and the gap hospitals' waits."""
    hospitals = sorted(check.joiner.hospitals)
    return {name: {run.name: {"loads": {pid: run.load(pid) for pid in sorted({pid for pid, _ in run.routed})},
                              "joiner_sites": sorted(run.sites(physician_id)), "gap_wait_minutes": run.wait(hospitals),
                              "gap_delayed": run.delayed(hospitals), "failed_attempts": sum(run.failures.values()),
                              "unrouted": sum(run.unrouted.values())} for run in runs}
            for name, runs in check.scenarios.items()}


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
    dataset: dict = field(default_factory=dict)  # {name, description, reference_files} for the header
    speech_available: bool = False  # offers get an audio_url only when text-to-speech can answer it

    def __post_init__(self):
        self._key, self._value = None, None
        self.swap = Lock()  # held while references and their operational tables are replaced together

    def use_references(self, refs: Refs, ops: OpsRefs, source: dict, dataset: dict) -> dict:
        """Switch to uploaded references: readers never see new references with the old operational tables."""
        with self.swap:
            report = self.coordinator.activate_references(refs, source)
            self.ops, self.dataset = ops, dataset
        return report

    def _current(self):
        with self.swap:
            return self.coordinator.current_publication(), self.ops

    @property
    def ready(self) -> bool:
        return self.ops is not None and self.coordinator.refs is not None

    def context(self) -> Context:
        p, ops = self._current()
        return Context(p.state, p.refs, ops, p.as_of, p.revision)

    def decisions(self) -> tuple[object, Decisions | None]:
        p, ops = self._current()
        key = (p.revision, id(p.state), p.as_of.replace(microsecond=0), self.desk.version, id(ops))
        if self._key == key:
            return self._value
        decisions = None
        if ops is not None and p.refs is not None:
            service = observed_service(self.coordinator.visible_events(), p.state)
            decisions = decide(p.state, p.refs, ops, p.as_of, self.desk.history(p.as_of), self.desk.accepted(), service=service)
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
                "scenarios": runs_view(check, best.physician_id)}

    def coverage_grid(self, p, d, coverage):
        """Now (free by signals), then every 15 min to +90 min (everyone scheduled, accepted split shifts included)."""
        steps = [p.as_of + STEP * n for n in range(7)]
        items = supply(p.state, p.refs, self.ops, d.views, p.as_of, self.desk.accepted())
        now_items = {i.id for i in d.items}
        current = {c.hospital_id: c for c in coverage}
        hospitals = []
        for hid in sorted(p.refs.hospitals):
            received, cells = _received(p.state, hid, p.as_of), []
            for n, t in enumerate(steps):
                if n == 0:
                    c = current[hid]
                    ids, missing, required = list(c.available), [], c.required
                    unverified = any("unverified" in d.views[x].flags for x in ids)
                    gap_id = f"now_gap:{hid}" if f"now_gap:{hid}" in now_items else None
                else:
                    here = [s for s in items if hid in s.hospitals and s.start <= t and (s.end is None or t < s.end)]
                    ids = sorted(s.physician_id for s in here)
                    missing = sorted(s.physician_id for s in here if not s.confirmed)
                    unverified = any("unverified" in d.views[s.physician_id].flags for s in here if s.physician_id in d.views and s.confirmed)
                    base, surge = self.ops.requirement(hid, t), surge_at(self.ops, hid, received, t)
                    required = None if base is None or surge is None else base + surge
                    gap_id = next((g.id for g in d.gaps if g.hospital_id == hid and g.kind == "hard" and g.start <= t < g.end), None)
                count = len(ids)
                status = "unknown" if required is None else "gap" if count < required else "at_minimum" if count == required else "above_minimum"
                cells.append({"at": t.isoformat(), "count": count, "required": required, "status": status, "unverified": unverified,
                              "schedule_incomplete": bool(missing), "physician_ids": ids, "incomplete_physician_ids": missing,
                              "gap_id": gap_id if status == "gap" else None})
            hospitals.append({"hospital_id": hid, "hospital_name": p.refs.hospitals[hid].name, "nobody_reachable_now": not current[hid].routable,
                              "cells": cells})
        return {"supported": True, "steps": [t.isoformat() for t in steps], "hospitals": hospitals,
                "assumption": "Now counts physicians free by signals; later steps count everyone scheduled (busy and temporarily unavailable included) "
                              "and starters from their start, with a surge's +1 until 60 minutes after its consults arrived"}

    def gap_view(self, gap_id):
        """A queue item, or a forecast gap from the grid, with its candidate table. None if neither exists now."""
        p, d = self.decisions()
        if d is None:
            return None
        item = next((i for i in d.items if i.id == gap_id), None)
        gap = next((g for g in d.gaps if g.id == gap_id), None)
        offer = next((o for o in self.desk.offers() if o.gap_id == gap_id and o.state in OPEN), None)
        if item is None and gap is None and offer is None:
            return None
        if offer is not None:
            # Under review: the table the lead sees is the check approval will run, so the offer's own physician is
            # not failed on R7 by the very offer being reviewed.
            start = max(offer.start, p.as_of)
            candidates = tuple(evaluate_proposal(Proposal(start, offer.end, offer.hospitals), p.refs, self.ops, p.as_of,
                                                 self.desk.history(p.as_of, exclude=offer.id), [g for g in d.gaps if g.kind == "hard"]))
        elif item is not None and item.candidates:
            candidates = item.candidates
        elif gap is not None:
            candidates = tuple(evaluate(gap, [g for g in d.gaps if g.kind == "hard"], p.refs, self.ops, p.as_of, self.desk.history(p.as_of)))
        else:
            return None
        hospitals = list(offer.hospitals) if offer else (item.where.get("hospital_ids") or [item.where.get("hospital_id")]) if item else [gap.hospital_id]
        why = item.why if item else {}
        start = max(offer.start, p.as_of) if offer else gap.start if gap else p.as_of
        end = offer.end if offer else gap.end if gap else outlook_end(p.refs, p.as_of)
        required = gap.required if gap else why.get("required")
        count = (gap.confirmed + gap.scheduled) if gap else len(why.get("available", []))
        causes = list(gap.causes if gap else why.get("causes", []))
        summary = (item.what if item else f"{p.refs.hospitals[gap.hospital_id].name} short of credentialed coverage") + (
            ". " + "; ".join(causes[:4]) if causes else "")
        return {"item": item, "gap": gap, "offer": offer, "candidates": candidates, "now": p.as_of, "revision": p.revision,
                "view": {"gap_id": gap_id, "hospital_ids": hospitals, "hospital_names": [p.refs.hospitals[h].name for h in hospitals],
                         "start": start.isoformat(), "end": end.isoformat(), "required": required, "count": count, "summary": summary}}

    def candidates_view(self, gap_id):
        g = self.gap_view(gap_id)
        if g is None:
            return None
        p, _ = self.decisions()
        ranked = [c for c in g["candidates"] if c.eligible]
        rules = [{"id": RULE_CODES.get(r.key, r.key), "label": r.label} for r in g["candidates"][0].rules] if g["candidates"] else []
        out = []
        for c in g["candidates"]:
            roster = self.ops.roster[c.physician_id]
            failed = [r for r in c.rules if not r.passed]
            out.append({"physician_id": c.physician_id, "name": p.refs.physicians[c.physician_id].name if c.physician_id in p.refs.physicians else c.physician_id,
                        "eligible": c.eligible, "rank": ranked.index(c) + 1 if c.eligible else None,
                        "primary_reason": f"{failed[0].label}: {failed[0].value}" if failed else ("low value: covers under 60 gap minutes" if c.low_value else None),
                        "results": [{"rule": RULE_CODES.get(r.key, r.key), "status": "pass" if r.passed else "fail", "explanation": r.value} for r in c.rules],
                        "ranking": {"gap_hospitals": len(c.hospitals), "minutes_to_online": roster.minutes_to_online, "declines_30d": roster.declines_30d,
                                    "hours_7d": roster.hours_last_7d},
                        "window": {"start": c.start.isoformat(), "end": c.end.isoformat(), "ready_at": c.ready_at.isoformat(), "hospitals": list(c.hospitals)}})
        fix = g["item"].fix if g["item"] else None
        return {"gap": g["view"], "revision": g["revision"], "rules": rules, "candidates": out,
                "fix": {"kind": fix.kind, "action": fix.action, "reason": fix.reason, "physician_id": fix.physician_id} if fix else None}

    def trap_view(self, gap_id):
        """The trap check for the gap's best eligible physician, summarized for the screen; raw runs under `scenarios`."""
        g = self.gap_view(gap_id)
        if g is None:
            return None
        item = g["item"]
        pid = (g["offer"].physician_id if g["offer"] else item.fix.physician_id if item is not None and item.fix.kind == "split_shift"
               else next((c.physician_id for c in g["candidates"] if c.eligible), None))
        if pid is None:
            return {"gap_id": gap_id, "physician_id": None, "passed": False, "reasons": ["nobody eligible: no offer to check; escalate"],
                    "seed_consults": None, "limited_to": [], "steps": [], "without": [], "with": [], "joiner_load": 0, "busiest_peer_load": 0,
                    "other_gaps_worsened": False, "assumption": None}
        best = next(c for c in g["candidates"] if c.physician_id == pid)
        if not best.eligible:
            return {"gap_id": gap_id, "physician_id": pid, "passed": False, "reasons": [f"{pid} fails {', '.join(best.failed)}: no offer to check"],
                    "seed_consults": None, "limited_to": [], "steps": [], "without": [], "with": [], "joiner_load": 0, "busiest_peer_load": 0,
                    "other_gaps_worsened": False, "assumption": None}
        p, d = self.decisions()
        check = trap_check(p.state, p.refs, self.ops, d.views, p.as_of, pid, best.ready_at, best.end, best.hospitals,
                           observed_service(self.coordinator.visible_events(), p.state), self.desk.accepted())
        if check is None:
            return {"gap_id": gap_id, "physician_id": pid, "passed": False, "reasons": ["not modeled: no service time observed yet"],
                    "seed_consults": None, "limited_to": [], "steps": [], "without": [], "with": [], "joiner_load": 0, "busiest_peer_load": 0,
                    "other_gaps_worsened": False, "assumption": None}
        _, _, guarded = check.scenarios["baseline"]
        none = check.scenarios["baseline"][0]
        sites = sorted(check.joiner.hospitals)
        others = sorted(set(p.refs.hospitals) - set(sites))
        grid = {h["hospital_id"]: h for h in self.coverage_grid(p, d, current_coverage(p.state, p.refs, self.ops, d.views, p.as_of))["hospitals"]}
        cells = grid[sites[0]]["cells"]
        joined = lambda t: best.ready_at <= datetime.fromisoformat(t) < best.end
        peers = sorted({x for x, _ in guarded.routed} - {pid})
        return {"gap_id": gap_id, "physician_id": pid, "passed": check.passed,
                "reasons": [f"{c.key.split(':', 1)[1].replace('_', ' ')} ({c.key.split(':', 1)[0]}): {c.value}" for c in check.criteria if not c.passed]
                           or [f"limited to {', '.join(sites)} and seeded at {check.seed}: joiner {guarded.load(pid)} consults, busiest peer "
                               f"{max((guarded.load(x) for x in peers), default=0)}; waits at the gap hospitals "
                               f"{none.wait(sites):g} -> {guarded.wait(sites):g} patient-min",
                               f"unguarded, the joiner would take {check.spill['baseline']} consult(s) at hospitals the offer never named"],
                "seed_consults": check.seed, "limited_to": [{"hospital_id": h, "hospital_name": p.refs.hospitals[h].name} for h in sites],
                "steps": [c["at"] for c in cells], "without": [{"count": c["count"], "required": c["required"]} for c in cells],
                "with": [{"count": c["count"] + (1 if joined(c["at"]) else 0), "required": c["required"]} for c in cells],
                "joiner_load": guarded.load(pid), "busiest_peer_load": max((guarded.load(x) for x in peers), default=0),
                "other_gaps_worsened": guarded.wait(others) > none.wait(others),
                "assumption": "Router rules 1-5 replayed with a usual day's demand" + (f", today's observed pace ({check.pace:.2f} x usual)" if "todays_pace" in check.scenarios else "")
                              + (" and the current surge continuing" if "surge_continues" in check.scenarios else "") + "; every scenario must pass. Service time is today's median busy minutes per consult",
                "scenarios": runs_view(check, pid)}

    def offer_view(self, o):
        refs = self.coordinator.refs
        sent = next((m["body"] for m in self.desk.outbox() if m["offer_id"] == o.id and m["kind"] == "offer"), None)
        return {"offer_id": o.id, "gap_id": o.gap_id, "physician_id": o.physician_id,
                "physician_name": refs.physicians[o.physician_id].name if o.physician_id in refs.physicians else o.physician_id,
                "hospital_ids": list(o.hospitals), "hospital_names": [refs.hospitals[h].name for h in o.hospitals],
                "start": o.start.isoformat(), "end": o.end.isoformat(), "state": STATE_LABELS[o.state], "checked_count": len(self.ops.roster),
                "proposed_by": o.proposed_by, "proposed_at": o.created_at.isoformat(), "approved_by": o.approved_by,
                "approved_at": o.sent_at.isoformat() if o.approved_by and o.sent_at else None,  # approve and send are one transaction
                "sent_at": o.sent_at.isoformat() if o.sent_at else None, "expires_at": o.expires_at.isoformat() if o.expires_at else None,
                "responded_at": o.updated_at.isoformat() if o.state in {"ACCEPTED", "DECLINED", "ALREADY_FILLED"} else None,
                "message": sent, "audio_url": f"/offers/{o.id}/audio" if sent and self.speech_available else None, "phone_url": None,
                "reject_reason": o.reason if o.state == "REJECTED" else None, "reason": o.reason, "replaces": o.replaces}

    def audit_view(self, gap_id):
        items = []
        for a in self.desk.audit(gap_id):
            d = a["detail"]
            if a["command"].endswith(":refused"):
                text = d.get("message", "")
            elif a["command"] == "propose":
                text = f"{d.get('physician_id')} · {', '.join(d.get('hospitals', []))} · {d.get('start')} to {d.get('end')}"
            else:
                text = "; ".join(f"{k}: {v}" for k, v in d.items() if v not in (None, "", [], {}))
            items.append({"at": a["at"].isoformat(), "actor": a["actor"],
                          "action": ACTIONS.get(a["command"], a["command"].replace(":", ": ").replace("_", " ")), "detail": text,
                          "offer_id": a["offer_id"], "command": a["command"], "from_state": a["from_state"], "to_state": a["to_state"]})
        return {"items": items}

    def snapshot(self, epoch: str, clock_mode: str) -> dict:
        p, d = self.decisions()
        consults = [{"consult_id": c.consult_id, "hospital_id": c.hospital_id, "consult_type": c.consult_type, "physician_id": c.owner,
                     "current_stage": c.stage, "stage_entered_at": c.entered_at.isoformat(),
                     "minutes_in_stage": max(0, int((p.as_of - c.entered_at).total_seconds() // 60)),
                     "minutes_since_received": max(0, int((p.as_of - c.received_at).total_seconds() // 60)),
                     "repeat_contacts": c.repeat_contacts, "routing_failures": c.routing_failures}
                    for c in p.state.consults.values() if c.stage != "Signed Off"]
        body = {"revision": p.revision, "reference_revision": p.reference_revision, "clock_revision": 0, "epoch": epoch, "sequence": p.revision,
                "clock": {"mode": clock_mode, "now": p.as_of.isoformat(), "paused": clock_mode == "fixed"}, "consults": consults,
                "data_quality": data_quality_view(p),
                "capabilities": {"orphan_holding": True, "reference_validation": p.refs is not None, "physician_state": d is not None, "detection": d is not None}}
        if d is None:
            return {**body, "headline": {"open_consults": len(consults)}, "physicians": {"supported": False, "items": []},
                    "hospitals": {"supported": False, "items": []}, "queue": {"supported": False, "items": []}, "coverage": {"supported": False},
                    "forecast": {"supported": False}, "demand": {"supported": False}, "workload": {"supported": False},
                    "offers": {"supported": False, "items": []}, "dataset": self.dataset, "pending_approvals": 0}
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
                "forecast": {"supported": True, "gaps": [{"id": g.id, "hospital_id": g.hospital_id, "kind": g.kind, "start": g.start.isoformat(),
                                                          "end": g.end.isoformat(), "required": g.required, "confirmed": g.confirmed,
                                                          "scheduled": g.scheduled, "surge": g.surge, "in_horizon": g.in_horizon,
                                                          "causes": list(g.causes)} for g in d.gaps],
                             "surges": [{"hospital_id": s.hospital_id, "count": s.count, "p90": s.p90, "until": s.until.isoformat()} for s in d.surges]},
                "offers": {"supported": True, "items": [self.offer_view(o) for o in offers]},
                "coverage": self.coverage_grid(p, d, coverage), "demand": demand_view(p, coverage), "workload": workload_view(p, d),
                "dataset": self.dataset,
                "pending_approvals": sum(o.state == "PROPOSED" for o in offers) + len(self.interventions.pending())}


# ---- views in the shapes the web screens render (docs/Web-Joy.md) --------------------------------------------
STEP = timedelta(minutes=15)
STATE_LABELS = {"PROPOSED": "Proposed", "APPROVED": "Approved", "REJECTED": "Rejected", "SENT": "Sent", "CANCELLED": "Cancelled",
                "ACCEPTED": "Accepted", "ALREADY_FILLED": "Already filled", "DECLINED": "Declined", "EXPIRED": "Expired", "WITHDRAWN": "Withdrawn"}
RULE_CODES = {"off_shift_now": "Off", "opted_in": "R1", "credentialed_at_gap": "R2", "rest_at_start_at_least_10h": "R3",
              "trailing7d_plus_offer_at_most_60h": "R4", "no_schedule_overlap": "R5", "nominal_duration_at_least_2h": "R6",
              "useful_duration_at_least_2h": "R6b", "no_open_offer": "R7", "weekly_offer_count_below_3": "R8", "start_not_in_past": "Start"}
ACTIONS = {"propose": "Proposed offer", "approve": "Approved offer", "send": "Sent offer", "reject": "Rejected offer", "accept": "Accepted offer",
           "decline": "Declined offer", "expire": "Offer expired", "withdraw": "Offer withdrawn (gap filled)", "cancel": "Offer cancelled",
           "accept:already_filled": "Accepted, but the gap was already filled", "approve:recheck_failed": "Cancelled at approval: a rule no longer passes",
           "next_candidate:none": "No other eligible physician: escalate", "reassign": "Reassignment recorded", "escalate": "Escalation requested",
           "authorize": "Escalation authorized", "reset": "Reset"}


def data_quality_view(p):
    st = dict(p.stats)
    return {"supported": True, "events_read": st.get("accepted", 0) + st.get("duplicates", 0) + st.get("conflicts", 0) + st.get("rejected", 0),
            "accepted": st.get("accepted", 0), "duplicates": st.get("duplicates", 0), "conflicts": st.get("conflicts", 0),
            "reordered": st.get("reordered", 0), "late": st.get("late", 0), "max_reorder_lag_s": st.get("max_reorder_lag_s", 0),
            "max_delivery_lag_s": st.get("max_delivery_lag_s", 0), "rejected": st.get("rejected", 0), "pending_orphans": p.held_orphans,
            "expired_orphans": st.get("expired_orphans", 0), "accepted_events": p.event_count}


def demand_view(p, coverage):
    return {"supported": True, "items": [{"hospital_id": c.hospital_id, "hospital_name": p.refs.hospitals[c.hospital_id].name,
                                          "trailing_60m": c.trailing_60m, "p90": c.p90,
                                          "status": "unknown" if c.surge is None else "surge" if c.surge else "normal"} for c in coverage]}


def workload_view(p, d):
    """On-shift physicians, riskiest first. Shift-end risk follows the open-notes rule (2+ notes Critical, 1 Warning, within 60 min)."""
    items = []
    for v in d.views.values():
        if "off_shift" in v.exclusion_reasons:
            continue
        notes = sum(c.owner == v.physician_id and c.stage in NOTE_STAGES for c in p.state.consults.values())
        soon = v.minutes_to_shift_end is not None and v.minutes_to_shift_end <= 60
        risk = ("Critical" if notes >= 2 else "Warning" if notes else None) if soon else None
        shift = next((s for s in p.refs.physicians[v.physician_id].shifts if s.start <= p.as_of < s.end), None)
        reason = (f"{notes} open note(s), shift ends in {v.minutes_to_shift_end} min" if risk else v.derived_state
                  + (f" ({', '.join(v.exclusion_reasons)})" if v.exclusion_reasons else ""))
        items.append({"physician_id": v.physician_id, "name": p.refs.physicians[v.physician_id].name, "consults": v.consults_this_shift,
                      "calls": v.calls_this_shift, "open_consults": v.open_consults, "shift_end": shift.end.isoformat() if shift else None,
                      "minutes_to_shift_end": v.minutes_to_shift_end, "overload": None, "shift_end_risk": risk, "open_notes": notes, "reason": reason})
    order = {"Critical": 0, "Warning": 1, None: 2}
    items.sort(key=lambda i: (order[i["shift_end_risk"]], i["minutes_to_shift_end"] if i["minutes_to_shift_end"] is not None else 10**6, i["physician_id"]))
    return {"supported": True, "items": items}
