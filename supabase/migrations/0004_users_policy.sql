-- NEXUS 0004: user table policies.
-- `users` is not tenant-scoped (a user can belong to several tenants), so it cannot use
-- the app.tenant_id policy. Registration needs INSERT; reading a password hash is only
-- possible through the narrow SECURITY DEFINER function below, never via a plain SELECT.

alter table users enable row level security;
alter table users force row level security;

drop policy if exists users_signup on users;
create policy users_signup on users for insert with check (true);

create or replace function login_lookup(p_email text)
returns table (id uuid, password_hash text)
language sql security definer
set search_path = public
as $$ select u.id, u.password_hash from users u where u.email = lower(p_email) $$;

revoke all on function login_lookup(text) from public;
grant execute on function login_lookup(text) to nexus_app;

-- The application role may create accounts but must never read hashes directly.
revoke select on users from nexus_app;
grant insert on users to nexus_app;
