"""Intent Signal Extractor Tool.

NLP-based extraction of buying intent signals from text.
Uses keyword matching + pattern analysis to identify budget signals,
urgency indicators, and custom signal hypothesis matches.
"""
import logging
import re

logger = logging.getLogger(__name__)

# Intent signal categories and their keyword patterns
INTENT_PATTERNS = {
    "active_evaluation": [
        r"evaluat\w+\s+(?:vendor|platform|solution|tool)",
        r"(?:RFP|RFI|request for proposal)",
        r"proof of concept|POC|pilot program",
        r"comparing\s+\w+\s+(?:vs|versus|or|and)",
        r"shortlist\w*|vendor\s+selection",
    ],
    "budget_allocated": [
        r"\$[\d,.]+\s*(?:million|M|billion|B|thousand|K)",
        r"budget\s+(?:of|for|allocated|approved)",
        r"investment\s+(?:in|of|for)",
        r"earmark\w*|allocat\w+\s+fund",
        r"capex|capital\s+expenditure",
    ],
    "migration_intent": [
        r"migrat\w+\s+(?:from|to|off)",
        r"replac\w+\s+(?:existing|current|legacy)",
        r"sunset\w*|deprecat\w*|phase\s+out",
        r"moderniz\w+|transform\w+",
        r"cloud\s+(?:migration|adoption|first)",
    ],
    "urgency_indicators": [
        r"deadline|timeline|by\s+(?:Q[1-4]|end\s+of)",
        r"urgent\w*|immediate\w*|asap",
        r"compliance\s+(?:deadline|requirement|mandate)",
        r"regulatory\s+(?:change|requirement|deadline)",
        r"contract\s+(?:expir\w+|renew\w+|end\w+)",
    ],
    "growth_signals": [
        r"expand\w+\s+(?:to|into|team|office)",
        r"(?:hiring|recruiting)\s+(?:surge|spree|rapidly)",
        r"new\s+(?:office|location|market|region)",
        r"headcount\s+(?:growth|increase|double)",
        r"series\s+[A-F]|funding\s+round",
    ],
}


def intent_signal_extractor(
    text: str,
    company_context: dict | None = None,
    signal_hypotheses: list[str] | None = None,
) -> dict:
    """Analyze text for buying intent signals, guided by signal hypotheses.

    Args:
        text: Text to analyze (article body, job description, etc.)
        company_context: Company info for context
        signal_hypotheses: User-defined signal hints to match against

    Returns dict with intent_signals, hypothesis_matches, overall_intent_score.
    """
    if not text or len(text.strip()) < 20:
        return {
            "intent_signals": [],
            "hypothesis_matches": {},
            "overall_intent_score": 0.0,
        }

    text_lower = text.lower()
    intent_signals = []

    # Pattern-based intent detection
    for intent_category, patterns in INTENT_PATTERNS.items():
        matches = []
        for pattern in patterns:
            found = re.findall(pattern, text_lower)
            matches.extend(found)

        if matches:
            # Find the evidence text (surrounding context)
            best_match = matches[0]
            idx = text_lower.find(best_match)
            start = max(0, idx - 50)
            end = min(len(text), idx + len(best_match) + 100)
            evidence_text = text[start:end].strip()

            confidence = min(0.95, 0.5 + len(matches) * 0.15)

            intent_signals.append({
                "signal_type": _map_to_signal_type(intent_category),
                "intent_category": intent_category,
                "evidence_text": evidence_text[:300],
                "match_count": len(matches),
                "confidence": round(confidence, 2),
                "urgency": "high" if intent_category in ("active_evaluation", "urgency_indicators") else "medium",
            })

    # Hypothesis matching
    hypothesis_matches = {}
    if signal_hypotheses:
        for hypothesis in signal_hypotheses:
            hyp_lower = hypothesis.lower().strip()
            if not hyp_lower:
                continue

            # Check if hypothesis keywords appear in text
            hyp_words = [w for w in hyp_lower.split() if len(w) > 3]
            matching_words = [w for w in hyp_words if w in text_lower]

            if matching_words:
                # Find evidence
                first_word = matching_words[0]
                idx = text_lower.find(first_word)
                start = max(0, idx - 50)
                end = min(len(text), idx + 150)
                evidence = text[start:end].strip()

                hypothesis_matches[hypothesis] = {
                    "matched": True,
                    "evidence": evidence[:300],
                    "matching_words": matching_words,
                    "confidence": round(min(0.9, len(matching_words) / max(len(hyp_words), 1)), 2),
                }
            else:
                hypothesis_matches[hypothesis] = {
                    "matched": False,
                    "evidence": None,
                    "matching_words": [],
                    "confidence": 0.0,
                }

    # Overall intent score
    if intent_signals:
        overall = sum(s["confidence"] for s in intent_signals) / len(intent_signals)
    else:
        overall = 0.0

    return {
        "intent_signals": intent_signals,
        "hypothesis_matches": hypothesis_matches,
        "overall_intent_score": round(overall, 2),
        "text_length": len(text),
    }


def _map_to_signal_type(intent_category: str) -> str:
    mapping = {
        "active_evaluation": "urgency_signal",
        "budget_allocated": "budget_signal",
        "migration_intent": "tech_adoption",
        "urgency_indicators": "urgency_signal",
        "growth_signals": "expansion",
    }
    return mapping.get(intent_category, "custom_signal")
