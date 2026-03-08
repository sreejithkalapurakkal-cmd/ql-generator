import json
import logging

from strands import Agent
from strands.models.bedrock import BedrockModel

from app.tools.apollo_tool import apollo_company_search
from app.tools.exa_tool import exa_search
from app.tools.tavily_tool import tavily_search
from app.tools.duckduckgo_tool import duckduckgo_search
from app.tools.hunter_tool import hunter_domain_search, hunter_email_finder
from app.tools.lusha_tool import lusha_person_search
from app.tools.web_scraper_tool import scrape_webpage
from app.tools.yc_tool import search_yc_companies
from app.tools.linkedin_search_tool import find_linkedin_profiles
from app.tools.team_scraper_tool import scrape_team_page
from app.tools.google_places_tool import get_company_phone
from app.tools.sec_tool import get_sec_filings
from app.tools.market_data_tool import get_market_data
from app.tools.world_bank_tool import get_economic_indicators
from app.tools.news_sentiment_tool import get_news_sentiment
from app.tools.icp_discovery_tool import discover_icp_companies
from app.tools.company_research_tool import research_company
from app.tools.find_executives_tool import find_company_executives
from app.config import get_settings

logger = logging.getLogger(__name__)

# Friendly display names for each tool
TOOL_DISPLAY_NAMES = {
    "apollo_company_search": "Searching company database",
    "exa_search": "Searching business intelligence sources",
    "tavily_search": "Checking recent news & press releases",
    "duckduckgo_search": "Searching the web",
    "hunter_domain_search": "Discovering contacts at company",
    "hunter_email_finder": "Verifying email address",
    "lusha_person_search": "Looking up phone number",
    "scrape_webpage": "Reading company website",
    "search_yc_companies": "Searching Y Combinator company directory",
    "find_linkedin_profiles": "Finding LinkedIn profiles for decision-makers",
    "scrape_team_page": "Scanning company team page for emails",
    "get_company_phone": "Looking up business phone number",
    "get_sec_filings": "Fetching SEC EDGAR filings",
    "get_market_data": "Pulling market data from Yahoo Finance",
    "get_economic_indicators": "Fetching economic indicators",
    "get_news_sentiment": "Analyzing recent news sentiment",
    "discover_icp_companies": "Running batch company discovery (15-25 searches)",
    "research_company": "Researching company (contacts, financials, news)",
    "find_company_executives": "Finding executives via 7 discovery methods",
}

STAGE_DISPLAY_NAMES = {
    "company_discovery": "Company Discovery",
    "contact_discovery": "Contact Discovery",
    "enrichment": "Contact Enrichment",
    "scoring": "BANT Scoring",
}


