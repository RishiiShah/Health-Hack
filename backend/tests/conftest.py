"""Each test gets its own throwaway PostgreSQL database on CC_TEST_DATABASE_URL's server."""
import os
from uuid import uuid4
import psycopg
from psycopg.conninfo import make_conninfo
import pytest

ADMIN_URL = os.getenv("CC_TEST_DATABASE_URL", "postgresql://postgres:postgres@127.0.0.1:5432/postgres")
# Tests create and drop whole databases: they must never reach the production RDS server.
if "rds.amazonaws.com" in ADMIN_URL or ADMIN_URL == os.getenv("CC_DATABASE_URL"):
    raise SystemExit("CC_TEST_DATABASE_URL points at the production database; use a disposable local PostgreSQL.")


@pytest.fixture(autouse=True)
def synthetic_reference_policy(monkeypatch):
    """Disposable synthetic test worlds may bootstrap their own kit; runtime always pins Sevaro."""
    from dataclasses import replace
    from app import main
    monkeypatch.setattr(main, "settings", replace(main.settings, reference_fingerprint=None))


@pytest.fixture
def new_db_url():
    names = []
    def create():
        names.append(f"cc_test_{uuid4().hex}")
        with psycopg.connect(ADMIN_URL, autocommit=True) as admin:
            admin.execute(f'CREATE DATABASE "{names[-1]}"')
        return make_conninfo(ADMIN_URL, dbname=names[-1])
    yield create
    with psycopg.connect(ADMIN_URL, autocommit=True) as admin:
        for name in names:
            admin.execute(f'DROP DATABASE "{name}" WITH (FORCE)')


@pytest.fixture
def db_url(new_db_url):
    return new_db_url()


from app.auth import Auth  # noqa: E402

TEST_AUTH = Auth(coordinator_token="coord-token", lead_token="lead-token", admin_token="admin-token", lead_name="Dr. Lead", secret="test-secret")
COORD = {"Authorization": "Bearer coord-token"}
LEAD = {"Authorization": "Bearer lead-token"}
ADMIN = {"Authorization": "Bearer admin-token"}
