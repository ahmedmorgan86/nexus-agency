-- Login must find a user's tenants before any tenant context exists.
-- This SECURITY DEFINER function (owned by the migration owner) is the single, narrow RLS bypass.
create or replace function login_memberships(p_user uuid)
returns table (tenant_id uuid, role text)
language sql security definer
set search_path = public
as $$ select m.tenant_id, m.role from memberships m where m.user_id = p_user $$;

revoke all on function login_memberships(uuid) from public;
grant execute on function login_memberships(uuid) to nexus_app;
