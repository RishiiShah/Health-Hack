"""Clean-checkout HTTP checks: no challenge CSVs, external speech, or answer keys."""
from dataclasses import replace
from datetime import timedelta
import json
import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect
from app.auth import Accounts, Auth
from app.clock import FixedClock
from app.main import create_app
from app.passwords import hash_password
from conftest import ADMIN, COORD, LEAD, TEST_AUTH
from test_accepted_routing import START, END, world


class SyntheticSpeech:
    available = True
    def close(self):
        pass

    def audio(self, text):
        assert 'PATIENT' not in text and 'CONSULT' not in text
        return b'ID3-synthetic'


def test_trap_unknown_demand_is_exposed_in_api_and_queue(db_url, tmp_path, monkeypatch):
    refs, ops, _ = world()
    ops = replace(ops, baseline={k: v for k, v in ops.baseline.items() if k[0] != 'H'})
    ops = replace(ops, roster={**ops.roster, 'J': replace(ops.roster['J'], minutes_to_online=0)})
    monkeypatch.setattr('app.service.observed_service', lambda *args: {'*': 6.5})
    api = create_app(db_url, FixedClock(START - timedelta(minutes=20)), auth=TEST_AUTH,
                     references=(refs, ops), history_path=tmp_path/'absent', speech=SyntheticSpeech(), sweep_s=0)
    with TestClient(api) as c:
        items = c.get('/snapshot', headers=COORD).json()['queue']['items']
        item = next(i for i in items if i['fix']['kind'] == 'split_shift')
        assert item['why']['trap_guard']['unknown_demand'] == ['H']
        assert 'trap check unknown' in item['fix']['reason']
        check = c.get(f"/gaps/{item['id']}/trap-check", headers=LEAD).json()
        assert check['passed'] is False and check['unknown_demand'] == ['H']
        assert any('unknown' in r and 'H' in r for r in check['reasons'])
        assert 'Partial demand model' in check['assumption']
        raw = api.state.engine.trap(api.state.engine.item(item['id']))
        assert raw['unknown_demand'] == ['H'] and not raw['passed']


