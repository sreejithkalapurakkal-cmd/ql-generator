# qlGen — BANT Scoring & Tools Reference

## Table of Contents

1. [BANT Scoring — Overview](#1-bant-scoring--overview)
2. [How BANT Scoring Works End-to-End](#2-how-bant-scoring-works-end-to-end)
3. [BANT Dimensions & Scoring Rubric](#3-bant-dimensions--scoring-rubric)
4. [BANT Data Flow](#4-bant-data-flow)
5. [BANT in the Database](#5-bant-in-the-database)
6. [BANT on the Frontend](#6-bant-on-the-frontend)
7. [Tools — Overview](#7-tools--overview)
8. [Tool-by-Tool Reference](#8-tool-by-tool-reference)
9. [MCP Servers vs Direct API Calls](#9-mcp-servers-vs-direct-api-calls)
10. [Tool Usage by Pipeline Stage](#10-tool-usage-by-pipeline-stage)
11. [Tool Infrastructure (Shared Client)](#11-tool-infrastructure-shared-client)

---

## 1. BANT Scoring — Overview

**BANT** is a B2B sales qualification framework used to evaluate how likely a prospect company is to buy. It stands for:

| Letter | Dimension | Question It Answers |
|---|---|---|
| **B** | **Budget** | Does this company have the financial capacity to buy? |
| **A** | **Authority** | Have we found the person who can actually make the purchasing decision? |
| **N** | **Need** | Does this company have a genuine problem that our offering solves? |
| **T** | **Timing** | Is now the right time — are they actively looking or about to be? |

In qlGen, BANT scoring is performed **automatically by the AI agent** (Claude Sonnet 4 via Amazon Bedrock) at the end of every pipeline run. It is not a manual process or a rule-based formula — the agent reads all evidence gathered during company and contact discovery, then reasons about each dimension independently and assigns a score with written justification.

Each dimension is scored **1–5**, giving a **maximum total of 20**. The total is then used to classify the lead into a tier.

---

## 2. How BANT Scoring Works End-to-End

### Step 1 — Agent executes Stages 1–3 first

Before any BANT scoring happens, the agent must complete:
- **Stage 1 (Company Discovery):** Collects company name, website, industry, size, revenue estimate, tech stack signals.
- **Stage 2 (Contact Discovery):** Finds 3–5 decision-makers per company with their titles, emails, phone numbers, and LinkedIn URLs.
- **Stage 3 (Enrichment):** Fills in any missing contact fields.

All of this data is accumulated in the agent's conversation context before scoring begins. The agent does **not** need to call additional tools for most companies — it scores based on what it already knows.

### Step 2 — Stage 4: BANT Scoring instruction

The system prompt instructs the agent in Stage 4:

```
STAGE 4: BANT SCORING
Score each company 1-5 on Budget, Authority, Need, Timing (max total: 20).
Use data already gathered. Only call tavily_search or scrape_webpage if evidence is thin.
Each score MUST cite specific evidence. No assumptions.
```

Key rules enforced by the prompt:
- **Reuse existing data first** — don't make unnecessary tool calls
- **Only fetch more evidence if it's thin** — call `tavily_search` (for funding/news) or `scrape_webpage` (for company content) as needed
- **No assumptions** — every score must cite a concrete fact from the research
- **No fabrication** — if data is insufficient, score conservatively

### Step 3 — Evidence sources used for each dimension

| Dimension | Primary Evidence Sources |
|---|---|
| Budget | Revenue estimate (from Apollo/Exa), funding rounds (Tavily news), job postings mentioning budget, tech stack cost signals |
| Authority | Contact titles found in Stages 2–3, seniority level, decision-making scope of their role |
| Need | ICP alignment: operational pains, tech signals, strategic initiatives in the ICP vs what the agent found about the company |
| Timing | Recent funding announcements (Tavily), job postings for relevant roles, replatforming signals, press releases, stated transformation initiatives |

### Step 4 — Agent produces structured JSON output

For each company, the agent outputs a `bant_score` block inside the JSON response:

```json
"bant_score": {
  "budget_score": 4,
  "budget_reason": "Revenue ~$50M estimated via Apollo. Series B ($12M) raised Q1 2025 per Tavily results, indicating active tech investment.",
  "authority_score": 5,
  "authority_reason": "CTO Jane Doe identified via Apollo with direct ownership of digital infrastructure budget.",
  "need_score": 4,
  "need_reason": "Job postings reference 'legacy Magento migration' and 'headless commerce'. Two ICP pain points (platform scalability, slow time-to-market) clearly present.",
  "timing_score": 3,
  "timing_reason": "Growing 25% YoY per Exa results, but no public replatforming timeline announced yet. Likely 6–12 month horizon.",
  "total_score": 16,
  "overall_summary": "Strong prospect. Budget and authority are clear. Need is well evidenced by job postings. Timing is near-term but not urgent."
}
```

### Step 5 — Backend parses and saves the scores

`pipeline_service.py` extracts the JSON from the agent's response text and saves each `bant_score` block as a `BANTScore` database record linked to its company:

```python
# From pipeline_service.py
bant = BANTScore(
    company_id=company.id,
    budget_score=bant_data.get("budget_score"),
    budget_reason=bant_data.get("budget_reason"),
    authority_score=bant_data.get("authority_score"),
    authority_reason=bant_data.get("authority_reason"),
    need_score=bant_data.get("need_score"),
    need_reason=bant_data.get("need_reason"),
    timing_score=bant_data.get("timing_score"),
    timing_reason=bant_data.get("timing_reason"),
    total_score=bant_data.get("total_score"),
    overall_summary=bant_data.get("overall_summary"),
)
```

All BANT records for a run are bulk-inserted in a single `db.add_all()` + `commit()` call.

---

## 3. BANT Dimensions & Scoring Rubric

### Budget (B) — Financial Capacity

Measures whether the company has the money and willingness to spend on the type of solution being offered.

| Score | Meaning | Typical Evidence |
|---|---|---|
| **5** | Revenue exceeds the ICP's upper range; clear, active tech investment signals | Recent funding round, large headcount in engineering, AWS/cloud spend mentioned, multiple SaaS tools in tech stack |
| **4** | Revenue in the upper half of the ICP range; some budget indicators present | Mid-size tech team, some SaaS tools, moderate growth signals |
| **3** | Revenue within the ICP range; no specific budget signals available | Company size matches ICP but no financial signal either way |
| **2** | Revenue in the lower half of the ICP range; budget is unclear | Smaller team, limited public information on tech spending |
| **1** | Revenue below the ICP minimum; likely budget-constrained | Very small team, no tech spend signals, bootstrapped signals |

### Authority (A) — Decision-Making Power

Measures whether the contacts found have the seniority and function to actually approve a purchase.

| Score | Meaning | Typical Evidence |
|---|---|---|
| **5** | C-suite contact with direct ownership of the relevant budget | CTO, CDO, CEO (small company), COO with tech ownership — contact identified and verified |
| **4** | VP-level contact in a directly relevant function | VP Engineering, VP Ecommerce, VP Digital, VP Technology |
| **3** | Director-level contact in a relevant function | Director of Engineering, Director of Digital, Head of IT |
| **2** | Manager-level or an adjacent/indirect function | Engineering Manager, Product Manager, IT Manager |
| **1** | No relevant decision-maker found at all | Only generic contacts found, or contacts in unrelated functions |

### Need (N) — Problem-Solution Alignment

Measures how clearly the company's situation aligns with what the ICP's offering solves.

| Score | Meaning | Typical Evidence |
|---|---|---|
| **5** | 3 or more strong, specific signals matching the ICP's pain points and transformation drivers | Job postings naming the pain, press releases about a relevant initiative, tech stack showing legacy systems being replaced |
| **4** | 2 concrete matching signals | Two of: legacy platform, relevant job posting, growth friction, stated initiative |
| **3** | 1 matching signal or general industry alignment | Company is in the right industry and size but specific pain is inferred, not confirmed |
| **2** | Weak alignment; need is speculative | Company could have the problem but no evidence it does |
| **1** | No discernible need | Company's tech stack or strategy suggests no alignment with the offering |

### Timing (T) — Readiness to Act

Measures how urgently and actively the company appears to be looking for a solution.

| Score | Meaning | Typical Evidence |
|---|---|---|
| **5** | Actively in evaluation mode right now | Public RFP, vendor evaluation mentioned on job posting, active hiring for the relevant role |
| **4** | Strong near-term indicators | Recent funding (last 6 months) specifically for tech/digital, stated transformation timeline in press |
| **3** | General growth signals suggesting eventual near-term action | Growing 20%+ YoY, expanding into new markets, general tech hiring |
| **2** | No timing signals but profile suggests eventual need | Right profile but no urgency indicators |
| **1** | Actively deprioritizing or just completed a similar project | Recent acquisition, just launched a new platform, budget freeze signals |

### Total Score & Lead Tiers

```
total_score = budget_score + authority_score + need_score + timing_score
```

| Total Score | Lead Tier | Frontend Label | UI Color |
|---|---|---|---|
| 16 – 20 | Hot lead | 🟢 Hot | Green |
| 12 – 15 | Warm lead | 🟡 Warm | Gold |
| 9 – 11 | Cool lead | 🔵 Cool | Blue |
| 0 – 8 | Cold lead | 🔴 Cold | Red |

---

## 4. BANT Data Flow

```
ICP Config (user-defined pains, drivers, roles, size)
        │
        ▼
prompt_builder.py  ─── builds dynamic user prompt ───────────────────────────────────┐
                                                                                      │
        ▼                                                                             │
lead_gen_agent.py  ─── LEAD_GEN_SYSTEM_PROMPT (stage instructions + output schema) ──┤
                                                                                      │
        ▼                                                                             ▼
AWS Bedrock (Claude Sonnet 4)  ◄──── Full context: ICP + all tool results ────────────┘
        │
        │  Stage 1: discovers companies via Apollo, Exa, Tavily, DuckDuckGo
        │  Stage 2: discovers contacts via Apollo, Hunter, Scraper
        │  Stage 3: enriches missing fields via Hunter, Lusha, Exa
        │
        ▼
  Stage 4: BANT Scoring
        │
        ├── Uses data already in context (revenue, contacts, tech signals)
        │
        ├── [if evidence thin] → tavily_search("company name funding news 2025")
        │
        ├── [if evidence thin] → scrape_webpage("company.com/about")
        │
        └── Agent reasons per company:
               Budget:    revenue + funding + tech spend signals  → score 1-5 + reason
               Authority: contact seniority + role function       → score 1-5 + reason
               Need:      ICP pains vs company reality            → score 1-5 + reason
               Timing:    news + job posts + growth signals       → score 1-5 + reason
               Total:     sum(4 scores)
               Summary:   narrative paragraph
        │
        ▼
  Agent returns single JSON blob with bant_score per company
        │
        ▼
  pipeline_service.py → parse_json_from_agent_result()
        │
        ▼
  BANTScore ORM objects → db.add_all() → single db.commit()
        │
        ▼
  bant_scores table (PostgreSQL)
        │
        ▼
  GET /api/v1/leads/{run_id}/companies  ←── BANTScoreResponse schema
        │
        ▼
  Frontend LeadsPage
        ├── total_score shown as colored tag per row
        ├── Expandable row: all 4 scores + reasons + overall_summary
        ├── Filter: min_bant_score query param
        ├── Sort: by bant_score (default, descending)
        └── Export: BANT Score column in XLSX and CSV
```

---

## 5. BANT in the Database

### Table: `bant_scores`

One record per company, per pipeline run. Linked to `companies` via `company_id`.

```sql
CREATE TABLE bant_scores (
    id               UUID PRIMARY KEY,
    company_id       UUID REFERENCES companies(id),  -- always set
    contact_id       UUID REFERENCES contacts(id),   -- always NULL (reserved for future)
    budget_score     INTEGER,    -- 1-5
    budget_reason    TEXT,
    authority_score  INTEGER,    -- 1-5
    authority_reason TEXT,
    need_score       INTEGER,    -- 1-5
    need_reason      TEXT,
    timing_score     INTEGER,    -- 1-5
    timing_reason    TEXT,
    total_score      INTEGER,    -- sum of all 4, max 20
    overall_summary  TEXT,
    created_at       TIMESTAMPTZ DEFAULT now()
);
```

**ORM relationship** (defined in `company.py`):
```python
bant_score = relationship(
    "BANTScore",
    back_populates="company",
    uselist=False,  # one-to-one
    primaryjoin="and_(Company.id==BANTScore.company_id, BANTScore.contact_id==None)",
    cascade="all, delete-orphan",
)
```

The `primaryjoin` condition (`contact_id == None`) ensures the one-to-one relationship works correctly even though `contact_id` exists as a column — it's reserved for future per-contact scoring.

### Accessing BANT in queries

The `leads.py` API uses `selectinload` to eagerly load BANT scores alongside companies in a single query:

```python
query = (
    select(Company)
    .where(Company.pipeline_run_id == run_id)
    .options(selectinload(Company.contacts), selectinload(Company.bant_score))
)
```

Filtering and sorting happens in Python after the query:
```python
# Filter
if min_bant_score is not None:
    response = [c for c in response if c.bant_score and c.bant_score.total_score >= min_bant_score]

# Sort (default: descending by total_score)
response.sort(
    key=lambda c: (c.bant_score.total_score if c.bant_score else 0),
    reverse=True,
)
```

---

## 6. BANT on the Frontend

### Leads Table (`LeadsPage.tsx`)

Each row in the leads table shows the `total_score` as a colored badge:

| Condition | Badge Label | Colour |
|---|---|---|
| `total_score >= 16` | Hot | Green |
| `total_score >= 12` | Warm | Gold |
| `total_score >= 9` | Cool | Blue |
| `total_score < 9` | Cold | Red |

### Expandable Row

Clicking the expand arrow on a row opens the full BANT breakdown:
- Budget score (n/5) + reason text
- Authority score (n/5) + reason text
- Need score (n/5) + reason text
- Timing score (n/5) + reason text
- Overall summary paragraph

### Statistics Card

The leads page header shows:
- **Avg BANT Score** — average of all `total_score` values for the run
- **Hot leads count** — companies where `total_score >= 16`

### Export (XLSX / CSV)

Column 10 in both export formats is **BANT Score** (`total_score` integer, or `"N/A"` if not scored).

---

## 7. Tools — Overview

qlGen uses **9 tools** registered with the Strands agent. They are implemented as **Python functions decorated with `@tool`** from the `strands-agents` library.

### Quick Reference

| # | Tool Name | Service / Library | Type | Paid? | Used In Stage |
|---|---|---|---|---|---|
| 1 | `apollo_company_search` | Apollo.io REST API | Direct API | ✅ Yes | Stage 1 |
| 2 | `apollo_people_search` | Apollo.io REST API | Direct API | ✅ Yes | Stage 2 |
| 3 | `exa_search` | Exa AI REST API | Direct API | ✅ Yes | Stage 1, 3 |
| 4 | `tavily_search` | Tavily REST API | Direct API | ✅ Yes | Stage 1, 4 |
| 5 | `hunter_domain_search` | Hunter.io REST API | Direct API | ✅ Yes | Stage 2 |
| 6 | `hunter_email_finder` | Hunter.io REST API | Direct API | ✅ Yes | Stage 3 |
| 7 | `lusha_person_search` | Lusha REST API | Direct API | ✅ Yes | Stage 3 |
| 8 | `duckduckgo_search` | DuckDuckGo (library) | Python Library | 🆓 Free | Any (fallback) |
| 9 | `scrape_webpage` | Any website (httpx + BeautifulSoup) | HTTP + HTML parser | 🆓 Free | Stage 2, 4 |

**Total: 9 tools — 7 paid REST APIs + 1 free search library + 1 web scraper**

---

## 8. Tool-by-Tool Reference

### Tool 1 — `apollo_company_search`

| Property | Value |
|---|---|
| **File** | `app/tools/apollo_tool.py` |
| **Service** | Apollo.io |
| **Endpoint** | `POST https://api.apollo.io/v1/mixed_companies/search` |
| **Auth** | `api_key` field in the POST body |
| **HTTP Client** | Fast client (10s timeout) |
| **Caching** | Yes — keyed on `(query, industries, locations, min_emp, max_emp, page)` |
| **Retry** | Yes — 2 retries on timeout / 429 / 5xx |
| **Used In** | Stage 1: Company Discovery (primary source) |

**What it does:** Searches Apollo's structured B2B company database using keyword tags, industry filters, location filters, and employee count ranges. Returns a list of matching organizations with name, website, industry, headcount, revenue estimate, and location.

**Parameters the agent passes:**
```
query           — e.g., "ecommerce platform fashion retail"
industries      — e.g., ["Retail", "Fashion"]
locations       — e.g., ["United States", "United Kingdom"]
min_employees   — e.g., 50
max_employees   — e.g., 1500
page, per_page  — pagination (default: page 1, 25 per page)
```

---

### Tool 2 — `apollo_people_search`

| Property | Value |
|---|---|
| **File** | `app/tools/apollo_tool.py` |
| **Service** | Apollo.io |
| **Endpoint** | `POST https://api.apollo.io/v1/mixed_people/search` |
| **Auth** | `api_key` field in the POST body |
| **HTTP Client** | Fast client (10s timeout) |
| **Caching** | Yes — keyed on `(company_name, company_domain, titles, page)` |
| **Retry** | Yes — 2 retries on timeout / 429 / 5xx |
| **Used In** | Stage 2: Contact Discovery (primary source) |

**What it does:** Searches Apollo's people database to find contacts at a specific company. Filters by job title, company domain, and location. Returns name, title, email (if available), LinkedIn URL, phone, and company.

**Parameters the agent passes:**
```
company_domain  — e.g., "acme.com"
titles          — e.g., ["CTO", "VP Engineering", "VP Technology", "Director of Engineering"]
per_page        — 10 (default)
```

---

### Tool 3 — `exa_search`

| Property | Value |
|---|---|
| **File** | `app/tools/exa_tool.py` |
| **Service** | Exa AI |
| **Endpoint** | `POST https://api.exa.ai/search` |
| **Auth** | `x-api-key` request header |
| **HTTP Client** | Slow client (20s timeout) |
| **Caching** | Yes — keyed on `(query, num_results, include_domains, category)` |
| **Retry** | Yes — 2 retries |
| **Used In** | Stage 1 (company discovery), Stage 3 (LinkedIn enrichment) |

**What it does:** Neural semantic search. Unlike keyword search, Exa understands the meaning of the query and returns pages that semantically match. Returns URL, title, text snippet (capped at 1000 characters), author, and publish date.

**Two distinct use cases:**
1. **Stage 1:** Finding companies by qualitative description — e.g., *"midsize ecommerce companies using Shopify Plus in California with omnichannel challenges"*
2. **Stage 3:** Finding LinkedIn profiles — e.g., *"Jane Doe Acme Corp LinkedIn profile"* with `include_domains: ["linkedin.com"]`

---

### Tool 4 — `tavily_search`

| Property | Value |
|---|---|
| **File** | `app/tools/tavily_tool.py` |
| **Service** | Tavily |
| **Endpoint** | `POST https://api.tavily.com/search` |
| **Auth** | `api_key` field in the POST body |
| **HTTP Client** | Slow client (20s timeout) |
| **Caching** | Yes — keyed on `(query, max_results, search_depth)` |
| **Retry** | Yes — 2 retries |
| **Used In** | Stage 1 (news-based discovery), Stage 4 (BANT evidence) |

**What it does:** A web search API optimised for AI applications. Returns clean, structured results from real-time web sources (news, blogs, press releases). Default `search_depth` is `"basic"` for speed; `"advanced"` is available but slower.

**Two distinct use cases:**
1. **Stage 1:** Finding companies via recent news — e.g., *"Series B funded ecommerce companies 2025 fashion retail"*
2. **Stage 4 (BANT):** Gathering timing evidence — e.g., *"Acme Corp funding round digital transformation 2025"*

---

### Tool 5 — `hunter_domain_search`

| Property | Value |
|---|---|
| **File** | `app/tools/hunter_tool.py` |
| **Service** | Hunter.io |
| **Endpoint** | `GET https://api.hunter.io/v2/domain-search` |
| **Auth** | `api_key` query parameter |
| **HTTP Client** | Fast client (10s timeout) |
| **Caching** | Yes — keyed on `(domain, limit)` |
| **Retry** | Yes — 2 retries |
| **Used In** | Stage 2: Contact Discovery (secondary source) |

**What it does:** Given a company domain (e.g., `acme.com`), returns all email addresses Hunter has indexed for that domain, along with the person's name, job title, department, confidence score, and LinkedIn URL if available.

**Why it's useful:** Apollo may not return email addresses for all contacts. Hunter fills the gap using domain-based email pattern detection (e.g., `{first}.{last}@domain.com`).

---

### Tool 6 — `hunter_email_finder`

| Property | Value |
|---|---|
| **File** | `app/tools/hunter_tool.py` |
| **Service** | Hunter.io |
| **Endpoint** | `GET https://api.hunter.io/v2/email-finder` |
| **Auth** | `api_key` query parameter |
| **HTTP Client** | Fast client (10s timeout) |
| **Caching** | Yes — keyed on `(domain, first_name, last_name)` |
| **Retry** | Yes — 2 retries |
| **Used In** | Stage 3: Enrichment (for contacts missing an email) |

**What it does:** Given a domain, first name, and last name, Hunter predicts and verifies the most likely email address for that specific person. Returns the predicted email + confidence score (0–100) + verification sources.

**When the agent calls it:** Only if a contact was discovered in Stage 2 but has `email = null`. The agent extracts `first_name`, `last_name`, and the company domain and calls this tool.

---

### Tool 7 — `lusha_person_search`

| Property | Value |
|---|---|
| **File** | `app/tools/lusha_tool.py` |
| **Service** | Lusha |
| **Endpoint** | `POST https://api.lusha.com/person` |
| **Auth** | `api_key` request header |
| **HTTP Client** | Slow client (20s timeout) |
| **Caching** | Yes — keyed on `(first_name, last_name, company_name, company_domain)` |
| **Retry** | Yes — 2 retries |
| **Used In** | Stage 3: Enrichment (for contacts missing a phone number) |

**What it does:** Given a person's name and company, returns their direct phone number(s), additional email addresses, and social profile links. Lusha specialises in direct-dial phone numbers — something Apollo and Hunter rarely provide.

**When the agent calls it:** Only if a contact has `phone = null` after Stage 2. This is the only tool in the pipeline that can reliably produce direct phone numbers.

---

### Tool 8 — `duckduckgo_search`

| Property | Value |
|---|---|
| **File** | `app/tools/duckduckgo_tool.py` |
| **Service** | DuckDuckGo (via `duckduckgo-search` Python library) |
| **Endpoint** | No HTTP endpoint — uses `DDGS()` context manager internally |
| **Auth** | None required |
| **HTTP Client** | Uses the library's own internal client (no pooling) |
| **Caching** | Yes — keyed on `(query, max_results)` |
| **Retry** | No explicit retry (library handles internally) |
| **Used In** | Any stage — fallback when paid APIs are rate-limited or return thin results |

**What it does:** Runs a standard web text search on DuckDuckGo and returns title, URL, and text snippet for each result. It is the only tool that requires no API key, making it a zero-cost fallback.

**When the agent calls it:**
- Stage 1: If Apollo and Exa return fewer companies than needed
- Stage 2: Searching `"[company name] CTO LinkedIn"` or similar
- Stage 3: Finding a LinkedIn URL when Exa doesn't return one

---

### Tool 9 — `scrape_webpage`

| Property | Value |
|---|---|
| **File** | `app/tools/web_scraper_tool.py` |
| **Service** | Any public website |
| **Endpoint** | HTTP GET to any provided URL |
| **Auth** | None (uses `User-Agent: Mozilla/5.0 qlGen Research Bot`) |
| **HTTP Client** | Slow client (20s timeout, follows redirects) |
| **Parser** | BeautifulSoup 4 with `html.parser` |
| **Caching** | Yes — keyed on `(url,)` |
| **Retry** | No (HTTP errors return an error dict) |
| **Used In** | Stage 2 (team/about pages), Stage 4 (BANT evidence) |

**What it does:** Fetches a webpage, strips out non-content tags (`script`, `style`, `nav`, `footer`, `header`, `aside`, `noscript`), extracts the visible text (capped at **3000 characters**), and returns the page title + text + first 30 links.

**Two distinct use cases:**
1. **Stage 2 — Contact Discovery:** If Apollo and Hunter return fewer than 2 contacts for a company, the agent scrapes `company.com/team` or `company.com/about` to find additional names and titles.
2. **Stage 4 — BANT Evidence:** If the agent has thin evidence for a company's need or timing score, it scrapes the company homepage or a relevant blog/news page to gather more context.

---

## 9. MCP Servers vs Direct API Calls

### The answer: Zero MCP servers. All 9 tools are direct calls.

**MCP (Model Context Protocol)** is an open standard for connecting AI models to external tools via a separate server process. MCP servers run independently and expose tools over a standardised protocol that the agent connects to at runtime.

**qlGen does NOT use MCP.** Here is exactly how the tools work instead:

```
qlGen Tool Architecture:

  AWS Bedrock (Claude Sonnet 4)
          │
          │  tool_use request (via Converse API)
          │  e.g., { "name": "apollo_company_search", "input": {...} }
          ▼
  Strands Agent Framework  (strands-agents==0.1.7)
          │
          │  looks up the registered @tool function
          │
          ▼
  Python function in app/tools/*.py
          │
          │  synchronous httpx.Client.post/get()
          │  OR duckduckgo_search library call
          │  OR httpx.Client.get() + BeautifulSoup parse
          ▼
  External API / Website
  (Apollo, Exa, Tavily, Hunter, Lusha, DuckDuckGo, Any URL)
          │
          ▼
  JSON / HTML response returned directly to the Python function
          │
          ▼
  tool_result appended to conversation context
          │
          ▼
  Bedrock sees the result and continues reasoning
```

### How tools are registered

Tools are registered using the `@tool` decorator from `strands-agents`:

```python
# Example from apollo_tool.py
from strands import tool

@tool
def apollo_company_search(query: str, ...) -> dict:
    """Docstring — this is what Claude reads to decide when to use this tool."""
    ...
```

The decorator:
1. Reads the function's **type hints** to generate a JSON Schema for input validation
2. Uses the **docstring** as the tool description shown to the LLM
3. Registers the function so Strands can call it when Bedrock requests it

The `Agent` is created with the tools listed explicitly:
```python
# From lead_gen_agent.py
return Agent(
    model=BedrockModel(model_id=..., region_name=...),
    system_prompt=LEAD_GEN_SYSTEM_PROMPT,
    tools=[
        apollo_company_search,   # Tool 1
        exa_search,              # Tool 2 (note: exa is listed before apollo_people)
        tavily_search,           # Tool 3
        duckduckgo_search,       # Tool 4
        apollo_people_search,    # Tool 5
        hunter_domain_search,    # Tool 6
        hunter_email_finder,     # Tool 7
        lusha_person_search,     # Tool 8
        scrape_webpage,          # Tool 9
    ],
)
```

### Why not MCP?

| Aspect | MCP Server | qlGen's Approach |
|---|---|---|
| Deployment | Separate process / server | Inline Python functions |
| Protocol | MCP JSON-RPC over stdio/HTTP | Strands `@tool` decorator + Bedrock `tool_use` |
| Latency | Extra network hop per call | Direct in-process function call |
| Complexity | Requires running & managing server(s) | No extra infrastructure |
| Caching | Must be implemented in server | Handled centrally in `http_client.py` |
| Best suited for | Reusable tools shared across many agents | Single-agent, contained pipeline |

For this single-agent, self-contained pipeline, direct function calls are simpler, faster, and easier to debug than MCP servers.

---

## 10. Tool Usage by Pipeline Stage

```
STAGE 1: COMPANY DISCOVERY
┌─────────────────────────────────────────────────────────────────────┐
│  Priority  Tool                  Role                               │
│  ────────  ────────────────────  ──────────────────────────────── │
│  1 (PRIMARY)   apollo_company_search   Structured DB search        │
│  2 (SECONDARY) exa_search              Semantic/qualitative search  │
│  3 (SUPPL.)    tavily_search           Recent news / funding signals│
│  4 (FALLBACK)  duckduckgo_search       Free search if above fail    │
└─────────────────────────────────────────────────────────────────────┘

STAGE 2: CONTACT DISCOVERY
┌─────────────────────────────────────────────────────────────────────┐
│  Priority  Tool                  Role                               │
│  ────────  ────────────────────  ──────────────────────────────── │
│  1 (PRIMARY)   apollo_people_search    Find contacts by title       │
│  2 (SECONDARY) hunter_domain_search    Email discovery by domain    │
│  3 (SUPPL.)    scrape_webpage          Team/about page scraping     │
│  4 (FALLBACK)  duckduckgo_search       "[name] [company] LinkedIn"  │
└─────────────────────────────────────────────────────────────────────┘

STAGE 3: CONTACT ENRICHMENT
┌─────────────────────────────────────────────────────────────────────┐
│  Missing Field  Tool                  Role                          │
│  ─────────────  ────────────────────  ────────────────────────────│
│  email          hunter_email_finder   Predict email from name+domain│
│  phone          lusha_person_search   Direct-dial phone lookup      │
│  linkedin_url   exa_search            Semantic LinkedIn search      │
│  linkedin_url   duckduckgo_search     Fallback LinkedIn search      │
└─────────────────────────────────────────────────────────────────────┘

STAGE 4: BANT SCORING
┌─────────────────────────────────────────────────────────────────────┐
│  Condition      Tool                  Role                          │
│  ─────────────  ────────────────────  ────────────────────────────│
│  always first   (uses existing data)  No tool calls preferred       │
│  thin evidence  tavily_search         Funding/news/timing research  │
│  thin evidence  scrape_webpage        Company website content       │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 11. Tool Infrastructure (Shared Client)

All HTTP-based tools share a common infrastructure layer defined in `app/tools/http_client.py`. This module provides three capabilities applied to every tool call:

### Connection Pooling

Two persistent `httpx.Client` instances are reused across all tool calls in a pipeline run, eliminating the TCP handshake overhead of creating a new connection for each request:

```
Fast client (10s timeout)  →  Apollo, Hunter
Slow client (20s timeout)  →  Exa, Tavily, Lusha, Scraper
```

Each client maintains up to 10–20 keep-alive connections and reuses them for up to 120 seconds.

### In-Memory Result Cache

A global dict with a 10-minute TTL stores the result of every API call. Before making a network request, each tool hashes its parameters and checks the cache. If a hit is found, the cached value is returned instantly.

This eliminates redundant calls when the same company/domain is queried in multiple stages:
- `hunter_domain_search("acme.com")` in Stage 2 is reused in Stage 3 enrichment
- `tavily_search("Acme Corp")` in Stage 1 is reused if BANT asks the same query
- `scrape_webpage("acme.com/about")` in Stage 2 is reused if BANT scrapes the same page

The cache is cleared before and after every pipeline run to prevent stale data carrying over.

### Retry with Exponential Backoff

The `@retry_request` decorator retries failed HTTP calls up to 2 times:

```
Retries on:  timeout, HTTP 429 (rate limit), HTTP 500/502/503/504
Wait:        attempt 1 → 1.0s, attempt 2 → 2.0s
Retry-After: if the API returns a Retry-After header, it waits at least that long
```

DuckDuckGo and the web scraper do not use `@retry_request` — the library handles DuckDuckGo internally, and the scraper returns an error dict on failure rather than raising.
