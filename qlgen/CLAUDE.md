# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Project Is

qlGen is an ICP-driven qualified lead generation tool with an AI co-pilot. Users define an Ideal Customer Profile via a 9-step wizard, then a single AI agent (AWS Strands SDK + Claude Sonnet 4 via Bedrock) autonomously runs a 5-stage pipeline (Industry Discovery → Firmographic Fit → Budget/Urgency Signals → Contact Discovery → Final Scoring) using external API tools. Results are streamed to the frontend via SSE and stored in PostgreSQL. A conversational co-pilot agent provides context-aware data exploration and research recommendations. Authentication uses Google OAuth with JWT tokens.

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
make status               # Check if services are running (PostgreSQL, backend, frontend)
make logs                 # Tail backend + frontend logs (files in /tmp/qlgen-*.log)
make logs-backend         # Tail backend log only
make logs-frontend        # Tail frontend log only

# Docker (full stack alternative — entrypoint.sh auto-runs alembic upgrade head)
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

# Admin
make seed-admin EMAIL=user@example.com  # Create admin user
```

There is no test suite configured. The `backend/tests/` directory exists but is empty. No linter or formatter is configured for the backend.

**Dev process details:** Backend logs to `/tmp/qlgen-backend.log`, frontend to `/tmp/qlgen-frontend.log`. PIDs stored in `/tmp/qlgen-backend.pid` and `/tmp/qlgen-frontend.pid`. Makefile health-checks by polling `/api/v1/health` (backend) and port 3000 (frontend).

## Architecture

### Backend (`backend/app/`)

Async FastAPI application (Python 3.11+). All routes under `/api/v1`. Swagger UI at `/docs`.

- `main.py` — App creation, CORS middleware (origins from `settings.CORS_ALLOWED_ORIGINS`), router inclusion
- `config.py` — Pydantic Settings loading env vars from `.env`, `../.env`, and `backend/.env`

**API routes** (`api/`):
- `icp.py` — ICP CRUD + Excel import/export
- `pipeline.py` — Pipeline run + SSE stream (`GET /api/v1/pipeline/{run_id}/stream`) + history
- `leads.py` — Results + XLSX/CSV export
- `chat.py` — Co-pilot: SSE message streaming (`POST /api/v1/chat/send`), session management, context-aware recommendations, embedding backfill
- `auth.py` — Google OAuth login/logout + JWT token management
- `admin.py` — Admin-only endpoints (user management, tool control)
- `tools.py` — Tool management (availability, rate limits)
- `knowledge_base.py` — Knowledge base access
- `users.py` — User profile endpoints
- `health.py` — Health check
- `router.py` — Aggregates all sub-routers

**Models** (`models/`): SQLAlchemy async ORM. All use UUIDs. Config/raw data stored as JSONB.
- Core: `User`, `ICPConfig`, `PipelineRun`, `PipelineLog`, `Company` (includes 1024-dim pgvector embedding), `Contact`, `CompanyStageResult`
- Chat: `ChatSession`, `ChatMessage`
- Admin/Intelligence: `ToolRegistry`, `AuditLog`, `DiscoveryQuery`, `ToolEffectiveness`, `CompanyKnowledgeBase`
- Relationships: `PipelineRun` → `Company` → `Contact` + `CompanyStageResult`, all cascade delete. ICP deletion is soft (`is_active=False`).

**Services** (`services/`):
- `pipeline_service.py` — Core 5-stage orchestration: fetches ICP, creates Strands agent, runs in thread pool, parses JSON, saves to DB, emits SSE. Largest service file (~112 KB).
- `embedding_service.py` — AWS Bedrock Titan Embed Text v2 (1024-dim) for semantic company search
- `export_service.py` — Styled XLSX (openpyxl) and CSV exports
- `icp_import_service.py` — Excel template generation and multi-ICP parsing
- `tool_registry_service.py` — Tracks tool availability and rate limits
- `company_kb_service.py` — Knowledge base semantic search indexing
- `contact_dedup_service.py` — Contact deduplication
- `intelligence_service.py` — Discovery intelligence aggregation
- `validation_service.py` — Stage company/contact validation
- `event_store.py` — SSE event persistence for replay
- `audit_service.py` — Admin action logging

**Agents** (`agent/`):
- `lead_gen_agent.py` — Main pipeline agent with 5-stage system prompt. Callback handler emits SSE events (`stage_update`, `tool_start`, `agent_reasoning`, `completed`, `error`). ~51 KB.
- `copilot_agent.py` — Co-pilot agent with ~25 tools (6 DB tools + external research tools). Context-aware recommendations vary by page type.
- `prompt_builder.py` — Converts ICP config JSON into human-readable prompt (~40 KB)

**Tools** (`tools/`):
- Pipeline tools (Strands `@tool`): `apollo_tool`, `exa_tool`, `hunter_tool`, `lusha_tool`, `clay_tool`, `tavily_tool`, `duckduckgo_tool`, `web_scraper_tool`
- Co-pilot DB tools (`copilot_db_tools.py`, ~37 KB): `search_companies_semantic` (pgvector similarity), `search_companies_structured` (SQL filters), `get_company_details`, `get_icp_details`, `get_pipeline_summary`, `get_data_statistics`
- Research tools: `linkedin_search_tool`, `team_scraper_tool`, `google_places_tool`, `sec_tool`, `opencorporates_tool`, `market_data_tool`, `world_bank_tool`, `simfin_tool`, `fmp_tool`, `news_sentiment_tool`, `company_research_tool`, `find_executives_tool`, `icp_discovery_tool`, `yc_tool`, `github_tool`, `patent_tool`, `press_release_tool`, `producthunt_tool`, `govt_registry_tool`, `nordic_registry_tool`, `french_company_tool`, `job_search_tool`, `wikidata_tool`
- Utilities: `query_strategy.py`, `retry_utils.py`, `ddg_rate_limiter.py`

**Database** (`db/session.py`): Async SQLAlchemy engine (pool_size=10, max_overflow=20) + session factory using asyncpg. Provides `get_db()` dependency and `get_db_session()` context manager.

### Frontend (`frontend/src/`)

React 19 + TypeScript 5.9 + Vite 7 + Ant Design 6 + TailwindCSS 4.

- `App.tsx` — React Router (11 routes) + Ant Design ConfigProvider + Co-pilot panel
- `pages/` — `WelcomePage`, `DashboardPage`, `ICPListPage`, `ICPConfigPage` (9-step wizard), `PipelinePage` (SSE progress, ~108 KB), `LeadsPage` (results table + BANT + export, ~73 KB), `CompanyDetailPage` (~55 KB), `AllLeadsPage`, `ToolsPage`, `UserManagementPage`, `AuthCallbackPage`
- `components/` — `CoPilotPanel` (sliding chat panel), `CoPilotMessageBubble` (markdown rendering), `CoPilotRecommendations` (context-aware suggestions), `AppLayout` (sidebar nav), `ProtectedRoute` + `AdminRoute` (auth guards)
- `context/` — `PageContextProvider` derives page type from URL, extracts run_id/icp_id, passes context to co-pilot
- `api/` — `client.ts` (Axios with interceptors), `authApi.ts`, `icpApi.ts`, `pipelineApi.ts`, `leadsApi.ts`, `chatApi.ts`, `toolsApi.ts`, `usersApi.ts`
- `types/index.ts` — All TypeScript interfaces

Vite dev server proxies `/api` → `http://localhost:8000` (changeOrigin: true). Additional deps: recharts (charts), react-markdown + remark-gfm (markdown rendering in co-pilot).

