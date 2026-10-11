"""G15/G16: choose the cheapest safe fix per problem, name the approver and rank the queue. Pure."""
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from app.decide.eligibility import Candidate, OfferHistory, Proposal, evaluate, evaluate_proposal, ranked_above
from app.decide.routing_sim import routing_order, trap_check
from app.engine.replay import State
from app.ops.coverage import SIGNAL_BUSY, Gap, Surge, arrival, current_coverage, joiners_now, outlook_end, project, surges
from app.ops.detect import SEVERITY, Finding, detect, owner_can_act, views_at
from app.ops.refs import ET, OpsRefs
from app.references import Refs

@dataclass(frozen=True)
class Fix:
    kind: str  # assign | reassign | handoff | escalate | contact_physician | verify_physician | split_shift | watch | inform
    approver: str  # automatic | coordinator | clinical_lead
    action: str
    reason: str
    alternatives: tuple[str, ...] = ()
    physician_id: str | None = None


@dataclass(frozen=True)
class Item:
    id: str
    severity: str
    what: str
    where: dict
    why: dict
    fix: Fix
    rank_key: tuple
    candidates: tuple[Candidate, ...] = ()


@dataclass(frozen=True)
class Decisions:
    as_of: datetime
    items: tuple[Item, ...]
    gaps: tuple[Gap, ...]
    surges: tuple[Surge, ...]
    views: dict


SESSION_STATES = {"Video Consult", "Hospital Call"}  # transient: ends on its own within minutes


def free_soon(v) -> bool:
    """On shift and only briefly unroutable: in a call or video, or in the 2-minute post-call cooldown."""
    return "off_shift" not in v.exclusion_reasons and (v.derived_state in SESSION_STATES or set(v.exclusion_reasons) == {"cooldown"})


def _who_blocks(views, hospital_id):
    """Credentialed on-shift physicians and why each cannot take the consult now."""
    return [f"{v.physician_id}: {v.derived_state}" + (f" ({', '.join(v.exclusion_reasons)})" if v.exclusion_reasons else "")
            for v in views.values() if hospital_id in v.allowed_hospitals and "off_shift" not in v.exclusion_reasons]


def _routable(views, hospital_id, exclude=None):
    return [v for v in views.values() if v.routable and hospital_id in v.allowed_hospitals and v.physician_id != exclude]


def _split_alternative(hospital_id, refs, ops, now):
    """Fastest eligible off-shift physician for an immediate 2 h offer at this hospital."""
    probe = Gap(hospital_id, now, now + timedelta(hours=2), "hard", None, 0, 0, False, True, ())
    ranked = [c for c in evaluate(probe, [probe], refs, ops, now) if c.hospitals]
    eligible = [c for c in ranked if c.eligible]
    if not eligible:
        closest = min(ranked, key=lambda c: (len(c.failed), c.physician_id), default=None)
        return ("split shift: nobody off shift is credentialed here" if closest is None else
                f"split shift: nobody eligible for an immediate offer; closest {closest.physician_id} fails " +
                ", ".join(f"{r.label} ({r.value})" for r in closest.rules if not r.passed))
    best = min(eligible, key=lambda c: ops.roster[c.physician_id].minutes_to_online)
    return f"split shift: fastest eligible ({best.physician_id}) needs {ops.roster[best.physician_id].minutes_to_online} min to come online plus approval and a reply (up to 10 min); too slow for this consult, pursue via the coverage item"


