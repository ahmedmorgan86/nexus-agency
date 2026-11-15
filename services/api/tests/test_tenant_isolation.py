"""RLS tests. Require a running Postgres (scripts/start_test_pg.sh or NEXUS_TEST_*_URL).
Connects as the unprivileged nexus_app role, never as the owner."""
import os
import uuid

import psycopg
import pytest
from psycopg import errors

LOCAL_APP_DSN = "host=/tmp port=5433 dbname=nexus_test user=nexus_app"


def app_conn():
    # conftest points DATABASE_URL at the disposable test database before tests run.
    return psycopg.connect(os.environ.get("DATABASE_URL", LOCAL_APP_DSN), autocommit=True)


def set_tenant(conn, tenant_id):
    conn.execute("select set_config('app.tenant_id', %s, false)", (str(tenant_id),))


def make_tenant(name):
    tid = uuid.uuid4()
    c = app_conn()
    set_tenant(c, tid)
    c.execute("insert into tenants (id, name) values (%s, %s)", (tid, name))
    return tid, c


def test_app_role_cannot_bypass_rls():
    c = app_conn()
    row = c.execute("select rolsuper, rolbypassrls from pg_roles where rolname = current_user").fetchone()
    assert row == (False, False)


def test_tenant_sees_only_own_leads():
    a, ca = make_tenant("A")
    b, cb = make_tenant("B")
    ca.execute("insert into leads (tenant_id, business_name) values (%s, 'Acme')", (a,))
    cb.execute("insert into leads (tenant_id, business_name) values (%s, 'Beta')", (b,))
    assert [r[0] for r in ca.execute("select business_name from leads").fetchall()] == ["Acme"]
    assert [r[0] for r in cb.execute("select business_name from leads").fetchall()] == ["Beta"]


def test_no_tenant_context_sees_nothing():
    a, ca = make_tenant("A2")
    ca.execute("insert into leads (tenant_id, business_name) values (%s, 'Hidden')", (a,))
    anon = app_conn()
    assert anon.execute("select count(*) from leads").fetchone()[0] == 0


def test_cannot_insert_into_other_tenant():
    a, ca = make_tenant("A3")
    b, _ = make_tenant("B3")
    with pytest.raises(errors.InsufficientPrivilege):
        ca.execute("insert into leads (tenant_id, business_name) values (%s, 'Spoof')", (b,))


def test_cannot_update_or_delete_other_tenant_rows():
    a, ca = make_tenant("A4")
    b, cb = make_tenant("B4")
    cb.execute("insert into leads (tenant_id, business_name) values (%s, 'Target')", (b,))
    assert ca.execute("update leads set business_name = 'Hacked' where business_name = 'Target'").rowcount == 0
    assert ca.execute("delete from leads where business_name = 'Target'").rowcount == 0
    assert cb.execute("select business_name from leads").fetchone()[0] == "Target"


def test_cannot_move_row_to_other_tenant():
    a, ca = make_tenant("A5")
    b, _ = make_tenant("B5")
    ca.execute("insert into leads (tenant_id, business_name) values (%s, 'Mine')", (a,))
    with pytest.raises(errors.InsufficientPrivilege):
        ca.execute("update leads set tenant_id = %s", (b,))


def test_audit_logs_isolated():
    a, ca = make_tenant("A6")
    b, cb = make_tenant("B6")
    ca.execute("insert into audit_logs (tenant_id, action) values (%s, 'x')", (a,))
    assert cb.execute("select count(*) from audit_logs").fetchone()[0] == 0


def test_verification_status_constraint():
    a, ca = make_tenant("A7")
    with pytest.raises(errors.CheckViolation):
        ca.execute("insert into leads (tenant_id, business_name, verification_status) values (%s, 'X', 'MAYBE')", (a,))