def test_authenticated_live_ingest_media_reset_and_recovery_without_packs(db_url, tmp_path):
    refs, ops, _ = world()
    api = create_app(db_url, FixedClock(START - timedelta(minutes=20)), auth=TEST_AUTH,
                     references=(refs, ops), history_path=tmp_path/'absent', speech=SyntheticSpeech(), sweep_s=0)
    with TestClient(api) as c:
        assert c.get('/snapshot').status_code == 401
        assert c.get('/offers', headers=COORD).status_code == 200
        physician = {'Authorization': 'Bearer '+c.post('/admin/physician-tokens', headers=ADMIN,
                       json={'physician_id':'J'}).json()['token']}
        assert c.get('/snapshot', headers=physician).status_code == 403
        assert c.get('/me', headers=physician).json()['physician_id'] == 'J'
        assert c.get('/me/shift', headers=physician).json()['on_shift'] is False
        assert c.post('/admin/clock', headers=physician, json={'at':START.isoformat()}).status_code == 403
        snapshot = c.get('/snapshot', headers=COORD).json()
        epoch = snapshot['epoch']
        with c.websocket_connect('/ws?token=coord-token') as ws:
            message = ws.receive_json()
            assert message['epoch'] == epoch and message['snapshot']['queue']['supported']
        with pytest.raises(WebSocketDisconnect) as denied:
            with c.websocket_connect('/ws?token=wrong'):
                pass
        assert denied.value.code == 1008
        # The lead's command sends only after server-side eligibility and approval.
        offer = c.post('/offers', headers=COORD, json={'gap_id':'now_gap:G','physician_id':'J',
                       'start':START.isoformat(),'end':END.isoformat(),'hospitals':['G']})
        assert offer.status_code == 200, offer.text
        oid = offer.json()['offer_id']
        assert c.post(f'/offers/{oid}/approve', headers=COORD).status_code == 403
        assert c.get('/offers', headers=physician).json()['items'] == []
        assert c.get(f'/offers/{oid}', headers=physician).status_code == 404
        assert c.get(f'/offers/{oid}', headers=LEAD).status_code == 200
        assert c.get(f'/offers/{oid}/audio', headers=physician).status_code == 404
        assert c.get(f'/offers/{oid}/audio', headers=LEAD).status_code == 409
        sent = c.post(f'/offers/{oid}/approve', headers=LEAD)
        assert sent.status_code == 200, sent.text
        assert c.get('/offers', headers=physician).json()['items'][0]['offer_id'] == oid
        assert c.get(f'/offers/{oid}', headers=physician).status_code == 200
        assert c.get(f'/offers/{oid}/audio').status_code == 401
        audio = c.get(f'/offers/{oid}/audio', headers=physician)
        assert audio.status_code == 200 and audio.content == b'ID3-synthetic'
        assert c.get(f'/offers/{oid}/audio', headers=COORD).status_code == 403
        assert c.post(f'/offers/{oid}/accept', headers=physician).status_code == 200
        critical = next(i for i in snapshot['queue']['items'] if i['severity']=='Critical')
        assert c.get(f"/alerts/{critical['id']}/audio", headers=COORD).status_code == 200
        assert c.get(f"/alerts/{critical['id']}/audio", headers=physician).status_code == 403
        # A late delivery becomes visible when the persisted injected clock advances.
        csv = ('event_id,event_time,ingested_at,consult_id,event_type,physician_id,hospital_id,description\n'
               f'SYNTHETIC-RECEIPT,{START.isoformat()},{START.isoformat()},SYNTHETIC-CONSULT,consult_received,,G,Acute stroke consult requested\n')
        ingested = c.post('/events/csv', headers={**ADMIN,'Content-Type':'text/csv'}, content=csv.encode()).json()
        assert ingested['accepted']==1 and ingested['pending_future']==1
        duplicate = c.post('/events/csv', headers={**ADMIN,'Content-Type':'text/csv'}, content=csv.encode()).json()
        assert duplicate['accepted']==0 and duplicate['duplicates']==1
        assert c.post('/admin/clock', headers=ADMIN, json={'at':START.isoformat()}).status_code == 200
        assert c.get('/snapshot', headers=COORD).json()['consults'][0]['consult_id']=='SYNTHETIC-CONSULT'
    restarted = create_app(db_url, auth=TEST_AUTH, references=(refs,ops), history_path=tmp_path/'absent',
                           speech=SyntheticSpeech(), sweep_s=0)
    with TestClient(restarted) as c:
        snapshot = c.get('/snapshot', headers=COORD).json()
        assert snapshot['clock']['now']==START.isoformat()
        assert len(snapshot['consults'])==1
        assert c.get('/me/offers', headers=physician).json()['items'][0]['state']=='Accepted'
        assert c.post('/admin/reset', headers=ADMIN).json()['reset']
        fresh = c.get('/snapshot', headers=COORD).json()
        assert fresh['epoch']!=epoch and fresh['consults']==[] and fresh['offers']['items']==[]


def test_password_login_and_current_role_permissions_without_packs(db_url, tmp_path):
    password_hash = hash_password('test-only-password', iterations=1000)
    users = json.dumps([{'email':f'{role}@example.test','name':role,'role':role,'password_hash':password_hash,
                        **({'physician_id':'J'} if role=='physician' else {})} for role in ('coordinator','lead','physician')])
    auth = Auth(accounts=Accounts(users, 'synthetic-signing-secret-for-clean-ci'))
    refs,ops,_ = world()
    with TestClient(create_app(db_url,FixedClock(START),auth=auth,references=(refs,ops),history_path=tmp_path/'absent',
                              speech=SyntheticSpeech(),sweep_s=0)) as c:
        assert c.post('/auth/login',json={'email':'lead@example.test','password':'wrong'}).status_code==401
        for role in ('coordinator','lead','physician'):
            login=c.post('/auth/login',json={'email':f'{role}@example.test','password':'test-only-password'})
            assert login.status_code==200,login.text
            headers={'Authorization':'Bearer '+login.json()['token']}
            assert c.get('/auth/me',headers=headers).json()['user']['role']==role
            assert c.get('/snapshot',headers=headers).status_code==(403 if role=='physician' else 200)
            assert c.get('/me/shift',headers=headers).status_code==(200 if role=='physician' else 403)