def _consult_fix(f: Finding, views, refs, ops, now, reserved=()) -> Fix:
    """`reserved`: physicians already given a new consult in this pass. One new consult each [A47]:
    once rung, the router excludes them too, so the same physician is never recommended for every consult."""
    hid = f.hospital_id
    exclude = f.physician_id if f.kind in {"stranded", "handoff_needed"} else None
    # Same order as the router, except a manual assignment prefers physicians not leaving within the hour.
    leaving = {v.physician_id for v in views.values() if v.minutes_to_shift_end is not None and v.minutes_to_shift_end <= 60}
    routable = sorted(routing_order([v for v in _routable(views, hid, exclude) if v.physician_id not in reserved], refs),
                      key=lambda v: v.physician_id in leaving)
    taken = [p for p in reserved if p in {v.physician_id for v in _routable(views, hid, exclude)}]
    if f.kind == "handoff_needed":
        end = views[f.physician_id].shift.end
        stays = [v for v in routable if v.shift.end > end]
        if stays:
            t = stays[0]
            return Fix("handoff", "coordinator", f"Hand {f.consult_id} to {t.physician_id} before {f.physician_id}'s shift ends",
                       f"{t.physician_id} is routable, credentialed at {hid}, on shift until {t.shift.end.astimezone(ET):%H:%M}",
                       (f"keep with {f.physician_id}: shift ends in {f.why['minutes_to_shift_end']} min",), t.physician_id)
        later = routing_order([v for v in views.values() if hid in v.allowed_hospitals and v.physician_id != f.physician_id
                               and owner_can_act(v) and v.shift.end > end], refs)
        if later:
            t = later[0]
            return Fix("handoff", "coordinator", f"Hand {f.consult_id} to {t.physician_id} when they are free ({t.derived_state} now)",
                       f"only credentialed physician at {hid} on shift past {end.astimezone(ET):%H:%M} (until {t.shift.end.astimezone(ET):%H:%M})",
                       (f"keep with {f.physician_id}: shift ends in {f.why['minutes_to_shift_end']} min",), t.physician_id)
        return Fix("escalate", "clinical_lead", f"Escalate: no credentialed physician at {hid} stays past {end.astimezone(ET):%H:%M}",
                   "nobody can take over before the owner leaves", tuple(_who_blocks(views, hid)))
    verb = "assign" if f.kind == "unassigned" else "reassign"
    if routable:
        # Steady advice [A52]: the name comes from everyone free now or only briefly busy, so it does not swap each time
        # someone starts or ends a short session; being busy changes only the timing, and a free alternative is named.
        steady = sorted(routing_order([v for v in views.values() if (v.routable or free_soon(v)) and hid in v.allowed_hospitals
                                       and v.physician_id != exclude and v.physician_id not in reserved], refs),
                        key=lambda v: v.physician_id in leaving)
        t = steady[0]
        session = lambda v: "call cooldown" if v.derived_state not in SESSION_STATES else v.derived_state.lower()
        later = f"{t.physician_id} is routable and credentialed at {hid}; first under the modeled routing order ({t.consults_this_shift} consults this shift)"
        if not t.routable:
            busy = session(t)
            free = next(v for v in routable if v.physician_id != t.physician_id)
            return Fix(verb, "coordinator", f"{verb.title()} {f.consult_id} to {t.physician_id} when their {busy} ends; if it cannot wait, {free.physician_id} is free now",
                       f"{t.physician_id} is first under the modeled routing order ({t.consults_this_shift} consults this shift) and only briefly busy; "
                       f"{free.physician_id} ({free.consults_this_shift} consults) can take it immediately",
                       (f"{free.physician_id}: free now", *(f"{v.physician_id}: also routable, later in routing order" for v in routable[1:3] if v is not free)),
                       t.physician_id)
        return Fix(verb, "coordinator", f"{verb.title()} {f.consult_id} to {t.physician_id}",
                   later + (f"; shift ends in {t.minutes_to_shift_end} min, nobody staying is free" if t.physician_id in leaving else ""),
                   tuple(f"{v.physician_id}: " + ("also routable" if v.routable else f"free when their {session(v)} ends")
                         + ", later in routing order" for v in steady[1:3]), t.physician_id)
    alternatives = (f"{verb}: no routable credentialed physician at {hid}" + (f" left ({', '.join(taken)} already taking a higher-ranked consult)" if taken else ""),
                    *_who_blocks(views, hid), _split_alternative(hid, refs, ops, now))
    ringing = [v for v in views.values() if f.consult_id and "ringing" in v.exclusion_reasons and hid in v.allowed_hospitals
               and f.why.get("ringing_since")]
    if f.kind == "unassigned" and ringing and f.severity != "Critical":
        return Fix("contact_physician", "coordinator", f"Call {ringing[0].physician_id}, whose phone is ringing for {f.consult_id}",
                   "the call is already routed to them; reaching them is faster than escalating", alternatives, ringing[0].physician_id)
    if f.kind == "unassigned" and f.severity == "Info":
        return Fix("watch", "coordinator", f"Watch {f.consult_id}: routing still in progress", "no failed route and no breached limit yet", alternatives)
    # A credentialed physician in a call or video is busy for minutes, not absent: queue the consult for them
    # instead of escalating every short session (which made the advice flip between assign and escalate).
    in_session = sorted(routing_order([v for v in views.values() if hid in v.allowed_hospitals and v.physician_id != exclude
                                       and v.physician_id not in reserved and free_soon(v)], refs),
                        key=lambda v: v.physician_id in leaving)
    if in_session:
        t = in_session[0]
        critical = f.severity == "Critical"
        busy = "call cooldown" if t.derived_state not in SESSION_STATES else t.derived_state.lower()
        return Fix(verb, "coordinator", f"{verb.title()} {f.consult_id} to {t.physician_id} when their {busy} ends"
                   + (" and notify the clinical lead (critical)" if critical else ""),
                   f"nobody credentialed at {hid} is free now; {t.physician_id} is in a session, which is short, not an absence",
                   ("escalate: the lead can pull someone from other work if the session runs long", *alternatives), t.physician_id)
    return Fix("escalate", "clinical_lead", f"Escalate {f.consult_id} to the clinical lead",
               "nobody credentialed at this hospital can take it now; the lead decides whether to pull a physician from other work or ask an unavailable one to return",
               alternatives)


