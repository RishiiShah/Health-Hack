"""Reference deployment checks run without the ignored challenge data."""
from dataclasses import replace
from datetime import timedelta
from types import SimpleNamespace
from fastapi.testclient import TestClient
from app.config import settings
from app.clock import FixedClock
from app.main import create_app
from app.service import reference_manifest
from conftest import ADMIN, COORD, TEST_AUTH
from test_accepted_routing import START
from test_decision import HEADERS


def files():
    return {
      'hospitals.csv':'hospital_id,hospital_name,local_timezone\nH,Hospital,America/New_York\n',
      'physicians_on_shift.csv':'physician_id,name,shift_start_et,shift_end_et\nP,Physician,06:00,23:00\n',
      'physicians_off_shift_roster.csv':HEADERS['physicians_off_shift_roster.csv']+'\n',
      'credentialing_matrix.csv':'physician_id,name,H\nP,Physician,Y\n',
      'baseline_hourly_volume.csv':HEADERS['baseline_hourly_volume.csv']+'\n'+''.join(f'H,Hospital,weekday,{hour:02}:00,0.5,5,12\n' for hour in range(24)),
      'coverage_requirements.csv':HEADERS['coverage_requirements.csv']+'\nH,Hospital,00:00-12:00,1\nH,Hospital,12:00-00:00,1\n'
    }


def hosted(db_url,monkeypatch):
    monkeypatch.setattr('app.main.settings',replace(settings, reference_fingerprint=None,reference_dir=None))
    return create_app(db_url,FixedClock(START),auth=TEST_AUTH,sweep_s=0,
                      speech=SimpleNamespace(available=False,conn=SimpleNamespace(close=lambda:None)))


def test_persisted_reference_manifest_restart_counts_and_event_retention(db_url,monkeypatch):
    payload={'files':files(),'name':'Synthetic reference version','service_date':'2026-04-07'}
    with TestClient(hosted(db_url,monkeypatch)) as c:
        assert c.get('/admin/references',headers=ADMIN).json()['persisted'] is False
        assert c.get('/admin/references').status_code == 401
        r=c.post('/admin/references',headers=ADMIN,json=payload)
        assert r.status_code == 200,r.text
        token=c.post('/admin/physician-tokens',headers=ADMIN,json={'physician_id':'P'}).json()['token']
        assert c.get('/admin/references',headers={'Authorization':'Bearer '+token}).status_code == 403
        manifest = r.json()['manifest']
        assert manifest == reference_manifest(payload)
        assert len(manifest['files']) == 6
        assert c.post('/events',headers=ADMIN,json={'event_id':'R','event_type':'consult_received','event_time':START.isoformat(),
                                                  'hospital_id':'H','consult_id':'C','consult_type':'Stroke'}).status_code == 200
        assert c.post('/admin/references',headers=ADMIN,json=payload).status_code == 200
        status=c.get('/admin/references',headers=ADMIN).json()
        assert status['manifest']==manifest and status['event_count']==1
        assert (status['hospitals'],status['physicians'])==(1,1)
        assert 'files' not in status and 'source' not in status
    with TestClient(hosted(db_url,monkeypatch)) as c:
        assert c.get('/admin/references',headers=ADMIN).json()['manifest']==manifest
        assert len(c.get('/snapshot',headers=COORD).json()['consults'])==1


def test_manifest_depends_on_files_and_service_date_not_label():
    source={'files':files(),'service_date':'2026-04-07','name':'first'}
    original=reference_manifest(source)
    assert original==reference_manifest({**source,'name':'second','files':dict(reversed(list(source['files'].items())))})
    assert original!=reference_manifest({**source,'service_date':'2026-04-08'})
    assert original!=reference_manifest({**source,'files':{**source['files'],'hospitals.csv':source['files']['hospitals.csv'].replace('Hospital','Another')}})


def test_directory_reference_count_excludes_event_and_snapshot_csvs(db_url, monkeypatch, tmp_path):
    for name, text in files().items():
        (tmp_path / name).write_text(text)
    (tmp_path / 'event_stream.csv').write_text('event_id,event_time\n')
    (tmp_path / 'snapshot_open_consults.csv').write_text('consult_id\n')
    monkeypatch.setattr('app.main.settings', replace(settings, reference_fingerprint=None, reference_dir=str(tmp_path), service_date='2026-04-07'))
    with TestClient(create_app(db_url, FixedClock(START), auth=TEST_AUTH, sweep_s=0,
                              speech=SimpleNamespace(available=False, conn=SimpleNamespace(close=lambda: None)))) as client:
        status = client.get('/admin/references', headers=ADMIN).json()
        assert status['dataset']['reference_files'] == 6
        assert status['event_count'] == 0


