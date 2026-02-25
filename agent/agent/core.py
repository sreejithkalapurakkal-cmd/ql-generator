import asyncio
from datetime import datetime

import structlog
from strands import Agent

from agent.prompts.system_prompt import SYSTEM_PROMPT
from agent.tools import (
    tavily_search,
    exa_search,
    hunter_lookup,
    lusha_enrich,
    apollo_enrich,
    duckduckgo_search,
    bant_score,
)
from config import settings
from models import ICPProfile, BANTWeights, Lead, BANTScore

logger = structlog.get_logger()


class PipelineContext:
    """Shared context across all pipeline stages for a single job."""

    def __init__(self, job_id: str, icp_profile: ICPProfile, bant_weights: BANTWeights,
                 max_results: int, callback_url: str):
        self.job_id = job_id
        self.icp_profile = icp_profile
        self.bant_weights = bant_weights
        self.max_results = max_results
        self.callback_url = callback_url

        self.search_queries: list[str] = []
        self.raw_companies: list[dict] = []
        self.enriched_companies: list[dict] = []
        self.scored_leads: list[Lead] = []

        self.seen_domains: set[str] = set()
        self.total_tool_calls: int = 0

    def add_company(self, company: dict) -> bool:
        domain = (company.get("domain") or "").lower().strip()
        if not domain or domain in self.seen_domains:
            return False
        self.seen_domains.add(domain)
        self.raw_companies.append(company)
        return True


SEARCH_TOOLS = [
    ("tavily", tavily_search),
    ("exa", exa_search),
    ("duckduckgo", duckduckgo_search),
]

ENRICHMENT_TOOLS = [
    ("apollo", apollo_enrich),
    ("lusha", lusha_enrich),
    ("hunter", hunter_lookup),
]


def create_agent(context: PipelineContext) -> Agent:
    """Create a Strands agent with ICP-specific context."""
    icp = context.icp_profile
    bw = context.bant_weights

    dynamic_context = f"""
    ## Current Job Context
    - Job ID: {context.job_id}
    - Target Industries: {', '.join(icp.industries)}
    - Company Size: {icp.company_size_range.get('min', 0)}-{icp.company_size_range.get('max', 0)} employees
    - Revenue Range: ${icp.revenue_range.get('min', 0):,}-${icp.revenue_range.get('max', 0):,}
    - Geographies: {', '.join(icp.geographies)}
    - Tech Stack: {', '.join(icp.tech_stack) or 'Any'}
    - Keywords: {', '.join(icp.keywords) or 'None'}
    - Additional Notes: {icp.additional_notes or 'None'}
    - BANT Weights: B={bw.budget}, A={bw.authority}, N={bw.need}, T={bw.timeline}
    - Max Results: {context.max_results}
    """

    agent = Agent(
        model=f"bedrock/{settings.bedrock_model_id}",
        system_prompt=SYSTEM_PROMPT + dynamic_context,
        tools=[tavily_search, exa_search, hunter_lookup, lusha_enrich,
               apollo_enrich, duckduckgo_search, bant_score],
    )

    return agent


async def search_with_fallback(query: str, max_results: int = 10) -> list[dict]:
    """Try each search tool in order until one succeeds."""
    for name, tool_fn in SEARCH_TOOLS:
        try:
            results = await asyncio.wait_for(
                asyncio.to_thread(tool_fn, query=query, max_results=max_results),
                timeout=settings.tool_timeout_seconds,
            )
            if results:
                logger.info("search_succeeded", tool=name, result_count=len(results))
                return results
        except Exception as e:
            logger.warning("search_tool_failed", tool=name, error=str(e))
            continue
    return []


async def enrich_with_fallback(company: dict) -> dict:
    """Try enrichment tools in order until one succeeds."""
    domain = company.get("domain", "")
    name = company.get("title") or company.get("company_name") or ""

    for tool_name, tool_fn in ENRICHMENT_TOOLS:
        try:
            if tool_name == "apollo" and domain:
                result = await asyncio.wait_for(
                    asyncio.to_thread(tool_fn, domain=domain),
                    timeout=settings.tool_timeout_seconds,
                )
            elif tool_name == "hunter" and domain:
                result = await asyncio.wait_for(
                    asyncio.to_thread(tool_fn, domain=domain),
                    timeout=settings.tool_timeout_seconds,
                )
            elif tool_name == "lusha" and name:
                result = await asyncio.wait_for(
                    asyncio.to_thread(tool_fn, company_name=name, domain=domain),
                    timeout=settings.tool_timeout_seconds,
                )
            else:
                continue

            if result:
                merged = {**company, **result}
                logger.info("enrichment_succeeded", tool=tool_name, domain=domain)
                return merged
        except Exception as e:
            logger.warning("enrichment_tool_failed", tool=tool_name, error=str(e))
            continue

    return company


async def enrich_companies(companies: list[dict], max_concurrent: int = 5) -> list[dict]:
    """Enrich companies concurrently with a semaphore."""
    semaphore = asyncio.Semaphore(max_concurrent)

    async def enrich_single(company: dict) -> dict:
        async with semaphore:
            return await enrich_with_fallback(company)

    tasks = [enrich_single(c) for c in companies]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    return [r for r in results if isinstance(r, dict)]
