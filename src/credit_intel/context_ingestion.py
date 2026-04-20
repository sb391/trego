from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import pandas as pd


LOGGER = logging.getLogger(__name__)

CANONICAL_CONTEXT_COLUMNS = [
    "company_id",
    "company_name",
    "as_of_date",
    "source_type",
    "promoter_bureau_score",
    "promoter_delinquency_count",
    "promoter_overdue_accounts",
    "promoter_overdue_amount_lakh",
    "criminal_case_count",
    "criminal_case_flag",
    "regulatory_risk_score",
    "governance_risk_score",
    "projected_revenue_cagr_5y",
    "projected_ebitda_margin_pct_5y",
    "projected_debt_to_equity_5y",
    "projected_interest_coverage_5y",
    "industry_expected_revenue_cagr_5y",
    "industry_expected_ebitda_margin_pct_5y",
    "execution_track_record_score",
    "plan_progress_score",
    "plan_submission_available",
    "plan_on_track_flag",
    "promoter_adverse_hits",
    "public_negative_news_hits",
    "fraud_signal_hits",
    "regulatory_action_hits",
    "insolvency_signal_hits",
    "litigation_signal_hits",
    "public_risk_score",
    "industry_outlook_score",
    "public_risk_flag",
    "notes",
]

CONTEXT_COLUMN_ALIASES = {
    "company_id": "company_id",
    "company code": "company_id",
    "company_code": "company_id",
    "name": "company_name",
    "company": "company_name",
    "company_name": "company_name",
    "as_of": "as_of_date",
    "as_of_date": "as_of_date",
    "as of": "as_of_date",
    "date": "as_of_date",
    "source": "source_type",
    "source_type": "source_type",
    "bureau_score": "promoter_bureau_score",
    "bureau score": "promoter_bureau_score",
    "promoter_bureau_score": "promoter_bureau_score",
    "promoter bureau score": "promoter_bureau_score",
    "promoter_delinquency_count": "promoter_delinquency_count",
    "promoter delinquency count": "promoter_delinquency_count",
    "delinquency_count": "promoter_delinquency_count",
    "promoter_overdue_accounts": "promoter_overdue_accounts",
    "overdue_accounts": "promoter_overdue_accounts",
    "promoter_overdue_amount_lakh": "promoter_overdue_amount_lakh",
    "overdue_amount_lakh": "promoter_overdue_amount_lakh",
    "criminal_case_count": "criminal_case_count",
    "criminal cases": "criminal_case_count",
    "criminal_case_flag": "criminal_case_flag",
    "criminal_flag": "criminal_case_flag",
    "criminal flag": "criminal_case_flag",
    "regulatory_risk_score": "regulatory_risk_score",
    "regulatory risk score": "regulatory_risk_score",
    "governance_risk_score": "governance_risk_score",
    "governance risk score": "governance_risk_score",
    "projected_revenue_cagr_5y": "projected_revenue_cagr_5y",
    "projected revenue cagr 5y": "projected_revenue_cagr_5y",
    "projected_ebitda_margin_pct_5y": "projected_ebitda_margin_pct_5y",
    "projected ebitda margin pct 5y": "projected_ebitda_margin_pct_5y",
    "projected_debt_to_equity_5y": "projected_debt_to_equity_5y",
    "projected_interest_coverage_5y": "projected_interest_coverage_5y",
    "industry_expected_revenue_cagr_5y": "industry_expected_revenue_cagr_5y",
    "industry expected revenue cagr 5y": "industry_expected_revenue_cagr_5y",
    "industry_expected_ebitda_margin_pct_5y": "industry_expected_ebitda_margin_pct_5y",
    "industry expected ebitda margin pct 5y": "industry_expected_ebitda_margin_pct_5y",
    "execution_track_record_score": "execution_track_record_score",
    "execution track record score": "execution_track_record_score",
    "plan_progress_score": "plan_progress_score",
    "plan progress score": "plan_progress_score",
    "plan_submission_available": "plan_submission_available",
    "plan_on_track_flag": "plan_on_track_flag",
    "promoter_adverse_hits": "promoter_adverse_hits",
    "promoter adverse hits": "promoter_adverse_hits",
    "public_negative_news_hits": "public_negative_news_hits",
    "public negative news hits": "public_negative_news_hits",
    "negative_news_hits": "public_negative_news_hits",
    "fraud_signal_hits": "fraud_signal_hits",
    "fraud signal hits": "fraud_signal_hits",
    "regulatory_action_hits": "regulatory_action_hits",
    "regulatory action hits": "regulatory_action_hits",
    "insolvency_signal_hits": "insolvency_signal_hits",
    "insolvency signal hits": "insolvency_signal_hits",
    "litigation_signal_hits": "litigation_signal_hits",
    "litigation signal hits": "litigation_signal_hits",
    "public_risk_score": "public_risk_score",
    "public risk score": "public_risk_score",
    "industry_outlook_score": "industry_outlook_score",
    "industry outlook score": "industry_outlook_score",
    "public_risk_flag": "public_risk_flag",
    "public risk flag": "public_risk_flag",
    "notes": "notes",
}