def _finding_fix(f: Finding, views, refs, ops, now, reserved=()) -> Fix:
    if f.kind in {"unassigned", "stranded", "handoff_needed"}:
        return _consult_fix(f, views, refs, ops, now, reserved)
    if f.kind == "stage_breach":
        owner = views.get(f.physician_id) if f.physician_id else None
        if owner is None:
            return _consult_fix(Finding("unassigned", f.severity, f.what, f.hospital_id, f.consult_id), views, refs, ops, now, reserved)
        action = {"Assigned": "Prompt the hospital and physician to connect", "Imaging Pending": "Chase CT/CTA status with the hospital",
                  "Imaging Review": "Prompt the physician to start the video consult"}.get(f.why["stage"], "Prompt the physician")
        escalate = f.stroke and f.severity == "Critical"
        return Fix("contact_physician", "coordinator", action + (" and notify the clinical lead (stroke critical)" if escalate else ""),
                   f"{f.why['age_min']} min in {f.why['stage']} vs critical {f.why['critical_min']} min; owner {f.physician_id} is {owner.derived_state}")
    if f.kind in {"note_overdue", "notes_at_shift_end"}:
        owner = views.get(f.physician_id)
        if owner is None or "off_shift" in owner.exclusion_reasons:
            # Messages to off-shift physicians need approval [B p2]; only the coordinator is alerted.
            return Fix("contact_physician", "coordinator", f"Follow up {f.physician_id}'s open notes (now off shift)",
                       "no automatic message reaches an off-shift physician; the coordinator decides how to follow up")
        return Fix("contact_physician", "automatic", f"Alert {f.physician_id} to complete open notes", "internal low-risk alert to an on-shift physician [B p2]; documentation stays with the owner")
    if f.kind == "unanswered_ring":
        return Fix("contact_physician", "coordinator", f"Call the physician being rung about {f.consult_id}", "the ring is unanswered and the hospital is waiting")
    if f.kind in {"external_platform", "agent_offline"}:
        return Fix("verify_physician", "coordinator", f"Confirm {f.physician_id}'s real availability", "signals disagree; routing may be wrong about this physician")
    if f.kind == "overload":
        return Fix("inform", "coordinator", f"Review {f.physician_id}'s workload and arrange support",
                   "workload threshold reached; this warning does not prohibit routing or transfer note ownership")
    return Fix("inform", "automatic", "No live action; credentialing explains the load", "workload follows credentials, not effort")


