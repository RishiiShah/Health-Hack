"""Stored reference kits: an events-only CSV whose IDs belong to another stored kit switches to it; unknown IDs are refused."""
from dataclasses import replace
from datetime import timedelta
from threading import Thread
from time import sleep
from types import SimpleNamespace
from fastapi.testclient import TestClient
from app import main
from app.clock import FixedClock
from app.service import reference_manifest
from conftest import ADMIN, COORD, TEST_AUTH
from test_accepted_routing import START
from test_reference_database import files, hosted, seed

COLUMNS = 'event_id,event_time,ingested_at,consult_id,event_type,physician_id,hospital_id,description\n'


def second_kit():
    """The same shape as files(), with hospital H2 and physician P2 in place of H and P."""
    kit = {name: text.replace('\nH,', '\nH2,').replace('\nP,', '\nP2,') for name, text in files().items()}
    kit['credentialing_matrix.csv'] = kit['credentialing_matrix.csv'].replace('physician_id,name,H\n', 'physician_id,name,H2\n')
    return kit


def events(hospital, physician, prefix, minutes=(1, 2)):
    first, later = (START + timedelta(minutes=m) for m in minutes)
    return (COLUMNS + f'{prefix}-1,{first.isoformat()},{first.isoformat()},{prefix}-C,consult_received,,{hospital},Acute stroke consult requested\n'
            f'{prefix}-2,{later.isoformat()},{later.isoformat()},,physician_status_changed,{physician},,Self-reported status: Available\n')


def store_second(client):
    response = client.post('/admin/references', headers=ADMIN, json={'files': second_kit(), 'name': 'Second kit', 'service_date': '2026-04-07'})
    assert response.status_code == 200, response.text
    return response.json()


def upload(client, body):
    return client.post('/events/csv?advance_clock=true', headers=COORD, content=body)


def test_a_different_kit_is_stored_without_replacing_the_active_one(db_url, monkeypatch):
    with TestClient(hosted(db_url, monkeypatch)) as client:
        before = seed(client)
        stored = store_second(client)
        assert (stored['activated'], stored['stored']) == (False, True)
        after = client.get('/admin/references', headers=ADMIN).json()
        for key in ('manifest', 'dataset', 'reference_revision', 'hospitals', 'physicians'):
            assert after[key] == before[key]
        second = reference_manifest({'files': second_kit(), 'service_date': '2026-04-07'})['fingerprint']
        kits = {k['fingerprint']: k for k in after['kits']}
        assert kits[second] == {'fingerprint': second, 'name': 'Second kit', 'service_date': '2026-04-07',
                                'hospitals': 1, 'physicians': 1, 'active': False}
        assert kits[before['manifest']['fingerprint']]['active'] is True


def test_events_for_a_stored_kit_switch_to_a_fresh_stream_on_that_kit(db_url, monkeypatch):
    with TestClient(hosted(db_url, monkeypatch)) as client:
        seed(client)
        assert upload(client, events('H', 'P', 'OLD')).json()['accepted'] == 2
        store_second(client)
        response = upload(client, events('H2', 'P2', 'NEW', minutes=(-30, -20)))
        assert response.status_code == 200, response.text
        report = response.json()
        assert report['dataset_switched_to']['name'] == 'Second kit'
        assert (report['accepted'], report['held_orphans']) == (2, 0)
        # A fresh stream: the clock moves to the file's latest event, even backwards, and old consults are gone.
        assert report['clock_advanced_to'] == (START - timedelta(minutes=20)).isoformat()
        snap = client.get('/snapshot', headers=COORD).json()
        assert {c['consult_id'] for c in snap['consults']} == {'NEW-C'}
        assert snap['dataset']['name'] == 'Second kit'
        status = client.get('/admin/references', headers=ADMIN).json()
        assert (status['event_count'], status['manifest']['fingerprint']) == (2, report['dataset_switched_to']['fingerprint'])
        # Uploading the first kit's events switches back the same way.
        back = upload(client, events('H', 'P', 'AGAIN')).json()
        assert back['dataset_switched_to']['name'] == 'Fixed reference kit'
        assert {c['consult_id'] for c in client.get('/snapshot', headers=COORD).json()['consults']} == {'AGAIN-C'}


