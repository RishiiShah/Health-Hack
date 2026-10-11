"""The repeatable uploader skips matching versions and verifies every write."""
import importlib.util
import sys
from pathlib import Path
import pytest
from app.service import reference_manifest
from test_reference_database import files

spec=importlib.util.spec_from_file_location('upload_references',Path(__file__).resolve().parents[2]/'scripts/upload_references.py')
upload=importlib.util.module_from_spec(spec)
spec.loader.exec_module(upload)


def setup(tmp_path,monkeypatch,*flags):
    for name,text in files().items(): (tmp_path/name).write_text(text)
    monkeypatch.setenv('CC_API_TOKEN','synthetic-script-token')
    monkeypatch.setattr(sys,'argv',['upload_references.py',str(tmp_path),'--service-date','2026-04-07',*flags])
    return {'persisted':True,'manifest':reference_manifest({'files':files(),'service_date':'2026-04-07'}),
            'dataset':{'name':'Synthetic'},'hospitals':1,'physicians':1}


def test_matching_version_check_and_repeat_upload_do_not_write(tmp_path,monkeypatch,capsys):
    status=setup(tmp_path,monkeypatch)
    calls=[]
    def get(url,payload=None,token=None):
        calls.append(payload)
        return status
    monkeypatch.setattr(upload,'request',get)
    upload.main()
    assert calls==[None] and 'No changes made' in capsys.readouterr().out


def test_check_does_not_activate_missing_version(tmp_path,monkeypatch):
    status=setup(tmp_path,monkeypatch,'--check')
    monkeypatch.setattr(upload,'request',lambda *a,**k:{**status,'persisted':False})
    with pytest.raises(SystemExit,match='Reference check failed'): upload.main()


def test_a_different_version_is_stored_beside_the_active_one(tmp_path,monkeypatch,capsys):
    status=setup(tmp_path,monkeypatch)
    mine=status['manifest']['fingerprint']
    active={**status,'manifest':{**status['manifest'],'fingerprint':'different'},'kits':[]}
    calls=[]
    def request(url,payload=None,token=None):
        calls.append(payload)
        if payload: return {**status,'stored':True}
        return active if len(calls)==1 else {**active,'kits':[{'fingerprint':mine,'name':'Synthetic'}]}
    monkeypatch.setattr(upload,'request',request)
    upload.main()
    assert len(calls)==3 and 'Stored' in capsys.readouterr().out


def test_new_database_upload_is_verified_against_persisted_hash(tmp_path,monkeypatch,capsys):
    status=setup(tmp_path,monkeypatch)
    calls=[]
    def request(url,payload=None,token=None):
        calls.append(payload)
        if len(calls)==1: return {**status,'persisted':False}
        if payload:
            assert reference_manifest(payload)==status['manifest']
        return status
    monkeypatch.setattr(upload,'request',request)
    upload.main()
    assert len(calls)==3 and calls[0] is calls[2] is None and 'Stored in PostgreSQL' in capsys.readouterr().out
