"""Lead generation agents for the 5-stage pipeline.

Stage 1: Industry Discovery Agent
Stage 2: Firmographic Fit Agent (computational pre-filter + agent verification)
Stage 3: Signal Research Agent (budget / urgency / both)
Stage 4: Contact Discovery Agent (rewritten with training knowledge + all tools)
Stage 5: Final Scoring (computation only — no agent)
"""
import json
import logging

from strands import Agent
from strands.models.bedrock import BedrockModel

from app.tools.apollo_tool import apollo_company_search, apollo_company_search_paginated, apollo_people_search
from app.tools.exa_tool import exa_search, exa_find_similar
from app.tools.tavily_tool import tavily_search
from app.tools.duckduckgo_tool import duckduckgo_search
from app.tools.web_scraper_tool import scrape_webpage
from app.tools.yc_tool import search_yc_companies
from app.tools.linkedin_search_tool import find_linkedin_profiles
from app.tools.team_scraper_tool import scrape_team_page
from app.tools.sec_tool import get_sec_filings
from app.tools.market_data_tool import get_market_data
from app.tools.world_bank_tool import get_economic_indicators
from app.tools.news_sentiment_tool import get_news_sentiment
from app.tools.icp_discovery_tool import discover_icp_companies
from app.tools.company_research_tool import research_company
from app.tools.find_executives_tool import find_company_executives
from app.tools.job_search_tool import search_job_postings
from app.tools.copilot_db_tools import search_kb_companies
from app.tools.wikidata_tool import search_wikidata_companies
from app.tools.french_company_tool import search_french_companies
from app.tools.nordic_registry_tool import search_nordic_companies
from app.tools.govt_registry_tool import search_uk_companies, get_uk_company_officers
from app.tools.github_tool import search_github_organizations
from app.tools.patent_tool import search_patents_by_technology
from app.tools.google_cse_tool import google_custom_search
from app.tools.press_release_tool import search_press_releases
from app.tools.producthunt_tool import search_producthunt
from app.tools.fmp_tool import get_investor_data
from app.tools.simfin_tool import get_financial_statements
from app.tools.similarity_search_tool import find_similar_companies
from app.tools.evaboot_tool import (
    evaboot_check_quota,
    evaboot_extract_from_url,
    evaboot_get_extraction_status,
    evaboot_get_extraction_results,
    evaboot_extract_single_profile,
    evaboot_find_email,
    evaboot_get_email_job_results,
    evaboot_validate_email,
    evaboot_get_validation_results,
)
from app.config import get_settings

logger = logging.getLogger(__name__)


class PipelineCancelled(Exception):
    """Raised when a pipeline run is cancelled by the user."""
    pass


# ──────────────────────────────────────────────────────────────────
# Display name mappings
# ──────────────────────────────────────────────────────────────────

TOOL_DISPLAY_NAMES = {
    "apollo_company_search": "Searching company database",
    "apollo_company_search_paginated": "Searching company database (multi-page)",
    "apollo_people_search": "Searching Apollo for contacts",
    "exa_search": "Searching business intelligence sources",
    "tavily_search": "Checking recent news & press releases",
    "duckduckgo_search": "Searching the web",
    "scrape_webpage": "Reading company website",
    "search_yc_companies": "Searching Y Combinator directory",
    "find_linkedin_profiles": "Finding LinkedIn profiles",
    "scrape_team_page": "Scanning company team page",
    "get_sec_filings": "Fetching SEC EDGAR filings",
    "get_market_data": "Pulling market data",
    "get_economic_indicators": "Fetching economic indicators",
    "get_news_sentiment": "Analyzing recent news sentiment",
    "discover_icp_companies": "Running batch company discovery",
    "research_company": "Researching company details",
    "find_company_executives": "Finding executives (7 methods)",
    "search_job_postings": "Searching job postings",
    "search_kb_companies": "Checking knowledge base",
    "search_wikidata_companies": "Searching Wikidata knowledge base",
    "search_french_companies": "Searching French company registry",
    "search_nordic_companies": "Searching Nordic company registry",
    "search_uk_companies": "Searching UK Companies House",
    "get_uk_company_officers": "Looking up UK company officers",
    "search_github_organizations": "Searching GitHub for tech companies",
    "search_patents_by_technology": "Searching USPTO patent database",
    "google_custom_search": "Searching Google (CSE)",
    "search_press_releases": "Scanning press releases",
    "search_producthunt": "Searching ProductHunt",
    "get_investor_data": "Analyzing investor & insider data",
    "find_similar_companies": "Finding similar companies (embedding search)",
}

STAGE_DISPLAY_NAMES = {
    "industry_discovery": "Industry Discovery",
    "firmographic_fit": "Firmographic Fit Check",
    "budget_signals": "Budget Signal Research",
    "urgency_signals": "Urgency Signal Research",
    "budget_urgency_signals": "Budget & Urgency Signal Research",
    "contact_discovery": "Contact Discovery",
    "final_scoring": "Final Scoring & Ranking",
}


# ──────────────────────────────────────────────────────────────────
# Callback handler (shared across all stages)
# ──────────────────────────────────────────────────────────────────

