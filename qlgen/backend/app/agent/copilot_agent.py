"""Co-pilot chat agent for interactive data exploration and research."""
import json
import logging
import queue

from strands import Agent
from strands.models.bedrock import BedrockModel

# DB search tools
from app.tools.copilot_db_tools import (
    search_companies_semantic,
    search_companies_structured,
    get_company_details,
    get_icp_details,
    get_pipeline_summary,
    get_data_statistics,
)

# Reuse all 19 external tools from lead gen agent
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
from app.tools.google_places_tool import get_company_phone
from app.tools.sec_tool import get_sec_filings
from app.tools.opencorporates_tool import get_company_registry
from app.tools.market_data_tool import get_market_data
from app.tools.world_bank_tool import get_economic_indicators
from app.tools.simfin_tool import get_financial_statements
from app.tools.fmp_tool import get_investor_data
from app.tools.news_sentiment_tool import get_news_sentiment

from app.config import get_settings

logger = logging.getLogger(__name__)

COPILOT_SYSTEM_PROMPT = """You are an expert B2B sales intelligence co-pilot embedded in qlGen,
a qualified lead generation platform. You help users explore their lead data, research companies,
and get actionable recommendations.

═══════════════════════════════════════════════════════════════
YOUR CAPABILITIES
═══════════════════════════════════════════════════════════════

DATABASE TOOLS (search existing data):
  • search_companies_semantic — Vector similarity search across all companies in the database.
    Use for natural language queries like "find fintech companies" or "companies with legacy tech".
  • search_companies_structured — SQL filter search by industry, country, city, BANT range,
    employee count, tech keyword. Use for precise filtering.
  • get_company_details — Get full details for a specific company by UUID, including contacts and BANT.
  • get_icp_details — Get ICP configuration(s). Shows what criteria were used for lead generation.
  • get_pipeline_summary — Get pipeline run stats. Shows when searches were run and what was found.
  • get_data_statistics — Aggregate stats: totals, industry breakdown, BANT distribution, geo breakdown.

EXTERNAL RESEARCH TOOLS (live data from the web):
  • apollo_company_search, apollo_people_search — B2B database
  • exa_search — Semantic web search
  • tavily_search — News and press releases
  • duckduckgo_search — General web search (FREE, unlimited)
  • hunter_domain_search, hunter_email_finder — Email discovery
  • lusha_person_search — Phone number lookup
  • scrape_webpage — Read any webpage
  • search_yc_companies — Y Combinator directory
  • find_linkedin_profiles — LinkedIn profile search
  • scrape_team_page — Team page scraping
  • get_company_phone — Google Places phone lookup
  • get_sec_filings — SEC EDGAR filings
  • get_company_registry — OpenCorporates registry
  • get_market_data — Yahoo Finance data
  • get_economic_indicators — World Bank indicators
  • get_financial_statements — SimFin financials
  • get_investor_data — FMP investor data
  • get_news_sentiment — News with sentiment analysis

═══════════════════════════════════════════════════════════════
BEHAVIORAL GUIDELINES
═══════════════════════════════════════════════════════════════

1. ALWAYS USE TOOLS BEFORE MAKING CLAIMS. Don't guess — search the database or web first.
2. CITE YOUR DATA. When referencing company data, mention the source or tool used.
3. USE MARKDOWN for formatting: headers, bullet points, tables, bold text.
4. PREFER DATABASE TOOLS FIRST. Search existing data before making external API calls.
5. BE CONCISE but thorough. Provide actionable insights, not just raw data dumps.
6. When the user asks about a specific company they're viewing, use get_company_details
   with the company_id from the page context.
7. For questions about "my data" or "my leads", use get_data_statistics and search tools.
8. When comparing or ranking, use structured search with appropriate filters.
9. For latest news or real-time information, use external tools (tavily, duckduckgo).
10. NEVER fabricate data. If you don't find something, say so.

═══════════════════════════════════════════════════════════════
PAGE CONTEXT
═══════════════════════════════════════════════════════════════

The user's current page context is provided with each message. Use it to give relevant answers:
- LeadsPage (run_id): Focus on companies/contacts from that pipeline run
- DashboardPage: Broad overview, cross-run insights
- ICPConfigPage (icp_id): Focus on that specific ICP's performance and criteria
- ICPListPage: Compare ICPs, suggest new ones
- PipelinePage (run_id): Focus on that pipeline run's progress

═══════════════════════════════════════════════════════════════
RESPONSE PATTERNS
═══════════════════════════════════════════════════════════════

For "show me hot leads":
  → Use search_companies_structured with min_bant_score=16
  → Format as a ranked list with key metrics

For "tell me about [company]":
  → Use get_company_details if UUID available, else search_companies_semantic
  → Present company profile, contacts, BANT breakdown

For "find companies like X":
  → Get details of X, then use search_companies_semantic with X's profile as query

For "what's the latest on [company]":
  → Use duckduckgo_search or tavily_search for recent news

For "summarize my data":
  → Use get_data_statistics for aggregate view
  → Present key metrics, top industries, BANT distribution

For "compare these ICPs":
  → Use get_icp_details for each, then get_pipeline_summary for their runs
  → Present side-by-side comparison
"""

