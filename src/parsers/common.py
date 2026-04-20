from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..schemas import normalize_outlook, normalize_rating_label
from ..schemas.models import RatingEvent
from ..utils import (
    compact_spaces,
    extract_bullet_like_items,
    find_first_date,
    normalize_multiline_text,
    parse_amount_to_crore,
    prettify_filename_stem,
    slugify,
)


LONG_TERM_PATTERN = r"(AAA|AA\+|AA-|AA|A\+|A-|BBB\+|BBB-|BBB|BB\+|BB-|BB|B\+|B-|C\+|A|B|C|D)"
SHORT_TERM_PATTERN = r"(A1\+|A1|A2\+|A2|A3\+|A3|A4\+|A4|P1\+|P1|P2\+|P2|P3\+|P3|P4\+|P4|P5|D)"
MONTH_NAME_PATTERN = r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec|January|February|March|April|June|July|August|September|October|November|December)"

LIQUIDITY_KEYWORDS = {
    "Strong": (r"\bliquidity[: ]+strong\b",),
    "Adequate": (r"\bliquidity[: ]+adequate\b", r"\bliquidity adequate\b", r"\bliquidity position is adequate\b"),
    "Comfortable": (r"\bliquidity[: ]+comfortable\b", r"\bliquidity remains comfortable\b"),
    "Stretched": (r"\bliquidity[: ]+stretched\b", r"\bliquidity remains stretched\b"),
    "Weak": (r"\bliquidity[: ]+weak\b",),
}

FEATURE_PATTERNS = {
    "has_management_strength": (r"experienced management", r"track record of promoters", r"experienced promoters"),
    "has_group_support": (r"group support", r"part of established group", r"association with", r"group company"),
    "has_scale_constraint": (r"modest scale", r"small scale", r"scale constraint", r"scale remains constrained"),
    "has_working_capital_pressure": (r"working capital", r"elongation in working capital", r"gross current assets", r"\bGCA\b"),
    "has_liquidity_adequate": (r"\bliquidity adequate\b", r"\bliquidity[: ]+adequate\b", r"\bliquidity[: ]+strong\b"),
    "has_liquidity_stretched": (r"\bliquidity stretched\b", r"\bliquidity[: ]+stretched\b", r"\bliquidity[: ]+weak\b"),
    "has_regulatory_risk": (r"regulatory risk", r"USFDA", r"regulatory"),
    "has_fx_risk": (r"foreign exchange risk", r"foreign currency risk", r"\bfx risk\b"),
    "has_customer_concentration": (r"customer concentration", r"top customer", r"concentration risk"),
    "has_product_diversification": (r"diversified portfolio", r"product diversification", r"diversification initiatives"),
    "has_export_risk": (r"export", r"overseas market", r"geopolitical risks"),
    "has_capex_risk": (r"\bcapex\b", r"capacity expansion", r"brownfield project"),
    "has_margin_pressure": (r"margin pressure", r"profitability dip", r"decline in profitability", r"pricing headwinds"),
    "has_leverage_improvement": (r"improvement in leverage", r"moderation in leverage", r"low gearing"),
    "has_turnaround_story": (r"turnaround", r"structural turnaround", r"turn around"),
    "has_non_cooperation_flag": (r"issuer not cooperating", r"not cooperating", r"best available information"),
    "has_contingent_liability_risk": (r"contingent liabilit",),
    "has_msa_dependency": (r"manufacturing service agreement", r"\bMSA\b"),
    "has_capacity_expansion": (r"capacity expansion", r"doubling capacities", r"brownfield"),
    "has_niche_complex_portfolio": (r"niche", r"complex portfolio", r"high potent", r"complex products"),
    "has_strong_roce": (r"strong return on capital employed", r"strong roce", r"\bROCE\b"),
    "has_net_cash_position": (r"net cash position",),
}


@dataclass(slots=True)
class RatingComponents:
    long_term_rating: str | None
    short_term_rating: str | None
    outlook: str | None
    watch_status: str | None
    rating_rank_numeric: int | None
    is_withdrawn: bool
    is_issuer_not_cooperating: bool
    is_best_available_information: bool


