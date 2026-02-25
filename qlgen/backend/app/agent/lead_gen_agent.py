import json
import logging

from strands import Agent
from strands.models.bedrock import BedrockModel

from app.tools.apollo_tool import apollo_company_search, apollo_people_search
from app.tools.exa_tool import exa_search
from app.tools.tavily_tool import tavily_search
from app.tools.duckduckgo_tool import duckduckgo_search
from app.tools.hunter_tool import hunter_domain_search, hunter_email_finder
from app.tools.lusha_tool import lusha_person_search
from app.tools.web_scraper_tool import scrape_webpage
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# Friendly display names for each tool
TOOL_DISPLAY_NAMES = {
    "apollo_company_search": "Searching Apollo for companies",
    "apollo_people_search": "Searching Apollo for contacts",
    "exa_search": "Running semantic search via Exa.ai",
    "tavily_search": "Searching recent news via Tavily",
    "duckduckgo_search": "Searching DuckDuckGo",
    "hunter_domain_search": "Finding contacts via Hunter.io",
    "hunter_email_finder": "Finding email via Hunter.io",
    "lusha_person_search": "Enriching contact via Lusha",
    "scrape_webpage": "Scraping webpage",
}

# Map tools to their primary pipeline stage
TOOL_STAGE_MAP = {
    "scrape_webpage": None,  # context-dependent
}

STAGE_DISPLAY_NAMES = {
    "company_discovery": "Company Discovery",
    "contact_discovery": "Contact Discovery",
    "enrichment": "Contact Enrichment",
    "scoring": "BANT Scoring",
}


