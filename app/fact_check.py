"""Independent fact-check pass over tailored resume output.

This is the safeguard discussed earlier: the tailoring prompt instructs the
model not to invent facts, but instructions alone aren't reliable enough for
something as consequential as your resume. This module re-checks the output
two ways:

1. A fast deterministic check: any number (team size, percentage, node count,
   years) appearing in the tailored text that does NOT appear anywhere in the
   original resume text gets flagged automatically. Numbers are the most
   common and most damaging form of resume embellishment.
2. An LLM-based semantic check: a second Claude call, given ONLY the original
   resume and the tailored resume (not the JD, to avoid bias toward
   justifying JD-matching claims), is asked to list every claim in the
   tailored version not supported by the original.

Flags are surfaced to the human during review - this module never silently
edits or removes anything.
"""
import json
import re

from app.llm_client import complete_json
from app.models import FactCheckFlag, ResumeData

FACT_CHECK_SYSTEM_PROMPT = """You compare an ORIGINAL resume against a
TAILORED version of the same resume. Your only job is to find claims in the
tailored version that are NOT supported by the original: invented
technologies, fabricated team/infrastructure scale, exaggerated outcomes,
new certifications, or responsibilities that were not in the original.

Wording changes, reordering, and rephrasing that preserve the same meaning
are FINE and should not be flagged.

Output ONLY a valid JSON array, no markdown fences, no commentary. Each item:
{"claim": "the exact unsupported phrase from the tailored version",
 "reason": "why it's not supported by the original",
 "severity": "high" | "medium" | "low"}

If there are no unsupported claims, output an empty array: []
"""


def _numeric_claims(text: str) -> set[str]:
    """Pulls out numbers with their immediate context, e.g. '5,000 nodes'."""
    pattern = r"\b\d[\d,.]*\+?\s*(?:%|percent|nodes?|servers?|engineers?|people|years?|clusters?|environments?|users?|requests?|TB|GB)\b"
    return {m.group(0).lower() for m in re.finditer(pattern, text, flags=re.IGNORECASE)}


def _heuristic_numeric_check(original_text: str, tailored_text: str) -> list[FactCheckFlag]:
    original_numbers = _numeric_claims(original_text)
    tailored_numbers = _numeric_claims(tailored_text)
    new_numbers = tailored_numbers - original_numbers

    flags = []
    for claim in new_numbers:
        flags.append(
            FactCheckFlag(
                claim=claim,
                reason="This number/scale claim does not appear anywhere in the original resume.",
                severity="high",
            )
        )
    return flags


def _llm_semantic_check_text(original_text: str, candidate_text: str, document_label: str) -> list[FactCheckFlag]:
    user_prompt = f"""ORIGINAL RESUME (ground truth facts):
{original_text}

{document_label} TO CHECK:
{candidate_text}
"""
    text = complete_json(FACT_CHECK_SYSTEM_PROMPT, user_prompt, max_tokens=1500)
    try:
        items = json.loads(text)
    except json.JSONDecodeError:
        return []
    return [FactCheckFlag(**item) for item in items]


def _dedupe(flags: list[FactCheckFlag]) -> list[FactCheckFlag]:
    severity_rank = {"high": 2, "medium": 1, "low": 0}
    by_claim: dict[str, FactCheckFlag] = {}
    for f in flags:
        existing = by_claim.get(f.claim.lower())
        if not existing or severity_rank[f.severity] > severity_rank[existing.severity]:
            by_claim[f.claim.lower()] = f
    return list(by_claim.values())


def fact_check(original: ResumeData, tailored: ResumeData) -> list[FactCheckFlag]:
    original_text = original.flat_text()
    # Only check the fields tailor.py actually lets the LLM rewrite - never
    # the structural fields (dates, cities, countries, education, URLs)
    # that are always copied through verbatim and can't have been altered.
    tailored_text = tailored.tailorable_text()

    flags = _heuristic_numeric_check(original_text, tailored_text)
    flags.extend(_llm_semantic_check_text(original_text, tailored_text, "TAILORED RESUME"))
    return _dedupe(flags)


def fact_check_text(original: ResumeData, candidate_text: str, document_label: str = "DOCUMENT") -> list[FactCheckFlag]:
    """Same guard, generalized to any free-text document (e.g. a cover
    letter) instead of a structured ResumeData object."""
    original_text = original.flat_text()

    flags = _heuristic_numeric_check(original_text, candidate_text)
    flags.extend(_llm_semantic_check_text(original_text, candidate_text, document_label))
    return _dedupe(flags)
