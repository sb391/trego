from __future__ import annotations

from functools import lru_cache
from pathlib import Path
import re
from typing import Any

import pandas as pd

from ..io_utils import normalize_company_name
from .config import CreditIntelConfig
from .matching import score_name_match
from .schemas import MatchedDatasetCompany


def _slugify_header(value: str) -> str:
    text = str(value).strip().lower()
    text = text.replace("%", " pct ")
    text = text.replace("&", " and ")
    text = text.replace("/", " ")
    text = text.replace("*", " ")
    text = re.sub(r"[^a-z0-9]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("_")
    return text or "unknown"


def _flatten_excel_columns(columns: pd.MultiIndex) -> list[str]:
    flattened: list[str] = []
    seen: dict[str, int] = {}
    for top, bottom in columns.tolist():
        top_value = str(top).strip()
        bottom_value = str(bottom).strip()
        if not bottom_value or bottom_value.startswith("Unnamed"):
            column_name = _slugify_header(top_value)
        else:
            column_name = f"{_slugify_header(top_value)}__{_slugify_header(bottom_value)}"
        count = seen.get(column_name, 0)
        flattened.append(column_name if count == 0 else f"{column_name}_{count + 1}")
        seen[column_name] = count + 1
    return flattened


def _coerce_float(value: Any) -> float | None:
    try:
        if value is None or (isinstance(value, float) and pd.isna(value)):
            return None
        text = str(value).strip().replace(",", "").replace("%", "")
        if not text or text.lower() in {"nan", "none", "-"}:
            return None
        return float(text)
    except (TypeError, ValueError):
        return None


def _coerce_bool(value: Any) -> bool | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    text = str(value).strip().lower()
    if text in {"yes", "y", "true"}:
        return True
    if text in {"no", "n", "false", "-", ""}:
        return False
    return None


@lru_cache(maxsize=2)
def load_agriculture_dataset(workbook_path: str) -> pd.DataFrame:
    raw = pd.read_excel(Path(workbook_path), sheet_name="Explore Excel", header=[1, 2])
    raw.columns = _flatten_excel_columns(raw.columns)
    frame = raw.copy()
    frame = frame.rename(
        columns={
            "sr_no": "sr_no",
            "company_name": "company_name",
            "overview__cin": "cin",
            "overview__comp_id": "company_id",
            "overview__pan": "pan",
            "overview__city": "city",
            "overview__state": "state",
            "overview__status": "status",
            "overview__listing_status": "listing_status",
            "overview__products": "products",
            "overview__corpository_sector": "sector",
            "overview__business_type": "business_type",
            "overview__paid_up_capital": "paid_up_capital_crore",
            "overview__financial_year": "financial_year",
            "overview__latest_balance_sheet": "latest_balance_sheet",
            "overview__consolidated_standalone": "standalone_or_consolidated",
            "overview__total_revenue": "total_revenue_crore",
            "overview__ebitda": "ebitda_crore",
            "overview__pat": "pat_crore",
            "overview__networth": "networth_crore",
            "overview__long_term_liabilities": "long_term_liabilities_crore",
            "overview__total_borrowings": "total_borrowings_crore",
            "credit_rating__credit_rated": "credit_rated",
            "credit_rating__latest_ratings": "latest_ratings",
            "profit_loss__total_revenue_from_operations": "revenue_from_operations_crore",
            "profit_loss__total_revenue": "total_revenue_reported_crore",
            "profit_loss__ebitda": "ebitda_reported_crore",
            "profit_loss__ebitda_pct": "ebitda_margin_pct",
            "profit_loss__pat": "pat_reported_crore",
            "profit_loss__pat_pct": "pat_margin_pct",
            "profit_loss__networth": "networth_reported_crore",
            "balance_sheet__long_term_borrowings": "long_term_borrowings_crore",
            "balance_sheet__short_term_borrowings": "short_term_borrowings_crore",
            "ratios__revenue_growth": "revenue_growth_pct",
            "ratios__receivables_days": "receivables_days",
            "ratios__inventory_days": "inventory_days",
            "ratios__current_ratio": "current_ratio",
            "ratios__total_debt_equity": "debt_to_equity",
            "ratios__debt_to_ebitda": "debt_to_ebitda",
            "ratios__interest_coverage": "interest_coverage",
            "ratios__roe_pct": "roe_pct",
            "ratios__roce_pct": "roce_pct",
            "contact_details__company_email_address": "email",
            "contact_details__company_telephone_number": "phone",
            "contact_details__company_website": "website",
            "contact_details__company_address": "address",
        }
    )
    if "sector" not in frame.columns and "company_profile__corpository_sector" in frame.columns:
        frame["sector"] = frame["company_profile__corpository_sector"]
    if "listing_status" not in frame.columns and "company_profile__listing_status" in frame.columns:
        frame["listing_status"] = frame["company_profile__listing_status"]
    frame["normalized_name"] = frame["company_name"].map(normalize_company_name)
    numeric_columns = [
        "paid_up_capital_crore",
        "total_revenue_crore",
        "ebitda_crore",
        "pat_crore",
        "networth_crore",
        "long_term_liabilities_crore",
        "total_borrowings_crore",
        "revenue_from_operations_crore",
        "total_revenue_reported_crore",
        "ebitda_reported_crore",
        "ebitda_margin_pct",
        "pat_reported_crore",
        "pat_margin_pct",
        "networth_reported_crore",
        "long_term_borrowings_crore",
        "short_term_borrowings_crore",
        "revenue_growth_pct",
        "receivables_days",
        "inventory_days",
        "current_ratio",
        "debt_to_equity",
        "debt_to_ebitda",
        "interest_coverage",
        "roe_pct",
        "roce_pct",
    ]
    for column in numeric_columns:
        if column in frame.columns:
            frame[column] = frame[column].map(_coerce_float)

    frame["credit_rated_flag"] = frame.get("credit_rated", pd.Series(dtype=object)).map(_coerce_bool)
    frame["listing_status"] = frame.get("listing_status", pd.Series(dtype=object)).fillna("unknown").astype(str).str.strip().str.lower()
    frame["turnover_crore"] = (
        frame.get("total_revenue_crore", pd.Series(dtype=float))
        .fillna(frame.get("revenue_from_operations_crore", pd.Series(dtype=float)))
        .fillna(frame.get("total_revenue_reported_crore", pd.Series(dtype=float)))
    )
    return frame


class AgricultureDatasetService:
    def __init__(self, config: CreditIntelConfig) -> None:
        self.config = config

    @property
    def frame(self) -> pd.DataFrame:
        return load_agriculture_dataset(str(self.config.agriculture_workbook_path))

    def match_company(self, company_name: str) -> MatchedDatasetCompany | None:
        scored_rows: list[tuple[float, str, dict[str, Any]]] = []
        for record in self.frame.to_dict(orient="records"):
            score, reason = score_name_match(company_name, str(record.get("company_name") or ""))
            if score >= 0.72:
                scored_rows.append((score, reason, record))
        if not scored_rows:
            return None

        scored_rows.sort(key=lambda item: item[0], reverse=True)
        best_score, reason, record = scored_rows[0]
        return self._build_match(record, best_score, reason)

    def get_default_sample_companies(self, *, limit: int = 5) -> list[str]:
        frame = self.frame.copy()
        frame = frame[frame["turnover_crore"].fillna(0) > self.config.turnover_threshold_crore]
        frame = frame.sort_values("turnover_crore", ascending=False)
        return frame["company_name"].dropna().astype(str).head(limit).tolist()

    def _build_match(self, record: dict[str, Any], score: float, reason: str) -> MatchedDatasetCompany:
        return MatchedDatasetCompany(
            company_id=str(record.get("company_id") or record.get("cin") or record.get("company_name")),
            company_name=str(record.get("company_name") or ""),
            normalized_name=str(record.get("normalized_name") or ""),
            match_confidence=round(score, 4),
            cin=_string(record.get("cin")),
            pan=_string(record.get("pan")),
            listing_status=_string(record.get("listing_status")),
            status=_string(record.get("status")),
            city=_string(record.get("city")),
            state=_string(record.get("state")),
            products=_string(record.get("products")),
            sector=_string(record.get("sector")),
            business_type=_string(record.get("business_type")),
            financial_year=_string(record.get("financial_year")),
            latest_balance_sheet=_string(record.get("latest_balance_sheet")),
            standalone_or_consolidated=_string(record.get("standalone_or_consolidated")),
            total_revenue_crore=record.get("turnover_crore"),
            ebitda_crore=record.get("ebitda_crore"),
            pat_crore=record.get("pat_crore"),
            networth_crore=record.get("networth_crore"),
            total_borrowings_crore=record.get("total_borrowings_crore"),
            long_term_liabilities_crore=record.get("long_term_liabilities_crore"),
            paid_up_capital_crore=record.get("paid_up_capital_crore"),
            revenue_growth_pct=record.get("revenue_growth_pct"),
            ebitda_margin_pct=record.get("ebitda_margin_pct"),
            pat_margin_pct=record.get("pat_margin_pct"),
            debt_to_equity=record.get("debt_to_equity"),
            debt_to_ebitda=record.get("debt_to_ebitda"),
            interest_coverage=record.get("interest_coverage"),
            receivables_days=record.get("receivables_days"),
            inventory_days=record.get("inventory_days"),
            current_ratio=record.get("current_ratio"),
            roe_pct=record.get("roe_pct"),
            roce_pct=record.get("roce_pct"),
            credit_rated_flag=record.get("credit_rated_flag"),
            latest_ratings_text=_string(record.get("latest_ratings")),
            email=_string(record.get("email")),
            phone=_string(record.get("phone")),
            website=_string(record.get("website")),
            address=_string(record.get("address")),
            raw_row={**record, "_match_reason": reason},
        )


def _string(value: Any) -> str | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    text = str(value).strip()
    return text or None