def create_pipeline_callback_handler(events: dict, run_id_str: str, event_collector: list = None, initial_stage: str = "company_discovery"):
    """Create a Strands callback handler that emits SSE events for pipeline progress.

    The handler captures tool calls, agent reasoning text, and lifecycle events
    and pushes them into the in-memory SSE event queue. If event_collector is
    provided, events are also appended there for later DB persistence.

    Args:
        initial_stage: The pipeline stage this agent starts in. Prevents stage
            detection from regressing (e.g. a BANT agent won't jump back to
            "contact_discovery" based on keyword matches in reasoning text).
    """
    state = {
        "current_stage": initial_stage,
        "text_buffer": "",
        "last_reasoning": "",          # last emitted reasoning text (used as tool context)
        "seen_tools": set(),           # set of tool names (for stage inference)
        "emitted_tool_ids": set(),     # set of toolUseIds already emitted
        "pending_tool": None,          # tool info waiting to be emitted (accumulating input)
        "tool_call_count": 0,
    }

    # Stage ordering for progression detection
    stage_order = ["company_discovery", "contact_discovery", "enrichment", "scoring"]

    def _emit(event: dict):
        if events is not None and run_id_str in events:
            events[run_id_str].append(event)
        if event_collector is not None:
            event_collector.append(event)

    def _try_detect_stage_from_text(text: str):
        """Detect stage transitions from the agent's reasoning text."""
        text_lower = text.lower()
        detected = None
        if any(kw in text_lower for kw in ("stage 2", "contact discovery", "find contacts", "finding contacts", "decision-makers")):
            detected = "contact_discovery"
        elif any(kw in text_lower for kw in ("stage 3", "contact enrichment", "enrichment", "missing email", "missing linkedin")):
            detected = "enrichment"
        elif any(kw in text_lower for kw in ("stage 4", "bant scor", "bant framework")):
            detected = "scoring"

        if not detected:
            return

        current_idx = stage_order.index(state["current_stage"]) if state["current_stage"] in stage_order else 0
        new_idx = stage_order.index(detected) if detected in stage_order else current_idx

        if new_idx > current_idx:
            state["current_stage"] = detected
            progress = 20 + (new_idx * 20)
            _emit({
                "type": "stage_update",
                "stage": detected,
                "progress": progress,
                "message": f"Entering {STAGE_DISPLAY_NAMES.get(detected, detected)}...",
            })

    def _extract_context(tool_input) -> str:
        """Extract the most relevant search parameter from tool input for display."""
        # Handle case where input is still a string (accumulated JSON text)
        if isinstance(tool_input, str):
            tool_input = tool_input.strip()
            if tool_input:
                try:
                    tool_input = json.loads(tool_input)
                except (json.JSONDecodeError, ValueError):
                    # Partial JSON — try to extract key-value pairs with regex
                    import re
                    for key in ("query", "domain", "company_domain", "name", "url"):
                        match = re.search(rf'"{key}"\s*:\s*"([^"]+)"', tool_input)
                        if match:
                            return match.group(1)[:150]
                    return ""
        if not isinstance(tool_input, dict):
            return ""
        for key in ("query", "domain", "company_domain", "name", "url", "keyword_tags"):
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

        # Try to extract context from tool input; fall back to last reasoning text
        context = _extract_context(tool_input)
        if not context and state["last_reasoning"]:
            # Use the preceding reasoning text as context (the agent usually says
            # "Let me search for X" right before calling a tool)
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
        try:
            # Handle tool use events
            # Strands streams current_tool_use multiple times as input accumulates.
            # We buffer the latest version and emit once the tool changes or a
            # data/lifecycle event arrives (indicating tool input streaming is done).
            if "current_tool_use" in kwargs:
                tool_info = kwargs["current_tool_use"]
                tool_name = tool_info.get("name", "")
                tool_id = tool_info.get("toolUseId", "")

                if not tool_name:
                    return

                # Skip if already emitted
                if tool_id and tool_id in state["emitted_tool_ids"]:
                    return

                # Capture any unflushed reasoning text as context for this tool
                if state["text_buffer"].strip():
                    text = state["text_buffer"].strip()
                    if not text.startswith("{") and not text.startswith("```"):
                        state["last_reasoning"] = text
                    state["text_buffer"] = ""

                # If this is a different tool_id, flush the previous pending tool
                if state["pending_tool"] and state["pending_tool"].get("toolUseId") != tool_id:
                    pending_id = state["pending_tool"].get("toolUseId", "")
                    if pending_id:
                        state["emitted_tool_ids"].add(pending_id)
                    _flush_pending_tool()

                # Buffer the latest version (with most complete input)
                state["pending_tool"] = {
                    "name": tool_name,
                    "toolUseId": tool_id,
                    "input": tool_info.get("input", {}),
                }
                return

            # Any non-tool event should flush the pending tool first
            if state["pending_tool"]:
                pending_id = state["pending_tool"].get("toolUseId", "")
                if pending_id:
                    state["emitted_tool_ids"].add(pending_id)
                _flush_pending_tool()

            # Handle tool result events
            if "tool_result" in kwargs:
                result = kwargs["tool_result"]
                tool_name = result.get("name", "unknown")
                content = result.get("content", "")
                is_error = bool(result.get("error") or result.get("status") == "error")
                # Truncate long results for log readability
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

            # Handle text/reasoning output from the agent
            if "data" in kwargs:
                chunk = kwargs["data"]
                if chunk and isinstance(chunk, str):
                    state["text_buffer"] += chunk
                    # Emit reasoning in smaller chunks for finer granularity
                    buf = state["text_buffer"]
                    if len(buf) > 80 or buf.rstrip().endswith((".", "!", "?", ":")):
                        text = buf.strip()
                        if text and not text.startswith("{") and not text.startswith("```"):
                            state["last_reasoning"] = text
                            # Detect stage transitions from reasoning text
                            _try_detect_stage_from_text(text)
                            _emit({
                                "type": "agent_reasoning",
                                "text": text,
                                "stage": state["current_stage"],
                            })
                        state["text_buffer"] = ""

            # Handle lifecycle events — also flush any remaining text buffer
            if "init_event_loop" in kwargs:
                # Flush remaining buffered reasoning text
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

        except Exception as e:
            logger.warning(f"Callback handler error (non-fatal): {e}")

    return callback_handler

