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

from app.tools.apollo_tool import apollo_company_search, apollo_people_search
from app.tools.exa_tool import exa_search
from app.tools.tavily_tool import tavily_search
from app.tools.duckduckgo_tool import duckduckgo_search
from app.tools.hunter_tool import hunter_domain_search, hunter_email_finder
from app.tools.lusha_tool import lusha_person_search
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
from app.tools.copilot_db_tools import search_local_companies
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
    "apollo_people_search": "Searching Apollo for contacts",
    "exa_search": "Searching business intelligence sources",
    "tavily_search": "Checking recent news & press releases",
    "duckduckgo_search": "Searching the web",
    "hunter_domain_search": "Discovering contacts at company",
    "hunter_email_finder": "Verifying email address",
    "lusha_person_search": "Looking up phone number",
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
    "search_local_companies": "Checking local database",
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

STEP 1 — LOCAL DATABASE:
Call search_local_companies with the industry and country filters. This returns companies
we already know about from previous searches. Include ALL matching results.

STEP 2 — TRAINING KNOWLEDGE:
List well-known companies in the specified industry from your training knowledge. Include:
major corporations, mid-market companies, notable startups, recently funded companies,
companies you know are active in this space. Be exhaustive.

STEP 3 — TOOL-BASED DISCOVERY:
Use ALL available tools aggressively to discover additional companies beyond your knowledge:
- apollo_company_search: PAGINATE heavily. Query variations by sub-vertical, region, keyword.
  Fetch pages 1, 2, 3, 4+ for each query.
- exa_search: Run 8-12+ different query angles. Vary keywords, regions, adjacent terms.
- discover_icp_companies: Use for broad DDG-based batch discovery.
- search_yc_companies: Check YC directory for startups in this vertical.
- tavily_search: Search for "top [industry] companies [country]" lists, directories, rankings.
- duckduckgo_search: Search for industry directories, associations, conference exhibitor lists.
- scrape_webpage: Scrape industry directories and "top companies" lists found by other tools.

Do NOT filter by revenue, employee count, or tech stack at this stage. That happens later.
Output: name, website, industry, sub_industry, country, city, employee_count (if available),
revenue_estimate (if available), description, source, is_from_local_db (boolean).

Return the results as a JSON object with a "companies" array and "discovery_summary" object.
"""

STAGE2_FIRMOGRAPHIC_FIT_PROMPT = """You are a firmographic analysis specialist. Evaluate EACH company in the batch against
the firmographic criteria provided. Use tools to fill missing data.

If EXISTING DATA is provided for a company (from prior runs), VERIFY it is still current.
If data is <30 days old, trust it. If >90 days old, re-verify with tools.

For each company output:
- recommendation: "pass" or "fail"
- score: 0-100 firmographic fit score
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

Score each signal 0-5 with evidence text and source URL.
Compute composite score (0-100) with confidence level (high/medium/low).

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
Use ALL of these methods:
A. apollo_people_search — Paid B2B database (primary). Paginate.
B. find_company_executives — Multi-method executive finder. Always call this.
C. research_company — Comprehensive single-company research.
D. find_linkedin_profiles — Batch LinkedIn search.
E. scrape_team_page — Scan /team, /about, /leadership pages.
F. hunter_domain_search / hunter_email_finder — Email discovery.
G. lusha_person_search — Phone/email lookup.
H. search_job_postings — Job postings for org structure signals.
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
    """Score 0-100 based on contact enrichment quality."""
    if not contacts:
        return 0
    has_email = sum(1 for c in contacts if c.email)
    has_phone = sum(1 for c in contacts if c.phone)
    has_linkedin = sum(1 for c in contacts if c.linkedin_url)
    total = len(contacts)
    return min(100, has_email * 15 + has_phone * 10 + has_linkedin * 10 + total * 5)


def compute_final_score(company) -> float:
    """Compute composite score from all pipeline stages.

    Weights: firmographic=30%, budget=25%, urgency=25%, contact=20%.
    Confidence multiplier based on data completeness (0.6-1.0).
    """
    firmographic = company.icp_match_score or 0
    budget = company.budget_signal_score or 0
    urgency = company.urgency_signal_score or 0
    contact_score = compute_contact_reachability(company.contacts)

    final = (firmographic * 0.30) + (budget * 0.25) + (urgency * 0.25) + (contact_score * 0.20)

    # Confidence multiplier based on data completeness
    filled = sum(1 for d in [firmographic, budget, urgency, contact_score] if d > 0)
    confidence = 0.6 + (filled / 4) * 0.4  # range 0.6-1.0

    return round(final * confidence, 1)


# ──────────────────────────────────────────────────────────────────
# Agent factory functions
# ──────────────────────────────────────────────────────────────────

def _filter_tools(tools: list, disabled_tools: set[str] | None) -> list:
    """Filter out disabled tools by their __name__ attribute."""
    if not disabled_tools:
        return tools
    return [t for t in tools if getattr(t, "__name__", "") not in disabled_tools]


def create_industry_discovery_agent(callback_handler=None, disabled_tools: set[str] | None = None) -> Agent:
    """Create Stage 1 agent — broad company discovery."""
    settings = get_settings()
    model = BedrockModel(
        model_id=settings.BEDROCK_MODEL_ID,
        region_name=settings.AWS_REGION,
        max_tokens=64000,
    )

    tools = _filter_tools([
        search_local_companies,  # LOCAL DB CHECK
        apollo_company_search,   # PRIMARY
        exa_search,              # PRIMARY
        discover_icp_companies,  # SECONDARY
        tavily_search,           # SECONDARY
        search_yc_companies,     # SECONDARY
        duckduckgo_search,       # FALLBACK
        scrape_webpage,          # VERIFICATION
    ], disabled_tools)

    kwargs = {
        "model": model,
        "system_prompt": STAGE1_INDUSTRY_DISCOVERY_PROMPT,
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
        max_tokens=16000,
    )

    tools = _filter_tools([
        get_sec_filings,
        get_market_data,
        get_news_sentiment,
        tavily_search,
        exa_search,
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
        max_tokens=16000,
    )

    tools = _filter_tools([
        apollo_people_search,
        research_company,
        find_company_executives,
        find_linkedin_profiles,
        scrape_team_page,
        scrape_webpage,
        hunter_domain_search,
        hunter_email_finder,
        lusha_person_search,
        duckduckgo_search,
        exa_search,
        tavily_search,
        search_job_postings,
    ], disabled_tools)

    kwargs = {
        "model": model,
        "system_prompt": STAGE4_CONTACT_DISCOVERY_PROMPT,
        "tools": tools,
    }
    if callback_handler is not None:
        kwargs["callback_handler"] = callback_handler

    return Agent(**kwargs)
