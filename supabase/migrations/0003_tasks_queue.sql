-- NEXUS 0003: durable task queue, audit events, human approvals.
create table tasks (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references tenants(id) on delete cascade,
  agent_id text not null,
  input jsonb not null default '{}',
  status text not null default 'CREATED' check (status in
    ('CREATED','QUEUED','RUNNING','WAITING_APPROVAL','COMPLETED','FAILED','CANCELLED','RETRYING')),
  priority int not null default 0,
  depends_on uuid[] not null default '{}',
  retry_count int not null default 0,
  max_retries int not null default 3,
  timeout_seconds int not null default 300,
  idempotency_key text,
  requires_approval boolean not null default false,
  cost_cents numeric(12,4) not null default 0,
  output jsonb,
  error text,
  run_after timestamptz not null default now(),
  locked_at timestamptz,
  started_at timestamptz,
  finished_at timestamptz,
  created_by uuid,
  created_at timestamptz not null default now()
);
create unique index tasks_idem_uq on tasks (tenant_id, idempotency_key) where idempotency_key is not null;
create index tasks_claim_idx on tasks (status, run_after, priority desc, created_at);
create index tasks_tenant_idx on tasks (tenant_id);

create table task_events (
  id bigserial primary key,
  tenant_id uuid not null references tenants(id) on delete cascade,
  task_id uuid not null references tasks(id) on delete cascade,
  from_status text,
  to_status text not null,
  detail jsonb not null default '{}',
  created_at timestamptz not null default now()
);
create index task_events_task_idx on task_events (task_id);

create table approvals (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references tenants(id) on delete cascade,
  task_id uuid not null references tasks(id) on delete cascade,
  status text not null default 'pending' check (status in ('pending','approved','rejected')),
  summary text,
  requested_at timestamptz not null default now(),
  decided_by uuid,
  decided_at timestamptz
);
create unique index approvals_one_pending on approvals (task_id) where status = 'pending';
create index approvals_tenant_idx on approvals (tenant_id, status);

alter table tasks enable row level security;       alter table tasks force row level security;
alter table task_events enable row level security; alter table task_events force row level security;
alter table approvals enable row level security;   alter table approvals force row level security;

create policy tasks_isolation on tasks
  using (tenant_id = app_tenant()) with check (tenant_id = app_tenant());
create policy task_events_isolation on task_events
  using (tenant_id = app_tenant()) with check (tenant_id = app_tenant());
create policy approvals_isolation on approvals
  using (tenant_id = app_tenant()) with check (tenant_id = app_tenant());

grant select, insert, update on tasks, approvals to nexus_app;
grant select, insert on task_events to nexus_app;
grant usage, select on all sequences in schema public to nexus_app;

-- Separate role for the worker process: only it may use the cross-tenant queue functions.
-- Created NOLOGIN: scripts/bootstrap_roles.py grants LOGIN with a password from the environment.
do $$ begin
  if not exists (select 1 from pg_roles where rolname = 'nexus_worker') then
    create role nexus_worker nologin nosuperuser nobypassrls;
  end if;
end $$;
grant usage on schema public to nexus_worker;

-- Worker claim: the only cross-tenant read. Atomic (SKIP LOCKED), honours priority, run_after and dependencies.
create or replace function claim_next_task()
returns table (id uuid, tenant_id uuid, agent_id text, input jsonb, timeout_seconds int, retry_count int)
language plpgsql security definer set search_path = public as $$
declare t tasks%rowtype;
begin
  select * into t from tasks k
   where k.status in ('QUEUED','RETRYING') and k.run_after <= now()
     and not exists (
       select 1 from unnest(k.depends_on) d
        where not exists (select 1 from tasks x where x.id = d and x.status = 'COMPLETED'))
   order by k.priority desc, k.created_at
   for update skip locked limit 1;
  if not found then return; end if;
  update tasks set status = 'RUNNING', locked_at = now(), started_at = coalesce(tasks.started_at, now())
   where tasks.id = t.id;
  insert into task_events (tenant_id, task_id, from_status, to_status) values (t.tenant_id, t.id, t.status, 'RUNNING');
  return query select t.id, t.tenant_id, t.agent_id, t.input, t.timeout_seconds, t.retry_count;
end $$;

-- Recover tasks whose worker died or hung past their timeout.
create or replace function reap_timed_out(p_backoff_base int default 5)
returns int language plpgsql security definer set search_path = public as $$
declare t tasks%rowtype; n int := 0;
begin
  for t in select * from tasks k where k.status = 'RUNNING'
            and k.locked_at + (k.timeout_seconds * interval '1 second') < now() for update skip locked
  loop
    if t.retry_count < t.max_retries then
      update tasks set status = 'RETRYING', retry_count = retry_count + 1, error = 'timeout',
             run_after = now() + (p_backoff_base * power(2, t.retry_count)) * interval '1 second', locked_at = null
       where id = t.id;
      insert into task_events (tenant_id, task_id, from_status, to_status, detail)
        values (t.tenant_id, t.id, 'RUNNING', 'RETRYING', '{"reason":"timeout"}');
    else
      update tasks set status = 'FAILED', error = 'timeout', finished_at = now(), locked_at = null where id = t.id;
      insert into task_events (tenant_id, task_id, from_status, to_status, detail)
        values (t.tenant_id, t.id, 'RUNNING', 'FAILED', '{"reason":"timeout"}');
    end if;
    n := n + 1;
  end loop;
  return n;
end $$;

-- Dependents of failed/cancelled tasks can never run: cancel them.
create or replace function cancel_blocked_tasks()
returns int language plpgsql security definer set search_path = public as $$
declare t tasks%rowtype; n int := 0;
begin
  for t in select * from tasks k where k.status in ('QUEUED','RETRYING','WAITING_APPROVAL','CREATED')
     and exists (select 1 from unnest(k.depends_on) d join tasks x on x.id = d where x.status in ('FAILED','CANCELLED'))
     for update skip locked
  loop
    update tasks set status = 'CANCELLED', error = 'dependency failed', finished_at = now() where id = t.id;
    insert into task_events (tenant_id, task_id, from_status, to_status, detail)
      values (t.tenant_id, t.id, t.status, 'CANCELLED', '{"reason":"dependency failed"}');
    n := n + 1;
  end loop;
  return n;
end $$;

revoke all on function claim_next_task() from public;
revoke all on function reap_timed_out(int) from public;
revoke all on function cancel_blocked_tasks() from public;
grant execute on function claim_next_task() to nexus_worker;
grant execute on function reap_timed_out(int) to nexus_worker;
grant execute on function cancel_blocked_tasks() to nexus_worker;
