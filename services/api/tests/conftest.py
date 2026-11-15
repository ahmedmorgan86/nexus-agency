import os
import pathlib

import psycopg
import pytest
from psycopg import sql

MIGRATIONS = pathlib.Path(__file__).resolve().parents[3] / "supabase" / "migrations"

# Local development default (scripts/start_test_pg.sh). CI/hosted runs override all three.
LOCAL_OWNER_DSN = "host=/tmp port=5433 dbname=nexus_test user=nexus_owner"
LOCAL_APP_DSN = "host=/tmp port=5433 dbname=nexus_test user=nexus_app password=nexus_app"
LOCAL_WORKER_DSN = "host=/tmp port=5433 dbname=nexus_test user=nexus_worker password=nexus_worker"


def _owner_dsn() -> str:
    return os.environ.get("NEXUS_TEST_OWNER_URL", LOCAL_OWNER_DSN)


def _app_dsn() -> str:
    return os.environ.get("NEXUS_TEST_APP_URL", LOCAL_APP_DSN)


def _worker_dsn() -> str:
    return os.environ.get("NEXUS_TEST_WORKER_URL", LOCAL_WORKER_DSN)


@pytest.fixture(scope="session", autouse=True)
def schema():
    owner_dsn = _owner_dsn()
    # Dropping `public` is destructive. Refuse unless the caller opted in explicitly
    # (the local socket default is always safe).
    if owner_dsn != LOCAL_OWNER_DSN and os.environ.get("NEXUS_ALLOW_DESTRUCTIVE_TEST_DB") != "1":
        pytest.fail(
            "refusing to drop schema public on a non-local database; "
            "set NEXUS_ALLOW_DESTRUCTIVE_TEST_DB=1 after confirming NEXUS_TEST_OWNER_URL "
            "points at a disposable test database"
        )
    try:
        owner = psycopg.connect(owner_dsn, autocommit=True, connect_timeout=20)
    except psycopg.OperationalError as exc:
        pytest.fail(f"test database not reachable ({exc}); run scripts/start_test_pg.sh or set NEXUS_TEST_*_URL")

    owner.execute("drop schema public cascade; create schema public;")
    for f in sorted(MIGRATIONS.glob("*.sql")):
        owner.execute(f.read_text(encoding="utf-8"))
    # Migrations create the roles NOLOGIN (no password in SQL). Tests need LOGIN, plus a
    # password when the cluster requires one (CI Postgres service); local clusters use
    # trust auth and hosted test databases already have a password from bootstrap_roles.py.
    for role, env in (("nexus_app", "NEXUS_APP_PASSWORD"), ("nexus_worker", "NEXUS_WORKER_PASSWORD")):
        password = os.environ.get(env)
        if password:
            owner.execute(sql.SQL("alter role {} login password {}").format(sql.Identifier(role), sql.Literal(password)))
        else:
            owner.execute(sql.SQL("alter role {} login").format(sql.Identifier(role)))

    # The API and worker under test must talk to this disposable database.
    os.environ["DATABASE_URL"] = _app_dsn()
    os.environ["WORKER_DATABASE_URL"] = _worker_dsn()
    yield
    owner.close()


@pytest.fixture(autouse=True)
def fast_backoff(monkeypatch):
    monkeypatch.setenv("NEXUS_BACKOFF_BASE", "0")
