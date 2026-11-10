-- Operiq Agency OS secure tenant hardening.
-- Apply only after migration 002 has been reviewed and applied to a disposable/staging database.
-- This migration tightens role permissions, binds assignments to agency memberships,
-- makes audit events append-only, and adds trusted workspace provisioning.


-- Replace the two SECURITY DEFINER helpers created by migration 002 with an
-- explicit safe search_path. Keep public objects schema-qualified in these functions.
create or replace function public.agency_os_is_member(target_agency_id uuid)
returns boolean
language sql
stable
security definer
set search_path = public, pg_temp
as $$
  select exists (
    select 1 from public.agency_memberships m
    where m.agency_id = target_agency_id
      and m.user_id = auth.uid()
      and m.status = 'active'
  );
$$;

create or replace function public.agency_os_is_admin(target_agency_id uuid)
returns boolean
language sql
stable
security definer
set search_path = public, pg_temp
as $$
  select exists (
    select 1 from public.agency_memberships m
    where m.agency_id = target_agency_id
      and m.user_id = auth.uid()
      and m.status = 'active'
      and m.role in ('owner','admin')
  );
$$;

revoke all on function public.agency_os_is_member(uuid) from public;
revoke all on function public.agency_os_is_admin(uuid) from public;
grant execute on function public.agency_os_is_member(uuid) to authenticated;
grant execute on function public.agency_os_is_admin(uuid) to authenticated;

create or replace function public.agency_os_role(target_agency_id uuid)
returns text
language sql stable security definer
set search_path = public, pg_temp
as $$
  select m.role
  from public.agency_memberships m
  where m.agency_id = target_agency_id
    and m.user_id = auth.uid()
    and m.status = 'active'
  limit 1;
$$;

create or replace function public.agency_os_can_write(target_agency_id uuid)
returns boolean
language sql stable security definer
set search_path = public, pg_temp
as $$
  select coalesce(public.agency_os_role(target_agency_id) in
    ('owner','admin','manager','agent','service'), false);
$$;

create or replace function public.agency_os_is_owner(target_agency_id uuid)
returns boolean
language sql stable security definer
set search_path = public, pg_temp
as $$
  select coalesce(public.agency_os_role(target_agency_id) = 'owner', false);
$$;

revoke all on function public.agency_os_role(uuid) from public;
revoke all on function public.agency_os_can_write(uuid) from public;
revoke all on function public.agency_os_is_owner(uuid) from public;
grant execute on function public.agency_os_role(uuid) to authenticated;
grant execute on function public.agency_os_can_write(uuid) to authenticated;
grant execute on function public.agency_os_is_owner(uuid) to authenticated;

-- Read-only members can read but cannot insert or update agency records.
do $$
declare
  table_name text;
begin
  foreach table_name in array array[
    'agency_contacts','agency_contact_roles','agency_leads','agency_clients',
    'agency_policies','agency_opportunities','agency_referrals','agency_activities',
    'agency_tasks','agency_revenue_records','agency_automation_rules'
  ]
  loop
    execute format('drop policy if exists %I_member_insert on public.%I', table_name, table_name);
    execute format('create policy %I_member_insert on public.%I for insert with check (public.agency_os_can_write(agency_id))', table_name, table_name);
    execute format('drop policy if exists %I_member_update on public.%I', table_name, table_name);
    execute format('create policy %I_member_update on public.%I for update using (public.agency_os_can_write(agency_id)) with check (public.agency_os_can_write(agency_id))', table_name, table_name);
  end loop;
end;
$$;

-- Only the owner may change membership records. This prevents admins from
-- elevating themselves or another member to owner through the membership table.
drop policy if exists agency_membership_admin_insert on public.agency_memberships;
create policy agency_membership_owner_insert on public.agency_memberships
  for insert with check (public.agency_os_is_owner(agency_id));
drop policy if exists agency_membership_admin_update on public.agency_memberships;
create policy agency_membership_owner_update on public.agency_memberships
  for update using (public.agency_os_is_owner(agency_id))
  with check (public.agency_os_is_owner(agency_id));

