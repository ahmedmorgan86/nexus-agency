"""Durable task queue on Postgres. All tenant-scoped functions expect a connection whose tenant context is set."""
import os
import time
import uuid

import psycopg
from psycopg.types.json import Jsonb

from app import agents
from app.server import dsn

ALLOWED = {
    "CREATED": {"QUEUED", "WAITING_APPROVAL", "CANCELLED"},
    "QUEUED": {"RUNNING", "CANCELLED"},
    "WAITING_APPROVAL": {"QUEUED", "CANCELLED"},
    "RUNNING": {"COMPLETED", "FAILED", "RETRYING", "CANCELLED"},
    "RETRYING": {"RUNNING", "CANCELLED"},
    "FAILED": {"RETRYING"},
    "COMPLETED": set(),
    "CANCELLED": set(),
}
UPDATABLE = {"output", "error", "cost_cents", "retry_count", "run_after", "finished_at", "locked_at"}


class IllegalTransition(Exception):
    pass


class UnknownOrNotRunnableAgent(Exception):
    pass


def worker_dsn() -> str:
    return os.environ.get("WORKER_DATABASE_URL",
                          "host=/tmp port=5433 dbname=nexus_test user=nexus_worker password=nexus_worker")


def backoff_base() -> int:
    return int(os.environ.get("NEXUS_BACKOFF_BASE", "5"))


def transition(conn, task_id, to, detail=None, **fields):
    row = conn.execute("select status from tasks where id = %s for update", (task_id,)).fetchone()
    if not row:
        raise LookupError("task not found")
    frm = row[0]
    if to not in ALLOWED[frm]:
        raise IllegalTransition(f"{frm} -> {to}")
    sets, vals = ["status = %s"], [to]
    for k, v in fields.items():
        if k not in UPDATABLE:
            raise ValueError(k)
        sets.append(f"{k} = %s")
        vals.append(Jsonb(v) if k == "output" else v)
    conn.execute(f"update tasks set {', '.join(sets)} where id = %s", (*vals, task_id))
    conn.execute(
        "insert into task_events (tenant_id, task_id, from_status, to_status, detail) "
        "select tenant_id, id, %s, %s, %s from tasks where id = %s",
        (frm, to, Jsonb(detail or {}), task_id))


def enqueue(conn, tenant_id, user_id, agent_id, input=None, priority=0, depends_on=(),
            idempotency_key=None, requires_approval=False, max_retries=3, timeout_seconds=300):
    """Returns (task_id, created). Same idempotency_key returns the existing task: no duplicates."""
    agent = agents.get(agent_id)
    if agent is None or agent.status not in agents.RUNNABLE:
        raise UnknownOrNotRunnableAgent(agent_id)
    needs_approval = requires_approval or agent.external_effect
    tid = uuid.uuid4()
    row = conn.execute(
        "insert into tasks (id, tenant_id, agent_id, input, priority, depends_on, idempotency_key, "
        "requires_approval, max_retries, timeout_seconds, created_by) "
        "values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) "
        "on conflict (tenant_id, idempotency_key) where idempotency_key is not null do nothing returning id",
        (tid, tenant_id, agent_id, Jsonb(input or {}), priority, list(depends_on), idempotency_key,
         needs_approval, max_retries, timeout_seconds, user_id)).fetchone()
    if row is None:
        existing = conn.execute("select id from tasks where idempotency_key = %s", (idempotency_key,)).fetchone()
        return existing[0], False
    conn.execute("insert into task_events (tenant_id, task_id, from_status, to_status) values (%s,%s,null,'CREATED')",
                 (tenant_id, tid))
    if needs_approval:
        transition(conn, tid, "WAITING_APPROVAL")
        conn.execute("insert into approvals (tenant_id, task_id, summary) values (%s,%s,%s)",
                     (tenant_id, tid, f"{agent_id} requires approval"))
    else:
        transition(conn, tid, "QUEUED")
    return tid, True


