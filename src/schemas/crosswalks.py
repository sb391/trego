from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict


LONG_TERM_ORDER = [
    "AAA",
    "AA+",
    "AA",
    "AA-",
    "A+",
    "A",
    "A-",
    "BBB+",
    "BBB",
    "BBB-",
    "BB+",
    "BB",
    "BB-",
    "B+",
    "B",
    "B-",
    "C+",
    "C",
    "D",
]

SHORT_TERM_ORDER = [
    "A1+",
    "A1",
    "A2+",
    "A2",
    "A3+",
    "A3",
    "A4+",
    "A4",
    "D",
]

SHORT_TERM_ALIASES = {
    "P1+": "A1+",
    "P1": "A1",
    "P2+": "A2+",
    "P2": "A2",
    "P3+": "A3+",
    "P3": "A3",
    "P4+": "A4+",
    "P4": "A4",
    "P5": "D",
}

OUTLOOK_VALUES = {
    "stable": "Stable",
    "positive": "Positive",
    "negative": "Negative",
    "developing": "Developing",
}

AGENCY_PREFIXES = {
    "crisil": ("CRISIL",),
    "care": ("CARE", "CAREEDGE"),
    "india_ratings": ("IND", "IND-RA", "INDIA RATINGS"),
    "acuite": ("ACUITE", "ACUITEE"),
    "brickwork": ("BWR", "BRICKWORK"),
    "infomerics": ("IVR", "INFOMERICS"),
    "icra": ("ICRA",),
}

SPECIAL_STATE_PATTERNS = {
    "withdrawn": re.compile(r"\bWITHDRAWN\b", re.I),
    "issuer_not_cooperating": re.compile(r"\bISSUER\s+NOT\s+COOPERATING\b", re.I),
    "not_cooperating": re.compile(r"\bNOT\s+COOPERATING\b", re.I),
    "best_available_information": re.compile(r"\bBEST\s+AVAILABLE\s+INFORMATION\b", re.I),
}


class RatingScaleEntry(BaseModel):
    model_config = ConfigDict(extra="allow")

    agency_name: str
    original_label: str
    scale_type: Literal["long_term", "short_term"]
    normalized_label: str
    rating_rank_numeric: int


class RatingNormalization(BaseModel):
    model_config = ConfigDict(extra="allow")

    agency_name: str
    original_label: str
    cleaned_label: str
    scale_type: str | None = None
    normalized_label: str | None = None
    rating_rank_numeric: int | None = None
    outlook: str | None = None
    watch_status: str | None = None
    is_withdrawn: bool = False
    is_issuer_not_cooperating: bool = False
    is_not_cooperating: bool = False
    is_best_available_information: bool = False


def _build_scale_entries(agency_name: str) -> list[RatingScaleEntry]:
    entries: list[RatingScaleEntry] = []
    prefix = AGENCY_PREFIXES[agency_name][0]
    for idx, label in enumerate(LONG_TERM_ORDER, start=1):
        entries.append(
            RatingScaleEntry(
                agency_name=agency_name,
                original_label=f"{prefix} {label}",
                scale_type="long_term",
                normalized_label=label,
                rating_rank_numeric=idx,
            )
        )
    for idx, label in enumerate(SHORT_TERM_ORDER, start=1):
        entries.append(
            RatingScaleEntry(
                agency_name=agency_name,
                original_label=f"{prefix} {label}",
                scale_type="short_term",
                normalized_label=label,
                rating_rank_numeric=idx,
            )
        )
    return entries


AGENCY_RATING_CROSSWALKS = {
    agency_name: _build_scale_entries(agency_name)
    for agency_name in AGENCY_PREFIXES
}

LONG_TERM_RANKS = {label: index for index, label in enumerate(LONG_TERM_ORDER, start=1)}
SHORT_TERM_RANKS = {label: index for index, label in enumerate(SHORT_TERM_ORDER, start=1)}
LONG_TERM_REGEX = r"(AAA|AA\+|AA-|AA|A\+|A-|BBB\+|BBB-|BBB|BB\+|BB-|BB|B\+|B-|C\+|A|B|C|D)"
SHORT_TERM_REGEX = r"(A1\+|A1|A2\+|A2|A3\+|A3|A4\+|A4|P1\+|P1|P2\+|P2|P3\+|P3|P4\+|P4|P5|D)"


def normalize_rating_label(agency_name: str, label: str | None) -> RatingNormalization:
    original_label = label or ""
    cleaned = _clean_rating_label(original_label)

    normalization = RatingNormalization(
        agency_name=agency_name,
        original_label=original_label,
        cleaned_label=cleaned,
    )
    normalization.is_withdrawn = bool(SPECIAL_STATE_PATTERNS["withdrawn"].search(cleaned))
    normalization.is_issuer_not_cooperating = bool(SPECIAL_STATE_PATTERNS["issuer_not_cooperating"].search(cleaned))
    normalization.is_not_cooperating = bool(SPECIAL_STATE_PATTERNS["not_cooperating"].search(cleaned))
    normalization.is_best_available_information = bool(
        SPECIAL_STATE_PATTERNS["best_available_information"].search(cleaned)
    )
    normalization.outlook = _extract_outlook(cleaned)
    normalization.watch_status = _extract_watch_status(cleaned)

    long_term_match = re.search(rf"(?<![A-Z0-9]){LONG_TERM_REGEX}(?![A-Z0-9])", cleaned)
    short_term_match = re.search(rf"(?<![A-Z0-9]){SHORT_TERM_REGEX}(?![A-Z0-9])", cleaned)

    if long_term_match:
        label_value = long_term_match.group(1)
        normalization.scale_type = "long_term"
        normalization.normalized_label = label_value
        normalization.rating_rank_numeric = LONG_TERM_RANKS[label_value]
        return normalization

    if short_term_match:
        label_value = short_term_match.group(1)
        canonical_label = SHORT_TERM_ALIASES.get(label_value, label_value)
        normalization.scale_type = "short_term"
        normalization.normalized_label = canonical_label
        normalization.rating_rank_numeric = SHORT_TERM_RANKS[canonical_label]
        return normalization

    return normalization


def extract_special_states(label: str | None) -> dict[str, bool]:
    cleaned = _clean_rating_label(label or "")
    return {
        "is_withdrawn": bool(SPECIAL_STATE_PATTERNS["withdrawn"].search(cleaned)),
        "is_issuer_not_cooperating": bool(SPECIAL_STATE_PATTERNS["issuer_not_cooperating"].search(cleaned)),
        "is_not_cooperating": bool(SPECIAL_STATE_PATTERNS["not_cooperating"].search(cleaned)),
        "is_best_available_information": bool(
            SPECIAL_STATE_PATTERNS["best_available_information"].search(cleaned)
        ),
    }


def normalize_outlook(label: str | None) -> str | None:
    cleaned = _clean_rating_label(label or "").lower()
    for token, normalized in OUTLOOK_VALUES.items():
        if re.search(rf"\b{re.escape(token)}\b", cleaned):
            return normalized
    return None


def _clean_rating_label(label: str) -> str:
    text = (label or "").upper()
    text = text.replace("[", " ").replace("]", " ")
    text = text.replace("(", " ").replace(")", " ")
    text = text.replace(";", " ")
    text = text.replace(",", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _extract_outlook(label: str) -> str | None:
    match = re.search(r"\b(STABLE|POSITIVE|NEGATIVE)\b", label)
    return match.group(1).title() if match else None


def _extract_watch_status(label: str) -> str | None:
    match = re.search(r"\b(WATCH|OUTLOOK/WATCH|DEVELOPING)\b", label)
    return match.group(1).title() if match else None
