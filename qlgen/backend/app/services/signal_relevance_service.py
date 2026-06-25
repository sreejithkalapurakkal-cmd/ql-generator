"""Signal relevance verification service.

Wraps the tool-less signal_relevance_agent into a batched, fail-open helper.
Given a target company and a list of candidate signals, it returns one verdict
per candidate so callers can decide whether to surface the signal.

Fail-open policy: if the LLM call errors, returns malformed JSON, or omits a
verdict, the affected candidate's `relevant` is returned as None ("unchecked").
Unchecked signals are treated as visible — we never silently drop real signals
because of a transient LLM hiccup; they are simply not yet validated.
"""
import asyncio
import json
import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)

# Cap how much evidence text we feed the model per candidate (keeps the prompt
# bounded and cheap; the title/summary/url carry most of the disambiguation).
_MAX_ARTICLES = 3
_MAX_SNIPPET_CHARS = 400


def _candidate_evidence_snippet(sig_data: dict) -> str:
    """Build a compact evidence snippet from a candidate signal's evidence."""
    evidence = sig_data.get("evidence") or {}
    articles = evidence.get("articles") or []
    parts: list[str] = []
    for art in articles[:_MAX_ARTICLES]:
        if not isinstance(art, dict):
            continue
        title = (art.get("title") or "").strip()
        body = (art.get("body") or art.get("content") or "").strip()
        url = (art.get("href") or art.get("url") or "").strip()
        chunk = " ".join(p for p in [title, body] if p)[:_MAX_SNIPPET_CHARS]
        if url:
            chunk = f"[{url}] {chunk}"
        if chunk:
            parts.append(chunk)
    return "\n".join(parts)


def _build_candidate_payload(candidates: list[dict]) -> list[dict]:
    """Reduce candidate signals to the minimal fields the judge needs."""
    payload = []
    for i, sig in enumerate(candidates):
        payload.append({
            "index": i,
            "title": (sig.get("title") or "")[:300],
            "summary": (sig.get("summary") or "")[:500],
            "source_url": sig.get("source_url") or "",
            "evidence": _candidate_evidence_snippet(sig),
        })
    return payload


def _extract_json(text: str) -> Optional[dict]:
    """Best-effort extraction of a JSON object from raw model output."""
    if not text:
        return None
    # Strip code fences if present
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json)?", "", cleaned).strip()
    cleaned = re.sub(r"```$", "", cleaned).strip()
    try:
        return json.loads(cleaned)
    except Exception:
        pass
    # Fall back to the first balanced-looking {...} block
    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except Exception:
            return None
    return None


def _result_text(result) -> str:
    """Extract final text from a Strands AgentResult (or any stringifiable result)."""
    try:
        message = getattr(result, "message", None)
        if isinstance(message, dict):
            content = message.get("content")
            if isinstance(content, list):
                texts = [c.get("text", "") for c in content if isinstance(c, dict)]
                joined = "".join(texts).strip()
                if joined:
                    return joined
            elif isinstance(content, str):
                return content
    except Exception:
        pass
    return str(result or "")


async def verify_signal_relevance(
    company_name: str,
    domain: str,
    candidates: list[dict],
) -> list[dict]:
    """Judge whether each candidate signal is about `company_name` (`domain`).

    Returns a list aligned 1:1 with `candidates`, each:
        {"relevant": True|False|None, "confidence": float, "reason": str}

    `relevant=None` means "could not verify" (fail-open → treated as visible).
    """
    if not candidates:
        return []

    # Default fail-open verdicts; overwritten as the model returns answers.
    verdicts: list[dict] = [
        {"relevant": None, "confidence": 0.0, "reason": "not verified"}
        for _ in candidates
    ]

    payload = _build_candidate_payload(candidates)
    prompt = (
        f"TARGET COMPANY:\n"
        f"  name: {company_name}\n"
        f"  domain: {domain or 'unknown'}\n\n"
        f"CANDIDATE SIGNALS (JSON):\n{json.dumps(payload, ensure_ascii=False)}\n\n"
        f"Return the verdicts JSON now."
    )

    try:
        from app.agent.signal_relevance_agent import create_signal_relevance_agent
        agent = create_signal_relevance_agent()
        result = await asyncio.to_thread(agent, prompt)
        parsed = _extract_json(_result_text(result))
    except Exception as e:
        logger.warning(
            "Relevance verification failed for %s (%d candidates): %s — failing open",
            company_name, len(candidates), e,
        )
        return verdicts

    if not parsed or not isinstance(parsed.get("verdicts"), list):
        logger.warning(
            "Relevance verification returned unparseable output for %s — failing open",
            company_name,
        )
        return verdicts

    for v in parsed["verdicts"]:
        if not isinstance(v, dict):
            continue
        idx = v.get("index")
        if not isinstance(idx, int) or not (0 <= idx < len(verdicts)):
            continue
        rel = v.get("relevant")
        try:
            conf = float(v.get("confidence", 0.0))
        except (TypeError, ValueError):
            conf = 0.0
        verdicts[idx] = {
            "relevant": bool(rel) if isinstance(rel, bool) else None,
            "confidence": max(0.0, min(1.0, conf)),
            "reason": str(v.get("reason") or "")[:500],
        }

    return verdicts
