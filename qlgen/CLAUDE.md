# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Project Is

qlGen is an ICP-driven qualified lead generation tool. Users define an Ideal Customer Profile via a 9-step wizard, then a single AI agent (AWS Strands SDK + Claude Sonnet 4 via Bedrock) autonomously runs a 4-stage pipeline (Company Discovery → Contact Discovery → Contact Enrichment → BANT Scoring) using 9 external API tools. Results are streamed to the frontend via SSE and stored in PostgreSQL.

## Common Commands

```bash
# Full setup
make install              # Install backend venv + frontend node_modules
make db-start             # Start PostgreSQL via Docker Compose
make migrate              # Run Alembic migrations

# Development
make dev                  # Start both backend (port 8000) and frontend (port 3000)
make dev-backend          # Backend only (uvicorn with --reload)
make dev-frontend         # Frontend only (Vite dev server)
make stop                 # Stop both services
make status               # Check if services are running
make logs                 # Tail backend + frontend logs

# Database
make migrate-create MSG="description"   # Create new Alembic migration
cd backend && backend/venv/bin/alembic upgrade head   # Apply migrations directly

# Frontend
cd frontend && npm run dev              # Vite dev server
cd frontend && npm run build            # Production build
cd frontend && npx tsc --noEmit         # Type check only
```

There is no test suite configured. The `backend/tests/` directory exists but is empty. No linter or formatter is configured for the backend.

## Architecture

**Backend** (`backend/app/`): Async FastAPI application. All routes are under `/api/v1`.

- `main.py` — App creation, CORS middleware, router inclusion
- `config.py` — Pydantic Settings loading env vars from `.env`
- `api/` — Route handlers: `icp.py` (CRUD), `pipeline.py` (run + SSE stream), `leads.py` (results + export), `health.py`
- `api/router.py` — Aggregates all sub-routers into one
- `models/` — SQLAlchemy async ORM: `ICPConfig`, `PipelineRun`, `Company`, `Contact`, `BANTScore`. All use UUIDs. Config/raw data stored as JSONB.
- `schemas/` — Pydantic request/response models
- `services/pipeline_service.py` — Core orchestration: fetches ICP, creates agent, runs it in a thread pool, parses JSON output, saves companies/contacts/BANT to DB, emits SSE events
- `services/export_service.py` — Generates styled XLSX (openpyxl) and CSV exports
- `agent/lead_gen_agent.py` — Creates the Strands agent with system prompt defining 4 stages. Includes callback handler that emits SSE events (`stage_update`, `tool_start`, `agent_reasoning`, `completed`, `error`)
- `agent/prompt_builder.py` — Converts ICP config JSON into a human-readable prompt with all 8 ICP dimensions
- `tools/` — 9 tools decorated with Strands `@tool`: `apollo_tool.py` (company + people search), `exa_tool.py`, `hunter_tool.py` (domain + email), `lusha_tool.py`, `tavily_tool.py`, `duckduckgo_tool.py`, `web_scraper_tool.py`
- `db/session.py` — Async SQLAlchemy engine + session factory using asyncpg

**Frontend** (`frontend/src/`): React 19 + TypeScript + Vite + Ant Design + TailwindCSS.

- `App.tsx` — React Router routes and layout
- `pages/` — `DashboardPage`, `ICPListPage`, `ICPConfigPage` (9-step wizard), `PipelinePage` (SSE progress), `LeadsPage` (results + export)
- `api/client.ts` — Axios instance using `VITE_API_BASE_URL` env var
- `api/` — `icpApi.ts`, `pipelineApi.ts`, `leadsApi.ts`

**Infrastructure** (`infra/`): Terraform modules for AWS deployment — VPC/networking, Secrets Manager, RDS PostgreSQL, ECS Fargate (backend), CloudFront + S3 (frontend).

## Key Data Flow

1. Frontend POSTs ICP config → saved to `icp_configs` table
2. `POST /api/v1/pipeline/run` creates a `PipelineRun` record and starts `execute_pipeline` as a background task
3. Frontend connects to `GET /api/v1/pipeline/{run_id}/stream` for SSE
4. `PipelineService` creates a Strands agent, runs it in a thread pool executor. The agent calls tools across 4 stages and returns structured JSON.
5. JSON is parsed → `Company`, `Contact`, `BANTScore` records saved to DB
6. Callback handler pushes SSE events to the frontend throughout execution
7. `GET /api/v1/leads/{run_id}/companies` returns results; export endpoint generates XLSX/CSV

## Database

PostgreSQL 16 with pgvector extension. Schema managed by Alembic (single migration so far). Relationships: `PipelineRun` → `Company` → `Contact` + `BANTScore`, all with cascade delete. ICP deletion is soft (`is_active=False`).

Connection strings configured via `DATABASE_URL` (async, uses `postgresql+asyncpg://`) and `DATABASE_URL_SYNC` (for Alembic, uses `postgresql://`).

## Environment Variables

Configured in `.env` at project root (copied to `backend/.env` by Makefile). Key variables:
- `DATABASE_URL` / `DATABASE_URL_SYNC` — PostgreSQL connection
- `AWS_REGION`, `BEDROCK_MODEL_ID` — AWS Bedrock config (model ID must use inference profile format, prefixed with `us.`)
- `APOLLO_API_KEY`, `EXA_API_KEY`, `HUNTER_API_KEY`, `LUSHA_API_KEY`, `TAVILY_API_KEY` — External API keys
- `VITE_API_BASE_URL` — Frontend API base URL (default `http://localhost:8000/api/v1`)
