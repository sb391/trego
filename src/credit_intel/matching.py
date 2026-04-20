from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher

from ..io_utils import company_name_tokens, normalize_company_name


@dataclass(slots=True)
class MatchCandidate:
    company_name: str
    normalized_name: str
    score: float
    reason: str


def score_name_match(query: str, candidate: str) -> tuple[float, str]:
    normalized_query = normalize_company_name(query)
    normalized_candidate = normalize_company_name(candidate)
    if not normalized_query or not normalized_candidate:
        return 0.0, "empty"
    if normalized_query == normalized_candidate:
        return 1.0, "exact_normalized_match"
    if normalized_query in normalized_candidate or normalized_candidate in normalized_query:
        return 0.93, "substring_match"

    left_tokens = set(company_name_tokens(query))
    right_tokens = set(company_name_tokens(candidate))
    token_overlap = len(left_tokens & right_tokens) / max(len(left_tokens | right_tokens), 1)
    sequence = SequenceMatcher(None, normalized_query, normalized_candidate).ratio()
    score = round(max(token_overlap * 0.45 + sequence * 0.55, sequence * 0.8), 4)
    reason = f"token_overlap={token_overlap:.2f};sequence={sequence:.2f}"
    return score, reason