# ═══════════════════════════════════════════════════════════════
# PHASE-SPECIFIC AGENTS for multi-phase pipeline
# ═══════════════════════════════════════════════════════════════

PHASE1_DISCOVERY_PROMPT = """You are an expert B2B company discovery specialist. Your ONLY job is to find companies
that match the given ICP, score each against ALL 9 ICP dimensions, collect per-dimension evidence,
and classify by evidence strength. You do NOT find contacts or do BANT scoring — that happens later.

═══════════════════════════════════════════
SECTION 1: GEOGRAPHIC DIVERSITY + MULTI-SOURCE MANDATE
═══════════════════════════════════════════
CRITICAL RULE: When the ICP lists multiple countries/regions, you MUST search EACH region
separately and return companies from EVERY geographic zone. Do NOT make a single API call
with all countries — this biases results toward the largest market (usually USA).

STRATEGY: Make separate Apollo/Exa calls per geographic zone (Americas, Europe, Asia-Pacific, etc.).
If one zone returns fewer results, make ADDITIONAL targeted calls for that zone.
Final results MUST include companies from at least 3 different countries when the ICP targets 3+ countries.

You MUST use multiple data sources. Minimum: 3 different tool types.

PRIMARY (MUST use both):
  - apollo_company_search — structured company database with firmographics
  - exa_search — semantic search for company intelligence, news, and web content

SECONDARY (use at least 2):
  - discover_icp_companies — batch DuckDuckGo-based company discovery
  - search_yc_companies — Y Combinator startup directory
  - tavily_search — news, press releases, market data
  - duckduckgo_search — general web search for niche queries

VERIFICATION (for top 10-15 candidates):
  - scrape_webpage — read /about, /technology, /careers pages to verify qualitative
    dimensions (tech maturity, infrastructure readiness, transformation signals)

═══════════════════════════════════════════
SECTION 1b: RATE-LIMIT AVOIDANCE
═══════════════════════════════════════════
Each tool has different rate-limit characteristics. Follow these rules:

APOLLO (200 req/min, generous):
  - DO NOT pass internal industry tag IDs to the 'industries' parameter.
    Use freeform keywords (e.g., "medical devices"). They are merged into keyword search.
  - You can safely make 3-4 calls. Space them out — don't fire all at once.
  - If you get a 422 error, simplify the query (fewer keywords, remove filters).

EXA (10 queries/sec, generous):
  - Safe for 3-4 calls. Keep queries concise and natural.
  - If you get a 400 error, simplify the query. Do NOT stop using Exa — just fix the query.

DUCKDUCKGO-BASED TOOLS (strict, easily rate-limited):
  - discover_icp_companies runs up to 15 DDG queries internally per call.
    Call it AT MOST 1-2 times total. It has built-in delays and will stop if rate-limited.
  - duckduckgo_search: use sparingly (max 3-5 calls). Keep max_results at 10.
  - If either tool returns "rate_limited", IMMEDIATELY stop using all DDG-based tools.
    Switch to Apollo, Exa, or Tavily.

TAVILY (reasonable limits):
  - Good fallback. Safe for 3-5 calls.

GENERAL STRATEGY:
  1. Start with Apollo + Exa calls (they are reliable and fast).
  2. After getting initial results, use discover_icp_companies once for broader coverage.
  3. Use scrape_webpage selectively on top candidates only.
  4. If any tool returns a rate-limit error, do NOT retry it. Move to the next tool.

═══════════════════════════════════════════
SECTION 2: 9-DIMENSION SCORING RUBRIC
═══════════════════════════════════════════
Score each company on ALL 9 dimensions. Each dimension scores 0-2, with a weight multiplier.

Dim 1: TARGET OFFERING FIT (weight 3x)
  0 = Wrong buyer type (would never purchase the ICP's offerings)
  1 = Adjacent buyer (related industry, might purchase)
  2 = Direct buyer (makes/develops products that directly need ICP's services)

Dim 2: GEOGRAPHY (weight 2x)
  0 = Wrong region entirely
  1 = Correct region/country but not in priority area
  2 = Located in a stated priority area

Dim 3: INDUSTRY MATCH (weight 2x)
  0 = Wrong vertical
  1 = Correct vertical
  2 = Exact vertical + sub_vertical match

Dim 4: COMPANY SIZE (weight 2x)
  0 = Outside range by >50%
  1 = Within 25% of boundary
  2 = Within stated employee/revenue range

Dim 5: TECHNOLOGY MATURITY (weight 1x)
  0 = No tech signals found OR has negative/disqualifying signals
  1 = Some positive tech signals
  2 = Multiple positive signals, zero negative signals

Dim 6: INFRASTRUCTURE READINESS (weight 1x)
  0 = No indicators found
  1 = 1 matching indicator
  2 = 2+ matching indicators

Dim 7: DIGITAL TRANSFORMATION DRIVERS (weight 1x)
  0 = No driver match
  1 = 1 category matched (growth triggers, operational pains, competitive pressures, or strategic initiatives)
  2 = 2+ categories matched

Dim 8: LEADERSHIP TRAITS (weight 0.5x)
  0 = No data on leadership
  1 = Some role alignment with target roles
  2 = Behavioral traits align with ICP's leadership profile

Dim 9: PRIORITY AREAS (weight 0.5x)
  0 = Not in any priority area
  1 = Adjacent to a priority area
  2 = Located in a stated priority area

MAX WEIGHTED SCORE = (2×3)+(2×2)+(2×2)+(2×2)+(2×1)+(2×1)+(2×1)+(2×0.5)+(2×0.5) = 26
NORMALIZED SCORE = (weighted_sum / 26) × 100

═══════════════════════════════════════════
SECTION 3: EVIDENCE COLLECTION MANDATE
═══════════════════════════════════════════
For EACH dimension, record:
  - score (0-2)
  - confidence: "verified" (from structured API data like Apollo), "inferred" (from web scraping/snippets), or "unknown" (no data)
  - evidence: 1-2 sentence summary of the data points supporting the score
  - sources: list of {url, tool} showing where data came from

RULES:
  - Dimensions with confidence "unknown" MUST score 0
  - At least the 4 critical dimensions (offering_fit, geography, industry, company_size) must have evidence
  - Use scrape_webpage to gather evidence for qualitative dimensions when structured data is insufficient

═══════════════════════════════════════════
SECTION 4: CLASSIFICATION
═══════════════════════════════════════════
Based on normalized score and evidence breadth:

  "verified_match" — score >= 70, all 4 critical dims (offering, geography, industry, size) score >= 1,
                     AND at least 6 of 9 dimensions have evidence (confidence != "unknown")

  "potential_match" — score >= 50, AND offering_fit + geography + industry all score >= 1

  "weak_match" — score >= 35, AND offering_fit >= 1

  DISCARD — score < 35 OR offering_fit = 0

═══════════════════════════════════════════
SECTION 5: OUTPUT FORMAT
═══════════════════════════════════════════
Return a JSON object. match_reasoning should be 2-3 sentences with specific dimension callouts.

```json
{
  "companies": [
    {
      "name": "Acme Corp",
      "website": "acme.com",
      "industry": "Medical Device Manufacturing",
      "sub_industry": "Wearable Medical Devices",
      "city": "San Francisco",
      "state": "California",
      "country": "US",
      "employee_count": 150,
      "revenue_estimate": 15000000,
      "tech_signals": ["AWS", "Python", "React"],
      "description": "Mid-size medical device company specializing in wearable health monitors.",
      "source": "apollo_company_search",
      "icp_match_score": 78.5,
      "qualification": "verified_match",
      "match_reasoning": "Direct buyer of medical device engineering services with 150 employees within ICP range. Bay Area location matches priority area. Cloud-native tech stack with AI/ML signals and no negative indicators.",
      "dimension_evidence": {
        "target_offering_fit": {
          "score": 2, "confidence": "verified",
          "evidence": "Develops wearable medical devices, outsources V&V per Careers page",
          "sources": [{"url": "https://acme.com/careers", "tool": "scrape_webpage"}]
        },
        "geography": {
          "score": 2, "confidence": "verified",
          "evidence": "HQ in San Francisco, CA — matches Bay Area priority area",
          "sources": [{"url": "", "tool": "apollo_company_search"}]
        },
        "industry_match": {
          "score": 2, "confidence": "verified",
          "evidence": "Medical Device Manufacturing > Wearable Devices matches ICP vertical + sub-vertical",
          "sources": [{"url": "", "tool": "apollo_company_search"}]
        },
        "company_size": {
          "score": 2, "confidence": "verified",
          "evidence": "150 employees, est. $15M revenue — within ICP range of 50-800 / $10-30M",
          "sources": [{"url": "", "tool": "apollo_company_search"}]
        },
        "technology_maturity": {
          "score": 1, "confidence": "inferred",
          "evidence": "Uses AWS and Python per job postings",
          "sources": [{"url": "https://acme.com/careers", "tool": "scrape_webpage"}]
        },
        "infrastructure_readiness": {
          "score": 0, "confidence": "unknown",
          "evidence": "No infrastructure data found",
          "sources": []
        },
        "digital_transformation": {
          "score": 1, "confidence": "inferred",
          "evidence": "Job postings mention digital health platform migration",
          "sources": [{"url": "https://acme.com/careers", "tool": "scrape_webpage"}]
        },
        "leadership_traits": {
          "score": 0, "confidence": "unknown",
          "evidence": "No leadership data found during discovery",
          "sources": []
        },
        "priority_areas": {
          "score": 2, "confidence": "verified",
          "evidence": "San Francisco is in the Bay Area priority area",
          "sources": [{"url": "", "tool": "apollo_company_search"}]
        }
      }
    }
  ],
  "discovery_summary": {
    "total_candidates_found": 45,
    "verified_match_count": 8,
    "potential_match_count": 12,
    "weak_match_count": 5,
    "discarded_count": 20,
    "tools_used": {
      "apollo_company_search": 4,
      "exa_search": 3,
      "discover_icp_companies": 2,
      "scrape_webpage": 10
    },
    "geographic_coverage": {
      "Americas": 10,
      "Europe": 8,
      "Asia-Pacific": 7
    }
  }
}
```
"""