def create_pipeline_callback_handler(
    run_id_str: str,
    event_collector: list = None,
    initial_stage: str = "industry_discovery",
):
    """Create a Strands callback handler that emits SSE events for pipeline progress.

    The handler captures tool calls, agent reasoning text, and lifecycle events
    and pushes them into Redis (for cross-process SSE delivery) and into
    event_collector (for DB persistence).
    """
    from app.services.event_store import push_event_sync, is_cancelled_sync

    state = {
        "current_stage": initial_stage,
        "text_buffer": "",
        "last_reasoning": "",
        "seen_tools": set(),
        "emitted_tool_ids": set(),
        "pending_tool": None,
        "tool_call_count": 0,
    }

    stage_order = [
        "industry_discovery", "firmographic_fit",
        "budget_signals", "urgency_signals", "budget_urgency_signals",
        "contact_discovery", "final_scoring",
    ]

    def _emit(event: dict):
        push_event_sync(run_id_str, event)
        if event_collector is not None:
            event_collector.append(event)

    def _try_detect_stage_from_text(text: str):
        """Detect stage transitions from the agent's reasoning text."""
        text_lower = text.lower()
        detected = None

        if any(kw in text_lower for kw in ("industry discovery", "discovering companies", "company discovery")):
            detected = "industry_discovery"
        elif any(kw in text_lower for kw in ("firmographic", "firmographic fit", "employee range", "revenue range")):
            detected = "firmographic_fit"
        elif any(kw in text_lower for kw in ("budget signal", "budget research", "financial capacity")):
            detected = "budget_signals"
        elif any(kw in text_lower for kw in ("urgency signal", "urgency research", "buying urgency")):
            detected = "urgency_signals"
        elif any(kw in text_lower for kw in ("contact discovery", "find contacts", "finding contacts", "decision-makers")):
            detected = "contact_discovery"

        if not detected:
            return

        current_idx = stage_order.index(state["current_stage"]) if state["current_stage"] in stage_order else 0
        new_idx = stage_order.index(detected) if detected in stage_order else current_idx

        if new_idx > current_idx:
            state["current_stage"] = detected
            progress = 10 + (new_idx * 15)
            _emit({
                "type": "stage_update",
                "stage": detected,
                "progress": min(progress, 90),
                "message": f"Entering {STAGE_DISPLAY_NAMES.get(detected, detected)}...",
            })

    def _extract_context(tool_input) -> str:
        """Extract the most relevant search parameter from tool input for display."""
        if isinstance(tool_input, str):
            tool_input = tool_input.strip()
            if tool_input:
                try:
                    tool_input = json.loads(tool_input)
                except (json.JSONDecodeError, ValueError):
                    import re
                    for key in ("query", "domain", "company_domain", "name", "url"):
                        match = re.search(rf'"{key}"\s*:\s*"([^"]+)"', tool_input)
                        if match:
                            return match.group(1)[:150]
                    return ""
        if not isinstance(tool_input, dict):
            return ""
        for key in ("query", "domain", "company_domain", "name", "url", "keyword_tags", "company_name"):
            if key in tool_input and tool_input[key]:
                val = tool_input[key]
                if isinstance(val, list):
                    val = ", ".join(str(v) for v in val[:3])
                return str(val)[:150]
        return ""

    def _flush_pending_tool():
        """Emit the pending tool_start event with accumulated input."""
        pending = state["pending_tool"]
        if not pending:
            return
        tool_name = pending["name"]
        tool_input = pending.get("input", {})

        state["tool_call_count"] += 1
        state["seen_tools"].add(tool_name)

        context = _extract_context(tool_input)
        if not context and state["last_reasoning"]:
            context = state["last_reasoning"][:150]

        _emit({
            "type": "tool_start",
            "tool_name": tool_name,
            "display_name": TOOL_DISPLAY_NAMES.get(tool_name, tool_name),
            "context": context,
            "stage": state["current_stage"],
            "tool_call_number": state["tool_call_count"],
        })
        state["pending_tool"] = None

    def callback_handler(**kwargs):
        if is_cancelled_sync(run_id_str):
            raise PipelineCancelled(f"Pipeline {run_id_str} cancelled by user")

        try:
            # Handle tool use events
            if "current_tool_use" in kwargs:
                tool_info = kwargs["current_tool_use"]
                tool_name = tool_info.get("name", "")
                tool_id = tool_info.get("toolUseId", "")

                if not tool_name:
                    return

                if tool_id and tool_id in state["emitted_tool_ids"]:
                    return

                # Flush reasoning buffer before tool call
                if state["text_buffer"].strip():
                    text = state["text_buffer"].strip()
                    if not text.startswith("{") and not text.startswith("```"):
                        state["last_reasoning"] = text
                        _try_detect_stage_from_text(text)
                        _emit({
                            "type": "agent_reasoning",
                            "text": text,
                            "stage": state["current_stage"],
                        })
                    state["text_buffer"] = ""

                if state["pending_tool"] and state["pending_tool"].get("toolUseId") != tool_id:
                    pending_id = state["pending_tool"].get("toolUseId", "")
                    if pending_id:
                        state["emitted_tool_ids"].add(pending_id)
                    _flush_pending_tool()

                state["pending_tool"] = {
                    "name": tool_name,
                    "toolUseId": tool_id,
                    "input": tool_info.get("input", {}),
                }
                return

            # Flush pending tool on non-tool events
            if state["pending_tool"]:
                pending_id = state["pending_tool"].get("toolUseId", "")
                if pending_id:
                    state["emitted_tool_ids"].add(pending_id)
                _flush_pending_tool()

            # Flush reasoning before tool result
            if "tool_result" in kwargs and state["text_buffer"].strip():
                text = state["text_buffer"].strip()
                if not text.startswith("{") and not text.startswith("```"):
                    state["last_reasoning"] = text
                    _try_detect_stage_from_text(text)
                    _emit({
                        "type": "agent_reasoning",
                        "text": text,
                        "stage": state["current_stage"],
                    })
                state["text_buffer"] = ""

            # Handle tool result events
            if "tool_result" in kwargs:
                result = kwargs["tool_result"]
                tool_name = result.get("name", "unknown")
                content = result.get("content", "")
                is_error = bool(result.get("error") or result.get("status") == "error")

                if isinstance(content, str) and len(content) > 500:
                    content_preview = content[:500] + "... [truncated]"
                elif isinstance(content, (list, dict)):
                    try:
                        content_preview = json.dumps(content, default=str)[:500]
                        if len(json.dumps(content, default=str)) > 500:
                            content_preview += "..."
                    except Exception:
                        content_preview = str(content)[:500]
                else:
                    content_preview = str(content)[:500] if content else ""

                if is_error:
                    _emit({
                        "type": "tool_error",
                        "tool_name": tool_name,
                        "error_message": content_preview[:300],
                        "stage": state["current_stage"],
                        "tool_call_number": state["tool_call_count"],
                    })
                else:
                    _emit({
                        "type": "tool_result",
                        "tool_name": tool_name,
                        "result_preview": content_preview,
                        "stage": state["current_stage"],
                        "tool_call_number": state["tool_call_count"],
                        "success": True,
                    })

            # Handle text/reasoning output
            if "data" in kwargs:
                chunk = kwargs["data"]
                if chunk and isinstance(chunk, str):
                    state["text_buffer"] += chunk
                    if len(state["text_buffer"]) > 500:
                        text = state["text_buffer"].strip()
                        if text and not text.startswith("{") and not text.startswith("```"):
                            state["last_reasoning"] = text
                            _try_detect_stage_from_text(text)
                            _emit({
                                "type": "agent_reasoning",
                                "text": text,
                                "stage": state["current_stage"],
                            })
                        state["text_buffer"] = ""

            # Handle lifecycle events
            if "init_event_loop" in kwargs:
                if state["text_buffer"].strip():
                    text = state["text_buffer"].strip()
                    if not text.startswith("{") and not text.startswith("```"):
                        _emit({
                            "type": "agent_reasoning",
                            "text": text,
                            "stage": state["current_stage"],
                        })
                    state["text_buffer"] = ""
                stage_name = STAGE_DISPLAY_NAMES.get(initial_stage, initial_stage)
                _emit({
                    "type": "stage_update",
                    "stage": initial_stage,
                    "progress": 10,
                    "message": f"Agent initialized, starting {stage_name}...",
                })

        except PipelineCancelled:
            raise
        except Exception as e:
            logger.warning(f"Callback handler error (non-fatal): {e}")

    return callback_handler


