# Doc 3 — AI Agent Implementation Plan (Python / Strands)

## qlGen: ICP-Driven Qualified Lead Generation Tool

---

## 1. Architecture Design

```
                         ┌──────────────┐
                         │ Spring Boot  │
                         │  Backend     │
                         └──────┬───────┘
                                │ HTTP REST (dispatch + callback)
                                v
┌───────────────────────────────────────────────────────────────────────┐
│                     Python Agent Service (FastAPI + Strands)          │
│                                                                       │
│  ┌──────────────┐   ┌─────────────────────────────────────────────┐  │
│  │  FastAPI      │   │           Strands Agent Core                │  │
│  │  HTTP Server  │──>│                                             │  │
│  └──────────────┘   │  ┌───────────┐  ┌───────────┐              │  │
│                      │  │ ICP       │  │ Query     │              │  │
│                      │  │ Interpreter│  │ Generator │              │  │
│                      │  └─────┬─────┘  └─────┬─────┘              │  │
│                      │        │              │                     │  │
│                      │  ┌─────v──────────────v─────┐              │  │
│                      │  │    Company Discovery      │              │  │
│                      │  │    (Tool Orchestration)    │              │  │
│                      │  └─────────────┬─────────────┘              │  │
│                      │                │                             │  │
│                      │  ┌─────────────v─────────────┐              │  │
│                      │  │    Company Enrichment      │              │  │
│                      │  └─────────────┬─────────────┘              │  │
│                      │                │                             │  │
│                      │  ┌─────────────v─────────────┐              │  │
│                      │  │    BANT Scoring Engine      │              │  │
│                      │  └─────────────┬─────────────┘              │  │
│                      │                │                             │  │
│                      │  ┌─────────────v─────────────┐              │  │
│                      │  │    Ranking & Response       │              │  │
│                      │  └───────────────────────────┘              │  │
│                      └─────────────────────────────────────────────┘  │
│                                                                       │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │                    Tool Layer (MCP + REST)                     │  │
│  │                                                                │  │
│  │  ┌─────────┐ ┌────────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ │  │
│  │  │ Tavily  │ │ Hunter │ │ Exa  │ │ Lusha│ │Apollo│ │DuckDuck│ │  │
│  │  │  MCP    │ │  API   │ │ MCP  │ │ API  │ │  MCP │ │  Go   │ │  │
│  │  └─────────┘ └────────┘ └──────┘ └──────┘ └──────┘ └──────┘ │  │
│  └────────────────────────────────────────────────────────────────┘  │
│                                                                       │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │                    LLM Provider (AWS Bedrock)                  │  │
│  │              Claude 4 Sonnet / Claude 4 Haiku                  │  │
│  └────────────────────────────────────────────────────────────────┘  │
└───────────────────────────────────────────────────────────────────────┘
```

### Technology Stack

| Layer              | Technology              | Version / Detail           |
|--------------------|-------------------------|----------------------------|
| Language           | Python                  | 3.11+                      |
| Agent Framework    | Strands Agents          | Latest                     |
| HTTP Server        | FastAPI + Uvicorn       | 0.110+ / 0.29+             |
| LLM Provider       | AWS Bedrock             | Claude 4 Sonnet            |
| MCP Client         | Strands MCP integration | Built-in                   |
| HTTP Client        | httpx                   | 0.27+                      |
| Validation         | Pydantic                | 2.x                        |
| Async Runtime      | asyncio                 | Built-in                   |
| Configuration      | pydantic-settings       | 2.x                        |

---

## 2. Internal Components / Modules

### 2.1 Project Structure

```
agent/
├── main.py                          # FastAPI app entry point
├── config.py                        # Settings via pydantic-settings
├── models/
│   ├── __init__.py
│   ├── icp.py                       # ICP profile Pydantic models
│   ├── lead.py                      # Lead & BANT score models
│   ├── job.py                       # Job request/response models
│   └── progress.py                  # Progress update models
├── agent/
│   ├── __init__.py
│   ├── core.py                      # Strands Agent initialization + system prompt
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── tavily_search.py         # Tavily MCP tool wrapper
│   │   ├── exa_search.py            # Exa MCP tool wrapper
│   │   ├── hunter_lookup.py         # Hunter API tool (email/domain)
│   │   ├── lusha_enrich.py          # Lusha API tool (company enrichment)
│   │   ├── apollo_enrich.py         # Apollo MCP tool wrapper
│   │   ├── duckduckgo_search.py     # DuckDuckGo fallback search
│   │   └── company_scorer.py        # BANT scoring tool
│   └── prompts/
│       └── system_prompt.py         # System prompt template
├── services/
│   ├── __init__.py
│   ├── callback_client.py           # HTTP client to send results back to backend
│   └── progress_reporter.py         # Reports progress to backend
├── requirements.txt
├── Dockerfile
└── tests/
    ├── test_models.py
    └── test_scoring.py
```