### Infrastructure (`infra/`)

Terraform modules for AWS: VPC/networking, Secrets Manager, RDS PostgreSQL (pgvector), ECS Fargate (backend), CloudFront + S3 (frontend). See `terraform.tfvars.example` for required variables.

## Key Data Flow

**Lead Generation Pipeline:**
1. Frontend POSTs ICP config → `icp_configs` table
2. `POST /api/v1/pipeline/run` creates `PipelineRun`, starts `execute_pipeline` background task
3. Frontend connects to `GET /api/v1/pipeline/{run_id}/stream` for SSE
4. Strands agent runs in thread pool, calls tools across 5 stages, returns structured JSON
5. JSON parsed → `Company`, `Contact`, `CompanyStageResult` saved to DB; SSE events persisted to `pipeline_logs` for replay
6. `GET /api/v1/leads/{run_id}/companies` returns results; export endpoint generates XLSX/CSV

**Co-pilot Chat:**
1. Frontend sends message + page context via `POST /api/v1/chat/send`
2. Co-pilot agent runs with access to DB tools (semantic/structured search) and external research tools
3. Response streamed back as SSE events (`text_delta`, `tool_use`, `tool_result`)
4. Messages persisted in `ChatSession` / `ChatMessage` tables

**Authentication:**
1. Frontend redirects to Google OAuth → callback to `/auth/callback`
2. Backend validates Google token, creates/finds `User`, returns JWT access + refresh tokens
3. Frontend stores tokens, Axios interceptor attaches `Authorization: Bearer` header
4. `ProtectedRoute` / `AdminRoute` components guard frontend pages

## Database

PostgreSQL 16 with pgvector extension (Docker image: `pgvector/pgvector:pg16`). Schema managed by Alembic. Connection strings: `DATABASE_URL` (async, `postgresql+asyncpg://`) and `DATABASE_URL_SYNC` (Alembic, `postgresql://`). Default local credentials: user `qlgen`, password `qlgen_pass`, database `qlgen`.

## Environment Variables

Configured in `.env` at project root (copied to `backend/.env` by Makefile):
- `DATABASE_URL` / `DATABASE_URL_SYNC` — PostgreSQL connections (async/sync)
- `AWS_REGION`, `BEDROCK_MODEL_ID` — Bedrock config (model ID uses inference profile format, prefixed with `us.`)
- `BEDROCK_EMBEDDING_MODEL_ID` — Titan Embed Text v2 (default: `amazon.titan-embed-text-v2:0`)
- `APOLLO_API_KEY`, `EXA_API_KEY`, `HUNTER_API_KEY`, `LUSHA_API_KEY`, `TAVILY_API_KEY` — Core pipeline API keys
- `GOOGLE_PLACES_API_KEY`, `SIMFIN_API_KEY`, `FMP_API_KEY`, `NEWS_API_KEY` — Research tool API keys
- `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REDIRECT_URI` — Google OAuth
- `ALLOWED_EMAIL_DOMAIN` — Restrict sign-ups to a domain
- `JWT_SECRET_KEY`, `JWT_ACCESS_TOKEN_EXPIRE_MINUTES`, `JWT_REFRESH_TOKEN_EXPIRE_DAYS` — JWT auth config
- `REDIS_URL` — Redis connection for caching
- `VITE_API_BASE_URL` — Frontend API base URL (default `http://localhost:8000/api/v1`)
