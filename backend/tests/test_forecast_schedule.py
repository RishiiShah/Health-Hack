"""Shared forecast horizon and live schedule are checked on a synthetic roster."""
from dataclasses import replace
from datetime import timedelta
from types import SimpleNamespace
from fastapi.testclient import TestClient
from app.clock import FixedClock
from app.models import EventInput
from app.main import create_app
from app.ops.coverage import forecast_steps, project
from app.ops.detect import views_at
from app.ops.refs import ET
from app.references import Physician, Refs, Shift
from conftest import ADMIN, COORD, LEAD, TEST_AUTH
from test_accepted_routing import START, event, world
from app.engine.replay import replay


def scenario():
    now=START.replace(hour=22,minute=20)
    refs,ops,_=world()
    refs=Refs(refs.hospitals,{p:Physician(p,(Shift(now-timedelta(hours=3),now+timedelta(minutes=n)),))
                            for p,n in [('A',40),('B',100)]},
              {'A':frozenset({'G'}),'B':frozenset({'G'})})
    return now, refs, replace(ops,roster={})


def test_final_cliff_between_regular_steps_is_in_grid_and_gap_flags():
    now,refs,ops=scenario()
    state=replay(())
    steps=forecast_steps(refs,ops,now)
    assert steps[-1] == now+timedelta(minutes=100)
    assert now+timedelta(minutes=40) in steps and now+timedelta(minutes=90) in steps
    gaps=project(state,refs,ops,views_at(state,refs,now),now)
    assert any(g.start == steps[-1] and g.kind=='hard' and g.in_horizon for g in gaps)
    later=Refs(refs.hospitals,{**refs.physicians,'B':Physician('B',(Shift(now-timedelta(hours=3),now+timedelta(minutes=121)),))},refs.credentials)
    assert forecast_steps(later,ops,now)[-1] == now+timedelta(minutes=90)


def test_live_grid_schedule_headline_and_recommendation_evidence(db_url,tmp_path):
    now,refs,ops=scenario()
    app=create_app(db_url,FixedClock(now),auth=TEST_AUTH,references=(refs,ops),history_path=tmp_path/'absent',sweep_s=0,
                   speech=SimpleNamespace(available=False,conn=SimpleNamespace(close=lambda:None)))
    with TestClient(app) as c:
        assert c.get('/schedule').status_code==401
        snapshot=c.get('/snapshot',headers=COORD).json()
        assert snapshot['headline']['forecast_horizon_minutes']==100
        grid=snapshot['coverage']
        assert grid['horizon_end']==(now+timedelta(minutes=100)).isoformat()
        g=next(h for h in grid['hospitals'] if h['hospital_id']=='G')
        assert g['cells'][-1]['count']==0 and g['cells'][-1]['status']=='gap'
        assert snapshot['headline']['hospitals_short_in_horizon']==1
        schedule=c.get('/schedule',headers=LEAD).json()
        assert schedule['date']==now.astimezone(ET).date().isoformat()
        assert {d['id'] for d in schedule['doctors']}=={'A','B'}
        assert all(d['group']=='On shift' and d['intervals'][0]['source']=='scheduled' for d in schedule['doctors'])
        trail=app.state.engine.desk.audit()
        recommendations=[r for r in trail if r['command']=='recommendation']
        assert recommendations and all(r['detail']['fix']['action'] for r in recommendations)
        c.get('/snapshot',headers=COORD)
        assert app.state.engine.desk.audit()==trail  # reading the cached pass does not duplicate history
        evidence=c.get('/audit',headers=LEAD).json()['items'][0]['evidence']
        assert 'fix' in evidence and 'candidates' in evidence and 'gaps' in evidence
    restarted=create_app(db_url,FixedClock(now),auth=TEST_AUTH,references=(refs,ops),history_path=tmp_path/'absent',sweep_s=0,
                         speech=SimpleNamespace(available=False,conn=SimpleNamespace(close=lambda:None)))
    with TestClient(restarted) as c:
        c.get('/snapshot',headers=COORD)
        assert restarted.state.engine.desk.audit()==trail


def test_schedule_distinguishes_pending_accepted_arrived_and_incomplete(db_url,tmp_path):
    refs,ops,_=world()
    clock=FixedClock(START-timedelta(minutes=20))
    app=create_app(db_url,clock,auth=TEST_AUTH,references=(refs,ops),history_path=tmp_path/'absent',sweep_s=0,
                   speech=SimpleNamespace(available=False,conn=SimpleNamespace(close=lambda:None)))
    with TestClient(app) as c:
        o=c.post('/offers',headers=COORD,json={'gap_id':'now_gap:G','physician_id':'J','start':START.isoformat(),
                                              'end':(START+timedelta(hours=2)).isoformat(),'hospitals':['G']}).json()
        row=c.get('/schedule',headers=LEAD).json()['doctors'][0]
        assert row['tone']=='offer' and 'not confirmed' in row['detail'] and row['intervals']==[]
        oid=o['offer_id']
        assert c.post(f'/offers/{oid}/approve',headers=LEAD).status_code==200
        token=c.post('/admin/physician-tokens',headers=ADMIN,json={'physician_id':'J'}).json()['token']
        physician={'Authorization':'Bearer '+token}
        assert c.get('/schedule',headers=physician).status_code==403
        assert c.post(f'/offers/{oid}/accept',headers=physician).status_code==200
        c.post('/admin/clock',headers=ADMIN,json={'at':START.isoformat()})
        row=c.get('/schedule',headers=LEAD).json()['doctors'][0]
        assert row['status']=='Accepted; awaiting observed arrival' and row['group']=='Off shift'
        assert row['intervals'][0]['source']=='accepted'
        e=event('online','shift_started',START,pid='J')
        response=c.post('/events',headers=ADMIN,json=e.model_dump(mode='json',include=set(EventInput.model_fields)))
        assert response.status_code==200,response.text
        assert c.get('/schedule',headers=LEAD).json()['doctors'][0]['group']=='On shift'
        roster=replace(ops.roster['J'],next_shift_start=START+timedelta(hours=3),next_shift_end=None)
        app.state.engine.ops=replace(ops,roster={'J':roster})
        row=c.get('/schedule',headers=LEAD).json()['doctors'][0]
        assert 'end unknown' in row['detail'] and len(row['intervals'])==1
