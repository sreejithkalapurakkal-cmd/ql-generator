# qlGen Backend — Technical Documentation

## Table of Contents

1. [Overview](#1-overview)
2. [Architecture](#2-architecture)
3. [API Endpoints](#3-api-endpoints)
4. [Authentication & Authorization](#4-authentication--authorization)
5. [Database](#5-database)
6. [AWS Integration](#6-aws-integration)
7. [External APIs & Data Sources](#7-external-apis--data-sources)
8. [Environment & Configuration](#8-environment--configuration)
9. [Deployment](#9-deployment)

---

## 1. Overview

### What the Backend Does

The qlGen backend is the core orchestration layer of the lead generation platform. It is responsible for:

1. **Storing and managing ICP configurations** — persisting the user's Ideal Customer Profile definitions in a PostgreSQL database.
2. **Orchestrating AI-driven lead generation pipelines** — spawning a multi-tool AWS Bedrock AI agent that executes four sequential stages (Company Discovery → Contact Discovery → Enrichment → BANT Scoring).
3. **Streaming real-time progress** to the frontend via Server-Sent Events (SSE) as the agent works.
4. **Persisting structured results** — saving discovered companies, contacts, and BANT scores into normalized database tables.
5. **Exposing results for consumption** — serving the structured lead data with filtering and sorting, and generating downloadable XLSX and CSV exports.

### Framework

| Technology | Version | Role |
|---|---|---|
| FastAPI | 0.115.0 | Web framework (async, OpenAPI auto-docs) |
| Uvicorn | 0.30.6 | ASGI server |
| Python | 3.11 | Runtime |
| Pydantic / Pydantic Settings | 2.5.2 | Request/response validation, config management |

### Folder Structure

```
backend/
├── Dockerfile                          # Python 3.11-slim container image
├── entrypoint.sh                       # Container startup: run migrations → start server
├── requirements.txt                    # All Python dependencies
├── alembic.ini                         # Alembic migration configuration
├── alembic/
│   ├── env.py                          # Alembic runtime environment (uses sync DB URL)
│   ├── script.py.mako                  # Migration file template
│   └── versions/
│       └── ad6870bc307f_initial_schema_with_pgvector.py  # Single migration: full schema
└── app/
    ├── __init__.py
    ├── main.py                         # FastAPI app instantiation, CORS, router mounting
    ├── config.py                       # Pydantic Settings class; reads .env
    ├── api/                            # HTTP route handlers
    │   ├── __init__.py
    │   ├── router.py                   # Aggregates all sub-routers under /api/v1
    │   ├── health.py                   # GET /health
    │   ├── icp.py                      # ICP CRUD (5 endpoints)
    │   ├── pipeline.py                 # Pipeline orchestration (4 endpoints)
    │   └── leads.py                    # Leads retrieval + file export (2 endpoints)
    ├── models/                         # SQLAlchemy ORM table definitions
    │   ├── __init__.py
    │   ├── icp.py                      # ICPConfig model
    │   ├── company.py                  # Company model
    │   ├── contact.py                  # Contact model
    │   ├── bant.py                     # BANTScore model
    │   └── pipeline.py                 # PipelineRun model
    ├── schemas/                        # Pydantic request/response schemas
    │   ├── __init__.py
    │   ├── icp.py                      # ICP create/update/response schemas
    │   ├── company.py                  # Company/Contact/BANT response schemas
    │   └── pipeline.py                 # Pipeline request/response schemas
    ├── services/                       # Business logic (no direct HTTP concerns)
    │   ├── __init__.py
    │   ├── pipeline_service.py         # Full pipeline execution logic
    │   └── export_service.py           # XLSX and CSV file generation
    ├── db/                             # Database connection setup
    │   ├── __init__.py
    │   ├── base.py                     # SQLAlchemy DeclarativeBase
    │   └── session.py                  # Async engine + session factory + get_db dependency
    ├── agent/                          # AI agent definition
    │   ├── __init__.py
    │   ├── lead_gen_agent.py           # Strands Agent factory with system prompt + tools
    │   └── prompt_builder.py           # Dynamic prompt construction from ICP config
    └── tools/                          # Tool wrappers for the agent
        ├── __init__.py
        ├── apollo_tool.py              # Apollo.io company/people search
        ├── exa_tool.py                 # Exa semantic web search
        ├── hunter_tool.py              # Hunter.io domain search + email finder
        ├── lusha_tool.py               # Lusha phone/email lookup
        ├── tavily_tool.py              # Tavily news and web search
        ├── duckduckgo_tool.py          # DuckDuckGo free fallback search
        └── web_scraper_tool.py         # BeautifulSoup HTML scraper
```

---

## 2. Architecture

### Design Pattern

The backend follows a **layered architecture** with clear separation of concerns:

```
HTTP Request
     │
     ▼
┌─────────────┐
│  API Layer  │  app/api/*.py  — Route handlers, dependency injection, HTTP I/O
└──────┬──────┘
       │  calls
       ▼
┌─────────────────┐
│  Schema Layer   │  app/schemas/*.py  — Pydantic validation (in/out DTOs)
└──────┬──────────┘
       │  passes validated data to
       ▼
┌─────────────────┐
│  Service Layer  │  app/services/*.py  — Business logic, agent orchestration, export
└──────┬──────────┘
       │  reads/writes via
       ▼
┌─────────────────┐
│  Model Layer    │  app/models/*.py  — SQLAlchemy ORM entities
└──────┬──────────┘
       │
       ▼
┌─────────────────┐
│  Data Layer     │  app/db/session.py  — Async PostgreSQL sessions
└─────────────────┘
```

Separately, the **Agent subsystem** (`app/agent/` + `app/tools/`) is invoked by the service layer during pipeline execution and operates independently of the HTTP request/response cycle.

### Application Entry Point — `app/main.py`

```python
app = FastAPI(
    title="qlGen API",
    version="1.0.0",
    description="ICP-Driven Qualified Lead Generation Tool"
)
```

**CORS** is configured to allow the frontend origins:
- `http://localhost:3000`
- `http://localhost:5173`
- `http://127.0.0.1:3000`
- `http://127.0.0.1:5173`

All methods (`*`) and headers (`*`) are allowed, with credentials enabled.

The main API router is mounted at the `/api/v1` prefix:
```python
app.include_router(api_router, prefix="/api/v1")
```

A root endpoint at `GET /` returns a health/info message with a link to `/docs`.

### Async Design

The backend is **fully async** end-to-end:
- FastAPI handles requests asynchronously.
- All database operations use `asyncpg` through SQLAlchemy's async extension.
- External API calls in tools use `httpx` (async HTTP client).
- The pipeline is launched as a FastAPI `BackgroundTask` so the initial `POST /pipeline/run` returns immediately without blocking on agent execution.

### Background Task Pattern

When a pipeline is triggered:
1. `POST /pipeline/run` creates a `PipelineRun` DB record with `status = "pending"`.
2. It registers `execute_pipeline(run_id)` as a FastAPI `BackgroundTask`.
3. The response (with the new `run_id`) is returned immediately to the frontend.
4. The background task runs the agent independently, emitting SSE events and updating the DB.

### SSE (Server-Sent Events) Architecture

`GET /pipeline/{run_id}/stream` uses FastAPI's `StreamingResponse` with `media_type="text/event-stream"`. Events are accumulated in an in-memory list (`events` dict keyed by `run_id`) during background task execution. The SSE endpoint yields events as they appear using an async generator with polling every 0.5 seconds. This is a simple in-process pub/sub mechanism — suitable for single-process deployments but not horizontally scalable as-is.

---

## 3. API Endpoints

All endpoints are under the prefix `/api/v1`. Full OpenAPI documentation is auto-generated by FastAPI and available at `http://localhost:8000/docs` (Swagger UI) and `http://localhost:8000/redoc`.

### Health

| Method | Path | Purpose | Response |
|---|---|---|---|
| `GET` | `/api/v1/health` | Service liveness check | `{"status": "healthy", "service": "qlGen API"}` |

### ICP Configuration — `/api/v1/icp`

| Method | Path | Purpose | Request Body | Response |
|---|---|---|---|---|
| `POST` | `/icp` | Create a new ICP config | `ICPConfigCreate` | `ICPConfigResponse` (201) |
| `GET` | `/icp` | List all active ICPs (newest first) | — | `List[ICPConfigResponse]` |
| `GET` | `/icp/{id}` | Fetch single ICP by UUID | — | `ICPConfigResponse` (404 if not found) |
| `PUT` | `/icp/{id}` | Partially update an ICP | `ICPConfigUpdate` (all fields optional) | `ICPConfigResponse` |
| `DELETE` | `/icp/{id}` | Soft-delete (sets `is_active=False`) | — | `{"message": "ICP configuration deleted"}` |

**Request Body — `ICPConfigCreate`:**
```json
{
  "name": "string",
  "description": "optional string",
  "config": { /* ICPDefinition JSON object */ }
}
```

**Response — `ICPConfigResponse`:**
```json
{
  "id": "uuid",
  "name": "string",
  "description": "string | null",
  "config": { /* ICPDefinition */ },
  "created_at": "ISO 8601 datetime",
  "updated_at": "ISO 8601 datetime | null",
  "is_active": true
}
```

### Pipeline — `/api/v1/pipeline`

| Method | Path | Purpose | Request Body | Response |
|---|---|---|---|---|
| `POST` | `/pipeline/run` | Start a new pipeline run | `PipelineRunRequest` | `PipelineRunResponse` (202) |
| `GET` | `/pipeline/{run_id}` | Poll pipeline status | — | `PipelineRunResponse` |
| `GET` | `/pipeline/{run_id}/stream` | SSE stream of progress events | — | `text/event-stream` |
| `GET` | `/pipeline/history/list` | Last 50 pipeline runs | — | `List[PipelineRunResponse]` |

**Request Body — `PipelineRunRequest`:**
```json
{
  "icp_config_id": "uuid",
  "options": {
    "max_companies": 25,
    "max_contacts_per_company": 5
  }
}
```

**Response — `PipelineRunResponse`:**
```json
{
  "id": "uuid",
  "icp_config_id": "uuid",
  "status": "pending | running | completed | failed",
  "current_stage": "string | null",
  "companies_found": 0,
  "contacts_found": 0,
  "started_at": "ISO 8601 | null",
  "completed_at": "ISO 8601 | null",
  "error_log": "string | null"
}
```

**SSE Event Format:**

Each SSE event follows the standard `text/event-stream` format:
```
event: stage_update
data: {"stage": "Company Discovery", "message": "Found 12 companies via Apollo...", "timestamp": "..."}

event: completed
data: {"companies_found": 18, "contacts_found": 72, "run_id": "uuid"}

event: error
data: {"error": "Agent invocation failed: ...", "run_id": "uuid"}
```

### Leads & Export — `/api/v1/leads`

| Method | Path | Query Params | Purpose | Response |
|---|---|---|---|---|
| `GET` | `/leads/{run_id}/companies` | `min_bant_score`, `industry_filter`, `sort_by` | Fetch qualified lead companies with contacts + BANT | `List[CompanyResponse]` |
| `GET` | `/leads/{run_id}/export` | `format` (`xlsx` or `csv`) | Download leads as a file | Binary file attachment |

**Query Parameters for `/companies`:**
- `min_bant_score` (int, optional) — Only return companies with `total_score ≥` this value.
- `industry_filter` (str, optional) — Case-insensitive partial match on `company.industry`.
- `sort_by` (str, optional) — `"bant_score"` (default, descending) or `"company_name"` (ascending).

**`CompanyResponse`** includes nested `List[ContactResponse]` and optional `BANTScoreResponse`.

**Export response headers:**
- XLSX: `Content-Type: application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`
- CSV: `Content-Type: text/csv`
- Both include `Content-Disposition: attachment; filename="leads_{run_id}.xlsx|csv"`

---

## 4. Authentication & Authorization

**There is currently no authentication or authorization layer implemented.** All API endpoints are open and accept any request within the allowed CORS origins.

Key observations:
- No JWT validation middleware.
- No API key verification.
- No role-based access control.
- No session management.

This is a significant security gap for any externally accessible deployment. For production use, authentication (e.g., JWT via `python-jose`, OAuth2 via `fastapi-users`, or an API gateway with IAM) should be added.

---

## 5. Database

### Database System

| Property | Value |
|---|---|
| Engine | PostgreSQL 16 |
| Extension | `pgvector` (vector similarity search — installed but not actively used in current code) |
| ORM | SQLAlchemy 2.0 (async mode) |
| Driver | `asyncpg` (async) + `psycopg2-binary` (sync, for Alembic) |
| Migrations | Alembic |

### Connection

**Async connection** (for FastAPI request handlers and background tasks):
```
postgresql+asyncpg://qlgen:qlgen_pass@db:5432/qlgen
```

**Sync connection** (for Alembic migrations only):
```
postgresql://qlgen:qlgen_pass@db:5432/qlgen
```

The `db/session.py` module creates:
- An async engine (`create_async_engine`) with `echo=False`.
- An `async_sessionmaker` factory producing `AsyncSession` objects.
- A `get_db()` FastAPI dependency yielding a session per request (context-managed).
- A `get_db_session()` async context manager for use in background tasks (outside a request lifecycle).

### Schema — Tables

#### `icp_configs` — Ideal Customer Profile Definitions

| Column | Type | Notes |
|---|---|---|
| `id` | UUID | Primary key, auto-generated |
| `name` | VARCHAR(255) | Human-readable ICP name |
| `description` | TEXT | Optional description |
| `config_json` | JSONB | Full ICP definition object (nested structure) |
| `created_at` | TIMESTAMP | Auto-set to `now()` |
| `updated_at` | TIMESTAMP | Updated on modification |
| `is_active` | BOOLEAN | `true` by default; `false` for soft-deleted records |

The `config_json` stores the full ICP definition as a nested JSON object matching the `ICPDefinition` TypeScript interface, covering target offering, regions, industries, company size, technology maturity, infrastructure readiness, transformation drivers, and leadership traits.

#### `pipeline_runs` — Pipeline Execution Records

| Column | Type | Notes |
|---|---|---|
| `id` | UUID | Primary key |
| `icp_config_id` | UUID | Foreign key → `icp_configs.id` |
| `status` | VARCHAR(50) | `pending`, `running`, `completed`, `failed` |
| `current_stage` | VARCHAR(100) | Name of the stage currently executing |
| `companies_found` | INTEGER | Running count of discovered companies |
| `contacts_found` | INTEGER | Running count of discovered contacts |
| `started_at` | TIMESTAMP | When pipeline execution began |
| `completed_at` | TIMESTAMP | When pipeline finished (success or failure) |
| `error_log` | TEXT | Exception trace if status is `failed` |
| `stage_details` | JSONB | Reserved for per-stage metadata |
| `options` | JSONB | `PipelineOptions` used for this run (max_companies, max_contacts_per_company) |

#### `companies` — Qualified Lead Companies

| Column | Type | Notes |
|---|---|---|
| `id` | UUID | Primary key |
| `pipeline_run_id` | UUID | Foreign key → `pipeline_runs.id` (CASCADE DELETE) |
| `name` | VARCHAR(500) | Company name |
| `website` | VARCHAR(500) | Company website URL |
| `industry` | VARCHAR(255) | Primary industry |
| `sub_industry` | VARCHAR(255) | Sub-industry or vertical |
| `city` | VARCHAR(255) | City |
| `state_region` | VARCHAR(255) | State or region |
| `country` | VARCHAR(255) | Country |
| `employee_count` | INTEGER | Headcount |
| `revenue_estimate` | BIGINT | Annual revenue estimate (USD) |
| `tech_stack_json` | JSONB | Detected technology stack signals |
| `description` | TEXT | Company description |
| `source` | VARCHAR(100) | Data source: `apollo`, `exa`, `tavily`, `duckduckgo` |
| `source_id` | VARCHAR(500) | Identifier from the source API |
| `qualification` | VARCHAR(50) | Qualification label (e.g., `qualified`, `borderline`) |
| `rejection_reason` | TEXT | Why a company was disqualified (if applicable) |
| `icp_match_score` | FLOAT | 1–10 score of ICP alignment |
| `match_reasoning` | TEXT | Explanation of the match score |
| `raw_data_json` | JSONB | Raw response from the source API |
| `created_at` | TIMESTAMP | Auto-set to `now()` |

#### `contacts` — Decision-Maker Contacts

| Column | Type | Notes |
|---|---|---|
| `id` | UUID | Primary key |
| `company_id` | UUID | Foreign key → `companies.id` |
| `full_name` | VARCHAR(500) | Combined full name |
| `first_name` | VARCHAR(255) | First name |
| `last_name` | VARCHAR(255) | Last name |
| `designation` | VARCHAR(500) | Job title |
| `role_category` | VARCHAR(100) | Standardized role category (e.g., `CTO`, `VP Engineering`) |
| `email` | VARCHAR(500) | Work email address |
| `phone` | VARCHAR(100) | Phone number |
| `linkedin_url` | VARCHAR(500) | LinkedIn profile URL |
| `city` | VARCHAR(255) | City |
| `source` | VARCHAR(100) | Data source: `apollo`, `hunter`, `scraper`, etc. |
| `confidence` | FLOAT | Confidence score (0.0–1.0) for contact data accuracy |
| `enrichment_status` | VARCHAR(50) | `pending`, `partial`, `enriched`, or `failed` |
| `raw_data_json` | JSONB | Raw response from the source API |
| `created_at` | TIMESTAMP | Auto-set to `now()` |

#### `bant_scores` — BANT Qualification Scores

| Column | Type | Notes |
|---|---|---|
| `id` | UUID | Primary key |
| `company_id` | UUID | Foreign key → `companies.id` (one-to-one) |
| `contact_id` | UUID | Optional foreign key → `contacts.id` |
| `budget_score` | INTEGER | 1–5; budget capacity and tech spending signals |
| `budget_reason` | TEXT | Evidence-backed justification |
| `authority_score` | INTEGER | 1–5; seniority and decision-making power |
| `authority_reason` | TEXT | Evidence-backed justification |
| `need_score` | INTEGER | 1–5; pain/need alignment with ICP offering |
| `need_reason` | TEXT | Evidence-backed justification |
| `timing_score` | INTEGER | 1–5; readiness and urgency signals |
| `timing_reason` | TEXT | Evidence-backed justification |
| `total_score` | INTEGER | Sum of 4 scores; max 20 |
| `overall_summary` | TEXT | Narrative summary of the overall BANT assessment |
| `created_at` | TIMESTAMP | Auto-set to `now()` |

### Entity Relationships

```
icp_configs
    │
    └── pipeline_runs (many per ICP config)
            │
            └── companies (many per run, CASCADE DELETE)
                    │
                    ├── contacts (many per company)
                    │
                    └── bant_scores (one per company)
```

### Migrations

Alembic manages schema migrations. The `alembic/env.py` imports all models (`from app.models import *`) so Alembic can auto-detect changes. The single existing migration (`ad6870bc307f`) creates all five tables and runs `CREATE EXTENSION IF NOT EXISTS vector` for pgvector.

On container startup, `entrypoint.sh` runs `alembic upgrade head` before launching Uvicorn, ensuring the schema is always up-to-date.

---

## 6. AWS Integration

### AWS SDK

The backend uses **`boto3` 1.35.36** (AWS SDK for Python) exclusively for accessing **Amazon Bedrock** through the `strands-agents` framework. No other AWS services are directly integrated in the current codebase.

### Bedrock Configuration

AWS credentials are **not explicitly configured in code**. They are resolved by the standard AWS credential chain in this order:
1. Environment variables (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_SESSION_TOKEN`)
2. AWS credentials file (`~/.aws/credentials`)
3. IAM instance profile (if running on EC2/ECS)
4. AWS SSO / container credentials

The region and model ID are configured via `app/config.py`:

```python
AWS_REGION: str = "us-east-1"
BEDROCK_MODEL_ID: str = "anthropic.claude-sonnet-4-20250514"
```

> **Important:** The actual `.env` in use sets the model ID to `us.anthropic.claude-sonnet-4-20250514-v1:0` — an **inference profile ID** (cross-region inference). This is required for Claude Sonnet 4 models in Bedrock and differs from the default in `config.py`.

### AWS Services Used

| Service | Usage |
|---|---|
| **Amazon Bedrock** | Hosts and serves the Claude Sonnet 4 LLM used by the Strands agent for all four pipeline stages |

No other AWS services (S3, SQS, Lambda, Secrets Manager, DynamoDB, etc.) are used in the current codebase. All data is stored locally in the PostgreSQL container.

### IAM Requirements

The IAM identity (user or role) running the backend must have the following Bedrock permissions:

```json
{
  "Effect": "Allow",
  "Action": [
    "bedrock:InvokeModel",
    "bedrock:InvokeModelWithResponseStream"
  ],
  "Resource": "arn:aws:bedrock:us-east-1::foundation-model/anthropic.claude-sonnet-4-20250514"
}
```

If using a cross-region inference profile:
```json
{
  "Resource": "arn:aws:bedrock:us-east-1:<account-id>:inference-profile/us.anthropic.claude-sonnet-4-20250514-v1:0"
}
```

---

## 7. External APIs & Data Sources

The agent uses 7 external tools (5 paid APIs + 1 free search + 1 scraper). All API keys are loaded from environment variables.

### Apollo.io — `app/tools/apollo_tool.py`

| Property | Details |
|---|---|
| Purpose | Primary source for structured company and people data |
| API Base URL | `https://api.apollo.io/api/v1` |
| Auth | `api_key` header (from `APOLLO_API_KEY`) |
| Used In | Stage 1 (Company Discovery), Stage 2 (Contact Discovery) |

**`apollo_company_search` tool:**
- Endpoint: `POST /mixed_companies/search`
- Supports filters: keyword query, industries (list), locations (list), employee count range, pagination
- Returns: list of organizations with name, website, industry, headcount, revenue, location

**`apollo_people_search` tool:**
- Endpoint: `POST /mixed_people/search`
- Supports filters: company name, company domain, job titles (list), locations (list), pagination
- Returns: list of people with name, title, email, LinkedIn URL, phone

### Exa — `app/tools/exa_tool.py`

| Property | Details |
|---|---|
| Purpose | Neural/semantic web search for qualitative company data |
| API Base URL | `https://api.exa.ai` |
| Auth | `x-api-key` header (from `EXA_API_KEY`) |
| Used In | Stage 1 (Company Discovery), Stage 3 (Enrichment — LinkedIn URLs) |

**`exa_search` tool:**
- Endpoint: `POST /search`
- Supports: query, num_results, autoprompt, domain inclusion/exclusion filters, content type category
- Returns: search results with URL, title, text snippet, author, publish date

### Hunter.io — `app/tools/hunter_tool.py`

| Property | Details |
|---|---|
| Purpose | Email discovery by company domain and person name |
| API Base URL | `https://api.hunter.io/v2` |
| Auth | `api_key` query parameter (from `HUNTER_API_KEY`) |
| Used In | Stage 2 (Contact Discovery), Stage 3 (Enrichment) |

**`hunter_domain_search` tool:**
- Endpoint: `GET /domain-search`
- Input: domain name, result limit
- Returns: list of emails with confidence scores, names, roles, departments, LinkedIn

**`hunter_email_finder` tool:**
- Endpoint: `GET /email-finder`
- Input: domain, first name, last name
- Returns: predicted email with confidence score and source URLs

### Lusha — `app/tools/lusha_tool.py`

| Property | Details |
|---|---|
| Purpose | Phone number and email lookup for specific individuals |
| API Base URL | `https://api.lusha.com/person` |
| Auth | `api_key` header (from `LUSHA_API_KEY`) |
| Used In | Stage 3 (Enrichment — phone numbers) |

**`lusha_person_search` tool:**
- Input: first name, last name, optional company name and domain
- Returns: phone numbers, emails, social profiles

### Tavily — `app/tools/tavily_tool.py`

| Property | Details |
|---|---|
| Purpose | Recent news, funding rounds, and web search for BANT evidence |
| API Base URL | `https://api.tavily.com/search` |
| Auth | `api_key` in request body (from `TAVILY_API_KEY`) |
| Used In | Stage 1 (Company Discovery), Stage 4 (BANT Scoring) |

**`tavily_search` tool:**
- Input: query, max_results, search_depth (`"basic"` or `"advanced"`)
- Returns: list of results with title, URL, content, relevance score

### DuckDuckGo — `app/tools/duckduckgo_tool.py`

| Property | Details |
|---|---|
| Purpose | Free web search fallback when paid APIs are rate-limited |
| Library | `duckduckgo-search` 6.3.7 |
| Auth | None (no API key required) |
| Used In | Any stage as fallback |

**`duckduckgo_search` tool:**
- Input: query string, max_results
- Returns: list of results with title, href, body snippet

### Web Scraper — `app/tools/web_scraper_tool.py`

| Property | Details |
|---|---|
| Purpose | Extract text from company websites (team pages, about pages) |
| Library | `BeautifulSoup4` + `httpx` |
| Auth | None |
| Used In | Stage 2 (Contact Discovery), Stage 4 (BANT evidence) |

**`scrape_webpage` tool:**
- Input: URL string
- Process: HTTP GET → parse HTML with BeautifulSoup → extract visible text (strip scripts/styles) → truncate to 5000 characters
- Returns: `{url, title, content, links: [list of all href links]}`
- Error handling: Returns error dict on HTTP failure or parsing exception

### MCP Servers

**No MCP (Model Context Protocol) servers are used.** All tools are implemented as direct API calls using `httpx` and wrapped with the `@tool` decorator from the `strands-agents` library.

### Data Flow Summary

```
Apollo.io ──────────────────────┐
Exa ─────────────────────────── ├──→ Agent Tool Calls ──→ Parsed JSON ──→ PostgreSQL
Tavily ──────────────────────── │
DuckDuckGo (fallback) ──────────┘
                                     Stage 1 → companies[]

Apollo.io (people) ─────────────┐
Hunter.io (domain search) ────── ├──→ Agent Tool Calls ──→ contacts[] per company
Web Scraper (team pages) ───────┘
                                     Stage 2 → contacts[]

Hunter.io (email finder) ───────┐
Lusha (phone lookup) ─────────── ├──→ Agent Tool Calls ──→ enriched contacts
Exa (LinkedIn search) ──────────┘
                                     Stage 3 → enrichment_status updated

Tavily (news/signals) ──────────┐
Web Scraper (company pages) ──── ├──→ Agent reasoning ──→ BANT scores
                                 ┘
                                     Stage 4 → bant_scores[]
```

---

## 8. Environment & Configuration

### Configuration Module — `app/config.py`

Uses **Pydantic Settings** (`BaseSettings`) to load and validate environment variables. The `get_settings()` function is cached with `@lru_cache` so the `.env` file is read only once.

### Required Environment Variables

| Variable | Description | Default |
|---|---|---|
| `DATABASE_URL` | Async PostgreSQL connection string (asyncpg driver) | `postgresql+asyncpg://qlgen:qlgen_pass@localhost:5432/qlgen` |
| `DATABASE_URL_SYNC` | Sync PostgreSQL connection string (for Alembic) | `postgresql://qlgen:qlgen_pass@localhost:5432/qlgen` |
| `AWS_REGION` | AWS region for Bedrock | `us-east-1` |
| `BEDROCK_MODEL_ID` | Bedrock model/inference profile ID | `anthropic.claude-sonnet-4-20250514` |
| `APOLLO_API_KEY` | Apollo.io API key | `""` (required for production) |
| `EXA_API_KEY` | Exa API key | `""` (required for production) |
| `HUNTER_API_KEY` | Hunter.io API key | `""` (required for production) |
| `LUSHA_API_KEY` | Lusha API key | `""` (required for production) |
| `TAVILY_API_KEY` | Tavily API key | `""` (required for production) |

**AWS credential variables** (not in Pydantic Settings; resolved by boto3/SDK automatically):

| Variable | Description |
|---|---|
| `AWS_ACCESS_KEY_ID` | AWS access key (if not using IAM role or SSO) |
| `AWS_SECRET_ACCESS_KEY` | AWS secret key |
| `AWS_SESSION_TOKEN` | Session token (if using temporary credentials / SSO) |

### `.env` File

The `.env` file is placed at the project root (sibling to `docker-compose.yml`) and loaded by Docker Compose via `env_file: ../.env`. For local development, it is placed in `backend/` and loaded by `pydantic-settings` via the `Config.env_file = ".env"` setting.

> **Note:** The `.env` file is listed in `.gitignore` and is never committed. A `.env.example` file does not currently exist in the repository. This is a gap for onboarding new developers.

---

## 9. Deployment

### Docker Compose (Primary Deployment Method)

The application is deployed as a 3-service Docker Compose stack defined in `docker-compose.yml`:

```
┌─────────────────────────────────────────────────┐
│                 docker-compose.yml               │
│                                                  │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐ │
│  │    db      │  │  backend   │  │  frontend  │ │
│  │ PostgreSQL │  │  FastAPI   │  │  React/    │ │
│  │    16+     │  │  Uvicorn   │  │  Vite      │ │
│  │  :5432     │  │  :8000     │  │  :3000     │ │
│  │  pgvector  │  │            │  │            │ │
│  └────────────┘  └────────────┘  └────────────┘ │
│        pgdata (persistent volume)                │
└─────────────────────────────────────────────────┘
```

**Database service (`db`):**
- Image: `pgvector/pgvector:pg16`
- Port: `5432:5432`
- Volume: `pgdata` for data persistence
- Health check: `pg_isready -U qlgen -d qlgen` every 5s, 5 retries

**Backend service (`backend`):**
- Build: `./backend/Dockerfile` (Python 3.11-slim)
- Port: `8000:8000`
- Depends on: `db` (health condition)
- Env file: `../.env` (root-level `.env`)
- Startup: Runs `entrypoint.sh` → `alembic upgrade head` → `uvicorn app.main:app --reload`

**Frontend service (`frontend`):**
- Build: `./frontend/Dockerfile` (Node.js)
- Port: `3000:3000`
- Environment: `VITE_BACKEND_PROXY_URL=http://backend:8000`
- Depends on: `backend`

### Backend Dockerfile

```dockerfile
FROM python:3.11-slim
WORKDIR /app
RUN apt-get update && apt-get install -y gcc libpq-dev && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
EXPOSE 8000
ENTRYPOINT ["/entrypoint.sh"]
```

`gcc` and `libpq-dev` are required to compile `psycopg2-binary` from source in the slim base image.

### Running Locally (Without Docker)

```bash
# Start PostgreSQL separately (or use Docker for just the DB)
# Set environment variables in backend/.env

cd backend
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

### CI/CD

**No CI/CD pipeline is currently configured.** There is no `.github/workflows/`, `Jenkinsfile`, or other CI configuration in the repository. Deployments are currently manual via `docker compose up --build`.

### Production Considerations (Current Gaps)

| Gap | Impact | Recommendation |
|---|---|---|
| No auth/authorization | All endpoints are open | Add JWT or API gateway authentication |
| Uvicorn `--reload` in production | Performance overhead | Remove `--reload` flag in prod entrypoint |
| SSE events stored in-memory | Not scalable horizontally | Use Redis pub/sub for multi-process SSE |
| No CI/CD | Manual deployments only | Add GitHub Actions pipeline |
| No `.env.example` | Difficult onboarding | Create template `.env.example` |
| No tests | No regression safety | Add pytest test suite |
| pgvector installed but unused | Unused dependency | Implement vector search or remove |
