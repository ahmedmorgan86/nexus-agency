"""Grant LOGIN to the unprivileged NEXUS roles using passwords from the environment.

No password is stored in the repository or in a migration. Run this once per database
cluster, right after `supabase/migrations/*.sql` have been applied by an owner role.

Environment:
  NEXUS_OWNER_DATABASE_URL   owner/DSN able to ALTER ROLE (e.g. Supabase `postgres`)
  NEXUS_APP_PASSWORD         password for nexus_app   (>= 24 chars)
  NEXUS_WORKER_PASSWORD      password for nexus_worker (>= 24 chars, must differ)

Usage:
  python scripts/bootstrap_roles.py            # apply
  python scripts/bootstrap_roles.py --check    # verify only, no changes
"""
from __future__ import annotations

import os
import pathlib
import sys

import psycopg
from psycopg import sql

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from _env import load_dotenv  # noqa: E402

ROLES = {"nexus_app": "NEXUS_APP_PASSWORD", "nexus_worker": "NEXUS_WORKER_PASSWORD"}
MIN_LEN = 24


def fail(msg: str) -> "None":
    print(f"ERROR: {msg}", file=sys.stderr)
    raise SystemExit(2)


def main(argv: list[str]) -> int:
    load_dotenv()
    check_only = "--check" in argv
    owner_dsn = os.environ.get("NEXUS_OWNER_DATABASE_URL") or os.environ.get("DATABASE_URL")
    if not owner_dsn:
        fail("NEXUS_OWNER_DATABASE_URL (or DATABASE_URL) is required")

    secrets = {}
    for role, env in ROLES.items():
        value = os.environ.get(env, "")
        if check_only:
            secrets[role] = None
            continue
        if not value:
            fail(f"{env} is required")
        if len(value) < MIN_LEN:
            fail(f"{env} must be at least {MIN_LEN} characters")
        if value.lower() == role:
            fail(f"{env} must not equal the role name")
        secrets[role] = value
    if not check_only and secrets["nexus_app"] == secrets["nexus_worker"]:
        fail("nexus_app and nexus_worker must use different passwords")

    with psycopg.connect(owner_dsn, connect_timeout=20, autocommit=True) as conn:
        for role, env in ROLES.items():
            row = conn.execute(
                "select rolcanlogin, rolbypassrls, rolsuper from pg_roles where rolname = %s", (role,)
            ).fetchone()
            if row is None:
                fail(f"role {role} does not exist: apply supabase/migrations first")
            can_login, bypass_rls, is_super = row
            if bypass_rls or is_super:
                fail(f"role {role} must not be superuser or BYPASSRLS")
            if check_only:
                print(f"{role}: login={can_login} bypassrls={bypass_rls} super={is_super}")
                continue
            conn.execute(
                sql.SQL("alter role {} login password {}").format(sql.Identifier(role), sql.Literal(secrets[role]))
            )
            print(f"{role}: LOGIN granted, password set from {env}")

    if check_only:
        print("check complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