### 2.2 Module Responsibilities

| Module                   | Responsibility                                                 |
|--------------------------|----------------------------------------------------------------|
| `main.py`                | FastAPI server — receives job requests, launches agent          |
| `config.py`              | Centralized configuration from environment variables           |
| `agent/core.py`          | Initializes Strands Agent with tools, system prompt, LLM config|
| `agent/tools/*`          | Individual tool wrappers for each external data provider        |
| `agent/prompts/`         | System prompt construction with dynamic ICP context            |
| `services/callback_client.py` | Sends final results to Spring Boot callback URL          |
| `services/progress_reporter.py` | Sends intermediate progress updates to backend         |
| `models/*`               | Pydantic models for request/response validation                |

---

## 3. Communication Flow

### 3.1 Backend → Agent (Inbound)

**POST `/api/v1/process`** — Receives job dispatch from Spring Boot backend.

```python
@app.post("/api/v1/process")
async def process_job(request: JobRequest, background_tasks: BackgroundTasks):
    """Accept a job and process it asynchronously."""
    background_tasks.add_task(run_agent_pipeline, request)
    return {"status": "accepted", "jobId": request.job_id}
```

### 3.2 Agent → Backend (Outbound)

The agent sends two types of callbacks to the backend:

1. **Progress Updates** — During processing
   ```
   POST http://backend:8080/api/v1/internal/jobs/{jobId}/progress
   {"stage": "ENRICHING", "message": "Enriching 5/20 companies", "progress": 35}
   ```

2. **Final Results** — On completion
   ```
   POST http://backend:8080/api/v1/internal/jobs/{jobId}/callback
   {"jobId": "...", "status": "COMPLETED", "leads": [...]}
   ```

### 3.3 Agent → External Tools (MCP + REST)

```
Agent Core
    │
    ├──MCP──> Tavily (search queries)
    ├──MCP──> Exa (semantic company search)
    ├──MCP──> Apollo (company/contact enrichment)
    ├──REST──> Hunter (domain → email/company verification)
    ├──REST──> Lusha (company enrichment)
    ├──REST──> DuckDuckGo (fallback web search, no API key)
    └──LLM──> AWS Bedrock (Claude for reasoning/scoring)
```

### 3.4 Full Pipeline Sequence

```
Backend         Agent (FastAPI)        Strands Agent         External Tools       Bedrock LLM
   │                  │                      │                     │                   │
   │──POST /process──>│                      │                     │                   │
   │<──202 accepted───│                      │                     │                   │
   │                  │──launch pipeline────>│                     │                   │
   │                  │                      │                     │                   │
   │                  │  STAGE 1: INTERPRET ICP                    │                   │
   │                  │                      │─────────────────────────────────────────>│
   │                  │                      │<──parsed ICP + search strategy───────────│
   │<──progress───────│                      │                     │                   │
   │                  │                      │                     │                   │
   │                  │  STAGE 2: DISCOVER COMPANIES               │                   │
   │                  │                      │──search queries────>│ (Tavily/Exa)      │
   │                  │                      │<──raw results───────│                   │
   │<──progress───────│                      │                     │                   │
   │                  │                      │                     │                   │
   │                  │  STAGE 3: ENRICH                           │                   │
   │                  │                      │──enrich requests───>│ (Hunter/Lusha)    │
   │                  │                      │<──enriched data─────│                   │
   │<──progress───────│                      │                     │                   │
   │                  │                      │                     │                   │
   │                  │  STAGE 4: SCORE (BANT)                     │                   │
   │                  │                      │─────────────────────────────────────────>│
   │                  │                      │<──BANT scores + reasoning────────────────│
   │<──progress───────│                      │                     │                   │
   │                  │                      │                     │                   │
   │                  │  STAGE 5: RANK & RETURN                    │                   │
   │<──callback (results)──│<──ranked leads──│                     │                   │
```

---

## 4. Deployment Architecture

### 4.1 Dockerfile

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
```

### 4.2 Docker Compose Service

```yaml
agent:
  build: ./agent
  ports:
    - "8000:8000"
  environment:
    - AWS_ACCESS_KEY_ID=${AWS_ACCESS_KEY_ID}
    - AWS_SECRET_ACCESS_KEY=${AWS_SECRET_ACCESS_KEY}
    - AWS_DEFAULT_REGION=us-east-1
    - BEDROCK_MODEL_ID=anthropic.claude-sonnet-4-20250514-v1:0
    - TAVILY_API_KEY=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
    - HUNTER_API_KEY=562b7f3fe6001d7373b4b5853aed3781b114607d
    - LUSHA_API_KEY=b2c47f59-0b7d-40d4-98e3-1988a01982a8
    - EXA_API_KEY=985db767-02c0-4f65-9bc5-380e0c836a70
    - CLAY_API_KEY=55bd2296e2bc09c3ed68
    - BACKEND_CALLBACK_BASE_URL=http://backend:8080