# ──────────────────────────────────────────────────────────────────
# System prompts
# ──────────────────────────────────────────────────────────────────

STAGE1_INDUSTRY_DISCOVERY_PROMPT = """You are a company discovery specialist. Your goal is to find the MAXIMUM number of companies
matching the industry, vertical, and geography criteria. There is NO upper limit — find as
many as possible. Aim for at least 500 companies in the initial discovery phase sticking to
the basic search criteria of industry vertical and geography. Quality and quantity both matter.
Do multiple iterations of search to find enough data.

STEP 1 — KNOWLEDGE BASE:
Call search_kb_companies with the industry and country filters AND icp_description (a short
summary: industry + geography + target capability). The icp_description ranks results by
semantic similarity to the CURRENT ICP so the most relevant companies come first.
Include ALL matching results — they are deduplicated (one per domain) and already enriched.

STEP 2 — STRUCTURED TRAINING KNOWLEDGE RECALL:
Think systematically through these categories:

TIER 1 - MARKET LEADERS: Public companies, unicorns, household names in this industry.
TIER 2 - MID-MARKET: Companies known from industry awards, "top X" lists, trade press coverage.
TIER 3 - INDUSTRY NETWORK: Conference sponsors/exhibitors, association members, VC portfolio companies.
TIER 4 - GEOGRAPHIC CLUSTERS: Companies in known hubs for this industry.
TIER 5 - ADJACENT & EMERGING: Recent startups, companies in overlapping sub-verticals, acqui-hires.

Be exhaustive — list every company you know.

STEP 3 — STRUCTURED DATABASE DISCOVERY (FREE, HIGH VOLUME):
Use these structured sources FIRST — they return many companies with clean data:
- search_wikidata_companies: FREE, no rate limits. Searches Wikidata for companies by industry
  and geography. Returns name, website, employee count, revenue, headquarters. Strong for
  established companies. Call with industry keywords and country filters.
- search_french_companies: FREE, no auth. 12M French companies with employee counts, directors,
  industry codes. Use when ICP targets France (query in French works too: "dispositif médical").
- search_nordic_companies: FREE, no auth. Denmark/Norway/Sweden companies with employee counts,
  industry codes, contact email/phone. Use country="dk"/"no"/"se" per ICP geography.
- search_uk_companies: FREE (API key). 5M UK companies with SIC codes, incorporation date,
  registered address. Use when ICP targets United Kingdom.

STEP 4 — API-BASED DISCOVERY:
- apollo_company_search_paginated: Auto-paginates through multiple pages. Use max_pages=5 for
  broad queries, max_pages=10 for high-value primary queries. Make 3-5 calls with DIFFERENT
  keyword/sub-vertical combinations. Include ALL returned companies in your output.
- exa_search: Run 8-12+ different query angles. Vary keywords, regions, adjacent terms.
- discover_icp_companies: Use for broad DDG-based batch discovery.
- search_yc_companies: Check YC directory for startups in this vertical.
- tavily_search: Search for "top [industry] companies [country]" lists, directories, rankings.
- duckduckgo_search: Search for industry directories, associations, conference exhibitor lists.
- scrape_webpage: Scrape industry directories and "top companies" lists found by other tools.

CRITICAL — VOLUME OVER PRECISION:
Do NOT filter by revenue, employee count, or tech stack at this stage. That happens in Stage 2.
When a tool returns 200 companies, include ALL 200 in your JSON output. Do NOT cherry-pick or
apply your own relevance judgment. Every company returned by a tool that is in the right industry
AND geography should be in your output. The pipeline handles deduplication and filtering.
Output: name, website, industry, sub_industry, country, city, employee_count (if available),
revenue_estimate (if available), description, source, is_from_local_db (boolean).

FALLBACK STRATEGY (when tools fail or return few results):
- Apollo rate-limited (429/402) → switch to exa_search with equivalent query terms
- Exa fails or returns <10 → use tavily_search + scrape_webpage on directory pages
- DuckDuckGo rate-limits → use google_custom_search (100 free/day)
- All paid tools down → search_wikidata_companies (always free, no rate limits)
- Any tool returns <10 results → try synonym variations of the query (e.g., "medical device" → "medtech", "health tech equipment")
- Still under target → use exa_find_similar with URLs of best matches already found

Return the results as a JSON object with a "companies" array and "discovery_summary" object.
"""