def _gap_item(gap: Gap, hard: list[Gap], refs, ops, now, history) -> Item:
    candidates = tuple(evaluate(gap, sorted({*hard, gap}, key=lambda g: (g.hospital_id, g.start)), refs, ops, now, history))
    eligible = [c for c in candidates if c.eligible]
    window = f"{gap.start.astimezone(ET):%H:%M}-{gap.end.astimezone(ET):%H:%M}"
    if gap.kind == "at_risk":
        fix = Fix("watch", "coordinator", f"Watch: covered only if the scheduled starter comes online; {len(eligible)} split-shift candidate(s) ready",
                  "a scheduled shift closes this gap; an offer now would duplicate it", (f"split shift ready: {eligible[0].physician_id}",) if eligible else ())
    elif gap.kind == "unknown":
        fix = Fix("inform", "coordinator", "Coverage unknown: reference data missing for this block", "missing baseline or requirement row")
    elif eligible:
        best = eligible[0]
        fix = Fix("split_shift", "clinical_lead",
                  f"Offer {best.physician_id} a split shift {best.start.astimezone(ET):%H:%M}-{best.end.astimezone(ET):%H:%M} at {', '.join(best.hospitals)}",
                  f"passes every rule; covers {best.covered_minutes} gap minutes" + ("; low value" if best.low_value else "")
                  + (f"; chosen over {eligible[1].physician_id} because {best.physician_id} {ranked_above(best, eligible[1], ops, history)}" if len(eligible) > 1 else ""),
                  ("reassign: does not add capacity", *(f"{c.physician_id}: eligible, ranked lower: {above.physician_id} {ranked_above(above, c, ops, history)}"
                                                        for above, c in zip(eligible, eligible[1:])),
                   *(f"{c.physician_id}: fails {', '.join(c.failed)}" for c in candidates if not c.eligible)), best.physician_id)
    else:
        fix = Fix("escalate", "clinical_lead", f"Escalate: no off-shift physician may cover {gap.hospital_id} {window}",
                  "every off-shift physician fails at least one rule; rules are never bent [H ch2 #8]",
                  tuple(f"{c.physician_id}: fails {', '.join(c.failed)}" for c in candidates))
    severity = {"hard": "Critical" if gap.in_horizon else "Warning", "at_risk": "Warning" if gap.in_horizon else "Info"}.get(gap.kind, "Warning")
    shortfall = None if gap.required is None else gap.required - gap.confirmed - (gap.scheduled if gap.kind == "hard" else 0)
    item = Item(gap.id, severity, f"{refs.hospitals[gap.hospital_id].name} short of credentialed coverage {window}" + (" (at risk)" if gap.kind == "at_risk" else ""),
                {"hospital_id": gap.hospital_id}, {"required": gap.required, "confirmed": gap.confirmed, "scheduled": gap.scheduled, "short_by": shortfall,
                                                   "in_horizon": gap.in_horizon, "causes": list(gap.causes)}, fix, (), candidates)
    return item


def _rank_key(severity, in_horizon, ownerless, stroke, repeat, since, affected, item_id):
    # Lexicographic, no weights [doc 5.5]. `since` is first contact (consults) or gap start.
    return (SEVERITY.index(severity), not in_horizon, not ownerless, not stroke, not repeat, since.timestamp() if since else float("inf"), -affected, item_id)


# Which finding drives the fix when several describe the same consult or physician.
PRIMARY = ("stranded", "unassigned", "handoff_needed", "stage_breach", "unanswered_ring", "notes_at_shift_end", "note_overdue",
           "overload", "external_platform", "agent_offline", "credential_imbalance")


def _subject(f: Finding, note_owners):
    if f.kind == "note_overdue" and f.physician_id:
        return ("physician", f.physician_id)  # one notes item per owner (folded into their shift-end item if any)
    return ("consult", f.consult_id) if f.consult_id else ("physician", f.physician_id)


