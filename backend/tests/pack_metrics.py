"""Decision-engine metrics on each allowed pack. Run: `.venv/bin/python tests/pack_metrics.py [step_minutes]`.

Three kinds of evidence, because the engine is rules, not a model, and has no "accuracy" in the ML sense:
1. Answer-key agreement: field-level match of replayed state, forecast and candidate table with expected/.
2. Scenario recall: each scenario family the pack plants shows up in the queue at its checkpoint (and the
   negative control does not).
3. A clock-advancing sweep (the demo: live events arrive while the clock moves): per tick, safety invariants,
   whether every critical problem gets an action, trap-guard results, churn between ticks, and latency.
expected/ is read here and in tests only, never by app code.
"""
import json
import random
import statistics
import sys
import time
from datetime import datetime, timedelta
from test_pack import PACKS, consult_row, coverage_row, load_pack, physician_row, state_at
from app.clock import utc
from app.decide.eligibility import Proposal, evaluate_proposal
from app.decide.interventions import decide, free_soon
from app.decide.routing_sim import observed_service
from app.engine.replay import replay
from app.models import Event
from app.ops.coverage import current_coverage, supply
from app.ops.detect import views_at
from app.ops.refs import ET

ACTIONS = {"assign", "reassign", "handoff", "escalate", "contact_physician", "split_shift"}


def visible(rows, now):
    return tuple(Event(**{**r.model_dump(), "received_at": r.ingested_at, "raw_json": {}})
                 for r in rows.values() if r.ingested_at <= now and r.event_time <= now)


def field_match(pairs):
    """pairs: (actual dict, expected row). Returns (matching fields, compared fields)."""
    hit = total = 0
    for actual, row in pairs:
        for f, v in row.items():
            if f in actual:
                total += 1
                hit += actual[f] == v
    return hit, total


def answer_key(pack):
    refs, ops, rows, expected = pack.refs, pack.ops, pack.rows, pack.expected
    out = {}
    for cp in pack.checkpoints:
        now = utc(datetime.fromisoformat(cp["as_of"]))
        state = state_at(rows, now)
        cov = {c.hospital_id: c for c in current_coverage(state, refs, ops, views_at(state, refs, now), now)}
        out[cp["label"]] = {
            "consults": field_match((consult_row(state.consults[r["consult_id"]], now), r) for r in expected(f"snapshot_consults_{cp['label']}.csv")),
            "physicians": field_match((physician_row(state, refs, r["physician_id"], now), r) for r in expected(f"snapshot_physicians_{cp['label']}.csv")),
            "coverage": field_match((coverage_row(cov[r["hospital_id"]], ops, now), r) for r in expected(f"snapshot_coverage_{cp['label']}.csv")),
        }
    now = pack.time("1820")
    state = state_at(rows, now)
    items = supply(state, refs, ops, views_at(state, refs, now), now)
    pairs = []
    for row in expected("forecast_schedule_bounds_1820.csv"):
        t, h = utc(datetime.fromisoformat(row["forecast_at"])), row["hospital_id"]
        ceiling = sum(1 for s in items if h in s.hospitals and s.start <= t and (s.end is None or t < s.end))
        base = ops.requirement(h, t)
        pairs.append(({"base_requirement": str(base), "scheduled_capacity_ceiling": str(ceiling), "guaranteed_baseline_gap": str(max(0, base - ceiling))}, row))
    out["forecast_1820"] = field_match(pairs)
    key = json.loads((pack.path / "expected/candidate_checks_1820.json").read_text())
    now = utc(datetime.fromisoformat(key["now"]))
    proposal = Proposal(utc(datetime.fromisoformat(key["proposal"]["start"])), utc(datetime.fromisoformat(key["proposal"]["end"])), tuple(key["proposal"]["hospitals"]))
    got = {c.physician_id: c for c in evaluate_proposal(proposal, refs, ops, now, pack.history(now))}
    rules = [(r.passed, want["rules"][r.key]) for want in key["candidates"] for r in got[want["physician_id"]].rules]
    out["candidate_rules"] = (sum(a == b for a, b in rules), len(rules))
    out["candidate_eligible"] = (sum(got[w["physician_id"]].eligible == w["eligible"] for w in key["candidates"]), len(key["candidates"]))
    return out


def mentions(item, evidence):
    """Strict match: the evidence ID is the item's subject, not just named in an alternative."""
    where = [v for v in item.where.values() if v] + [h for v in item.where.values() if isinstance(v, list) for h in v]
    return evidence in item.id or evidence in where or any(evidence in s for s in item.why.get("free_elsewhere", ()))


