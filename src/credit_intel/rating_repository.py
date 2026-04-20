from __future__ import annotations

from pathlib import Path

import pandas as pd

from ..io_utils import normalize_company_name
from .schemas import RatingHistoryEntry, RatingInsight


AGENCY_TOKENS = ("crisil", "care", "icra", "india ratings", "ind", "acuite", "brickwork", "infomerics")


def parse_rating_text(latest_ratings_text: str | None) -> RatingInsight:
    if not latest_ratings_text:
        return RatingInsight()
    text = str(latest_ratings_text).strip()
    agency = next((token.title() for token in AGENCY_TOKENS if token in text.lower()), None)
    rating = None
    for token in ["AAA", "AA+", "AA", "AA-", "A1+", "A1", "A+", "A", "A-", "BBB+", "BBB", "BBB-", "BB+", "BB", "BB-", "B+", "B", "B-", "C+", "C", "D", "A4+", "A4", "A3+", "A3"]:
        if token in text.upper():
            rating = token
            break
    return RatingInsight(
        rating_available_flag=rating is not None,
        rating_status="available" if rating else "not_available",
        agency_name=agency,
        rating=rating,
        history=[
            RatingHistoryEntry(
                agency_name=agency,
                rating=rating,
                current_rating_text=text,
                source="dataset_hint",
            )
        ] if rating else [],
        notes=["Parsed from agriculture master dataset."] if rating else [],
    )


class ExistingRatingRepository:
    def __init__(self, history_path: Path) -> None:
        self.history_path = history_path

    def lookup(self, company_name: str) -> RatingInsight | None:
        if not self.history_path.exists():
            return None
        frame = pd.read_csv(self.history_path)
        if frame.empty or "company_name" not in frame.columns:
            return None
        normalized = normalize_company_name(company_name)
        frame["_normalized_name"] = frame["company_name"].astype(str).map(normalize_company_name)
        matches = frame[frame["_normalized_name"] == normalized].copy()
        if matches.empty:
            return None
        if "rating_date" in matches.columns:
            matches["rating_date"] = pd.to_datetime(matches["rating_date"], errors="coerce")
            matches = matches.sort_values("rating_date", ascending=False)
        latest = matches.iloc[0]
        history = [
            RatingHistoryEntry(
                rating_date=_string(row.get("rating_date")),
                agency_name=_string(row.get("rating_agency")),
                rating=_string(row.get("rating")),
                source_url=_string(row.get("rating_update_url")),
                current_rating_text=_string(row.get("notes")),
                source="existing_credit_rating_history",
            )
            for row in matches.to_dict(orient="records")
        ]
        return RatingInsight(
            rating_available_flag=bool(_string(latest.get("rating"))),
            rating_status="available" if _string(latest.get("rating")) else "not_available",
            agency_name=_string(latest.get("rating_agency")),
            rating=_string(latest.get("rating")),
            rating_date=_iso_timestamp(latest.get("rating_date")),
            rating_action=None,
            history=history,
            notes=["Loaded from cached Screener-derived credit rating history."],
        )


def _iso_timestamp(value) -> str | None:  # type: ignore[no-untyped-def]
    if pd.isna(value):
        return None
    if hasattr(value, "date"):
        try:
            return value.date().isoformat()
        except Exception:  # noqa: BLE001
            return str(value)
    return _string(value)


def _string(value) -> str | None:  # type: ignore[no-untyped-def]
    if value is None or (hasattr(pd, "isna") and pd.isna(value)):
        return None
    text = str(value).strip()
    return text or None
