from __future__ import annotations

import calendar
import math
import re
from datetime import datetime
from urllib.parse import parse_qs, urlsplit


EMPTY_VALUES = {"", "-", "--", "---", "na", "n/a", "none", "null", "nan", "nil"}
ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def clean_text(value: str | None) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", value.replace("\xa0", " ")).strip()


def clean_row_label(value: str | None) -> str:
    cleaned = clean_text(value)
    cleaned = cleaned.replace(" +", "").replace("+", " ")
    cleaned = re.sub(r"\s+\[\d+\]$", "", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip()


def canonicalize_metric_key(value: str | None) -> str:
    cleaned = clean_row_label(value).lower()
    cleaned = cleaned.replace("&", "and")
    cleaned = cleaned.replace("%", " percent")
    cleaned = cleaned.replace("/", " ")
    cleaned = cleaned.replace(".", " ")
    cleaned = re.sub(r"[^a-z0-9]+", "_", cleaned)
    cleaned = re.sub(r"_+", "_", cleaned).strip("_")
    return cleaned


def normalize_cell_text(value: str | None) -> str | None:
    cleaned = clean_text(value)
    if cleaned.lower() in EMPTY_VALUES:
        return None
    return cleaned


def parse_numeric_value(value: str | None) -> float | None:
    cleaned = normalize_cell_text(value)
    if cleaned is None:
        return None

    is_negative = False
    if cleaned.startswith("(") and cleaned.endswith(")"):
        is_negative = True
        cleaned = cleaned[1:-1].strip()

    normalized = (
        cleaned.replace(",", "")
        .replace("%", "")
        .replace("₹", "")
        .replace("Rs.", "")
        .replace("Rs", "")
        .replace("Cr.", "")
        .replace("Cr", "")
        .replace("crores", "")
        .replace("crore", "")
        .replace("x", "")
        .replace("X", "")
        .replace("−", "-")
        .strip()
    )
    if normalized.lower() in EMPTY_VALUES:
        return None

    match = re.search(r"-?\d+(?:\.\d+)?", normalized)
    if match is None:
        return None
    numeric_value = float(match.group())
    if is_negative and numeric_value > 0:
        return -numeric_value
    return numeric_value


def parse_integer_value(value: str | None) -> int | None:
    numeric_value = parse_numeric_value(value)
    if numeric_value is None:
        return None
    return int(round(numeric_value))


def parse_scope_from_text(value: str | None) -> str | None:
    cleaned = clean_text(value).lower()
    if "consolidated figures" in cleaned:
        return "consolidated"
    if "standalone figures" in cleaned:
        return "standalone"
    return None


def parse_statement_scope_from_url(url: str) -> str:
    path = urlsplit(url).path.lower()
    if "/consolidated/" in path:
        return "consolidated"
    return "standalone"


def parse_unit_from_text(value: str | None) -> str | None:
    cleaned = clean_text(value)
    match = re.search(r"Figures in (.+?)(?:/|$)", cleaned, flags=re.IGNORECASE)
    if match is None:
        return None
    return clean_text(match.group(1))


def safe_divide(numerator: float | None, denominator: float | None) -> float | None:
    if numerator is None or denominator in {None, 0}:
        return None
    return numerator / denominator


def parse_nse_symbol(url: str | None) -> str | None:
    if not url:
        return None
    query = parse_qs(urlsplit(url).query)
    symbol = query.get("symbol", [])
    return symbol[0] if symbol else None


def normalize_scalar_value(value: object) -> object:
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    if isinstance(value, str):
        cleaned = normalize_cell_text(value)
        return cleaned
    return value


def canonicalize_period_type(value: str | None) -> str | None:
    cleaned = clean_text(value).lower()
    if not cleaned:
        return None
    aliases = {
        "annual": "annual",
        "yearly": "annual",
        "quarterly": "quarterly",
        "quarter": "quarterly",
        "ttm": "ttm",
    }
    return aliases.get(cleaned, cleaned)


def normalize_period_value(
    period_label: str | None,
    period_key: str | None,
    *,
    default_period_type: str | None,
) -> dict[str, str | None]:
    normalized_period_type = canonicalize_period_type(default_period_type)
    for candidate in (clean_text(period_key), clean_text(period_label)):
        if not candidate:
            continue
        if candidate.upper() == "TTM":
            return {
                "period": "TTM",
                "period_type": "ttm",
            }
        if ISO_DATE_RE.match(candidate):
            return {
                "period": candidate,
                "period_type": normalized_period_type,
            }
        for fmt in ("%b %Y", "%B %Y"):
            try:
                parsed = datetime.strptime(candidate, fmt)
            except ValueError:
                continue
            last_day = calendar.monthrange(parsed.year, parsed.month)[1]
            return {
                "period": f"{parsed.year:04d}-{parsed.month:02d}-{last_day:02d}",
                "period_type": normalized_period_type,
            }

    fallback = clean_text(period_key) or clean_text(period_label) or None
    return {
        "period": fallback,
        "period_type": normalized_period_type,
    }
