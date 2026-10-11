"""Runtime bootstraps the official kit; the active kit is never replaced by a reference upload, only stored beside."""
from dataclasses import replace
from types import SimpleNamespace
import pytest
from fastapi.testclient import TestClient
from app import main
from app.clock import FixedClock
from app.config import Settings, OFFICIAL_REFERENCE_FINGERPRINT
from app.service import reference_manifest
from conftest import ADMIN, TEST_AUTH
from test_reference_database import files, hosted, seed
from test_accepted_routing import START


@pytest.mark.parametrize('change', ['name', 'baseline', 'service_date'])
def test_initialized_reference_kit_is_kept_and_a_changed_kit_is_stored(db_url, monkeypatch, change):
    with TestClient(hosted(db_url, monkeypatch)) as client:
        before = seed(client)
        changed = files()
        payload = {'files': changed, 'name': 'Replacement', 'service_date': '2026-04-07'}
        if change == 'name': changed['hospitals.csv'] = changed['hospitals.csv'].replace('Hospital,', 'Changed,')
        if change == 'baseline': changed['baseline_hourly_volume.csv'] = changed['baseline_hourly_volume.csv'].replace('0.5,5,12', '2,8,12')
        if change == 'service_date': payload['service_date'] = '2026-04-08'
        response = client.post('/admin/references', headers=ADMIN, json=payload)
        assert response.status_code == 200
        assert (response.json()['activated'], response.json()['stored']) == (False, True)
        after = client.get('/admin/references', headers=ADMIN).json()
        assert {k: v for k, v in after.items() if k != 'kits'} == {k: v for k, v in before.items() if k != 'kits'}
        assert len(after['kits']) == 2 and sum(k['active'] for k in after['kits']) == 1


def test_matching_reference_upload_is_read_only_and_keeps_label(db_url, monkeypatch):
    with TestClient(hosted(db_url, monkeypatch)) as client:
        before = seed(client)
        response = client.post('/admin/references', headers=ADMIN, json={
            'files': files(), 'name': 'Different label', 'service_date': '2026-04-07'})
        assert response.status_code == 200
        assert response.json()['unchanged'] is True
        assert client.get('/admin/references', headers=ADMIN).json() == before



def test_runtime_default_is_the_official_sevaro_fingerprint():
    assert Settings().reference_fingerprint == OFFICIAL_REFERENCE_FINGERPRINT


def test_wrong_bootstrap_and_tampered_restart_are_rejected(db_url, monkeypatch):
    pin = reference_manifest({'files': files(), 'service_date': '2026-04-07'})['fingerprint']
    monkeypatch.setattr(main, 'settings', replace(main.settings, reference_dir=None, reference_fingerprint=pin))
    def pinned():
        return main.create_app(db_url, FixedClock(START), auth=TEST_AUTH, sweep_s=0,
                               speech=SimpleNamespace(available=False, conn=SimpleNamespace(close=lambda: None)))
    with TestClient(pinned()) as client:
        changed = files()
        changed['hospitals.csv'] = changed['hospitals.csv'].replace('Hospital,', 'Changed,')
        assert client.post('/admin/references', headers=ADMIN, json={'files': changed, 'service_date': '2026-04-07'}).status_code == 409
        seed(client)
        db = client.app.state.db
        saved = db.metadata('references')
        saved['source']['files']['baseline_hourly_volume.csv'] += '\n'
        import json
        db.conn.execute("UPDATE metadata SET value=%s WHERE key='references'", (json.dumps(saved),))
    with pytest.raises(ValueError, match='official Sevaro kit or a stored reference kit'):
        with TestClient(pinned()): pass