def infer_company_name_from_text(text: str, *, agency_name: str, source_file: str) -> str:
    normalized = normalize_multiline_text(text)
    header_lines = [compact_spaces(line) for line in normalized.splitlines() if compact_spaces(line)][:80]
    header_blob = "\n".join(header_lines)

    agency_patterns = {
        "crisil": (
            r"(?P<name>[A-Z][A-Za-z0-9&.,'() -]+?)\s+Ratings\s+\w+\s+at",
            r"Rating Rationale\s+\w+\s+\d{1,2},\s+\d{4}\s+\|\s+[A-Za-z ]+\s+(?P<name>[A-Z][A-Za-z0-9&.,'() -]+)",
            r"CRISIL\s+\w+\s+ratings\s+on\s+(?P<name>[A-Z][A-Za-z0-9&.,'() -]+?)\s+to",
        ),
        "care": (r"Press Release\s+(?P<name>[A-Z][A-Za-z0-9&.,'() -]+?(?:Limited|Ltd\.?))",),
        "india_ratings": (
            r"\|\s*(?P<name>[A-Z][A-Za-z0-9&.,'() -]+?(?:Limited|Ltd\.?)(?:\s+\(Formerly[^|]+\))?)\s*\|",
            rf"{MONTH_NAME_PATTERN}\s+\d{{1,2}},\s+\d{{4}}\s*\|\s*(?P<name>[A-Z][A-Za-z0-9&.,'() -]+?(?:Limited|Ltd\.?)(?:\s+\(Formerly[^|]+\))?)\s*\|",
        ),
        "acuite": (r"Press Release\s+(?P<name>[A-Z][A-Za-z0-9&.,'() -]+?(?:LIMITED|LTD\.?))",),
        "brickwork": (r"\d{1,2}[A-Za-z]{3}\d{4}\s+(?P<name>[A-Z][A-Za-z0-9&.,'() -]+?(?:Limited|Ltd\.?))",),
        "infomerics": (r"^(?P<name>[A-Z][A-Za-z0-9&.,'() -]+?(?:Limited|Ltd\.?))\s+\w+\s+\d{1,2},\s+\d{4}$",),
        "icra": (r"\w+\s+\d{1,2},\s+\d{4}\s+(?P<name>[A-Z][^:\n]+?(?:Limited|Ltd\.?)):",),
    }

    for pattern in agency_patterns.get(agency_name, ()):
        match = re.search(pattern, header_blob, flags=re.I | re.S | re.M)
        if match:
            return clean_company_name(match.group("name"))

    for line in header_lines[:20]:
        if _looks_like_company_name(line):
            return clean_company_name(line)

    return clean_company_name(prettify_filename_stem(source_file))


def clean_company_name(value: str) -> str:
    text = compact_spaces(value)
    text = re.sub(r"^Credit update\s*[-:]\s*", "", text, flags=re.I)
    text = re.sub(r":.*$", "", text)
    text = re.sub(r"\s+\|\s+.*$", "", text)
    text = re.sub(r"\s+(Ratings|Rating Rationale|Press Release).*$", "", text, flags=re.I)
    return text.strip(" -|")


def infer_doc_date(text: str) -> Any:
    return find_first_date(text[:5000])


def determine_document_type(text: str) -> str:
    lowered = text[:3000].lower()
    if "press release" in lowered:
        return "press_release"
    if "rating rationale" in lowered:
        return "rating_rationale"
    return "credit_rating_report"


def extract_liquidity_label(text: str, sections: dict[str, str]) -> str | None:
    candidates = [sections.get("liquidity", ""), sections.get("rationale", ""), text[:5000]]
    for candidate in candidates:
        for label, patterns in LIQUIDITY_KEYWORDS.items():
            if any(re.search(pattern, candidate, flags=re.I) for pattern in patterns):
                return label
    return None