STAGE2_FIRMOGRAPHIC_FIT_PROMPT = """You are a firmographic analysis specialist. Evaluate EACH company in the batch against
the firmographic criteria provided. Use tools to fill missing data.

If EXISTING DATA is provided for a company (from prior runs), VERIFY it is still current.
If data is <30 days old, trust it. If >90 days old, re-verify with tools.

For each company output:
- recommendation: "pass" or "fail"
- score: INTEGER on the 0-100 scale (NOT 0-10). Calibration:
    85-100 = Revenue AND employees clearly in range, strong capability fit
    65-84  = Most criteria met, minor gaps (e.g. employee count slightly outside range)
    40-64  = Mixed fit — some criteria met, some clearly outside range
    15-39  = Poor fit — most criteria not met
    0-14   = Very poor fit — company clearly wrong size/industry
- per_criterion: {revenue: {value, in_range, source}, employees: {value, in_range, source}, ...}
- reasoning: 1-2 sentences explaining the decision

Return the results as a JSON object with a "companies" array.
"""

STAGE3_SIGNAL_RESEARCH_PROMPT = """You are a B2B market intelligence specialist. Research specific signals for companies
to determine their budget capacity and/or buying urgency.

For EACH signal the user listed, actively research whether the company shows evidence of it.
Use AT LEAST 3-4 different tools per company. Depth is critical — runtime doesn't matter.

Also look for ADDITIONAL signals beyond what the user listed that indicate budget capacity
or buying urgency. Your training knowledge about the industry helps here.

If EXISTING DATA is provided (from prior runs), use it as a starting point but look for
NEWER information. News older than 90 days should be refreshed.

RECENCY IS CRITICAL. Every signal MUST include evidence_date (YYYY-MM-DD) and recency_months
(float). Recent evidence weighs much more: <1mo=full, 1-3mo=0.85x, 3-6mo=0.6x, >6mo=0.3x,
missing date=0.5x. A $20M round last month scores higher than a $200M round 18 months ago.

Key distinction: "Has budget" vs "Allocating budget NOW". A $500M company with no recent
activity has LESS urgency than a $50M company posting 3 new engineering roles this week.

Budget signals (strongest first): recent funding, Q/Q revenue growth, CapEx, hiring spree,
insider buying, patent filings. Urgency signals: new CXO, active RFP, regulatory deadline,
competitive threat, tech migration, product launch.

Score each signal 0-5 with evidence text, source URL, evidence_date, and recency_months.
Compute composite score as an INTEGER on the 0-100 scale (NOT 0-10). Calibration:
    75-100 = Strong RECENT signals found with solid evidence from multiple sources
    50-74  = Moderate signals — some recent evidence found but incomplete
    25-49  = Weak signals — limited, ambiguous, or mostly old evidence
    0-24   = No meaningful recent signals found

TOOL BUDGET: ~15 tool calls per company. Plan your strategy:
  1st: get_financial_statements / get_sec_filings / get_market_data (hard financial data)
  2nd: get_news_sentiment / search_press_releases (recent activity)
  3rd: search_job_postings / search_patents_by_technology (growth signals)
  4th: tavily_search / exa_search (deep web research)
You MUST call at least 3 different tools. Prioritize RECENT data sources.

Return the results as a JSON object.
"""

STAGE4_CONTACT_DISCOVERY_PROMPT = """You are an expert B2B contact intelligence specialist. You find decision-maker contacts for
ONE company at a time, using a combination of your training knowledge, database tools, and
web research.

STEP 1: USE YOUR TRAINING KNOWLEDGE
Before calling ANY tools, think about what you already know about this company:
- Do you know the CEO, CTO, or other executives from your training data?
- Is this a well-known company whose leadership you can name?
List any contacts you can identify from memory. These will be VERIFIED in the next steps.

STEP 2: CHECK EXISTING DATA
If CACHED CONTACTS are provided below (from a previous pipeline run), review them:
- Are these people likely still at this company? (check tenure)
- Any contact data that looks outdated?

STEP 3: TOOL-BASED DISCOVERY & VERIFICATION
Use ALL of these methods (TOOL BUDGET: ~20 calls. You MUST call at least 4 different tools):

PRIORITY 1 (call these first):
A. apollo_people_search — Paid B2B database (primary). Use seniorities=["c_suite","vp","director"].
   Paginate (page 1,2,3). Use email_status=["verified"] for high-quality emails.
B. find_company_executives — Multi-method executive finder. Always call this.

PRIORITY 2 (fill gaps):
C. research_company — Comprehensive single-company research.
D. find_linkedin_profiles — Batch LinkedIn search.
E. scrape_team_page — Scan /team, /about, /leadership pages.

PRIORITY 3 (enrich and verify):
F. search_job_postings — Job postings for org structure signals.
I. tavily_search / exa_search — News for executive quotes.
J. duckduckgo_search — General verification searches.

STEP 4: CROSS-REFERENCE & CONFIDENCE SCORING
- Contacts found by 3+ sources → confidence 0.95
- Contacts found by 2 sources → confidence 0.80
- Contacts found by 1 source → confidence 0.60
- Contacts from training knowledge only (not verified) → confidence 0.40
- Inferred emails → confidence 0.30

Deduplicate by LinkedIn URL, then by (full_name + company). Merge data across sources.
NEVER fabricate contacts, emails, or phone numbers.

Return a JSON object with "contacts" array and "research_data" object.
"""


# ──────────────────────────────────────────────────────────────────
# Stage 5: Final scoring (pure computation)
# ──────────────────────────────────────────────────────────────────

