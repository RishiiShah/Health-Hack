"""G8b boundaries, comparable observation windows and consistent API/queue output."""
from datetime import timedelta
from dataclasses import replace
from types import SimpleNamespace
import pytest
from app.engine.replay import replay
from app.ops.detect import detect, views_at
from app.ops.overload import overloads
from app.references import Hospital, Physician, Refs, Shift
from app.service import workload_view
from test_accepted_routing import START, event


def scenario(counts, *, until=START + timedelta(hours=2), observed=True, closed=False):
    refs = Refs({'G': Hospital('Hospital', 'America/New_York')},
                {p: Physician(p, (Shift(START-timedelta(hours=3), until),)) for p in counts},
                {p: frozenset({'G'}) for p in counts})
    events = []
    for pid, count in counts.items():
        if observed:
            events.append(event(pid+'online', 'shift_started', START-timedelta(hours=3), pid=pid))
        for n in range(count):
            cid = f'{pid}{n}'
            at = START-timedelta(minutes=30)+timedelta(seconds=n)
            events.extend([event(cid+'r','consult_received',at,cid=cid,hospital_id='G',consult_type='Stroke'),
                           event(cid+'a','physician_assigned',at+timedelta(seconds=1),cid=cid,pid=pid)])
            if closed:
                events.append(event(cid+'s','note_signed',at+timedelta(seconds=2),cid=cid,pid=pid))
    state = replay(events)
    return refs, state, views_at(state, refs, START)


@pytest.mark.parametrize('count,expected', [(2,None),(3,'Warning'),(4,'Critical')])
def test_open_thresholds_do_not_ban_routing(count, expected):
    refs,state,views = scenario({'P':count})
    evidence = overloads(state,views,START)['P']
    assert evidence['level'] == expected
    assert not evidence['rate_available'] and evidence['rate_unavailable_reason'] == 'insufficient peers'
    assert views['P'].routable
    finding = [f for f in detect(state,refs,views,START) if f.kind == 'overload']
    assert [f.severity for f in finding] == ([expected] if expected else [])
    d = SimpleNamespace(views=views)
    row = workload_view(SimpleNamespace(state=state, refs=refs, as_of=START), d)['items'][0]
    assert row['overload'] == expected and row['overload_evidence'] == evidence


def test_warning_with_shift_end_note_risk_is_critical():
    refs,state,views = scenario({'P':3},until=START+timedelta(minutes=60))
    owned = dict(state.consults)
    owned['P0'] = replace(owned['P0'],stage='Documentation',note_pending_since=START-timedelta(minutes=5))
    state = replace(state,consults=owned)
    assert overloads(state,views,START)['P']['level'] == 'Critical'
    earlier = views_at(state,refs,START-timedelta(seconds=1))
    assert earlier['P'].minutes_to_shift_end == 60  # whole minutes must not turn 60m+1s into a risk
    assert overloads(state,earlier,START-timedelta(seconds=1))['P']['level'] == 'Warning'


@pytest.mark.parametrize('count,expected',[(3,None),(4,'Warning')])
def test_rate_requires_strictly_more_than_peer_median(count,expected):
    refs,state,views = scenario({'P':count,'A':2,'B':2,'C':2},closed=True)
    evidence = overloads(state,views,START)['P']
    assert evidence['peer_ids'] == ['A','B','C'] and evidence['peer_median'] == 2
    assert evidence['rate_available'] and evidence['level'] == expected


@pytest.mark.parametrize('observed,peers,reason',[(True,3,'zero peer median'),(True,2,'insufficient peers'),(False,3,'physician not observed for full window')])
def test_missing_comparison_retains_open_work_warning(observed,peers,reason):
    _,state,views = scenario({'P':3,**{str(n):0 for n in range(peers)}},observed=observed)
    e = overloads(state,views,START)['P']
    assert e['level'] == 'Warning' and e['rate_unavailable_reason'] == reason and not e['rate_available']


def test_rate_distinct_window_excludes_lower_boundary_future_and_short_peer():
    refs,state,views = scenario({'P':2,'A':2,'B':2,'C':2},closed=True)
    consults = dict(state.consults)
    consults['P0'] = replace(consults['P0'],assignments=(('P',START-timedelta(hours=2)),))
    consults['P1'] = replace(consults['P1'],assignments=(('P',START),('P',START),('P',START+timedelta(seconds=1))))
    state = replace(state,consults=consults)
    e = overloads(state,views,START)['P']
    assert e['assignments_in_window'] == 1
    views['C'] = replace(views['C'],shift=Shift(START-timedelta(minutes=119), START+timedelta(hours=2)))
    assert overloads(state,views,START)['P']['rate_unavailable_reason'] == 'insufficient peers'
