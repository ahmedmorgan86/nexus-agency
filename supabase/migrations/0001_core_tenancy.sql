-- NEXUS 0001: tenancy core. Tenant isolation is enforced by RLS, not only by API code.
create extension if not exists pgcrypto;

create table tenants (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  created_at timestamptz not null default now()
);

create table users (
  id uuid primary key default gen_random_uuid(),
  email text not null unique,
  password_hash text not null,
  created_at timestamptz not null default now()
);

create table memberships (
  user_id uuid not null references users(id) on delete cascade,
  tenant_id uuid not null references tenants(id) on delete cascade,
  role text not null check (role in ('owner','admin','operator','client_viewer')),
  primary key (user_id, tenant_id)
);

create table leads (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references tenants(id) on delete cascade,
  business_name text not null,
  website text,
  verification_status text not null default 'DISCOVERED'
    check (verification_status in ('DISCOVERED','PARTIALLY_VERIFIED','VERIFIED','UNVERIFIED','REJECTED')),
  source_url text,
  discovered_at timestamptz not null default now(),
  created_at timestamptz not null default now()
);
create index leads_tenant_idx on leads (tenant_id);

create table audit_logs (
  id bigserial primary key,
  tenant_id uuid references tenants(id) on delete set null,
  actor_user_id uuid,
  action text not null,
  detail jsonb not null default '{}',
  created_at timestamptz not null default now()
);

-- Unprivileged application role: not owner, no BYPASSRLS.
do $$ begin
  if not exists (select 1 from pg_roles where rolname = 'nexus_app') then
    create role nexus_app login password 'nexus_app' nosuperuser nobypassrls;
  end if;
end $$;

create or replace function app_tenant() returns uuid language sql stable as
$$ select nullif(current_setting('app.tenant_id', true), '')::uuid $$;

alter table leads enable row level security;
alter table leads force row level security;
create policy leads_isolation on leads
  using (tenant_id = app_tenant()) with check (tenant_id = app_tenant());

alter table audit_logs enable row level security;
alter table audit_logs force row level security;
create policy audit_isolation on audit_logs
  using (tenant_id = app_tenant()) with check (tenant_id = app_tenant());

alter table memberships enable row level security;
alter table memberships force row level security;
create policy memberships_isolation on memberships
  using (tenant_id = app_tenant()) with check (tenant_id = app_tenant());

alter table tenants enable row level security;
alter table tenants force row level security;
create policy tenants_isolation on tenants using (id = app_tenant());
create policy tenants_insert on tenants for insert with check (true);

grant usage on schema public to nexus_app;
grant select, insert, update, delete on leads, memberships to nexus_app;
grant select, insert on tenants, audit_logs, users to nexus_app;
grant usage, select on all sequences in schema public to nexus_app;