CONTACT_AGENT_PROMPT = """You are an expert B2B contact discovery specialist. You are researching
ONE company at a time. Your ONLY job is to find decision-maker contacts and gather company
research data (financials, news, tech signals). You do NOT score BANT — that happens later.

═══════════════════════════════════════════
MANDATORY DUAL-METHOD CONTACT DISCOVERY
═══════════════════════════════════════════
You MUST call BOTH of these tools for the company:

1. research_company — Gets company info, LinkedIn profiles, team emails, financials, news.
   This is your PRIMARY data source. It returns contacts AND research data in one call.
2. find_company_executives — Uses 7 independent methods (LinkedIn, Crunchbase, press releases,
   website scraping, conference speakers, email inference) to find executives.

Together these two tools typically find 3-5 contacts. Do NOT skip either tool.
If one returns no contacts, the other often will.

═══════════════════════════════════════════
ADDITIONAL TOOLS (use for gaps)
═══════════════════════════════════════════
- duckduckgo_search: "[company] [role] LinkedIn" searches for specific people.
- scrape_webpage: Read /about, /team, /leadership pages for contacts.
- find_linkedin_profiles: Batch LinkedIn search by company + titles.
- scrape_team_page: Scrapes /team, /about, /people paths for personal emails.
- hunter_domain_search: Contacts by domain with email patterns.
- hunter_email_finder: Verify/find email by name + domain.
- lusha_person_search: Phone numbers and email by name + company.
- get_company_phone: Google Places business phone lookup.

═══════════════════════════════════════════
RATE LIMIT RESILIENCE
═══════════════════════════════════════════
Paid tools (Hunter, Lusha, Google Places) may return "RATE_LIMITED". If so, STOP using
that tool and switch to free alternatives (duckduckgo_search, find_linkedin_profiles,
scrape_team_page). NEVER retry a rate-limited tool.

═══════════════════════════════════════════
CONTACT QUALITY RULES
═══════════════════════════════════════════
- Include a contact even if only LinkedIn URL is known (no email). Partial data > no data.
- Mark email confidence: 0.9 = verified, 0.7 = scraped from website, 0.4 = inferred pattern.
- Set enrichment_status: "enriched" (linkedin+email), "partial" (one of them), "inferred" (email pattern only).
- Deduplicate contacts by LinkedIn URL or full name. Merge data from multiple sources.
- NEVER fabricate contacts, emails, or phone numbers. Only use data from tool results.
- Inferred emails from find_company_executives are acceptable — mark confidence=0.4.

═══════════════════════════════════════════
OUTPUT FORMAT
═══════════════════════════════════════════
Return a JSON object with the company's contacts AND research_data gathered by the tools.
The research_data will be passed to a downstream BANT scoring agent.

```json
{
  "name": "Company Name",
  "website": "domain.com",
  "contacts": [
    {
      "full_name": "Jane Doe",
      "first_name": "Jane",
      "last_name": "Doe",
      "designation": "Chief Technology Officer",
      "role_category": "CTO",
      "email": "jane@domain.com",
      "phone": null,
      "linkedin_url": "https://linkedin.com/in/janedoe",
      "source": "research_company",
      "confidence": 0.8,
      "enrichment_status": "partial"
    }
  ],
  "research_data": {
    "financials": "Summary of financial data found (revenue, funding, etc.)",
    "news": "Summary of recent news and press mentions",
    "tech_signals": ["signal1", "signal2"],
    "source_urls": [
      {"url": "https://...", "title": "Page title", "tool": "research_company"}
    ]
  }
}
```
"""

