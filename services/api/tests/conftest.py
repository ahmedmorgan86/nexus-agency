import pathlib

import psycopg
import pytest

OWNER_DSN = "host=/tmp port=5433 dbname=nexus_test user=nexus_owner"
MIGRATIONS = pathlib.Path(__file__).resolve().parents[3] / "supabase" / "migrations"


@pytest.fixture(scope="session", autouse=True)
def schema():
    try:
        owner = psycopg.connect(OWNER_DSN, autocommit=True)
    except psycopg.OperationalError:
        pytest.fail("Postgres not running: run scripts/start_test_pg.sh")
    owner.execute("drop schema public cascade; create schema public;")
    for f in sorted(MIGRATIONS.glob("*.sql")):
        owner.execute(f.read_text())
    yield
    owner.close()


@pytest.fixture(autouse=True)
def fast_backoff(monkeypatch):
    monkeypatch.setenv("NEXUS_BACKOFF_BASE", "0")
