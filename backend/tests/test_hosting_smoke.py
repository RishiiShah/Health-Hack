"""The deployment probe must work with fixed references and paused simulation clocks."""
import importlib.util
from pathlib import Path
from types import SimpleNamespace
from fastapi.testclient import TestClient
from app.main import create_app
from app.clock import FixedClock
from conftest import ADMIN, COORD, TEST_AUTH
from test_accepted_routing import START, world


def probe():
    path = Path(__file__).resolve().parents[2] / 'scripts' / 'hosting_smoke.py'
    spec = importlib.util.spec_from_file_location('hosting_smoke', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_hosting_probe_seeds_known_hospital_at_paused_clock_then_verifies(db_url, monkeypatch):
    refs, ops, _ = world()
    app = create_app(db_url, FixedClock(START), auth=TEST_AUTH, references=(refs,ops), sweep_s=0,
                     speech=SimpleNamespace(available=False,close=lambda: None))
    smoke = probe()
    monkeypatch.setenv('CC_ADMIN_TOKEN','admin-token')
    monkeypatch.setenv('CC_COORDINATOR_TOKEN','coord-token')
    with TestClient(app) as client:
        def request(url, payload=None, token=None):
            headers = {'Authorization':'Bearer '+token} if token else {}
            response = client.request('GET' if payload is None else 'POST',url.replace('http://testserver',''),headers=headers,json=payload)
            response.raise_for_status()
            return response.json()
        monkeypatch.setattr(smoke,'request',request)
        fingerprint = app.state.coordinator.refs.payload()
        for operation in ('seed','verify','seed'):
            monkeypatch.setattr('sys.argv',['hosting_smoke.py',operation,'--url','http://testserver'])
            smoke.main()
        snapshot = client.get('/snapshot',headers=COORD).json()
        consult = next(c for c in snapshot['consults'] if c['consult_id']=='hosting-smoke-consult')
        assert consult['hospital_id'] == sorted(refs.hospitals)[0]
        assert app.state.coordinator.refs.payload() == fingerprint
        assert snapshot['clock']['now'] == START.isoformat()
        assert client.get('/admin/references',headers=ADMIN).json()['event_count'] == 1
