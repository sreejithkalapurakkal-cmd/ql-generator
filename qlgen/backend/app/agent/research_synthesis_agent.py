"""Research Synthesis Agent.

Pure synthesis agent (no tools) that combines all specialist agent outputs
into a structured 8-section research brief with citations and confidence scores.
"""
import logging
from strands import Agent
from strands.models.bedrock import BedrockModel
from app.config import get_settings

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a research synthesis specialist. You receive outputs from multiple
specialist research agents and synthesize them into a structured 8-section research brief.

## Your Task

Combine all provided research data into a coherent, actionable brief. Cross-reference
findings across agents to identify correlations and patterns.

## Brief Sections (generate all 8)

1. **overview** — Company Overview: size, industry, key facts, public/private
2. **org** — Org Structure & Key Contacts: decision makers, reporting lines
3. **signals** — Recent Signals: detected signals with evidence and timing
4. **competitive** — Competitive Landscape: vendor stack, evaluations, displacement
5. **tech** — Tech Stack & Infrastructure: technologies, migrations, patterns
6. **budget** — Budget & Spend Indicators: disclosed budgets, procurement cycles
7. **why-now** — Why Now: timing analysis, urgency windows, optimal outreach period
8. **angle** — Recommended Angle: opening hooks, key messages, proof points

## Output Format (JSON)

```json
{
  "sections": [
    {
      "id": "overview",
      "heading": "Company Overview",
      "body": "Text with inline citations [1] referencing sources below...",
      "bullets": ["Key fact 1", "Key fact 2"],
      "sources": [
        {"label": "Source Name", "source_class": "press_release", "url": "https://...", "date": "2026-04-15"}
      ],
      "insufficient": false,
      "confidence": 0.85
    }
  ],
  "correlations_found": [
    "CDO appointment + hiring surge suggests new data initiative"
  ],
  "word_count": 920
}
```

## Rules
- Every claim MUST be backed by evidence from the provided data
- Use inline citations [1], [2], etc. that correspond to sources array
- If insufficient data for a section, set insufficient=true and explain what's missing
- Cross-reference findings: hiring data + executive changes + tech signals = patterns
- The "Why Now" and "Angle" sections require strategic reasoning, not just data compilation

Return ONLY valid JSON."""


def create_research_synthesis_agent(callback_handler=None) -> Agent:
    settings = get_settings()
    model = BedrockModel(
        model_id=settings.BEDROCK_MODEL_ID,
        region_name=settings.AWS_REGION,
        max_tokens=32000,
    )
    kwargs = {"model": model, "system_prompt": SYSTEM_PROMPT, "tools": []}
    if callback_handler:
        kwargs["callback_handler"] = callback_handler
    return Agent(**kwargs)


def build_synthesis_prompt(
    company: dict,
    signals: list,
    hiring_data: dict | None = None,
    executive_data: dict | None = None,
    competitive_data: dict | None = None,
    tech_stack_data: dict | None = None,
) -> str:
    import json
    parts = [f"Synthesize a research brief for this company:\n\n## Company\n{json.dumps(company, indent=2, default=str)}"]

    if signals:
        parts.append(f"\n## Detected Signals ({len(signals)})\n{json.dumps(signals[:20], indent=2, default=str)}")
    if hiring_data:
        parts.append(f"\n## Hiring Intelligence\n{json.dumps(hiring_data, indent=2, default=str)}")
    if executive_data:
        parts.append(f"\n## Executive Intelligence\n{json.dumps(executive_data, indent=2, default=str)}")
    if competitive_data:
        parts.append(f"\n## Competitive Intelligence\n{json.dumps(competitive_data, indent=2, default=str)}")
    if tech_stack_data:
        parts.append(f"\n## Tech Stack Intelligence\n{json.dumps(tech_stack_data, indent=2, default=str)}")

    parts.append("\n\nGenerate the 8-section research brief now as JSON.")
    return "\n".join(parts)
