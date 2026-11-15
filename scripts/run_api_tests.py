"""Run services/api tests against a disposable test database.

Local (default): expects scripts/start_test_pg.sh to be running on port 5433.
Hosted: set NEXUS_TEST_OWNER_URL / NEXUS_TEST_APP_URL / NEXUS_TEST_WORKER_URL to the
`nexus_test` database and pass --allow-destructive (the schema is dropped and rebuilt).

Convenience: if only NEXUS_OWNER_DATABASE_URL / DATABASE_URL / WORKER_DATABASE_URL are set
(e.g. from .env), the database name is swapped for NEXUS_TEST_DB_NAME (default nexus_test).
"""
from __future__ import annotations

import os
import pathlib
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from _env import load_dotenv  # noqa: E402

API_DIR = pathlib.Path(__file__).resolve().parents[1] / "services" / "api"


def _swap_db(dsn: str | None, dbname: str) -> str | None:
    if not dsn:
        return None
    head, sep, _ = dsn.rpartition("/")
    return f"{head}/{dbname}" if sep else None


def _redact(dsn: str | None) -> str:
    """Never print a password into logs."""
    if not dsn:
        return "(local socket default)"
    head, sep, tail = dsn.partition("://")
    if not sep:
        return dsn
    creds, _, rest = tail.partition("@")
    user = creds.split(":", 1)[0]
    return f"{head}://{user}:****@{rest}"


def main(argv: list[str]) -> int:
    load_dotenv()
    allow = "--allow-destructive" in argv
    dbname = os.environ.get("NEXUS_TEST_DB_NAME", "nexus_test")

    owner = os.environ.get("NEXUS_TEST_OWNER_URL") or _swap_db(os.environ.get("NEXUS_OWNER_DATABASE_URL"), dbname)
    app = os.environ.get("NEXUS_TEST_APP_URL") or _swap_db(os.environ.get("DATABASE_URL"), dbname)
    worker = os.environ.get("NEXUS_TEST_WORKER_URL") or _swap_db(os.environ.get("WORKER_DATABASE_URL"), dbname)

    env = dict(os.environ)
    if owner:
        env["NEXUS_TEST_OWNER_URL"] = owner
    if app:
        env["NEXUS_TEST_APP_URL"] = app
    if worker:
        env["NEXUS_TEST_WORKER_URL"] = worker
    if allow:
        env["NEXUS_ALLOW_DESTRUCTIVE_TEST_DB"] = "1"
    env.setdefault("NEXUS_BACKOFF_BASE", "0")
    env.setdefault("JWT_SECRET", "test-only-secret-0123456789abcdef")

    cmd = [sys.executable, "-m", "pytest", "-q", *[a for a in argv if not a.startswith("--allow")]]
    print("running:", " ".join(cmd), "in", API_DIR)
    print("test db:", _redact(owner))
    return subprocess.call(cmd, cwd=API_DIR, env=env)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
