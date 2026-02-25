import asyncio
import re
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
        if _is_irrelevant_domain(domain):
            return False
        if not company.get("company_name"):
            company["company_name"] = _derive_company_name(domain)
        self.seen_domains.add(domain)
        self.raw_companies.append(company)
        return True


_BLOCKED_DOMAINS = {
    "linkedin.com", "in.linkedin.com", "facebook.com", "twitter.com",
    "instagram.com", "youtube.com", "reddit.com", "quora.com",
    "wikipedia.org", "wikimedia.org",
    "timesofindia.indiatimes.com", "economictimes.indiatimes.com",
    "thehindubusinessline.com", "thehindu.com", "ndtv.com", "moneycontrol.com",
    "livemint.com", "businessinsider.com", "forbes.com", "fortune.com",
    "techcrunch.com", "venturebeat.com", "wired.com", "medium.com",
    "tracxn.com", "crunchbase.com", "bseindia.com", "nseindia.com",
    "craft.co", "uploads2.craft.co", "zoominfo.com", "dnb.com",
    "glassdoor.com", "indeed.com", "naukri.com", "ambitionbox.com",
    "aws.amazon.com", "azure.microsoft.com", "cloud.google.com",
    "talent500.com", "codemotion.com", "dev.to", "stackoverflow.com",
    "github.com", "gitlab.com",
    "thecompanycheck.com", "tofler.in", "comparably.com", "owler.com",
    "indiatimes.com", "economictimes.com", "hindustantimes.com",
    "businesstoday.in", "financialexpress.com", "inc42.com",
    "yourstory.com", "entrackr.com", "startupstorymedia.com",
    "businesswire.com", "prnewswire.com", "globenewswire.com",
    "bloomberg.com", "reuters.com", "wsj.com", "ft.com",
    "g2.com", "capterra.com", "trustradius.com", "getapp.com",
    "clutch.co", "goodfirms.co",
    "glassdoor.co.in", "glassdoor.ca", "glassdoor.com",
    "interviewbit.com", "geeksforgeeks.org", "selectedfirms.co",
    "scribd.com", "ziprecruiter.com", "hackerx.org",
    "builtin.com", "superprof.co.uk", "tripleten.com",
    "alueducation.com", "hrkatha.com", "ceicdata.com",
    "easyleadz.com", "lusha.com",
}

_BLOCKED_DOMAIN_SUFFIXES = (
    ".gov", ".edu", ".ac.in", ".ac.uk",
)

_BLOCKED_PARENT_DOMAINS = (
    "indiatimes.com", "economictimes.com",
)


def _is_irrelevant_domain(domain: str) -> bool:
    """Return True if the domain is a news site, aggregator, social network, or other non-company."""
    if domain in _BLOCKED_DOMAINS:
        return True
    for suffix in _BLOCKED_DOMAIN_SUFFIXES:
        if domain.endswith(suffix):
            return True
    # Block any subdomain of a blocked parent (e.g. m.economictimes.com, anything.linkedin.com)
    for parent in _BLOCKED_PARENT_DOMAINS:
        if domain == parent or domain.endswith("." + parent):
            return True
    for blocked in _BLOCKED_DOMAINS:
        if domain.endswith("." + blocked):
            return True
    return False


def _derive_company_name(domain: str) -> str:
    """Derive a readable company name from a domain (e.g. 'cybage.com' -> 'Cybage')."""
    base = domain.split(".")[0]  # take first label
    # Convert kebab/underscore to spaces, then title-case
    name = re.sub(r"[-_]", " ", base).title()
    return name


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
    # Prefer the derived/real company_name over the raw page title for Lusha
    name = company.get("company_name") or ""

    _domain_only_tools = {"clearbit", "pdl", "apollo", "hunter"}

    for tool_name, tool_fn in ENRICHMENT_TOOLS:
        try:
            if tool_name in _domain_only_tools and domain:
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
                # Merge enrichment data but never overwrite a real company_name with an empty string
                merged = {**company}
                for k, v in result.items():
                    if v or k not in merged or not merged[k]:
                        merged[k] = v
                logger.info("enrichment_succeeded", tool=tool_name, domain=domain)
                return merged
        except Exception as e:
            logger.warning("enrichment_tool_failed", tool=tool_name, error=str(e))
            continue

    # All enrichment tools failed — try to extract location from raw search content
    if not company.get("location"):
        extracted_location = _extract_location_from_content(company.get("content", "") or company.get("description", "") or "")
        if extracted_location:
            company = {**company, "location": extracted_location}
            logger.info("location_extracted_from_content", domain=domain, location=extracted_location)

    return company


_LOCATION_HINTS: list[str] = [
    "Kerala", "Karnataka", "Maharashtra", "Tamil Nadu", "Telangana",
    "Andhra Pradesh", "Delhi", "Goa", "Gujarat", "Rajasthan",
    "Bengaluru", "Bangalore", "Mumbai", "Hyderabad", "Chennai",
    "Kochi", "Cochin", "Thiruvananthapuram", "Trivandrum", "Kozhikode",
    "Calicut", "Thrissur", "Kollam", "Kannur", "Mysuru", "Mysore",
    "Mangaluru", "Mangalore", "Hubli", "Belgaum", "Belagavi",
    "Pune", "Noida", "Gurugram", "Gurgaon", "Ahmedabad", "Surat",
    "Jaipur", "Kolkata", "India",
]


def _extract_location_from_content(content: str) -> str | None:
    """Scan raw search snippet for known city/state names and return the first match."""
    if not content:
        return None
    content_lower = content.lower()
    for hint in _LOCATION_HINTS:
        if hint.lower() in content_lower:
            return hint
    return None


async def enrich_companies(companies: list[dict], max_concurrent: int = 5) -> list[dict]:
    """Enrich companies concurrently with a semaphore."""
    semaphore = asyncio.Semaphore(max_concurrent)

    async def enrich_single(company: dict) -> dict:
        async with semaphore:
            return await enrich_with_fallback(company)

    tasks = [enrich_single(c) for c in companies]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    return [r for r in results if isinstance(r, dict)]
