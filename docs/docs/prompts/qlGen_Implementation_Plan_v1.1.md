# qlGen — Implementation Plan

## ICP-Driven Qualified Lead Generation Tool

**Version:** 1.1 (Single-Agent Architecture)  
**Date:** February 25, 2026  
**Target:** 8-Hour Hackathon Build → AWS Production Deployment

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Technology Stack](#2-technology-stack)
3. [Repository Structure](#3-repository-structure)
4. [Phase 0 — Environment & Project Bootstrap](#4-phase-0--environment--project-bootstrap)
5. [Phase 1 — Database Layer](#5-phase-1--database-layer)
6. [Phase 2 — Backend API (FastAPI)](#6-phase-2--backend-api-fastapi)
7. [Phase 3 — Agentic Layer (AWS Strands)](#7-phase-3--agentic-layer-aws-strands)
8. [Phase 4 — Frontend (React)](#8-phase-4--frontend-react)
9. [Phase 5 — Integration & End-to-End Testing](#9-phase-5--integration--end-to-end-testing)
10. [Phase 6 — AWS Deployment](#10-phase-6--aws-deployment)
11. [API External Tool Reference](#11-api-external-tool-reference)
12. [Data Models](#12-data-models)
13. [BANT Scoring Algorithm](#13-bant-scoring-algorithm)
14. [Risk & Mitigation](#14-risk--mitigation)
15. [Scaling to Multi-Agent (Future)](#15-scaling-to-multi-agent-future)

---

## 1. Architecture Overview

### Design Decision: Single Agent

This implementation uses a **single Strands agent** with all tools registered, rather than multiple specialized agents. Rationale:

- The four pipeline stages (Company Discovery → Contact Discovery → Enrichment → BANT Scoring) are **sequential and dependent** — each stage feeds into the next. There is no parallelism to exploit.
- The total tool count (9 tools) is well within a single agent's capacity. LLMs handle 10-15 tools comfortably without confusion.
- A single agent maintains **full context** across all stages — it can reference company data discovered in Stage 1 when scoring in Stage 4, producing better-informed BANT reasoning.
- The orchestrator code is dramatically simpler — one agent invocation per pipeline run instead of four separate agent lifecycles with intermediate serialization.
- For the hackathon scope (15–25 companies), context window limits are not a concern.

### High-Level Architecture Diagram

```
┌──────────────────────────────────────────────────────────────────────┐
│                        FRONTEND (React)                              │
│  ┌──────────┐ ┌──────────────┐ ┌────────────┐ ┌──────────────────┐  │
│  │   ICP    │ │  Pipeline    │ │  Results   │ │   Export /       │  │
│  │  Config  │ │  Dashboard   │ │  Explorer  │ │   Download       │  │
│  │  Wizard  │ │  & Status    │ │  & Scoring │ │   (XLSX/CSV)     │  │
│  └────┬─────┘ └──────┬───────┘ └─────┬──────┘ └───────┬──────────┘  │
│       │               │               │                │             │
└───────┼───────────────┼───────────────┼────────────────┼─────────────┘
        │               │               │                │
        ▼               ▼               ▼                ▼
┌──────────────────────────────────────────────────────────────────────┐
│                     BACKEND (FastAPI)                                 │
│  ┌──────────┐ ┌──────────────┐ ┌────────────┐ ┌──────────────────┐  │
│  │ ICP API  │ │  Pipeline    │ │  Leads     │ │   Export         │  │
│  │ CRUD     │ │  Orchestrator│ │  API       │ │   Service        │  │
│  └────┬─────┘ └──────┬───────┘ └─────┬──────┘ └───────┬──────────┘  │
│       │               │               │                │             │
│       │         ┌─────▼──────────────────────────────┐ │             │
│       │         │  SINGLE STRANDS AGENT              │ │             │
│       │         │  (Lead Generation Specialist)       │ │             │
│       │         │                                    │ │             │
│       │         │  System Prompt defines 4 stages:   │ │             │
│       │         │  ┌────────────────────────────────┐│ │             │
│       │         │  │ Stage 1: Company Discovery     ││ │             │
│       │         │  │ Stage 2: Contact Discovery     ││ │             │
│       │         │  │ Stage 3: Contact Enrichment    ││ │             │
│       │         │  │ Stage 4: BANT Scoring          ││ │             │
│       │         │  └────────────────────────────────┘│ │             │
│       │         │                                    │ │             │
│       │         │  9 Tools:                          │ │             │
│       │         │  apollo_company_search  exa_search │ │             │
│       │         │  apollo_people_search   tavily     │ │             │
│       │         │  hunter_domain_search   lusha      │ │             │
│       │         │  hunter_email_finder    ddg_search │ │             │
│       │         │  scrape_webpage                    │ │             │
│       │         └─────────────────┬──────────────────┘ │             │
│       │                           │                    │             │
└───────┼───────────────────────────┼────────────────────┼─────────────┘
        │                           │                    │
        ▼                           ▼                    ▼
┌──────────────────────────────────────────────────────────────────────┐
│                   DATA LAYER                                         │
│  ┌────────────────────┐  ┌────────────────────────────────────────┐  │
│  │    PostgreSQL       │  │         pgvector Extension             │  │
│  │  • icp_configs      │  │  • company_embeddings                 │  │
│  │  • companies        │  │  • Used for semantic ICP matching     │  │
│  │  • contacts         │  │    and deduplication                  │  │
│  │  • bant_scores      │  │                                      │  │
│  │  • pipeline_runs    │  │                                      │  │
│  └────────────────────┘  └────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────┘
        │                           │
        ▼                           ▼
┌──────────────────────────────────────────────────────────────────────┐
│               EXTERNAL SERVICES & TOOLS                              │
│  ┌─────────┐ ┌─────────┐ ┌───────┐ ┌────────┐ ┌────────┐          │
│  │Apollo.io│ │  Exa    │ │Hunter │ │ Tavily │ │  Lusha │          │
│  └─────────┘ └─────────┘ └───────┘ └────────┘ └────────┘          │
│  ┌─────────┐ ┌───────────┐ ┌──────────────────────────┐            │
│  │  Clay   │ │DuckDuckGo │ │  AWS Bedrock (LLM)       │            │
│  └─────────┘ └───────────┘ └──────────────────────────┘            │
└──────────────────────────────────────────────────────────────────────┘
```

### Data Flow

```
User defines ICP (UI)
        │
        ▼
ICP saved to PostgreSQL via FastAPI
        │
        ▼
Pipeline Orchestrator constructs prompt from ICP → invokes Single Agent
        │
        ▼
┌──────────────────────────────────────────────────────┐
│  SINGLE AGENT EXECUTION (multi-step tool use)        │
│                                                      │
│  The agent autonomously follows its system prompt:   │
│                                                      │
│  Step 1: Analyze ICP, formulate search strategies    │
│     ↓    Calls: apollo_company_search, exa_search,   │
│          tavily_search, duckduckgo_search             │
│     ↓    Qualifies & deduplicates companies          │
│                                                      │
│  Step 2: For each company, find decision-makers      │
│     ↓    Calls: apollo_people_search,                │
│          hunter_domain_search, scrape_webpage         │
│     ↓    Maps contacts to target roles               │
│                                                      │
│  Step 3: Enrich missing contact data                 │
│     ↓    Calls: hunter_email_finder,                 │
│          lusha_person_search, exa_search              │
│     ↓    Fills email, phone, LinkedIn                │
│                                                      │
│  Step 4: Score each company+contacts using BANT      │
│     ↓    Calls: tavily_search, scrape_webpage        │
│          (for additional signals if needed)           │
│     ↓    Produces scored, explained output            │
│                                                      │
│  Returns: Complete JSON with companies, contacts,    │
│           enrichment data, and BANT scores            │
└──────────────────────────────────────────────────────┘
        │
        ▼
Orchestrator parses JSON → saves to PostgreSQL
        │
        ▼
Results available via API → Rendered in UI → Exportable as XLSX/CSV
```

---

## 2. Technology Stack

| Layer | Technology | Version / Notes |
|-------|-----------|-----------------|
| **Frontend** | React 18 + Vite | TypeScript, TailwindCSS, Ant Design (AntD) for professional UI components |
| **Backend** | Python FastAPI | 0.110+, async-first, Pydantic v2 models |
| **Database** | PostgreSQL 16 | Primary relational store |
| **Vector DB** | pgvector (PG extension) | Semantic ICP matching & dedup |
| **Agentic Framework** | AWS Strands Agents SDK | Python SDK, single-agent with tool-use pattern |
| **LLM** | AWS Bedrock | `anthropic.claude-sonnet-4-20250514` — single model for all reasoning |
| **ORM** | SQLAlchemy 2.0 + Alembic | Async support, migrations |
| **Export** | openpyxl | XLSX generation |
| **Local Dev** | Docker Compose | PG + pgvector, backend, frontend |
| **AWS Deploy** | ECS Fargate, RDS, ALB, S3 | Production infrastructure |

---

## 3. Repository Structure

```
qlgen/
├── README.md
├── docker-compose.yml              # Local dev: PG + pgvector + backend + frontend
├── docker-compose.prod.yml         # Production overrides
├── .env.example                    # Environment variable template
│
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── alembic/                    # Database migrations
│   │   ├── alembic.ini
│   │   ├── env.py
│   │   └── versions/
│   │
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                 # FastAPI application entry point
│   │   ├── config.py               # Settings (Pydantic BaseSettings)
│   │   │
│   │   ├── api/                    # API route definitions
│   │   │   ├── __init__.py
│   │   │   ├── router.py           # Master router
│   │   │   ├── icp.py              # ICP CRUD endpoints
│   │   │   ├── pipeline.py         # Pipeline trigger & status endpoints
│   │   │   ├── leads.py            # Lead results & export endpoints
│   │   │   └── health.py           # Health check
│   │   │
│   │   ├── models/                 # SQLAlchemy ORM models
│   │   │   ├── __init__.py
│   │   │   ├── icp.py              # ICPConfig model
│   │   │   ├── company.py          # Company model
│   │   │   ├── contact.py          # Contact model
│   │   │   ├── bant.py             # BANTScore model
│   │   │   └── pipeline.py         # PipelineRun model
│   │   │
│   │   ├── schemas/                # Pydantic request/response schemas
│   │   │   ├── __init__.py
│   │   │   ├── icp.py
│   │   │   ├── company.py
│   │   │   ├── contact.py
│   │   │   ├── bant.py
│   │   │   ├── pipeline.py
│   │   │   └── export.py
│   │   │
│   │   ├── services/               # Business logic
│   │   │   ├── __init__.py
│   │   │   ├── icp_service.py
│   │   │   ├── pipeline_service.py # Orchestrates the single-agent pipeline
│   │   │   └── export_service.py   # XLSX/CSV generation
│   │   │
│   │   ├── agent/                  # Single AWS Strands agent
│   │   │   ├── __init__.py
│   │   │   ├── lead_gen_agent.py   # Agent definition + system prompt
│   │   │   └── prompt_builder.py   # Builds user prompt from ICP config
│   │   │
│   │   ├── tools/                  # Strands tool definitions (API wrappers)
│   │   │   ├── __init__.py
│   │   │   ├── apollo_tool.py      # apollo_company_search + apollo_people_search
│   │   │   ├── exa_tool.py         # exa_search
│   │   │   ├── hunter_tool.py      # hunter_domain_search + hunter_email_finder
│   │   │   ├── lusha_tool.py       # lusha_person_search
│   │   │   ├── clay_tool.py        # clay_search (if needed)
│   │   │   ├── tavily_tool.py      # tavily_search
│   │   │   ├── duckduckgo_tool.py  # duckduckgo_search (free fallback)
│   │   │   └── web_scraper_tool.py # scrape_webpage (BeautifulSoup)
│   │   │
│   │   └── db/                     # Database utilities
│   │       ├── __init__.py
│   │       ├── session.py          # Async session factory
│   │       └── base.py             # Declarative base
│   │
│   └── tests/
│       ├── __init__.py
│       ├── test_icp_api.py
│       ├── test_pipeline.py
│       └── test_tools.py           # Individual tool unit tests
│
├── frontend/
│   ├── Dockerfile
│   ├── package.json
│   ├── vite.config.ts
│   ├── tsconfig.json
│   ├── tailwind.config.js
│   ├── index.html
│   │
│   ├── public/
│   │   └── qlgen-logo.svg
│   │
│   └── src/
│       ├── main.tsx
│       ├── App.tsx
│       ├── api/                    # API client (axios)
│       │   ├── client.ts
│       │   ├── icpApi.ts
│       │   ├── pipelineApi.ts
│       │   └── leadsApi.ts
│       │
│       ├── components/
│       │   ├── layout/
│       │   │   ├── AppLayout.tsx    # Sidebar + header + content
│       │   │   ├── Sidebar.tsx
│       │   │   └── Header.tsx
│       │   │
│       │   ├── icp/
│       │   │   ├── ICPWizard.tsx            # Multi-step ICP form
│       │   │   ├── ICPStepOffering.tsx      # Step 1: Target Offering
│       │   │   ├── ICPStepRegions.tsx       # Step 2: Regions
│       │   │   ├── ICPStepIndustry.tsx      # Step 3: Industry & Verticals
│       │   │   ├── ICPStepCompanySize.tsx   # Step 4: Size parameters
│       │   │   ├── ICPStepTechMaturity.tsx  # Step 5: Technology signals
│       │   │   ├── ICPStepInfra.tsx         # Step 6: Infrastructure
│       │   │   ├── ICPStepDrivers.tsx       # Step 7: Transformation drivers
│       │   │   ├── ICPStepLeadership.tsx    # Step 8: Leadership traits
│       │   │   ├── ICPSummary.tsx           # Review before submit
│       │   │   └── ICPListPage.tsx          # Saved ICP configurations
│       │   │
│       │   ├── pipeline/
│       │   │   ├── PipelineDashboard.tsx    # Run status & progress
│       │   │   ├── PipelineStageCard.tsx    # Individual stage status
│       │   │   └── PipelineHistory.tsx      # Past runs
│       │   │
│       │   ├── leads/
│       │   │   ├── LeadResultsTable.tsx     # Master results table
│       │   │   ├── CompanyCard.tsx          # Expandable company detail
│       │   │   ├── ContactRow.tsx           # Contact detail row
│       │   │   ├── BANTScoreDisplay.tsx     # Visual BANT score breakdown
│       │   │   └── ExportControls.tsx       # Download XLSX/CSV
│       │   │
│       │   └── common/
│       │       ├── LoadingSpinner.tsx
│       │       ├── EmptyState.tsx
│       │       └── StatusBadge.tsx
│       │
│       ├── pages/
│       │   ├── DashboardPage.tsx
│       │   ├── ICPConfigPage.tsx
│       │   ├── PipelinePage.tsx
│       │   └── LeadsPage.tsx
│       │
│       ├── hooks/
│       │   ├── useICP.ts
│       │   ├── usePipeline.ts
│       │   └── useLeads.ts
│       │
│       ├── types/
│       │   └── index.ts              # TypeScript interfaces matching backend schemas
│       │
│       └── utils/
│           ├── constants.ts
│           └── formatters.ts
│
└── infra/                            # AWS deployment (IaC)
    ├── cloudformation/
    │   ├── vpc.yml
    │   ├── rds.yml
    │   ├── ecs.yml
    │   ├── alb.yml
    │   └── s3.yml
    └── scripts/
        ├── deploy.sh
        └── seed-db.sh
```

**Key structural change from v1.0:** The `agents/` directory is now `agent/` (singular) with just two files: the agent definition and the prompt builder. The four separate agent files (`company_discovery.py`, `contact_discovery.py`, `enrichment.py`, `bant_scoring.py`) are eliminated. The `scoring_service.py` is also removed since BANT scoring logic lives entirely in the agent's system prompt.

---

## 4. Phase 0 — Environment & Project Bootstrap

**Duration:** ~30 minutes

### Step 0.1 — Prerequisites

Ensure the development machine has the following installed:

- Python 3.11+
- Node.js 20 LTS + npm
- Docker & Docker Compose
- AWS CLI configured (`aws configure` with Bedrock access)
- Git

### Step 0.2 — Initialize Repository

```bash
mkdir qlgen && cd qlgen
git init
```

### Step 0.3 — Create `.env.example`

```env
# Database
DATABASE_URL=postgresql+asyncpg://qlgen:qlgen_pass@localhost:5432/qlgen
DATABASE_URL_SYNC=postgresql://qlgen:qlgen_pass@localhost:5432/qlgen

# AWS Bedrock
AWS_REGION=us-east-1
BEDROCK_MODEL_ID=anthropic.claude-sonnet-4-20250514

# External APIs
APOLLO_API_KEY=i9CO8Qi178IVdr8tjhLzQg
APOLLO_BASE_URL=https://api.apollo.io/v1

EXA_API_KEY=985db767-02c0-4f65-9bc5-380e0c836a70
EXA_BASE_URL=https://api.exa.ai

HUNTER_API_KEY=8b9783830d55228365bfb645f9ea77848502f27f
HUNTER_BASE_URL=https://api.hunter.io/v2

LUSHA_API_KEY=b2c47f59-0b7d-40d4-98e3-1988a01982a8
LUSHA_BASE_URL=https://api.lusha.com

CLAY_API_KEY=55bd2296e2bc09c3ed68
CLAY_BASE_URL=https://api.clay.com

TAVILY_API_KEY=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
TAVILY_BASE_URL=https://api.tavily.com

# Frontend
VITE_API_BASE_URL=http://localhost:8000/api/v1
```

### Step 0.4 — Docker Compose (Local Dev)

```yaml
# docker-compose.yml
version: "3.9"
services:
  db:
    image: pgvector/pgvector:pg16
    environment:
      POSTGRES_USER: qlgen
      POSTGRES_PASSWORD: qlgen_pass
      POSTGRES_DB: qlgen
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data

  backend:
    build: ./backend
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
    ports:
      - "8000:8000"
    env_file: .env
    depends_on:
      - db
    volumes:
      - ./backend:/app
      - ~/.aws:/root/.aws:ro    # Mount AWS credentials for local Bedrock access

  frontend:
    build: ./frontend
    command: npm run dev -- --host 0.0.0.0 --port 3000
    ports:
      - "3000:3000"
    environment:
      - VITE_API_BASE_URL=http://localhost:8000/api/v1
    volumes:
      - ./frontend:/app
      - /app/node_modules

volumes:
  pgdata:
```

### Step 0.5 — Backend Project Init

```bash
cd backend
python -m venv venv && source venv/bin/activate
pip install fastapi uvicorn[standard] sqlalchemy[asyncio] asyncpg \
    alembic pydantic-settings httpx openpyxl pgvector \
    strands-agents strands-agents-tools boto3 \
    beautifulsoup4 python-multipart duckduckgo-search
pip freeze > requirements.txt
```

### Step 0.6 — Frontend Project Init

```bash
cd frontend
npm create vite@latest . -- --template react-ts
npm install antd @ant-design/icons tailwindcss @tailwindcss/vite \
    axios react-router-dom@6 recharts
```

---

## 5. Phase 1 — Database Layer

**Duration:** ~45 minutes

### Step 1.1 — Enable pgvector

In an Alembic migration or init SQL:

```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

### Step 1.2 — Define SQLAlchemy Models

#### `models/icp.py` — ICP Configuration

```python
class ICPConfig(Base):
    __tablename__ = "icp_configs"

    id            = Column(UUID, primary_key=True, default=uuid4)
    name          = Column(String(255), nullable=False)           # User-given name
    description   = Column(Text, nullable=True)
    config_json   = Column(JSONB, nullable=False)                 # Full ICP as structured JSON
    created_at    = Column(DateTime, server_default=func.now())
    updated_at    = Column(DateTime, onupdate=func.now())
    is_active     = Column(Boolean, default=True)

    # Relationships
    pipeline_runs = relationship("PipelineRun", back_populates="icp_config")
```

The `config_json` field stores the entire ICP definition as a flexible JSONB document with this schema:

```json
{
  "target_offering": ["Platform engineering", "Custom storefront dev"],
  "regions": {
    "countries": ["United States"],
    "priority_areas": ["California", "New York", "Texas"]
  },
  "industry_types": [
    {"vertical": "Fashion & Apparel", "sub_vertical": null},
    {"vertical": "Consumer Electronics", "sub_vertical": "Gadgets"}
  ],
  "company_size": {
    "employees_min": 50,
    "employees_max": 1500,
    "revenue_min": 10000000,
    "revenue_max": 500000000,
    "revenue_currency": "USD"
  },
  "technology_maturity": {
    "signals": ["Running on Shopify Plus", "Evaluating headless commerce"],
    "negative_signals": ["Legacy Magento 1 migration overdue"]
  },
  "infrastructure_readiness": {
    "indicators": ["Cloud-hosted storefront", "API-first platform"]
  },
  "digital_transformation_drivers": {
    "growth_triggers": ["YoY revenue growth >20%"],
    "operational_pains": ["Site performance degrading during peak traffic"],
    "competitive_pressures": ["Rising CAC"],
    "strategic_initiatives": ["Launching mobile app or PWA"]
  },
  "leadership_traits": {
    "target_roles": ["CEO", "CTO", "VP of Engineering", "VP of ECommerce"],
    "behavioral_traits": ["Data-driven decision maker", "Active on LinkedIn"]
  }
}
```

#### `models/company.py` — Discovered Companies

```python
class Company(Base):
    __tablename__ = "companies"

    id              = Column(UUID, primary_key=True, default=uuid4)
    pipeline_run_id = Column(UUID, ForeignKey("pipeline_runs.id"))
    name            = Column(String(500), nullable=False)
    website         = Column(String(500))
    industry        = Column(String(255))
    sub_industry    = Column(String(255))
    city            = Column(String(255))
    state_region    = Column(String(255))
    country         = Column(String(255))
    employee_count  = Column(Integer)
    revenue_estimate= Column(BigInteger)                          # In cents/smallest unit
    tech_stack_json = Column(JSONB)                               # Detected technologies
    description     = Column(Text)
    source          = Column(String(100))                         # Which API found it
    source_id       = Column(String(500))                         # External ID
    qualification   = Column(String(50), default="pending")       # pending | qualified | rejected
    rejection_reason= Column(Text)
    embedding       = Column(Vector(1536))                        # pgvector for semantic match
    raw_data_json   = Column(JSONB)                               # Full raw response for audit
    created_at      = Column(DateTime, server_default=func.now())

    # Relationships
    contacts       = relationship("Contact", back_populates="company")
    bant_score     = relationship("BANTScore", back_populates="company", uselist=False)
    pipeline_run   = relationship("PipelineRun", back_populates="companies")
```

#### `models/contact.py` — Discovered Contacts

```python
class Contact(Base):
    __tablename__ = "contacts"

    id              = Column(UUID, primary_key=True, default=uuid4)
    company_id      = Column(UUID, ForeignKey("companies.id"))
    full_name       = Column(String(500))
    first_name      = Column(String(255))
    last_name       = Column(String(255))
    designation     = Column(String(500))
    role_category   = Column(String(100))                         # Normalized: CTO, VP Eng, etc.
    email           = Column(String(500))
    phone           = Column(String(100))
    linkedin_url    = Column(String(500))
    city            = Column(String(255))
    source          = Column(String(100))
    confidence      = Column(Float)                               # Data confidence 0.0–1.0
    enrichment_status = Column(String(50), default="pending")     # pending | enriched | partial | failed
    raw_data_json   = Column(JSONB)
    created_at      = Column(DateTime, server_default=func.now())

    # Relationships
    company        = relationship("Company", back_populates="contacts")
    bant_score     = relationship("BANTScore", back_populates="contact", uselist=False)
```

#### `models/bant.py` — BANT Scores

```python
class BANTScore(Base):
    __tablename__ = "bant_scores"

    id              = Column(UUID, primary_key=True, default=uuid4)
    company_id      = Column(UUID, ForeignKey("companies.id"), nullable=True)
    contact_id      = Column(UUID, ForeignKey("contacts.id"), nullable=True)
    budget_score    = Column(Integer)                              # 1–5
    budget_reason   = Column(Text)
    authority_score = Column(Integer)                              # 1–5
    authority_reason= Column(Text)
    need_score      = Column(Integer)                              # 1–5
    need_reason     = Column(Text)
    timing_score    = Column(Integer)                              # 1–5
    timing_reason   = Column(Text)
    total_score     = Column(Integer)                              # Composite 4–20
    overall_summary = Column(Text)                                 # LLM-generated explanation
    created_at      = Column(DateTime, server_default=func.now())

    # Relationships
    company        = relationship("Company", back_populates="bant_score")
    contact        = relationship("Contact", back_populates="bant_score")
```

#### `models/pipeline.py` — Pipeline Run Tracking

```python
class PipelineRun(Base):
    __tablename__ = "pipeline_runs"

    id              = Column(UUID, primary_key=True, default=uuid4)
    icp_config_id   = Column(UUID, ForeignKey("icp_configs.id"))
    status          = Column(String(50), default="pending")       # pending | running | completed | failed
    current_stage   = Column(String(100))                         # company_discovery | contact_discovery | enrichment | scoring | completed
    companies_found = Column(Integer, default=0)
    contacts_found  = Column(Integer, default=0)
    started_at      = Column(DateTime)
    completed_at    = Column(DateTime)
    error_log       = Column(Text)
    stage_details   = Column(JSONB)                               # Per-stage progress/stats

    # Relationships
    icp_config     = relationship("ICPConfig", back_populates="pipeline_runs")
    companies      = relationship("Company", back_populates="pipeline_run")
```

### Step 1.3 — Alembic Setup & Initial Migration

```bash
cd backend
alembic init alembic
# Edit alembic/env.py to use async engine and import all models
alembic revision --autogenerate -m "Initial schema with pgvector"
alembic upgrade head
```

### Step 1.4 — Database Session Factory

```python
# app/db/session.py
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

engine = create_async_engine(settings.DATABASE_URL, echo=False)
async_session = async_sessionmaker(engine, expire_on_commit=False)

async def get_db():
    async with async_session() as session:
        yield session
```

---

## 6. Phase 2 — Backend API (FastAPI)

**Duration:** ~1.5 hours

### Step 2.1 — FastAPI Application Setup

```python
# app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="qlGen API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "https://qlgen.yourdomain.com"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api/v1")
```

### Step 2.2 — API Endpoints

#### ICP Configuration Endpoints (`/api/v1/icp`)

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/icp` | Create a new ICP configuration |
| `GET` | `/icp` | List all saved ICP configurations |
| `GET` | `/icp/{id}` | Get a specific ICP configuration |
| `PUT` | `/icp/{id}` | Update an ICP configuration |
| `DELETE` | `/icp/{id}` | Soft-delete an ICP configuration |

**Request body for POST/PUT (`ICPCreateRequest`):**

```json
{
  "name": "MidMarket US ECommerce 2026",
  "description": "Targeting midsize US ecommerce companies...",
  "config": {
    "target_offering": [...],
    "regions": {...},
    "industry_types": [...],
    "company_size": {...},
    "technology_maturity": {...},
    "infrastructure_readiness": {...},
    "digital_transformation_drivers": {...},
    "leadership_traits": {...}
  }
}
```

#### Pipeline Endpoints (`/api/v1/pipeline`)

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/pipeline/run` | Start a new pipeline run for a given ICP config ID |
| `GET` | `/pipeline/{run_id}` | Get pipeline run status & progress |
| `GET` | `/pipeline/{run_id}/stream` | SSE endpoint for real-time progress updates |
| `GET` | `/pipeline/history` | List past pipeline runs |
| `POST` | `/pipeline/{run_id}/cancel` | Cancel a running pipeline |

**Request body for POST run:**

```json
{
  "icp_config_id": "uuid-here",
  "options": {
    "max_companies": 25,
    "max_contacts_per_company": 5
  }
}
```

**SSE stream response format:**

```
event: stage_update
data: {"stage": "company_discovery", "progress": 45, "message": "Found 12 companies matching ICP..."}

event: stage_update
data: {"stage": "contact_discovery", "progress": 70, "message": "Discovered 3 contacts for Acme Corp..."}

event: completed
data: {"companies_found": 25, "contacts_found": 87, "avg_bant_score": 14.2}
```

#### Leads Endpoints (`/api/v1/leads`)

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/leads/{run_id}` | Get all leads for a pipeline run (paginated) |
| `GET` | `/leads/{run_id}/companies` | Get qualified companies with nested contacts |
| `GET` | `/leads/{run_id}/export` | Download as XLSX |
| `GET` | `/leads/{run_id}/export?format=csv` | Download as CSV |

**Query params for leads:** `page`, `per_page`, `sort_by` (bant_score, company_name), `min_bant_score`, `industry_filter`

### Step 2.3 — Export Service Implementation

```python
# app/services/export_service.py
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border

async def generate_xlsx(run_id: UUID, db: AsyncSession) -> BytesIO:
    """Generate sales-ready XLSX matching the spec output format."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Qualified Leads"

    # Headers per spec
    headers = [
        "Serial#", "Company Name", "Website", "Geo/City",
        "Contact Name", "Designation", "LinkedIn", "Email",
        "Phone", "BANT Score"
    ]

    # Style headers
    header_fill = PatternFill(start_color="1F4E79", fill_type="solid")
    header_font = Font(color="FFFFFF", bold=True, size=11)

    for col, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=header)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center")

    # Populate data rows (grouped by company, multiple contacts per company)
    row_num = 2
    serial = 1
    companies = await fetch_companies_with_contacts(run_id, db)

    for company in companies:
        for contact in company.contacts:
            ws.cell(row=row_num, column=1, value=serial)
            ws.cell(row=row_num, column=2, value=company.name)
            ws.cell(row=row_num, column=3, value=company.website)
            ws.cell(row=row_num, column=4, value=f"{company.city}")
            ws.cell(row=row_num, column=5, value=contact.full_name)
            ws.cell(row=row_num, column=6, value=contact.designation)
            ws.cell(row=row_num, column=7, value=contact.linkedin_url)
            ws.cell(row=row_num, column=8, value=contact.email)
            ws.cell(row=row_num, column=9, value=contact.phone)
            ws.cell(row=row_num, column=10, value=contact.bant_score.total_score if contact.bant_score else "N/A")
            serial += 1
            row_num += 1

    # Auto-fit columns, add filters, freeze header row
    # ...

    buffer = BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return buffer
```

### Step 2.4 — Background Task Runner

Pipeline runs must be async and non-blocking. Use FastAPI `BackgroundTasks` for hackathon, or a task queue for production.

```python
# app/api/pipeline.py
from fastapi import BackgroundTasks

@router.post("/pipeline/run")
async def start_pipeline(
    request: PipelineRunRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    run = await create_pipeline_run(request.icp_config_id, db)
    background_tasks.add_task(execute_pipeline, run.id)
    return {"run_id": run.id, "status": "started"}
```

---

## 7. Phase 3 — Agentic Layer (AWS Strands)

**Duration:** ~2.5 hours (this is the core of the system)

### Step 3.0 — AWS Strands Framework Overview

AWS Strands Agents SDK uses a **tool-use pattern** where you define:
1. An **Agent** with a system prompt and a model (Bedrock)
2. **Tools** the agent can invoke (Python functions decorated with `@tool`)
3. The agent reasons about which tools to call, processes results, and continues until the task is complete

```python
from strands import Agent
from strands.models.bedrock import BedrockModel

model = BedrockModel(
    model_id="anthropic.claude-sonnet-4-20250514",
    region_name="us-east-1"
)

agent = Agent(
    model=model,
    system_prompt="You are a lead generation specialist...",
    tools=[apollo_company_search, apollo_people_search, exa_search, ...]
)

result = agent("Find and qualify 20 ecommerce companies matching this ICP: ...")
```

### Step 3.1 — Tool Definitions

Each external API is wrapped as a Strands tool. All 9 tools are registered with the single agent. Tool docstrings are critical — they tell the LLM when and how to use each tool.

#### Tool: Apollo Company Search (`tools/apollo_tool.py`)

```python
from strands.types.tools import tool
import httpx

@tool
def apollo_company_search(
    query: str,
    industries: list[str] = None,
    locations: list[str] = None,
    min_employees: int = None,
    max_employees: int = None,
    min_revenue: int = None,
    max_revenue: int = None,
    page: int = 1,
    per_page: int = 25
) -> dict:
    """
    Search for companies using Apollo.io API.
    BEST FOR: Structured company database search with filters for industry,
    location, employee count, and revenue range.
    USE IN STAGE: Company Discovery (Stage 1)

    Args:
        query: Search query describing the type of company (e.g., "ecommerce fashion")
        industries: List of industry verticals to filter by
        locations: List of locations (cities, states, countries)
        min_employees: Minimum number of employees
        max_employees: Maximum number of employees
        min_revenue: Minimum annual revenue in USD
        max_revenue: Maximum annual revenue in USD
        page: Page number for pagination
        per_page: Results per page (max 25)

    Returns:
        dict with 'companies' list and 'pagination' info
    """
    url = f"{APOLLO_BASE_URL}/mixed_companies/search"
    headers = {"Content-Type": "application/json", "Cache-Control": "no-cache"}
    payload = {
        "api_key": APOLLO_API_KEY,
        "q_organization_keyword_tags": query,
        "organization_industry_tag_ids": industries,
        "organization_locations": locations,
        "organization_num_employees_ranges": [f"{min_employees},{max_employees}"] if min_employees else None,
        "page": page,
        "per_page": per_page
    }
    payload = {k: v for k, v in payload.items() if v is not None}

    response = httpx.post(url, json=payload, timeout=30)
    response.raise_for_status()
    return response.json()
```

#### Tool: Apollo People Search (`tools/apollo_tool.py`)

```python
@tool
def apollo_people_search(
    company_name: str = None,
    company_domain: str = None,
    titles: list[str] = None,
    locations: list[str] = None,
    page: int = 1,
    per_page: int = 10
) -> dict:
    """
    Search for people/contacts at specific companies using Apollo.io.
    BEST FOR: Finding decision-makers by title at known companies.
    USE IN STAGE: Contact Discovery (Stage 2)

    Args:
        company_name: Name of the company to search within
        company_domain: Domain of the company (e.g., "acme.com")
        titles: List of job titles to filter by (e.g., ["CTO", "VP Engineering"])
        locations: List of locations to filter
        page: Page number
        per_page: Results per page

    Returns:
        dict with 'people' list containing name, title, email, linkedin, phone
    """
    url = f"{APOLLO_BASE_URL}/mixed_people/search"
    headers = {"Content-Type": "application/json"}
    payload = {
        "api_key": APOLLO_API_KEY,
        "q_organization_name": company_name,
        "organization_domains": [company_domain] if company_domain else None,
        "person_titles": titles,
        "person_locations": locations,
        "page": page,
        "per_page": per_page
    }
    payload = {k: v for k, v in payload.items() if v is not None}

    response = httpx.post(url, json=payload, timeout=30)
    response.raise_for_status()
    return response.json()
```

#### Tool: Exa Search (`tools/exa_tool.py`)

```python
@tool
def exa_search(
    query: str,
    num_results: int = 10,
    use_autoprompt: bool = True,
    include_domains: list[str] = None,
    exclude_domains: list[str] = None,
    start_published_date: str = None,
    category: str = None
) -> dict:
    """
    Neural/semantic web search using Exa API.
    BEST FOR: Finding companies by qualitative descriptions — tech stack,
    business model, growth signals. Also good for finding LinkedIn profiles.
    USE IN STAGES: Company Discovery (Stage 1), Enrichment (Stage 3)

    Args:
        query: Natural language search query (e.g., "midsize ecommerce companies
               using Shopify Plus in California")
        num_results: Number of results to return (max 50)
        use_autoprompt: Let Exa optimize the query
        include_domains: Only search these domains
        exclude_domains: Exclude these domains
        start_published_date: Filter by date (ISO format)
        category: Filter category (company, research_paper, news, etc.)

    Returns:
        dict with 'results' list containing url, title, text, author, published_date
    """
    url = f"{EXA_BASE_URL}/search"
    headers = {
        "x-api-key": EXA_API_KEY,
        "Content-Type": "application/json"
    }
    payload = {
        "query": query,
        "numResults": num_results,
        "useAutoprompt": use_autoprompt,
        "includeDomains": include_domains,
        "excludeDomains": exclude_domains,
        "startPublishedDate": start_published_date,
        "category": category,
        "contents": {"text": {"maxCharacters": 2000}}
    }
    payload = {k: v for k, v in payload.items() if v is not None}

    response = httpx.post(url, json=payload, headers=headers, timeout=30)
    response.raise_for_status()
    return response.json()
```

#### Tool: Hunter Email Finder (`tools/hunter_tool.py`)

```python
@tool
def hunter_domain_search(domain: str, limit: int = 10) -> dict:
    """
    Find email addresses associated with a company domain using Hunter.io.
    BEST FOR: Discovering contacts at a company when you know the domain.
    USE IN STAGE: Contact Discovery (Stage 2)

    Args:
        domain: Company domain (e.g., "acme.com")
        limit: Max number of results

    Returns:
        dict with 'emails' list containing value, type, confidence, first_name,
        last_name, position, department, linkedin
    """
    url = f"{HUNTER_BASE_URL}/domain-search"
    params = {"domain": domain, "api_key": HUNTER_API_KEY, "limit": limit}
    response = httpx.get(url, params=params, timeout=30)
    response.raise_for_status()
    return response.json()


@tool
def hunter_email_finder(domain: str, first_name: str, last_name: str) -> dict:
    """
    Find a specific person's email address at a company using Hunter.io.
    BEST FOR: Getting email for a known person when you have their name + company domain.
    USE IN STAGE: Enrichment (Stage 3)

    Args:
        domain: Company domain
        first_name: Person's first name
        last_name: Person's last name

    Returns:
        dict with email, confidence score, and sources
    """
    url = f"{HUNTER_BASE_URL}/email-finder"
    params = {
        "domain": domain,
        "first_name": first_name,
        "last_name": last_name,
        "api_key": HUNTER_API_KEY
    }
    response = httpx.get(url, params=params, timeout=30)
    response.raise_for_status()
    return response.json()
```

#### Tool: Tavily Web Search (`tools/tavily_tool.py`)

```python
@tool
def tavily_search(query: str, max_results: int = 5, search_depth: str = "advanced") -> dict:
    """
    Web search using Tavily API.
    BEST FOR: Finding recent news, funding rounds, company announcements,
    technology adoption signals, and job postings.
    USE IN STAGES: Company Discovery (Stage 1), BANT Scoring (Stage 4)

    Args:
        query: Search query
        max_results: Maximum number of results
        search_depth: 'basic' or 'advanced' (advanced = more detailed)

    Returns:
        dict with 'results' list containing title, url, content, score
    """
    url = f"{TAVILY_BASE_URL}/search"
    payload = {
        "api_key": TAVILY_API_KEY,
        "query": query,
        "max_results": max_results,
        "search_depth": search_depth,
        "include_raw_content": False
    }
    response = httpx.post(url, json=payload, timeout=30)
    response.raise_for_status()
    return response.json()
```

#### Tool: Lusha Contact Lookup (`tools/lusha_tool.py`)

```python
@tool
def lusha_person_search(
    first_name: str,
    last_name: str,
    company_name: str = None,
    company_domain: str = None
) -> dict:
    """
    Look up phone numbers and email for a specific person using Lusha.
    BEST FOR: Getting phone numbers when you already have name + company.
    USE IN STAGE: Enrichment (Stage 3)

    Args:
        first_name: Person's first name
        last_name: Person's last name
        company_name: Company name for disambiguation
        company_domain: Company website domain

    Returns:
        dict with phone numbers, email addresses, and social profiles
    """
    url = f"{LUSHA_BASE_URL}/person"
    headers = {"api_key": LUSHA_API_KEY, "Content-Type": "application/json"}
    payload = {
        "firstName": first_name,
        "lastName": last_name,
        "company": company_name,
        "domain": company_domain
    }
    payload = {k: v for k, v in payload.items() if v is not None}

    response = httpx.post(url, json=payload, headers=headers, timeout=30)
    response.raise_for_status()
    return response.json()
```

#### Tool: DuckDuckGo (Free Fallback) (`tools/duckduckgo_tool.py`)

```python
@tool
def duckduckgo_search(query: str, max_results: int = 10) -> list[dict]:
    """
    Free web search using DuckDuckGo.
    BEST FOR: General fallback when other search tools are rate-limited.
    Also useful for finding company websites, LinkedIn profiles, and team pages.
    USE IN STAGES: Any stage as needed.

    Args:
        query: Search query string
        max_results: Number of results to return

    Returns:
        list of dicts with 'title', 'link', 'snippet' for each result
    """
    from duckduckgo_search import DDGS
    with DDGS() as ddgs:
        results = list(ddgs.text(query, max_results=max_results))
    return results
```

#### Tool: Web Scraper (Free) (`tools/web_scraper_tool.py`)

```python
@tool
def scrape_webpage(url: str, extract_type: str = "text") -> dict:
    """
    Scrape a webpage to extract text content.
    BEST FOR: Reading company about pages, team pages, technology pages,
    and blog posts to extract detailed information not available via APIs.
    USE IN STAGES: Any stage — especially Contact Discovery (team pages)
    and BANT Scoring (gathering evidence).

    Args:
        url: The URL to scrape
        extract_type: 'text' for plain text, 'structured' for team member extraction

    Returns:
        dict with 'url', 'title', 'content' (extracted text), 'links'
    """
    import httpx
    from bs4 import BeautifulSoup

    response = httpx.get(url, follow_redirects=True, timeout=15,
                         headers={"User-Agent": "Mozilla/5.0 qlGen Research Bot"})
    soup = BeautifulSoup(response.text, "html.parser")

    for tag in soup(["script", "style", "nav", "footer"]):
        tag.decompose()

    return {
        "url": url,
        "title": soup.title.string if soup.title else "",
        "content": soup.get_text(separator="\n", strip=True)[:5000],
        "links": [a.get("href") for a in soup.find_all("a", href=True)[:50]]
    }
```

### Step 3.2 — Single Agent Definition

This is the core of the entire system. One agent, one comprehensive system prompt, all tools.

```python
# agent/lead_gen_agent.py
from strands import Agent
from strands.models.bedrock import BedrockModel

from app.tools.apollo_tool import apollo_company_search, apollo_people_search
from app.tools.exa_tool import exa_search
from app.tools.hunter_tool import hunter_domain_search, hunter_email_finder
from app.tools.lusha_tool import lusha_person_search
from app.tools.tavily_tool import tavily_search
from app.tools.duckduckgo_tool import duckduckgo_search
from app.tools.web_scraper_tool import scrape_webpage


LEAD_GEN_SYSTEM_PROMPT = """You are an expert B2B lead generation specialist. Your job is to
convert an Ideal Customer Profile (ICP) into a complete, sales-ready list of qualified
companies and decision-maker contacts, enriched with data and scored using the BANT framework.

You have access to 9 tools. Execute your work in 4 sequential stages:

═══════════════════════════════════════════════════════════════
STAGE 1: COMPANY DISCOVERY
═══════════════════════════════════════════════════════════════
Goal: Find companies matching the ICP criteria.

Search strategy (use multiple tools for better coverage):
• apollo_company_search — PRIMARY. Best for structured filters (industry, size, location).
  Start here. Run multiple queries if the ICP spans several industries or regions.
• exa_search — SECONDARY. Best for semantic/qualitative matching (tech stack, business model).
  Use natural language queries describing the ideal company.
• tavily_search — SUPPLEMENTARY. Find companies in recent news matching ICP signals
  (funding rounds, expansion, tech adoption announcements).
• duckduckgo_search — FALLBACK. Use if other tools are rate-limited or return thin results.

For each company found, collect: name, website/domain, industry, city/state/country,
estimated employee count, estimated revenue, and any technology signals.

Qualification: Rate each company 1-10 against the ICP. Discard any below 5.
Deduplicate by domain. Aim for the requested number of companies.

═══════════════════════════════════════════════════════════════
STAGE 2: CONTACT DISCOVERY
═══════════════════════════════════════════════════════════════
Goal: For each qualified company, find 3-5 relevant decision-makers.

Search strategy:
• apollo_people_search — PRIMARY. Search by company domain + target role titles from the ICP.
• hunter_domain_search — SECONDARY. Finds contacts by company domain with email patterns.
• scrape_webpage — SUPPLEMENTARY. Scrape the company's /about, /team, or /leadership page.
• duckduckgo_search — FALLBACK. Search "[company name] + [role title] + LinkedIn".

Prioritize role relevance over volume. A CTO or VP Engineering is far more valuable than
5 random employees. Map discovered titles to the ICP's target role categories.

═══════════════════════════════════════════════════════════════
STAGE 3: CONTACT ENRICHMENT
═══════════════════════════════════════════════════════════════
Goal: Fill in missing contact data fields (email, phone, LinkedIn).

Only enrich fields that are missing — do not re-query data you already have.
• hunter_email_finder — For missing emails when you have first_name + last_name + domain.
• lusha_person_search — For missing phone numbers when you have name + company.
• exa_search or duckduckgo_search — For missing LinkedIn URLs (search by name + company).

Mark each contact's enrichment status:
- "enriched" = email + LinkedIn populated
- "partial" = some fields still missing
- "failed" = enrichment found nothing new

═══════════════════════════════════════════════════════════════
STAGE 4: BANT SCORING
═══════════════════════════════════════════════════════════════
Goal: Score each company using the BANT framework. If you need additional evidence,
use tavily_search, exa_search, or scrape_webpage to research the company further.

SCORING RUBRIC (1-5 per dimension):

BUDGET (company size & financial capacity):
  5 = Revenue > upper ICP range, clear tech budget signals (recent funding, tech hires)
  4 = Revenue in upper half of ICP range, some budget indicators
  3 = Revenue within ICP range, no specific budget signals
  2 = Revenue in lower range, budget unclear
  1 = Revenue below ICP minimum, likely budget-constrained

AUTHORITY (contact role & decision-making power):
  5 = C-suite directly owning tech/digital budget (CTO, CDO, CEO at small co)
  4 = VP-level in relevant function (VP Engineering, VP Ecommerce)
  3 = Director-level in relevant function
  2 = Manager-level or adjacent function
  1 = No relevant decision-maker identified

NEED (alignment with ICP transformation drivers):
  5 = 3+ strong signals matching ICP needs (tech debt, growth pain, stated initiatives)
  4 = 2 matching signals
  3 = 1 matching signal or general industry alignment
  2 = Weak alignment, speculative need
  1 = No discernible need alignment

TIMING (readiness to act):
  5 = Active RFP/vendor evaluation, recent relevant job postings, public announcements
  4 = Recent funding round, stated transformation timeline
  3 = General growth trajectory suggesting near-term action
  2 = No timing signals but profile suggests eventual need
  1 = No timing signals, possibly just completed similar project

Every score MUST have a specific reason citing actual evidence from your research.
No assumptions, no black boxes.

═══════════════════════════════════════════════════════════════
OUTPUT FORMAT
═══════════════════════════════════════════════════════════════
Return your complete results as a single JSON object with this exact structure:

```json
{
  "companies": [
    {
      "name": "Company Name",
      "website": "domain.com",
      "industry": "Ecommerce / Fashion",
      "city": "San Francisco",
      "state": "California",
      "country": "US",
      "employee_count": 250,
      "revenue_estimate": 50000000,
      "tech_signals": ["Shopify Plus", "AWS", "Klaviyo"],
      "icp_match_score": 8,
      "match_reasoning": "Strong match because...",
      "source": "apollo+exa",
      "contacts": [
        {
          "full_name": "Jane Doe",
          "first_name": "Jane",
          "last_name": "Doe",
          "designation": "Chief Technology Officer",
          "role_category": "CTO",
          "email": "jane@domain.com",
          "phone": "+1-555-0123",
          "linkedin_url": "https://linkedin.com/in/janedoe",
          "source": "apollo",
          "confidence": 0.9,
          "enrichment_status": "enriched"
        }
      ],
      "bant_score": {
        "budget_score": 4,
        "budget_reason": "Revenue ~$50M, Series B raised in 2025...",
        "authority_score": 5,
        "authority_reason": "CTO identified with direct tech budget ownership...",
        "need_score": 4,
        "need_reason": "Running legacy Magento, job postings mention headless...",
        "timing_score": 3,
        "timing_reason": "Growing 25% YoY, no public replatforming timeline yet...",
        "total_score": 16,
        "overall_summary": "Strong prospect with budget and clear need. CTO access confirmed. Timing uncertain but signals suggest 12-month window. Recommend outreach with replatforming case study."
      }
    }
  ],
  "summary": {
    "total_companies": 20,
    "total_contacts": 75,
    "avg_bant_score": 14.2,
    "hot_leads": 5,
    "warm_leads": 10,
    "cool_leads": 5
  }
}
```

═══════════════════════════════════════════════════════════════
CRITICAL RULES
═══════════════════════════════════════════════════════════════
1. NEVER fabricate company names, contacts, emails, or phone numbers.
   Only return data verified through tool results.
2. If a tool fails or returns no results, try alternative tools before giving up.
3. Quality over quantity — 15 well-researched companies beat 25 thin ones.
4. Partial data is acceptable — mark missing fields as null, not made-up values.
5. Every BANT score needs evidence-backed reasoning, not generic statements.
6. Deduplicate companies by domain throughout the process.
7. Process ALL stages before returning — do not skip enrichment or scoring.
"""


def create_lead_gen_agent() -> Agent:
    """Create the single lead generation agent with all tools."""
    model = BedrockModel(
        model_id="anthropic.claude-sonnet-4-20250514",
        region_name="us-east-1"
    )

    return Agent(
        model=model,
        system_prompt=LEAD_GEN_SYSTEM_PROMPT,
        tools=[
            # Stage 1: Company Discovery
            apollo_company_search,
            exa_search,
            tavily_search,
            duckduckgo_search,
            # Stage 2: Contact Discovery
            apollo_people_search,
            hunter_domain_search,
            # Stage 3: Enrichment
            hunter_email_finder,
            lusha_person_search,
            # Used across stages
            scrape_webpage,
        ]
    )
```

### Step 3.3 — Prompt Builder

The prompt builder converts the structured ICP JSON into a natural-language prompt for the agent.

```python
# agent/prompt_builder.py
import json

def build_pipeline_prompt(icp: dict, options: dict) -> str:
    """Convert ICP config + options into a full agent prompt."""

    max_companies = options.get("max_companies", 25)
    max_contacts = options.get("max_contacts_per_company", 5)

    return f"""
Execute the full lead generation pipeline for the following Ideal Customer Profile.
Find {max_companies} qualified companies with up to {max_contacts} contacts each.

══════════════════════════════════════
IDEAL CUSTOMER PROFILE
══════════════════════════════════════

1. TARGET OFFERING:
{json.dumps(icp['target_offering'], indent=2)}

2. TARGET REGIONS:
{json.dumps(icp['regions'], indent=2)}

3. INDUSTRY TYPES & VERTICALS:
{json.dumps(icp['industry_types'], indent=2)}

4. COMPANY SIZE:
   - Employees: {icp['company_size']['employees_min']:,} to {icp['company_size']['employees_max']:,}
   - Revenue: {icp['company_size'].get('revenue_currency', 'USD')} {icp['company_size']['revenue_min']:,} to {icp['company_size']['revenue_max']:,}

5. TECHNOLOGY MATURITY SIGNALS:
   Positive signals: {json.dumps(icp['technology_maturity'].get('signals', []), indent=2)}
   Negative signals (migration needs): {json.dumps(icp['technology_maturity'].get('negative_signals', []), indent=2)}

6. INFRASTRUCTURE READINESS:
{json.dumps(icp['infrastructure_readiness'], indent=2)}

7. DIGITAL TRANSFORMATION DRIVERS:
   Growth triggers: {json.dumps(icp['digital_transformation_drivers'].get('growth_triggers', []))}
   Operational pains: {json.dumps(icp['digital_transformation_drivers'].get('operational_pains', []))}
   Competitive pressures: {json.dumps(icp['digital_transformation_drivers'].get('competitive_pressures', []))}
   Strategic initiatives: {json.dumps(icp['digital_transformation_drivers'].get('strategic_initiatives', []))}

8. LEADERSHIP TRAITS:
   Target roles: {json.dumps(icp['leadership_traits'].get('target_roles', []))}
   Behavioral traits: {json.dumps(icp['leadership_traits'].get('behavioral_traits', []))}

══════════════════════════════════════
INSTRUCTIONS
══════════════════════════════════════
Now execute all 4 stages (Company Discovery → Contact Discovery → Enrichment → BANT Scoring)
and return the complete results as the JSON structure defined in your system prompt.

Begin with Stage 1: Company Discovery.
"""
```

### Step 3.4 — Simplified Pipeline Orchestrator

With a single agent, the orchestrator is dramatically simpler.

```python
# services/pipeline_service.py
import json
from uuid import UUID
from datetime import datetime

from app.agent.lead_gen_agent import create_lead_gen_agent
from app.agent.prompt_builder import build_pipeline_prompt
from app.db.session import get_db_session


async def execute_pipeline(run_id: UUID):
    """
    Main pipeline execution.
    Creates a single agent, sends it the ICP prompt, parses the result,
    and saves everything to the database.
    """
    async with get_db_session() as db:
        run = await get_pipeline_run(run_id, db)
        icp_config = await get_icp_config(run.icp_config_id, db)
        icp = icp_config.config_json

        try:
            # ── Mark pipeline as running ─────────────────────────
            await update_run(run_id, status="running",
                           current_stage="agent_executing",
                           started_at=datetime.utcnow(), db=db)

            # ── Create agent and execute ─────────────────────────
            agent = create_lead_gen_agent()
            prompt = build_pipeline_prompt(icp, run.options or {})

            # Single agent call — it handles all 4 stages internally
            result = agent(prompt)

            # ── Parse the agent's JSON output ────────────────────
            result_json = parse_json_from_agent_result(result)

            # ── Save results to database ─────────────────────────
            companies_saved = 0
            contacts_saved = 0

            for company_data in result_json.get("companies", []):
                # Save company
                company = await save_company(company_data, run_id, db)
                companies_saved += 1

                # Save contacts
                for contact_data in company_data.get("contacts", []):
                    await save_contact(contact_data, company.id, db)
                    contacts_saved += 1

                # Save BANT score
                bant_data = company_data.get("bant_score")
                if bant_data:
                    await save_bant_score(bant_data, company.id, db)

            # ── Mark completed ───────────────────────────────────
            await update_run(run_id,
                           status="completed",
                           current_stage="completed",
                           companies_found=companies_saved,
                           contacts_found=contacts_saved,
                           completed_at=datetime.utcnow(),
                           db=db)

        except Exception as e:
            await update_run(run_id,
                           status="failed",
                           error_log=str(e),
                           db=db)
            raise


def parse_json_from_agent_result(result) -> dict:
    """
    Extract JSON from the agent's text response.
    The agent may wrap JSON in ```json blocks or include preamble text.
    """
    text = str(result)

    # Try to find JSON block in markdown code fence
    if "```json" in text:
        start = text.index("```json") + 7
        end = text.index("```", start)
        text = text[start:end].strip()
    elif "```" in text:
        start = text.index("```") + 3
        end = text.index("```", start)
        text = text[start:end].strip()

    # Try to find JSON object
    if "{" in text:
        start = text.index("{")
        # Find matching closing brace
        depth = 0
        for i, char in enumerate(text[start:], start):
            if char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    text = text[start:i+1]
                    break

    return json.loads(text)
```

### Step 3.5 — Progress Tracking via Strands Callbacks (Optional Enhancement)

Strands supports callback hooks that fire during agent execution. Use these to update pipeline progress in real-time for the SSE endpoint:

```python
# agent/lead_gen_agent.py — enhanced with callbacks

from strands.agent.callback_handler import CallbackHandler

class PipelineProgressCallback(CallbackHandler):
    """Tracks which stage the agent is in based on tool usage patterns."""

    def __init__(self, run_id: UUID):
        self.run_id = run_id
        self.tools_called = []

    def on_tool_start(self, tool_name: str, tool_input: dict):
        self.tools_called.append(tool_name)

        # Infer current stage from tool usage pattern
        if tool_name in ["apollo_company_search", "exa_search"] and \
           "apollo_people_search" not in self.tools_called:
            stage = "company_discovery"
        elif tool_name in ["apollo_people_search", "hunter_domain_search"]:
            stage = "contact_discovery"
        elif tool_name in ["hunter_email_finder", "lusha_person_search"]:
            stage = "enrichment"
        else:
            stage = "scoring"

        # Fire async update (non-blocking)
        asyncio.create_task(
            update_run(self.run_id, current_stage=stage)
        )

    def on_tool_end(self, tool_name: str, tool_output):
        pass  # Could log tool results for debugging


def create_lead_gen_agent(run_id: UUID = None) -> Agent:
    model = BedrockModel(
        model_id="anthropic.claude-sonnet-4-20250514",
        region_name="us-east-1"
    )

    callback = PipelineProgressCallback(run_id) if run_id else None

    return Agent(
        model=model,
        system_prompt=LEAD_GEN_SYSTEM_PROMPT,
        tools=[
            apollo_company_search, exa_search, tavily_search,
            duckduckgo_search, apollo_people_search,
            hunter_domain_search, hunter_email_finder,
            lusha_person_search, scrape_webpage,
        ],
        callback_handler=callback
    )
```

---

## 8. Phase 4 — Frontend (React)

**Duration:** ~2 hours

### Step 4.1 — Application Shell & Routing

```tsx
// src/App.tsx
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { ConfigProvider, theme } from 'antd';
import AppLayout from './components/layout/AppLayout';

function App() {
  return (
    <ConfigProvider theme={{ algorithm: theme.defaultAlgorithm,
                             token: { colorPrimary: '#1F4E79', borderRadius: 8 } }}>
      <BrowserRouter>
        <AppLayout>
          <Routes>
            <Route path="/" element={<Navigate to="/dashboard" />} />
            <Route path="/dashboard" element={<DashboardPage />} />
            <Route path="/icp/new" element={<ICPConfigPage />} />
            <Route path="/icp/:id/edit" element={<ICPConfigPage />} />
            <Route path="/icp" element={<ICPListPage />} />
            <Route path="/pipeline/:runId" element={<PipelinePage />} />
            <Route path="/leads/:runId" element={<LeadsPage />} />
          </Routes>
        </AppLayout>
      </BrowserRouter>
    </ConfigProvider>
  );
}
```

### Step 4.2 — ICP Configuration Wizard

The ICP wizard is a multi-step form matching the 8 configuration parameters from the spec. Use Ant Design `Steps` component and `Form`.

**Wizard Steps:**

| Step | Component | ICP Fields | UI Elements |
|------|-----------|-----------|-------------|
| 1 | `ICPStepOffering` | target_offering | TextArea for service descriptions, tag input for adding multiple offerings |
| 2 | `ICPStepRegions` | regions | Country selector, state/city multi-select with search |
| 3 | `ICPStepIndustry` | industry_types | Cascading checklist (vertical → sub-vertical), custom entry option |
| 4 | `ICPStepCompanySize` | company_size | Slider ranges for employees & revenue, currency selector |
| 5 | `ICPStepTechMaturity` | technology_maturity | Tag input for positive signals, separate tag input for negative signals |
| 6 | `ICPStepInfra` | infrastructure_readiness | Checklist of infrastructure indicators with ability to add custom |
| 7 | `ICPStepDrivers` | digital_transformation_drivers | Categorized inputs (Growth Triggers, Operational Pains, Competitive Pressures, Strategic Initiatives) — each is a tag list |
| 8 | `ICPStepLeadership` | leadership_traits | Multi-select for target roles, tag input for behavioral traits |

**Final Step:** `ICPSummary` — read-only review of all entered data, with a "Save & Run Pipeline" button.

```tsx
// Simplified wizard structure
const ICPWizard: React.FC = () => {
  const [current, setCurrent] = useState(0);
  const [formData, setFormData] = useState<ICPConfig>(defaultICP);

  const steps = [
    { title: 'Offering',    content: <ICPStepOffering data={formData} onChange={setFormData} /> },
    { title: 'Regions',     content: <ICPStepRegions data={formData} onChange={setFormData} /> },
    { title: 'Industry',    content: <ICPStepIndustry data={formData} onChange={setFormData} /> },
    { title: 'Size',        content: <ICPStepCompanySize data={formData} onChange={setFormData} /> },
    { title: 'Tech',        content: <ICPStepTechMaturity data={formData} onChange={setFormData} /> },
    { title: 'Infra',       content: <ICPStepInfra data={formData} onChange={setFormData} /> },
    { title: 'Drivers',     content: <ICPStepDrivers data={formData} onChange={setFormData} /> },
    { title: 'Leadership',  content: <ICPStepLeadership data={formData} onChange={setFormData} /> },
    { title: 'Review',      content: <ICPSummary data={formData} /> },
  ];

  return (
    <div>
      <Steps current={current} items={steps.map(s => ({ title: s.title }))} />
      <div className="mt-8">{steps[current].content}</div>
      <div className="mt-6 flex justify-between">
        {current > 0 && <Button onClick={() => setCurrent(c => c - 1)}>Previous</Button>}
        {current < steps.length - 1 && (
          <Button type="primary" onClick={() => setCurrent(c => c + 1)}>Next</Button>
        )}
        {current === steps.length - 1 && (
          <Button type="primary" onClick={handleSaveAndRun}>Save & Run Pipeline</Button>
        )}
      </div>
    </div>
  );
};
```

### Step 4.3 — Pipeline Dashboard

Real-time pipeline progress using Server-Sent Events (SSE). Since the single agent handles all stages, progress is inferred from tool-usage callbacks.

```tsx
const PipelineDashboard: React.FC<{ runId: string }> = ({ runId }) => {
  const [status, setStatus] = useState<PipelineStatus>({
    stage: 'pending', progress: 0, message: ''
  });

  useEffect(() => {
    const eventSource = new EventSource(
      `${API_BASE}/pipeline/${runId}/stream`
    );

    eventSource.addEventListener('stage_update', (event) => {
      const data = JSON.parse(event.data);
      setStatus(data);
    });

    eventSource.addEventListener('completed', (event) => {
      const data = JSON.parse(event.data);
      setStatus({ stage: 'completed', ...data });
      eventSource.close();
    });

    eventSource.addEventListener('error', () => {
      eventSource.close();
    });

    return () => eventSource.close();
  }, [runId]);

  const stages = [
    { key: 'company_discovery', title: 'Company Discovery', icon: <SearchOutlined /> },
    { key: 'contact_discovery', title: 'Contact Discovery', icon: <TeamOutlined /> },
    { key: 'enrichment',        title: 'Enrichment',        icon: <DatabaseOutlined /> },
    { key: 'scoring',           title: 'BANT Scoring',      icon: <BarChartOutlined /> },
  ];

  return (
    <Card title="Pipeline Progress">
      <Steps
        current={stages.findIndex(s => s.key === status.stage)}
        items={stages.map(s => ({
          title: s.title,
          icon: s.icon,
          status: getStepStatus(s.key, status.stage),
        }))}
      />
      <div className="mt-6 text-center">
        {status.stage !== 'completed' ? (
          <Spin tip={status.message || 'Agent is working...'} />
        ) : (
          <Result
            status="success"
            title="Pipeline Complete"
            subTitle={`${status.companies_found} companies, ${status.contacts_found} contacts`}
            extra={<Button type="primary" href={`/leads/${runId}`}>View Results</Button>}
          />
        )}
      </div>
    </Card>
  );
};
```

### Step 4.4 — Lead Results Table

Professional data table with expandable company rows, BANT visualization, and export controls.

```tsx
const LeadResultsTable: React.FC<{ runId: string }> = ({ runId }) => {
  const { data, loading } = useLeads(runId);

  const columns = [
    { title: 'Serial#', dataIndex: 'serial', width: 80 },
    { title: 'Company Name', dataIndex: 'company_name', sorter: true },
    { title: 'Website', dataIndex: 'website', render: (url) => <a href={`https://${url}`} target="_blank">{url}</a> },
    { title: 'Geo/City', dataIndex: 'city' },
    { title: 'Contact Name', dataIndex: 'contact_name' },
    { title: 'Designation', dataIndex: 'designation' },
    { title: 'LinkedIn', dataIndex: 'linkedin', render: (url) => url ? <a href={url} target="_blank">Profile</a> : '—' },
    { title: 'Email', dataIndex: 'email' },
    { title: 'Phone', dataIndex: 'phone' },
    { title: 'BANT Score', dataIndex: 'bant_score',
      render: (score) => <BANTScoreDisplay score={score} />,
      sorter: true, defaultSortOrder: 'descend' },
  ];

  return (
    <div>
      <div className="flex justify-between mb-4">
        <h2>Qualified Leads</h2>
        <ExportControls runId={runId} />
      </div>
      <Table
        columns={columns}
        dataSource={data}
        loading={loading}
        expandable={{
          expandedRowRender: (record) => <BANTDetailPanel score={record.bant_detail} />
        }}
        pagination={{ pageSize: 50 }}
      />
    </div>
  );
};
```

### Step 4.5 — BANT Score Display Component

```tsx
const BANTScoreDisplay: React.FC<{ score: BANTDetail }> = ({ score }) => {
  const color = score.total >= 16 ? '#52c41a'      // Green — hot lead
              : score.total >= 12 ? '#faad14'       // Yellow — warm lead
              : '#ff4d4f';                           // Red — cold lead

  return (
    <Tooltip title={`B:${score.budget} A:${score.authority} N:${score.need} T:${score.timing}`}>
      <Tag color={color} style={{ fontWeight: 'bold', fontSize: 14 }}>
        {score.total}/20
      </Tag>
    </Tooltip>
  );
};

const BANTDetailPanel: React.FC<{ score: BANTDetail }> = ({ score }) => (
  <Descriptions bordered size="small" column={2}>
    <Descriptions.Item label={`Budget (${score.budget}/5)`}>{score.budget_reason}</Descriptions.Item>
    <Descriptions.Item label={`Authority (${score.authority}/5)`}>{score.authority_reason}</Descriptions.Item>
    <Descriptions.Item label={`Need (${score.need}/5)`}>{score.need_reason}</Descriptions.Item>
    <Descriptions.Item label={`Timing (${score.timing}/5)`}>{score.timing_reason}</Descriptions.Item>
    <Descriptions.Item label="Summary" span={2}>{score.overall_summary}</Descriptions.Item>
  </Descriptions>
);
```

---

## 9. Phase 5 — Integration & End-to-End Testing

**Duration:** ~30 minutes

### Step 5.1 — Manual E2E Test Checklist

| # | Test Case | Expected Result |
|---|-----------|----------------|
| 1 | Create ICP via wizard with sample US Ecommerce config | ICP saved, appears in list |
| 2 | Trigger pipeline run | Run starts, status updates stream via SSE |
| 3 | Agent completes full pipeline | Companies, contacts, and BANT scores all populated |
| 4 | Companies are in target geography/industry | No off-target results |
| 5 | 3-5 contacts per company with role relevance | Decision-makers, not random employees |
| 6 | Enrichment: email filled for 60%+ contacts | LinkedIn for 70%+ |
| 7 | BANT scores have explanations | Every score has a specific, evidence-based reason |
| 8 | Results table loads with all spec columns | Matches spec output format exactly |
| 9 | BANT score expand shows detailed reasoning | All 4 dimensions + summary |
| 10 | Export XLSX | Downloads valid Excel file matching spec format |
| 11 | Export CSV | Downloads valid CSV |
| 12 | Second ICP (Indian Manufacturing) | Different config, separate run, different results |

### Step 5.2 — Tool Error Handling

All tools should implement retry logic with exponential backoff:

```python
import time
from functools import wraps

def retry_with_backoff(max_retries=3, base_delay=1):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except httpx.HTTPStatusError as e:
                    if e.response.status_code == 429 and attempt < max_retries - 1:
                        delay = base_delay * (2 ** attempt)
                        time.sleep(delay)
                    else:
                        raise
            return func(*args, **kwargs)
        return wrapper
    return decorator
```

Apply this decorator to each `@tool` function, or implement it inside the tool functions before the HTTP call.

---

## 10. Phase 6 — AWS Deployment

### Target Architecture (AWS)

```
                    ┌─────────────┐
                    │   Route 53  │
                    │  DNS        │
                    └──────┬──────┘
                           │
                    ┌──────▼──────┐
                    │  CloudFront │  ← S3 (React build)
                    │  CDN        │
                    └──────┬──────┘
                           │
                    ┌──────▼──────┐
                    │  ALB        │  ← HTTPS termination
                    │             │
                    └──┬──────┬───┘
                       │      │
               ┌───────▼──┐ ┌─▼────────┐
               │  ECS      │ │  ECS     │
               │  Backend  │ │  Backend │  ← Fargate tasks (auto-scaling)
               │  Task 1   │ │  Task 2  │
               └─────┬─────┘ └──┬───────┘
                     │           │
               ┌─────▼───────────▼─────┐
               │   Amazon RDS          │
               │   PostgreSQL 16       │
               │   + pgvector          │
               │   (Multi-AZ)          │
               └───────────────────────┘
                     │
               ┌─────▼───────────────┐
               │   AWS Bedrock       │
               │   (Claude Sonnet)   │
               └─────────────────────┘
```

### Step 6.1 — Dockerize for Production

**Backend Dockerfile:**

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app/ app/
COPY alembic/ alembic/
COPY alembic.ini .
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4"]
```

**Frontend Dockerfile (multi-stage build):**

```dockerfile
FROM node:20-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
```

### Step 6.2 — AWS Resource Provisioning

| Resource | Service | Config |
|----------|---------|--------|
| VPC | VPC + 2 public/2 private subnets | 10.0.0.0/16 |
| Database | RDS PostgreSQL 16 | db.t3.medium, Multi-AZ, pgvector enabled |
| Backend | ECS Fargate | 1 vCPU, 2GB RAM, min 2 tasks, autoscale to 4 |
| Frontend | S3 + CloudFront | Static hosting with OAI |
| Load Balancer | ALB | HTTPS (ACM cert), path-based routing |
| Secrets | Secrets Manager | API keys, DB credentials |
| IAM | Task execution role | Bedrock InvokeModel, Secrets Manager read, CloudWatch Logs |
| Monitoring | CloudWatch | Logs, metrics, alarms on error rates |

### Step 6.3 — Deployment Script

```bash
#!/bin/bash
# infra/scripts/deploy.sh

# 1. Build and push Docker images
aws ecr get-login-password | docker login --username AWS --password-stdin $ECR_REPO
docker build -t qlgen-backend ./backend
docker tag qlgen-backend:latest $ECR_REPO/qlgen-backend:latest
docker push $ECR_REPO/qlgen-backend:latest

# 2. Build and deploy frontend to S3
cd frontend && npm run build
aws s3 sync dist/ s3://$FRONTEND_BUCKET --delete
aws cloudfront create-invalidation --distribution-id $CF_DIST_ID --paths "/*"

# 3. Update ECS service
aws ecs update-service --cluster qlgen --service qlgen-backend --force-new-deployment

# 4. Run DB migrations (via ECS run-task)
aws ecs run-task --cluster qlgen --task-definition qlgen-migrate --launch-type FARGATE
```

### Step 6.4 — Environment Variables (Production)

Use AWS Secrets Manager for sensitive values. Reference them in ECS task definition:

```json
{
  "secrets": [
    {"name": "DATABASE_URL", "valueFrom": "arn:aws:secretsmanager:us-east-1:...:qlgen/db-url"},
    {"name": "APOLLO_API_KEY", "valueFrom": "arn:aws:secretsmanager:us-east-1:...:qlgen/apollo-key"},
    {"name": "EXA_API_KEY", "valueFrom": "arn:aws:secretsmanager:us-east-1:...:qlgen/exa-key"},
    {"name": "HUNTER_API_KEY", "valueFrom": "arn:aws:secretsmanager:us-east-1:...:qlgen/hunter-key"},
    {"name": "LUSHA_API_KEY", "valueFrom": "arn:aws:secretsmanager:us-east-1:...:qlgen/lusha-key"},
    {"name": "TAVILY_API_KEY", "valueFrom": "arn:aws:secretsmanager:us-east-1:...:qlgen/tavily-key"}
  ]
}
```

---

## 11. API External Tool Reference

### Tool Selection Strategy by Stage

All tools are registered with the single agent. The system prompt guides the agent on which tools to prefer at each stage, but the agent can use any tool at any time if it determines it would be helpful.

| Stage | Primary Tools | Secondary/Fallback | Purpose |
|-------|--------------|-------------------|---------|
| **Company Discovery** | `apollo_company_search`, `exa_search` | `tavily_search`, `duckduckgo_search` | Find companies matching ICP criteria |
| **Contact Discovery** | `apollo_people_search`, `hunter_domain_search` | `scrape_webpage`, `duckduckgo_search` | Find decision-makers |
| **Enrichment** | `hunter_email_finder`, `lusha_person_search` | `exa_search`, `duckduckgo_search` | Fill missing contact data |
| **BANT Scoring** | `tavily_search`, `exa_search` | `duckduckgo_search`, `scrape_webpage` | Gather evidence for scoring |

### API Rate Limits & Quotas (Estimated)

| API | Rate Limit | Daily Quota | Cost |
|-----|-----------|-------------|------|
| Apollo.io | 5 req/sec | Varies by plan | Credit-based |
| Exa | 10 req/sec | 1000/month (free tier) | Pay per search |
| Hunter.io | 10 req/sec | 25/month (free), 500/month (starter) | Per verification |
| Lusha | 5 req/sec | 5 credits/month (free) | Credit-based |
| Tavily | 5 req/sec | 1000/month (free) | Per search |
| DuckDuckGo | No official limit | Unlimited (free) | Free |

### Fallback Strategy

The single agent handles fallback logic naturally through its system prompt instructions:
1. If a primary tool returns an error or empty results, the agent tries the secondary tool.
2. If all tools fail for a specific data point, the agent marks it as null and continues.
3. DuckDuckGo serves as the unlimited free fallback for any stage.
4. The agent never blocks the entire pipeline on a single tool failure.

---

## 12. Data Models

### Pydantic Request/Response Schemas

```python
# schemas/icp.py
class ICPConfigCreate(BaseModel):
    name: str
    description: str | None = None
    config: dict  # Validated against ICP JSON schema

class ICPConfigResponse(BaseModel):
    id: UUID
    name: str
    description: str | None
    config: dict
    created_at: datetime
    updated_at: datetime | None

# schemas/pipeline.py
class PipelineRunRequest(BaseModel):
    icp_config_id: UUID
    options: PipelineOptions = PipelineOptions()

class PipelineOptions(BaseModel):
    max_companies: int = 25
    max_contacts_per_company: int = 5

class PipelineRunResponse(BaseModel):
    id: UUID
    status: str
    current_stage: str | None
    companies_found: int
    contacts_found: int
    started_at: datetime | None
    completed_at: datetime | None

# schemas/export.py — matches spec output format exactly
class LeadExportRow(BaseModel):
    serial: int
    company_name: str
    website: str | None
    geo_city: str | None
    contact_name: str | None
    designation: str | None
    linkedin: str | None
    email: str | None
    phone: str | None
    bant_score: int | None
```

---

## 13. BANT Scoring Algorithm

### Scoring Methodology

The BANT scoring is **LLM-driven but deterministic in structure**. The single agent receives the full context — the ICP definition, all discovered company data, contact information, and any additional research it conducted — and produces scores within the defined rubric embedded in its system prompt.

Because the single agent has seen everything from Stage 1 through Stage 3, it has **richer context** for scoring than a separate scoring agent would. It remembers the tech signals it found during company discovery and the role seniority it identified during contact discovery, producing more nuanced and evidence-backed scores.

### Score Interpretation Guide

| Total Score | Label | Color | Sales Action |
|-------------|-------|-------|-------------|
| 17–20 | **Hot** | Green | Immediate outreach — high-priority |
| 13–16 | **Warm** | Amber | Qualified — schedule outreach within 1 week |
| 9–12 | **Cool** | Blue | Nurture — add to drip sequence |
| 4–8 | **Cold** | Red | Low priority — revisit quarterly |

### Explainability Guarantee

Every BANT score includes:
- Individual dimension scores (1–5) with text reasoning
- An overall summary paragraph written for a sales rep
- Source attribution (which data points drove the score)

This ensures **no black box** scoring, per the spec requirement.

---

## 14. Risk & Mitigation

| Risk | Impact | Mitigation |
|------|--------|-----------|
| Agent context window fills up (>50 companies) | Incomplete output, truncated JSON | Limit hackathon runs to 25 companies; see Section 15 for scaling strategy |
| API rate limits during demo | Agent retries stall | Pre-run a demo dataset; DuckDuckGo as unlimited fallback |
| LLM hallucinating company data | Fake companies in output | System prompt explicitly forbids fabrication; post-processing validates website domains resolve |
| Slow pipeline (10+ min for 25 companies) | Poor demo experience | Show progress via SSE; Strands callbacks infer stage from tool usage |
| API key quotas exhausted | Tools return errors | Agent handles errors gracefully per system prompt; graceful degradation |
| Agent JSON output malformed | Pipeline save fails | Robust JSON parser with fallback extraction; retry agent call once if parse fails |
| pgvector embedding costs | High Bedrock usage | Only generate embeddings for dedup; optional for hackathon |
| Contact data privacy concerns | Legal risk | Only collect publicly available business contact info; include disclaimer in export |

---

## 15. Scaling to Multi-Agent (Future)

The single-agent design is optimal for the hackathon (15–25 companies). For production scale, here's the migration path:

### When to Split

| Signal | Threshold | Action |
|--------|----------|--------|
| Context window limits | >50 companies per run | Split into 2 agents |
| Pipeline duration | >15 minutes | Split + parallelize |
| Output quality drops | BANT scores become generic | Dedicated scoring agent with focused context |

### Recommended 2-Agent Split

```
Agent 1: Discovery Agent
  - Stage 1 (Company Discovery) + Stage 2 (Contact Discovery)
  - Tools: apollo_company_search, exa_search, tavily_search,
           apollo_people_search, hunter_domain_search, duckduckgo_search, scrape_webpage
  - Output: Companies + contacts saved to DB

Agent 2: Enrichment & Scoring Agent
  - Reads companies+contacts from DB (not from Agent 1's context)
  - Stage 3 (Enrichment) + Stage 4 (BANT Scoring)
  - Tools: hunter_email_finder, lusha_person_search, tavily_search,
           exa_search, duckduckgo_search, scrape_webpage
  - Processes companies in batches of 10 to manage context
  - Output: Enriched contacts + BANT scores saved to DB
```

### Code Changes Required

The modular tool design means splitting requires:
1. Creating a second agent definition file with a focused system prompt
2. Updating the orchestrator to call agents sequentially with DB as intermediate store
3. No changes to tools, models, API, or frontend

This is why keeping tools in separate files (one per API) is important — they can be reassigned to any agent without refactoring.

---

## Implementation Timeline (8-Hour Hackathon)

| Hour | Activity | Deliverable |
|------|---------|------------|
| 0:00–0:30 | **Phase 0**: Environment setup, Docker Compose, project scaffolding | Running local dev environment |
| 0:30–1:15 | **Phase 1**: Database schema, Alembic migrations, pgvector | Working database with all tables |
| 1:15–2:45 | **Phase 2**: FastAPI endpoints (ICP CRUD, Pipeline, Leads, Export) | All API endpoints functional |
| 2:45–5:15 | **Phase 3**: Single agent + 9 tools + prompt builder + orchestrator | Pipeline runs end-to-end |
| 5:15–7:15 | **Phase 4**: React frontend — ICP wizard, pipeline dashboard, results table | Full UI functional |
| 7:15–8:00 | **Phase 5**: Integration testing, bug fixes, demo prep | Working prototype |

> **Post-hackathon**: Phase 6 (AWS deployment) is done after functional verification.

**Time savings vs multi-agent approach:** ~30 minutes saved on agent orchestration complexity, intermediate data serialization, and debugging inter-agent handoffs. That time is reallocated to frontend polish and testing.

---

## Quick Start Commands

```bash
# 1. Clone and setup
git clone <repo> && cd qlgen
cp .env.example .env   # Fill in API keys

# 2. Start infrastructure
docker-compose up -d db

# 3. Run backend
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload --port 8000

# 4. Run frontend
cd frontend
npm install
npm run dev

# 5. Open http://localhost:3000
```

---

*This document serves as the complete implementation blueprint. The single-agent architecture prioritizes simplicity and hackathon velocity while maintaining a clear path to multi-agent scaling when needed (see Section 15).*