```

### 4.3 Local Development

```bash
cd agent
python -m venv venv
source venv/bin/activate       # Linux/Mac
# venv\Scripts\activate        # Windows
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

---

## 5. Security Considerations

| Concern                  | Mitigation                                                    |
|--------------------------|---------------------------------------------------------------|
| API Key Storage          | All keys in environment variables, never in code              |
| Input Validation         | Pydantic models validate all inbound requests                 |
| LLM Prompt Injection     | System prompt instructs agent to ignore user-injected instructions |
| Output Sanitization      | Agent output validated against Pydantic response models       |
| Rate Limiting            | Per-tool rate limits to avoid burning API quotas               |
| Network Isolation        | Agent only accessible within Docker network (not exposed publicly) |
| Dependency Security      | Pin dependency versions in requirements.txt                   |
| AWS Credentials          | IAM role with minimum Bedrock permissions; no root keys       |

### Configuration Management

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # AWS
    aws_access_key_id: str
    aws_secret_access_key: str
    aws_default_region: str = "us-east-1"
    bedrock_model_id: str = "anthropic.claude-sonnet-4-20250514-v1:0"

    # Tool API Keys
    tavily_api_key: str
    hunter_api_key: str
    lusha_api_key: str
    exa_api_key: str
    clay_api_key: str = ""

    # Backend
    backend_callback_base_url: str = "http://backend:8080"

    # Agent
    max_search_results: int = 50
    max_enrichment_concurrent: int = 5
    tool_timeout_seconds: int = 30

    class Config:
        env_file = ".env"

settings = Settings()
```

---

## 6. Error Handling Strategy

### 6.1 Multi-Layer Error Handling

| Layer              | Strategy                                                      |
|--------------------|---------------------------------------------------------------|
| FastAPI            | Exception handlers return structured JSON errors              |
| Agent Pipeline     | Try/except around each stage; partial results on failure      |
| Individual Tools   | Per-tool timeout + retry; fallback to alternative tools       |
| LLM Calls          | Retry with exponential backoff; fallback to Claude 4 Haiku if Sonnet fails |
| Callback Delivery  | Retry result delivery to backend 3 times                      |

### 6.2 Tool Fallback Chain

```python
SEARCH_TOOL_CHAIN = [
    ("tavily", tavily_search),      # Primary
    ("exa", exa_search),            # Secondary
    ("duckduckgo", duckduckgo_search),  # Fallback (no API key needed)
]

ENRICHMENT_TOOL_CHAIN = [
    ("apollo", apollo_enrich),       # Primary
    ("lusha", lusha_enrich),         # Secondary
    ("hunter", hunter_lookup),       # Tertiary (email-focused)
]

async def search_with_fallback(query: str) -> list[dict]:
    """Try each search tool in order until one succeeds."""
    for name, tool_fn in SEARCH_TOOL_CHAIN:
        try:
            results = await asyncio.wait_for(tool_fn(query), timeout=30)
            if results:
                logger.info(f"Search succeeded with {name}: {len(results)} results")
                return results
        except Exception as e:
            logger.warning(f"Search tool {name} failed: {e}")
            continue
    return []
```

### 6.3 Graceful Degradation

```python
async def run_agent_pipeline(request: JobRequest):
    try:
        report_progress(request.job_id, "SEARCHING", "Interpreting ICP...", 5)

        # Stage 1: Interpret ICP
        search_queries = await interpret_icp(request.icp_profile)

        report_progress(request.job_id, "SEARCHING", "Discovering companies...", 15)

        # Stage 2: Discover companies
        raw_companies = await discover_companies(search_queries)
        if not raw_companies:
            return send_callback(request.job_id, "COMPLETED", leads=[])

        report_progress(request.job_id, "ENRICHING", f"Enriching {len(raw_companies)} companies...", 40)

        # Stage 3: Enrich (partial failure OK)
        enriched = await enrich_companies(raw_companies)

        report_progress(request.job_id, "SCORING", "Applying BANT scoring...", 70)

        # Stage 4: Score
        scored_leads = await score_companies(enriched, request.bant_weights)

        # Stage 5: Rank and return
        ranked = sorted(scored_leads, key=lambda l: l.bant_score.total, reverse=True)
        ranked = ranked[:request.max_results]

        report_progress(request.job_id, "COMPLETED", f"Found {len(ranked)} qualified leads", 100)
        await send_callback(request.job_id, "COMPLETED", leads=ranked)

    except Exception as e:
        logger.error(f"Pipeline failed for job {request.job_id}: {e}")
        await send_callback(request.job_id, "FAILED", error=str(e))
