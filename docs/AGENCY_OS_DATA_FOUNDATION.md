# Operiq Agency OS — Data Foundation

## Status

Iteration 1 architecture package. This is an **additive, opt-in PostgreSQL migration** on branch `feature/agency-os-data-foundation`. It has not been applied to a database, deployed, or connected to the running UI.

## Repository findings

The existing application already has a substantial legacy data layer:

- `backend/data_store.py` defines flat tables for contacts, opportunities, revenue, referral sources, imports, tasks/actions, and business configuration.
- `backend/db.py` supports Supabase/PostgreSQL when `DATABASE_URL` is present and SQLite as a fallback.
- `backend/migrations/001_supabase_schema.sql` initializes the legacy schema.
- `shared/schema.ts` currently defines only a small SQLite users table through Drizzle.

The current model is useful for the existing application, but it does not yet provide a complete tenant-scoped, normalized domain model for a multi-agency product. The new migration deliberately does not rename, drop, or rewrite existing tables.

## Architectural decisions

1. **One workspace per agency.** Every business record is scoped by `agency_id`.
2. **Canonical contacts.** A person is stored once. Prospect, client, referral partner, carrier representative, and other roles are represented separately in `agency_contact_roles`.
3. **Lifecycle entities are distinct.** Leads, clients, policies, opportunities, referrals, activities, and tasks have their own records and foreign-key relationships.
4. **Tenant integrity is enforced twice.** Composite foreign keys prevent cross-agency references; PostgreSQL row-level security (RLS) limits end-user access to agencies where they have an active membership.
5. **Money is explicit.** Currency is stored with revenue; premiums and commissions use `numeric(14,2)`, not floating point.
6. **History is retained.** Important changes are recorded in append-only `agency_audit_events`; business records are archived rather than deleted through ordinary client access.
7. **Sensitive insurance identifiers stay out of the general CRM model.** Policy references are masked display values only. Do not add SSNs, full policy numbers, payment credentials, or medical details to these tables. A separately reviewed encrypted vault and access model would be required if such data is ever needed.
8. **Automation is approval-first.** Rules default to disabled and require approval by default.

## Entity map

- `agency_workspaces` → agency tenant
- `agency_memberships` → user, agency, role and membership status
- `agency_contacts` → canonical people and organizations
- `agency_contact_roles` → many-to-many contact roles
- `agency_leads` → prospect lifecycle and assignment
- `agency_clients` → client relationship and review lifecycle
- `agency_policies` → policy metadata linked to a client
- `agency_opportunities` → pipeline and expected premium/commission
- `agency_referrals` → referrer, referred contact and opportunity attribution
- `agency_activities` → calls, emails, meetings, notes and system events
- `agency_tasks` → assigned operational work
- `agency_revenue_records` → projected, earned, received and reversed revenue
- `agency_automation_rules` → disabled-by-default workflow definitions
- `agency_audit_events` → append-only change history

## Apply safely

1. Confirm the target Supabase project and take a restorable database backup.
2. Apply this migration to a staging database first using the Supabase SQL Editor or a PostgreSQL migration runner.
3. Verify all tables, indexes, triggers, and RLS policies were created.
4. Create an agency workspace and its first owner membership through a trusted server-side provisioning path. Do not allow a browser client to self-assign the owner role.
5. Test two users in two different agencies. Verify that neither can read, update, or reference the other's data.
6. Only after those checks, plan a separate, reviewed backfill from legacy contacts/opportunities/revenue. Do not auto-copy records until tenant ownership and deduplication rules are known.

The migration references Supabase Auth (`auth.users` and `auth.uid()`). If the target database is plain PostgreSQL rather than Supabase, adapt the identity foreign keys and membership helper functions before applying it.

## Important integration caveat

The current Python backend can connect with a server-side `DATABASE_URL`. Depending on the credential used, server-side connections may bypass RLS (for example, a Supabase service-role connection). The API must therefore derive the authenticated user and authorized agency from a trusted session, then include `agency_id` in every query and write. Never trust a client-supplied `agency_id` by itself.

The existing SQLite/legacy tables remain in place. This migration is not wired into the current startup path and should not be run automatically at application boot.

## Next implementation slice

- Add a server-side agency provisioning and membership resolver.
- Add tenant-scoped repository methods for contacts, leads, clients, opportunities and tasks.
- Add contract tests proving cross-tenant isolation and lifecycle transitions.
- Build a one-time migration/backfill plan from legacy records after a specific agency owner and data source are confirmed.