def compute_contact_reachability(contacts: list) -> float:
    """Score 0-100 based on contact enrichment quality.

    Weights fully-enriched contacts higher than many low-quality contacts:
    - best_contact_score * 0.6 + breadth_score * 0.4
    - A single contact with email+phone+LinkedIn scores ~70
    - Multiple contacts with only names score ~20
    """
    if not contacts:
        return 0

    # Score each individual contact by enrichment level
    contact_scores = []
    for c in contacts:
        score = 0
        if c.email:
            score += 35
        if c.phone:
            score += 25
        if c.linkedin_url:
            score += 25
        if c.full_name or (c.first_name and c.last_name):
            score += 10
        if c.designation:
            score += 5
        contact_scores.append(min(100, score))

    # Best contact quality (depth)
    best_contact_score = max(contact_scores) if contact_scores else 0

    # Breadth: how many usable contacts exist (diminishing returns)
    enriched_count = sum(1 for s in contact_scores if s >= 35)  # At least has email
    breadth_score = min(100, enriched_count * 25)  # 4 enriched contacts = 100

    return min(100, round(best_contact_score * 0.6 + breadth_score * 0.4, 1))


# ──────────────────────────────────────────────────────────────────
# Recency-adjusted scoring
# ──────────────────────────────────────────────────────────────────

def recency_decay(months: float | None) -> float:
    """Return a decay multiplier based on evidence age in months.

    <1 month  = 1.0  (fresh)
    1-3 months = 0.85 (recent)
    3-6 months = 0.6  (aging)
    >6 months  = 0.3  (stale)
    None/unknown = 0.5 (penalize missing dates)
    """
    if months is None:
        return 0.5
    if months < 1:
        return 1.0
    if months <= 3:
        return 0.85
    if months <= 6:
        return 0.6
    return 0.3