def scenario_recall(pack):
    queues = {cp["label"]: decide(state_at(pack.rows, now), pack.refs, pack.ops, now, pack.history(now)).items
              for cp in pack.checkpoints for now in [pack.time(cp["label"])]}
    out = []
    for row in pack.expected("scenario_instances.csv"):
        labels = [c for c in row["checkpoint"].split("|") if c in queues]
        if not labels:
            out.append((row["family_id"], row["scenario"], "workflow: see step 8 / simulator", None))
            continue
        if row["family_id"] in {"HB07", "HB08"}:
            out.append((row["family_id"], row["scenario"], "state-level: scored by answer-key agreement", None))
            continue
        evidence = row["evidence"].split("|")
        control = evidence[1:] if "negative control" in row["scenario"] else []
        found = {e: [l for l in labels if any(mentions(i, e) for i in queues[l])] for e in evidence if e not in control}
        false_alarm = {e: [l for l in labels if any(mentions(i, e) and i.id.startswith("stage_breach") for i in queues[l])] for e in control}
        ok = all(found.values()) and not any(false_alarm.values())
        out.append((row["family_id"], row["scenario"], f"found {found}" + (f", negative control flagged {false_alarm}" if control else ""), ok))
    return out


def violations(d, state, refs, ops, now):
    """Safety and feasibility rules every pass must satisfy. Returns a list of strings (empty = clean)."""
    bad = []
    off = {pid for pid, v in d.views.items() if "off_shift" in v.exclusion_reasons}
    gap_sites = {g.hospital_id for g in d.gaps if g.kind == "hard"} | {c.hospital_id for c in current_coverage(state, refs, ops, d.views, now) if c.gap}
    targets = []
    consults = [c for i in d.items for c in ([i.where["consult_id"]] if i.where.get("consult_id") else i.where.get("consult_ids", []))]
    if len(consults) != len(set(consults)):
        bad.append("duplicate consult items")
    for i in d.items:
        f = i.fix
        if f.approver == "automatic" and (i.where.get("physician_id") in off or f.physician_id in off):
            bad.append(f"{i.id}: automatic action aimed at an off-shift physician")
        if f.kind == "split_shift":
            best = next((c for c in i.candidates if c.physician_id == f.physician_id), None)
            sites = set(i.where.get("hospital_ids") or [i.where["hospital_id"]])
            if f.approver != "clinical_lead":
                bad.append(f"{i.id}: offer without clinical-lead approval")
            if best is None or not best.eligible:
                bad.append(f"{i.id}: offer to a physician failing a rule")
            if not sites <= gap_sites:
                bad.append(f"{i.id}: offer names non-gap hospitals {sorted(sites - gap_sites)}")
            if not isinstance(i.why.get("trap_guard"), dict):
                bad.append(f"{i.id}: offer without a trap check")  # a failed check is shown to the lead, not a violation
        if f.kind in {"assign", "reassign"}:
            targets.append(f.physician_id)
            v = d.views[f.physician_id]
            if i.where["hospital_id"] not in v.credentialed_hospitals or not (v.routable or free_soon(v)):
                bad.append(f"{i.id}: {f.kind} to {f.physician_id}, who is not on shift, credentialed and free or in a short session")
    if len(targets) != len(set(targets)):
        bad.append("same physician given two new consults in one pass")
    return bad


def sweep(pack, start, end, step):
    refs, ops, rows = pack.refs, pack.ops, pack.rows
    ticks, previous = [], None
    now = start
    while now <= end:
        events = visible(rows, now)
        began = time.perf_counter()
        state = replay(events)
        service = observed_service(events, state)
        d = decide(state, refs, ops, now, pack.history(now), service=service)
        ms = (time.perf_counter() - began) * 1000
        critical = [i for i in d.items if i.severity == "Critical"]
        offers = [i for i in d.items if i.fix.kind == "split_shift"]
        fixes = {i.id: (i.fix.kind, i.fix.physician_id) for i in d.items}
        changed = [k for k in fixes if previous and k in previous and previous[k] != fixes[k]]
        ticks.append({"now": now, "ms": ms, "items": len(d.items), "critical": len(critical),
                      "critical_unactioned": [i.id for i in critical if i.fix.kind not in ACTIONS],
                      "offers": len(offers), "escalations": sum(i.fix.kind == "escalate" for i in d.items),
                      "trap": [(i.fix.physician_id, i.why["trap_guard"]["passed"], i.why["trap_guard"]["trap_shown_unguarded"],
                                i.why["trap_guard"]["wait_minutes_removed"]) for i in offers if isinstance(i.why.get("trap_guard"), dict)],
                      "violations": violations(d, state, refs, ops, now), "persisting": len([k for k in fixes if previous and k in previous]),
                      "changed": changed, "fixes": fixes})
        previous = fixes
        now += step
    return ticks


