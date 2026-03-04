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


def create_pipeline_callback_handler(events: dict, run_id_str: str, event_collector: list = None):
    """Create a Strands callback handler that emits SSE events for pipeline progress.

    The handler captures tool calls, agent reasoning text, and lifecycle events
    and pushes them into the in-memory SSE event queue. If event_collector is
    provided, events are also appended there for later DB persistence.
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
        if event_collector is not None:
            event_collector.append(event)

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

            # Handle tool result events
            if "tool_result" in kwargs:
                result = kwargs["tool_result"]
                tool_name = result.get("name", "unknown")
                content = result.get("content", "")
                is_error = bool(result.get("error") or result.get("status") == "error")
                # Truncate long results for log readability
                if isinstance(content, str) and len(content) > 500:
                    content_preview = content[:500] + "... [truncated]"
                elif isinstance(content, (list, dict)):
                    try:
                        content_preview = json.dumps(content, default=str)[:500]
                        if len(json.dumps(content, default=str)) > 500:
                            content_preview += "..."
                    except Exception:
                        content_preview = str(content)[:500]
                else:
                    content_preview = str(content)[:500] if content else ""

                if is_error:
                    _emit({
                        "type": "tool_error",
                        "tool_name": tool_name,
                        "error_message": content_preview[:300],
                        "stage": state["current_stage"],
                        "tool_call_number": state["tool_call_count"],
                    })
                else:
                    _emit({
                        "type": "tool_result",
                        "tool_name": tool_name,
                        "result_preview": content_preview,
                        "stage": state["current_stage"],
                        "tool_call_number": state["tool_call_count"],
                        "success": True,
                    })

            # Handle text/reasoning output from the agent
            if "data" in kwargs:
                chunk = kwargs["data"]
                if chunk and isinstance(chunk, str):
                    state["text_buffer"] += chunk
                    # Emit reasoning in smaller chunks for finer granularity
                    buf = state["text_buffer"]
                    if len(buf) > 80 or buf.rstrip().endswith((".", "!", "?", ":")):
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

            # Handle lifecycle events — also flush any remaining text buffer
            if "init_event_loop" in kwargs:
                # Flush remaining buffered reasoning text
                if state["text_buffer"].strip():
                    text = state["text_buffer"].strip()
                    if not text.startswith("{") and not text.startswith("```"):
                        _emit({
                            "type": "agent_reasoning",
                            "text": text,
                            "stage": state["current_stage"],
                        })
                    state["text_buffer"] = ""
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

You have access to 9 tools. Execute your work in 4 sequential stages.

═══════════════════════════════════════════════════════════════
ADVANCED SEARCH TECHNIQUES — Use these across ALL stages:
═══════════════════════════════════════════════════════════════

a) GOOGLE DORKING: Use duckduckgo_search with targeted operators:
   - site:linkedin.com/in "[company name]" "[role title]" — find specific contacts
   - site:crunchbase.com "[company name]" — find funding/revenue data
   - "[company name]" filetype:pdf annual report — find financial reports
   - "[company name]" "press release" (funding OR acquisition OR partnership) — find news
   - site:[company domain] (about OR team OR leadership OR careers) — find internal pages

b) FINANCIAL DATA RESEARCH: For each company, attempt to find:
   - Revenue & growth data: Search "[company name] revenue" or "[company name] annual report"
   - Stock/funding data: Search "[company name] site:crunchbase.com" or
     "[company name] funding round" or "[company name] stock price"
   - Press releases: Search "[company name] press release 2025 2026"
   - For public companies: tavily_search "[company name] SEC filing 10-K" or
     "[company name] Yahoo Finance" for financial summaries
   - Use scrape_webpage on the company's /about, /press, /investors, /newsroom pages

c) JOB POSTING ANALYSIS: Search "[company name] careers [technology]" to infer:
   - Tech stack (what they're hiring for)
   - Growth signals (volume of hiring)
   - Transformation signals (new technology roles)

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

IMPORTANT: Do NOT discard a company solely because contact information is sparse.
A company with strong ICP match but few contacts is still valuable — contacts can
be enriched in Stage 2-3. Only discard companies that fail the ICP criteria match
(score below 5).

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

If standard contact search tools return limited results for a company, use these
fallback techniques:
- duckduckgo_search "site:linkedin.com/in [company name] [target role]"
- scrape_webpage on company's /team, /about, /leadership pages
- exa_search "[company name] [role title]" to find mentions in articles/interviews
- If no contacts found at all, keep the company with an empty contacts list rather
  than removing it. The company data + BANT score is still valuable for the user.

CRITICAL — LINKEDIN PROFILE COLLECTION:
For EVERY contact discovered, you MUST attempt to find their LinkedIn profile URL.
This is non-negotiable. Use these methods in order:
1. apollo_people_search results often include linkedin_url — always extract it
2. duckduckgo_search "site:linkedin.com/in [full name] [company name]" — highly effective
3. exa_search "[full name] [company name] linkedin" — finds profile mentions
4. If the contact was found via hunter or lusha, use their name + company to search LinkedIn

A contact without a LinkedIn URL should be treated as INCOMPLETE. Make at least 2
attempts using different tools before giving up on finding the LinkedIn URL.

═══════════════════════════════════════════════════════════════
STAGE 3: CONTACT ENRICHMENT
═══════════════════════════════════════════════════════════════
Goal: Fill in missing contact data fields (email, phone, LinkedIn).

Only enrich fields that are missing — do not re-query data you already have.
• hunter_email_finder — For missing emails when you have first_name + last_name + domain.
• lusha_person_search — For missing phone numbers when you have name + company.
• exa_search or duckduckgo_search — For missing LinkedIn URLs (search by name + company).

ENRICHMENT PRIORITIES (in order of importance):
1. LinkedIn URL — HIGHEST priority. Search "site:linkedin.com/in [name] [company]" via
   duckduckgo_search if not already found. This is the most valuable field for sales teams.
2. Email address — Use hunter_email_finder with first_name + last_name + domain.
3. Phone number — Use lusha_person_search with name + company.

Mark each contact's enrichment status:
- "enriched" = LinkedIn URL + email populated (both required for "enriched" status)
- "partial" = has either LinkedIn OR email but not both
- "failed" = enrichment found nothing new

For EACH contact missing a LinkedIn URL, you MUST run at least:
  duckduckgo_search "site:linkedin.com/in [first_name] [last_name] [company]"
This single query has a high success rate and must not be skipped.

═══════════════════════════════════════════════════════════════
STAGE 4: BANT SCORING
═══════════════════════════════════════════════════════════════
Goal: Score each company using the BANT framework. This is the most important stage.
Invest significant research effort here — data accuracy is the highest priority.

IMPORTANT: For each BANT dimension, you MUST include "*_sources" — a list of
{"url": "...", "title": "...", "tool": "..."} objects citing where you found the
evidence. Every dimension requires 2-3 source URLs. These MUST be the specific
page URLs from your tool results — NEVER use a company homepage as a source.
Use the exact article URL, profile URL, or sub-page URL where evidence was found.

PRE-SCORING RESEARCH (mandatory for each company):
Before scoring ANY company, you MUST conduct dedicated research:

a) BUDGET EVIDENCE: Conduct thorough financial research:
   - Search for recent funding rounds: tavily_search "[company] funding round 2025 2026"
   - Search financial data: duckduckgo_search "[company] revenue estimate" or
     "[company] site:crunchbase.com"
   - For public companies: search "[company] Yahoo Finance" or "[company] 10-K SEC filing"
   - Look for press releases: tavily_search "[company] press release" for financial news
   - Scrape the company's /about or /investors page for self-reported data
   - Look at hiring velocity as a proxy for budget (many open roles = growing budget)

b) AUTHORITY VERIFICATION: Verify the identified contact's role and decision-making
   power. Search their LinkedIn profile context via exa_search or duckduckgo_search.
   Look for evidence of them speaking at conferences, publishing articles, or being
   quoted in industry publications.

c) NEED VALIDATION: Search for specific pain points or transformation signals. Look for
   job postings (tavily_search "[company] careers [technology]"), tech stack analysis,
   industry reports mentioning the company, or news about operational challenges.

d) TIMING SIGNALS: Search for recent events suggesting readiness: new executive hires,
   RFP announcements, vendor evaluations, contract expirations, fiscal year planning.
   Use tavily_search and exa_search for news within the last 6 months.

Each research step should use AT LEAST 2 different tools to cross-validate findings.
Use dynamic tool selection — if tavily_search doesn't find budget evidence, try
exa_search with a different query, then scrape_webpage on the company's press page.

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

EVIDENCE REQUIREMENTS:
- Each BANT dimension MUST cite 2-3 specific sources with URLs.
- Sources must be from your actual tool results — never fabricate URLs.
- For each source, explain what specific evidence it provides in the reason text.
- Prefer recent sources (< 12 months old) over older ones.
- If you cannot find strong evidence for a dimension, score it lower (1-2) rather than
  guessing. Honest low scores are more valuable than inflated unverifiable scores.

SOURCE URL SPECIFICITY (CRITICAL):
- NEVER use a company's homepage (e.g., "https://acme.com") as a source URL.
  Homepage URLs tell the user nothing about where the evidence was found.
- Instead, use the SPECIFIC page URL where you found the evidence:
  ✓ "https://techcrunch.com/2025/03/acme-raises-30m" (specific article)
  ✓ "https://acme.com/about" or "https://acme.com/careers" (specific sub-page)
  ✓ "https://linkedin.com/in/janedoe" (specific LinkedIn profile)
  ✓ "https://crunchbase.com/organization/acme" (specific Crunchbase page)
  ✗ "https://acme.com" (WRONG — too generic, provides no value)
  ✗ "https://www.google.com" (WRONG — search engine URL)
- For each source, use the exact URL from your tool results (the URL returned
  by tavily_search, exa_search, etc.), NOT the company's root domain.
- Each source must point to a DIFFERENT page — do not list the same URL twice.
- Include the page title that describes what evidence is on that page.

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
        "budget_sources": [
          {"url": "https://techcrunch.com/2025/acme-series-b", "title": "Acme raises $30M Series B", "tool": "tavily"},
          {"url": "https://acme.com/about", "title": "Company about page", "tool": "scrape_webpage"}
        ],
        "authority_score": 5,
        "authority_reason": "CTO identified with direct tech budget ownership...",
        "authority_sources": [
          {"url": "https://linkedin.com/in/janedoe", "title": "Jane Doe - CTO at Acme", "tool": "apollo"}
        ],
        "need_score": 4,
        "need_reason": "Running legacy Magento, job postings mention headless...",
        "need_sources": [
          {"url": "https://builtwith.com/acme.com", "title": "Acme tech profile", "tool": "exa"}
        ],
        "timing_score": 3,
        "timing_reason": "Growing 25% YoY, no public replatforming timeline yet...",
        "timing_sources": [
          {"url": "https://acme.com/careers", "title": "Job postings page", "tool": "scrape_webpage"}
        ],
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
5. Every BANT score MUST have evidence-backed reasoning with 2-3 source URLs per
   dimension. Conduct dedicated research per company before scoring — do not rely
   solely on data gathered during company/contact discovery. If evidence is weak,
   score conservatively and explain what is missing.
6. Deduplicate companies by domain throughout the process.
7. Process ALL stages before returning — do not skip enrichment or scoring.
8. BANT scoring is the most important output. Spend proportionally more time on
   research for scoring than on company/contact discovery. A well-researched BANT
   score with specific evidence is far more valuable than finding additional companies.
9. NEVER skip or remove a company from results because of sparse contact data.
   A company with strong ICP match, good BANT score, but limited contacts is still
   a valuable lead. Keep it in results with whatever contact data you found (even if
   the contacts list is empty). The user values company-level intelligence.
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
