# RBAC & Data Isolation Implementation

## Overview

All authenticated users previously saw all ICPs, pipeline runs, leads, and chat sessions regardless of who created them. The `user_id` foreign key existed on `ICPConfig`, `PipelineRun`, and `ChatSession` and was set correctly on creation, but no query ever filtered by `user_id`.

This refactor enforces data isolation so normal users see only their own data, while super_admins see everything.

### Access Rules

| Role | Own data | Others' data | Legacy (NULL user_id) |
|------|----------|--------------|----------------------|
| Normal user | Full CRUD | Invisible (404) | Invisible |
| Super admin | Full CRUD | View + Delete (no edit) | Visible |

---

## Files Created (5)

### `backend/app/auth/authorization.py`

Reusable RBAC helpers used by all route files:

- `is_admin(user)` — checks `user.role == "super_admin"`
- `ownership_filter(user_id_column, user)` — SQLAlchemy WHERE clause; returns `true()` for admins, `column == user.id` for normal users
- `check_resource_access(resource_user_id, user)` — raises 404 if non-owner non-admin (404 instead of 403 to avoid leaking resource existence)
- `check_edit_permission(resource_user_id, user)` — raises 403 if admin tries to edit another user's resource
- `check_delete_permission(resource_user_id, user)` — allows owner OR admin to delete

### `backend/app/auth/context.py`

Context variables for passing user identity into synchronous co-pilot DB tools:

```python
current_user_id = contextvars.ContextVar('current_user_id', default=None)
current_user_is_admin = contextvars.ContextVar('current_user_is_admin', default=False)
```

`asyncio.to_thread` automatically propagates contextvars to the spawned thread.

### `backend/app/models/audit_log.py`

`AuditLog` model with columns: `id`, `user_id`, `action`, `resource_type`, `resource_id`, `details` (JSONB), `ip_address`, `created_at`. Indexed on all filter columns plus a composite index on `(resource_type, resource_id)`.

### `backend/app/services/audit_service.py`

Single async function `log_audit(db, user_id, action, resource_type, ...)`. Fire-and-forget pattern — catches all exceptions, never raises.

### `backend/app/api/admin.py`

Admin-only endpoints (require `super_admin` role):

- `GET /api/v1/admin/audit-logs` — filterable by `resource_type`, `user_id`, `limit` (max 500). Returns logs with resolved user names/emails.
- `GET /api/v1/admin/activity` — returns `user_summaries` (per-user ICP/pipeline counts + last activity), `recent_runs` (last 20 across all users with attribution), `recent_icps` (last 20 across all users with attribution).

---

## Files Modified — Backend (10)

### `backend/app/api/icp.py`

| Endpoint | Change |
|----------|--------|
| `GET /icp` (list) | Filters by `user_id == user.id` for non-admins |
| `GET /icp/{id}` | `check_resource_access(icp.user_id, user)` after fetch |
| `PUT /icp/{id}` | `check_edit_permission(icp.user_id, user)` — blocks admin editing others' ICPs |
| `DELETE /icp/{id}` | `check_delete_permission(icp.user_id, user)` |
| `POST /icp` | Audit log on create |
| All endpoints | `_user` renamed to `user` where needed |

Added `_build_icp_response()` helper that populates `user_name` and `user_email` fields when the requesting user is an admin.

### `backend/app/api/pipeline.py`

| Endpoint | Change |
|----------|--------|
| `POST /pipeline/run` | Verifies user owns the ICP before creating run. Audit log on create. |
| `GET /pipeline/history/list` | `ownership_filter(PipelineRun.user_id, user)` |
| `GET /pipeline/stats/by-icp` | `ownership_filter(PipelineRun.user_id, user)` |
| `GET /pipeline/{run_id}` | `check_resource_access(run.user_id, user)` |
| `DELETE /pipeline/{run_id}` | `check_delete_permission(run.user_id, user)`. Audit log. |
| `POST /pipeline/{run_id}/cancel` | `check_resource_access(run.user_id, user)`. Audit log. |
| `POST .../promote-firmographic` | `check_resource_access(run.user_id, user)` |
| `POST .../promote-first-signal` | `check_resource_access(run.user_id, user)` |
| `POST .../promote-signals` | `check_resource_access(run.user_id, user)` |
| `GET .../companies-by-stage` | Fetches run first, calls `check_resource_access` |
| `GET .../logs` | Fetches run first, calls `check_resource_access` |
| `GET .../stream` | Calls `check_resource_access` when run exists in DB |

Updated `_build_run_response()` to accept optional `requesting_user` param and populate `user_name` for admins.

### `backend/app/api/leads.py`

All endpoints scoped by `run_id`. Added `_get_run_with_access_check()` helper that fetches the `PipelineRun` and calls `check_resource_access`. Applied to all 4 endpoints: `companies`, `disqualified`, `stage-summary`, `export`.

### `backend/app/api/chat.py`

