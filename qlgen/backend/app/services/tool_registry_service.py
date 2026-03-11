"""Tool registry service: seeding, health checks, and metrics aggregation."""
import logging
import os
from datetime import datetime, timezone

import httpx
from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tool_registry import ToolRegistry
from app.config import get_settings

logger = logging.getLogger(__name__)

# Canonical tool definitions for seeding
TOOL_SEED_DATA = [
    # Pipeline tools
    {
        "tool_name": "apollo_company_search",
        "display_name": "Apollo Company Search",
        "category": "pipeline",
        "requires_api_key": True,
        "api_key_env_var": "APOLLO_API_KEY",
        "base_url": "https://api.apollo.io/v1",
        "rate_limit_info": "50 req/hr (free)",
    },
    {
        "tool_name": "apollo_people_search",
        "display_name": "Apollo People Search",
        "category": "pipeline",
        "requires_api_key": True,
        "api_key_env_var": "APOLLO_API_KEY",
        "base_url": "https://api.apollo.io/v1",
        "rate_limit_info": "50 req/hr (free)",
    },
    {
        "tool_name": "exa_search",
        "display_name": "Exa Search",
        "category": "pipeline",
        "requires_api_key": True,
        "api_key_env_var": "EXA_API_KEY",
        "base_url": "https://api.exa.ai",
        "rate_limit_info": "1,000 req/mo (free)",
    },
    {
        "tool_name": "tavily_search",
        "display_name": "Tavily Search",
        "category": "pipeline",
        "requires_api_key": True,
        "api_key_env_var": "TAVILY_API_KEY",
        "base_url": "https://api.tavily.com",
        "rate_limit_info": "1,000 req/mo (free)",
    },
    {
        "tool_name": "duckduckgo_search",
        "display_name": "DuckDuckGo Search",
        "category": "pipeline",
        "requires_api_key": False,
        "api_key_env_var": None,
        "base_url": None,
        "rate_limit_info": "~5 req/burst, auto-backoff",
    },
    {
        "tool_name": "hunter_domain_search",
        "display_name": "Hunter Domain Search",
        "category": "pipeline",
        "requires_api_key": True,
        "api_key_env_var": "HUNTER_API_KEY",
        "base_url": "https://api.hunter.io/v2",
        "rate_limit_info": "25 req/mo (free)",
    },
    {
        "tool_name": "hunter_email_finder",
        "display_name": "Hunter Email Finder",
        "category": "pipeline",
        "requires_api_key": True,
        "api_key_env_var": "HUNTER_API_KEY",
        "base_url": "https://api.hunter.io/v2",
        "rate_limit_info": "25 req/mo (free)",
    },
    {
        "tool_name": "lusha_person_search",
        "display_name": "Lusha Person Search",
        "category": "pipeline",
        "requires_api_key": True,
        "api_key_env_var": "LUSHA_API_KEY",
        "base_url": "https://api.lusha.com",
        "rate_limit_info": "5 credits/mo (free)",
    },
    {
        "tool_name": "scrape_webpage",
        "display_name": "Web Scraper",
        "category": "pipeline",
        "requires_api_key": False,
        "api_key_env_var": None,
        "base_url": None,
        "rate_limit_info": "No limit (self-hosted)",
    },
    {
        "tool_name": "search_yc_companies",
        "display_name": "Y Combinator Search",
        "category": "pipeline",
        "requires_api_key": False,
        "api_key_env_var": None,
        "base_url": None,
        "rate_limit_info": None,
    },
    {
        "tool_name": "find_linkedin_profiles",
        "display_name": "LinkedIn Profile Finder",
        "category": "pipeline",
        "requires_api_key": False,
        "api_key_env_var": None,
        "base_url": None,
        "rate_limit_info": "2s delay between searches",
    },
    {
        "tool_name": "scrape_team_page",
        "display_name": "Team Page Scraper",
        "category": "pipeline",
        "requires_api_key": False,
        "api_key_env_var": None,
        "base_url": None,
        "rate_limit_info": "No limit (self-hosted)",
    },
    {
        "tool_name": "get_company_phone",
        "display_name": "Google Places Phone Lookup",
        "category": "pipeline",
        "requires_api_key": True,
        "api_key_env_var": "GOOGLE_PLACES_API_KEY",
        "base_url": "https://maps.googleapis.com/maps/api/place",
        "rate_limit_info": None,
    },
    {
        "tool_name": "discover_icp_companies",
        "display_name": "ICP Company Discovery",
        "category": "pipeline",
        "requires_api_key": False,
        "api_key_env_var": None,
        "base_url": None,
        "rate_limit_info": "Exp. backoff 4-20s",
    },
    {
        "tool_name": "research_company",
        "display_name": "Company Research",
        "category": "pipeline",
        "requires_api_key": False,
        "api_key_env_var": None,
        "base_url": None,
        "rate_limit_info": "30s backoff on limit",
    },
    {
        "tool_name": "find_company_executives",
        "display_name": "Executive Finder",
        "category": "pipeline",
        "requires_api_key": False,
        "api_key_env_var": None,
        "base_url": None,
        "rate_limit_info": "30s backoff on limit",
    },
    # Research tools
    {
        "tool_name": "get_sec_filings",
        "display_name": "SEC EDGAR Filings",
        "category": "research",
        "requires_api_key": False,
        "api_key_env_var": None,
        "base_url": "https://data.sec.gov",
        "rate_limit_info": "10 req/sec (SEC EDGAR)",
    },
    {
        "tool_name": "get_company_registry",
        "display_name": "OpenCorporates Registry",
        "category": "research",
        "requires_api_key": False,
        "api_key_env_var": None,
        "base_url": "https://api.opencorporates.com",
        "rate_limit_info": None,
    },
    {
        "tool_name": "get_market_data",
        "display_name": "Market Data (Yahoo Finance)",
        "category": "research",
        "requires_api_key": False,
        "api_key_env_var": None,
        "base_url": None,
        "rate_limit_info": None,
    },
    {
        "tool_name": "get_economic_indicators",
        "display_name": "World Bank Economic Data",
        "category": "research",
        "requires_api_key": False,
        "api_key_env_var": None,
        "base_url": "https://api.worldbank.org",
        "rate_limit_info": None,
    },
    {
        "tool_name": "get_financial_statements",
        "display_name": "SimFin Financials",
        "category": "research",
        "requires_api_key": True,
        "api_key_env_var": "SIMFIN_API_KEY",
        "base_url": "https://backend.simfin.com/api/v3",
        "rate_limit_info": None,
    },
    {
        "tool_name": "get_investor_data",
        "display_name": "FMP Investor Data",
        "category": "research",
        "requires_api_key": True,
        "api_key_env_var": "FMP_API_KEY",
        "base_url": "https://financialmodelingprep.com/api/v3",
        "rate_limit_info": "250 req/day (FMP free)",
    },
    {
        "tool_name": "get_news_sentiment",
        "display_name": "News Sentiment Analysis",
        "category": "research",
        "requires_api_key": True,
        "api_key_env_var": "NEWS_API_KEY",
        "base_url": "https://newsapi.org/v2",
        "rate_limit_info": "100 req/day (NewsAPI free)",
    },
    # Copilot DB tools
    {
        "tool_name": "search_companies_semantic",
        "display_name": "Semantic Company Search",
        "category": "copilot_db",
        "requires_api_key": False,
        "api_key_env_var": None,
        "base_url": None,
        "rate_limit_info": "No limit (local DB)",
    },
    {
        "tool_name": "search_companies_structured",
        "display_name": "Structured Company Search",
        "category": "copilot_db",
        "requires_api_key": False,
        "api_key_env_var": None,
        "base_url": None,
        "rate_limit_info": "No limit (local DB)",
    },
    {
        "tool_name": "get_company_details",
        "display_name": "Company Details Lookup",
        "category": "copilot_db",
        "requires_api_key": False,
        "api_key_env_var": None,
        "base_url": None,
        "rate_limit_info": "No limit (local DB)",
    },
    {
        "tool_name": "get_icp_details",
        "display_name": "ICP Details Lookup",
        "category": "copilot_db",
        "requires_api_key": False,
        "api_key_env_var": None,
        "base_url": None,
        "rate_limit_info": "No limit (local DB)",
    },
    {
        "tool_name": "get_pipeline_summary",
        "display_name": "Pipeline Summary",
        "category": "copilot_db",
        "requires_api_key": False,
        "api_key_env_var": None,
        "base_url": None,
        "rate_limit_info": "No limit (local DB)",
    },
    {
        "tool_name": "get_data_statistics",
        "display_name": "Data Statistics",
        "category": "copilot_db",
        "requires_api_key": False,
        "api_key_env_var": None,
        "base_url": None,
        "rate_limit_info": "No limit (local DB)",
    },
]