```

---

## 7. Data Flow Lifecycle

```
┌──────────────────────────────────────────────────────────────────┐
│                       AGENT DATA FLOW                            │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  1. RECEIVE JOB REQUEST                                          │
│     POST /api/v1/process → Validate with Pydantic                │
│     Launch background pipeline                                   │
│              │                                                   │
│              v                                                   │
│  2. ICP INTERPRETATION (LLM)                                     │
│     Send ICP profile to Claude via Bedrock                       │
│     Output: 3-5 optimized search queries + search strategy       │
│     Example: "SaaS companies 50-500 employees Series B US"       │
│              │                                                   │
│              v                                                   │
│  3. COMPANY DISCOVERY (Tools)                                    │
│     Execute search queries across Tavily + Exa + DuckDuckGo      │
│     Deduplicate by domain                                        │
│     Output: List of raw company mentions (name, domain, snippet)  │
│              │                                                   │
│              v                                                   │
│  4. COMPANY ENRICHMENT (Tools)                                   │
│     For each company: query Apollo/Lusha/Hunter                  │
│     Concurrent enrichment (max 5 parallel)                       │
│     Output: Enriched company profiles (size, revenue, tech, etc) │
│              │                                                   │
│              v                                                   │
│  5. BANT SCORING (LLM)                                           │
│     Send each enriched company to Claude for BANT analysis       │
│     Apply user-defined weights (Budget/Authority/Need/Timeline)  │
│     Output: Scored leads with reasoning for each BANT dimension  │
│              │                                                   │
│              v                                                   │
│  6. RANKING & DELIVERY                                           │
│     Sort by weighted total score                                 │
│     Trim to maxResults                                           │
│     POST results to backend callback URL                         │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

### Data Models

```python
from pydantic import BaseModel, Field

class ICPProfile(BaseModel):
    industries: list[str]
    company_size_range: dict  # {"min": 50, "max": 500}
    revenue_range: dict       # {"min": 1000000, "max": 50000000}
    geographies: list[str]
    tech_stack: list[str] = []
    keywords: list[str] = []
    additional_notes: str = ""

class BANTWeights(BaseModel):
    budget: float = Field(ge=0, le=1)
    authority: float = Field(ge=0, le=1)
    need: float = Field(ge=0, le=1)
    timeline: float = Field(ge=0, le=1)

class BANTScore(BaseModel):
    budget: float = Field(ge=0, le=10)
    authority: float = Field(ge=0, le=10)
    need: float = Field(ge=0, le=10)
    timeline: float = Field(ge=0, le=10)
    total: float = Field(ge=0, le=10)
    reasoning: str

class Lead(BaseModel):
    company_name: str
    domain: str
    industry: str
    employee_count: int | None = None
    estimated_revenue: int | None = None
    location: str | None = None
    description: str | None = None
    tech_stack: list[str] = []
    funding_stage: str | None = None
    bant_score: BANTScore

class JobRequest(BaseModel):
    job_id: str
    icp_profile: ICPProfile
    bant_weights: BANTWeights
    max_results: int = 25
    callback_url: str
```

---

## 8. Scalability Considerations

| Concern                  | Approach                                                      |
|--------------------------|---------------------------------------------------------------|
| Concurrent Enrichment    | `asyncio.gather` with semaphore (max 5 concurrent API calls)  |
| LLM Token Optimization   | Batch BANT scoring (5 companies per LLM call)                |
| Multiple Worker Processes| Uvicorn with 2-4 workers for concurrent job handling          |
| Tool Rate Limiting       | Per-tool semaphores respecting provider rate limits            |
| Result Caching           | Cache enrichment results by domain (in-memory dict for MVP)   |
| Pipeline Parallelism     | Search across multiple tools concurrently                     |

### Concurrent Enrichment with Semaphore

```python
ENRICHMENT_SEMAPHORE = asyncio.Semaphore(5)

async def enrich_single(company: dict) -> dict:
    async with ENRICHMENT_SEMAPHORE:
        enriched = await enrich_with_fallback(company)
        return enriched

async def enrich_companies(companies: list[dict]) -> list[dict]:
    tasks = [enrich_single(c) for c in companies]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    return [r for r in results if not isinstance(r, Exception)]
```

---

## 9. Observability

### 9.1 Structured Logging

```python
import structlog

logger = structlog.get_logger()

# Usage
logger.info("pipeline_started", job_id=job_id, industries=icp.industries)
logger.info("search_completed", job_id=job_id, tool="tavily", result_count=len(results))
logger.warning("tool_failed", job_id=job_id, tool="lusha", error=str(e))
logger.error("pipeline_failed", job_id=job_id, stage="ENRICHING", error=str(e))
```

### 9.2 Health Check

