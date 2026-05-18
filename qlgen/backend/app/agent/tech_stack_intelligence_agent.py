"""Tech Stack Intelligence Agent.

Detects technology adoption, migrations, and infrastructure signals
from web content, job descriptions, and public data.
"""
import logging
from strands import Agent
from strands.models.bedrock import BedrockModel
from app.config import get_settings

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a technology stack intelligence specialist. Detect what technologies
a company uses, what they're migrating to/from, and infrastructure signals.

## Research Focus

1. **Current Tech Stack** — Languages, frameworks, databases, cloud providers, SaaS tools
   Sources: job postings (required skills), website headers, GitHub repos, blog posts
2. **Technology Migrations** — Moving from X to Y (e.g., on-prem to cloud, Hadoop to Snowflake)
3. **New Adoptions** — Recently adopted technologies visible in job posts or press
4. **Infrastructure Signals** — Cloud spend, scaling patterns, architecture changes

## Output Format (JSON)

```json
{
  "company_name": "...",
  "detected_technologies": [
    {"name": "Snowflake", "category": "Data Warehouse", "confidence": "high", "evidence": "5 job postings require Snowflake experience"},
    {"name": "AWS", "category": "Cloud", "confidence": "high", "evidence": "Careers page mentions AWS-first architecture"}
  ],
  "migrations": [
    {"from": "Hadoop", "to": "Snowflake", "confidence": "medium", "evidence": "Job posting mentions migrating legacy Hadoop pipelines"}
  ],
  "new_adoptions": [
    {"technology": "dbt", "first_seen": "2026-03", "evidence": "3 recent dbt-related job postings"}
  ],
  "signal_strength": 65
}
```

Return ONLY valid JSON."""


def create_tech_stack_intelligence_agent(callback_handler=None, disabled_tools=None) -> Agent:
    settings = get_settings()
    model = BedrockModel(
        model_id=settings.BEDROCK_MODEL_ID,
        region_name=settings.AWS_REGION,
        max_tokens=16000,
    )

    from app.tools.exa_tool import exa_search, search_job_postings
    from app.tools.web_scraper_tool import scrape_webpage
    from app.tools.duckduckgo_tool import duckduckgo_search

    all_tools = [exa_search, search_job_postings, scrape_webpage, duckduckgo_search]
    if disabled_tools:
        all_tools = [t for t in all_tools if getattr(t, '__name__', '') not in disabled_tools]

    kwargs = {"model": model, "system_prompt": SYSTEM_PROMPT, "tools": all_tools}
    if callback_handler:
        kwargs["callback_handler"] = callback_handler
    return Agent(**kwargs)