def test_a_kit_stored_twice_with_other_line_endings_is_one_match(db_url, monkeypatch):
    with TestClient(hosted(db_url, monkeypatch)) as client:
        seed(client)
        store_second(client)
        crlf = {name: text.replace('\n', '\r\n') for name, text in second_kit().items()}
        stored = client.post('/admin/references', headers=ADMIN, json={'files': crlf, 'name': 'uploaded references', 'service_date': '2026-04-07'})
        assert stored.json().get('stored'), stored.text
        report = upload(client, events('H2', 'P2', 'NEW', minutes=(-30, -20))).json()
        assert report['dataset_switched_to']['name'] == 'Second kit'
        assert client.get('/snapshot', headers=COORD).json()['dataset']['name'] == 'Second kit'


def test_a_kit_switch_does_not_deadlock_with_a_desk_command(db_url, monkeypatch):
    """A desk command holds the desk lock while it reads the context; a switching upload must not hold swap meanwhile."""
    with TestClient(hosted(db_url, monkeypatch)) as client:
        seed(client)
        store_second(client)
        engine = client.app.state.engine
        with engine.desk.lock:  # as a desk command does, before it calls context()
            switch = Thread(target=upload, args=(client, events('H2', 'P2', 'NEW', minutes=(-30, -20))), daemon=True)
            switch.start()
            sleep(0.3)  # let the upload take whatever it takes first
            read = Thread(target=engine.context, daemon=True)
            read.start()
            read.join(3)
            assert not read.is_alive(), 'context() blocked behind the upload: lock-order deadlock'
        switch.join(10)
        assert not switch.is_alive()
        assert client.get('/snapshot', headers=COORD).json()['dataset']['name'] == 'Second kit'


def test_events_matching_no_stored_kit_are_refused_without_holds(db_url, monkeypatch):
    with TestClient(hosted(db_url, monkeypatch)) as client:
        before = seed(client)
        response = upload(client, events('H9', 'P9', 'X'))
        assert response.status_code == 422
        assert 'H9' in response.json()['detail'] and 'P9' in response.json()['detail']
        snap = client.get('/snapshot', headers=COORD).json()
        assert snap['data_quality']['pending_orphans'] == 0
        assert client.get('/admin/references', headers=ADMIN).json()['event_count'] == before['event_count']


def test_a_file_that_shares_ids_with_the_active_kit_appends_as_before(db_url, monkeypatch):
    with TestClient(hosted(db_url, monkeypatch)) as client:
        seed(client)
        store_second(client)
        report = upload(client, events('H', 'P2', 'MIX')).json()
        assert 'dataset_switched_to' not in report
        assert (report['accepted'], report['held_orphans']) == (1, 1)  # P2 is not on the active roster: the usual G4 hold


def test_restart_recovers_a_switched_kit_under_the_official_pin(db_url, monkeypatch):
    pin = reference_manifest({'files': files(), 'service_date': '2026-04-07'})['fingerprint']
    monkeypatch.setattr(main, 'settings', replace(main.settings, reference_dir=None, reference_fingerprint=pin))
    def pinned():
        return main.create_app(db_url, FixedClock(START), auth=TEST_AUTH, sweep_s=0,
                               speech=SimpleNamespace(available=False, close=lambda: None))
    with TestClient(pinned()) as client:
        # The first kit must be the official one; others are stored beside it.
        assert client.post('/admin/references', headers=ADMIN, json={'files': second_kit(), 'service_date': '2026-04-07'}).status_code == 409
        seed(client)
        store_second(client)
        assert upload(client, events('H2', 'P2', 'NEW', minutes=(-30, -20))).json()['dataset_switched_to']['name'] == 'Second kit'
    with TestClient(pinned()) as client:  # the injected clock is START, after the events
        snap = client.get('/snapshot', headers=COORD).json()
        assert snap['dataset']['name'] == 'Second kit'
        assert {c['consult_id'] for c in snap['consults']} == {'NEW-C'}