```python
@app.get("/health")
async def health():
    return {
        "status": "UP",
        "service": "qlgen-agent",
        "timestamp": datetime.utcnow().isoformat(),
        "tools": {
            "tavily": await check_tool_health("tavily"),
            "exa": await check_tool_health("exa"),
            "hunter": await check_tool_health("hunter"),
        }
    }
```

### 9.3 Key Metrics

| Metric                          | Type    | Description                          |
|---------------------------------|---------|--------------------------------------|
| `agent.pipeline.duration`       | Timer   | Total pipeline execution time        |
| `agent.tool.{name}.calls`      | Counter | Calls per external tool              |
| `agent.tool.{name}.errors`     | Counter | Errors per external tool             |
| `agent.tool.{name}.latency`    | Timer   | Latency per external tool call       |
| `agent.llm.tokens.input`       | Counter | Bedrock input tokens consumed        |
| `agent.llm.tokens.output`      | Counter | Bedrock output tokens consumed       |
| `agent.leads.discovered`       | Counter | Raw companies found per job          |
| `agent.leads.scored`           | Counter | Companies successfully scored        |

---

## 10. Production Readiness Checklist

| #  | Item                                             | Status |
|----|--------------------------------------------------|--------|
| 1  | All Pydantic models validate inbound requests    | [ ]    |
| 2  | Tool fallback chains tested                       | [ ]    |
| 3  | Agent pipeline handles partial failures gracefully| [ ]    |
| 4  | Progress updates sent at each pipeline stage      | [ ]    |
| 5  | Callback delivery retries implemented             | [ ]    |
| 6  | All API keys externalized to environment vars     | [ ]    |
| 7  | Structured logging with job_id correlation        | [ ]    |
| 8  | Health endpoint returns tool availability status  | [ ]    |
| 9  | Docker image builds and runs successfully         | [ ]    |
| 10 | BANT scoring produces valid 0-10 scores           | [ ]    |
| 11 | Deduplication by domain prevents duplicate leads  | [ ]    |
| 12 | Concurrent enrichment semaphore limits load        | [ ]    |
| 13 | LLM calls have timeout and retry logic            | [ ]    |
| 14 | System prompt tested with edge case ICPs          | [ ]    |
| 15 | Output format matches backend's expected schema    | [ ]    |

---

## 11. System Prompt Design (Agent-Specific)

```python
SYSTEM_PROMPT = """
You are qlGen, an expert B2B lead generation analyst. Your role is to discover,
enrich, and score companies that match an Ideal Customer Profile (ICP) using
the BANT framework.

## Your Role
You are a methodical research analyst who:
1. Interprets ICP criteria into actionable search strategies
2. Uses available tools to discover matching companies
3. Enriches company profiles with detailed firmographic data
4. Scores each company on the BANT framework with transparent reasoning

## Constraints
- ONLY use the tools provided to you. Do not fabricate company data.
- If a tool fails, try alternative tools before giving up.
- If you cannot find sufficient data to score a dimension, assign a score of 3/10
  and note "Insufficient data" in your reasoning.
- Never invent financial figures, employee counts, or funding data.
- Always provide reasoning for each BANT score dimension.
- Limit your discovery to the maxResults specified by the user.

## BANT Scoring Framework

For each company, evaluate:

**Budget (0-10):** Does this company have the financial capacity?
- Revenue indicators, funding stage, growth signals
- Score 8-10: Clear budget signals (recent funding, high revenue)
- Score 4-7: Moderate indicators
- Score 1-3: Limited or no financial data available

**Authority (0-10):** Can we reach decision makers?
- Organizational structure, identifiable C-suite/VP contacts
- Score 8-10: Key contacts identified with direct access
- Score 4-7: Company info available but contacts unclear
- Score 1-3: Minimal organizational visibility

**Need (0-10):** Does this company need our solution?
- Tech stack alignment, industry fit, stated pain points
- Score 8-10: Strong alignment with ICP tech/industry needs
- Score 4-7: Partial alignment
- Score 1-3: Weak or no alignment

**Timeline (0-10):** Is there urgency or buying signals?
- Recent job postings, tech migrations, growth signals, funding rounds
- Score 8-10: Active buying signals detected
- Score 4-7: Some growth/change indicators
- Score 1-3: No urgency signals detected

## Output Format

For each scored company, return a JSON object with:
{
  "companyName": "string",
  "domain": "string",
  "industry": "string",
  "employeeCount": number or null,
  "estimatedRevenue": number or null,
  "location": "string",
  "description": "string",
  "techStack": ["string"],
  "fundingStage": "string or null",
  "bantScore": {
    "budget": number (0-10),
    "authority": number (0-10),
    "need": number (0-10),
    "timeline": number (0-10),
    "total": number (weighted average),
    "reasoning": "Detailed explanation for each dimension score"
  }
}

## Important
- Deduplicate companies by domain before scoring.
- Apply the user-provided BANT weights to calculate the total score.
- Rank companies by total score descending.
- Be thorough but efficient — prioritize data quality over quantity.
"""
```