BANT_AGENT_PROMPT = """You are an expert B2B lead qualification analyst. You score ONE company
at a time using the BANT framework (Budget, Authority, Need, Timing). You receive pre-gathered
research data from a prior contact discovery step — use it first before calling any tools.

═══════════════════════════════════════════
SCORING PROCESS
═══════════════════════════════════════════
1. REVIEW the pre-gathered research_data (financials, news, tech_signals, source_urls).
   This data was collected by a prior agent — cite these sources in your scoring.
2. ONLY call tools to fill gaps. If research_data already covers a dimension well,
   score it directly without additional tool calls.
3. For PUBLIC companies (if you know the stock ticker): use get_sec_filings and
   get_market_data for authoritative financial data.
4. For PRIVATE companies: use duckduckgo_search for funding/revenue if not in research_data.
5. Use get_news_sentiment for timing/need evidence if news data is sparse.

═══════════════════════════════════════════
TOOLS AVAILABLE
═══════════════════════════════════════════
- get_sec_filings: SEC EDGAR filings for US public companies (pass stock ticker).
- get_market_data: Yahoo Finance real-time data (pass stock ticker).
- get_news_sentiment: Recent news with sentiment scoring (pass company name).
- get_economic_indicators: World Bank macro data (pass ISO country code).
- duckduckgo_search: General web search for any gaps.
- scrape_webpage: Read specific pages for evidence.

═══════════════════════════════════════════
SCORING RUBRIC (1-5 per dimension)
═══════════════════════════════════════════

BUDGET (financial capacity to purchase):
  5 = Revenue > upper ICP range, clear tech budget signals (recent funding, tech hires,
      stated digital transformation budget)
  4 = Revenue in upper half of ICP range, some budget indicators (growing team, tech investments)
  3 = Revenue within ICP range, no specific budget signals beyond size
  2 = Revenue in lower range, budget unclear or constrained signals
  1 = Revenue below ICP minimum, likely budget-constrained, or no financial data found

AUTHORITY (decision-making power of identified contacts):
  5 = C-suite directly owning tech/digital budget (CTO, CDO, CEO at small company)
  4 = VP-level in relevant function (VP Engineering, VP IT, VP Operations)
  3 = Director-level in relevant function (Director of Engineering, IT Director)
  2 = Manager-level or adjacent function (may influence but not decide)
  1 = No relevant decision-maker identified among contacts

NEED (alignment with ICP's target offering):
  5 = 3+ strong signals matching ICP needs (tech debt, growth pain, stated digital
      initiatives, job postings for relevant roles, industry pressure)
  4 = 2 matching signals (e.g., relevant job postings + industry trend)
  3 = 1 matching signal or general industry alignment
  2 = Weak alignment, speculative need based on industry alone
  1 = No discernible need alignment found

TIMING (readiness to act in near term):
  5 = Active RFP/vendor evaluation, recent relevant job postings, public announcements
      of digital transformation, new CTO/CIO hire
  4 = Recent funding round, stated transformation timeline, fiscal year planning
  3 = General growth trajectory suggesting near-term action
  2 = No timing signals but profile suggests eventual need
  1 = No timing signals, possibly just completed similar project

═══════════════════════════════════════════
SOURCE REQUIREMENTS
═══════════════════════════════════════════
Every BANT dimension MUST include 2-3 source URLs as evidence.
- Use SPECIFIC page URLs from tool results or research_data (techcrunch.com/..., acme.com/about)
- NEVER use company homepages (acme.com) or search engines (google.com)
- Each source must point to a DIFFERENT page. Include the page title.
- If evidence is weak, score 1-2 honestly and explain what is missing.
  Honest low scores beat inflated unverifiable ones.

═══════════════════════════════════════════
OUTPUT FORMAT
═══════════════════════════════════════════
Return a JSON object with the BANT score. Keep reason strings concise (1-2 sentences, max 150 chars each).

```json
{
  "name": "Company Name",
  "website": "domain.com",
  "bant_score": {
    "budget_score": 4,
    "budget_reason": "Revenue ~$50M, Series B raised in 2025",
    "budget_sources": [
      {"url": "https://techcrunch.com/2025/acme-series-b", "title": "Acme raises $30M", "tool": "research_company"},
      {"url": "https://acme.com/about", "title": "Company about page", "tool": "scrape_webpage"}
    ],
    "authority_score": 5,
    "authority_reason": "CTO identified with direct tech budget ownership",
    "authority_sources": [
      {"url": "https://linkedin.com/in/janedoe", "title": "Jane Doe - CTO at Acme", "tool": "find_company_executives"}
    ],
    "need_score": 4,
    "need_reason": "Running legacy Magento, job postings mention headless commerce",
    "need_sources": [
      {"url": "https://builtwith.com/acme.com", "title": "Acme tech profile", "tool": "research_company"}
    ],
    "timing_score": 3,
    "timing_reason": "Growing 25% YoY, no public replatforming timeline yet",
    "timing_sources": [
      {"url": "https://acme.com/careers", "title": "Job postings page", "tool": "scrape_webpage"}
    ],
    "total_score": 16,
    "overall_summary": "Strong prospect with budget and clear need."
  }
}
```
"""


