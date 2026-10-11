"""Regression requirements from the fixed-reference and CSV-ingestion audit."""
import csv
import hashlib
import io
from dataclasses import replace
from datetime import timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from app.config import settings
from app.service import reference_manifest
from conftest import ADMIN, COORD
from test_reference_database import files, hosted, seed
from test_accepted_routing import START

FIELDS = 'event_id,event_time,ingested_at,consult_id,event_type,physician_id,hospital_id,description'.split(',')


def csv_body(*rows):
    stream = io.StringIO()
    writer = csv.DictWriter(stream, FIELDS)
    writer.writeheader()
    for row in rows:
        writer.writerow({'event_id': 'R', 'event_time': START.isoformat(), 'ingested_at': START.isoformat(),
                         'consult_id': 'C', 'event_type': 'consult_received', 'hospital_id': 'H',
                         'description': 'Stroke consult request received', **row})
    return stream.getvalue()


def upload(client, body, name='unseen.csv'):
    return client.post('/events/csv?advance_clock=true', headers={**COORD, 'X-Upload-Filename': name}, content=body)


def test_rejected_held_and_duplicate_future_rows_do_not_move_clock(db_url, monkeypatch):
    with TestClient(hosted(db_url, monkeypatch)) as client:
        seed(client)
        before = client.get('/snapshot', headers=COORD).json()['clock']['now']
        future = (START + timedelta(days=100)).isoformat()
        report = upload(client, csv_body({'event_time': future, 'ingested_at': future, 'event_type': 'unsupported_event'})).json()
        assert report['accepted'] == 0
        assert client.get('/snapshot', headers=COORD).json()['clock']['now'] == before
        # A file whose only IDs match no stored kit is refused whole.
        assert upload(client, csv_body({'event_time': future, 'ingested_at': future, 'hospital_id': 'UNKNOWN'})).status_code == 422
        assert client.get('/snapshot', headers=COORD).json()['clock']['now'] == before


def test_clock_moves_only_to_accepted_rows_and_commits_with_events(db_url, monkeypatch):
    with TestClient(hosted(db_url, monkeypatch)) as client:
        seed(client)
        good = (START + timedelta(minutes=10)).isoformat()
        bad = (START + timedelta(days=100)).isoformat()
        report = upload(client, csv_body({'event_id': 'GOOD', 'event_time': good, 'ingested_at': good},
                                        {'event_id': 'BAD', 'event_time': bad, 'ingested_at': bad, 'event_type': 'unsupported_event'})).json()
        assert report['clock_advanced_to'] == good
        assert report['row_results'][0]['pending_future'] is False
        coord = client.app.state.coordinator
        original = coord.db.commit_batch
        def fail_clock(*args, **kwargs):
            if kwargs.get('clock'): raise RuntimeError('clock transaction failed')
            return original(*args, **kwargs)
        monkeypatch.setattr(coord.db, 'commit_batch', fail_clock)
        with pytest.raises(RuntimeError, match='clock transaction failed'):
            upload(client, csv_body({'event_id': 'FAILED', 'consult_id': 'FAILED-C',
                                    'event_time': (START + timedelta(minutes=20)).isoformat(),
                                    'ingested_at': (START + timedelta(minutes=20)).isoformat()}))
        assert 'FAILED' not in {e.event_id for e in coord.db.events()}


def test_row_results_and_totals_identify_missing_dependencies_and_conflicts(db_url, monkeypatch):
    with TestClient(hosted(db_url, monkeypatch)) as client:
        seed(client)
        assert upload(client, csv_body({})).json()['accepted'] == 1
        body = csv_body({'description': 'General Neuro consult request received'},
                        {'event_id': 'ORPHAN', 'consult_id': 'MISSING', 'event_type': 'consult_triaged', 'description': 'Consult triaged'},
                        {'event_id': 'UNKNOWN', 'hospital_id': 'UNKNOWN-H', 'physician_id': 'UNKNOWN-P'},
                        {'event_id': 'BAD', 'event_type': 'unsupported_event'})
        report = upload(client, body).json()
        results = {r['event_id']: r for r in report['row_results']}
        assert results['R']['status'] == 'conflict' and results['R']['row_number'] == 2
        assert 'consult_received' in results['ORPHAN']['reason']
        assert 'UNKNOWN-H' in results['UNKNOWN']['reason'] and 'UNKNOWN-P' in results['UNKNOWN']['reason']
        assert results['BAD']['status'] == 'quarantined'
        quality = client.get('/snapshot', headers=COORD).json()['data_quality']
        assert quality['events_read'] == 5
        assert quality['accepted_events'] == 1


