"""Research Planner Agent.

Pure reasoning agent (no tools) that analyzes a company profile and
determines which specialist agents to invoke, in what order, and why.
Returns a prioritized execution plan.
"""
import logging
from strands import Agent
from strands.models.bedrock import BedrockModel
from app.config import get_settings

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a B2B sales research planning specialist. Given a company profile, existing signals,
and research configuration, you must plan which research activities to conduct and in what order.

## Your Task

Analyze the company and return a JSON research plan. Consider:
1. Company size, industry, and region — determines which data sources are relevant
2. Existing signals — avoid re-discovering what's already known
3. Research depth — standard (quick scan), deep (thorough), comprehensive (exhaustive)
4. Signal hints — user-provided areas of interest guide prioritization

## Available Research Agents

1. **signal_discovery** — General signal detection (funding, press, partnerships, expansion)
2. **hiring_intelligence** — Job posting analysis, hiring velocity, department concentration
3. **executive_intelligence** — Leadership changes, champion movements, board changes
4. **competitive_intelligence** — Vendor stack mapping, displacement opportunities
5. **tech_stack_intelligence** — Technology adoption, migrations, infrastructure signals
6. **research_synthesis** — Combines all findings into a structured brief

## Output Format (JSON only)

```json
{
  "research_plan": [
    {
      "agent": "signal_discovery",
      "priority": 1,
      "reason": "No recent signals detected — need baseline scan",
      "estimated_tool_calls": 6,
      "estimated_time_sec": 20
    }
  ],
  "parallel_groups": [[0, 1, 2], [3, 4], [5]],
  "skip_reasons": {
    "competitive_intelligence": "Company is small startup, limited public vendor data"
  },
  "total_estimated_cost_usd": 0.25,
  "total_estimated_time_sec": 60
}
```

Return ONLY valid JSON. No explanation outside the JSON."""


def create_research_planner_agent(callback_handler=None) -> Agent:
    settings = get_settings()
    model = BedrockModel(
        model_id=settings.BEDROCK_MODEL_ID,
        region_name=settings.AWS_REGION,
        max_tokens=4000,
    )
    kwargs = {"model": model, "system_prompt": SYSTEM_PROMPT, "tools": []}
    if callback_handler:
        kwargs["callback_handler"] = callback_handler
    return Agent(**kwargs)


def build_planner_prompt(company: dict, existing_signals: list, config: dict) -> str:
    import json
    return f"""Plan research for this company:

## Company
{json.dumps(company, indent=2, default=str)}

## Existing Signals ({len(existing_signals)} found)
{json.dumps(existing_signals[:10], indent=2, default=str) if existing_signals else "None detected yet."}

## Configuration
Research depth: {config.get('research_depth', 'standard')}
Signal hints: {json.dumps(config.get('signal_hints', {}), default=str)}

Create the research plan now."""