def _merge(findings, views, refs, ops, now):
    note_owners = {f.physician_id for f in findings if f.kind == "notes_at_shift_end"}
    groups = {}
    for f in findings:
        groups.setdefault(_subject(f, note_owners), []).append(f)
    ranked = []
    for group in groups.values():
        group.sort(key=lambda f: (PRIMARY.index(f.kind), f.id))
        primary = group[0]
        severity = min((f.severity for f in group), key=SEVERITY.index)
        ownerless = any(f.kind in {"unassigned", "stranded"} for f in group)
        since = min((f.waiting_since for f in group if f.waiting_since), default=None)
        key = _rank_key(severity, True, ownerless, any(f.stroke for f in group), any(f.repeat_contacts for f in group), since, len(group), primary.id)
        ranked.append((key, group, primary, severity))
    items, reserved = [], set()
    for key, group, primary, severity in sorted(ranked, key=lambda r: r[0]):
        why = {**{k: v for f in reversed(group) for k, v in f.why.items()}, "repeat_contacts": primary.repeat_contacts}
        fix = _finding_fix(Finding(**{**primary.__dict__, "severity": severity, "why": why}), views, refs, ops, now, reserved)
        if fix.kind in {"assign", "reassign"} or (fix.kind == "handoff" and views[fix.physician_id].routable):  # incl. queued for a session
            reserved.add(fix.physician_id)
        if primary.kind == "unanswered_ring" or (primary.kind == "unassigned" and primary.consult_id and any(f.kind == "unanswered_ring" for f in group)):
            why["other_routable_credentialed"] = len(_routable(views, primary.hospital_id))
        also = [f"{f.severity}: {f.what}" for f in group[1:]]
        if also:
            why["also"] = also
        items.append(Item(primary.id, severity, primary.what,
                          {"hospital_id": primary.hospital_id, "consult_id": primary.consult_id, "physician_id": primary.physician_id}, why, fix, key))
    return items


def _incidents(items, refs):
    """Escalations for consults at the same hospital share one cause (nobody credentialed free there), so the lead
    gets one incident per hospital instead of one alert per patient [H ch7]. Every consult stays listed with its wait."""
    groups = {}
    for item in items:
        if item.fix.kind == "escalate" and item.where.get("consult_id"):
            groups.setdefault(item.where["hospital_id"], []).append(item)
    replaced = {}
    for hid, group in groups.items():
        if len(group) < 2:
            continue
        group.sort(key=lambda i: i.rank_key)
        head = group[0]
        ids = [i.where["consult_id"] for i in group]
        waits = {i.where["consult_id"]: i.why.get("waited_min") for i in group}
        fix = Fix("escalate", "clinical_lead", f"Escalate {len(group)} consults at {refs.hospitals[hid].name} to the clinical lead (most urgent first: {', '.join(ids)})",
                  "nobody credentialed at this hospital can take them now; one decision covers all of them", head.fix.alternatives)
        item_id = f"escalate:{hid}"
        replaced[head.id] = Item(item_id, head.severity, f"{len(group)} consults waiting at {refs.hospitals[hid].name} with nobody credentialed free",
                                 {"hospital_id": hid, "consult_ids": ids}, {**head.why, "consults": ids, "waited_min": waits,
                                                                            "also": [i.what for i in group[1:]]},
                                 fix, head.rank_key[:-2] + (-len(group), item_id))
        replaced.update({i.id: None for i in group[1:]})
    return [replaced.get(i.id, i) for i in items if replaced.get(i.id, i) is not None]


def _relied_on(gap):
    return tuple(c.removeprefix("relies on ") for c in gap.causes if c.startswith("relies on "))


