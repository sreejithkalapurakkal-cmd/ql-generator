# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Project Is

qlGen is an ICP-driven qualified lead generation tool with an AI co-pilot. Users define an Ideal Customer Profile via a 9-step wizard, then a single AI agent (AWS Strands SDK + Claude Sonnet 4 via Bedrock) autonomously runs a 4-stage pipeline (Company Discovery → Contact Discovery → Contact Enrichment → BANT Scoring) using external API tools. Results are streamed to the frontend via SSE and stored in PostgreSQL. A conversational co-pilot agent provides context-aware data exploration and research recommendations.

## Common Commands

```bash
# Full setup
make install              # Install backend venv + frontend node_modules
make db-start             # Start PostgreSQL via Docker Compose (waits with pg_isready)
make migrate              # Run Alembic migrations

# Development
make dev                  # Start both backend (port 8000) and frontend (port 3000)
make dev-backend          # Backend only (uvicorn with --reload)
make dev-frontend         # Frontend only (Vite dev server)
make stop                 # Stop both services
make status               # Check if services are running
make logs                 # Tail backend + frontend logs (files in /tmp/qlgen-*.log)

# Docker (full stack alternative)
docker compose up -d      # Start all services (db + backend + frontend)

# Database
make migrate-create MSG="description"   # Create new Alembic migration (autogenerate)
make migrate                            # Apply pending migrations
cd backend && ../backend/venv/bin/alembic upgrade head  # Apply migrations directly

# Frontend
cd frontend && npm run dev              # Vite dev server
cd frontend && npm run build            # Production build (runs tsc -b first)
cd frontend && npx tsc --noEmit         # Type check only
cd frontend && npm run lint             # ESLint 9 (TypeScript + React hooks + React refresh)
```

There is no test suite configured. The `backend/tests/` directory exists but is empty. No linter or formatter is configured for the backend.

## Architecture

### Backend (`backend/app/`)

Async FastAPI application (Python 3.11+). All routes under `/api/v1`. Swagger UI at `/docs`.

- `main.py` — App creation, CORS middleware (localhost:3000, 5173), router inclusion
- `config.py` — Pydantic Settings loading env vars from `.env`

**API routes** (`api/`):
- `icp.py` — ICP CRUD + Excel import/export
- `pipeline.py` — Pipeline run + SSE stream (`GET /api/v1/pipeline/{run_id}/stream`)
- `leads.py` — Results + XLSX/CSV export
- `chat.py` — Co-pilot: SSE message streaming (`POST /api/v1/chat/send`), session management, context-aware recommendations, embedding backfill
- `health.py` — Health check
- `router.py` — Aggregates all sub-routers

**Models** (`models/`): SQLAlchemy async ORM. All use UUIDs. Config/raw data stored as JSONB.
- `ICPConfig`, `PipelineRun`, `PipelineLog`, `Company` (includes 1024-dim pgvector embedding), `Contact`, `BANTScore`, `ChatSession`, `ChatMessage`
- Relationships: `PipelineRun` → `Company` → `Contact` + `BANTScore`, all cascade delete. ICP deletion is soft (`is_active=False`).

**Services** (`services/`):
- `pipeline_service.py` — Core orchestration: fetches ICP, creates Strands agent, runs in thread pool, parses JSON, saves to DB, emits SSE
- `embedding_service.py` — Generates embeddings via AWS Bedrock Titan Embed Text v2 (1024-dim) for semantic company search
- `export_service.py` — Styled XLSX (openpyxl) and CSV exports
- `icp_import_service.py` — Excel template generation and multi-ICP parsing

**Agents** (`agent/`):
- `lead_gen_agent.py` — Main pipeline agent with 4-stage system prompt. Callback handler emits SSE events (`stage_update`, `tool_start`, `agent_reasoning`, `completed`, `error`). Largest backend file.
- `copilot_agent.py` — Co-pilot agent with ~25 tools (6 DB tools + external research tools). Context-aware recommendations vary by page (LeadsPage, DashboardPage, ICPConfigPage, etc.).
- `prompt_builder.py` — Converts ICP config JSON into human-readable prompt