-- A user can only be assigned to records in an agency where they have a membership.
-- Existing orphan assignments must be reconciled before this migration is applied.
do $$
declare
  table_name text;
begin
  foreach table_name in array array[
    'agency_leads','agency_clients','agency_opportunities','agency_tasks'
  ]
  loop
    execute format(
      'alter table public.%I add constraint %I foreign key (agency_id, assigned_to) references public.agency_memberships(agency_id, user_id) on delete restrict',
      table_name, table_name || '_assigned_member_fk'
    );
  end loop;
end;
$$;

-- Audit actors must belong to the same agency. Null actor is reserved for trusted
-- system events. Append-only trigger prevents UPDATE/DELETE even for ordinary SQL roles.
alter table public.agency_audit_events
  add constraint agency_audit_actor_member_fk
  foreign key (agency_id, actor_user_id)
  references public.agency_memberships(agency_id, user_id)
  on delete restrict;

create or replace function public.agency_os_reject_audit_mutation()
returns trigger language plpgsql
as $$
begin
  raise exception 'agency_audit_events is append-only';
end;
$$;

drop trigger if exists agency_audit_events_append_only on public.agency_audit_events;
create trigger agency_audit_events_append_only
  before update or delete on public.agency_audit_events
  for each row execute function public.agency_os_reject_audit_mutation();

-- Trusted first-workspace provisioning: the authenticated caller becomes owner.
-- No client-supplied user_id is accepted.
create or replace function public.agency_os_provision_workspace(
  workspace_name text,
  workspace_slug text,
  workspace_industry text default 'insurance'
)
returns uuid
language plpgsql
security definer
set search_path = public, auth, pg_temp
as $$
declare
  caller_id uuid := auth.uid();
  new_agency_id uuid;
begin
  if caller_id is null then
    raise exception 'Authentication required' using errcode = '28000';
  end if;
  if nullif(trim(workspace_name), '') is null then
    raise exception 'Workspace name is required' using errcode = '22023';
  end if;
  if workspace_slug !~ '^[a-z0-9][a-z0-9-]{2,47}$' then
    raise exception 'Workspace slug must be 3-48 lowercase letters, numbers, or hyphens' using errcode = '22023';
  end if;

  insert into public.agency_workspaces (name, slug, industry, created_by)
  values (trim(workspace_name), workspace_slug, coalesce(nullif(trim(workspace_industry), ''), 'insurance'), caller_id)
  returning id into new_agency_id;

  insert into public.agency_memberships (agency_id, user_id, role, status, joined_at)
  values (new_agency_id, caller_id, 'owner', 'active', now());

  return new_agency_id;
end;
$$;

revoke all on function public.agency_os_provision_workspace(text, text, text) from public;
grant execute on function public.agency_os_provision_workspace(text, text, text) to authenticated;

comment on function public.agency_os_provision_workspace(text, text, text)
  is 'Creates an agency workspace and makes auth.uid() its owner; caller identity is never accepted as an argument.';

-- Assignment must target an active member, not merely a historical membership row.
create or replace function public.agency_os_validate_assignee()
returns trigger language plpgsql
set search_path = public, pg_temp
as $$
begin
  if new.assigned_to is not null and not exists (
    select 1 from public.agency_memberships m
    where m.agency_id = new.agency_id
      and m.user_id = new.assigned_to
      and m.status = 'active'
  ) then
    raise exception 'assigned_to must be an active member of this agency'
      using errcode = '23514';
  end if;
  return new;
end;
$$;

do $$
declare
  table_name text;
begin
  foreach table_name in array array[
    'agency_leads','agency_clients','agency_opportunities','agency_tasks'
  ]
  loop
    execute format('drop trigger if exists %I_active_assignee on public.%I', table_name, table_name);
    execute format(
      'create trigger %I_active_assignee before insert or update of assigned_to, agency_id on public.%I for each row execute function public.agency_os_validate_assignee()',
      table_name, table_name
    );
  end loop;
end;
$$;