---

## 12. Guardrails & Safety Controls (Agent-Specific)

### 12.1 Input Guardrails

```python
class InputGuardrails:
    MAX_INDUSTRIES = 10
    MAX_GEOGRAPHIES = 20
    MAX_KEYWORDS = 15
    MAX_RESULTS_CAP = 50
    MAX_ADDITIONAL_NOTES_LENGTH = 1000

    @staticmethod
    def validate_icp(icp: ICPProfile) -> ICPProfile:
        if len(icp.industries) > InputGuardrails.MAX_INDUSTRIES:
            raise ValueError(f"Max {InputGuardrails.MAX_INDUSTRIES} industries allowed")
        if len(icp.geographies) > InputGuardrails.MAX_GEOGRAPHIES:
            raise ValueError(f"Max {InputGuardrails.MAX_GEOGRAPHIES} geographies allowed")
        if len(icp.keywords) > InputGuardrails.MAX_KEYWORDS:
            raise ValueError(f"Max {InputGuardrails.MAX_KEYWORDS} keywords allowed")
        if len(icp.additional_notes) > InputGuardrails.MAX_ADDITIONAL_NOTES_LENGTH:
            icp.additional_notes = icp.additional_notes[:InputGuardrails.MAX_ADDITIONAL_NOTES_LENGTH]
        return icp
```

### 12.2 Output Guardrails

```python
class OutputGuardrails:
    @staticmethod
    def validate_bant_score(score: BANTScore) -> BANTScore:
        """Ensure all scores are within valid range."""
        for field in ["budget", "authority", "need", "timeline"]:
            value = getattr(score, field)
            if not (0 <= value <= 10):
                setattr(score, field, max(0, min(10, value)))
        return score

    @staticmethod
    def sanitize_lead(lead: Lead) -> Lead:
        """Remove any PII that shouldn't be in the output."""
        # Strip personal email addresses (only company domains)
        # Strip phone numbers
        # Ensure no raw API responses leak through
        return lead

    @staticmethod
    def validate_reasoning(reasoning: str) -> str:
        """Ensure reasoning is substantive, not hallucinated."""
        if len(reasoning) < 20:
            return reasoning + " [Note: Limited data available for detailed reasoning]"
        return reasoning
```

### 12.3 Rate Limiting

```python
from asyncio import Semaphore
from collections import defaultdict
import time

class ToolRateLimiter:
    def __init__(self):
        self.limits = {
            "tavily": {"calls_per_minute": 50, "semaphore": Semaphore(5)},
            "hunter": {"calls_per_minute": 30, "semaphore": Semaphore(3)},
            "exa": {"calls_per_minute": 50, "semaphore": Semaphore(5)},
            "lusha": {"calls_per_minute": 30, "semaphore": Semaphore(3)},
            "apollo": {"calls_per_minute": 40, "semaphore": Semaphore(4)},
            "bedrock": {"calls_per_minute": 20, "semaphore": Semaphore(3)},
        }
        self.call_timestamps: dict[str, list[float]] = defaultdict(list)

    async def acquire(self, tool_name: str):
        config = self.limits.get(tool_name)
        if not config:
            return
        await config["semaphore"].acquire()
        # Clean old timestamps and check rate
        now = time.time()
        self.call_timestamps[tool_name] = [
            t for t in self.call_timestamps[tool_name] if now - t < 60
        ]
        if len(self.call_timestamps[tool_name]) >= config["calls_per_minute"]:
            await asyncio.sleep(2)  # Brief backoff
        self.call_timestamps[tool_name].append(now)

    def release(self, tool_name: str):
        config = self.limits.get(tool_name)
        if config:
            config["semaphore"].release()
```

---

## 13. Tool Definitions & Usage Policy (Agent-Specific)

### 13.1 Tool Registry

| Tool Name         | Provider    | Protocol | Purpose                              | Priority |
|-------------------|-------------|----------|--------------------------------------|----------|
| `tavily_search`   | Tavily      | MCP      | Web search for company discovery     | Primary  |
| `exa_search`      | Exa         | MCP      | Semantic search for companies        | Primary  |
| `duckduckgo_search`| DuckDuckGo | REST     | Fallback web search (free)           | Fallback |
| `apollo_enrich`   | Apollo.io   | MCP      | Company & contact enrichment         | Primary  |
| `lusha_enrich`    | Lusha       | REST     | Company enrichment (firmographics)   | Secondary|
| `hunter_lookup`   | Hunter      | REST     | Domain verification & email lookup   | Secondary|
| `bant_scorer`     | Internal    | LLM      | BANT score calculation via Claude    | Required |

### 13.2 Tool Schemas

