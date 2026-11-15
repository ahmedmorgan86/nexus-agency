"""Apply supabase/migrations/*.sql in order, recording what has been applied.

Environment:
  NEXUS_OWNER_DATABASE_URL  owner/DDL DSN (Supabase `postgres`)

The runner is idempotent: each file runs at most once per database. It never drops data.
Use `--dry-run` to list pending files without touching the database.
"""
from __future__ import annotations

import hashlib
import os
import pathlib
import sys

import psycopg

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from _env import load_dotenv  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[1]
MIGRATIONS = ROOT / "supabase" / "migrations"


def main(argv: list[str]) -> int:
    load_dotenv()
    dry_run = "--dry-run" in argv
    dsn = os.environ.get("NEXUS_OWNER_DATABASE_URL") or os.environ.get("DATABASE_URL")
    if not dsn:
        print("ERROR: NEXUS_OWNER_DATABASE_URL (or DATABASE_URL) is required", file=sys.stderr)
        return 2

    files = sorted(MIGRATIONS.glob("*.sql"))
    if not files:
        print("ERROR: no migration files found", file=sys.stderr)
        return 2

    with psycopg.connect(dsn, connect_timeout=20, autocommit=True) as conn:
        conn.execute(
            "create table if not exists _migrations ("
            " name text primary key, checksum text not null, applied_at timestamptz not null default now())"
        )
        applied = dict(conn.execute("select name, checksum from _migrations").fetchall())
        pending = []
        for f in files:
            checksum = hashlib.sha256(f.read_bytes()).hexdigest()
            if f.name in applied:
                if applied[f.name] != checksum:
                    print(f"ERROR: {f.name} changed after being applied; add a new migration instead",
                          file=sys.stderr)
                    return 2
                continue
            pending.append((f, checksum))

        if not pending:
            print("database is up to date")
            return 0
        if dry_run:
            for f, _ in pending:
                print(f"pending: {f.name}")
            return 0

        for f, checksum in pending:
            print(f"applying {f.name} ...", end=" ")
            try:
                conn.execute(f.read_text(encoding="utf-8"))
            except Exception as exc:  # noqa: BLE001 - surface the real error, stop immediately
                print("FAILED")
                print(f"ERROR: {f.name}: {exc}", file=sys.stderr)
                return 1
            conn.execute("insert into _migrations (name, checksum) values (%s, %s)", (f.name, checksum))
            print("ok")
    print("done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