def flip_flops(ticks):
    """A fix that changes and later returns to an earlier choice for the same item: unstable advice."""
    seen, flips = {}, []
    for t in ticks:
        for k, fix in t["fixes"].items():
            past = seen.setdefault(k, [])
            if past and past[-1] != fix and fix in past:
                flips.append((t["now"], k))
            if not past or past[-1] != fix:
                past.append(fix)
    return flips


def order_invariance(pack):
    refs, ops, rows = pack.refs, pack.ops, pack.rows
    out = []
    for cp in pack.checkpoints:
        now = utc(datetime.fromisoformat(cp["as_of"]))
        events = list(visible(rows, now))
        base = decide(replay(tuple(events)), refs, ops, now, service=observed_service(events, replay(tuple(events))))
        random.Random(1).shuffle(events)
        shuffled = decide(replay(tuple(events)), refs, ops, now, service=observed_service(events, replay(tuple(events))))
        out.append([(i.id, i.fix) for i in base.items] == [(i.id, i.fix) for i in shuffled.items])
    return out


def pct(pair):
    hit, total = pair
    return f"{hit}/{total} ({100 * hit / total:.1f}%)" if total else "n/a"


def report(pack, step_minutes):
    print(f"\n######## {pack.path.name} (example offer: {pack.manifest['eligible_candidates_for_example_offer']} eligible) ########")
    print("== 1. Answer-key agreement (field level) ==")
    for k, v in answer_key(pack).items():
        print(f"  {k:18} " + (", ".join(f"{n} {pct(p)}" for n, p in v.items()) if isinstance(v, dict) else pct(v)))
    print("\n== 2. Scenario recall at the pack's checkpoints ==")
    recall = scenario_recall(pack)
    for fam, name, detail, ok in recall:
        print(f"  {fam} {'PASS' if ok else 'MISS' if ok is False else ' -- '} {name}: {detail}")
    scored = [ok for *_, ok in recall if ok is not None]
    print(f"  recall {sum(scored)}/{len(scored)}")
    start, end = pack.time(pack.checkpoints[0]["label"]), pack.time(pack.checkpoints[-1]["label"])
    ticks = sweep(pack, start, end, timedelta(minutes=step_minutes))
    print(f"\n== 3. Clock sweep {start.astimezone(ET):%H:%M}-{end.astimezone(ET):%H:%M} every {step_minutes} min ({len(ticks)} passes) ==")
    print("  time  items crit offers esc changed  ms   trap guard (physician, passed, trap shown unguarded, wait-min removed)")
    for t in ticks:
        print(f"  {t['now'].astimezone(ET):%H:%M} {t['items']:5} {t['critical']:4} {t['offers']:6} {t['escalations']:3} {len(t['changed']):7} {t['ms']:5.0f}  {t['trap']}"
              + (f"  VIOLATIONS {t['violations']}" if t["violations"] else "") + (f"  UNACTIONED {t['critical_unactioned']}" if t["critical_unactioned"] else ""))
    ms = sorted(t["ms"] for t in ticks)
    persisting = sum(t["persisting"] for t in ticks)
    changed = sum(len(t["changed"]) for t in ticks)
    offers = [g for t in ticks for g in t["trap"]]
    print("\n== Summary ==")
    print(f"  safety/feasibility violations: {sum(len(t['violations']) for t in ticks)} across {len(ticks)} passes")
    print(f"  critical items without an action: {sum(len(t['critical_unactioned']) for t in ticks)} of {sum(t['critical'] for t in ticks)}")
    print(f"  offers with a passing trap guard: {sum(p for _, p, _, _ in offers)}/{len(offers)}; trap shown when unguarded: {sum(s for _, _, s, _ in offers)}/{len(offers)}")
    print(f"  fix churn: {changed}/{persisting} persisting items changed fix between passes; flip-flops: {len(flip_flops(ticks))}")
    print(f"  order invariance at checkpoints: {order_invariance(pack)}")
    print(f"  latency per pass (replay + decide): median {statistics.median(ms):.0f} ms, p95 {ms[int(0.95 * (len(ms) - 1))]:.0f} ms, max {ms[-1]:.0f} ms")


if __name__ == "__main__":
    for path in PACKS:
        report(load_pack(path), int(sys.argv[1]) if len(sys.argv) > 1 else 5)