```python
# Tavily Search Tool
@tool
def tavily_search(query: str, max_results: int = 10) -> list[dict]:
    """
    Search the web for companies matching a query.

    Args:
        query: Search query optimized for finding B2B companies
        max_results: Maximum number of results to return (default: 10)

    Returns:
        List of search results with title, url, and content snippet
    """
    pass

# Hunter Domain Lookup Tool
@tool
def hunter_lookup(domain: str) -> dict:
    """
    Look up company information and email patterns for a domain.

    Args:
        domain: Company website domain (e.g., 'acmecorp.com')

    Returns:
        Company info including organization name, email pattern, and contacts
    """
    pass

# Lusha Company Enrichment Tool
@tool
def lusha_enrich(company_name: str, domain: str = None) -> dict:
    """
    Enrich company data with firmographic details.

    Args:
        company_name: Name of the company
        domain: Optional domain for more precise matching

    Returns:
        Company profile with employee count, revenue, industry, location
    """
    pass

# BANT Scorer Tool (LLM-based)
@tool
def bant_score(company_profile: dict, icp_profile: dict, bant_weights: dict) -> dict:
    """
    Score a company on the BANT framework against an ICP.

    Args:
        company_profile: Enriched company data
        icp_profile: The target ICP criteria
        bant_weights: Weight allocation for each BANT dimension

    Returns:
        BANT scores (0-10 per dimension) with reasoning and weighted total
    """
    pass
```

### 13.3 Tool Usage Policy

| Rule                                  | Description                                                   |
|---------------------------------------|---------------------------------------------------------------|
| Search-first, enrich-second           | Always discover companies before enriching them                |
| Fallback on failure                   | If primary tool fails, use secondary before giving up          |
| No data fabrication                   | If a tool returns no data, score that dimension low, don't invent data |
| Deduplicate before enriching          | Remove duplicate companies (by domain) before enrichment calls |
| Concurrent but rate-limited           | Run enrichments in parallel but respect per-tool rate limits   |
| Cache enrichment results              | Don't re-enrich the same domain within one pipeline run        |
| Tool timeout                          | Individual tool calls timeout after 30 seconds                 |
| Maximum tool calls per job            | Cap at 100 total tool invocations per pipeline run             |

---

## 14. Explainability Strategy (Agent-Specific)

### 14.1 BANT Reasoning Transparency

Every scored lead includes a `reasoning` field that explains why each BANT dimension received its score. This is generated by the LLM during the scoring step.

**Reasoning Format:**
```
Budget (8/10): Recent Series B funding of $20M indicates strong financial capacity.
Annual revenue estimated at $15M with 40% YoY growth.

Authority (7/10): Company has 250 employees. LinkedIn shows VP of Engineering
and CTO profiles. Decision-making structure appears accessible.

Need (9/10): Tech stack includes AWS and Python, aligning with ICP requirements.
Job postings indicate active investment in cloud infrastructure.

Timeline (6/10): No immediate buying signals detected, but recent hiring spree
suggests growth phase that may trigger near-term purchasing decisions.

Weighted Total: 7.85/10 (weights: B=0.30, A=0.25, N=0.25, T=0.20)
```

### 14.2 Data Source Attribution

```python
class LeadWithProvenance(Lead):
    """Extended lead model with data source tracking."""
    data_sources: dict[str, list[str]] = {}
    # Example: {"employee_count": ["apollo"], "revenue": ["lusha", "exa"],
    #           "tech_stack": ["tavily_search_result"]}

    confidence_level: str  # "high", "medium", "low"
    # Based on number of corroborating sources
```

### 14.3 Score Audit Trail

Each pipeline run produces a structured audit log:

```python
audit_entry = {
    "job_id": "550e...",
    "company": "Acme Corp",
    "discovery_source": "tavily_search",
    "enrichment_sources": ["apollo", "hunter"],
    "bant_scores": {
        "budget": {"score": 8, "data_points": ["Series B $20M", "Revenue $15M"]},
        "authority": {"score": 7, "data_points": ["250 employees", "CTO identified"]},
        "need": {"score": 9, "data_points": ["AWS stack", "Python jobs posted"]},
        "timeline": {"score": 6, "data_points": ["Hiring spree Q1 2025"]},
    },
    "weights_applied": {"budget": 0.30, "authority": 0.25, "need": 0.25, "timeline": 0.20},
    "total_score": 7.85,
}
```

---

## 15. Memory Integration Strategy (Agent-Specific)

### 15.1 Pipeline Context Management

The Strands agent maintains context across the multi-step pipeline within a single job execution. This is achieved through a shared context object passed between stages.