def extract_key_points(section_text: str | None) -> list[str]:
    if not section_text:
        return []
    text = normalize_multiline_text(section_text)
    named_points = [compact_spaces(match.group(1)) for match in re.finditer(r"([A-Z][A-Za-z0-9&(),'/ -]{3,120}):", text)]
    if named_points:
        return list(dict.fromkeys(named_points))
    items = extract_bullet_like_items(text)
    if items:
        return items[:8]
    return [line for line in text.splitlines() if len(line.split()) >= 4][:5]


def extract_inline_section(text: str, *, start_aliases: tuple[str, ...], end_aliases: tuple[str, ...]) -> str | None:
    normalized = normalize_multiline_text(text)
    for start_alias in start_aliases:
        start_match = re.search(re.escape(start_alias), normalized, flags=re.I)
        if not start_match:
            continue
        body = normalized[start_match.end() :].strip()
        if end_aliases:
            end_pattern = "|".join(re.escape(alias) for alias in end_aliases)
            end_match = re.search(end_pattern, body, flags=re.I)
            if end_match:
                body = body[: end_match.start()]
        body = compact_spaces(body)
        if body:
            return body
    return None


def split_sensitivities(section_text: str | None) -> tuple[list[str], list[str]]:
    if not section_text:
        return [], []
    text = normalize_multiline_text(section_text)
    upward_match = re.search(r"Upward(?:s)?\s+factors?(?P<body>.*?)(?:Downward(?:s)?\s+factors?|$)", text, flags=re.I | re.S)
    downward_match = re.search(r"Downward(?:s)?\s+factors?(?P<body>.*)$", text, flags=re.I | re.S)

    if upward_match or downward_match:
        upward = extract_bullet_like_items(upward_match.group("body") if upward_match else "")
        downward = extract_bullet_like_items(downward_match.group("body") if downward_match else "")
        return upward, downward

    items = extract_bullet_like_items(text)
    upward: list[str] = []
    downward: list[str] = []
    for item in items:
        if re.search(r"\b(growth|improvement|higher|increase|healthy|stronger)\b", item, flags=re.I):
            upward.append(item)
        elif re.search(r"\b(decline|lower|stretched|pressure|deterioration|weak)\b", item, flags=re.I):
            downward.append(item)
    return upward, downward


def extract_analytical_approach(text: str, sections: dict[str, str]) -> str | None:
    section = sections.get("analytical_approach")
    if section:
        return compact_spaces(section)
    match = re.search(r"Analytical approach[: ]+(?P<value>.+?)(?:Outlook:|$)", text, flags=re.I | re.S)
    if match:
        return compact_spaces(match.group("value"))
    return None


def extract_standalone_or_consolidated(text: str, analytical_approach: str | None) -> str | None:
    combined = "\n".join(filter(None, [analytical_approach, text[:6000]]))
    match = re.search(r"\b(Standalone|Consolidated)\b", combined, flags=re.I)
    return match.group(1).title() if match else None


def extract_feature_flags(text: str, sections: dict[str, str]) -> dict[str, bool]:
    combined = normalize_multiline_text("\n".join(filter(None, [text, *sections.values()])))
    flags: dict[str, bool] = {}
    for field_name, patterns in FEATURE_PATTERNS.items():
        flags[field_name] = any(re.search(pattern, combined, flags=re.I) for pattern in patterns)
    return flags


def extract_qualitative_summary(sections: dict[str, str]) -> str | None:
    rationale = sections.get("rationale") or sections.get("key_rating_drivers")
    if not rationale:
        return None
    text = compact_spaces(rationale)
    return text[:1200] if text else None


def extract_key_financial_indicators(section_text: str | None) -> dict[str, Any]:
    if not section_text:
        return {}
    indicators: dict[str, Any] = {}
    for line in normalize_multiline_text(section_text).splitlines():
        if not re.search(r"\d", line):
            continue
        match = re.match(r"(?P<label>[A-Za-z/&(),.% -]+?)\s+(?P<values>(?:[-+]?\d[\d.,%]*\s+){1,8}[-+]?\d[\d.,%]*)$", line)
        if match:
            values = [token for token in match.group("values").split() if token]
            indicators[compact_spaces(match.group("label"))] = values
        else:
            key = f"line_{len(indicators) + 1}"
            indicators[key] = compact_spaces(line)
    return indicators


