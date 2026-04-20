from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from datetime import date, datetime
from pathlib import Path


MONTH_PATTERN = r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec|January|February|March|April|June|July|August|September|October|November|December)"


def slugify(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    normalized = re.sub(r"[^A-Za-z0-9]+", "_", normalized).strip("_").lower()
    return normalized or "unknown"


def sanitize_filename(value: str) -> str:
    sanitized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    sanitized = re.sub(r"[^\w.-]+", "_", sanitized).strip("._")
    return sanitized or "unknown"


def compact_spaces(value: str | None) -> str:
    text = value or ""
    text = text.replace("\xa0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


def normalize_multiline_text(value: str | None) -> str:
    text = value or ""
    text = text.replace("\xa0", " ")
    text = text.replace("\u2013", "-").replace("\u2014", "-").replace("\u2019", "'")
    text = re.sub(r"\r\n?", "\n", text)
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    lines = [compact_spaces(line) for line in text.splitlines()]
    return "\n".join(line for line in lines).strip()


def compute_text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def parse_date_string(value: str | None) -> date | None:
    if not value:
        return None

    candidates = [
        compact_spaces(re.sub(r"\s+,", ",", value)),
        compact_spaces(re.sub(r"(\d{1,2})([A-Za-z]{3,9})(\d{4})", r"\1 \2 \3", value)),
    ]

    formats = (
        "%B %d, %Y",
        "%B %d,%Y",
        "%b %d, %Y",
        "%b %d,%Y",
        "%B %Y",
        "%b %Y",
        "%d %B %Y",
        "%d %b %Y",
        "%d%b%Y",
        "%d%B%Y",
    )

    for candidate in candidates:
        for fmt in formats:
            try:
                return datetime.strptime(candidate, fmt).date()
            except ValueError:
                continue
    return None


def find_first_date(text: str) -> date | None:
    patterns = (
        rf"\b{MONTH_PATTERN}\s+\d{{1,2}}\s*,\s*\d{{4}}\b",
        rf"\b{MONTH_PATTERN}\s+\d{{4}}\b",
        rf"\b\d{{1,2}}\s+{MONTH_PATTERN}\s+\d{{4}}\b",
        rf"\b\d{{1,2}}{MONTH_PATTERN}\d{{4}}\b",
    )
    candidates: list[tuple[int, date]] = []
    for pattern in patterns:
        for match in re.finditer(pattern, text, re.I):
            parsed = parse_date_string(match.group(0))
            if parsed:
                candidates.append((match.start(), parsed))
    if not candidates:
        return None
    candidates.sort(key=lambda item: item[0])
    return candidates[0][1]


def prettify_filename_stem(path_or_name: str | Path) -> str:
    stem = Path(path_or_name).stem
    stem = re.sub(r"^[A-Za-z]+[_-]", "", stem)
    stem = stem.replace("_", " ").replace("-", " ")
    stem = re.sub(r"\s+", " ", stem).strip()
    return stem


def parse_amount_to_crore(value: str | None, *, unit_hint: str | None = None) -> float | None:
    if value is None:
        return None
    match = re.search(r"[-+]?\d[\d,]*(?:\.\d+)?", value.replace("₹", ""))
    if not match:
        return None
    numeric = float(match.group(0).replace(",", ""))
    hint = (unit_hint or value).lower()
    if "million" in hint:
        return round(numeric / 10.0, 4)
    return numeric


def extract_bullet_like_items(value: str | None) -> list[str]:
    if not value:
        return []
    text = normalize_multiline_text(value)
    items: list[str] = []
    buffer: list[str] = []

    def flush() -> None:
        if buffer:
            item = compact_spaces(" ".join(buffer))
            if item and item not in items:
                items.append(item)
            buffer.clear()

    for raw_line in text.splitlines():
        line = compact_spaces(raw_line)
        if not line:
            flush()
            continue
        if re.match(r"^[\-•*]\s+", line):
            flush()
            buffer.append(re.sub(r"^[\-•*]\s+", "", line))
            continue
        if re.match(r"^[A-Z][A-Za-z0-9&(),'/ -]{2,100}:", line):
            flush()
            items.append(line)
            continue
        buffer.append(line)

    flush()
    return items


def sentence_case_join(lines: list[str]) -> str | None:
    cleaned = [compact_spaces(line) for line in lines if compact_spaces(line)]
    if not cleaned:
        return None
    return " ".join(cleaned)


def json_dumps_compact(value: object) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True)