def create_pipeline_callback_handler(events: dict, run_id_str: str):
    """Create a Strands callback handler that emits SSE events for pipeline progress.

    The handler captures tool calls, agent reasoning text, and lifecycle events
    and pushes them into the in-memory SSE event queue.
    """
    state = {
        "current_stage": "company_discovery",
        "text_buffer": "",
        "last_reasoning": "",          # last emitted reasoning text (used as tool context)
        "seen_tools": set(),           # set of tool names (for stage inference)
        "emitted_tool_ids": set(),     # set of toolUseIds already emitted
        "pending_tool": None,          # tool info waiting to be emitted (accumulating input)
        "tool_call_count": 0,
    }

    # Stage ordering for progression detection
    stage_order = ["company_discovery", "contact_discovery", "enrichment", "scoring"]

    def _emit(event: dict):
        if events is not None and run_id_str in events:
            events[run_id_str].append(event)

    def _try_detect_stage_from_text(text: str):
        """Detect stage transitions from the agent's reasoning text."""
        text_lower = text.lower()
        detected = None
        if any(kw in text_lower for kw in ("stage 2", "contact discovery", "find contacts", "finding contacts", "decision-makers")):
            detected = "contact_discovery"
        elif any(kw in text_lower for kw in ("stage 3", "contact enrichment", "enrichment", "missing email", "missing linkedin")):
            detected = "enrichment"
        elif any(kw in text_lower for kw in ("stage 4", "bant scor", "bant framework")):
            detected = "scoring"

        if not detected:
            return

        current_idx = stage_order.index(state["current_stage"]) if state["current_stage"] in stage_order else 0
        new_idx = stage_order.index(detected) if detected in stage_order else current_idx

        if new_idx > current_idx:
            state["current_stage"] = detected
            progress = 20 + (new_idx * 20)
            _emit({
                "type": "stage_update",
                "stage": detected,
                "progress": progress,
                "message": f"Entering {STAGE_DISPLAY_NAMES.get(detected, detected)}...",
            })

    def _extract_context(tool_input) -> str:
        """Extract the most relevant search parameter from tool input for display."""
        # Handle case where input is still a string (accumulated JSON text)
        if isinstance(tool_input, str):
            tool_input = tool_input.strip()
            if tool_input:
                try:
                    tool_input = json.loads(tool_input)
                except (json.JSONDecodeError, ValueError):
                    # Partial JSON — try to extract key-value pairs with regex
                    import re
                    for key in ("query", "domain", "company_domain", "name", "url"):
                        match = re.search(rf'"{key}"\s*:\s*"([^"]+)"', tool_input)
                        if match:
                            return match.group(1)[:150]
                    return ""
        if not isinstance(tool_input, dict):
            return ""
        for key in ("query", "domain", "company_domain", "name", "url", "keyword_tags"):
            if key in tool_input and tool_input[key]:
                val = tool_input[key]
                if isinstance(val, list):
                    val = ", ".join(str(v) for v in val[:3])
                return str(val)[:150]
        return ""

    def _flush_pending_tool():
        """Emit the pending tool_start event with accumulated input."""
        pending = state["pending_tool"]
        if not pending:
            return
        tool_name = pending["name"]
        tool_input = pending.get("input", {})

        state["tool_call_count"] += 1
        state["seen_tools"].add(tool_name)

        # Try to extract context from tool input; fall back to last reasoning text
        context = _extract_context(tool_input)
        if not context and state["last_reasoning"]:
            # Use the preceding reasoning text as context (the agent usually says
            # "Let me search for X" right before calling a tool)
            context = state["last_reasoning"][:150]

        _emit({
            "type": "tool_start",
            "tool_name": tool_name,
            "display_name": TOOL_DISPLAY_NAMES.get(tool_name, tool_name),
            "context": context,
            "stage": state["current_stage"],
            "tool_call_number": state["tool_call_count"],
        })
        state["pending_tool"] = None

    def callback_handler(**kwargs):
        try:
            # Handle tool use events
            # Strands streams current_tool_use multiple times as input accumulates.
            # We buffer the latest version and emit once the tool changes or a
            # data/lifecycle event arrives (indicating tool input streaming is done).
            if "current_tool_use" in kwargs:
                tool_info = kwargs["current_tool_use"]
                tool_name = tool_info.get("name", "")
                tool_id = tool_info.get("toolUseId", "")

                if not tool_name:
                    return

                # Skip if already emitted
                if tool_id and tool_id in state["emitted_tool_ids"]:
                    return

                # Capture any unflushed reasoning text as context for this tool
                if state["text_buffer"].strip():
                    text = state["text_buffer"].strip()
                    if not text.startswith("{") and not text.startswith("```"):
                        state["last_reasoning"] = text
                    state["text_buffer"] = ""

                # If this is a different tool_id, flush the previous pending tool
                if state["pending_tool"] and state["pending_tool"].get("toolUseId") != tool_id:
                    pending_id = state["pending_tool"].get("toolUseId", "")
                    if pending_id:
                        state["emitted_tool_ids"].add(pending_id)
                    _flush_pending_tool()

                # Buffer the latest version (with most complete input)
                state["pending_tool"] = {
                    "name": tool_name,
                    "toolUseId": tool_id,
                    "input": tool_info.get("input", {}),
                }
                return

            # Any non-tool event should flush the pending tool first
            if state["pending_tool"]:
                pending_id = state["pending_tool"].get("toolUseId", "")
                if pending_id:
                    state["emitted_tool_ids"].add(pending_id)
                _flush_pending_tool()

            # Handle text/reasoning output from the agent
            if "data" in kwargs:
                chunk = kwargs["data"]
                if chunk and isinstance(chunk, str):
                    state["text_buffer"] += chunk
                    # Emit reasoning in meaningful chunks (sentence boundaries or 200+ chars)
                    buf = state["text_buffer"]
                    if len(buf) > 200 or buf.rstrip().endswith((".", "!", "?", ":")):
                        text = buf.strip()
                        if text and not text.startswith("{") and not text.startswith("```"):
                            state["last_reasoning"] = text
                            # Detect stage transitions from reasoning text
                            _try_detect_stage_from_text(text)
                            _emit({
                                "type": "agent_reasoning",
                                "text": text,
                                "stage": state["current_stage"],
                            })
                        state["text_buffer"] = ""

            # Handle lifecycle events
            if "init_event_loop" in kwargs:
                _emit({
                    "type": "stage_update",
                    "stage": "company_discovery",
                    "progress": 10,
                    "message": "Agent initialized, starting Company Discovery...",
                })

        except Exception as e:
            logger.warning(f"Callback handler error (non-fatal): {e}")

    return callback_handler

