"""The demo's moving clock on each allowed pack: decisions stay safe and actionable at every pass, not only at checkpoints."""
from collections import Counter
from datetime import timedelta
import pytest
from test_pack import PACKS, load_pack

pytestmark = pytest.mark.skipif(not PACKS, reason="scenario packs are not committed")


@pytest.fixture(scope="module", params=PACKS, ids=lambda p: p.name)
def ticks(request):
    from pack_metrics import sweep
    pack = load_pack(request.param)
    return sweep(pack, pack.time("1820"), pack.time("2220"), timedelta(minutes=10))


def test_every_pass_is_safe_and_feasible(ticks):
    assert [(t["now"], t["violations"]) for t in ticks if t["violations"]] == []


def test_every_critical_item_gets_an_action(ticks):
    assert [(t["now"], t["critical_unactioned"]) for t in ticks if t["critical_unactioned"]] == []


def test_every_offer_is_trap_guarded_and_the_trap_is_real(ticks):
    offers = [o for t in ticks for o in t["trap"]]
    assert all(passed and shown for _, passed, shown, _ in offers)  # whether an offer should exist: test_pack example-offer test
    assert all(removed["baseline"] > 0 for *_, removed in offers)  # the guarded joiner shortens waits at the gap hospitals


def test_one_escalation_per_hospital_per_pass(ticks):
    for t in ticks:
        escalations = Counter(k.split(":", 1)[1] for k, (kind, _) in t["fixes"].items() if kind == "escalate" and k.startswith("escalate:"))
        assert all(n == 1 for n in escalations.values())


def test_advice_is_stable_between_passes(ticks):
    from pack_metrics import flip_flops
    persisting = sum(t["persisting"] for t in ticks)
    assert sum(len(t["changed"]) for t in ticks) <= 0.05 * persisting
    # Remaining flips are two free physicians swapping places in the router's order as each takes calls.
    assert len(flip_flops(ticks)) <= 0.02 * persisting
