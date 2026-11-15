import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app import agents, queue
from app.server import Principal, current_principal, db, require_write

router = APIRouter()
APPROVER_ROLES = {"owner", "admin"}


def require_approver(p: Principal = Depends(current_principal)) -> Principal:
    if p.role not in APPROVER_ROLES:
        raise HTTPException(403, "only owner/admin can decide approvals")
    return p


class TaskIn(BaseModel):
    agent_id: str = Field(max_length=100)
    input: dict = Field(default_factory=dict)
    priority: int = Field(default=0, ge=-100, le=100)
    depends_on: list[uuid.UUID] = Field(default_factory=list, max_length=50)
    idempotency_key: str | None = Field(default=None, max_length=200)
    requires_approval: bool = False
    max_retries: int = Field(default=3, ge=0, le=10)
    timeout_seconds: int = Field(default=300, ge=1, le=3600)


def _task_row(r):
    return {"id": str(r[0]), "agent_id": r[1], "status": r[2], "priority": r[3], "retry_count": r[4],
            "cost_cents": float(r[5]), "output": r[6], "error": r[7], "requires_approval": r[8],
            "created_at": r[9].isoformat()}


TASK_COLS = "id, agent_id, status, priority, retry_count, cost_cents, output, error, requires_approval, created_at"


@router.get("/agents")
def list_agents(_: Principal = Depends(current_principal)):
    return [agents.public_view(a) for a in agents.REGISTRY.values()]


@router.post("/tasks", status_code=201)
def create_task(body: TaskIn, p: Principal = Depends(require_write)):
    try:
        with db(p.tenant_id) as conn:
            if body.depends_on:
                n = conn.execute("select count(*) from tasks where id = any(%s)", (list(body.depends_on),)).fetchone()[0]
                if n != len(set(body.depends_on)):
                    raise HTTPException(422, "unknown dependency")
            tid, created = queue.enqueue(
                conn, p.tenant_id, p.user_id, body.agent_id, body.input, body.priority, body.depends_on,
                body.idempotency_key, body.requires_approval, body.max_retries, body.timeout_seconds)
            status = conn.execute("select status from tasks where id = %s", (tid,)).fetchone()[0]
    except queue.UnknownOrNotRunnableAgent:
        raise HTTPException(422, "agent unknown or not implemented yet")
    return {"id": str(tid), "status": status, "created": created}


@router.get("/tasks")
def list_tasks(status: str | None = None, p: Principal = Depends(current_principal)):
    with db(p.tenant_id) as conn:
        if status:
            rows = conn.execute(f"select {TASK_COLS} from tasks where status = %s order by created_at desc limit 200",
                                (status,)).fetchall()
        else:
            rows = conn.execute(f"select {TASK_COLS} from tasks order by created_at desc limit 200").fetchall()
    return [_task_row(r) for r in rows]


@router.get("/tasks/{task_id}")
def get_task(task_id: uuid.UUID, p: Principal = Depends(current_principal)):
    with db(p.tenant_id) as conn:
        r = conn.execute(f"select {TASK_COLS} from tasks where id = %s", (task_id,)).fetchone()
        if not r:
            raise HTTPException(404, "task not found")
        ev = conn.execute("select from_status, to_status, detail, created_at from task_events "
                          "where task_id = %s order by id", (task_id,)).fetchall()
    out = _task_row(r)
    out["events"] = [{"from": e[0], "to": e[1], "detail": e[2], "at": e[3].isoformat()} for e in ev]
    return out


def _guarded(fn):
    try:
        return fn()
    except LookupError:
        raise HTTPException(404, "not found")
    except queue.IllegalTransition as e:
        raise HTTPException(409, str(e))


@router.post("/tasks/{task_id}/cancel")
def cancel_task(task_id: uuid.UUID, p: Principal = Depends(require_approver)):
    def go():
        with db(p.tenant_id) as conn:
            queue.transition(conn, task_id, "CANCELLED", {"by": str(p.user_id)},
                             finished_at=queue._now(conn))
    _guarded(go)
    return {"status": "CANCELLED"}


@router.post("/tasks/{task_id}/retry")
def retry_task(task_id: uuid.UUID, p: Principal = Depends(require_approver)):
    def go():
        with db(p.tenant_id) as conn:
            queue.transition(conn, task_id, "RETRYING", {"manual_retry_by": str(p.user_id)},
                             retry_count=0, error=None, finished_at=None)
    _guarded(go)
    return {"status": "RETRYING"}


@router.get("/approvals")
def list_approvals(status: str = "pending", p: Principal = Depends(current_principal)):
    with db(p.tenant_id) as conn:
        rows = conn.execute(
            "select a.id, a.task_id, t.agent_id, a.summary, a.status, a.requested_at "
            "from approvals a join tasks t on t.id = a.task_id where a.status = %s "
            "order by a.requested_at desc limit 200", (status,)).fetchall()
    return [{"id": str(r[0]), "task_id": str(r[1]), "agent_id": r[2], "summary": r[3], "status": r[4],
             "requested_at": r[5].isoformat()} for r in rows]


def _decide(approval_id, p, approve):
    def go():
        with db(p.tenant_id) as conn:
            tid = queue.decide_approval(conn, approval_id, p.user_id, approve)
            conn.execute("insert into audit_logs (tenant_id, actor_user_id, action, detail) values (%s,%s,%s,%s)",
                         (p.tenant_id, p.user_id, "approval.approved" if approve else "approval.rejected",
                          queue.Jsonb({"approval_id": str(approval_id), "task_id": str(tid)})))
    _guarded(go)
    return {"status": "approved" if approve else "rejected"}


@router.post("/approvals/{approval_id}/approve")
def approve(approval_id: uuid.UUID, p: Principal = Depends(require_approver)):
    return _decide(approval_id, p, True)


@router.post("/approvals/{approval_id}/reject")
def reject(approval_id: uuid.UUID, p: Principal = Depends(require_approver)):
    return _decide(approval_id, p, False)