# Tool display names for the co-pilot callback
COPILOT_TOOL_DISPLAY_NAMES = {
    "search_companies_semantic": "Searching company database",
    "search_companies_structured": "Filtering companies",
    "get_company_details": "Looking up company details",
    "get_icp_details": "Loading ICP configuration",
    "get_pipeline_summary": "Checking pipeline results",
    "get_data_statistics": "Analyzing data statistics",
    "apollo_company_search": "Searching B2B database",
    "apollo_people_search": "Finding contacts",
    "exa_search": "Searching business intelligence",
    "tavily_search": "Checking recent news",
    "duckduckgo_search": "Searching the web",
    "hunter_domain_search": "Discovering contacts",
    "hunter_email_finder": "Verifying email",
    "lusha_person_search": "Looking up phone number",
    "scrape_webpage": "Reading webpage",
    "search_yc_companies": "Searching YC directory",
    "find_linkedin_profiles": "Finding LinkedIn profiles",
    "scrape_team_page": "Scanning team page",
    "get_company_phone": "Looking up phone number",
    "get_sec_filings": "Fetching SEC filings",
    "get_company_registry": "Checking company registry",
    "get_market_data": "Pulling market data",
    "get_economic_indicators": "Fetching economic data",
    "get_financial_statements": "Fetching financials",
    "get_investor_data": "Looking up investor data",
    "get_news_sentiment": "Analyzing news sentiment",
}


def create_copilot_callback_handler(event_queue: queue.Queue):
    """Create a callback handler that pushes events to a queue for SSE streaming.

    Lighter than the pipeline callback — focuses on text streaming and tool indicators.
    """
    state = {
        "text_buffer": "",
        "pending_tool": None,
        "emitted_tool_ids": set(),
    }

    def _flush_pending_tool():
        pending = state["pending_tool"]
        if not pending:
            return
        tool_name = pending["name"]
        event_queue.put({
            "type": "tool_use",
            "tool_name": tool_name,
            "display_name": COPILOT_TOOL_DISPLAY_NAMES.get(tool_name, tool_name),
        })
        state["pending_tool"] = None

    def callback_handler(**kwargs):
        try:
            # Tool use events
            if "current_tool_use" in kwargs:
                tool_info = kwargs["current_tool_use"]
                tool_name = tool_info.get("name", "")
                tool_id = tool_info.get("toolUseId", "")

                if not tool_name:
                    return

                if tool_id and tool_id in state["emitted_tool_ids"]:
                    return

                # Flush previous pending tool
                if state["pending_tool"] and state["pending_tool"].get("toolUseId") != tool_id:
                    pending_id = state["pending_tool"].get("toolUseId", "")
                    if pending_id:
                        state["emitted_tool_ids"].add(pending_id)
                    _flush_pending_tool()

                state["pending_tool"] = {
                    "name": tool_name,
                    "toolUseId": tool_id,
                }
                return

            # Non-tool events flush pending tool
            if state["pending_tool"]:
                pending_id = state["pending_tool"].get("toolUseId", "")
                if pending_id:
                    state["emitted_tool_ids"].add(pending_id)
                _flush_pending_tool()

            # Tool result events
            if "tool_result" in kwargs:
                result = kwargs["tool_result"]
                tool_name = result.get("name", "unknown")
                is_error = bool(result.get("error") or result.get("status") == "error")
                event_queue.put({
                    "type": "tool_result",
                    "tool_name": tool_name,
                    "success": not is_error,
                })

            # Text streaming
            if "data" in kwargs:
                chunk = kwargs["data"]
                if chunk and isinstance(chunk, str):
                    event_queue.put({
                        "type": "text_delta",
                        "content": chunk,
                    })

        except Exception as e:
            logger.warning(f"Copilot callback error (non-fatal): {e}")

    return callback_handler


def create_copilot_agent(callback_handler=None) -> Agent:
    """Create the co-pilot agent with all 25 tools (6 DB + 19 external)."""
    settings = get_settings()
    model = BedrockModel(
        model_id=settings.BEDROCK_MODEL_ID,
        region_name=settings.AWS_REGION,
    )

    kwargs = {
        "model": model,
        "system_prompt": COPILOT_SYSTEM_PROMPT,
        "tools": [
            # DB search tools
            search_companies_semantic,
            search_companies_structured,
            get_company_details,
            get_icp_details,
            get_pipeline_summary,
            get_data_statistics,
            # External tools
            apollo_company_search,
            apollo_people_search,
            exa_search,
            tavily_search,
            duckduckgo_search,
            hunter_domain_search,
            hunter_email_finder,
            lusha_person_search,
            scrape_webpage,
            search_yc_companies,
            find_linkedin_profiles,
            scrape_team_page,
            get_company_phone,
            get_sec_filings,
            get_company_registry,
            get_market_data,
            get_economic_indicators,
            get_financial_statements,
            get_investor_data,
            get_news_sentiment,
        ],
    }

    if callback_handler is not None:
        kwargs["callback_handler"] = callback_handler

    return Agent(**kwargs)
