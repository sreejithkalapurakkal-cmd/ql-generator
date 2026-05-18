"""Executive Intelligence Agent.

Tracks leadership changes, champion movements, and board changes.
Identifies new decision-makers and their backgrounds.
"""
import logging
from strands import Agent
from strands.models.bedrock import BedrockModel
from app.config import get_settings

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are an executive intelligence specialist for B2B sales. Track leadership
changes and identify key decision makers at target companies.

## Research Focus

1. **New Executive Hires** — C-suite and VP-level appointments in last 90 days
2. **Departures** — Key leaders who have left (creating power vacuums)
3. **Champion Movements** — Known contacts who moved from a customer company to this target
4. **Board Changes** — New board members who may influence technology decisions
5. **Background Analysis** — Where did new leaders come from? What did they do there?

## Output Format (JSON)

```json
{
  "company_name": "...",
  "current_executives": [
    {"name": "Dr. Priya Nair", "title": "CDO", "started": "2026-04", "previous_company": "Kaiser Permanente", "linkedin": "..."}
  ],
  "changes_detected": [
    {"type": "new_hire", "person": "Dr. Priya Nair", "role": "CDO", "confidence": "high", "source": "press release"}
  ],
  "champion_movements": [],
  "board_changes": [],
  "signal_strength": 85
}
```

Use multiple tools for cross-validation. Return ONLY valid JSON."""


def create_executive_intelligence_agent(callback_handler=None, disabled_tools=None) -> Agent:
    settings = get_settings()
    model = BedrockModel(
        model_id=settings.BEDROCK_MODEL_ID,
        region_name=settings.AWS_REGION,
        max_tokens=16000,
    )

    from app.tools.find_executives_tool import find_company_executives
    from app.tools.exa_tool import exa_search
    from app.tools.tavily_tool import tavily_search
    from app.tools.duckduckgo_tool import duckduckgo_search

    all_tools = [find_company_executives, exa_search, tavily_search, duckduckgo_search]
    if disabled_tools:
        all_tools = [t for t in all_tools if getattr(t, '__name__', '') not in disabled_tools]

    kwargs = {"model": model, "system_prompt": SYSTEM_PROMPT, "tools": all_tools}
    if callback_handler:
        kwargs["callback_handler"] = callback_handler
    return Agent(**kwargs)