def parse_rating_components(agency_name: str, rating_text: str | None) -> RatingComponents:
    label = compact_spaces(rating_text)
    normalization = normalize_rating_label(agency_name, label)
    long_term_match = re.search(rf"(?<![A-Z0-9]){LONG_TERM_PATTERN}(?![A-Z0-9])", (label or "").upper())
    short_term_match = re.search(rf"(?<![A-Z0-9]){SHORT_TERM_PATTERN}(?![A-Z0-9])", (label or "").upper())
    outlook = normalization.outlook or normalize_outlook(label)
    return RatingComponents(
        long_term_rating=long_term_match.group(1).upper() if long_term_match else None,
        short_term_rating=short_term_match.group(1).upper() if short_term_match else None,
        outlook=outlook,
        watch_status=normalization.watch_status,
        rating_rank_numeric=normalization.rating_rank_numeric,
        is_withdrawn=normalization.is_withdrawn,
        is_issuer_not_cooperating=normalization.is_issuer_not_cooperating or normalization.is_not_cooperating,
        is_best_available_information=normalization.is_best_available_information,
    )


def extract_rating_action(text: str | None) -> str | None:
    if not text:
        return None
    match = re.search(
        r"\b(reaffirmed|upgraded|downgraded|withdrawn|assigned|revised|removed from issuer not cooperating category|continues to remain)\b",
        text,
        flags=re.I,
    )
    if not match:
        return None
    value = match.group(1)
    return " ".join(token.capitalize() if token.lower() != "to" else token.lower() for token in value.split())


def build_rating_event(
    *,
    rationale_doc_id: str,
    company_name: str,
    agency_name: str,
    rating_date: Any,
    instrument_type: str | None,
    facility_amount: float | None,
    current_rating: str | None,
    previous_rating: str | None = None,
    rating_action: str | None = None,
    event_index: int = 1,
) -> RatingEvent:
    current = parse_rating_components(agency_name, current_rating)
    previous = parse_rating_components(agency_name, previous_rating) if previous_rating else None
    instrument_slug = slugify(instrument_type or f"event_{event_index}")
    return RatingEvent(
        rating_event_id=f"{rationale_doc_id}__{instrument_slug}__{event_index:02d}",
        company_name=company_name,
        agency_name=agency_name,
        rating_date=rating_date,
        instrument_type=instrument_type,
        facility_amount=facility_amount,
        long_term_rating=current.long_term_rating,
        short_term_rating=current.short_term_rating,
        outlook=current.outlook,
        watch_status=current.watch_status,
        rating_action=rating_action or extract_rating_action(current_rating),
        previous_rating=compact_spaces(previous_rating) if previous_rating else None,
        current_rating=compact_spaces(current_rating) if current_rating else None,
        rating_rank_numeric=current.rating_rank_numeric or (previous.rating_rank_numeric if previous else None),
        is_withdrawn=current.is_withdrawn,
        is_issuer_not_cooperating=current.is_issuer_not_cooperating or current.is_best_available_information,
        rationale_doc_id=rationale_doc_id,
    )


def find_amount_near_label(text: str, label: str) -> float | None:
    pattern = rf"{re.escape(label)}\s+(?P<amount>\d[\d,.]*)"
    match = re.search(pattern, text, flags=re.I)
    if not match:
        return None
    return parse_amount_to_crore(match.group("amount"))


def _looks_like_company_name(line: str) -> bool:
    if not re.search(r"\b(Limited|Ltd\.?|Private Limited|Pvt\.?\s+Ltd\.?)\b", line, flags=re.I):
        return False
    if any(token in line.lower() for token in ("ratings", "press release", "page |", "www.", "analytical approach")):
        return False
    return True
