"""Step 9: the engine behind the API. Builds decisions from the live publication and serializes them for clients.

Clients only display what this returns; every level, gap, candidate and fix is computed here [00-Boundaries].
"""
from dataclasses import asdict, dataclass, field
import hashlib
import json
from datetime import date, datetime, time, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Lock
from app.act.interventions import InterventionLog
from app.act.offers import OPEN, Context, OfferDesk
from app.decide.eligibility import OfferHistory, Proposal, evaluate, evaluate_proposal, load_offer_history, ranked_above
from app.decide.interventions import Decisions, decide
from app.decide.routing_sim import observed_service, trap_check
from app.ops.coverage import HORIZON, current_coverage, forecast_steps, outlook_end, supply, surge_at, _received
from app.ops.detect import NOTE_STAGES, UNASSIGNED_STAGES, consult_sla, sla_limit
from app.ops.refs import ET, OpsRefs, load_ops_refs
from app.ops.overload import overloads
from app.ops.demand import expected_arrivals
from app.references import Refs, load_reference_dir


def load_references(directory: str | Path, service_date: date | None = None) -> tuple[Refs, OpsRefs]:
    refs = load_reference_dir(directory, service_date)
    return refs, load_ops_refs(directory, {h: x.timezone for h, x in refs.hospitals.items()}, set(refs.physicians))


REFERENCE_FILES = ("hospitals.csv", "physicians_on_shift.csv", "physicians_off_shift_roster.csv", "credentialing_matrix.csv",
                   "baseline_hourly_volume.csv", "coverage_requirements.csv")


