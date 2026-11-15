import os
import uuid
from concurrent.futures import ThreadPoolExecutor

import psycopg
import pytest
from fastapi.testclient import TestClient

from app import queue
from app.server import app, make_token

client = TestClient(app)
OWNER = os.environ.get("NEXUS_TEST_OWNER_URL", "host=/tmp port=5433 dbname=nexus_test user=nexus_owner")
PW = "correct-horse-battery"


def app_dsn() -> str:
    return os.environ.get("DATABASE_URL", "host=/tmp port=5433 dbname=nexus_test user=nexus_app")


@pytest.fixture(autouse=True)
def drain():
    while queue.run_once():
        pass


def reg(name="T"):
    r = client.post("/auth/register", json={"email": f"{uuid.uuid4().hex[:8]}@example.com", "password": PW, "tenant_name": name})
    return r.json()["token"], r.json()["tenant_id"]


def H(t):
    return {"Authorization": f"Bearer {t}"}


def post_task(tok, agent="system.echo", **kw):
    r = client.post("/tasks", json={"agent_id": agent, **kw}, headers=H(tok))
    assert r.status_code == 201, r.text
    return r.json()


def get_task(tok, tid):
    return client.get(f"/tasks/{tid}", headers=H(tok)).json()


def run_until(tid, tok, status, limit=20):
    for _ in range(limit):
        queue.run_once()
        if get_task(tok, tid)["status"] == status:
            return True
    return False


def test_task_runs_to_completion_with_audit_trail():
    tok, _ = reg()
    t = post_task(tok, input={"hello": "world"})
    assert t["status"] == "QUEUED"
    assert queue.run_once() == t["id"]
    g = get_task(tok, t["id"])
    assert g["status"] == "COMPLETED" and g["output"] == {"echo": {"hello": "world"}}
    assert [e["to"] for e in g["events"]] == ["CREATED", "QUEUED", "RUNNING", "COMPLETED"]


def test_idempotency_prevents_duplicates():
    tok, _ = reg()
    a = post_task(tok, idempotency_key="k1")
    b = post_task(tok, idempotency_key="k1")
    assert a["id"] == b["id"] and a["created"] and not b["created"]
    assert len(client.get("/tasks", headers=H(tok)).json()) == 1


def test_same_idempotency_key_in_different_tenants_is_independent():
    ta, _ = reg("A")
    tb, _ = reg("B")
    assert post_task(ta, idempotency_key="k")["id"] != post_task(tb, idempotency_key="k")["id"]


def test_external_agent_requires_approval_and_is_not_claimed():
    tok, tid = reg()
    t = post_task(tok, agent="system.external_demo")
    assert t["status"] == "WAITING_APPROVAL"
    assert queue.run_once() is None
    assert get_task(tok, t["id"])["status"] == "WAITING_APPROVAL"
    ap = client.get("/approvals", headers=H(tok)).json()
    assert len(ap) == 1 and ap[0]["task_id"] == t["id"]


def test_approval_flow_roles_and_double_decision():
    tok, tid = reg()
    t = post_task(tok, agent="system.external_demo")
    ap = client.get("/approvals", headers=H(tok)).json()[0]["id"]
    operator = make_token(uuid.uuid4(), tid, "operator")
    assert client.post(f"/approvals/{ap}/approve", headers=H(operator)).status_code == 403
    admin = make_token(uuid.uuid4(), tid, "admin")
    assert client.post(f"/approvals/{ap}/approve", headers=H(admin)).status_code == 200
    assert client.post(f"/approvals/{ap}/approve", headers=H(admin)).status_code == 409
    assert run_until(t["id"], tok, "COMPLETED")
    assert get_task(tok, t["id"])["output"]["sent"] is False


def test_rejection_cancels_task():
    tok, _ = reg()
    t = post_task(tok, agent="system.external_demo")
    ap = client.get("/approvals", headers=H(tok)).json()[0]["id"]
    assert client.post(f"/approvals/{ap}/reject", headers=H(tok)).status_code == 200
    assert get_task(tok, t["id"])["status"] == "CANCELLED"
    assert queue.run_once() is None


def test_requires_approval_flag_on_any_agent():
    tok, _ = reg()
    assert post_task(tok, requires_approval=True)["status"] == "WAITING_APPROVAL"


def test_retry_then_success():
    tok, _ = reg()
    t = post_task(tok, agent="system.flaky", input={"fail_times": 2})
    assert run_until(t["id"], tok, "COMPLETED")
    g = get_task(tok, t["id"])
    assert g["retry_count"] == 2 and g["output"] == {"attempts": 3}
    assert [e["to"] for e in g["events"]].count("RETRYING") == 2


def test_retries_exhausted_marks_failed_and_manual_retry_requires_admin():
    tok, tid = reg()
    t = post_task(tok, agent="system.flaky", input={"fail_times": 99}, max_retries=1)
    assert run_until(t["id"], tok, "FAILED")
    assert "induced failure" in get_task(tok, t["id"])["error"]
    op = make_token(uuid.uuid4(), tid, "operator")
    assert client.post(f"/tasks/{t['id']}/retry", headers=H(op)).status_code == 403
    assert client.post(f"/tasks/{t['id']}/retry", headers=H(tok)).status_code == 200
    assert get_task(tok, t["id"])["status"] == "RETRYING"
    queue.run_once()  # still fails (fail_times=99) -> goes back around
    assert get_task(tok, t["id"])["status"] in {"RETRYING", "FAILED"}
    while queue.run_once():
        pass