def _at_risk_items(gaps, hard, refs, ops, now, history):
    """One watch item per scheduled starter the coverage depends on, instead of one per hospital."""
    groups = {}
    for g in gaps:
        if g.kind == "at_risk":
            groups.setdefault(_relied_on(g), []).append(g)
    items = []
    for starters, members in sorted(groups.items()):
        members.sort(key=lambda g: (g.start, g.hospital_id))
        first = members[0]
        lead = _gap_item(first, hard, refs, ops, now, history)
        in_horizon = any(g.in_horizon for g in members)
        severity = "Warning" if in_horizon else "Info"
        windows = [f"{refs.hospitals[g.hospital_id].name} {g.start.astimezone(ET):%H:%M}-{g.end.astimezone(ET):%H:%M}" for g in members]
        item_id = "watch:" + "+".join(starters)
        items.append(Item(item_id, severity, f"Coverage at {len(members)} hospital window(s) depends on {' and '.join(starters)}",
                          {"hospital_ids": sorted({g.hospital_id for g in members})},
                          {"windows": windows, "earliest": first.start, "in_horizon": in_horizon, "causes": list(first.causes),
                           "becomes_hard_if": "no shift_started by 5 min after the scheduled start"},
                          lead.fix, _rank_key(severity, in_horizon, False, False, False, first.start, len(members), item_id), lead.candidates))
    return items


def _merge_offers(items, refs, ops, now, history, gaps):
    """Gaps whose best fix is the same physician become one offer (one approval, one message), but only if
    the merged window still passes every rule; otherwise the separate offers stay as they are."""
    by_physician = {}
    for item in items:
        if item.fix.kind == "split_shift":
            by_physician.setdefault(item.fix.physician_id, []).append(item)
    replaced = {}
    for pid, group in by_physician.items():
        if len(group) < 2:
            continue
        group.sort(key=lambda i: i.rank_key)
        bests = [next(c for c in i.candidates if c.physician_id == pid) for i in group]
        proposal = Proposal(min(c.start for c in bests), max(c.end for c in bests), tuple(sorted({h for c in bests for h in c.hospitals})))
        candidates = tuple(evaluate_proposal(proposal, refs, ops, now, history, gaps))
        best = next(c for c in candidates if c.physician_id == pid)
        if not best.eligible:
            continue
        first = group[0]
        hospitals = list(proposal.hospitals)
        runner = next((c for c in candidates if c.eligible and c.physician_id != pid), None)
        fix = Fix("split_shift", "clinical_lead", f"Offer {pid} a split shift {proposal.start.astimezone(ET):%H:%M}-{proposal.end.astimezone(ET):%H:%M} at {', '.join(hospitals)}",
                  f"passes every rule for the combined window; covers {best.covered_minutes} gap minutes; ready {best.ready_at.astimezone(ET):%H:%M}"
                  + (f"; chosen over {runner.physician_id} because {pid} {ranked_above(best, runner, ops, history)}" if runner and candidates.index(best) < candidates.index(runner) else ""),
                  first.fix.alternatives, pid)
        replaced[first.id] = Item(first.id, first.severity, f"{first.what} (+{len(group) - 1} more gap(s) closed by the same offer)", {"hospital_ids": hospitals},
                                  {**first.why, "also": [i.what for i in group[1:]]}, fix, first.rank_key, candidates)
        replaced.update({i.id: None for i in group[1:]})
    return [replaced.get(i.id, i) for i in items if replaced.get(i.id, i) is not None]