def test_upload_batches_survive_restart_navigation_and_reset(db_url, monkeypatch):
    body = csv_body({})
    with TestClient(hosted(db_url, monkeypatch)) as client:
        seed(client)
        report = upload(client, body, 'judge.csv').json()
        assert report['batch_id']
        batches = client.get('/admin/uploads', headers=COORD).json()['items']
        assert len(batches) == 1
        batch = batches[0]
        assert batch['filename'] == 'judge.csv'
        assert batch['sha256'] == hashlib.sha256(body.encode()).hexdigest()
        assert batch['actor'] == 'Coordinator'
        assert batch['consult_ids'] == ['C']
        assert batch['report']['accepted'] == 1
        assert batch['reference_fingerprint'] == reference_manifest({'files': files(), 'service_date': '2026-04-07'})['fingerprint']
        assert client.get('/admin/uploads').status_code == 401
        event = client.app.state.db.events()[0]
        assert event.source == 'upload:' + report['batch_id']
    with TestClient(hosted(db_url, monkeypatch)) as client:
        assert client.get('/admin/uploads', headers=COORD).json()['items'][0]['batch_id'] == batch['batch_id']
        assert client.post('/admin/reset', headers=ADMIN).status_code == 200
        assert client.get('/admin/uploads', headers=COORD).json()['items'][0]['batch_id'] == batch['batch_id']


def test_invalid_csv_encoding_and_headers_return_actionable_errors(db_url, monkeypatch):
    with TestClient(hosted(db_url, monkeypatch)) as client:
        seed(client)
        assert upload(client, b'\xff').status_code == 422
        assert upload(client, 'wrong,columns\n1,2\n').status_code == 422
        assert upload(client, ','.join(FIELDS) + '\n').status_code == 422


def test_valid_large_date_jump_is_pending_and_duplicate_does_not_advance(db_url, monkeypatch):
    with TestClient(hosted(db_url, monkeypatch)) as client:
        seed(client)
        future = (START + timedelta(days=2)).isoformat()
        body = csv_body({'event_time': future, 'ingested_at': future})
        report = upload(client, body).json()
        assert report['accepted'] == 1 and report['pending_future'] == 1
        assert report['row_results'][0]['pending_future'] is True
        assert '24 hours' in report['clock_warning']
        assert client.get('/snapshot', headers=COORD).json()['clock']['now'] == START.isoformat()
        repeated = upload(client, body).json()
        assert repeated['duplicates'] == 1
        assert 'clock_advanced_to' not in repeated


def test_overlapping_instance_upload_cannot_rewind_persisted_clock(db_url, monkeypatch):
    with TestClient(hosted(db_url, monkeypatch)) as seed_client: seed(seed_client)
    with TestClient(hosted(db_url, monkeypatch)) as first, TestClient(hosted(db_url, monkeypatch)) as second:
        later = (START + timedelta(minutes=20)).isoformat()
        earlier = (START + timedelta(minutes=10)).isoformat()
        assert upload(second, csv_body({'event_id': 'LATER', 'consult_id': 'LATER-C', 'event_time': later, 'ingested_at': later})).json()['accepted'] == 1
        assert upload(first, csv_body({'event_id': 'EARLIER', 'consult_id': 'EARLIER-C', 'event_time': earlier, 'ingested_at': earlier})).json()['accepted'] == 1
        assert first.app.state.db.metadata('clock')['at'] == later
