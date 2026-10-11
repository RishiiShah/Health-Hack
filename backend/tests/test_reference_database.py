"""Reference deployment checks run without the ignored challenge data."""
from dataclasses import replace
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
    monkeypatch.setattr('app.main.settings',replace(settings,reference_dir=None))
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