def _current_gap_items(state, refs, ops, views, now, hard, history, accepted=()):
    """Short right now by signals [B p4]: available = on shift, credentialed and not busy."""
    items, probes, end = [], [], outlook_end(refs, now)
    waiting = {}
    for c in state.consults.values():
        if c.stage in {"Received", "Triaged"} and c.owner == "Unassigned":
            waiting.setdefault(c.hospital_id, []).append(c.consult_id)
    free = [v for v in views.values() if "off_shift" not in v.exclusion_reasons and v.derived_state not in SIGNAL_BUSY]
    for cc in current_coverage(state, refs, ops, views, now):
        if not cc.gap or len(cc.available) + joiners_now(state, ops, accepted, cc.hospital_id, now, views) >= cc.required:
            continue  # short by signals, but an accepted split shift is already the fix
        hid = cc.hospital_id
        elsewhere = [f"{v.physician_id} is free but not credentialed here" for v in free if hid not in v.allowed_hospitals]
        causes = (*_who_blocks(views, hid), *(["surge: +1 required"] if cc.surge else []), *elsewhere)
        probe = Gap(hid, now, end, "hard", cc.required, len(cc.available), 0, bool(cc.surge), True, causes)
        probes.append(probe)
        base = _gap_item(probe, hard, refs, ops, now, history)
        severity = "Critical" if waiting.get(hid) else "Warning"
        if not waiting.get(hid):
            # Short by signals but nobody waiting: busy time is transient, so watch rather than call someone in.
            ready = [c.physician_id for c in base.candidates if c.eligible]
            base = Item(base.id, base.severity, base.what, base.where, base.why,
                        Fix("watch", "coordinator", f"Watch: short by signals with no consult waiting; {len(ready)} split-shift candidate(s) ready",
                            "physicians here are busy, not absent; an offer is proposed once a consult waits or the forecast shows a gap",
                            tuple(f"split shift ready: {pid}" for pid in ready[:1])), base.rank_key, base.candidates)
        item_id = f"now_gap:{hid}"
        items.append(Item(item_id, severity, f"{refs.hospitals[hid].name}: {len(cc.available)} of {cc.required} required credentialed physicians free now",
                          {"hospital_id": hid},
                          {"required": cc.required, "base_requirement": cc.base_requirement, "surge": cc.surge, "available": list(cc.available),
                           "routable": list(cc.routable), "waiting_unassigned": sorted(waiting.get(hid, [])), "free_elsewhere": elsewhere, "causes": list(causes)},
                          base.fix, _rank_key(severity, True, bool(waiting.get(hid)), False, False, now, cc.gap, item_id), base.candidates))
    return items, probes


def _with_trap_guard(item: Item, state, refs, ops, views, now, service, accepted) -> Item:
    """Step 7: every split-shift offer carries the router setting that contains the trap, and the model's verdict on it."""
    best = next(c for c in item.candidates if c.physician_id == item.fix.physician_id)
    check = trap_check(state, refs, ops, views, now, best.physician_id, best.ready_at, best.end, best.hospitals, service, accepted)
    if check is None:
        return Item(item.id, item.severity, item.what, item.where, {**item.why, "trap_guard": "not modeled: no service time observed yet"},
                    item.fix, item.rank_key, item.candidates)
    failed = [c.key for c in check.criteria if not c.passed]
    setting = f"router setting: restrict {best.physician_id} to {', '.join(sorted(check.joiner.hospitals))} and seed {check.seed} consults"
    verdict = "trap check passed" if not failed else "trap check failed: " + ", ".join(failed)
    guard = {"restrict_to": sorted(check.joiner.hospitals), "seed": check.seed, "passed": check.passed, "trap_shown_unguarded": check.trap_shown,
             "wait_minutes_removed": dict(check.relief), "unguarded_spill": dict(check.spill), "criteria": [f"{c.key}: {c.value}" for c in check.criteria]}
    if all(n <= 0 for n in check.relief.values()):
        guard["note"] = "model predicts no shorter waits; the offer meets the coverage requirement, not a routing failure"
    fix = Fix(item.fix.kind, item.fix.approver, item.fix.action, f"{item.fix.reason}; {setting} ({verdict})",
              (*item.fix.alternatives, f"unguarded join: {'floods other hospitals or out-loads every peer (trap)' if check.trap_shown else 'no trap under modeled demand'}"),
              item.fix.physician_id)
    return Item(item.id, item.severity, item.what, item.where, {**item.why, "trap_guard": guard}, fix, item.rank_key, item.candidates)


