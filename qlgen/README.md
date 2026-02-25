# qlGen — ICP-Driven Qualified Lead Generation Tool

A config-driven system that converts a detailed Ideal Customer Profile (ICP) into a sales-ready list of target companies and decision-makers, complete with BANT scoring.

## Architecture Overview

```
┌─────────────────────────────────────────────┐
│           FRONTEND (React + Vite)            │
│  ICP Wizard │ Pipeline Dashboard │ Leads     │
└──────────────────┬──────────────────────────┘
                   │ HTTP / SSE
┌──────────────────▼──────────────────────────┐
│           BACKEND (FastAPI)                  │
│  ICP CRUD │ Pipeline Orchestrator │ Export   │
│                   │                          │
│  ┌────────────────▼─────────────────────┐   │
│  │     SINGLE STRANDS AGENT             │   │
│  │  9 Tools → 4 Stages → JSON Output   │   │
│  └──────────────────────────────────────┘   │
└──────────────────┬──────────────────────────┘
                   │
┌──────────────────▼──────────────────────────┐
│  PostgreSQL + pgvector │ AWS Bedrock (LLM)  │
│  External APIs: Apollo, Exa, Hunter, etc.   │
└─────────────────────────────────────────────┘
```

### Pipeline Stages

1. **Company Discovery** — Finds companies matching ICP criteria using Apollo, Exa, Tavily, DuckDuckGo
2. **Contact Discovery** — Finds decision-makers at each company using Apollo People Search, Hunter, web scraping
3. **Contact Enrichment** — Fills missing emails, phones, LinkedIn using Hunter Email Finder, Lusha
4. **BANT Scoring** — Scores each company on Budget, Authority, Need, Timing (1-5 each, max 20)

## Technology Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React 18 + Vite + TypeScript + Ant Design + TailwindCSS |
| Backend | Python FastAPI (async) |
| Database | PostgreSQL 16 + pgvector |
| Agent Framework | AWS Strands Agents SDK |
| LLM | AWS Bedrock (Claude Sonnet 4) |
| ORM | SQLAlchemy 2.0 + Alembic |
| Export | openpyxl (XLSX), csv (CSV) |

## Prerequisites

- Python 3.11+
- Node.js 20+ and npm
- PostgreSQL 16 with pgvector extension
- AWS CLI configured with Bedrock access (`aws configure`)
- API keys for: Apollo.io, Exa, Hunter.io, Lusha, Tavily

## Quick Start

### 1. Clone and Configure

```bash
cd qlgen
cp .env.example .env   # or edit .env directly with your API keys
```

Edit `.env` and fill in your API keys:
- `APOLLO_API_KEY`
- `EXA_API_KEY`
- `HUNTER_API_KEY`
- `LUSHA_API_KEY`
- `TAVILY_API_KEY`
- `BEDROCK_MODEL_ID` — Set to a valid Bedrock inference profile ID (e.g., `us.anthropic.claude-sonnet-4-20250514-v1:0`)

### 2. Set Up PostgreSQL

If PostgreSQL is running locally:

```bash
sudo -u postgres psql -c "CREATE USER qlgen WITH PASSWORD 'qlgen_pass';"
sudo -u postgres psql -c "CREATE DATABASE qlgen OWNER qlgen;"
sudo -u postgres psql -d qlgen -c "CREATE EXTENSION IF NOT EXISTS vector;"
sudo -u postgres psql -d qlgen -c "GRANT ALL ON SCHEMA public TO qlgen;"
```

Or use Docker:

```bash
docker compose up -d db
```

### 3. Set Up Backend

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Run database migrations
alembic upgrade head