```python
class PipelineContext:
    """Shared context across all pipeline stages for a single job."""

    def __init__(self, request: JobRequest):
        self.job_id = request.job_id
        self.icp_profile = request.icp_profile
        self.bant_weights = request.bant_weights
        self.max_results = request.max_results
        self.callback_url = request.callback_url

        # Accumulated across stages
        self.search_queries: list[str] = []
        self.raw_companies: list[dict] = []
        self.enriched_companies: list[dict] = []
        self.scored_leads: list[Lead] = []

        # Deduplication cache
        self.seen_domains: set[str] = set()

        # Tool call tracking
        self.tool_calls: list[dict] = []
        self.total_tool_calls: int = 0

    def add_company(self, company: dict) -> bool:
        """Add company if not a duplicate. Returns True if added."""
        domain = company.get("domain", "").lower().strip()
        if not domain or domain in self.seen_domains:
            return False
        self.seen_domains.add(domain)
        self.raw_companies.append(company)
        return True

    def track_tool_call(self, tool_name: str, success: bool, latency_ms: int):
        self.tool_calls.append({
            "tool": tool_name,
            "success": success,
            "latency_ms": latency_ms,
            "timestamp": datetime.utcnow().isoformat(),
        })
        self.total_tool_calls += 1
```

### 15.2 Strands Agent Conversation Management

```python
from strands import Agent

def create_agent(context: PipelineContext) -> Agent:
    """Create a Strands agent with ICP-specific context injected into the prompt."""

    dynamic_context = f"""
    ## Current Job Context
    - Job ID: {context.job_id}
    - Target Industries: {', '.join(context.icp_profile.industries)}
    - Company Size: {context.icp_profile.company_size_range['min']}-{context.icp_profile.company_size_range['max']} employees
    - Revenue Range: ${context.icp_profile.revenue_range['min']:,}-${context.icp_profile.revenue_range['max']:,}
    - Geographies: {', '.join(context.icp_profile.geographies)}
    - Tech Stack: {', '.join(context.icp_profile.tech_stack) or 'Any'}
    - Keywords: {', '.join(context.icp_profile.keywords) or 'None'}
    - Additional Notes: {context.icp_profile.additional_notes or 'None'}
    - BANT Weights: B={context.bant_weights.budget}, A={context.bant_weights.authority}, N={context.bant_weights.need}, T={context.bant_weights.timeline}
    - Max Results: {context.max_results}
    """

    agent = Agent(
        model="bedrock/anthropic.claude-sonnet-4-20250514-v1:0",
        system_prompt=SYSTEM_PROMPT + dynamic_context,
        tools=[tavily_search, exa_search, hunter_lookup, lusha_enrich,
               apollo_enrich, duckduckgo_search, bant_score],
    )

    return agent
```

### 15.3 Cross-Stage Context Flow

```
Stage 1 (ICP Interpret)    → PipelineContext.search_queries populated
         │
Stage 2 (Company Discover) → PipelineContext.raw_companies populated
         │                    PipelineContext.seen_domains tracks dedup
Stage 3 (Company Enrich)   → PipelineContext.enriched_companies populated
         │                    Enrichment data merged with discovery data
Stage 4 (BANT Score)       → PipelineContext.scored_leads populated
         │                    Scores include data from all previous stages
Stage 5 (Rank & Return)    → Final ranked list derived from scored_leads
```

The `PipelineContext` ensures no data is lost between stages and provides a single source of truth for the entire pipeline run. Each stage reads from and writes to this shared context.

---

## Appendix A: requirements.txt

```
strands-agents>=0.1.0
strands-agents-tools>=0.1.0
fastapi>=0.110.0
uvicorn>=0.29.0
httpx>=0.27.0
pydantic>=2.0.0
pydantic-settings>=2.0.0
structlog>=24.0.0
boto3>=1.34.0
python-dotenv>=1.0.0
```

## Appendix B: Docker Compose (Full Stack)

```yaml
version: '3.8'

services:
  frontend:
    build: ./frontend
    ports:
      - "3000:80"
    depends_on:
      - backend

  backend:
    build: ./backend
    ports:
      - "8080:8080"
    environment:
      - SPRING_PROFILES_ACTIVE=dev
      - AGENT_BASE_URL=http://agent:8000
      - SPRING_DATASOURCE_URL=jdbc:postgresql://postgres:5432/qlgen
      - SPRING_DATASOURCE_USERNAME=qlgen
      - SPRING_DATASOURCE_PASSWORD=${DB_PASSWORD:-qlgen_dev}
    depends_on:
      - agent
      - postgres

  agent:
    build: ./agent
    ports:
      - "8000:8000"
    env_file:
      - ./agent/.env
    environment:
      - BACKEND_CALLBACK_BASE_URL=http://backend:8080

  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: qlgen
      POSTGRES_USER: qlgen
      POSTGRES_PASSWORD: ${DB_PASSWORD:-qlgen_dev}
    volumes:
      - pgdata:/var/lib/postgresql/data
    ports:
      - "5432:5432"

volumes:
  pgdata:
```
