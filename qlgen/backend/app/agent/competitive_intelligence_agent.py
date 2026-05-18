"""Competitive Intelligence Agent.

Maps a company's current vendor stack, identifies competitive dynamics,
and finds displacement opportunities by analyzing job postings,
web content, and press mentions.
"""
import logging
from strands import Agent
from strands.models.bedrock import BedrockModel
from app.config import get_settings

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a competitive intelligence specialist for B2B sales. Your job is to map
a company's current vendor/technology stack and identify competitive dynamics.

## Research Focus

1. **Current Vendor Stack** — What software, platforms, and services does the company use?
   Look in: job descriptions (required skills), press releases (partnership announcements),
   website tech detection, industry reports.

2. **Evaluations In Progress** — Is the company evaluating new vendors?
   Look for: RFP mentions, POC job postings, "evaluating alternatives" language.

3. **Displacement Opportunities** — Where could a new vendor win?
   Look for: contract renewal timelines, dissatisfaction signals, migration language.

4. **Competitive Wins/Losses** — Has the company recently switched vendors?
   Look for: "migrating from X to Y", "replacing", "sunset" language.

## Output Format (JSON)

```json
{
  "company_name": "...",
  "current_stack": [
    {"vendor": "Salesforce", "category": "CRM", "confidence": "high", "evidence": "Job posting requires Salesforce admin experience"}
  ],
  "evaluations": [
    {"category": "BI", "evidence": "Job posting mentions 'evaluate BI platforms'", "confidence": "medium"}
  ],
  "displacement_opportunities": [
    {"category": "BI", "current_vendor": "Tableau", "evidence": "Multiple complaints in Glassdoor reviews", "window": "Q3 2026"}
  ],
  "recent_switches": []
}
```

Return ONLY valid JSON."""


def create_competitive_intelligence_agent(callback_handler=None, disabled_tools=None) -> Agent:
    settings = get_settings()
    model = BedrockModel(
        model_id=settings.BEDROCK_MODEL_ID,
        region_name=settings.AWS_REGION,
        max_tokens=16000,
    )

    from app.tools.exa_tool import exa_search, search_job_postings
    from app.tools.tavily_tool import tavily_search
    from app.tools.duckduckgo_tool import duckduckgo_search
    from app.tools.web_scraper_tool import scrape_webpage

    all_tools = [exa_search, search_job_postings, tavily_search, duckduckgo_search, scrape_webpage]
    if disabled_tools:
        all_tools = [t for t in all_tools if getattr(t, '__name__', '') not in disabled_tools]

    kwargs = {"model": model, "system_prompt": SYSTEM_PROMPT, "tools": all_tools}
    if callback_handler:
        kwargs["callback_handler"] = callback_handler
    return Agent(**kwargs)