def create_discovery_agent(callback_handler=None) -> Agent:
    """Create Phase 1 agent — company discovery and ICP scoring only."""
    settings = get_settings()
    model = BedrockModel(
        model_id=settings.BEDROCK_MODEL_ID,
        region_name=settings.AWS_REGION,
        max_tokens=64000,
    )

    kwargs = {
        "model": model,
        "system_prompt": PHASE1_DISCOVERY_PROMPT,
        "tools": [
            apollo_company_search,   # PRIMARY
            exa_search,              # PRIMARY
            discover_icp_companies,  # SECONDARY
            tavily_search,           # SECONDARY
            search_yc_companies,     # SECONDARY
            duckduckgo_search,       # FALLBACK
            scrape_webpage,          # VERIFICATION
        ],
    }

    if callback_handler is not None:
        kwargs["callback_handler"] = callback_handler

    return Agent(**kwargs)


def create_contact_agent(callback_handler=None) -> Agent:
    """Create Phase 2 agent — contact discovery + enrichment for one company."""
    settings = get_settings()
    model = BedrockModel(
        model_id=settings.BEDROCK_MODEL_ID,
        region_name=settings.AWS_REGION,
        max_tokens=16000,
    )

    kwargs = {
        "model": model,
        "system_prompt": CONTACT_AGENT_PROMPT,
        "tools": [
            research_company,
            find_company_executives,
            duckduckgo_search,
            scrape_webpage,
            find_linkedin_profiles,
            scrape_team_page,
            hunter_domain_search,
            hunter_email_finder,
            lusha_person_search,
            get_company_phone,
        ],
    }

    if callback_handler is not None:
        kwargs["callback_handler"] = callback_handler

    return Agent(**kwargs)


def create_bant_agent(callback_handler=None) -> Agent:
    """Create Phase 3 agent — BANT scoring for one company."""
    settings = get_settings()
    model = BedrockModel(
        model_id=settings.BEDROCK_MODEL_ID,
        region_name=settings.AWS_REGION,
        max_tokens=8000,
    )

    kwargs = {
        "model": model,
        "system_prompt": BANT_AGENT_PROMPT,
        "tools": [
            get_sec_filings,
            get_market_data,
            get_news_sentiment,
            get_economic_indicators,
            duckduckgo_search,
            scrape_webpage,
        ],
    }

    if callback_handler is not None:
        kwargs["callback_handler"] = callback_handler

    return Agent(**kwargs)