def decide_approval(conn, approval_id, user_id, approve: bool):
    row = conn.execute("select task_id, status from approvals where id = %s for update", (approval_id,)).fetchone()
    if not row:
        raise LookupError("approval not found")
    if row[1] != "pending":
        raise IllegalTransition(f"approval already {row[1]}")
    conn.execute("update approvals set status = %s, decided_by = %s, decided_at = now() where id = %s",
                 ("approved" if approve else "rejected", user_id, approval_id))
    if approve:
        transition(conn, row[0], "QUEUED", {"approved_by": str(user_id)})
    else:
        transition(conn, row[0], "CANCELLED", {"rejected_by": str(user_id)}, finished_at=_now(conn))
    return row[0]


def _now(conn):
    return conn.execute("select now()").fetchone()[0]


# ---- worker ---------------------------------------------------------------

def _tenant_conn(tenant_id):
    conn = psycopg.connect(dsn())
    conn.execute("select set_config('app.tenant_id', %s, true)", (str(tenant_id),))
    return conn


def _handler_echo(inp, attempt):
    return {"echo": inp}, 0


def _handler_flaky(inp, attempt):
    if attempt < int(inp.get("fail_times", 0)):
        raise RuntimeError(f"induced failure on attempt {attempt}")
    return {"attempts": attempt + 1}, 0


def _handler_external_demo(inp, attempt):
    # Simulation only: nothing leaves the system.
    return {"simulated": True, "sent": False}, 0


# agent_id -> (handler(input, attempt) -> (output, cost_cents), verifier(output) -> bool)
HANDLERS = {
    "system.echo": (_handler_echo, lambda o: isinstance(o, dict) and "echo" in o),
    "system.flaky": (_handler_flaky, lambda o: isinstance(o, dict) and "attempts" in o),
    "system.external_demo": (_handler_external_demo, lambda o: o.get("simulated") is True),
}


def run_once() -> str | None:
    """Claim and execute at most one task. Returns the task id handled, or None."""
    with psycopg.connect(worker_dsn()) as w:
        w.execute("select reap_timed_out(%s)", (backoff_base(),))
        w.execute("select cancel_blocked_tasks()")
        claimed = w.execute("select * from claim_next_task()").fetchone()
    if not claimed:
        return None
    task_id, tenant_id, agent_id, inp, _timeout, attempt = claimed
    try:
        handler, verify = HANDLERS[agent_id]
        output, cost = handler(inp, attempt)
        if not verify(output):  # COMPLETED only after output verification
            raise ValueError("output failed verification")
    except Exception as e:  # noqa: BLE001 - any handler failure is recorded, never swallowed
        _fail(task_id, tenant_id, attempt, str(e)[:500])
        return str(task_id)
    with _tenant_conn(tenant_id) as c:
        try:
            transition(c, task_id, "COMPLETED", {"verified": True}, output=output, cost_cents=cost,
                       finished_at=_now(c), error=None)
        except IllegalTransition:
            pass  # reaped/cancelled while running: do not overwrite
    return str(task_id)


def _fail(task_id, tenant_id, attempt, message):
    with _tenant_conn(tenant_id) as c:
        row = c.execute("select max_retries from tasks where id = %s", (task_id,)).fetchone()
        try:
            if attempt < row[0]:
                delay = backoff_base() * (2 ** attempt)
                transition(c, task_id, "RETRYING", {"error": message}, retry_count=attempt + 1, error=message,
                           run_after=c.execute("select now() + %s * interval '1 second'", (delay,)).fetchone()[0],
                           locked_at=None)
            else:
                transition(c, task_id, "FAILED", {"error": message}, error=message, finished_at=_now(c))
        except IllegalTransition:
            pass


def run_forever(poll_seconds=1.0):
    while True:
        if run_once() is None:
            time.sleep(poll_seconds)
