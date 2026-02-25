# qlGen AI Agent — Technical Documentation

## Table of Contents

1. [Overview](#1-overview)
2. [Architecture & Flow](#2-architecture--flow)
3. [Amazon Bedrock Integration](#3-amazon-bedrock-integration)
4. [Tools & Capabilities](#4-tools--capabilities)
5. [Guardrails & Safety](#5-guardrails--safety)
6. [Data Fetching & Enrichment](#6-data-fetching--enrichment)
7. [Memory & Context](#7-memory--context)
8. [Configuration & Prompts](#8-configuration--prompts)
9. [Environment & Deployment](#9-environment--deployment)

---

## 1. Overview

### Purpose

The qlGen agent is an autonomous, multi-step B2B lead generation specialist. Given a structured Ideal Customer Profile (ICP), the agent independently discovers, qualifies, enriches, and scores sales leads — producing a structured dataset of companies and decision-maker contacts without manual human intervention.

The agent solves the core problem of converting a high-level sales target description into a concrete, actionable list of qualified prospects, complete with:
- Company data (size, revenue, industry, location, tech stack)
- Decision-maker contacts (names, titles, emails, phone numbers, LinkedIn URLs)
- BANT scoring (Budget, Authority, Need, Timing — each scored 1–5, max 20) with written reasoning

### Agent Framework

| Property | Value |
|---|---|
| Framework | **AWS Strands Agents** (`strands-agents` 0.1.7) |
| LLM Provider | **Amazon Bedrock** |
| Model | **Claude Sonnet 4** (`anthropic.claude-sonnet-4-20250514` / inference profile `us.anthropic.claude-sonnet-4-20250514-v1:0`) |
| Tool Protocol | Strands `@tool` decorator (function-calling via Bedrock's tool use API) |
| Invocation Pattern | Single agent call that internally orchestrates all 4 stages |
| Output Format | Structured JSON (parsed from agent response text) |

**Strands Agents** is an AWS-native agentic framework that wraps Bedrock's Converse API with tool use support, providing a simple `Agent` class that handles the reasoning loop automatically.

---

## 2. Architecture & Flow

### High-Level Pipeline Flow

```
User (Frontend)
     │
     │  POST /api/v1/pipeline/run
     ▼
FastAPI (pipeline.py)
     │
     │  Create PipelineRun (status=pending)
     │  Register BackgroundTask
     │  Return run_id immediately (HTTP 202)
     ▼
BackgroundTask: execute_pipeline(run_id)  [pipeline_service.py]
     │
     │  1. Fetch ICP config from DB
     │  2. Mark run status = "running"
     │  3. Create Strands Agent (with 9 tools + system prompt)
     │  4. Build dynamic prompt from ICP definition
     │  5. Call agent(prompt) ──────────────────────────────────────────────┐
     │                                                                       │
     │  ◄─── Blocks until agent completes all 4 stages ─────────────────────┘
     │
     │  6. Parse JSON from agent response text
     │  7. Save companies to DB
     │  8. Save contacts to DB
     │  9. Save BANT scores to DB
     │  10. Mark run status = "completed"
     │  11. Emit SSE "completed" event
     ▼
PostgreSQL (results persisted)
     │
     ▼
Frontend SSE listener → Updates UI → User views leads
```

### Agent Internal Reasoning Loop (Strands Framework)

The Strands framework manages the agent's reasoning loop internally. It follows a standard **ReAct-style** (Reason + Act) loop:

```
AGENT LOOP (managed by Strands):
┌─────────────────────────────────────────────────┐
│                                                 │
│  1. LLM receives: system_prompt + user_prompt   │
│                                                 │
│  2. LLM responds with either:                   │
│     a) A tool call → Strands executes the tool  │
│        → Tool result appended to context        │
│        → Loop continues                         │
│     b) A final text response → Loop ends        │
│                                                 │
│  This continues for as many tool calls as the   │
│  LLM deems necessary to complete the task.      │
└─────────────────────────────────────────────────┘
```

The agent decides which tool to call based on:
1. The **stage** it is currently in (dictated by the system prompt structure)
2. The **availability** of data (e.g., if a company has no email, it calls `hunter_email_finder`)
3. The **priority order** specified in the system prompt (primary → secondary → supplementary → fallback)
4. **Rate limits or errors** from a primary tool → falls back to alternatives

### Four-Stage Execution Plan

The system prompt instructs the agent to execute exactly four stages sequentially. The agent does not "know" when to stop a stage and begin the next — it follows the stage descriptions in the system prompt as a plan.

```
┌─────────────────────────────────────────────────────────┐
│  STAGE 1: Company Discovery                             │
│  Goal: Find 15–25 companies matching the ICP           │
│  Primary:      apollo_company_search                   │
│  Secondary:    exa_search                              │
│  Supplementary: tavily_search                          │
│  Fallback:     duckduckgo_search                       │
│  Output: company list with name, website, industry,    │
│          size, revenue, tech signals, ICP match score  │
└─────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│  STAGE 2: Contact Discovery                             │
│  Goal: Find 3–5 decision-makers per company            │
│  Primary:      apollo_people_search                    │
│  Secondary:    hunter_domain_search                    │
│  Supplementary: scrape_webpage (team/about pages)      │
│  Fallback:     duckduckgo_search                       │
│  Output: contacts with name, title, email, phone,      │
│          LinkedIn URL, role category                   │
└─────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│  STAGE 3: Contact Enrichment                            │
│  Goal: Fill gaps in contact data                       │
│  Missing email:   hunter_email_finder                  │
│  Missing phone:   lusha_person_search                  │
│  Missing LinkedIn: exa_search                          │
│  Output: enrichment_status per contact                 │
│          (enriched / partial / failed)                 │
└─────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│  STAGE 4: BANT Scoring                                 │
│  Goal: Score each company 1–5 on 4 dimensions          │
│  Evidence sources: tavily_search, scrape_webpage,      │
│                    data already gathered               │
│  Output: budget/authority/need/timing score +          │
│          reasoning text + total score + summary        │
└─────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│  FINAL OUTPUT: Single JSON object                       │
│  {                                                      │
│    "companies": [ ... ],                               │
│    "summary": { ... }                                  │
│  }                                                      │
└─────────────────────────────────────────────────────────┘
```

---

## 3. Amazon Bedrock Integration

### Model Details

| Property | Value |
|---|---|
| Model Family | Anthropic Claude |
| Model Name | Claude Sonnet 4 |
| Model ID (direct) | `anthropic.claude-sonnet-4-20250514` |
| Inference Profile ID | `us.anthropic.claude-sonnet-4-20250514-v1:0` |
| API Mode | Bedrock Converse API (with tool use) |
| Region | `us-east-1` (configurable via `AWS_REGION`) |

The inference profile ID (`us.*`) enables **cross-region inference**, allowing Bedrock to route the request to whichever AWS region has available capacity for the model, reducing latency and throttling issues.

### How Bedrock API Calls are Structured

The Strands framework wraps Bedrock's **Converse API** (`bedrock-runtime:Converse`). Under the hood, each turn of the agent loop translates to a `Converse` API call with:

- `modelId`: the configured model/inference profile ID
- `system`: the system prompt (LEAD_GEN_SYSTEM_PROMPT)
- `messages`: the growing conversation history (user prompt + tool call results)
- `toolConfig`: auto-generated from the `@tool`-decorated functions (JSON Schema for each tool's parameters)

The `BedrockModel` class from `strands-agents` handles:
- Constructing the `toolConfig` from decorated Python functions
- Parsing the model's `toolUse` response blocks
- Calling the appropriate Python function and appending `toolResult` blocks

### Agent Creation

```python
from strands import Agent
from strands.models.bedrock import BedrockModel
from app.config import get_settings

settings = get_settings()

def create_lead_gen_agent() -> Agent:
    model = BedrockModel(
        model_id=settings.BEDROCK_MODEL_ID,  # e.g., "us.anthropic.claude-sonnet-4-20250514-v1:0"
        region_name=settings.AWS_REGION,     # e.g., "us-east-1"
    )

    return Agent(
        model=model,
        system_prompt=LEAD_GEN_SYSTEM_PROMPT,
        tools=[
            apollo_company_search,
            exa_search,
            tavily_search,
            duckduckgo_search,
            apollo_people_search,
            hunter_domain_search,
            hunter_email_finder,
            lusha_person_search,
            scrape_webpage,
        ],
    )
```

### Bedrock Knowledge Bases

**No Bedrock Knowledge Bases are used.** The agent retrieves all information dynamically through its tool calls. There is no pre-indexed document store or RAG layer backed by Bedrock.

### Bedrock Agents (Managed)

**No Bedrock Agents (the managed service) are used.** The orchestration is implemented directly in the application code using the Strands SDK, not via the Bedrock Agents managed service. This is a code-level agent, not a serverless Bedrock Agent.

### AWS Credentials

Credentials are resolved via the standard boto3 credential chain. In Docker Compose, they must be passed as environment variables (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, optionally `AWS_SESSION_TOKEN`). On EC2 or ECS, the instance/task IAM role is used automatically.

---

## 4. Tools & Capabilities

The agent has access to 9 tools, registered via the `@tool` decorator from the `strands-agents` library. Each tool's Python docstring serves as the tool description that the LLM reads when deciding whether to use it.

### Tool Registry

| Tool Name | Source | Purpose | Used In Stage |
|---|---|---|---|
| `apollo_company_search` | `tools/apollo_tool.py` | Search for companies in Apollo.io's database | Stage 1 |
| `exa_search` | `tools/exa_tool.py` | Semantic web search for company descriptions and LinkedIn | Stage 1, 3 |
| `tavily_search` | `tools/tavily_tool.py` | News and web search for recent signals | Stage 1, 4 |
| `duckduckgo_search` | `tools/duckduckgo_tool.py` | Free web search fallback | Any stage |
| `apollo_people_search` | `tools/apollo_tool.py` | Search for people/contacts at companies | Stage 2 |
| `hunter_domain_search` | `tools/hunter_tool.py` | Find all known emails at a company domain | Stage 2 |
| `hunter_email_finder` | `tools/hunter_tool.py` | Find a specific person's email by name + domain | Stage 3 |
| `lusha_person_search` | `tools/lusha_tool.py` | Find phone numbers for specific individuals | Stage 3 |
| `scrape_webpage` | `tools/web_scraper_tool.py` | Scrape text content from any public URL | Stage 2, 4 |

### Tool Implementation Pattern

All tools follow the same pattern:

```python
from strands import tool
import httpx
from app.config import get_settings

settings = get_settings()

@tool
def tool_name(param1: type, param2: type = default) -> dict:
    """
    Docstring — this is what the LLM reads to understand
    when and how to use this tool.
    """
    try:
        response = httpx.get/post(
            url,
            headers={"api-key": settings.API_KEY},
            params/json={...}
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        return {"error": str(e)}
```

All external HTTP calls use **`httpx`** (synchronous mode within tool functions, as the Strands tool execution is synchronous within the async pipeline service).

### Tool Parameter Schemas

The `@tool` decorator uses Python type hints and docstrings to auto-generate JSON Schema for the Bedrock tool use API. The LLM sees these schemas and fills in the parameters based on context from the ICP and previous tool results.

### Tool Details

#### `apollo_company_search`
```
Parameters:
  query (str)             — Free-text search query
  industries (list[str])  — Industry filter list
  locations (list[str])   — Location filter list
  min_employees (int)     — Minimum headcount
  max_employees (int)     — Maximum headcount
  page (int)              — Pagination page (default: 1)
  per_page (int)          — Results per page (default: 25)

Returns:
  {organizations: [{name, website_url, industry, employee_count,
                    estimated_num_employees, annual_revenue_printed,
                    city, state, country, ...}],
   pagination: {total_entries, total_pages, ...}}
```

#### `apollo_people_search`
```
Parameters:
  company_name (str)      — Target company name
  company_domain (str)    — Target company domain
  titles (list[str])      — Job title filters
  locations (list[str])   — Location filters
  page (int)              — Pagination
  per_page (int)          — Results per page (default: 10)

Returns:
  {people: [{name, title, email, linkedin_url, phone_numbers,
             organization_name, city, state, country, ...}]}
```

#### `exa_search`
```
Parameters:
  query (str)                 — Natural language search query
  num_results (int)           — Number of results (default: 10)
  use_autoprompt (bool)       — Let Exa optimize the query
  include_domains (list[str]) — Restrict results to these domains
  exclude_domains (list[str]) — Exclude these domains
  category (str)              — Content category filter

Returns:
  {results: [{url, title, text, author, published_date, score}]}
```

#### `hunter_domain_search`
```
Parameters:
  domain (str)    — Company domain (e.g., "acme.com")
  limit (int)     — Max emails to return (default: 10)

Returns:
  {data: {emails: [{value, type, confidence, first_name, last_name,
                    position, department, linkedin}]}}
```

#### `hunter_email_finder`
```
Parameters:
  domain (str)      — Company domain
  first_name (str)  — Person's first name
  last_name (str)   — Person's last name

Returns:
  {data: {email, confidence, sources: [{uri, extracted_on, ...}]}}
```

#### `lusha_person_search`
```
Parameters:
  first_name (str)      — Person's first name
  last_name (str)       — Person's last name
  company_name (str)    — Optional company name
  company_domain (str)  — Optional company domain

Returns:
  {phone: [{number, type}], email: [{email}],
   social_profiles: [{network, url}]}
```

#### `tavily_search`
```
Parameters:
  query (str)           — Search query
  max_results (int)     — Max results (default: 5)
  search_depth (str)    — "basic" or "advanced"

Returns:
  {results: [{title, url, content, score}]}
```

#### `duckduckgo_search`
```
Parameters:
  query (str)       — Search query
  max_results (int) — Max results (default: 10)

Returns:
  [{title, href, body}]
```

#### `scrape_webpage`
```
Parameters:
  url (str)  — Full URL to scrape

Returns:
  {url, title, content (≤5000 chars), links: [all href values]}
  OR
  {error: "Error message"} on failure
```

---

## 5. Guardrails & Safety

### AWS Bedrock Guardrails

**No AWS Bedrock Guardrails are configured.** The agent calls Bedrock directly without attaching a guardrail ID to the Converse API calls.

### Custom Safety Layers

The application has minimal custom safety measures:

**Input validation (Pydantic):**
- All API request bodies are validated through Pydantic schemas before reaching the agent.
- Numeric fields (e.g., `max_companies`, employee counts, revenue ranges) have type constraints.
- UUID parameters are validated by FastAPI before DB lookups.

**Tool-level error handling:**
- Every tool function wraps API calls in `try/except` and returns a structured error dict instead of raising exceptions. This prevents a single failed API call from crashing the entire pipeline.
- The scraper caps content at 5000 characters to avoid excessive token consumption.

**Agent output parsing:**
- `parse_json_from_agent_result()` in `pipeline_service.py` attempts to extract and validate the JSON output from the agent's response text using regex pattern matching and `json.loads()`. If parsing fails, the pipeline is marked as `failed` with an error log.

### What is NOT Addressed

| Risk | Status |
|---|---|
| Prompt injection via tool results | Not mitigated — scraped web content or API responses could contain adversarial instructions |
| Hallucinated contact data (fake emails/phones) | Not validated — data is saved as-is from agent output |
| PII handling | No special PII policies applied |
| Rate limiting | No application-level rate limiting on API endpoints |
| Agent cost runaway | No maximum token limit enforced beyond model defaults |
| Off-topic or harmful output | No content filters applied |

For a production deployment handling real sales data, adding input sanitization for scraped web content, Bedrock Guardrails for PII/content filtering, and rate limiting middleware would be advisable.

---

## 6. Data Fetching & Enrichment

### Full Data Flow

```
User Input (ICP Definition)
         │
         ▼
prompt_builder.py → builds structured prompt from ICP fields
         │
         ▼
lead_gen_agent.py → creates Agent with system_prompt + 9 tools
         │
         ▼ agent(prompt)
         │
┌────────────────────────────────────────────────────────────┐
│                    STAGE 1: Company Discovery              │
│                                                            │
│  apollo_company_search(industries, locations, size)        │
│    → Apollo.io database → structured company records       │
│                                                            │
│  exa_search("companies in [industry] with [tech signals]") │
│    → Semantic web search → company descriptions + URLs     │
│                                                            │
│  tavily_search("top [industry] companies [year]")          │
│    → Recent news/lists → additional companies              │
│                                                            │
│  duckduckgo_search(...) [if above fail/insufficient]       │
│                                                            │
│  AGENT REASONING: Filter to best 15-25 matches,           │
│  score each 1-10 against ICP, discard <5                   │
└────────────────────────────────────────────────────────────┘
         │ companies[]
         ▼
┌────────────────────────────────────────────────────────────┐
│                    STAGE 2: Contact Discovery              │
│                                                            │
│  For each company:                                         │
│    apollo_people_search(company_domain, titles=[...])      │
│      → Contact list with name, title, email, phone        │
│                                                            │
│    hunter_domain_search(domain)                            │
│      → Email list with confidence scores                  │
│                                                            │
│    scrape_webpage(company_url + "/team" or "/about")       │
│      → Team page text → extract names/titles              │
│                                                            │
│  AGENT REASONING: Select top 3-5 decision-makers          │
│  by role relevance (CTO > VP > Director > Manager)        │
└────────────────────────────────────────────────────────────┘
         │ contacts[] per company
         ▼
┌────────────────────────────────────────────────────────────┐
│                    STAGE 3: Enrichment                     │
│                                                            │
│  For each contact with missing email:                      │
│    hunter_email_finder(domain, first_name, last_name)      │
│                                                            │
│  For each contact with missing phone:                      │
│    lusha_person_search(name, company)                      │
│                                                            │
│  For each contact with missing LinkedIn:                   │
│    exa_search("[name] [company] LinkedIn")                 │
│                                                            │
│  AGENT ASSIGNS enrichment_status:                         │
│    "enriched" — all fields found                          │
│    "partial"  — some fields found                         │
│    "failed"   — no additional data found                  │
└────────────────────────────────────────────────────────────┘
         │ enriched contacts[]
         ▼
┌────────────────────────────────────────────────────────────┐
│                    STAGE 4: BANT Scoring                   │
│                                                            │
│  For each company:                                         │
│    tavily_search("[company] funding revenue growth 2024")  │
│      → Recent financial signals → Budget evidence         │
│                                                            │
│    scrape_webpage(company_url)                             │
│      → Website copy → Need/Timing evidence                │
│                                                            │
│  AGENT REASONING:                                          │
│    Budget  (1-5): Revenue size, tech spending signals     │
│    Authority (1-5): Seniority of contacts found           │
│    Need (1-5): Pain/goal alignment with ICP offering      │
│    Timing (1-5): Growth triggers, initiatives, urgency    │
│                                                            │
│    total_score = budget + authority + need + timing       │
│    (max 20)                                               │
└────────────────────────────────────────────────────────────┘
         │ JSON: {companies[], summary{}}
         ▼
pipeline_service.py
  → parse_json_from_agent_result()
  → Save to PostgreSQL (companies, contacts, bant_scores tables)
  → Emit SSE "completed" event
```

### Data Sources Priority

| Stage | Primary | Secondary | Supplementary | Fallback |
|---|---|---|---|---|
| 1 - Company Discovery | Apollo.io | Exa | Tavily | DuckDuckGo |
| 2 - Contact Discovery | Apollo.io People | Hunter Domain | Web Scraper | DuckDuckGo |
| 3 - Enrichment (email) | Hunter Email Finder | — | — | — |
| 3 - Enrichment (phone) | Lusha | — | — | — |
| 3 - Enrichment (LinkedIn) | Exa | — | — | — |
| 4 - BANT Evidence | Tavily | Web Scraper | Existing data | — |

---

## 7. Memory & Context

### Short-Term Memory (Within a Pipeline Run)

The agent maintains a **growing conversation context** within a single pipeline run invocation. All tool calls and their results are appended to the message history passed back to the model on each turn. This means:

- Company data discovered in Stage 1 is in context when doing Stage 2 contact discovery.
- Contact data from Stage 2 is in context when doing Stage 3 enrichment.
- All gathered data is in context when doing Stage 4 BANT scoring.

This is the standard Converse API multi-turn pattern: the message list grows with each tool call and response.

### Long-Term Memory

**There is no long-term memory.** Each pipeline run starts with a fresh agent instance. The agent has no access to data from previous pipeline runs.

Historical data from past runs does exist in the PostgreSQL database, but the agent does not query it. There is no vector store, embeddings layer, or retrieval mechanism connecting past runs to new agent invocations.

### Session / Conversation History

Each pipeline run creates a new `Agent` instance via `create_lead_gen_agent()`. The Strands `Agent` object accumulates tool call history internally for the duration of that single `.invoke()` call. When the call completes, the history is discarded. The agent does not persist state between runs.

### Vector Store / RAG

**No vector store or RAG layer is implemented.** Despite `pgvector` being installed as a PostgreSQL extension and listed as a Python dependency, no vector embeddings are created, stored, or queried anywhere in the codebase. This appears to be infrastructure for a planned future feature.

---

## 8. Configuration & Prompts

### System Prompt — `LEAD_GEN_SYSTEM_PROMPT`

Defined as a module-level constant in `app/agent/lead_gen_agent.py`. It is a large, detailed plain-English prompt that:

1. **Establishes the agent's role:** "You are an expert B2B lead generation specialist."
2. **Defines the four stages** with explicit instructions for each, including which tools to use in which order and what data to collect.
3. **Specifies tool priority** for each stage (Primary → Secondary → Supplementary → Fallback).
4. **Defines qualification criteria:** Discard companies with ICP match score < 5.
5. **Specifies contact prioritization:** Role relevance hierarchy (CTO > VP Engineering > Director > Manager > etc.).
6. **Defines enrichment status values:** `"enriched"`, `"partial"`, `"failed"`.
7. **Defines BANT scoring rubric:** What each score (1–5) means for each dimension, and what types of evidence to gather.
8. **Mandates the exact output format:** A single JSON object with `companies[]` and `summary{}` fields, with specific field names for each nested object.

The system prompt is **hardcoded** in the Python source file. It is not stored in a database, S3, or external configuration store.

### Dynamic Prompt — `build_pipeline_prompt()`

Defined in `app/agent/prompt_builder.py`. This function takes the ICP config JSON and pipeline options and produces a structured Markdown prompt that is passed as the **user message** to the agent.

The prompt covers all 8 ICP dimensions:

```markdown
## TARGET OFFERING
- [list of service/product areas from ICP]

## TARGET REGIONS
Countries: [list of countries]
Priority Areas: [list of priority sub-regions]

## INDUSTRY TYPES
- [Vertical: Sub-Vertical] (for each entry)

## COMPANY SIZE
- Employees: [min] – [max]
- Revenue: [currency] [min] – [max]

## TECHNOLOGY MATURITY
Positive signals: [list]
Negative signals (disqualifiers): [list]

## INFRASTRUCTURE READINESS
[list of readiness indicators]

## DIGITAL TRANSFORMATION DRIVERS
Growth Triggers: [list]
Operational Pains: [list]
Competitive Pressures: [list]
Strategic Initiatives: [list]

## LEADERSHIP TRAITS
Target Roles: [list]
Behavioral Traits: [list]

---
Execute all 4 stages now. Max companies: [N]. Max contacts per company: [M].
Return a single JSON object with the full results.
```

The user prompt is dynamically constructed at runtime from the stored ICP config, ensuring the agent always uses the exact, current ICP definition.

### Model Parameters

The `BedrockModel` is instantiated with only `model_id` and `region_name`. No explicit generation parameters are passed, meaning the model uses its **default values**:

| Parameter | Value |
|---|---|
| Temperature | Default (determined by Bedrock/Claude defaults) |
| Max tokens | Default (model maximum) |
| Top-p | Default |
| Top-k | Default |
| Stop sequences | None configured |

> **Note:** For a lead generation task requiring consistent, structured JSON output, it would be advisable to set a low temperature (e.g., `0.1–0.3`) to reduce variability, and a high `max_tokens` value (e.g., `8192–16384`) to ensure the agent can complete the full JSON output for 20+ companies. These are currently not configured.

### Prompt Storage

| Component | Storage Location | Mutable at Runtime? |
|---|---|---|
| System prompt | Hardcoded in `lead_gen_agent.py` | No (requires code deploy) |
| User prompt template | Hardcoded in `prompt_builder.py` | No (requires code deploy) |
| ICP data (fills the prompt) | PostgreSQL `icp_configs.config_json` | Yes (editable by user) |

---

## 9. Environment & Deployment

### Environment Variables Required by the Agent

| Variable | Purpose | Required? |
|---|---|---|
| `AWS_REGION` | Bedrock region for Claude model | Yes |
| `BEDROCK_MODEL_ID` | Bedrock model or inference profile ID | Yes |
| `AWS_ACCESS_KEY_ID` | AWS auth (if not using IAM role) | Situational |
| `AWS_SECRET_ACCESS_KEY` | AWS auth (if not using IAM role) | Situational |
| `AWS_SESSION_TOKEN` | AWS auth (for temporary credentials / SSO) | Situational |
| `APOLLO_API_KEY` | Apollo.io tool | Yes (for production) |
| `EXA_API_KEY` | Exa tool | Yes (for production) |
| `HUNTER_API_KEY` | Hunter.io tools | Yes (for production) |
| `LUSHA_API_KEY` | Lusha tool | Yes (for production) |
| `TAVILY_API_KEY` | Tavily tool | Yes (for production) |

### Deployment

The agent runs **in-process** within the FastAPI backend service. There is no separate agent microservice. When a pipeline is triggered, the backend's BackgroundTask executor runs the agent function in the same Python process.

```
Docker Container: backend
  └── Uvicorn (ASGI server)
        └── FastAPI app
              └── BackgroundTask: execute_pipeline()
                    └── Strands Agent (Claude via Bedrock)
                          └── Tool calls (httpx HTTP requests to external APIs)
```

### Scalability Considerations

| Concern | Current Behavior | Recommendation |
|---|---|---|
| Concurrent pipelines | Multiple BackgroundTasks run in the same process | Offload to Celery/SQS + dedicated workers |
| Agent execution time | A full 4-stage run can take 2–10 minutes depending on API latency | Add timeout handling; stream partial results |
| SSE state | Stored in-memory dict; lost on restart | Use Redis for SSE event storage |
| API rate limits | No retry logic or backoff in tool implementations | Add `tenacity` retry decorators |
| Token limits | Long multi-company JSON output may exceed model context | Chunk outputs or reduce max_companies |
| Cost | Each pipeline run makes many Bedrock + 5 paid API calls | Implement caching for repeated company lookups |

### Monitoring & Observability

**No dedicated monitoring is implemented.** Pipeline execution errors are caught and stored in `PipelineRun.error_log`. There is no:
- Logging to CloudWatch or any structured log aggregator
- Metrics collection (Prometheus, CloudWatch Metrics)
- Distributed tracing (X-Ray, OpenTelemetry)
- Bedrock invocation logging or cost tracking

For production readiness, adding structured logging with `structlog` or Python's `logging` module, plus CloudWatch integration, is recommended.