BOOLEAN_COLUMNS = {
    "criminal_case_flag",
    "plan_submission_available",
    "plan_on_track_flag",
    "public_risk_flag",
}

NUMERIC_COLUMNS = {
    "promoter_bureau_score",
    "promoter_delinquency_count",
    "promoter_overdue_accounts",
    "promoter_overdue_amount_lakh",
    "criminal_case_count",
    "regulatory_risk_score",
    "governance_risk_score",
    "projected_revenue_cagr_5y",
    "projected_ebitda_margin_pct_5y",
    "projected_debt_to_equity_5y",
    "projected_interest_coverage_5y",
    "industry_expected_revenue_cagr_5y",
    "industry_expected_ebitda_margin_pct_5y",
    "execution_track_record_score",
    "plan_progress_score",
    "promoter_adverse_hits",
    "public_negative_news_hits",
    "fraud_signal_hits",
    "regulatory_action_hits",
    "insolvency_signal_hits",
    "litigation_signal_hits",
    "public_risk_score",
    "industry_outlook_score",
}


def build_context_feature_dataset(
    *,
    input_path: Path,
    output_dir: Path,
) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    normalized = normalize_context_frame(_load_context_input(input_path))
    context_path = output_dir / "context_features.csv"
    template_path = output_dir / "context_feature_template.csv"
    status_path = output_dir / "context_ingestion_status.csv"

    normalized.to_csv(context_path, index=False)
    pd.DataFrame(columns=CANONICAL_CONTEXT_COLUMNS).to_csv(template_path, index=False)
    pd.DataFrame(
        [
            {
                "input_path": str(input_path),
                "rows_loaded": int(len(normalized)),
                "company_rows": int(normalized["company_id"].fillna("").astype(str).str.strip().ne("").sum()) if not normalized.empty else 0,
                "status": "parsed" if not normalized.empty else "empty",
            }
        ]
    ).to_csv(status_path, index=False)
    return {
        "context_features": context_path,
        "context_feature_template": template_path,
        "context_ingestion_status": status_path,
    }


def normalize_context_frame(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame(columns=CANONICAL_CONTEXT_COLUMNS)

    working = frame.copy()
    renamed: dict[str, str] = {}
    for column in working.columns:
        normalized_column = _normalize_column_name(column)
        if normalized_column in CONTEXT_COLUMN_ALIASES:
            renamed[column] = CONTEXT_COLUMN_ALIASES[normalized_column]
    working = working.rename(columns=renamed)

    for column in CANONICAL_CONTEXT_COLUMNS:
        if column not in working.columns:
            working[column] = None

    working = working[CANONICAL_CONTEXT_COLUMNS].copy()
    working["as_of_date"] = pd.to_datetime(working["as_of_date"], errors="coerce").dt.date.astype("string")

    for column in NUMERIC_COLUMNS:
        working[column] = pd.to_numeric(working[column], errors="coerce")
    for column in BOOLEAN_COLUMNS:
        working[column] = working[column].apply(_to_bool)

    working["company_id"] = working["company_id"].fillna("").astype(str).str.strip()
    working["company_name"] = working["company_name"].fillna("").astype(str).str.strip()
    working["source_type"] = working["source_type"].fillna("manual_context").astype(str).str.strip()
    working["notes"] = working["notes"].fillna("").astype(str).str.strip()

    if working["company_id"].eq("").all() and not working["company_name"].eq("").all():
        working["company_id"] = working["company_name"].str.replace(r"[^A-Za-z0-9]+", "_", regex=True).str.strip("_")

    return working.drop_duplicates(subset=["company_id", "as_of_date", "source_type"], keep="last").reset_index(drop=True)


def _load_context_input(input_path: Path) -> pd.DataFrame:
    suffix = input_path.suffix.lower()
    if suffix == ".csv":
        return pd.read_csv(input_path)
    if suffix in {".xlsx", ".xls"}:
        return pd.read_excel(input_path)
    if suffix == ".json":
        payload = json.loads(input_path.read_text(encoding="utf-8"))
        if isinstance(payload, list):
            return pd.DataFrame(payload)
        if isinstance(payload, dict):
            if isinstance(payload.get("rows"), list):
                return pd.DataFrame(payload["rows"])
            return pd.DataFrame([payload])
    raise ValueError(f"Unsupported context input format: {input_path}")


def _normalize_column_name(value: Any) -> str:
    text = str(value).strip().lower()
    return " ".join(part for part in "".join(character if character.isalnum() else " " for character in text).split())


def _to_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return False
    if isinstance(value, (int, float)):
        return bool(value)
    return str(value).strip().lower() in {"1", "true", "yes", "y"}