| Endpoint | Change |
|----------|--------|
| `POST /chat/send` | Added `ChatSession.user_id == user.id` to existing session query. Sets `current_user_id` and `current_user_is_admin` contextvars before `asyncio.to_thread(agent, prompt)`. |
| `GET /chat/sessions` | Added `ownership_filter(ChatSession.user_id, user)` |
| `GET /chat/sessions/{id}/messages` | `check_resource_access(session.user_id, user)` |
| `DELETE /chat/sessions/{id}` | `check_delete_permission(session.user_id, user)` |

### `backend/app/api/users.py`

Added audit logging to `POST /users` (invite), `PUT /users/{id}` (update), `DELETE /users/{id}` (delete). Each records the admin's user_id, the action, and relevant details (email, changed_fields).

### `backend/app/api/router.py`

Registered `admin_router` from `app.api.admin`.

### `backend/app/tools/copilot_db_tools.py`

All 7 DB tools scoped by user via contextvars:

| Tool | Scoping method |
|------|---------------|
| `search_companies_semantic` | Raw SQL: conditional `JOIN pipeline_runs` + `WHERE pr.user_id = :user_id` |
| `search_companies_structured` | ORM: `_apply_company_user_filter(query)` |
| `get_company_details` | ORM: joins PipelineRun, filters by user_id |
| `get_icp_details` | ORM: filters `ICPConfig.user_id` |
| `get_pipeline_summary` | ORM: filters `PipelineRun.user_id` |
| `get_data_statistics` | All aggregate queries scoped via `scoped_company_query()` helper + direct user_id filters on PipelineRun/ICPConfig |
| `search_local_companies` | ORM: `_apply_company_user_filter(query)` |

Helper functions added:
- `_get_user_scope()` — reads contextvars, returns `(user_id, is_admin)`
- `_apply_company_user_filter(query)` — joins Company to PipelineRun and filters by user_id for non-admins

### `backend/app/models/__init__.py`

Added `AuditLog` import and registration.

### `backend/app/schemas/icp.py`

Added `user_name: Optional[str] = None` and `user_email: Optional[str] = None` to `ICPConfigResponse`.

### `backend/app/schemas/pipeline.py`

Added `user_name: Optional[str] = None` to `PipelineRunResponse`.

---

## Migration (1)

### `backend/alembic/versions/g1a2b3c4d5e6_add_audit_logs_table.py`

Creates `audit_logs` table with columns and indexes:

```
audit_logs:
  id          UUID PK (gen_random_uuid)
  user_id     UUID FK -> users.id (indexed)
  action      String(50) NOT NULL (indexed)
  resource_type String(50) NOT NULL (indexed)
  resource_id UUID (indexed)
  details     JSONB
  ip_address  String(45)
  created_at  DateTime with tz (server_default=now(), indexed)

Composite index: (resource_type, resource_id)
```

Revision chain: `704565025b67` -> `g1a2b3c4d5e6`

---

## Files Modified — Frontend (5)

### `frontend/src/types/index.ts`

- Added `user_name?: string | null` and `user_email?: string | null` to `ICPConfig`
- Added `user_name?: string | null` to `PipelineRun`
- New interfaces: `AdminUserSummary`, `AdminActivityResponse`, `AuditLogEntry`

### `frontend/src/api/pipelineApi.ts`

Added `getAdminActivity()` — calls `GET /admin/activity`.

### `frontend/src/api/usersApi.ts`

Added `getAuditLogs(params?)` — calls `GET /admin/audit-logs` with optional filters.

### `frontend/src/pages/DashboardPage.tsx`

- Imports `useAuth` to check admin role
- Fetches admin activity data on mount when user is super_admin
- Renders admin activity section at bottom of page (conditionally for admins):
  - **User Activity Summary Table** — name, email, role, ICP count, pipeline count, last activity
  - **Recent Searches Table** — run name, user attribution, status, date (across all users)
  - **Recent ICPs Table** — ICP name, user attribution, created date (across all users)
- Shows "by {user_name}" badge on pipeline run cards for admin users

### `frontend/src/pages/ICPListPage.tsx`

- Imports `useAuth` to check admin role
- Shows "by {user_name}" next to ICP name on cards for admin users

---

## Verification Checklist

| # | Scenario | Expected |
|---|----------|----------|
| 1 | User A creates ICP-1, User B calls `GET /icp` | User B does NOT see ICP-1; Admin sees it |
| 2 | User A starts pipeline, User B calls `GET /pipeline/history/list` | User B does NOT see it |
| 3 | User B calls `GET /leads/{run_id}/companies` with User A's run_id | 404 |
| 4 | User B calls `GET /pipeline/{run_id}/stream` with User A's run_id | 404 |
| 5 | Admin calls `PUT /icp/{id}` on User A's ICP | 403 (edit blocked) |
| 6 | Admin calls `DELETE /icp/{id}` on User A's ICP | Success |
| 7 | Legacy data (NULL user_id) | Invisible to normal users, visible to admin |
| 8 | Co-pilot: User B asks "show me all companies" | Only sees own data; Admin sees all |
| 9 | Create/update/delete ICP | Entries appear in `GET /admin/audit-logs` |
| 10 | Admin dashboard | Shows user activity table + pipeline runs with user attribution |
