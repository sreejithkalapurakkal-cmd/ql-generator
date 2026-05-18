"""Hiring Intelligence Agent.

Analyzes job postings to detect buying intent signals:
hiring velocity, department concentration, role seniority,
and intent keywords in job descriptions.
"""
import logging
from strands import Agent
from strands.models.bedrock import BedrockModel
from app.config import get_settings

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a hiring intelligence specialist for B2B sales. Analyze job postings
to detect buying intent signals and organizational growth patterns.

## Research Focus

1. **Hiring Velocity** — How many roles posted in 30/60/90 day windows?
2. **Department Concentration** — Which departments are growing fastest?
3. **Seniority Analysis** — Are they hiring VP+ level (new initiative) or IC level (scaling)?
4. **Intent Keywords** — Do job descriptions mention buying signals?
   Examples: "vendor evaluation", "platform migration", "build vs buy", "RFP"
5. **Technology Requirements** — What tools/platforms do they require in job postings?

## Output Format (JSON)

```json
{
  "company_name": "...",
  "total_roles_found": 23,
  "relevant_roles": [
    {
      "title": "VP of Enterprise Architecture",
      "posted_date": "2026-04-25",
      "location": "New York, NY",
      "intent_signals": ["data platform evaluation", "cloud migration"],
      "seniority": "VP",
      "department_inference": "Technology"
    }
  ],
  "hiring_velocity": {"30d": 11, "60d": 18, "90d": 23},
  "department_concentration": {"Data & Platform": 45, "Sales": 23},
  "intent_keywords_found": ["revenue intelligence", "data platform"],
  "signal_strength": 78
}
```

Use at least 2-3 different tools. Return ONLY valid JSON."""


def create_hiring_intelligence_agent(callback_handler=None, disabled_tools=None) -> Agent:
    settings = get_settings()
    model = BedrockModel(
        model_id=settings.BEDROCK_MODEL_ID,
        region_name=settings.AWS_REGION,
        max_tokens=16000,
    )

    from app.tools.exa_tool import exa_search, search_job_postings
    from app.tools.duckduckgo_tool import duckduckgo_search
    from app.tools.web_scraper_tool import scrape_webpage

    all_tools = [exa_search, search_job_postings, duckduckgo_search, scrape_webpage]
    if disabled_tools:
        all_tools = [t for t in all_tools if getattr(t, '__name__', '') not in disabled_tools]

    kwargs = {"model": model, "system_prompt": SYSTEM_PROMPT, "tools": all_tools}
    if callback_handler:
        kwargs["callback_handler"] = callback_handler
    return Agent(**kwargs)
