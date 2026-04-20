from __future__ import annotations

import html
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Iterable
from urllib.parse import urljoin


LONG_TERM_RATINGS = (
    "AAA",
    "AA+",
    "AA-",
    "AA",
    "A+",
    "A-",
    "A",
    "BBB+",
    "BBB-",
    "BBB",
    "BB+",
    "BB-",
    "BB",
    "B+",
    "B-",
    "B",
    "C",
    "D",
)

SHORT_TERM_RATINGS = (
    "A1+",
    "A1",
    "A2+",
    "A2",
    "A3",
    "A4",
    "D",
)

OUTLOOK_PATTERN = r"(?:stable|positive|negative|watch|developing|issuer not cooperating)"
LONG_TERM_PATTERN = r"(?:AAA|AA\+|AA-|AA|A\+|A-|A|BBB\+|BBB-|BBB|BB\+|BB-|BB|B\+|B-|B|C|D)"
SHORT_TERM_PATTERN = r"(?:A1\+|A1|A2\+|A2|A3|A4|D)"

AGENCY_PATTERNS: dict[str, tuple[str, ...]] = {
    "crisil": (r"crisil",),
    "icra": (r"\[icra\]", r"icra"),
    "care": (r"care",),
    "fitch": (r"ind(?:ia)?", r"fitch"),
    "indiaratings": (r"ind(?:ia)?", r"fitch"),
    "smera": (r"acuite", r"smera"),
    "acuite": (r"acuite", r"smera"),
}


@dataclass(slots=True)
class RatingUpdateMetadata:
    rating_date: str | None
    rating_date_display: str | None
    rating_agency: str | None
    notes: str | None


@dataclass(slots=True)
class ParsedRatingResult:
    rating: str | None
    rating_scale: str | None
    extraction_method: str | None
    notes: str | None


def normalize_text(value: str) -> str:
    cleaned = html.unescape(value or "")
    cleaned = cleaned.replace("\u2018", "'").replace("\u2019", "'")
    cleaned = cleaned.replace("\u201c", '"').replace("\u201d", '"')
    cleaned = cleaned.replace("\xa0", " ")
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip()


def parse_rating_update_metadata(raw_text: str, *, current_year: int | None = None) -> RatingUpdateMetadata:
    cleaned = normalize_text(raw_text)
    cleaned = re.sub(r"^Rating update\s*", "", cleaned, flags=re.I).strip()

    if not cleaned:
        return RatingUpdateMetadata(None, None, None, "Rating update label was empty.")

    parts = re.split(r"\s+from\s+", cleaned, maxsplit=1, flags=re.I)
    date_part = parts[0].strip() if parts else cleaned
    agency = parts[1].strip().lower() if len(parts) == 2 else None

    inferred_year = current_year or datetime.now().year
    date_text = date_part
    notes: list[str] = []
    if re.search(r"\b\d{4}\b", date_text) is None and date_text:
        date_text = f"{date_text} {inferred_year}"
        notes.append(f"Year inferred as {inferred_year}.")

    rating_date = _parse_rating_date(date_text)
    if rating_date is None:
        notes.append(f"Could not parse rating date from {date_part!r}.")

    return RatingUpdateMetadata(
        rating_date=rating_date,
        rating_date_display=date_part or None,
        rating_agency=agency or None,
        notes=" ".join(notes) or None,
    )


def extract_pdf_url_from_html(html_text: str, *, base_url: str) -> str | None:
    patterns = (
        r'src=["\']([^"\']+\.pdf(?:\?[^"\']*)?)["\']',
        r'window\.location\.href\s*=\s*["\']([^"\']+\.pdf(?:\?[^"\']*)?)["\']',
        r'["\']((?:https?:)?//[^"\']+\.pdf(?:\?[^"\']*)?)["\']',
        r'["\'](\/Rating\/GetRationalReportFilePdf\?Id=\d+)["\']',
        r'file=([^"&]+(?:ShowRationalReportFilePdf\/\d+|\.pdf(?:\?[^"&]*)?))',
    )
    for pattern in patterns:
        match = re.search(pattern, html_text, flags=re.I)
        if match:
            return urljoin(base_url, match.group(1))
    return None


def extract_rating_from_text(text: str, *, agency: str | None = None) -> ParsedRatingResult:
    normalized = normalize_text(text)[:12000]
    if not normalized:
        return ParsedRatingResult(None, None, None, "Document text was empty.")

    agency_regexes = _agency_regexes(agency)

    long_term_patterns = [
        (
            "long_term_keyword",
            rf"long(?:-| )term rating[^A-Z0-9]{{0,50}}(?:{agency_regexes})?\s*({LONG_TERM_PATTERN})\b",
        ),
        (
            "headline_rating",
            rf"ratings? [a-z ]{{0,40}} at ['\"]?(?:{agency_regexes})\s*({LONG_TERM_PATTERN})\b",
        ),
        (
            "prefixed_outlook",
            rf"(?:{agency_regexes})\s*({LONG_TERM_PATTERN})\s*(?:/|\(|;|\|)\s*(?:{OUTLOOK_PATTERN})",
        ),
        (
            "assigned_with_outlook",
            rf"rating assigned(?: along with outlook/watch)?[^A-Z0-9]{{0,120}}(?:{agency_regexes})\s*({LONG_TERM_PATTERN})(?:/|;|\||\()",
        ),
        (
            "agency_prefixed",
            rf"(?:{agency_regexes})\s*({LONG_TERM_PATTERN})\b",
        ),
    ]

    for method, pattern in long_term_patterns:
        result = _first_match(normalized, (pattern,), scale="long_term", method=method)
        if result.rating is not None:
            return result

    short_term_patterns = [
        (
            "short_term_keyword",
            rf"short(?:-| )term rating[^A-Z0-9]{{0,50}}(?:{agency_regexes})?\s*({SHORT_TERM_PATTERN})\b",
        ),
        (
            "short_term_prefixed",
            rf"(?:{agency_regexes})\s*({SHORT_TERM_PATTERN})\b",
        ),
    ]

    for method, pattern in short_term_patterns:
        result = _first_match(normalized, (pattern,), scale="short_term", method=method)
        if result.rating is not None:
            return result

    return ParsedRatingResult(None, None, None, "No recognizable rating symbol was found in the document text.")


def _parse_rating_date(value: str) -> str | None:
    for fmt in ("%d %b %Y", "%d %B %Y"):
        try:
            return datetime.strptime(value, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def _agency_regexes(agency: str | None) -> str:
    if agency:
        patterns = AGENCY_PATTERNS.get(agency.lower())
        if patterns:
            return "|".join(patterns)
    return "|".join({pattern for values in AGENCY_PATTERNS.values() for pattern in values})


def _first_match(
    text: str,
    patterns: Iterable[str],
    *,
    scale: str,
    method: str,
) -> ParsedRatingResult:
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.I)
        if match:
            rating = match.group(1).upper()
            snippet = match.group(0)[:180]
            return ParsedRatingResult(
                rating=rating,
                rating_scale=scale,
                extraction_method=method,
                notes=f"Matched snippet: {snippet}",
            )
    return ParsedRatingResult(None, None, None, None)