async def ensure_tools_seeded(db: AsyncSession) -> None:
    """Seed tool registry with canonical tools. Uses INSERT ON CONFLICT DO NOTHING for races.
    Updates display_name/category/metadata for existing rows but preserves is_enabled, notes, health_status.
    """
    for tool_data in TOOL_SEED_DATA:
        stmt = pg_insert(ToolRegistry).values(
            tool_name=tool_data["tool_name"],
            display_name=tool_data["display_name"],
            category=tool_data["category"],
            requires_api_key=tool_data["requires_api_key"],
            api_key_env_var=tool_data["api_key_env_var"],
            base_url=tool_data["base_url"],
            rate_limit_info=tool_data.get("rate_limit_info"),
        ).on_conflict_do_update(
            index_elements=["tool_name"],
            set_={
                "display_name": tool_data["display_name"],
                "category": tool_data["category"],
                "requires_api_key": tool_data["requires_api_key"],
                "api_key_env_var": tool_data["api_key_env_var"],
                "base_url": tool_data["base_url"],
                "rate_limit_info": tool_data.get("rate_limit_info"),
            },
        )
        await db.execute(stmt)
    await db.commit()


async def check_tool_health(tool: ToolRegistry) -> dict:
    """Run a lightweight health check for a single tool.

    Returns dict with status, message, checked_at.
    """
    settings = get_settings()
    now = datetime.now(timezone.utc)

    # If requires API key and key is missing
    if tool.requires_api_key and tool.api_key_env_var:
        key_value = getattr(settings, tool.api_key_env_var, "") or os.getenv(tool.api_key_env_var, "")
        if not key_value:
            return {
                "status": "no_api_key",
                "message": f"API key {tool.api_key_env_var} is not configured",
                "checked_at": now,
            }

    # If base_url exists, probe it
    if tool.base_url:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(tool.base_url)
                # Any response (even 401/403/404) means server is reachable
                return {
                    "status": "healthy",
                    "message": f"Reachable (HTTP {resp.status_code})",
                    "checked_at": now,
                }
        except httpx.TimeoutException:
            return {
                "status": "unhealthy",
                "message": "Connection timed out",
                "checked_at": now,
            }
        except httpx.ConnectError as e:
            return {
                "status": "unhealthy",
                "message": f"Connection failed: {str(e)[:200]}",
                "checked_at": now,
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "message": f"Error: {str(e)[:200]}",
                "checked_at": now,
            }

    # No base_url and no API key needed — assume healthy (no external dependency to check)
    return {
        "status": "healthy",
        "message": "No external dependency to check",
        "checked_at": now,
    }