def test_a_server_behind_the_shared_database_does_not_judge_offers(db_url, monkeypatch):
    """Another server committed (new events, a kit switch): this one's sweep must not cancel offers on a stale view."""
    import psycopg, pytest
    from app.act.offers import OfferError
    with TestClient(hosted(db_url, monkeypatch)) as client:
        seed(client)
        desk = client.app.state.engine.desk
        desk.sweep()  # in step with the database: fine
        with psycopg.connect(db_url, autocommit=True) as other:
            other.execute("UPDATE metadata SET value=(value::int + 1)::text WHERE key='revision'")
        with pytest.raises(OfferError) as refused:
            desk.sweep()
        assert refused.value.code == 'stale_server'


def test_the_audit_view_returns_only_the_newest_rows(db_url, monkeypatch):
    from app import service
    monkeypatch.setattr(service, 'AUDIT_ROWS', 2)
    with TestClient(hosted(db_url, monkeypatch)) as client:
        seed(client)
        desk = client.app.state.engine.desk
        for actor in ('a', 'b', 'c'):
            desk.reset(actor, START)
        items = client.get('/audit', headers=COORD).json()['items']
        assert [i['actor'] for i in items] == ['b', 'c']


def test_a_restart_does_not_wait_for_another_server_reading_offers(db_url, monkeypatch):
    """A second server mid-transaction on offers must not block (and time out) this one's startup."""
    import psycopg
    with TestClient(hosted(db_url, monkeypatch)):
        pass  # the schema exists
    with psycopg.connect(db_url) as other:  # a transaction left open, as a stuck server leaves it
        other.execute("SELECT * FROM offers")
        with TestClient(hosted(db_url, monkeypatch)) as client:
            assert client.get('/ready').status_code == 200


def test_an_admin_switches_to_a_stored_kit_and_its_clock_waits_paused_at_18_20(db_url, monkeypatch):
    from datetime import datetime
    from zoneinfo import ZoneInfo
    with TestClient(hosted(db_url, monkeypatch)) as client:
        before = seed(client)
        upload(client, events('H', 'P', 'OLD'))
        second = store_second(client)['manifest']['fingerprint']
        switched = client.post('/admin/references/activate', headers=ADMIN, json={'fingerprint': second})
        assert switched.status_code == 200, switched.text
        start = datetime(2026, 4, 7, 18, 20, tzinfo=ZoneInfo('America/New_York'))
        assert switched.json()['paused'] is True and datetime.fromisoformat(switched.json()['now']) == start
        snap = client.get('/snapshot', headers=COORD).json()
        assert (snap['dataset']['name'], snap['consults']) == ('Second kit', [])
        assert client.get('/admin/references', headers=ADMIN).json()['event_count'] == 0
        # Back to the first kit the same way: its events are not carried over.
        assert client.post('/admin/references/activate', headers=ADMIN, json={'fingerprint': before['manifest']['fingerprint']}).status_code == 200
        assert client.get('/snapshot', headers=COORD).json()['consults'] == []
        assert client.post('/admin/references/activate', headers=ADMIN, json={'fingerprint': 'nope'}).status_code == 404


def test_a_stored_kit_uploaded_again_without_a_date_uses_its_stored_date(db_url, monkeypatch):
    with TestClient(hosted(db_url, monkeypatch)) as client:
        seed(client)
        store_second(client)
        kits = len(client.get('/admin/references', headers=ADMIN).json()['kits'])
        again = client.post('/admin/references', headers=ADMIN, json={'files': second_kit(), 'name': 'Second kit'})
        assert again.status_code == 200, again.text
        assert len(client.get('/admin/references', headers=ADMIN).json()['kits']) == kits
