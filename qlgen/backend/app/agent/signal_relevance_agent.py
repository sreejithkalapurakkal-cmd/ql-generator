"""Signal Relevance Agent.

A lightweight, TOOL-LESS LLM judge that decides whether a candidate sales
signal is genuinely about a specific target company — as opposed to a
different company that shares a similar name, generic industry news, or a
namesake person/product/place.

Unlike the confidence_verification_agent (which does web research to assess
how *credible* a claim is), this agent does no searching. It judges the
already-collected evidence against the target company's identity, so it is a
single fast LLM call with no tool loop.
"""
import logging

from strands import Agent
from strands.models.bedrock import BedrockModel

from app.config import get_settings

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a signal relevance validator for B2B sales intelligence.

You are given a TARGET COMPANY (its name and website domain) and a list of
candidate sales signals. Each candidate has a title, summary, source URL, and
evidence snippets gathered from the web. For EACH candidate, decide whether the
signal is genuinely about the TARGET COMPANY.

Mark a signal as NOT relevant (relevant=false) when:
- It is about a DIFFERENT company that shares a similar or identical name
  (name collision — e.g. "Apollo" the sales-CRM vs "Apollo" the tyre maker).
- It is generic industry, market, or macroeconomic news not specific to the
  target company.
- It is about a person, product, place, or fictional entity that merely shares
  the name.
- The evidence does not actually mention or concern the target company.

Treat the website DOMAIN as the strongest disambiguator: evidence that comes
from, links to, or unambiguously refers to that company/domain is relevant.
Be strict — if the evidence does not clearly tie to THIS specific company,
mark it relevant=false.

## Output Format

Return ONLY valid JSON, no prose, no code fences, in exactly this shape:

{"verdicts": [{"index": 0, "relevant": true, "confidence": 0.9, "reason": "short reason"}]}

Rules:
- Include EXACTLY ONE verdict object per candidate.
- "index" must match the candidate's given index.
- "relevant" is a boolean.
- "confidence" is a number from 0.0 to 1.0.
- "reason" is one short sentence.
Return ONLY the JSON object."""


def create_signal_relevance_agent(callback_handler=None) -> Agent:
    """Create the tool-less relevance-judging agent."""
    settings = get_settings()
    model = BedrockModel(
        model_id=settings.BEDROCK_MODEL_ID,
        region_name=settings.AWS_REGION,
        max_tokens=4000,
    )
    kwargs = {"model": model, "system_prompt": SYSTEM_PROMPT}
    if callback_handler:
        kwargs["callback_handler"] = callback_handler
    return Agent(**kwargs)
