# qlGen Improvement Plan — 7 Features

## Context

A sales team head tested qlGen and identified 7 usability gaps. These span Excel import for bulk ICP creation, agent log persistence, ICP-to-pipeline traceability, BANT source citations, interactive dashboard tiles, a descriptive home screen, and better long-running pipeline communication. This plan addresses all 7 in a carefully sequenced order that respects dependencies and minimizes rework.

---

## Implementation Order

| Phase | Feature | Scope |
|-------|---------|-------|
| 1 | #6 Descriptive Home Screen | Frontend only |
| 2 | #3 Link ICP to Pipeline Runs | Backend schema + Frontend (3 pages) |
| 3 | #2 Persist Agent Logs | New DB table + Backend service + Frontend |
| 4 | #7 Pipeline Duration Communication | Backend + Frontend |
| 5 | #4 BANT Source Citations | DB columns + Agent prompt + Backend + Frontend |
| 6 | #1 Excel Import for ICP | New backend service + Frontend modal |
| 7 | #5 Clickable Dashboard Tiles | New backend endpoint + Frontend modal |

**Dependencies:** #7 depends on #2 (persisted logs enable "return later"). #5 depends on #3 (ICP names needed for breakdown). All others are independent.

**Single Alembic migration** covers all DB changes (#2 new table + #4 new columns).

---

## Phase 1: Descriptive Home Screen (#6)

**Problem:** New users see an empty dashboard with no explanation of what qlGen does.

### Files to modify
- `frontend/src/pages/DashboardPage.tsx`

### Changes
1. Add a **welcome banner** above the metric tiles with:
   - App title and one-liner description ("AI-powered qualified lead generation")
   - 4-step visual flow: Define ICP → Run Pipeline → Review Leads → Export & Act
   - Each step as a numbered card with title + short description
   - Styled with gradient background using existing `--purple-pale` CSS variable
2. Enhance the **empty state** (when `runs.length === 0`) with a more descriptive getting-started CTA: "Create your first ICP to get started" with a prominent button
3. Add a collapsible flag via `localStorage.getItem('qlgen_welcome_dismissed')` so returning users can dismiss the banner

---

## Phase 2: Link ICP Configuration to Pipeline Runs (#3)

**Problem:** The `icp_config_id` FK exists on `PipelineRun` but ICP details aren't shown in the UI. Users can't identify which ICP a pipeline run came from.

### Files to modify
- `backend/app/schemas/pipeline.py` — Add `icp_name: Optional[str]` and `icp_description: Optional[str]` to `PipelineRunResponse`
- `backend/app/api/pipeline.py` — Eagerly load `icp_config` relationship via `selectinload(PipelineRun.icp_config)` in `list_pipeline_runs`, `get_pipeline_status`, and `start_pipeline`. Populate new schema fields from `run.icp_config.name`
- `frontend/src/types/index.ts` — Add `icp_name?: string | null` and `icp_description?: string | null` to `PipelineRun` interface
- `frontend/src/pages/DashboardPage.tsx` — Replace `Run #{run.id}` (line 99) with `run.icp_name || Run #${run.id.substring(0,8)}`
- `frontend/src/pages/PipelinePage.tsx` — Show ICP name in the progress header alongside "Generating Leads"
- `frontend/src/pages/LeadsPage.tsx` — Fetch pipeline run info via `getPipelineStatus(runId)` and show ICP name as a `Tag` above the summary bar

### No DB migration needed
The FK relationship already exists and works.

---

## Phase 3: Persist Agent Logs (#2)

**Problem:** Agent reasoning, tool calls, and stage updates are held in an in-memory dict (`pipeline_events`) and lost when the page is closed or server restarts. Users cannot review historical agent activity.

### Database changes — New table `pipeline_logs`

**New file:** `backend/app/models/pipeline_log.py`
```
PipelineLog:
  id              UUID PK
  pipeline_run_id UUID FK→pipeline_runs (indexed)
  event_type      String(50)   — stage_update | tool_start | agent_reasoning | completed | error
  event_data      JSONB        — full event payload
  sequence_number Integer      — ordering within a run
  created_at      DateTime(tz) — server_default=now()
```

### Backend changes

- `backend/app/models/pipeline_log.py` — New model file (above)
- `backend/app/models/__init__.py` — Add `PipelineLog` import
- `backend/app/models/pipeline.py` — Add `logs` relationship: `relationship("PipelineLog", back_populates="pipeline_run", cascade="all, delete-orphan")`
- `backend/app/agent/lead_gen_agent.py` — Modify `create_pipeline_callback_handler` to accept an `event_collector: list` parameter. The `_emit()` inner function appends to both the SSE events dict AND the collector list
- `backend/app/services/pipeline_service.py` — Create `event_collector = []`, pass it to callback handler. After agent completes (back in async context), batch-insert all collected events as `PipelineLog` rows before the final `db.commit()`. This avoids thread-safety issues since DB writes happen in the async context, not inside the synchronous agent thread
- `backend/app/api/pipeline.py` — New endpoint `GET /{run_id}/logs` returning persisted log entries ordered by `sequence_number`
- `backend/app/schemas/pipeline.py` — Add `PipelineLogResponse` schema
- `backend/alembic/env.py` — Add `PipelineLog` to imports

### Frontend changes

- `frontend/src/api/pipelineApi.ts` — Add `getPipelineLogs(runId)` function
- `frontend/src/types/index.ts` — Add `PipelineLogEntry` interface
- `frontend/src/pages/PipelinePage.tsx` — When loading a completed/failed run, call `getPipelineLogs(runId)` and populate the activity log from persisted data. The existing `ActivityEntry` type maps directly from `event_data` fields

---

## Phase 4: Better Pipeline Duration Communication (#7)

**Problem:** Pipeline runs take 5-10+ minutes. Users don't know how long to wait, whether they can leave, or how to return to see results.

### Backend changes

- `backend/app/api/pipeline.py` — In the SSE `stream_pipeline` endpoint, check if the run is already completed/failed before starting the generator. If so, send the terminal event immediately and close. This handles the "user returns later" case gracefully
- `backend/app/schemas/pipeline.py` — Add `estimated_duration_seconds: Optional[int]` to `PipelineRunResponse`
- `backend/app/api/pipeline.py` — Calculate estimate from options: `max_companies * 20 + 60` seconds (rough heuristic)

### Frontend changes — `frontend/src/pages/PipelinePage.tsx`

1. **Duration estimate banner** — Replace the coffee hint with a structured info box:
   - "Estimated duration: ~X minutes"
   - "You can safely leave this page — results are saved automatically"
   - "Go to Dashboard" link button
2. **Dynamic remaining time** — Use elapsed time + current stage progress to estimate remaining time
3. **"Safe to leave" messaging** — Prominent banner in the left panel with reassuring copy
4. **Return-to-results behavior** — When navigating to `/pipeline/{runId}` for an already-completed run, show a success notification (`message.success`) and load persisted logs from Phase 3
5. **Dashboard running indicator** — In `DashboardPage.tsx`, add a pulsing dot or spinner on run cards with `status === 'running'`

---

## Phase 5: BANT Source Citations (#4)

**Problem:** BANT reasoning has no proof or external references. Sales people can't verify the justifications.

**Decision:** Sources are **mandatory** — the agent MUST provide at least one source URL per BANT dimension, even if it requires additional verification searches. This may increase pipeline duration slightly but ensures every score is verifiable.

### Database changes — New columns on `bant_scores`

- `backend/app/models/bant.py` — Add 4 JSONB columns:
  ```
  budget_sources    JSONB  — [{"url": "...", "title": "...", "tool": "tavily"}]
  authority_sources JSONB
  need_sources      JSONB
  timing_sources    JSONB
  ```

### Alembic migration (combined with Phase 3)

Single migration file covering both the new `pipeline_logs` table and the 4 new `bant_scores` columns.

### Agent prompt changes — `backend/app/agent/lead_gen_agent.py`

Modify `LEAD_GEN_SYSTEM_PROMPT`:
1. In STAGE 4 instructions, add: "For each BANT dimension, you MUST include `*_sources` — a list of `{url, title, tool}` objects citing where you found the evidence. Every dimension requires at least one source. If you lack a source for a dimension, use tavily_search, exa_search, or scrape_webpage to find supporting evidence before scoring."
2. In the OUTPUT FORMAT JSON example, add `budget_sources`, `authority_sources`, `need_sources`, `timing_sources` arrays to the `bant_score` object with realistic example citations
3. Update CRITICAL RULE #5: "Every BANT score MUST have evidence-backed reasoning AND at least one source URL per dimension. No score without a citation."

### Backend changes

- `backend/app/schemas/company.py` — Add `BANTSourceCitation` model (`url: str, title: Optional[str], tool: Optional[str]`) and add 4 source list fields to `BANTScoreResponse`
- `backend/app/services/pipeline_service.py` — In BANT saving section (lines 170-183), add `.get("budget_sources")` etc. to the `BANTScore` constructor
- `backend/app/api/leads.py` — Include source fields in `BANTScoreResponse` construction
- `backend/app/services/export_service.py` — Optionally add a "Sources" column to XLSX export

### Frontend changes

- `frontend/src/types/index.ts` — Add `BANTSourceCitation` interface, add source arrays to `BANTScore`
- `frontend/src/pages/LeadsPage.tsx` — In the expandable BANT detail panel, render source citations as clickable links beneath each BANT dimension's reason text. Each link opens in a new tab and shows the source title + tool name

---

## Phase 6: Excel Import for ICP Configs (#1)

**Problem:** Creating ICPs one-by-one through the 9-step wizard is slow for users who already have ICP data in spreadsheets.

**Decision:** A single Excel file supports **multiple ICPs**. Each sheet uses an "ICP Name" column (column A) to group rows by ICP. The "Overview" sheet defines all ICP names/descriptions (one per row), and the data sheets use the same ICP Name to associate rows.

### Backend changes

**New file:** `backend/app/services/icp_import_service.py`

Two functions:
1. `generate_icp_template() -> BytesIO` — Creates an XLSX template with 8 sheets using openpyxl. Each sheet supports multiple ICPs via an "ICP Name" column (column A) that groups rows by ICP:
   - Sheet 1 "Overview": ICP Name (A), Description (B) — one row per ICP
   - Sheet 2 "Offerings": ICP Name (A), target_offering (B) — multiple rows per ICP
   - Sheet 3 "Regions": ICP Name (A), countries (B), priority_areas (C)
   - Sheet 4 "Industries": ICP Name (A), vertical (B), sub_vertical (C)
   - Sheet 5 "Company Size": ICP Name (A), employees_min (B), employees_max (C), revenue_min (D), revenue_max (E), revenue_currency (F) — one row per ICP
   - Sheet 6 "Technology": ICP Name (A), signals (B), negative_signals (C)
   - Sheet 7 "Drivers": ICP Name (A), growth_triggers (B), operational_pains (C), competitive_pressures (D), strategic_initiatives (E)
   - Sheet 8 "Leadership": ICP Name (A), target_roles (B), behavioral_traits (C)
   - Each sheet has headers in row 1 + example data for 2 sample ICPs in rows 2-5
   - Template styled with header formatting matching the export style

2. `parse_icp_excel(buffer: BytesIO) -> list[dict]` — Reads the uploaded XLSX, groups rows by ICP Name across all sheets, validates presence of required fields, returns a list of `{name, description, config: ICPDefinition, warnings: list[str]}` — one entry per ICP found

**Modified file:** `backend/app/api/icp.py`
- `GET /template/download` — Calls `generate_icp_template()`, returns as `StreamingResponse` with XLSX content type
- `POST /import/parse` — Accepts `UploadFile`, validates `.xlsx` extension, calls `parse_icp_excel()`, returns list of parsed ICP configs for frontend review. Uses existing `python-multipart` (already installed) and `openpyxl` (already installed)

The actual save reuses the existing `POST /icp` endpoint (called once per ICP) — no new save endpoint needed.

### Frontend changes

- `frontend/src/api/icpApi.ts` — Add `downloadICPTemplate()` (returns URL string) and `parseICPUpload(file: File)` (POST with FormData, returns list of parsed ICPs)
- `frontend/src/pages/ICPListPage.tsx` — Add "Import from Excel" button next to existing header buttons. On click, opens an Ant Design `Modal` with:
  1. **Step 1:** Download template link + `Upload.Dragger` for file upload
  2. **Step 2:** On successful parse, show a list/table of all parsed ICPs with expandable detail for each. Users can edit fields inline, remove individual ICPs, or add notes
  3. **Step 3:** "Save All" button iterates over each ICP and calls `createICP()` for each. Optional "Save & Run All" calls `createICP()` + `startPipeline()` for each
  - Warnings from parse are shown as Ant Design `Alert` banners per ICP
  - A summary count: "Found X ICPs in uploaded file"

---

## Phase 7: Clickable Dashboard Tiles (#5)

**Problem:** Dashboard metric tiles are display-only. Users want to click them and see details broken down by ICP.

### Backend changes

**New endpoint in** `backend/app/api/pipeline.py`:
- `GET /stats/by-icp` — Queries all completed `PipelineRun` rows with eagerly-loaded `icp_config`, groups by `icp_config_id`, returns per-ICP aggregates: `{icp_id, icp_name, run_count, total_companies, total_contacts, runs: [{id, status, companies_found, contacts_found, started_at, completed_at}]}`

### Frontend changes

- `frontend/src/api/pipelineApi.ts` — Add `getPipelineStatsByICP()` function and `ICPStat` type
- `frontend/src/pages/DashboardPage.tsx`:
  1. Add `cursor: pointer` + hover effect to `.metric-tile` elements
  2. On click, open an Ant Design `Modal` showing a `Table` of stats broken down by ICP
  3. Table columns: ICP Name, Runs, Companies, Contacts, Total Leads
  4. Expandable rows showing individual runs for each ICP, clickable to navigate to `/leads/{runId}`
  5. Filter the modal data based on which tile was clicked (e.g., "Companies Found" tile shows the companies column highlighted)
- `frontend/src/styles/theme.css` — Add hover styles for `.metric-tile` (box-shadow, border-color, translateY)

---

## Verification Plan

For each phase, verify by:

1. **#6 (Home Screen):** Load dashboard as new user (no runs) — see welcome banner + getting-started CTA. With runs, banner still visible but dismissible.
2. **#3 (ICP Linkage):** Run a pipeline, check dashboard cards show ICP name. Navigate to leads page, verify ICP name tag is visible. Check pipeline history list shows ICP names.
3. **#2 (Log Persistence):** Run a pipeline, let it complete. Refresh the page. Navigate to `/pipeline/{runId}` — activity log should reload from DB. Check `GET /pipeline/{runId}/logs` returns all events.
4. **#7 (Duration Communication):** Start a pipeline, verify duration estimate and "safe to leave" banner appear. Navigate away, return — verify logs load and completion notification shows.
5. **#4 (BANT Citations):** Run a pipeline, view leads. Expand a company row — BANT reasons should have clickable source links. Verify links open in new tabs.
6. **#1 (Excel Import):** Download template from ICP list page. Fill in data with multiple ICPs. Upload — verify preview shows all parsed ICPs correctly. Edit a field. Save All — verify all ICPs appear in list.
7. **#5 (Dashboard Tiles):** Click "Companies Found" tile — modal opens showing per-ICP breakdown. Click a run within the modal — navigates to leads page.

### Database migration
```bash
make migrate-create MSG="add_pipeline_logs_and_bant_sources"
make migrate
```