def test_unseen_csv_appends_history_updates_decisions_and_preserves_references(db_url, monkeypatch):
    payload = {'files': files(), 'name': 'Unchanged references', 'service_date': '2026-04-07'}
    with TestClient(hosted(db_url, monkeypatch)) as client:
        assert client.post('/admin/references', headers=ADMIN, json=payload).status_code == 200
        assert client.post('/events', headers=COORD, json={
            'event_id': 'OLD', 'event_type': 'consult_received', 'event_time': START.isoformat(),
            'hospital_id': 'H', 'consult_id': 'OLD-CONSULT', 'consult_type': 'Stroke',
        }).status_code == 200
        before = client.get('/admin/references', headers=ADMIN).json()
        persisted = client.app.state.db.metadata('references')
        first, triaged, later = (START + timedelta(minutes=n) for n in (1, 2, 10))
        body = ('event_id,event_time,ingested_at,consult_id,event_type,physician_id,hospital_id,description\n'
                f'NEW-1,{first.isoformat()},{first.isoformat()},NEW-CONSULT,consult_received,,H,Acute stroke consult requested\n'
                f'NEW-TRIAGE,{triaged.isoformat()},{triaged.isoformat()},NEW-CONSULT,consult_triaged,,H,Consult triaged\n'
                f'NEW-2,{later.isoformat()},{later.isoformat()},NEW-CONSULT,consult_received,,H,Stroke consult request received\n')
        response = client.post('/events/csv?advance_clock=true', headers=COORD, content=body)
        assert response.status_code == 200, response.text
        assert response.json()['accepted'] == 3
        snap = client.get('/snapshot', headers=COORD).json()
        assert {c['consult_id'] for c in snap['consults']} == {'OLD-CONSULT', 'NEW-CONSULT'}
        assert any(item['where'].get('consult_id') == 'NEW-CONSULT' and item['severity'] == 'Critical'
                   for item in snap['queue']['items'])
        after = client.get('/admin/references', headers=ADMIN).json()
        assert after['event_count'] == before['event_count'] + 3
        for key in ('manifest', 'reference_revision', 'dataset', 'hospitals', 'physicians'):
            assert after[key] == before[key]
        assert client.app.state.db.metadata('references') == persisted
        # A repeated upload preserves history and produces the same decisions.
        duplicate = client.post('/events/csv?advance_clock=true', headers=COORD, content=body).json()
        assert (duplicate['accepted'], duplicate['duplicates']) == (0, 3)
        assert client.get('/snapshot', headers=COORD).json()['queue'] == snap['queue']


def seed(client):
    response = client.post('/admin/references', headers=ADMIN, json={
        'files': files(), 'name': 'Fixed reference kit', 'service_date': '2026-04-07'})
    assert response.status_code == 200, response.text
    return client.get('/admin/references', headers=ADMIN).json()



def test_baseline_inventory_and_forecast_use_persisted_reference_hours(db_url, monkeypatch):
    with TestClient(hosted(db_url,monkeypatch)) as c:
        assert c.post('/admin/references',headers=ADMIN,json={'files':files(),'service_date':'2026-04-07'}).status_code == 200
        status = c.get('/admin/references',headers=ADMIN).json()
        baseline = status['operational_data']
        assert baseline['baseline_source_rows'] == 24
        assert baseline['baseline_lookup_entries'] == 120
        assert baseline['weeks_sampled'] == [12]
        assert baseline['hospitals'][0]['hours_by_weekday'] == [24,24,24,24,24,0,0]
        snap = c.get('/snapshot',headers=COORD).json()
        demand = snap['demand']
        assert demand['horizon_end'] == snap['coverage']['horizon_end']
        item = demand['items'][0]
        assert item['mean_per_hour'] == 0.5
        assert item['baseline_timezone'] == 'America/New_York'
        assert item['expected_arrivals'] == demand['horizon_minutes'] / 60 * 0.5
        assert item['p90'] == 5 and item['status'] == 'normal'
        # An unseen receipt changes the live observation, never the historical expectation.
        assert c.post('/events',headers=ADMIN,json={'event_id':'unseen','event_type':'consult_received','event_time':START.isoformat(),
                'hospital_id':'H','consult_id':'unseen','consult_type':'Stroke'}).status_code == 200
        after = c.get('/snapshot',headers=COORD).json()['demand']['items'][0]
        assert after['trailing_60m'] == 1
        assert after['expected_arrivals'] == item['expected_arrivals']
        assert c.get('/admin/references',headers=ADMIN).json()['manifest'] == status['manifest']