def reference_manifest(source):
    """Exact uploaded CSV text plus service date identify the reference version; labels do not."""
    content = {"files": source["files"], "service_date": source.get("service_date")}
    encoded = json.dumps(content, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return {"fingerprint": hashlib.sha256(encoded).hexdigest(), "service_date": content["service_date"],
            "files": {name: hashlib.sha256(text.encode("utf-8")).hexdigest() for name, text in sorted(content["files"].items())}}


def dataset_label(source):
    return {"name": source["name"], "description": "uploaded reference files", "reference_files": len(source["files"]),
            "fingerprint": reference_manifest(source)["fingerprint"]}


def same_files(a: dict, b: dict) -> bool:
    """The same CSVs, ignoring a byte-order mark, line endings and trailing blank lines (as a browser may save them)."""
    text = lambda files: {name: body.lstrip("\ufeff").replace("\r\n", "\n").strip() for name, body in files.items()}
    return text(a) == text(b)


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


def readable(value):
    """Audit detail for people: times as Eastern HH:MM, mappings as "key value" pairs, lists comma-separated."""
    if isinstance(value, dict):
        return ", ".join(f"{k} {readable(v)}" for k, v in value.items())
    if isinstance(value, (list, tuple)):
        return ", ".join(map(readable, value))
    if isinstance(value, str):
        try:
            moment = datetime.fromisoformat(value)
        except ValueError:
            return value
        return f"{moment.astimezone(ET):%H:%M}" if moment.tzinfo else value
    return str(value)


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


def kit_start(day: date) -> datetime:
    """18:20 Eastern on a kit's service date: the sample's as-of time, where a switched or reset clock waits, paused."""
    return datetime.combine(day, time(18, 20), ET)


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

    def use_references(self, refs: Refs, ops: OpsRefs, source: dict) -> dict:
        """Bootstrap the first kit. Once one is active, an identical upload changes nothing and a different kit is
        stored beside it, never replacing it: only an event upload for that kit switches to it (see `ingest_upload`)."""
        with self.swap:
            previous = (self.coordinator.db.metadata("references") or {}).get("source")
            if self.coordinator.refs is not None:
                if refs != self.coordinator.refs or ops != self.ops or (previous and
                        reference_manifest(previous)["fingerprint"] != reference_manifest(source)["fingerprint"]):
                    self.store_kit(refs, source)
                    return {"stored": True, "revision": self.coordinator.published.revision}
                if previous:
                    return {"unchanged": True, "revision": self.coordinator.published.revision}
            report = self.coordinator.activate_references(refs, source)
            self.store_kit(refs, source)
            self.ops, self.dataset = ops, dataset_label(source)
        return report

    def stored_kits(self) -> dict:
        """Reference kits by fingerprint. Content-addressed, so a stored kit (the official one included) never changes."""
        return self.coordinator.db.metadata("reference_kits") or {}

    def store_kit(self, refs: Refs, source: dict):
        kits = self.stored_kits()
        fingerprint = reference_manifest(source)["fingerprint"]
        if fingerprint not in kits:
            kits[fingerprint] = {"source": source, "hospital_ids": sorted(refs.hospitals), "physician_ids": sorted(refs.physicians)}
            self.coordinator.db.set_metadata("reference_kits", kits)

    def stored_service_date(self, files: dict) -> date | None:
        """The service date a stored copy of these CSVs was given, so the same kit can be uploaded again without one."""
        return next((date.fromisoformat(kit["source"]["service_date"]) for _, kit in sorted(self.stored_kits().items())
                     if kit["source"].get("service_date") and same_files(kit["source"]["files"], files)), None)

    def switch_kit(self, fingerprint: str, actor: str) -> datetime | None:
        """Make a stored kit active with a fresh, empty stream: offers and interventions start empty. Returns the
        kit's start time, 18:20 Eastern on its service date (the sample's as-of time), or None for a dated layout."""
        kit = self.stored_kits().get(fingerprint)
        if kit is None:
            raise KeyError(fingerprint)
        source = kit["source"]
        day = date.fromisoformat(source["service_date"]) if source.get("service_date") else None
        with self.desk.lock, self.swap:  # the desk lock first, as in ingest_upload
            refs, ops = references_from_files(source["files"], day)
            self.coordinator.ingest_raw([], refs=refs, source=source)
            self.ops, self.dataset = ops, dataset_label(source)
            self.desk.reset(actor, self.coordinator.clock.now())
            self.interventions.reset()
        return kit_start(day) if day else None

    def _kit_for(self, hospital_ids: set, physician_ids: set) -> dict | None:
        """The stored kit an events-only file belongs to, or None to append to the active kit. A file that shares any
        ID with the active kit appends as usual (unknown IDs then take the G4 hold); one that shares none must match
        exactly one stored kit."""
        refs = self.coordinator.refs
        if refs is None or not (hospital_ids or physician_ids) or hospital_ids & set(refs.hospitals) or physician_ids & set(refs.physicians):
            return None
        matches = [kit["source"] for _, kit in sorted(self.stored_kits().items())
                   if hospital_ids <= set(kit["hospital_ids"]) and physician_ids <= set(kit["physician_ids"])]
        # The same CSVs saved with other line endings (or without a service date) are one kit stored twice: use the dated copy.
        text = lambda kit: {name: body.lstrip("﻿").replace("\r\n", "\n").strip() for name, body in kit["files"].items()}
        if len(matches) > 1 and all(text(m) == text(matches[0]) for m in matches) and \
                len({m.get("service_date") for m in matches} - {None}) <= 1:
            matches = [next((m for m in matches if m.get("service_date")), matches[0])]
        if len(matches) == 1:
            return matches[0]
        listed = lambda ids: ", ".join(sorted(ids)[:5]) + (f" and {len(ids) - 5} more" if len(ids) > 5 else "")
        found = (f"hospitals {listed(hospital_ids)}" if hospital_ids else "") + (" and " if hospital_ids and physician_ids else "") + \
                (f"physicians {listed(physician_ids)}" if physician_ids else "")
        if matches:
            raise ValueError(f"This file's {found} match more than one stored reference kit ({', '.join(m['name'] for m in matches)}). Nothing was added.")
        raise ValueError(f"This file's {found} are not in the active reference kit ({self.dataset.get('name', 'unnamed')}) or any stored kit. "
                         "Store that dataset's six reference files first. Nothing was added.")

    def ingest_upload(self, rows: list[dict], adapter: str, upload: dict, actor: str, advance_clock=False) -> dict:
        """Append an events-only CSV, or, when its IDs belong to another stored kit, switch to that kit with a fresh
        stream: the kit, the new generation and the events commit together; offers and interventions start empty."""
        ids = lambda column: {(row.get(column) or "").strip() for row in rows} - {""}
        # The desk lock first: a desk command holds it while it reads the context (swap), so the reverse order deadlocks.
        with self.desk.lock, self.swap:
            source = self._kit_for(ids("hospital_id"), ids("physician_id"))
            if source is None:
                return self.coordinator.ingest_raw(rows, adapter, advance_clock=advance_clock, upload=upload)
            refs, ops = references_from_files(source["files"], date.fromisoformat(source["service_date"]) if source.get("service_date") else None)
            fingerprint = reference_manifest(source)["fingerprint"]
            report = self.coordinator.ingest_raw(rows, adapter, upload={**upload, "reference_fingerprint": fingerprint}, refs=refs, source=source)
            self.ops, self.dataset = ops, dataset_label(source)
            self.desk.reset(actor, self.coordinator.clock.now())
            self.interventions.reset()
        return {**report, "dataset_switched_to": {"name": source["name"], "fingerprint": fingerprint}}

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
            recommendations = []
            for rank, item in enumerate(decisions.items, 1):
                hospitals = item.where.get("hospital_ids") or [item.where.get("hospital_id")]
                recommendations.append({**item_payload(rank, item),
                                        "candidates": [{**asdict(c), "eligible": c.eligible} for c in item.candidates],
                                        "gaps": [asdict(g) for g in decisions.gaps if g.hospital_id in hospitals]})
            self.desk.record_decisions(Context(p.state, p.refs, ops, p.as_of, p.revision), recommendations)
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
                "unknown_demand": list(check.unknown_demand),
                "trap_shown_unguarded": check.trap_shown, "wait_minutes_removed": dict(check.relief), "unguarded_spill": dict(check.spill),
                "criteria": [{"key": c.key, "passed": c.passed, "value": c.value} for c in check.criteria],
                "scenarios": runs_view(check, best.physician_id)}

    def coverage_grid(self, p, d, coverage):
        """Now, then 15-minute observations and exact shift cliffs across the shared display horizon."""
        steps = forecast_steps(p.refs, self.ops, p.as_of, self.desk.accepted())
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
        return {"supported": True, "steps": [t.isoformat() for t in steps], "horizon_end": steps[-1].isoformat(), "hospitals": hospitals,
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
        if gap is None and item is None and offer is not None and len(offer.hospitals) == 1:
            gap = next((g for g in d.gaps if g.kind == "hard" and g.hospital_id in offer.hospitals
                        and g.start < offer.end and max(offer.start, p.as_of) < g.end), None)
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
        summary = (item.what if item else f"{', '.join(p.refs.hospitals[h].name for h in hospitals)} coverage under review") + (
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
        history = self.desk.history(p.as_of)
        rules = [{"id": RULE_CODES.get(r.key, r.key), "label": r.label} for r in g["candidates"][0].rules] if g["candidates"] else []
        out = []
        for c in g["candidates"]:
            roster = self.ops.roster[c.physician_id]
            failed = [r for r in c.rules if not r.passed]
            out.append({"physician_id": c.physician_id, "name": p.refs.physicians[c.physician_id].name if c.physician_id in p.refs.physicians else c.physician_id,
                        "eligible": c.eligible, "rank": ranked.index(c) + 1 if c.eligible else None,
                        "primary_reason": f"{failed[0].label}: {failed[0].value}" if failed else ("low value: covers under 60 gap minutes" if c.low_value else None),
                        "results": [{"rule": RULE_CODES.get(r.key, r.key), "status": "pass" if r.passed else "fail", "explanation": r.value} for r in c.rules],
                        "ranking": {"gap_hospitals": len(c.hospitals), "covered_minutes": c.covered_minutes, "minutes_to_online": roster.minutes_to_online,
                                    "declines_30d": roster.declines_30d, "hours_7d": roster.hours_last_7d, "offers_7d": history.sent_7d.get(c.physician_id, 0)},
                        # The first ranking step that separates this physician from the one ranked just above (or below, for #1).
                        "rank_reason": (None if not c.eligible or len(ranked) < 2 else
                                        f"ranked above {ranked[1].physician_id}: {ranked_above(c, ranked[1], self.ops, history)}" if c is ranked[0] else
                                        f"ranked below {ranked[ranked.index(c) - 1].physician_id}, who {ranked_above(ranked[ranked.index(c) - 1], c, self.ops, history)}"),
                        "window": {"start": c.start.isoformat(), "end": c.end.isoformat(), "ready_at": c.ready_at.isoformat(), "hospitals": list(c.hospitals)}})
        fix = g["item"].fix if g["item"] else None
        return {"gap": g["view"], "revision": g["revision"], "rules": rules, "candidates": out, "server_now": p.as_of.isoformat(),
                "fix": {"kind": fix.kind, "action": fix.action, "reason": fix.reason, "physician_id": fix.physician_id} if fix else None}

    def trap_view(self, gap_id):
        result = self._trap_view(gap_id)
        return {**result, "server_now": self.context().now.isoformat()} if result is not None else None

    def _trap_view(self, gap_id):
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
                "unknown_demand": list(check.unknown_demand),
                "reasons": (["trap check unknown: missing hourly demand for " + ", ".join(check.unknown_demand) + "; simulation results are partial"] if check.unknown_demand else [])
                           + [f"{c.key.split(':', 1)[1].replace('_', ' ')} ({c.key.split(':', 1)[0]}): {c.value}" for c in check.criteria if not c.passed]
                           or [f"limited to {', '.join(sites)} and seeded at {check.seed}: joiner {guarded.load(pid)} consults, busiest peer "
                               f"{max((guarded.load(x) for x in peers), default=0)}; waits at the gap hospitals "
                               f"{none.wait(sites):g} -> {guarded.wait(sites):g} patient-min",
                               f"unguarded, the joiner would take {check.spill['baseline']} consult(s) at hospitals the offer never named"],
                "seed_consults": check.seed, "limited_to": [{"hospital_id": h, "hospital_name": p.refs.hospitals[h].name} for h in sites],
                "steps": [c["at"] for c in cells], "without": [{"count": c["count"], "required": c["required"]} for c in cells],
                "with": [{"count": c["count"] + (1 if joined(c["at"]) else 0), "required": c["required"]} for c in cells],
                "joiner_load": guarded.load(pid), "busiest_peer_load": max((guarded.load(x) for x in peers), default=0),
                "other_gaps_worsened": guarded.wait(others) > none.wait(others),
                "assumption": ("Partial demand model; full trap verdict unknown. " if check.unknown_demand else "") + "Router rules 1-5 replayed with a usual day's demand" + (f", today's observed pace ({check.pace:.2f} x usual)" if "todays_pace" in check.scenarios else "")
                              + (" and the current surge continuing" if "surge_continues" in check.scenarios else "") + "; every scenario must pass. Service time is today's median busy minutes per consult",
                "scenarios": runs_view(check, pid)}

    def my_shift(self, physician_id: str) -> dict:
        """The physician's own screen: the shift they are on now (scheduled, or an accepted split shift), the hospitals it
        covers and only the consults they own. Nothing about other physicians or patients beyond their own consult rows."""
        p, ops = self._current()
        refs, now = p.refs, p.as_of
        shift = next(((s.start, s.end, refs.credentials.get(physician_id, frozenset())) for s in refs.physicians[physician_id].shifts
                      if s.start <= now < s.end), None) if refs and physician_id in refs.physicians else None
        if shift is None:
            shift = next(((s.start, s.end, s.hospitals) for s in self.desk.accepted() if s.physician_id == physician_id and s.start <= now < s.end), None)
        names = {h: x.name for h, x in refs.hospitals.items()} if refs else {}
        _, decisions = self.decisions()
        view = decisions.views.get(physician_id) if decisions else None
        mine = sorted((c for c in p.state.consults.values() if c.owner == physician_id and c.stage != "Signed Off"), key=lambda c: c.received_at)
        return {"name": refs.physicians[physician_id].name if refs and physician_id in refs.physicians else physician_id,
                "server_now": now.isoformat(), "clock_mode": self.coordinator.clock.mode,
                "on_shift": bool(view and view.shift), "shift_start": shift[0].isoformat() if shift else None,
                "consults_this_shift": view.consults_this_shift if view else None,
                "calls_this_shift": view.calls_this_shift if view else None,
                "shift_end": shift[1].isoformat() if shift else None,
                "minutes_to_shift_end": int((shift[1] - now).total_seconds() // 60) if shift else None,
                "hospitals": [names.get(h, h) for h in sorted(shift[2])] if shift else [],
                "consults": [{"consult_id": c.consult_id, "hospital_name": names.get(c.hospital_id, c.hospital_id), "consult_type": c.consult_type,
                              "stage": c.stage, "level": consult_sla(c, now)[0],
                              "minutes_in_stage": max(0, int((now - c.entered_at).total_seconds() // 60))} for c in mine]}

    def offer_view(self, o):
        refs = self.coordinator.refs
        sent = next((m["body"] for m in self.desk.outbox() if m["offer_id"] == o.id and m["kind"] == "offer"), None)
        return {"offer_id": o.id, "gap_id": o.gap_id, "physician_id": o.physician_id,
                "server_now": self.context().now.isoformat(), "clock_mode": self.coordinator.clock.mode,
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
        for a in self.desk.audit(gap_id, limit=AUDIT_ROWS):
            d = a["detail"]
            if a["command"].endswith(":refused"):
                text = d.get("message", "")
            elif a["command"] == "propose":
                text = f"{d.get('physician_id')} · {', '.join(d.get('hospitals', []))} · {readable(d.get('start'))} to {readable(d.get('end'))} ET"
            elif a["command"] == "recommendation":
                text = f"{d['what']}. {d['fix']['action']}"
            else:
                text = "; ".join(f"{k.replace('_', ' ')}: {readable(v)}" for k, v in d.items()
                                 if k not in {"decision", "final_coverage"} and v not in (None, "", [], {}))
            items.append({"at": a["at"].isoformat(), "actor": a["actor"],
                          "action": ACTIONS.get(a["command"], a["command"].replace(":", ": ").replace("_", " ")), "detail": text,
                          "offer_id": a["offer_id"], "gap_id": a["gap_id"], "revision": a["revision"], "evidence": jsonable(d),
                          "command": a["command"], "from_state": a["from_state"], "to_state": a["to_state"]})
        return {"items": items, "server_now": self.context().now.isoformat()}

    def schedule_view(self):
        """Joy's roster labels with observed shift membership and explicit complete intervals."""
        p, d = self.decisions()
        now = p.as_of.astimezone(ET)
        offers, accepted = self.desk.offers(), self.desk.accepted()
        doctors = []
        label = lambda t: t.astimezone(ET).strftime("%H:%M")
        offer_labels = {"PROPOSED": "Waiting for clinical lead approval", "APPROVED": "Approved; awaiting send",
                        "SENT": "Waiting for physician reply"}
        for pid, physician in sorted(p.refs.physicians.items()):
            v, roster = d.views[pid], self.ops.roster.get(pid)
            shifts = [(s.start, s.end, "scheduled") for s in physician.shifts]
            shifts += [(s.start, s.end, "accepted") for s in accepted if s.physician_id == pid]
            if roster and roster.next_shift_start and roster.next_shift_end and not any(s[0] == roster.next_shift_start for s in shifts):
                shifts.append((roster.next_shift_start, roster.next_shift_end, "roster"))
            shifts.sort()
            current = next((s for s in shifts if s[0] <= p.as_of < s[1]), None)
            upcoming = next((s for s in shifts if p.as_of < s[0] and s[0].astimezone(ET).date() == now.date()), None)
            interval = current or upcoming
            pending = next((o for o in offers if o.physician_id == pid and o.state in OPEN), None)
            on = "off_shift" not in v.exclusion_reasons
            bar = f"{label(interval[0])} to {label(interval[1])}" if interval else "Off today"
            detail = f"{interval[2].capitalize()} {bar} ET" if interval else "No complete upcoming interval"
            tone = "night" if interval and (interval[0].astimezone(ET).hour >= 18 or interval[1].astimezone(ET).date() > interval[0].astimezone(ET).date()) else "day" if interval else "off"
            status = v.derived_state if on else "Off shift"
            if current and current[2] == "accepted" and not on:
                status = "Accepted; awaiting observed arrival"
            elif on and v.minutes_to_shift_end is not None and v.minutes_to_shift_end <= 60:
                detail = f"Shift ends in {v.minutes_to_shift_end} min"
            elif not on and not interval and roster:
                start = roster.next_shift_start
                opted = "Opted into extra shifts" if roster.opt_in else "Not opted into extra shifts"
                if start and start.astimezone(ET).date() == now.date():
                    bar = f"{roster.role} · from {label(start)}"
                    tone = "night" if roster.role == "Night" or start.astimezone(ET).hour >= 18 else "day"
                    status = f"{'Starts' if start > p.as_of else 'Scheduled from'} {label(start)}"
                else:
                    status = f"Next shift {start.astimezone(ET):%a %H:%M}" if start and start > p.as_of else "No upcoming shift"
                detail = opted
            if roster and roster.next_shift_start and roster.next_shift_end is None:
                detail += f"; next start {roster.next_shift_start.astimezone(ET):%d %b %H:%M} ET, end unknown"
            if v.derived_state == "Temporarily Unavailable":
                tone = "unavailable"
            if pending:
                tone, bar = "offer", f"{label(pending.start)} to {label(pending.end)}"
                detail = offer_labels.get(pending.state, STATE_LABELS[pending.state]) + "; not confirmed"
                status = f"{status}; offer {STATE_LABELS[pending.state].lower()}"
            creds = sorted(v.credentialed_hospitals)
            workload = f"{roster.hours_last_7d:g} h in last 7 days" if roster and not on else f"{v.consults_this_shift} consults · {v.calls_this_shift} calls this shift · {v.open_consults} open"
            doctors.append({"id": pid, "name": physician.name, "group": "On shift" if on else "Off shift", "status": status,
                            "bar": bar, "tone": tone, "detail": detail,
                            "avatar": "".join(word[0] for word in physician.name.replace("Dr.", "").split())[:2],
                            "workload": workload,
                            "credentialed": f"{len(creds)} hospitals: " + ", ".join(p.refs.hospitals[h].name for h in creds),
                            "intervals": [{"start": start.isoformat(), "end": end.isoformat(), "source": source} for start, end, source in shifts]})
        filters = [{"label": "Everyone", "ids": [r["id"] for r in doctors]},
                   {"label": "On shift", "ids": [r["id"] for r in doctors if r["group"] == "On shift"]},
                   {"label": "Off shift", "ids": [r["id"] for r in doctors if r["group"] == "Off shift"]}]
        filters += [{"label": f"Credentialed at {h.name}", "ids": [pid for pid in sorted(p.refs.physicians) if hid in p.refs.credentials[pid]]}
                    for hid, h in sorted(p.refs.hospitals.items())]
        waiting = min((o for o in offers if o.state in OPEN), key=lambda o: (o.start, o.id), default=None)
        alert = ({"text": f"{p.refs.physicians[waiting.physician_id].name}'s offer: {offer_labels.get(waiting.state, STATE_LABELS[waiting.state])}.",
                  "physician_id": waiting.physician_id} if waiting else None)
        return {"date": now.date().isoformat(), "date_label": f"{now:%A} {now.day} {now:%B}", "now_label": now.strftime("%H:%M"),
                "server_now": p.as_of.isoformat(), "revision": p.revision, "alert": alert, "filters": filters, "doctors": doctors}

    def snapshot(self, epoch: str, clock_mode: str) -> dict:
        p, d = self.decisions()
        consults = [{"consult_id": c.consult_id, "hospital_id": c.hospital_id, "consult_type": c.consult_type, "physician_id": c.owner,
                     "current_stage": c.stage, "stage_entered_at": c.entered_at.isoformat(),
                     "minutes_in_stage": max(0, int((p.as_of - c.entered_at).total_seconds() // 60)),
                     "minutes_since_received": max(0, int((p.as_of - c.received_at).total_seconds() // 60)),
                     "repeat_contacts": c.repeat_contacts, "routing_failures": c.routing_failures,
                     # Each consult's own level, so a board never infers it from the queue (notes are grouped per physician there).
                     "level": consult_sla(c, p.as_of)[0], "limit_min": list(sla_limit(c)) if sla_limit(c) else None,
                     "measured_min": int(consult_sla(c, p.as_of)[1].total_seconds() // 60)}
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
        coverage_display = self.coverage_grid(p, d, coverage)
        horizon_end = datetime.fromisoformat(coverage_display["horizon_end"])
        open_states = [c for c in p.state.consults.values() if c.stage != "Signed Off"]
        short_now = {c.hospital_id for c in coverage if c.gap}
        overload = overloads(p.state, d.views, p.as_of)
        return {**body,
                "headline": {"open_consults": len(consults), "critical": sum(i.severity == "Critical" for i in d.items),
                             "overloaded_physicians": sum(x["level"] is not None for x in overload.values()),
                             "hard_gaps_in_horizon": sum(g.kind == "hard" and g.in_horizon for g in d.gaps),
                             # The PRD's headline numbers [PRD: headline numbers]. Short now = by live signals; in the
                             # horizon = short now or a schedule gap within the displayed horizon, including its final cliff.
                             "consults_past_critical": sum(consult_sla(c, p.as_of)[0] == "Critical" for c in open_states),
                             "unassigned_consults": sum(c.stage in UNASSIGNED_STAGES and c.owner == "Unassigned" for c in open_states),
                             "hospitals_short_now": len(short_now),
                             "hospitals_short_in_horizon": len(short_now | {g.hospital_id for g in d.gaps if g.kind == "hard" and g.in_horizon}),
                             "forecast_horizon_minutes": int((horizon_end-p.as_of).total_seconds()/60),
                             "offers_awaiting_approval": sum(o.state == "PROPOSED" for o in offers), "offers_out": sum(o.state == "SENT" for o in offers)},
                "queue": {"supported": True, "items": [item_payload(n, i, done.get(i.id)) for n, i in enumerate(d.items, 1)]},
                "physicians": {"supported": True, "items": [{"physician_id": v.physician_id, "name": p.refs.physicians[v.physician_id].name,
                                                             "derived_state": v.derived_state,
                                                             "self_reported_status": v.self_reported_status, "desktop_agent": v.desktop_agent,
                                                             "routable": v.routable, "exclusion_reasons": list(v.exclusion_reasons), "flags": list(v.flags),
                                                             "consults_this_shift": v.consults_this_shift, "open_consults": v.open_consults,
                                                             "minutes_to_shift_end": v.minutes_to_shift_end,
                                                             "credentialed_hospitals": sorted(v.credentialed_hospitals),
                                                             "routing_hospitals": sorted(v.allowed_hospitals)} for v in d.views.values()]},
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
                "coverage": coverage_display, "demand": demand_view(p, coverage, self.ops, horizon_end), "workload": workload_view(p, d),
                "dataset": self.dataset,
                "pending_approvals": sum(o.state == "PROPOSED" for o in offers) + len(self.interventions.pending())}


# ---- views in the shapes the web screens render (docs/Web-Joy.md) --------------------------------------------
STEP = timedelta(minutes=15)
AUDIT_ROWS = 300  # the newest rows only: the whole log (a recommendation pass per decision change) outgrows a small host's memory
STATE_LABELS = {"PROPOSED": "Proposed", "APPROVED": "Approved", "REJECTED": "Rejected", "SENT": "Sent", "CANCELLED": "Cancelled",
                "ACCEPTED": "Accepted", "ALREADY_FILLED": "Already filled", "DECLINED": "Declined", "EXPIRED": "Expired", "WITHDRAWN": "Withdrawn"}
RULE_CODES = {"off_shift_now": "Off", "opted_in": "R1", "credentialed_at_gap": "R2", "rest_at_start_at_least_10h": "R3",
              "trailing7d_plus_offer_at_most_60h": "R4", "no_schedule_overlap": "R5", "nominal_duration_at_least_2h": "R6",
              "useful_duration_at_least_2h": "R6b", "no_open_offer": "R7", "weekly_offer_count_below_3": "R8", "start_not_in_past": "Start"}
ACTIONS = {"recommendation": "Recommended action", "propose": "Proposed offer", "approve": "Approved offer", "send": "Sent offer", "reject": "Rejected offer", "accept": "Accepted offer",
           "decline": "Declined offer", "expire": "Offer expired", "withdraw": "Offer withdrawn (gap filled)", "cancel": "Offer cancelled",
           "accept:already_filled": "Accepted, but the gap was already filled", "approve:recheck_failed": "Cancelled at approval: a rule no longer passes",
           "next_candidate:none": "No other eligible physician: escalate", "reassign": "Reassignment recorded", "escalate": "Escalation requested",
           "authorize": "Escalation authorized", "reset": "Reset"}


def data_quality_view(p):
    st = dict(p.stats)
    return {"supported": True, "events_read": st.get("rows_received", 0), "counts_exact": st.get("counts_exact", False),
            "accepted": st.get("accepted", 0), "duplicates": st.get("duplicates", 0), "conflicts": st.get("conflicts", 0),
            "reordered": st.get("reordered", 0), "late": st.get("late", 0), "max_reorder_lag_s": st.get("max_reorder_lag_s", 0),
            "max_delivery_lag_s": st.get("max_delivery_lag_s", 0), "rejected": st.get("rejected", 0), "pending_orphans": p.held_orphans,
            "expired_orphans": st.get("expired_orphans", 0), "accepted_events": p.event_count}


def demand_view(p, coverage, ops, horizon_end):
    return {"supported": True, "horizon_end": horizon_end.isoformat(),
            "horizon_minutes": (horizon_end - p.as_of).total_seconds() / 60,
            "assumption": "Expected arrivals integrate hourly reference means over the coverage horizon. They are a baseline scenario, not a surge probability or future events. Missing hours remain unknown.",
            "items": [{"hospital_id": c.hospital_id, "hospital_name": p.refs.hospitals[c.hospital_id].name,
                       "trailing_60m": c.trailing_60m, "p90": c.p90,
                       "mean_per_hour": ops.mean(c.hospital_id, p.as_of),
                       "baseline_hour": ops.local(c.hospital_id, p.as_of).replace(minute=0,second=0,microsecond=0).isoformat(),
                       "baseline_timezone": ops.zones.get(c.hospital_id, "America/New_York"),
                       "expected_arrivals": expected_arrivals(ops, c.hospital_id, p.as_of, horizon_end),
                       "status": "unknown" if c.surge is None else "surge" if c.surge else "normal"} for c in coverage]}


def workload_view(p, d):
    """On-shift physicians, sorted by the higher of overload and exact-window open-note risk."""
    items = []
    overload = overloads(p.state, d.views, p.as_of)
    for v in d.views.values():
        if "off_shift" in v.exclusion_reasons:
            continue
        notes = sum(c.owner == v.physician_id and c.stage in NOTE_STAGES for c in p.state.consults.values())
        soon = v.shift is not None and timedelta(0) < v.shift.end - p.as_of <= timedelta(minutes=60)
        risk = ("Critical" if notes >= 2 else "Warning" if notes else None) if soon else None
        shift = v.shift
        reason = ("; ".join(overload[v.physician_id]["reasons"]) if overload[v.physician_id]["level"] else
                  f"{notes} open note(s), shift ends in {v.minutes_to_shift_end} min" if risk else v.derived_state
                  + (f" ({', '.join(v.exclusion_reasons)})" if v.exclusion_reasons else ""))
        items.append({"physician_id": v.physician_id, "name": p.refs.physicians[v.physician_id].name, "consults": v.consults_this_shift,
                      "calls": v.calls_this_shift, "open_consults": v.open_consults, "shift_end": shift.end.isoformat() if shift else None,
                      "minutes_to_shift_end": v.minutes_to_shift_end, "overload": overload[v.physician_id]["level"],
                      "overload_evidence": overload[v.physician_id], "shift_end_risk": risk, "open_notes": notes, "reason": reason})
    order = {"Critical": 0, "Warning": 1, None: 2}
    items.sort(key=lambda i: (min(order[i["shift_end_risk"]], order[i["overload"]]), i["minutes_to_shift_end"] if i["minutes_to_shift_end"] is not None else 10**6, i["physician_id"]))
    return {"supported": True, "items": items}