**Tools** (`tools/`):
- Pipeline tools (Strands `@tool`): `apollo_tool`, `exa_tool`, `hunter_tool`, `lusha_tool`, `tavily_tool`, `duckduckgo_tool`, `web_scraper_tool`
- Co-pilot DB tools (`copilot_db_tools.py`): `search_companies_semantic` (pgvector similarity), `search_companies_structured` (SQL filters), `get_company_details`, `get_icp_details`, `get_pipeline_summary`, `get_data_statistics`
- Research tools: `linkedin_search_tool`, `team_scraper_tool`, `google_places_tool`, `sec_tool`, `opencorporates_tool`, `market_data_tool`, `world_bank_tool`, `simfin_tool`, `fmp_tool`, `news_sentiment_tool`, `company_research_tool`, `find_executives_tool`, `icp_discovery_tool`, `yc_tool`

**Database** (`db/session.py`): Async SQLAlchemy engine + session factory using asyncpg.

### Frontend (`frontend/src/`)

React 19 + TypeScript + Vite + Ant Design 6 + TailwindCSS 4.

- `App.tsx` — React Router (7 routes) + Ant Design ConfigProvider
- `pages/` — `WelcomePage`, `DashboardPage`, `ICPListPage`, `ICPConfigPage` (9-step wizard), `PipelinePage` (SSE progress), `LeadsPage` (results table + BANT + export)
- `components/` — `CoPilotPanel` (sliding chat panel), `CoPilotMessageBubble` (markdown rendering), `CoPilotRecommendations` (context-aware suggestions), `AppLayout` (sidebar nav)
- `context/` — `PageContextProvider` derives page type from URL, extracts run_id/icp_id, passes context to co-pilot
- `api/` — `client.ts` (Axios), `icpApi.ts`, `pipelineApi.ts`, `leadsApi.ts`, `chatApi.ts`
- `types/index.ts` — All TypeScript interfaces

Vite dev server proxies `/api` → `http://localhost:8000`. Additional deps: recharts (charts), react-markdown + remark-gfm (markdown rendering in co-pilot).

### Infrastructure (`infra/`)

Terraform modules for AWS: VPC/networking, Secrets Manager, RDS PostgreSQL (pgvector), ECS Fargate (backend), CloudFront + S3 (frontend). See `terraform.tfvars.example` for required variables.

## Key Data Flow

**Lead Generation Pipeline:**
1. Frontend POSTs ICP config → `icp_configs` table
2. `POST /api/v1/pipeline/run` creates `PipelineRun`, starts `execute_pipeline` background task
3. Frontend connects to `GET /api/v1/pipeline/{run_id}/stream` for SSE
4. Strands agent runs in thread pool, calls tools across 4 stages, returns structured JSON
5. JSON parsed → `Company`, `Contact`, `BANTScore` saved to DB; SSE events persisted to `pipeline_logs` for replay
6. `GET /api/v1/leads/{run_id}/companies` returns results; export endpoint generates XLSX/CSV

**Co-pilot Chat:**
1. Frontend sends message + page context via `POST /api/v1/chat/send`
2. Co-pilot agent runs with access to DB tools (semantic/structured search) and external research tools
3. Response streamed back as SSE events (`text_delta`, `tool_use`, `tool_result`)
4. Messages persisted in `ChatSession` / `ChatMessage` tables

## Database

PostgreSQL 16 with pgvector extension (Docker image: `pgvector/pgvector:pg16`). Schema managed by Alembic (3 migrations). Connection strings: `DATABASE_URL` (async, `postgresql+asyncpg://`) and `DATABASE_URL_SYNC` (Alembic, `postgresql://`).

## Environment Variables

Configured in `.env` at project root (copied to `backend/.env` by Makefile):
- `DATABASE_URL` / `DATABASE_URL_SYNC` — PostgreSQL connections
- `AWS_REGION`, `BEDROCK_MODEL_ID` — Bedrock config (model ID uses inference profile format, prefixed with `us.`)
- `BEDROCK_EMBEDDING_MODEL_ID` — Titan Embed Text v2 (default: `amazon.titan-embed-text-v2:0`)
- `APOLLO_API_KEY`, `EXA_API_KEY`, `HUNTER_API_KEY`, `LUSHA_API_KEY`, `TAVILY_API_KEY` — Core pipeline API keys
- `GOOGLE_PLACES_API_KEY`, `SIMFIN_API_KEY`, `FMP_API_KEY`, `NEWS_API_KEY` — Research tool API keys
- `VITE_API_BASE_URL` — Frontend API base URL (default `http://localhost:8000/api/v1`)