def _late_joiner_items(state, refs, ops, now, accepted):
    """A doctor who accepted but has not come online no longer counts [A50]; the reopened gap gets its own item,
    and this one tells the coordinator to call them."""
    items = []
    for s in accepted:
        a = arrival(s, state, ops, now)
        if not a.late or now >= s.end:
            continue
        item_id = f"joiner_late:{s.physician_id}"
        names = ", ".join(refs.hospitals[h].name for h in sorted(s.hospitals))
        items.append(Item(item_id, "Warning", f"{s.physician_id} accepted a split shift but has not come online (expected {a.expected.astimezone(ET):%H:%M})",
                          {"physician_id": s.physician_id, "hospital_ids": sorted(s.hospitals)},
                          {"expected_online": a.expected, "accepted_at": s.accepted_at, "shift": f"{s.start.astimezone(ET):%H:%M}-{s.end.astimezone(ET):%H:%M}"},
                          Fix("contact_physician", "coordinator", f"Call {s.physician_id} about the accepted split shift at {names}",
                              "no shift_started by 5 min after the expected online time; their hours no longer count toward coverage",
                              physician_id=s.physician_id),
                          _rank_key("Warning", True, False, False, False, a.expected, len(s.hospitals), item_id)))
    return items


def decide(state: State, refs: Refs, ops: OpsRefs, now: datetime, history: OfferHistory = OfferHistory(), accepted=(),
           service=None) -> Decisions:
    """`service`: observed_service(events, state), median busy minutes per consult; enables the trap check on offers.
    `accepted` split shifts always count against R4/R5, even if `history` was built without them."""
    windows = {}
    for s in accepted:
        windows.setdefault(s.physician_id, set(history.accepted.get(s.physician_id, ()))).add((s.start, s.end))
    if windows:
        history = replace(history, accepted={**history.accepted, **{p: tuple(sorted(w)) for p, w in windows.items()}})
    views = views_at(state, refs, now, ops=ops, accepted=accepted)
    findings = detect(state, refs, views, now)
    gaps = project(state, refs, ops, views, now, accepted)
    hard = [g for g in gaps if g.kind == "hard"]
    items = _incidents(_merge(findings, views, refs, ops, now), refs)
    current, probes = _current_gap_items(state, refs, ops, views, now, hard, history, accepted)
    # A schedule gap starting now outranks a "busy, not absent" watch: nobody to wait for means act now.
    scheduled_short_now = {g.hospital_id for g in hard if g.start == now}
    current = [i for i in current if not (i.fix.kind == "watch" and i.where["hospital_id"] in scheduled_short_now)]
    acting_now = {i.where["hospital_id"] for i in current}
    for g in gaps:
        if g.kind == "at_risk" or (g.start == now and g.hospital_id in acting_now):
            continue  # a forecast gap starting now is already the current-gap item
        item = _gap_item(g, hard, refs, ops, now, history)
        items.append(Item(item.id, item.severity, item.what, item.where, item.why, item.fix,
                          _rank_key(item.severity, g.in_horizon, False, False, False, g.start, 1, item.id), item.candidates))
    items = _merge_offers(items + current, refs, ops, now, history, hard + probes)
    if service is not None:
        items = [_with_trap_guard(i, state, refs, ops, views, now, service, accepted) if i.fix.kind == "split_shift" else i for i in items]
    items += _at_risk_items(gaps, hard, refs, ops, now, history)
    items += _late_joiner_items(state, refs, ops, now, accepted)
    found_surges = surges(state, refs, ops, now)
    for s in found_surges:
        items.append(Item(f"surge:{s.hospital_id}", "Warning", f"{refs.hospitals[s.hospital_id].name} demand surge: {s.count} consults in 60 min vs p90 {s.p90:g}",
                          {"hospital_id": s.hospital_id}, {"count": s.count, "p90": s.p90, "until": s.until},
                          Fix("inform", "automatic", "Requirement +1 applied in the coverage projection", "trailing 60-minute consults above this hour's p90 [B p4]"),
                          _rank_key("Warning", True, False, False, False, s.until, s.count, f"surge:{s.hospital_id}")))
    items.sort(key=lambda i: i.rank_key)
    return Decisions(now, tuple(items), tuple(gaps), tuple(found_surges), views)