# Start the server
uvicorn app.main:app --reload --port 8000
```

Backend will be available at: http://localhost:8000
API docs at: http://localhost:8000/docs

### 4. Set Up Frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend will be available at: http://localhost:3000

### 5. Open the Application

Navigate to http://localhost:3000 in your browser.

## Usage Guide

### Creating an ICP Configuration

1. Click **"New ICP"** in the sidebar
2. Walk through the 9-step wizard:
   - **Offering** — Define your service areas and give the ICP a name
   - **Regions** — Target countries and priority areas
   - **Industry** — Verticals and sub-verticals
   - **Size** — Employee count and revenue ranges
   - **Tech** — Technology maturity signals (positive and negative)
   - **Infra** — Infrastructure readiness indicators
   - **Drivers** — Digital transformation drivers (growth triggers, pains, pressures, initiatives)
   - **Leadership** — Target roles and behavioral traits
   - **Review** — Summary of all entered data
3. Click **"Save & Run Pipeline"** to save the ICP and immediately start lead generation

### Running a Pipeline

- Pipelines run in the background using a single AWS Strands agent
- The agent autonomously executes all 4 stages using 9 external tools
- Progress is streamed via Server-Sent Events (SSE)
- A typical run for 5-15 companies completes in 2-5 minutes

### Viewing Results

- Navigate to the **Leads** page after pipeline completion
- Results are displayed in a table matching the spec format:
  - Serial#, Company Name, Website, Geo/City, Contact Name, Designation, LinkedIn, Email, Phone, BANT Score
- Expand any row to see detailed BANT scoring with evidence-backed reasons
- Filter by BANT score, sort by score or company name

### Exporting Data

- Click **"Export XLSX"** or **"Export CSV"** to download a sales-ready spreadsheet
- The XLSX includes styled headers, auto-fit columns, and filters

## API Endpoints

### ICP Configuration

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/icp` | Create ICP configuration |
| GET | `/api/v1/icp` | List all ICPs |
| GET | `/api/v1/icp/{id}` | Get specific ICP |
| PUT | `/api/v1/icp/{id}` | Update ICP |
| DELETE | `/api/v1/icp/{id}` | Delete ICP (soft) |

### Pipeline

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/pipeline/run` | Start pipeline run |
| GET | `/api/v1/pipeline/{run_id}` | Get run status |
| GET | `/api/v1/pipeline/{run_id}/stream` | SSE progress stream |
| GET | `/api/v1/pipeline/history/list` | List past runs |

### Leads

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/leads/{run_id}/companies` | Get qualified leads |
| GET | `/api/v1/leads/{run_id}/export?format=xlsx` | Export as XLSX |
| GET | `/api/v1/leads/{run_id}/export?format=csv` | Export as CSV |

## BANT Scoring

Each company is scored on 4 dimensions (1-5 each, max 20):

| Score Range | Label | Color | Action |
|-------------|-------|-------|--------|
| 17-20 | Hot | Green | Immediate outreach |
| 13-16 | Warm | Gold | Schedule outreach within 1 week |
| 9-12 | Cool | Blue | Add to nurture sequence |
| 4-8 | Cold | Red | Low priority |

Every score includes evidence-backed reasoning — no black boxes.

## Project Structure

```
qlgen/
├── .env                          # Environment configuration
├── docker-compose.yml            # PostgreSQL with pgvector
├── backend/
│   ├── requirements.txt
│   ├── alembic.ini
│   ├── alembic/                  # Database migrations
│   └── app/
│       ├── main.py               # FastAPI entry point
│       ├── config.py             # Settings
│       ├── api/                  # API routes (icp, pipeline, leads, health)
│       ├── models/               # SQLAlchemy ORM models
│       ├── schemas/              # Pydantic request/response schemas
│       ├── services/             # Business logic (pipeline, export)
│       ├── agent/                # Strands agent + prompt builder
│       ├── tools/                # 9 API tool wrappers
│       └── db/                   # Database session factory
└── frontend/
    ├── package.json
    ├── vite.config.ts
    └── src/
        ├── App.tsx               # Routes and layout
        ├── api/                  # API client (axios)
        ├── components/           # React components
        ├── pages/                # Page components
        └── types/                # TypeScript interfaces
```

## External API Tools

| Tool | API | Stage | Purpose |
|------|-----|-------|---------|
| apollo_company_search | Apollo.io | Company Discovery | Structured company search |
| apollo_people_search | Apollo.io | Contact Discovery | Find decision-makers |
| exa_search | Exa | Company Discovery, Enrichment | Semantic search |
| hunter_domain_search | Hunter.io | Contact Discovery | Domain email search |
| hunter_email_finder | Hunter.io | Enrichment | Find specific email |
| lusha_person_search | Lusha | Enrichment | Phone numbers |
| tavily_search | Tavily | Company Discovery, Scoring | News and signals |
| duckduckgo_search | DuckDuckGo | Fallback (all stages) | Free web search |
| scrape_webpage | BeautifulSoup | Contact Discovery, Scoring | Web scraping |

## Troubleshooting

### Backend won't start
- Ensure PostgreSQL is running and accessible on port 5432
- Check `.env` has correct `DATABASE_URL`
- Run `alembic upgrade head` to create tables

### Pipeline fails with model error
- Verify `BEDROCK_MODEL_ID` uses an inference profile ID (prefixed with `us.`)
- Check AWS credentials: `aws bedrock list-inference-profiles`
- Ensure your AWS account has Bedrock access enabled

### No companies found
- Check external API keys are valid
- DuckDuckGo (free) is used as fallback if paid APIs fail
- Try with broader ICP criteria (wider geography, larger size range)
