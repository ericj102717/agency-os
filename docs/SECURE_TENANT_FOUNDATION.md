# Secure Tenant Foundation

## Scope

This iteration introduces a separate authenticated API surface at `/api/agency-os`.
It does not migrate legacy records, alter Operiq Invest, or change the production
database. Legacy Agency OS routes remain in place and are not made tenant-safe by
this module.

## Security model

1. Supabase Auth validates each bearer access token through `/auth/v1/user`.
   The backend never trusts a decoded, unverified JWT or a browser-supplied user ID.
2. Active agency membership is resolved from PostgreSQL for every agency-scoped
   request. Agency IDs select a requested workspace; they do not grant access.
3. Read-only memberships may list records but cannot create them.
4. Contact inserts include an agency-scoped audit event in the same transaction.
5. Contact queries and writes always include the resolved agency ID predicate.
6. Workspace provisioning is performed by the database function
   `agency_os_provision_workspace`, which derives ownership from `auth.uid()`.
7. SQL migration 003 tightens RLS write policies, constrains record assignees and
   audit actors to same-agency memberships, and makes audit events append-only.

## Migration procedure

Migrations are never run automatically during application startup. After confirming
the target is a disposable/staging database and taking a restorable backup, run:

```bash
python backend/scripts/run_agency_os_migrations.py
```

The runner acquires a PostgreSQL advisory lock, applies 002 then 003 in separate
transactions, records SHA-256 checksums, and stops on the first error. If an applied
migration file changes, it refuses to continue; create a new migration instead.
Do not run this against production as part of this iteration.

## Required environment

- `SUPABASE_URL`: Supabase project URL
- `SUPABASE_ANON_KEY`: public anon/publishable key used only to call Supabase Auth
- `DATABASE_URL`: PostgreSQL connection string with permissions to query and write
  the Agency OS schema

Never put a Supabase service-role key in the browser. Do not enable the new API
until migrations 002 and 003 have been reviewed and applied to a staging database.

## API

- `GET /api/agency-os/me/agencies` — current user's active agency memberships
- `GET /api/agency-os/{agency_id}/contacts` — list up to 250 contacts
- `POST /api/agency-os/{agency_id}/contacts` — create a contact and audit event

All routes require `Authorization: Bearer <Supabase access token>`.
The create endpoint rejects `read_only` memberships. Membership roles are read
from PostgreSQL, never from request payloads.

## Staging verification checklist

- Apply migration 002 to an empty disposable Supabase project.
- Apply migration 003 and confirm all constraints and policies compile.
- Create two users and two agencies; each user must see only their own agency.
- Verify cross-agency contact reads return 404 and writes return 404.
- Verify read_only can GET contacts but receives 403 on POST.
- Verify agent can POST a contact and the audit event is created atomically.
- Attempt UPDATE/DELETE against audit events and confirm both fail.
- Attempt assigning a user who is not a member of that agency and confirm FK failure.
- Run `python -m unittest discover -s backend/tests -v`.

## Known boundaries

This is a foundation, not a full application migration. Existing legacy routes still
use their old auth and data paths. Do not expose those routes as multi-tenant APIs.
The new API currently covers agency discovery and the first contacts workflow only.
No migration has been applied to a live database, and no deployment is performed
by this change.