def test_illegal_transitions_rejected():
    tok, _ = reg()
    t = post_task(tok)
    queue.run_once()
    assert client.post(f"/tasks/{t['id']}/cancel", headers=H(tok)).status_code == 409  # COMPLETED is terminal
    assert client.post(f"/tasks/{t['id']}/retry", headers=H(tok)).status_code == 409


def test_priority_order():
    tok, _ = reg()
    low = post_task(tok, priority=1)
    high = post_task(tok, priority=50)
    assert queue.run_once() == high["id"]
    assert queue.run_once() == low["id"]


def test_dependencies_respected():
    tok, _ = reg()
    a = post_task(tok, priority=0)
    b = post_task(tok, priority=100, depends_on=[a["id"]])
    assert queue.run_once() == a["id"]     # B has higher priority but must wait for A
    assert queue.run_once() == b["id"]


def test_failed_dependency_cancels_dependents():
    tok, _ = reg()
    a = post_task(tok, agent="system.flaky", input={"fail_times": 99}, max_retries=0)
    b = post_task(tok, depends_on=[a["id"]])
    for _ in range(4):
        queue.run_once()
    assert get_task(tok, a["id"])["status"] == "FAILED"
    assert get_task(tok, b["id"])["status"] == "CANCELLED"


def test_unknown_dependency_rejected():
    tok, _ = reg()
    r = client.post("/tasks", json={"agent_id": "system.echo", "depends_on": [str(uuid.uuid4())]}, headers=H(tok))
    assert r.status_code == 422


def test_unimplemented_and_unknown_agents_refused():
    tok, _ = reg()
    assert client.post("/tasks", json={"agent_id": "video_production"}, headers=H(tok)).status_code == 422
    assert client.post("/tasks", json={"agent_id": "nope"}, headers=H(tok)).status_code == 422


def test_agent_registry_is_honest():
    tok, _ = reg()
    ag = {a["id"]: a for a in client.get("/agents", headers=H(tok)).json()}
    assert ag["video_production"]["runnable"] is False and ag["video_production"]["status"] == "NOT_IMPLEMENTED"
    assert ag["sales"]["external_effect"] is True
    assert ag["system.echo"]["runnable"] is True
    assert {"market_research", "discovery", "qa", "financial", "learning"} <= set(ag)


def test_timeout_reaper_recovers_hung_task():
    tok, _ = reg()
    t = post_task(tok, timeout_seconds=1)
    with psycopg.connect(queue.worker_dsn()) as w:       # simulate a worker that claims then dies
        assert w.execute("select id from claim_next_task()").fetchone()[0] == uuid.UUID(t["id"])
    with psycopg.connect(OWNER, autocommit=True) as o:
        o.execute("update tasks set locked_at = now() - interval '10 seconds' where id = %s", (t["id"],))
    assert run_until(t["id"], tok, "COMPLETED")
    events = [e["to"] for e in get_task(tok, t["id"])["events"]]
    assert "RETRYING" in events and events[-1] == "COMPLETED"


def test_cross_tenant_tasks_and_approvals_isolated():
    ta, _ = reg("A")
    tb, _ = reg("B")
    t = post_task(ta, agent="system.external_demo")
    ap = client.get("/approvals", headers=H(ta)).json()[0]["id"]
    assert client.get("/tasks", headers=H(tb)).json() == []
    assert client.get(f"/tasks/{t['id']}", headers=H(tb)).status_code == 404
    assert client.get("/approvals", headers=H(tb)).json() == []
    assert client.post(f"/approvals/{ap}/approve", headers=H(tb)).status_code == 404
    assert client.post(f"/tasks/{t['id']}/cancel", headers=H(tb)).status_code == 404
    assert get_task(ta, t["id"])["status"] == "WAITING_APPROVAL"


def test_viewer_cannot_enqueue():
    _, tid = reg()
    v = make_token(uuid.uuid4(), tid, "client_viewer")
    assert client.post("/tasks", json={"agent_id": "system.echo"}, headers=H(v)).status_code == 403
    assert client.get("/tasks", headers=H(v)).status_code == 200


def test_app_role_cannot_use_cross_tenant_queue_functions():
    with psycopg.connect(app_dsn(), autocommit=True) as c:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            c.execute("select * from claim_next_task()")


def test_concurrent_workers_never_double_run():
    tok, _ = reg()
    ids = [post_task(tok)["id"] for _ in range(25)]

    def work(_):
        n = 0
        while queue.run_once():
            n += 1
        return n

    with ThreadPoolExecutor(4) as ex:
        counts = list(ex.map(work, range(4)))
    assert sum(counts) == 25
    for i in ids:
        g = get_task(tok, i)
        assert g["status"] == "COMPLETED"
        assert [e["to"] for e in g["events"]].count("RUNNING") == 1
