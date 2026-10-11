"""The browser fixture must never create/drop a remote or unrelated database."""
import importlib.util
from pathlib import Path
import pytest

spec = importlib.util.spec_from_file_location('e2e_server',Path(__file__).resolve().parents[2]/'scripts'/'e2e_server.py')
fixture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture)


@pytest.mark.parametrize('url', ['postgresql://user:pass@db.example/postgres','postgresql://postgres:postgres@127.0.0.1/production'])
def test_browser_fixture_refuses_nonlocal_or_application_admin_database(url):
    with pytest.raises(ValueError,match='localhost'):
        fixture.local_admin_url(url)


@pytest.mark.parametrize('dbname,host', [('commandcenter','127.0.0.1'),('cc_browser_e2e_test','db.example')])
def test_browser_fixture_refuses_unrelated_saved_state(dbname,host):
    admin = fixture.local_admin_url('postgresql://postgres:postgres@127.0.0.1:5432/postgres')
    with pytest.raises(ValueError,match='fixture database'):
        fixture.checked_state({'dbname':dbname,'url':f'postgresql://postgres:postgres@{host}:5432/{dbname}'},admin)