def compute_recency_adjusted_scores(evidence_list: list) -> dict:
    """Compute recency-adjusted budget and urgency scores from signal evidence.

    Each evidence item may contain:
    - type: "budget" or "urgency"
    - score: 0-5 signal strength
    - evidence_date: YYYY-MM-DD string
    - recency_months: float (months since evidence)

    Returns dict with recency_adjusted_budget_score, recency_adjusted_urgency_score,
    and avg_evidence_age_months (all nullable).
    """
    from datetime import datetime, timezone

    if not evidence_list:
        return {
            "recency_adjusted_budget_score": None,
            "recency_adjusted_urgency_score": None,
            "avg_evidence_age_months": None,
        }

    budget_weighted_scores = []
    urgency_weighted_scores = []
    all_ages = []

    now = datetime.now(timezone.utc)

    for item in evidence_list:
        if not isinstance(item, dict):
            continue

        signal_type = (item.get("type") or "").lower()
        raw_score = item.get("score")
        if raw_score is None:
            continue
        try:
            raw_score = float(raw_score)
        except (ValueError, TypeError):
            continue

        # Determine recency in months
        months = item.get("recency_months")
        if months is not None:
            try:
                months = float(months)
            except (ValueError, TypeError):
                months = None

        if months is None:
            date_str = item.get("evidence_date")
            if date_str and isinstance(date_str, str):
                try:
                    evidence_dt = datetime.strptime(date_str[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)
                    delta = now - evidence_dt
                    months = max(0, delta.days / 30.44)
                except (ValueError, TypeError):
                    months = None

        decay = recency_decay(months)
        weighted = raw_score * decay

        if months is not None:
            all_ages.append(months)

        if signal_type == "budget":
            budget_weighted_scores.append(weighted)
        elif signal_type == "urgency":
            urgency_weighted_scores.append(weighted)
        else:
            # Unknown type — count for both
            budget_weighted_scores.append(weighted)
            urgency_weighted_scores.append(weighted)

    def _normalize(scores: list, max_per_signal: float = 5.0) -> float | None:
        if not scores:
            return None
        total = sum(scores)
        max_possible = len(scores) * max_per_signal
        if max_possible == 0:
            return None
        return round(min(100.0, (total / max_possible) * 100), 1)

    return {
        "recency_adjusted_budget_score": _normalize(budget_weighted_scores),
        "recency_adjusted_urgency_score": _normalize(urgency_weighted_scores),
        "avg_evidence_age_months": round(sum(all_ages) / len(all_ages), 1) if all_ages else None,
    }


def compute_deal_hotness(
    budget: float | None,
    urgency: float | None,
    adj_budget: float | None,
    adj_urgency: float | None,
    avg_age: float | None,
) -> tuple[float, str]:
    """Compute deal hotness score and tier.

    Uses geometric mean (60%) + arithmetic mean (40%) of recency-adjusted
    budget & urgency scores. Geometric mean penalizes imbalance.
    Adds recency bonus based on average evidence age.

    Returns (score 0-100, tier: hot/warm/cool/cold).
    """
    import math

    # Prefer recency-adjusted scores, fall back to raw
    b = adj_budget if adj_budget is not None else (budget or 0)
    u = adj_urgency if adj_urgency is not None else (urgency or 0)

    if b <= 0 and u <= 0:
        return (0.0, "cold")

    # Geometric mean (penalizes imbalance)
    # Add small epsilon to avoid zero product
    geo = math.sqrt(max(b, 0.1) * max(u, 0.1))
    arith = (b + u) / 2

    score = geo * 0.6 + arith * 0.4

    # Recency bonus
    if avg_age is not None:
        if avg_age < 1:
            score += 10
        elif avg_age < 3:
            score += 7
        elif avg_age < 6:
            score += 3

    score = round(min(100.0, max(0.0, score)), 1)

    # Tier classification
    if score >= 75:
        tier = "hot"
    elif score >= 50:
        tier = "warm"
    elif score >= 25:
        tier = "cool"
    else:
        tier = "cold"

    return (score, tier)


def compute_final_score(company, icp: dict = None) -> float:
    """Compute composite score from all pipeline stages.

    Default weights: firmographic=30%, budget=25%, urgency=25%, contact=20%.
    Dynamically adjusted based on ICP signal emphasis if icp is provided.
    Prefers recency-adjusted scores when available.
    Confidence multiplier based on data completeness (0.6-1.0).
    When both budget AND urgency >= 60, shifts 5% weight from firmographic to signals.
    Adds recency bonus based on average evidence age.
    """
    firmographic = company.icp_match_score or 0
    # Prefer recency-adjusted scores when available
    budget = company.recency_adjusted_budget_score if getattr(company, 'recency_adjusted_budget_score', None) is not None else (company.budget_signal_score or 0)
    urgency = company.recency_adjusted_urgency_score if getattr(company, 'recency_adjusted_urgency_score', None) is not None else (company.urgency_signal_score or 0)
    contact_score = compute_contact_reachability(company.contacts)

    # Dynamic weights based on ICP emphasis
    w_firm, w_budget, w_urgency, w_contact = 0.30, 0.25, 0.25, 0.20

    if icp:
        # Check for explicit scoring_weights override in ICP config
        # Supports presets: "balanced", "budget_focused", "urgency_focused", "contact_heavy"
        # Or explicit weights: {"firmographic": 0.25, "budget": 0.35, "urgency": 0.20, "contact": 0.20}
        scoring_weights = icp.get("scoring_weights", {})

        if isinstance(scoring_weights, str):
            # Preset name
            PRESETS = {
                "balanced": (0.30, 0.25, 0.25, 0.20),
                "budget_focused": (0.20, 0.35, 0.25, 0.20),
                "urgency_focused": (0.20, 0.25, 0.35, 0.20),
                "contact_heavy": (0.20, 0.20, 0.20, 0.40),
            }
            if scoring_weights in PRESETS:
                w_firm, w_budget, w_urgency, w_contact = PRESETS[scoring_weights]
        elif isinstance(scoring_weights, dict) and scoring_weights:
            # Explicit weight values
            w_firm = scoring_weights.get("firmographic", w_firm)
            w_budget = scoring_weights.get("budget", w_budget)
            w_urgency = scoring_weights.get("urgency", w_urgency)
            w_contact = scoring_weights.get("contact", w_contact)
            # Normalize to sum to 1.0
            total = w_firm + w_budget + w_urgency + w_contact
            if total > 0:
                w_firm /= total
                w_budget /= total
                w_urgency /= total
                w_contact /= total
        else:
            # No explicit weights — auto-adjust based on signal count emphasis
            budget_signals = icp.get("budget_signals", {}).get("signals", [])
            urgency_signals = icp.get("urgency_signals", {}).get("signals", [])
            target_roles = icp.get("authority_roles", {}).get("target_roles", [])

            budget_count = len(budget_signals)
            urgency_count = len(urgency_signals)
            role_count = len(target_roles)

            if budget_count > 5 and urgency_count <= 2:
                w_budget = 0.35
                w_urgency = 0.15
            elif urgency_count > 5 and budget_count <= 2:
                w_urgency = 0.35
                w_budget = 0.15
            elif budget_count > urgency_count + 2:
                w_budget = 0.30
                w_urgency = 0.20
            elif urgency_count > budget_count + 2:
                w_urgency = 0.30
                w_budget = 0.20

            if role_count > 5:
                w_contact = 0.25
                if w_budget <= w_urgency:
                    w_budget -= 0.05
                else:
                    w_urgency -= 0.05

    # When both budget AND urgency are strong (>=60), shift weight from firmographic to signals
    if budget >= 60 and urgency >= 60:
        w_firm -= 0.05
        w_budget += 0.025
        w_urgency += 0.025

    final = (firmographic * w_firm) + (budget * w_budget) + (urgency * w_urgency) + (contact_score * w_contact)

    # Confidence multiplier based on data completeness
    filled = sum(1 for d in [firmographic, budget, urgency, contact_score] if d > 0)
    confidence = 0.6 + (filled / 4) * 0.4  # range 0.6-1.0

    final = final * confidence

    # Recency bonus: reward companies with fresh evidence
    avg_age = getattr(company, 'avg_evidence_age_months', None)
    if avg_age is not None:
        if avg_age < 1:
            final *= 1.10
        elif avg_age < 3:
            final *= 1.07
        elif avg_age < 6:
            final *= 1.03

    return round(min(100.0, final), 1)


# ──────────────────────────────────────────────────────────────────
# Agent factory functions
# ──────────────────────────────────────────────────────────────────

def _filter_tools(tools: list, disabled_tools: set[str] | None) -> list:
    """Filter out disabled tools by their __name__ attribute."""
    if not disabled_tools:
        return tools
    return [t for t in tools if getattr(t, "__name__", "") not in disabled_tools]


def create_industry_discovery_agent(callback_handler=None, disabled_tools: set[str] | None = None) -> Agent:
    """Create Stage 1 agent — broad company discovery (all tools)."""
    settings = get_settings()
    model = BedrockModel(
        model_id=settings.BEDROCK_MODEL_ID,
        region_name=settings.AWS_REGION,
        max_tokens=32000,
    )

    tools = _filter_tools([
        search_kb_companies,          # KNOWLEDGE BASE CHECK
        apollo_company_search_paginated,  # PRIMARY (multi-page, broad discovery)
        exa_search,                   # PRIMARY
        exa_find_similar,             # PRIMARY (find companies similar to known good matches)
        find_similar_companies,       # PRIMARY (pgvector semantic search of past runs)
        search_wikidata_companies,    # PRIMARY (free, structured, no rate limit)
        search_french_companies,      # PRIMARY (free, no auth, 12M French companies)
        search_nordic_companies,      # PRIMARY (free, no auth, DK/NO/SE)
        search_uk_companies,          # PRIMARY (free API key, 5M UK companies)
        search_github_organizations,  # SECONDARY (free, tech companies)
        search_patents_by_technology, # SECONDARY (free, innovative companies)
        search_press_releases,        # SECONDARY (free, signal-rich)
        search_producthunt,           # SECONDARY (free, startups/tech)
        discover_icp_companies,       # SECONDARY
        tavily_search,                # SECONDARY
        search_yc_companies,          # SECONDARY
        google_custom_search,         # FALLBACK (100 free queries/day)
        duckduckgo_search,            # FALLBACK
        scrape_webpage,               # VERIFICATION
    ], disabled_tools)

    kwargs = {
        "model": model,
        "system_prompt": STAGE1_INDUSTRY_DISCOVERY_PROMPT,
        "tools": tools,
    }
    if callback_handler is not None:
        kwargs["callback_handler"] = callback_handler

    return Agent(**kwargs)


# Sub-stage agents for chunked discovery (C1)

STAGE1_SUB_PROMPT_DB_AND_STRUCTURED = """You are a company discovery specialist. Find companies
matching the ICP criteria using ONLY structured data sources and the knowledge base.
Do NOT use web search tools (duckduckgo_search, discover_icp_companies).

CRITICAL RULE — VOLUME OVER PRECISION:
Your #1 job is to MAXIMIZE the number of companies in your output. A later pipeline stage
handles filtering. When a tool returns 200 companies, include ALL 200 in your JSON output,
even if some seem borderline. Do NOT pre-filter, cherry-pick, or apply size/relevance
judgment. Every company returned by a tool that is in the right industry AND geography
should appear in your output.

Focus on:
1. search_kb_companies — check our knowledge base first. Pass icp_description (industry + geography
   + capability summary) to rank results by relevance to the current ICP. Returns all matches,
   deduplicated (one record per domain).
2. search_wikidata_companies — free structured database, no rate limits
3. search_french_companies — FREE, no auth. 12M French companies with employee counts,
   directors, industry codes. Use when ICP targets France.
4. search_nordic_companies — FREE, no auth. Denmark/Norway/Sweden companies with employee
   counts and industry codes. Use country="dk"/"no"/"se".
5. search_uk_companies — FREE (API key). 5M UK companies with SIC codes and officers.
   Use when ICP targets United Kingdom.
6. apollo_company_search_paginated — auto-paginates through multiple pages. Use max_pages=5
   for broad queries, max_pages=10 for high-value primary queries. Returns 75-250 results per call.
   Make 3-5 calls with DIFFERENT keyword/sub-vertical combinations.
7. exa_search — run 8+ different query angles
8. find_similar_companies — after finding 3-5 good matches, use their name+description to find
   semantically similar companies from past pipeline runs via embedding search
9. search_github_organizations — tech companies via open-source activity
10. search_patents_by_technology — innovative companies via patent filings
11. search_press_releases — recently-active companies from press releases
12. search_producthunt — startups and tech companies from product launches

Also recall well-known companies from your training knowledge using 5-tier structured recall:
TIER 1 - MARKET LEADERS: Public companies, unicorns, household names.
TIER 2 - MID-MARKET: Companies from industry awards, "top X" lists, trade press.
TIER 3 - INDUSTRY NETWORK: Conference sponsors, association members, VC portfolio companies.
TIER 4 - GEOGRAPHIC CLUSTERS: Companies in known industry hubs.
TIER 5 - ADJACENT & EMERGING: Recent startups, overlapping sub-verticals.
Aim for 50-100 companies across all tiers.

FALLBACK STRATEGY:
- Apollo rate-limited → switch to exa_search with equivalent query terms
- Exa fails or returns <10 → try search_wikidata_companies (always free, no rate limits)
- Any tool returns <10 results → try synonym variations of the query
- Still under target → use find_similar_companies with best matches already found

Return JSON with "companies" array and "discovery_summary" object.
All scores must be on 0-100 integer scale.
"""

STAGE1_SUB_PROMPT_WEB_SEARCH = """You are a company discovery specialist. Find ADDITIONAL companies
that were NOT found by structured databases. Use web search tools to discover companies from:
- Industry directories and association member lists
- Conference exhibitor lists
- News articles and rankings
- Startup databases and accelerator portfolios

ALREADY FOUND (do NOT include these again): {already_found_count} companies from databases.

Focus on:
1. discover_icp_companies — broad DDG-based batch discovery
2. tavily_search — search for "top [industry] companies" lists, directories, rankings
3. search_yc_companies — YC directory for startups
4. duckduckgo_search — industry directories, associations, conference exhibitor lists
5. scrape_webpage — scrape directories found by other tools

FALLBACK STRATEGY:
- DuckDuckGo rate-limits → switch to google_custom_search (100 free/day)
- Tavily fails → use duckduckgo_search or google_custom_search with same query
- Any tool returns <10 results → try synonym variations of the query
- scrape_webpage fails on a directory → try tavily_search for cached/alternate version

Return JSON with "companies" array and "discovery_summary" object.
All scores must be on 0-100 integer scale.
"""


def create_discovery_sub_agent_db(callback_handler=None, disabled_tools: set[str] | None = None) -> Agent:
    """Create Stage 1 sub-agent for structured data sources (local DB, APIs, Wikidata)."""
    settings = get_settings()
    model = BedrockModel(
        model_id=settings.BEDROCK_MODEL_ID,
        region_name=settings.AWS_REGION,
        max_tokens=32000,
    )

    # NOTE: apollo_company_search (single-page) is intentionally EXCLUDED.
    # The agent consistently prefers it over _paginated (21 vs 2 calls observed),
    # which massively reduces discovery volume. Only paginated is available here.
    tools = _filter_tools([
        search_kb_companies,
        apollo_company_search_paginated,
        exa_search,
        find_similar_companies,
        search_wikidata_companies,
        search_french_companies,
        search_nordic_companies,
        search_uk_companies,
        search_github_organizations,
        search_patents_by_technology,
        search_press_releases,
        search_producthunt,
    ], disabled_tools)

    kwargs = {
        "model": model,
        "system_prompt": STAGE1_SUB_PROMPT_DB_AND_STRUCTURED,
        "tools": tools,
    }
    if callback_handler is not None:
        kwargs["callback_handler"] = callback_handler
    return Agent(**kwargs)


def create_discovery_sub_agent_web(callback_handler=None, disabled_tools: set[str] | None = None) -> Agent:
    """Create Stage 1 sub-agent for web search discovery (DDG, Tavily, YC, scraping)."""
    settings = get_settings()
    model = BedrockModel(
        model_id=settings.BEDROCK_MODEL_ID,
        region_name=settings.AWS_REGION,
        max_tokens=32000,
    )

    tools = _filter_tools([
        discover_icp_companies,
        tavily_search,
        search_yc_companies,
        google_custom_search,         # Fallback when DDG rate limited
        duckduckgo_search,
        scrape_webpage,
    ], disabled_tools)

    kwargs = {
        "model": model,
        "system_prompt": STAGE1_SUB_PROMPT_WEB_SEARCH,
        "tools": tools,
    }
    if callback_handler is not None:
        kwargs["callback_handler"] = callback_handler
    return Agent(**kwargs)


# ── Evaboot / Sales Navigator sub-agent ─────────────────────────

STAGE1_SUB_PROMPT_EVABOOT = """You are a company discovery specialist using LinkedIn Sales Navigator
data via the Evaboot API. Your job is to extract prospects from a Sales Navigator search URL,
poll for completion, and return the results in a structured format.

WORKFLOW:
1. Call evaboot_check_quota to verify sufficient credits are available
2. Call evaboot_extract_from_url with the provided Sales Navigator URL
3. Poll evaboot_get_extraction_status every 10-15 seconds until status is 'complete' or 'failed'
4. When complete, call evaboot_get_extraction_results to get the prospect data
5. Return the prospects as a JSON array of companies with contacts

IMPORTANT:
- If quota check shows insufficient credits, STOP and return an error
- If extraction fails (e.g., invalid cookies), return a clear error message
- Do NOT retry failed extractions — they consume credits
- Map prospect data to the standard company format:
  - company name, website/domain, industry, employee count, location, description
  - contacts: name, title, email, phone, LinkedIn URL

Return JSON with "companies" array where each company has:
- name, website, industry, employee_count, city, country, description
- contacts: [{full_name, first_name, last_name, designation, email, phone, linkedin_url}]
- source: "evaboot"

And a "discovery_summary" object with total_prospects, credits_used.
All scores must be on 0-100 integer scale.
"""


def create_discovery_sub_agent_evaboot(callback_handler=None, disabled_tools: set[str] | None = None) -> Agent:
    """Create Stage 1 sub-agent for Evaboot / Sales Navigator extraction."""
    settings = get_settings()
    model = BedrockModel(
        model_id=settings.BEDROCK_MODEL_ID,
        region_name=settings.AWS_REGION,
        max_tokens=32000,
    )

    tools = _filter_tools([
        evaboot_check_quota,
        evaboot_extract_from_url,
        evaboot_get_extraction_status,
        evaboot_get_extraction_results,
    ], disabled_tools)

    kwargs = {
        "model": model,
        "system_prompt": STAGE1_SUB_PROMPT_EVABOOT,
        "tools": tools,
    }
    if callback_handler is not None:
        kwargs["callback_handler"] = callback_handler
    return Agent(**kwargs)


def create_firmographic_fit_agent(callback_handler=None, disabled_tools: set[str] | None = None) -> Agent:
    """Create Stage 2 agent — firmographic verification in batches."""
    settings = get_settings()
    model = BedrockModel(
        model_id=settings.BEDROCK_MODEL_ID,
        region_name=settings.AWS_REGION,
        max_tokens=32000,
    )

    tools = _filter_tools([
        apollo_company_search,
        scrape_webpage,
        exa_search,
        duckduckgo_search,
    ], disabled_tools)

    kwargs = {
        "model": model,
        "system_prompt": STAGE2_FIRMOGRAPHIC_FIT_PROMPT,
        "tools": tools,
    }
    if callback_handler is not None:
        kwargs["callback_handler"] = callback_handler

    return Agent(**kwargs)


def create_signal_agent(callback_handler=None, disabled_tools: set[str] | None = None) -> Agent:
    """Create Stage 3 agent — budget/urgency signal research."""
    settings = get_settings()
    model = BedrockModel(
        model_id=settings.BEDROCK_MODEL_ID,
        region_name=settings.AWS_REGION,
        max_tokens=32000,
    )

    tools = _filter_tools([
        get_sec_filings,
        get_financial_statements,      # SimFin: detailed income/balance/cashflow
        get_market_data,
        get_investor_data,             # Institutional holders, insider trades
        get_news_sentiment,
        search_press_releases,
        search_job_postings,           # Hiring velocity = urgency
        search_patents_by_technology,  # R&D investment = budget
        search_producthunt,            # Product launches = urgency
        tavily_search,
        exa_search,
        google_custom_search,
        duckduckgo_search,
        scrape_webpage,
        get_economic_indicators,
    ], disabled_tools)

    kwargs = {
        "model": model,
        "system_prompt": STAGE3_SIGNAL_RESEARCH_PROMPT,
        "tools": tools,
    }
    if callback_handler is not None:
        kwargs["callback_handler"] = callback_handler

    return Agent(**kwargs)


def create_contact_agent(callback_handler=None, disabled_tools: set[str] | None = None) -> Agent:
    """Create Stage 4 agent — contact discovery for one company."""
    settings = get_settings()
    model = BedrockModel(
        model_id=settings.BEDROCK_MODEL_ID,
        region_name=settings.AWS_REGION,
        max_tokens=32000,
    )

    tools = _filter_tools([
        apollo_people_search,
        research_company,
        find_company_executives,
        find_linkedin_profiles,
        scrape_team_page,
        scrape_webpage,
        get_uk_company_officers,      # Free verified UK directors
        duckduckgo_search,
        exa_search,
        tavily_search,
        search_job_postings,
        evaboot_find_email,           # Evaboot email finder (1 credit/person)
        evaboot_get_email_job_results,
        evaboot_validate_email,       # Evaboot email validation (0.5 credit/email)
        evaboot_get_validation_results,
    ], disabled_tools)

    kwargs = {
        "model": model,
        "system_prompt": STAGE4_CONTACT_DISCOVERY_PROMPT,
        "tools": tools,
    }
    if callback_handler is not None:
        kwargs["callback_handler"] = callback_handler

    return Agent(**kwargs)