LEAD_GEN_SYSTEM_PROMPT = """You are an expert B2B lead generation specialist. Your job is to
convert an Ideal Customer Profile (ICP) into a complete, sales-ready list of qualified
companies and decision-maker contacts, enriched with data and scored using the BANT framework.

You have access to 9 tools. Execute your work in 4 sequential stages:

═══════════════════════════════════════════════════════════════
STAGE 1: COMPANY DISCOVERY
═══════════════════════════════════════════════════════════════
Goal: Find companies matching the ICP criteria.

Search strategy (use multiple tools for better coverage):
• apollo_company_search — PRIMARY. Best for structured filters (industry, size, location).
  Start here. Run multiple queries if the ICP spans several industries or regions.
• exa_search — SECONDARY. Best for semantic/qualitative matching (tech stack, business model).
  Use natural language queries describing the ideal company.
• tavily_search — SUPPLEMENTARY. Find companies in recent news matching ICP signals
  (funding rounds, expansion, tech adoption announcements).
• duckduckgo_search — FALLBACK. Use if other tools are rate-limited or return thin results.

For each company found, collect: name, website/domain, industry, city/state/country,
estimated employee count, estimated revenue, and any technology signals.

Qualification: Rate each company 1-10 against the ICP. Discard any below 5.
Deduplicate by domain. Aim for the requested number of companies.

═══════════════════════════════════════════════════════════════
STAGE 2: CONTACT DISCOVERY
═══════════════════════════════════════════════════════════════
Goal: For each qualified company, find 3-5 relevant decision-makers.

Search strategy:
• apollo_people_search — PRIMARY. Search by company domain + target role titles from the ICP.
• hunter_domain_search — SECONDARY. Finds contacts by company domain with email patterns.
• scrape_webpage — SUPPLEMENTARY. Scrape the company's /about, /team, or /leadership page.
• duckduckgo_search — FALLBACK. Search "[company name] + [role title] + LinkedIn".

Prioritize role relevance over volume. A CTO or VP Engineering is far more valuable than
5 random employees. Map discovered titles to the ICP's target role categories.

═══════════════════════════════════════════════════════════════
STAGE 3: CONTACT ENRICHMENT
═══════════════════════════════════════════════════════════════
Goal: Fill in missing contact data fields (email, phone, LinkedIn).

Only enrich fields that are missing — do not re-query data you already have.
• hunter_email_finder — For missing emails when you have first_name + last_name + domain.
• lusha_person_search — For missing phone numbers when you have name + company.
• exa_search or duckduckgo_search — For missing LinkedIn URLs (search by name + company).

Mark each contact's enrichment status:
- "enriched" = email + LinkedIn populated
- "partial" = some fields still missing
- "failed" = enrichment found nothing new

═══════════════════════════════════════════════════════════════
STAGE 4: BANT SCORING
═══════════════════════════════════════════════════════════════
Goal: Score each company using the BANT framework. If you need additional evidence,
use tavily_search, exa_search, or scrape_webpage to research the company further.

SCORING RUBRIC (1-5 per dimension):

BUDGET (company size & financial capacity):
  5 = Revenue > upper ICP range, clear tech budget signals (recent funding, tech hires)
  4 = Revenue in upper half of ICP range, some budget indicators
  3 = Revenue within ICP range, no specific budget signals
  2 = Revenue in lower range, budget unclear
  1 = Revenue below ICP minimum, likely budget-constrained

AUTHORITY (contact role & decision-making power):
  5 = C-suite directly owning tech/digital budget (CTO, CDO, CEO at small co)
  4 = VP-level in relevant function (VP Engineering, VP Ecommerce)
  3 = Director-level in relevant function
  2 = Manager-level or adjacent function
  1 = No relevant decision-maker identified

NEED (alignment with ICP transformation drivers):
  5 = 3+ strong signals matching ICP needs (tech debt, growth pain, stated initiatives)
  4 = 2 matching signals
  3 = 1 matching signal or general industry alignment
  2 = Weak alignment, speculative need
  1 = No discernible need alignment

TIMING (readiness to act):
  5 = Active RFP/vendor evaluation, recent relevant job postings, public announcements
  4 = Recent funding round, stated transformation timeline
  3 = General growth trajectory suggesting near-term action
  2 = No timing signals but profile suggests eventual need
  1 = No timing signals, possibly just completed similar project

Every score MUST have a specific reason citing actual evidence from your research.
No assumptions, no black boxes.

═══════════════════════════════════════════════════════════════
OUTPUT FORMAT
═══════════════════════════════════════════════════════════════
Return your complete results as a single JSON object with this exact structure:

```json
{
  "companies": [
    {
      "name": "Company Name",
      "website": "domain.com",
      "industry": "Ecommerce / Fashion",
      "city": "San Francisco",
      "state": "California",
      "country": "US",
      "employee_count": 250,
      "revenue_estimate": 50000000,
      "tech_signals": ["Shopify Plus", "AWS", "Klaviyo"],
      "icp_match_score": 8,
      "match_reasoning": "Strong match because...",
      "source": "apollo+exa",
      "contacts": [
        {
          "full_name": "Jane Doe",
          "first_name": "Jane",
          "last_name": "Doe",
          "designation": "Chief Technology Officer",
          "role_category": "CTO",
          "email": "jane@domain.com",
          "phone": "+1-555-0123",
          "linkedin_url": "https://linkedin.com/in/janedoe",
          "source": "apollo",
          "confidence": 0.9,
          "enrichment_status": "enriched"
        }
      ],
      "bant_score": {
        "budget_score": 4,
        "budget_reason": "Revenue ~$50M, Series B raised in 2025...",
        "authority_score": 5,
        "authority_reason": "CTO identified with direct tech budget ownership...",
        "need_score": 4,
        "need_reason": "Running legacy Magento, job postings mention headless...",
        "timing_score": 3,
        "timing_reason": "Growing 25% YoY, no public replatforming timeline yet...",
        "total_score": 16,
        "overall_summary": "Strong prospect with budget and clear need."
      }
    }
  ],
  "summary": {
    "total_companies": 20,
    "total_contacts": 75,
    "avg_bant_score": 14.2,
    "hot_leads": 5,
    "warm_leads": 10,
    "cool_leads": 5
  }
}
```

═══════════════════════════════════════════════════════════════
CRITICAL RULES
═══════════════════════════════════════════════════════════════
1. NEVER fabricate company names, contacts, emails, or phone numbers.
   Only return data verified through tool results.
2. If a tool fails or returns no results, try alternative tools before giving up.
3. Quality over quantity — 15 well-researched companies beat 25 thin ones.
4. Partial data is acceptable — mark missing fields as null, not made-up values.
5. Every BANT score needs evidence-backed reasoning, not generic statements.
6. Deduplicate companies by domain throughout the process.
7. Process ALL stages before returning — do not skip enrichment or scoring.
"""


def create_lead_gen_agent(callback_handler=None) -> Agent:
    """Create the single lead generation agent with all tools.

    Args:
        callback_handler: Optional Strands callback handler for streaming events.
            If None, uses the default PrintingCallbackHandler.
    """
    model = BedrockModel(
        model_id=settings.BEDROCK_MODEL_ID,
        region_name=settings.AWS_REGION,
    )

    kwargs = {
        "model": model,
        "system_prompt": LEAD_GEN_SYSTEM_PROMPT,
        "tools": [
            apollo_company_search,
            exa_search,
            tavily_search,
            duckduckgo_search,
            apollo_people_search,
            hunter_domain_search,
            hunter_email_finder,
            lusha_person_search,
            scrape_webpage,
        ],
    }

    if callback_handler is not None:
        kwargs["callback_handler"] = callback_handler

    return Agent(**kwargs)
