-- Operiq Agency OS — foundational multi-tenant data model
-- Additive migration. Does not alter or backfill the legacy contacts/opportunities tables.
-- Apply to a staging Supabase/PostgreSQL database first, after a verified backup.
-- Requires Supabase Auth (auth.uid()) for end-user RLS policies.

create table if not exists public.agency_workspaces (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  slug text not null unique,
  industry text not null default 'insurance',
  timezone text not null default 'America/Denver',
  currency_code char(3) not null default 'USD',
  status text not null default 'active' check (status in ('active','suspended','archived')),
  created_by uuid references auth.users(id) on delete set null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.agency_memberships (
  id uuid primary key default gen_random_uuid(),
  agency_id uuid not null references public.agency_workspaces(id) on delete cascade,
  user_id uuid not null references auth.users(id) on delete cascade,
  role text not null default 'agent' check (role in ('owner','admin','manager','agent','service','read_only')),
  status text not null default 'active' check (status in ('invited','active','suspended','removed')),
  invited_at timestamptz,
  joined_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (agency_id, user_id),
  unique (agency_id, id)
);

create table if not exists public.agency_contacts (
  id uuid primary key default gen_random_uuid(),
  agency_id uuid not null references public.agency_workspaces(id) on delete cascade,
  first_name text not null,
  last_name text not null default '',
  display_name text generated always as (trim(first_name || ' ' || last_name)) stored,
  email text,
  normalized_email text generated always as (nullif(lower(trim(email)), '')) stored,
  phone text,
  normalized_phone text,
  organization_name text,
  preferred_contact_method text check (preferred_contact_method in ('email','phone','sms','mail','none')),
  lifecycle_status text not null default 'active' check (lifecycle_status in ('active','inactive','do_not_contact','archived')),
  source text,
  notes text,
  created_by uuid references auth.users(id) on delete set null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (agency_id, id)
);

-- A person may be a prospect, client, referral partner, or several of these over time.
create table if not exists public.agency_contact_roles (
  id uuid primary key default gen_random_uuid(),
  agency_id uuid not null,
  contact_id uuid not null,
  role text not null check (role in ('prospect','client','referral_partner','vendor','carrier_rep','other')),
  status text not null default 'active' check (status in ('active','inactive','archived')),
  started_at timestamptz not null default now(),
  ended_at timestamptz,
  created_at timestamptz not null default now(),
  foreign key (agency_id, contact_id) references public.agency_contacts(agency_id, id) on delete cascade,
  unique (agency_id, contact_id, role)
);

create table if not exists public.agency_leads (
  id uuid primary key default gen_random_uuid(),
  agency_id uuid not null,
  contact_id uuid not null,
  assigned_to uuid references auth.users(id) on delete set null,
  lead_source text,
  campaign text,
  stage text not null default 'new' check (stage in ('new','contacted','qualified','appointment_set','proposal','closing','won','lost','nurture')),
  status text not null default 'open' check (status in ('open','converted','disqualified','archived')),
  score numeric(5,2) check (score is null or (score >= 0 and score <= 100)),
  score_explanation jsonb not null default '{}'::jsonb,
  first_contact_at timestamptz,
  converted_at timestamptz,
  lost_reason text,
  notes text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  foreign key (agency_id, contact_id) references public.agency_contacts(agency_id, id) on delete restrict,
  unique (agency_id, id),
  unique (agency_id, contact_id)
);

create table if not exists public.agency_clients (
  id uuid primary key default gen_random_uuid(),
  agency_id uuid not null,
  contact_id uuid not null,
  assigned_to uuid references auth.users(id) on delete set null,
  lifecycle_status text not null default 'active' check (lifecycle_status in ('active','at_risk','inactive','former')),
  client_since date,
  next_review_at date,
  lifetime_revenue numeric(14,2) not null default 0 check (lifetime_revenue >= 0),
  notes text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  foreign key (agency_id, contact_id) references public.agency_contacts(agency_id, id) on delete restrict,
  unique (agency_id, id),
  unique (agency_id, contact_id)
);

create table if not exists public.agency_policies (
  id uuid primary key default gen_random_uuid(),
  agency_id uuid not null,
  client_id uuid not null,
  carrier_name text,
  product_line text not null,
  policy_reference_masked text,
  status text not null default 'active' check (status in ('quote','pending','active','renewal_due','cancelled','expired')),
  effective_date date,
  renewal_date date,
  premium_amount numeric(14,2) check (premium_amount is null or premium_amount >= 0),
  premium_frequency text check (premium_frequency in ('monthly','quarterly','semi_annual','annual','single','other')),
  notes text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  foreign key (agency_id, client_id) references public.agency_clients(agency_id, id) on delete restrict,
  unique (agency_id, id)
);

create table if not exists public.agency_opportunities (
  id uuid primary key default gen_random_uuid(),
  agency_id uuid not null,
  contact_id uuid not null,
  lead_id uuid,
  client_id uuid,
  assigned_to uuid references auth.users(id) on delete set null,
  title text not null,
  product_line text,
  stage text not null default 'new' check (stage in ('new','discovery','quoted','proposal','closing','won','lost','on_hold')),
  status text not null default 'open' check (status in ('open','won','lost','cancelled')),
  estimated_premium numeric(14,2) not null default 0 check (estimated_premium >= 0),
  estimated_commission numeric(14,2) not null default 0 check (estimated_commission >= 0),
  probability integer not null default 0 check (probability between 0 and 100),
  expected_close_date date,
  closed_at timestamptz,
  lost_reason text,
  source text,
  notes text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  foreign key (agency_id, contact_id) references public.agency_contacts(agency_id, id) on delete restrict,
  foreign key (agency_id, lead_id) references public.agency_leads(agency_id, id) on delete restrict,
  foreign key (agency_id, client_id) references public.agency_clients(agency_id, id) on delete restrict,
  unique (agency_id, id)
);

create table if not exists public.agency_referrals (
  id uuid primary key default gen_random_uuid(),
  agency_id uuid not null,
  referrer_contact_id uuid not null,
  referred_contact_id uuid not null,
  opportunity_id uuid,
  status text not null default 'received' check (status in ('received','contacted','qualified','converted','declined','invalid')),
  referred_at timestamptz not null default now(),
  converted_at timestamptz,
  attribution_value numeric(14,2) not null default 0 check (attribution_value >= 0),
  source_notes text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  foreign key (agency_id, referrer_contact_id) references public.agency_contacts(agency_id, id) on delete restrict,
  foreign key (agency_id, referred_contact_id) references public.agency_contacts(agency_id, id) on delete restrict,
  foreign key (agency_id, opportunity_id) references public.agency_opportunities(agency_id, id) on delete restrict,
  unique (agency_id, id),
  check (referrer_contact_id <> referred_contact_id)
);

create table if not exists public.agency_activities (
  id uuid primary key default gen_random_uuid(),
  agency_id uuid not null,
  contact_id uuid,
  opportunity_id uuid,
  policy_id uuid,
  actor_user_id uuid references auth.users(id) on delete set null,
  activity_type text not null check (activity_type in ('call','email','sms','meeting','note','task_update','policy_update','system_event','other')),
  direction text check (direction in ('inbound','outbound','internal')),
  subject text,
  summary text not null,
  occurred_at timestamptz not null default now(),
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  foreign key (agency_id, contact_id) references public.agency_contacts(agency_id, id) on delete restrict,
  foreign key (agency_id, opportunity_id) references public.agency_opportunities(agency_id, id) on delete restrict,
  foreign key (agency_id, policy_id) references public.agency_policies(agency_id, id) on delete restrict,
  unique (agency_id, id)
);

create table if not exists public.agency_tasks (
  id uuid primary key default gen_random_uuid(),
  agency_id uuid not null references public.agency_workspaces(id) on delete cascade,
  contact_id uuid,
  opportunity_id uuid,
  assigned_to uuid references auth.users(id) on delete set null,
  created_by uuid references auth.users(id) on delete set null,
  title text not null,
  description text,
  task_type text not null default 'follow_up',
  priority text not null default 'normal' check (priority in ('low','normal','high','urgent')),
  status text not null default 'open' check (status in ('open','in_progress','blocked','completed','cancelled')),
  due_at timestamptz,
  completed_at timestamptz,
  source_module text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  foreign key (agency_id, contact_id) references public.agency_contacts(agency_id, id) on delete restrict,
  foreign key (agency_id, opportunity_id) references public.agency_opportunities(agency_id, id) on delete restrict,
  unique (agency_id, id)
);

create table if not exists public.agency_revenue_records (
  id uuid primary key default gen_random_uuid(),
  agency_id uuid not null,
  client_id uuid,
  opportunity_id uuid,
  revenue_type text not null default 'commission',
  amount numeric(14,2) not null check (amount >= 0),
  currency_code char(3) not null default 'USD',
  status text not null default 'projected' check (status in ('projected','earned','received','reversed','cancelled')),
  earned_at date,
  received_at date,
  source text,
  external_reference text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  foreign key (agency_id, client_id) references public.agency_clients(agency_id, id) on delete restrict,
  foreign key (agency_id, opportunity_id) references public.agency_opportunities(agency_id, id) on delete restrict,
  unique (agency_id, id)
);

create table if not exists public.agency_automation_rules (
  id uuid primary key default gen_random_uuid(),
  agency_id uuid not null references public.agency_workspaces(id) on delete cascade,
  name text not null,
  description text,
  trigger_event text not null,
  conditions jsonb not null default '{}'::jsonb,
  actions jsonb not null default '[]'::jsonb,
  enabled boolean not null default false,
  requires_approval boolean not null default true,
  created_by uuid references auth.users(id) on delete set null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (agency_id, id),
  unique (agency_id, name)
);

-- Append-only record of consequential data and automation changes.
create table if not exists public.agency_audit_events (
  id uuid primary key default gen_random_uuid(),
  agency_id uuid not null references public.agency_workspaces(id) on delete cascade,
  actor_user_id uuid references auth.users(id) on delete set null,
  event_type text not null,
  entity_type text not null,
  entity_id uuid,
  before_data jsonb,
  after_data jsonb,
  source text not null default 'application',
  correlation_id text,
  occurred_at timestamptz not null default now()
);

create index if not exists idx_agency_memberships_user on public.agency_memberships(user_id, status);
create index if not exists idx_agency_contacts_email on public.agency_contacts(agency_id, normalized_email) where normalized_email is not null;
create index if not exists idx_agency_contacts_phone on public.agency_contacts(agency_id, normalized_phone) where normalized_phone is not null;
create index if not exists idx_agency_roles_role on public.agency_contact_roles(agency_id, role, status);
create index if not exists idx_agency_leads_stage on public.agency_leads(agency_id, stage, status);
create index if not exists idx_agency_leads_assignee on public.agency_leads(agency_id, assigned_to, status);
create index if not exists idx_agency_clients_review on public.agency_clients(agency_id, next_review_at) where lifecycle_status = 'active';
create index if not exists idx_agency_policies_renewal on public.agency_policies(agency_id, renewal_date) where status = 'active';
create index if not exists idx_agency_opportunities_pipeline on public.agency_opportunities(agency_id, stage, status);
create index if not exists idx_agency_opportunities_close on public.agency_opportunities(agency_id, expected_close_date) where status = 'open';
create index if not exists idx_agency_referrals_referrer on public.agency_referrals(agency_id, referrer_contact_id, referred_at desc);
create index if not exists idx_agency_activities_contact on public.agency_activities(agency_id, contact_id, occurred_at desc);
create index if not exists idx_agency_tasks_queue on public.agency_tasks(agency_id, status, priority, due_at);
create index if not exists idx_agency_revenue_date on public.agency_revenue_records(agency_id, earned_at, status);
create index if not exists idx_agency_audit_entity on public.agency_audit_events(agency_id, entity_type, entity_id, occurred_at desc);
create index if not exists idx_agency_audit_recent on public.agency_audit_events(agency_id, occurred_at desc);

create or replace function public.agency_os_set_updated_at()
returns trigger language plpgsql as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

do $$
declare
  table_name text;
begin
  foreach table_name in array array[
    'agency_workspaces','agency_memberships','agency_contacts','agency_leads',
    'agency_clients','agency_policies','agency_opportunities','agency_referrals',
    'agency_tasks','agency_revenue_records','agency_automation_rules'
  ]
  loop
    execute format('drop trigger if exists %I_set_updated_at on public.%I', table_name, table_name);
    execute format('create trigger %I_set_updated_at before update on public.%I for each row execute function public.agency_os_set_updated_at()', table_name, table_name);
  end loop;
end;
$$;

create or replace function public.agency_os_is_member(target_agency_id uuid)
returns boolean
language sql
stable
security definer
set search_path = public
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
set search_path = public
as $$
  select exists (
    select 1 from public.agency_memberships m
    where m.agency_id = target_agency_id
      and m.user_id = auth.uid()
      and m.status = 'active'
      and m.role in ('owner','admin')
  );
$$;

alter table public.agency_workspaces enable row level security;
alter table public.agency_memberships enable row level security;
alter table public.agency_contacts enable row level security;
alter table public.agency_contact_roles enable row level security;
alter table public.agency_leads enable row level security;
alter table public.agency_clients enable row level security;
alter table public.agency_policies enable row level security;
alter table public.agency_opportunities enable row level security;
alter table public.agency_referrals enable row level security;
alter table public.agency_activities enable row level security;
alter table public.agency_tasks enable row level security;
alter table public.agency_revenue_records enable row level security;
alter table public.agency_automation_rules enable row level security;
alter table public.agency_audit_events enable row level security;

-- Workspace visibility and admin-only workspace edits.
drop policy if exists agency_workspace_member_select on public.agency_workspaces;
create policy agency_workspace_member_select on public.agency_workspaces
  for select using (public.agency_os_is_member(id));
drop policy if exists agency_workspace_admin_update on public.agency_workspaces;
create policy agency_workspace_admin_update on public.agency_workspaces
  for update using (public.agency_os_is_admin(id)) with check (public.agency_os_is_admin(id));

-- Memberships: users see their own memberships; agency admins can manage membership.
drop policy if exists agency_membership_select on public.agency_memberships;
create policy agency_membership_select on public.agency_memberships
  for select using (user_id = auth.uid() or public.agency_os_is_admin(agency_id));
drop policy if exists agency_membership_admin_insert on public.agency_memberships;
create policy agency_membership_admin_insert on public.agency_memberships
  for insert with check (public.agency_os_is_admin(agency_id));
drop policy if exists agency_membership_admin_update on public.agency_memberships;
create policy agency_membership_admin_update on public.agency_memberships
  for update using (public.agency_os_is_admin(agency_id)) with check (public.agency_os_is_admin(agency_id));

-- Standard tenant-scoped access for mutable agency records. No client-side DELETE policy:
-- archive records instead; destructive cleanup belongs in a controlled admin workflow.
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
    execute format('drop policy if exists %I_member_select on public.%I', table_name, table_name);
    execute format('create policy %I_member_select on public.%I for select using (public.agency_os_is_member(agency_id))', table_name, table_name);
    execute format('drop policy if exists %I_member_insert on public.%I', table_name, table_name);
    execute format('create policy %I_member_insert on public.%I for insert with check (public.agency_os_is_member(agency_id))', table_name, table_name);
    execute format('drop policy if exists %I_member_update on public.%I', table_name, table_name);
    execute format('create policy %I_member_update on public.%I for update using (public.agency_os_is_member(agency_id)) with check (public.agency_os_is_member(agency_id))', table_name, table_name);
  end loop;
end;
$$;

-- Audit events are readable and appendable by members, but never mutable through RLS.
drop policy if exists agency_audit_member_select on public.agency_audit_events;
create policy agency_audit_member_select on public.agency_audit_events
  for select using (public.agency_os_is_member(agency_id));
drop policy if exists agency_audit_member_insert on public.agency_audit_events;
create policy agency_audit_member_insert on public.agency_audit_events
  for insert with check (public.agency_os_is_member(agency_id));

comment on table public.agency_contacts is 'Canonical person and organization records. Roles live in agency_contact_roles.';
comment on table public.agency_leads is 'Prospect lifecycle records linked to canonical contacts.';
comment on table public.agency_clients is 'Client relationship records linked to canonical contacts.';
comment on table public.agency_audit_events is 'Append-only audit trail for consequential agency changes.';
comment on column public.agency_policies.policy_reference_masked is 'Masked display reference only; do not store SSNs, full policy numbers, or other high-risk identifiers here.';