async def update_tool_health(db: AsyncSession, tool: ToolRegistry, health: dict) -> None:
    """Update a tool's health status in the database."""
    tool.health_status = health["status"]
    tool.last_health_check_at = health["checked_at"]
    tool.last_health_message = health["message"]
    await db.commit()


async def get_tool_metrics(db: AsyncSession) -> dict:
    """Aggregate tool usage metrics from pipeline_logs.

    Returns dict mapping tool_name -> {total_calls, successful_calls, failed_calls, last_used_at}.
    """
    query = text("""
        SELECT
            event_data->>'tool_name' AS tool_name,
            COUNT(*) FILTER (WHERE event_type IN ('tool_result', 'tool_error')) AS total_calls,
            COUNT(*) FILTER (WHERE event_type = 'tool_result') AS successful_calls,
            COUNT(*) FILTER (WHERE event_type = 'tool_error') AS failed_calls,
            MAX(created_at) AS last_used_at
        FROM pipeline_logs
        WHERE event_type IN ('tool_result', 'tool_error')
          AND event_data->>'tool_name' IS NOT NULL
        GROUP BY event_data->>'tool_name'
    """)
    result = await db.execute(query)
    rows = result.fetchall()

    metrics = {}
    for row in rows:
        metrics[row.tool_name] = {
            "total_calls": row.total_calls,
            "successful_calls": row.successful_calls,
            "failed_calls": row.failed_calls,
            "last_used_at": row.last_used_at,
        }
    return metrics


async def get_tool_last_errors(db: AsyncSession) -> dict:
    """Get the last error message per tool from pipeline_logs.

    Returns dict mapping tool_name -> last error message string.
    """
    query = text("""
        SELECT DISTINCT ON (event_data->>'tool_name')
            event_data->>'tool_name' AS tool_name,
            event_data->>'error_message' AS error_message,
            created_at
        FROM pipeline_logs
        WHERE event_type = 'tool_error'
          AND event_data->>'tool_name' IS NOT NULL
        ORDER BY event_data->>'tool_name', created_at DESC
    """)
    result = await db.execute(query)
    rows = result.fetchall()

    errors = {}
    for row in rows:
        errors[row.tool_name] = row.error_message
    return errors


async def get_disabled_tool_names(db: AsyncSession) -> set[str]:
    """Get the set of tool_name values that are disabled."""
    result = await db.execute(
        select(ToolRegistry.tool_name).where(ToolRegistry.is_enabled == False)
    )
    return {row[0] for row in result.fetchall()}
