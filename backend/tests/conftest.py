"""Each test gets its own throwaway PostgreSQL database on CC_TEST_DATABASE_URL's server."""
import os
from uuid import uuid4
import psycopg
from psycopg.conninfo import make_conninfo
import pytest

ADMIN_URL = os.getenv("CC_TEST_DATABASE_URL", "postgresql://postgres:postgres@127.0.0.1:5432/postgres")


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

TEST_AUTH = Auth("coord-token", "lead-token", "admin-token", "Dr. Lead", "test-secret")
COORD = {"Authorization": "Bearer coord-token"}
LEAD = {"Authorization": "Bearer lead-token"}
ADMIN = {"Authorization": "Bearer admin-token"}
