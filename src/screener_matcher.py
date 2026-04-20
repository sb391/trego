from __future__ import annotations

from difflib import SequenceMatcher
from urllib.parse import urljoin, urlsplit

from .config import BASE_URL
from .io_utils import company_name_tokens, normalize_code, normalize_company_name
from .models import CorporateRecord, MatchDecision, MatchScore, SearchCandidate


def candidate_from_payload(payload: dict[str, object], rank: int, base_url: str = BASE_URL) -> SearchCandidate:
    relative_url = str(payload.get("url", "")).strip()
    absolute_url = urljoin(base_url, relative_url)
    company_slug = extract_company_slug(absolute_url)
    name = str(payload.get("name", "")).strip()
    return SearchCandidate(
        rank=rank,
        name=name,
        url=absolute_url,
        company_slug=company_slug,
        normalized_name=normalize_company_name(name),
        normalized_tokens=company_name_tokens(name),
        source_payload=payload,
    )


def extract_company_slug(url: str) -> str:
    path_parts = [part for part in urlsplit(url).path.split("/") if part]
    try:
        index = path_parts.index("company")
    except ValueError:
        return path_parts[-1].upper() if path_parts else ""
    return path_parts[index + 1].upper() if len(path_parts) > index + 1 else ""


def score_candidate(company: CorporateRecord, candidate: SearchCandidate) -> MatchScore:
    reasons: list[str] = []
    exact_name_match = company.company_name.casefold() == candidate.name.casefold()
    normalized_name_match = company.normalized_name == candidate.normalized_name
    token_overlap = _token_overlap(company.normalized_tokens, candidate.normalized_tokens)
    sequence_similarity = SequenceMatcher(None, company.normalized_name, candidate.normalized_name).ratio()

    nse_code_match = bool(company.nse_code and normalize_code(candidate.company_slug) == company.nse_code)
    bse_code_match = bool(company.bse_code and normalize_code(candidate.company_slug) == company.bse_code)

    if nse_code_match:
        reasons.append("exact NSE code match")
    if bse_code_match:
        reasons.append("exact BSE code match")
    if exact_name_match:
        reasons.append("exact company name match")
    if normalized_name_match and not exact_name_match:
        reasons.append("normalized company name match")
    if token_overlap >= 0.6:
        reasons.append(f"strong token overlap ({token_overlap:.2f})")
    if sequence_similarity >= 0.85:
        reasons.append(f"high string similarity ({sequence_similarity:.2f})")

    total_score = 0.0
    if nse_code_match:
        total_score = max(total_score, 1.0)
    if bse_code_match:
        total_score = max(total_score, 0.95)
    if exact_name_match:
        total_score = max(total_score, 0.84)
    if normalized_name_match:
        total_score = max(total_score, 0.80)

    if total_score < 0.95:
        total_score += min(token_overlap * 0.18, 0.18)
        total_score += min(sequence_similarity * 0.18, 0.18)
        if candidate.rank == 1:
            total_score += 0.03
    total_score = min(total_score, 1.0)

    return MatchScore(
        candidate=candidate,
        total_score=round(total_score, 4),
        exact_name_match=exact_name_match,
        normalized_name_match=normalized_name_match,
        token_overlap=round(token_overlap, 4),
        sequence_similarity=round(sequence_similarity, 4),
        nse_code_match=nse_code_match,
        bse_code_match=bse_code_match,
        reasons=reasons or ["weak name similarity"],
    )


def choose_best_match(
    company: CorporateRecord,
    candidates: list[SearchCandidate],
    *,
    auto_threshold: float,
    ambiguity_gap_threshold: float,
) -> MatchDecision:
    search_query = company.search_name
    if not candidates:
        return MatchDecision(
            company=company,
            search_query=search_query,
            candidates=[],
            scored_candidates=[],
            status="no_results",
            matched_candidate=None,
            confidence=0.0,
            reason="No Screener candidates returned for search query.",
        )

    scored = sorted(
        (score_candidate(company, candidate) for candidate in candidates),
        key=lambda item: item.total_score,
        reverse=True,
    )
    best = scored[0]
    second_score = scored[1].total_score if len(scored) > 1 else 0.0
    score_gap = best.total_score - second_score

    if best.nse_code_match:
        return MatchDecision(
            company=company,
            search_query=search_query,
            candidates=candidates,
            scored_candidates=scored,
            status="matched",
            matched_candidate=best.candidate,
            confidence=best.total_score,
            reason="Matched automatically by exact NSE code.",
        )
    if best.bse_code_match and score_gap >= 0.03:
        return MatchDecision(
            company=company,
            search_query=search_query,
            candidates=candidates,
            scored_candidates=scored,
            status="matched",
            matched_candidate=best.candidate,
            confidence=best.total_score,
            reason="Matched automatically by exact BSE code.",
        )
    if best.total_score >= auto_threshold and score_gap >= ambiguity_gap_threshold:
        return MatchDecision(
            company=company,
            search_query=search_query,
            candidates=candidates,
            scored_candidates=scored,
            status="matched",
            matched_candidate=best.candidate,
            confidence=best.total_score,
            reason=f"Matched automatically with confidence {best.total_score:.2f}.",
        )
    return MatchDecision(
        company=company,
        search_query=search_query,
        candidates=candidates,
        scored_candidates=scored,
        status="ambiguous",
        matched_candidate=None,
        confidence=best.total_score,
        reason=f"Top candidate confidence {best.total_score:.2f} was not sufficiently above the next candidate ({second_score:.2f}).",
    )


def _token_overlap(left: tuple[str, ...], right: tuple[str, ...]) -> float:
    if not left or not right:
        return 0.0
    left_set = set(left)
    right_set = set(right)
    intersection = len(left_set & right_set)
    union = len(left_set | right_set)
    return intersection / union if union else 0.0

