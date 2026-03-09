import asyncio
import json
import logging

import boto3

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

_bedrock_client = None

ICP_CONFIG_KEYS = [
    "target_offering",
    "regions",
    "industry_types",
    "company_size",
    "technology_maturity",
    "infrastructure_readiness",
    "digital_transformation_drivers",
    "leadership_traits",
]

ICP_GENERATION_SYSTEM_PROMPT = """You are an expert B2B sales strategist. Given a natural language description of an ideal customer, generate a structured ICP (Ideal Customer Profile) configuration as a JSON object.

Return ONLY a JSON object with exactly these keys:
- "name": A short descriptive name for this ICP (e.g., "MidMarket US ECommerce 2026")
- "description": A one-sentence summary of the ICP
- "config": An object with exactly these 8 keys:

1. "target_offering" (array of strings): The products/services being sold
2. "regions": {"countries": [strings], "priority_areas": [strings like states/cities]}
3. "industry_types": [{"vertical": string, "sub_vertical": string or null}] - at least 1 entry
4. "company_size": {"employees_min": int, "employees_max": int, "revenue_min": int, "revenue_max": int, "revenue_currency": "USD"|"EUR"|"GBP"|"INR"}
5. "technology_maturity": {"signals": [strings], "negative_signals": [strings]}
6. "infrastructure_readiness": {"indicators": [strings]}
7. "digital_transformation_drivers": {"growth_triggers": [strings], "operational_pains": [strings], "competitive_pressures": [strings], "strategic_initiatives": [strings]}
8. "leadership_traits": {"target_roles": [strings], "behavioral_traits": [strings]}

Rules:
- All array fields must have at least 1 item
- Use sensible defaults: "mid-market" = 100-2000 employees, "enterprise" = 2000+, "SMB" = 10-200
- Revenue should be in whole numbers (e.g., 10000000 for $10M)
- If the user doesn't specify a region, default to "United States"
- If the user doesn't specify a currency, default to "USD"
- Generate 3-5 items per array field based on the description
- Return ONLY the JSON object, no markdown fences, no explanation"""


def _get_bedrock_client():
    global _bedrock_client
    if _bedrock_client is None:
        _bedrock_client = boto3.client(
            "bedrock-runtime",
            region_name=settings.AWS_REGION,
        )
    return _bedrock_client


def _extract_json_from_response(text: str) -> dict:
    """Extract JSON from response text, stripping markdown fences if present."""
    text = text.strip()

    # Strip markdown code fences
    if text.startswith("```"):
        first_newline = text.find("\n")
        if first_newline != -1:
            text = text[first_newline + 1:]
        closing = text.rfind("```")
        if closing != -1:
            text = text[:closing]
        text = text.strip()

    # Find outermost JSON object by brace-depth matching
    if "{" not in text:
        raise ValueError("No JSON object found in response")

    start = text.index("{")
    depth = 0
    for i, char in enumerate(text[start:], start):
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return json.loads(text[start:i + 1])

    # If we didn't find matching braces, try parsing from start of {
    return json.loads(text[start:])


def _validate_icp_structure(parsed: dict) -> dict:
    """Validate and normalize the parsed ICP structure."""
    # If Claude returned the config directly without name/description wrapper
    if "config" not in parsed and any(k in parsed for k in ICP_CONFIG_KEYS):
        parsed = {
            "name": "AI Generated ICP",
            "description": None,
            "config": parsed,
        }

    if "config" not in parsed:
        raise ValueError("Response missing 'config' key")

    config = parsed["config"]

    # Ensure all 8 required keys exist
    for key in ICP_CONFIG_KEYS:
        if key not in config:
            raise ValueError(f"Config missing required key: {key}")

    # Coerce numeric fields in company_size to int
    size = config.get("company_size", {})
    for field in ["employees_min", "employees_max", "revenue_min", "revenue_max"]:
        if field in size:
            try:
                size[field] = int(size[field])
            except (ValueError, TypeError):
                pass

    return parsed


def generate_icp_config(description: str) -> dict:
    """Call Bedrock to generate an ICP config from a natural language description."""
    client = _get_bedrock_client()

    body = json.dumps({
        "anthropic_version": "bedrock-2023-05-31",
        "system": ICP_GENERATION_SYSTEM_PROMPT,
        "messages": [
            {"role": "user", "content": description}
        ],
        "max_tokens": 4096,
        "temperature": 0.3,
    })

    response = client.invoke_model(
        modelId=settings.BEDROCK_MODEL_ID,
        body=body,
        contentType="application/json",
        accept="application/json",
    )

    result = json.loads(response["body"].read())
    text = result["content"][0]["text"]

    parsed = _extract_json_from_response(text)
    validated = _validate_icp_structure(parsed)

    return validated


async def generate_icp_config_async(description: str) -> dict:
    """Async wrapper around generate_icp_config."""
    return await asyncio.to_thread(generate_icp_config, description)
