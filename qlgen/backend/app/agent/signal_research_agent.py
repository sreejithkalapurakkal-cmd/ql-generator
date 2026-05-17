"""Dedicated signal research agent for tracking list companies.

Reuses tools from the pipeline Stage 3 agent but with a signal-detection-focused
system prompt. Returns structured SignalEvent-compatible JSON.
"""
import logging

from strands import Agent
from strands.models.bedrock import BedrockModel

from app.config import get_settings

logger = logging.getLogger(__name__)


SIGNAL_RESEARCH_SYSTEM_PROMPT = """You are a B2B signal intelligence specialist. Your job is to research companies
and identify actionable sales signals — events and changes that indicate a company may be ready to buy.

## Signal Categories to Research

For EACH company, research ALL of the following signal categories:

1. **funding** — Funding rounds, Series A/B/C/D, venture investments, IPO filings, secondary offerings
2. **hiring_surge** — Significant hiring activity, new departments, job posting volume increases
3. **executive_change** — New C-suite appointments, VP-level hires, board changes
4. **tech_adoption** — New technology deployments, platform migrations, vendor switches
5. **product_launch** — New products, features, service lines, or market entries
6. **earnings_report** — Quarterly results, revenue growth/decline, margin changes
7. **press_mention** — Significant press coverage, industry awards, analyst mentions
8. **partnership** — Strategic partnerships, alliances, joint ventures, channel partnerships
9. **expansion** — New offices, geographic expansion, market entry, M&A
10. **competitor_adoption** / **competitor_churn** — Competitors winning/losing similar deals

## Custom Signal Hints (if provided)

If budget_signals, urgency_signals, or custom_hints are provided, research those SPECIFIC topics
in ADDITION to the standard categories above. These hints represent what the sales team cares about most.

## Research Requirements

- Use AT LEAST 3-4 different tools per company for depth
- Prioritize RECENT evidence (< 3 months old)
- Always include evidence_date (YYYY-MM-DD) when available
- Include source_url for every signal found
- Rate signal strength 0-100 (100 = strongest evidence)

## Priority Classification

- **critical**: Immediate opportunity — funding just announced, executive just hired, RFP active
- **high**: Strong signal — recent hiring surge, tech migration underway, expansion announced
- **medium**: Moderate signal — press mention, partnership announced, steady growth
- **low**: Weak signal — old news, indirect evidence, speculation

## Output Format

Return a JSON object with this exact structure:

```json
{
  "companies": [
    {
      "company_name": "Company Name",
      "domain": "company.com",
      "signals": [
        {
          "signal_type": "funding",
          "signal_subtype": "series_b",
          "signal_category": "financial",
          "priority": "critical",
          "strength": 92,
          "title": "Acme Corp raises $50M Series B",
          "summary": "Detailed summary of the signal with evidence...",
          "evidence_date": "2026-04-15",
          "source_tool": "tavily_search",
          "source_url": "https://techcrunch.com/..."
        }
      ]
    }
  ]
}
```

IMPORTANT: Return ONLY valid JSON. Do not include markdown formatting or explanation outside the JSON.
"""


def create_signal_research_agent(callback_handler=None, disabled_tools: set[str] | None = None) -> Agent:
    """Create the dedicated signal research agent.

    Reuses the same 15 research tools from the pipeline Stage 3 agent
    but with a system prompt focused on signal detection (not scoring).
    """
    settings = get_settings()
    model = BedrockModel(
        model_id=settings.BEDROCK_MODEL_ID,
        region_name=settings.AWS_REGION,
        max_tokens=32000,
    )

    # Import tools (same as pipeline Stage 3)
    from app.tools.sec_tool import get_sec_filings
    from app.tools.simfin_tool import get_financial_statements
    from app.tools.market_data_tool import get_market_data
    from app.tools.fmp_tool import get_investor_data
    from app.tools.news_sentiment_tool import get_news_sentiment
    from app.tools.exa_tool import exa_search, search_press_releases, search_job_postings
    from app.tools.exa_tool import search_patents_by_technology, search_producthunt
    from app.tools.tavily_tool import tavily_search
    from app.tools.duckduckgo_tool import duckduckgo_search
    from app.tools.web_scraper_tool import scrape_webpage
    from app.tools.world_bank_tool import get_economic_indicators

    try:
        from app.tools.google_tool import google_custom_search
    except ImportError:
        google_custom_search = None

    all_tools = [
        get_sec_filings,
        get_financial_statements,
        get_market_data,
        get_investor_data,
        get_news_sentiment,
        search_press_releases,
        search_job_postings,
        search_patents_by_technology,
        search_producthunt,
        tavily_search,
        exa_search,
        duckduckgo_search,
        scrape_webpage,
        get_economic_indicators,
    ]
    if google_custom_search:
        all_tools.append(google_custom_search)

    # Filter disabled tools
    if disabled_tools:
        tools = [t for t in all_tools if getattr(t, '__name__', '') not in disabled_tools]
    else:
        tools = all_tools

    kwargs = {
        "model": model,
        "system_prompt": SIGNAL_RESEARCH_SYSTEM_PROMPT,
        "tools": tools,
    }
    if callback_handler is not None:
        kwargs["callback_handler"] = callback_handler

    return Agent(**kwargs)


def build_signal_research_prompt(
    companies: list[dict],
    signal_hints: dict | None = None,
) -> str:
    """Build the user prompt for the signal research agent.

    Args:
        companies: List of dicts with keys: company_name, domain, industry
        signal_hints: Optional dict with budget_signals, urgency_signals, custom_hints
    """
    company_lines = []
    for i, c in enumerate(companies, 1):
        name = c.get("company_name") or c.get("canonical_name") or "Unknown"
        domain = c.get("domain") or c.get("normalized_domain") or ""
        industry = c.get("industry") or ""
        company_lines.append(f"  {i}. {name} | {domain} | {industry}")

    hints_section = ""
    if signal_hints:
        parts = []
        if signal_hints.get("budget_signals"):
            parts.append(f"BUDGET SIGNALS to research: {', '.join(signal_hints['budget_signals'])}")
        if signal_hints.get("urgency_signals"):
            parts.append(f"URGENCY SIGNALS to research: {', '.join(signal_hints['urgency_signals'])}")
        if signal_hints.get("custom_hints"):
            parts.append(f"CUSTOM RESEARCH TOPICS: {', '.join(signal_hints['custom_hints'])}")
        if parts:
            hints_section = "\n\n## Custom Signal Hints\n" + "\n".join(parts)

    return f"""Research signals for the following {len(companies)} companies:

COMPANIES:
{chr(10).join(company_lines)}
{hints_section}

For each company, use at least 3-4 different tools and look for ALL signal categories.
Focus on RECENT events (last 3 months preferred). Return the results as JSON."""
