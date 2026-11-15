# Milestone 3 report

## Implemented
- Migration 0003_tasks_queue.sql: tasks, task_events, approvals (forced RLS); functions claim_next_task, reap_timed_out, cancel_blocked_tasks (SECURITY DEFINER, executable only by the separate nexus_worker role).
- app/queue.py: state machine (CREATED, QUEUED, RUNNING, WAITING_APPROVAL, COMPLETED, FAILED, CANCELLED, RETRYING) with illegal transitions rejected, idempotent enqueue, exponential-backoff retries, timeout recovery, dependency handling, output verification before COMPLETED, full event trail.
- app/agents.py: registry of 18 agents (3 plumbing agents runnable, 15 product agents declared NOT_IMPLEMENTED and refused by the API). Agents with external effects always require human approval.
- API: GET /agents, POST/GET /tasks, GET /tasks/{id} (with events), cancel, retry, GET /approvals, approve, reject. Only owner/admin can decide approvals, cancel or retry.
- Worker: python -m app.worker (separate DB role).
- Tests: 41 passed in total, including 25 tasks run by 4 concurrent workers with exactly one RUNNING event each, cross-tenant isolation of tasks and approvals, and the app role being denied the queue functions.

## Run
scripts/start_test_pg.sh; cd services/api; pip install -r requirements.txt; pytest; python -m app.worker

## Known limitations
- Handlers run in-process in the worker; the timeout is enforced by the reaper (task is requeued), it does not kill a hung handler thread.
- Only the three system.* agents have handlers. No real work (discovery, audits, media, email) exists yet.
- No budget gate yet (Milestone 10), so cost_cents is recorded but not enforced.
- Role still comes from the JWT (see Milestone 2 limitations). Approver identity is the token's user id.
- Approving does not re-check that the task payload is unchanged since the approval was requested (tasks are immutable after creation in this API, but there is no hash binding yet).
- Idempotency covers task creation, not side effects inside future real handlers; those must pass idempotency keys to providers.

## Rollback
Drop schema public cascade and re-run migrations up to 0002, or git revert this milestone.
