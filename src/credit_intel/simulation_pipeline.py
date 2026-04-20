from __future__ import annotations

import hashlib
import json
import logging
import pickle
import subprocess
import sys
import time
from ast import literal_eval
from collections import Counter
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import httpx
import numpy as np
import pandas as pd
from bs4 import BeautifulSoup
from sklearn.compose import ColumnTransformer
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import ExtraTreesClassifier, ExtraTreesRegressor
from sklearn.impute import SimpleImputer
from sklearn.metrics import accuracy_score, confusion_matrix
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

from ..credit_rating_parser import extract_pdf_url_from_html
from ..io_utils import load_download_status_records, load_input_companies, sanitize_filename
from ..parsers import PARSER_REGISTRY, get_parser
from ..schemas.crosswalks import LONG_TERM_ORDER, normalize_rating_label
from ..utils.pdf import detect_agency_name, extract_pdf_text
from ..utils.text import compute_text_hash, normalize_multiline_text
from .context_ingestion import normalize_context_frame
from .workbook_parser import ScreenerWorkbookParser


LOGGER = logging.getLogger(__name__)

CORE_FINANCIAL_FEATURES = [
    "revenue_crore",
    "ebitda_margin_pct",
    "pat_margin_pct",
    "debt_to_equity",
    "interest_coverage",
    "working_capital_days",
    "receivables_days",
    "inventory_days",
    "networth_crore",
    "total_borrowings_crore",
]
EXTENDED_FINANCIAL_FEATURES = [
    *CORE_FINANCIAL_FEATURES,
    "total_assets_crore",
    "cfo_to_debt",
    "cash_to_borrowings",
    "asset_turnover",
    "revenue_growth_pct",
    "profit_growth_pct",
]
ROLLING_WINDOW_SUFFIXES = ["avg3y", "delta1y", "delta2y", "std3y", "slope3y"]
ROLLING_FINANCIAL_FEATURES = [
    f"{feature}_{suffix}"
    for feature in EXTENDED_FINANCIAL_FEATURES
    for suffix in ROLLING_WINDOW_SUFFIXES
]
TREND_BINARY_FEATURES = [
    "profitability_trend_positive",
    "leverage_trend_improving",
    "coverage_trend_improving",
    "working_capital_trend_improving",
    "scale_growth_positive",
    "networth_growth_positive",
]
PRIOR_RATING_NUMERIC_FEATURES = [
    "prior_agency_rating_rank",
    "prior_any_rating_rank",
    "months_since_prior_agency_rating",
    "months_since_prior_any_rating",
    "since_prior_agency_revenue_growth_pct",
    "since_prior_agency_ebitda_margin_change",
    "since_prior_agency_debt_to_equity_change",
    "since_prior_agency_interest_coverage_change",
    "since_prior_agency_working_capital_days_change",
    "since_prior_any_revenue_growth_pct",
    "since_prior_any_ebitda_margin_change",
    "since_prior_any_debt_to_equity_change",
    "since_prior_any_interest_coverage_change",
    "since_prior_any_working_capital_days_change",
]
BENCHMARK_NUMERIC_FEATURES = [
    "industry_peer_sample_size",
    "industry_revenue_percentile",
    "industry_ebitda_margin_percentile",
    "industry_pat_margin_percentile",
    "industry_debt_to_equity_percentile",
    "industry_interest_coverage_percentile",
    "industry_working_capital_days_percentile",
    "industry_revenue_gap_to_median",
    "industry_ebitda_margin_gap_to_median",
    "industry_pat_margin_gap_to_median",
    "industry_debt_to_equity_gap_to_median",
    "industry_interest_coverage_gap_to_median",
    "industry_working_capital_days_gap_to_median",
]
TRAJECTORY_BENCHMARK_NUMERIC_FEATURES = [
    "scale_peer_sample_size",
    "scale_peer_forward_revenue_cagr",
    "scale_peer_forward_ebitda_margin_change",
    "scale_peer_forward_debt_to_equity_change",
    "scale_peer_forward_interest_coverage_change",
    "scale_peer_revenue_position_pct",
    "scale_peer_ebitda_margin_gap_to_median",
    "scale_peer_debt_to_equity_gap_to_median",
    "scale_peer_interest_coverage_gap_to_median",
    "projected_revenue_cagr_vs_scale_peers_gap",
    "projected_margin_vs_scale_peers_gap",
]
OPTIONAL_CONTEXT_NUMERIC_FEATURES = [
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
    "growth_plan_vs_industry_gap_pct",
    "margin_plan_vs_industry_gap_pct",
    "plan_aggressiveness_score",
    "promoter_adverse_hits",
    "public_negative_news_hits",
    "fraud_signal_hits",
    "regulatory_action_hits",
    "insolvency_signal_hits",
    "litigation_signal_hits",
    "public_risk_score",
    "industry_outlook_score",
]
PRIOR_RATING_BINARY_FEATURES = [
    "prior_agency_rating_available",
    "prior_any_rating_available",
]
OPTIONAL_CONTEXT_BINARY_FEATURES = [
    "promoter_delinquency_flag",
    "criminal_case_flag",
    "plan_submission_available",
    "plan_on_track_flag",
    "growth_plan_aggressive_flag",
    "public_risk_flag",
]
NUMERIC_MODEL_FEATURES = [
    *EXTENDED_FINANCIAL_FEATURES,
    *ROLLING_FINANCIAL_FEATURES,
    *PRIOR_RATING_NUMERIC_FEATURES,
    *BENCHMARK_NUMERIC_FEATURES,
    *TRAJECTORY_BENCHMARK_NUMERIC_FEATURES,
    *OPTIONAL_CONTEXT_NUMERIC_FEATURES,
]
CATEGORICAL_MODEL_FEATURES = ["sub_industry", "liquidity_label", "standalone_or_consolidated"]
RATIONALE_BINARY_FEATURES = [
    "has_management_strength",
    "has_group_support",
    "has_scale_constraint",
    "has_working_capital_pressure",
    "has_liquidity_adequate",
    "has_liquidity_stretched",
    "has_regulatory_risk",
    "has_fx_risk",
    "has_customer_concentration",
    "has_product_diversification",
    "has_export_risk",
    "has_capex_risk",
    "has_margin_pressure",
    "has_leverage_improvement",
    "has_turnaround_story",
    "has_non_cooperation_flag",
    "has_contingent_liability_risk",
    "has_msa_dependency",
    "has_capacity_expansion",
    "has_niche_complex_portfolio",
    "has_strong_roce",
    "has_net_cash_position",
]
RATIONALE_COUNT_FEATURES = [
    "strengths_count",
    "weaknesses_count",
    "sensitivities_up_count",
    "sensitivities_down_count",
    "qualitative_summary_length",
]
DERIVED_MODEL_FEATURES = [
    "days_from_financial_period",
    "data_completeness",
    "feature_coverage",
    "context_coverage",
    "history_periods_available",
    "financial_window_span_days",
    *TREND_BINARY_FEATURES,
    *PRIOR_RATING_BINARY_FEATURES,
    *OPTIONAL_CONTEXT_BINARY_FEATURES,
]
MODEL_NUMERIC_FEATURES = [
    *NUMERIC_MODEL_FEATURES,
    *RATIONALE_BINARY_FEATURES,
    *RATIONALE_COUNT_FEATURES,
    *DERIVED_MODEL_FEATURES,
]
TARGET_AGENCIES = [
    "crisil",
    "care",
    "icra",
    "india_ratings",
    "acuite",
    "brickwork",
    "infomerics",
]
AGENCY_ALIAS_MAP = {
    "acuite": "acuite",
    "acuite_ratings": "acuite",
    "brickwork": "brickwork",
    "brickwork_ratings": "brickwork",
    "care": "care",
    "care_edge": "care",
    "careedge": "care",
    "care_ratings": "care",
    "crisil": "crisil",
    "fitch": "india_ratings",
    "fitch_ratings": "india_ratings",
    "icra": "icra",
    "ind": "india_ratings",
    "india_ratings": "india_ratings",
    "india_ratings_and_research": "india_ratings",
    "india_ratings_research": "india_ratings",
    "indiaratings": "india_ratings",
    "infomerics": "infomerics",
    "smera": "acuite",
    "smera_ratings": "acuite",
}
RATIONALE_SIGNAL_LABELS = {
    "has_management_strength": "management strength",
    "has_group_support": "group support",
    "has_scale_constraint": "scale constraint",
    "has_working_capital_pressure": "working capital pressure",
    "has_liquidity_adequate": "adequate liquidity",
    "has_liquidity_stretched": "stretched liquidity",
    "has_regulatory_risk": "regulatory risk",
    "has_fx_risk": "foreign exchange risk",
    "has_customer_concentration": "customer concentration",
    "has_product_diversification": "product diversification",
    "has_export_risk": "export risk",
    "has_capex_risk": "capex risk",
    "has_margin_pressure": "margin pressure",
    "has_leverage_improvement": "leverage improvement",
    "has_turnaround_story": "turnaround story",
    "has_non_cooperation_flag": "non-cooperation flag",
    "has_contingent_liability_risk": "contingent liability risk",
    "has_msa_dependency": "MSA dependency",
    "has_capacity_expansion": "capacity expansion",
    "has_niche_complex_portfolio": "niche portfolio",
    "has_strong_roce": "strong ROCE",
    "has_net_cash_position": "net cash position",
}
SUPPORTED_AGENCIES = set(PARSER_REGISTRY)


class _BrowserTextRenderer:
    def __enter__(self) -> "_BrowserTextRenderer":
        return self

    def __exit__(self, exc_type, exc, exc_tb) -> None:
        self.close()

    def render_text(self, url: str) -> str | None:
        script = """
import sys
from playwright.sync_api import sync_playwright
from src.utils.text import normalize_multiline_text

url = sys.argv[1]
with sync_playwright() as playwright:
    browser = playwright.chromium.launch(
        headless=True,
        args=["--disable-gpu", "--disable-dev-shm-usage", "--no-sandbox", "--disable-setuid-sandbox"],
    )
    try:
        page = browser.new_page()
        page.goto(url, wait_until='domcontentloaded', timeout=60000)
        page.wait_for_timeout(4000)
        text = normalize_multiline_text(page.locator('body').first.inner_text())
        sys.stdout.write(text)
    finally:
        browser.close()
"""
        try:
            for attempt in range(1, 4):
                result = subprocess.run(
                    [sys.executable, "-c", script, url],
                    capture_output=True,
                    text=True,
                    cwd=str(Path(__file__).resolve().parents[2]),
                    timeout=120,
                    check=False,
                )
                if result.returncode == 0:
                    text = normalize_multiline_text(result.stdout)
                    return text if text else None
                if attempt < 3:
                    time.sleep(1.0)
            stderr = (result.stderr or "").strip() or f"exit code {result.returncode}"
            LOGGER.warning("Browser render failed for %s: %s", url, stderr)
            return None
        except Exception as exc:  # noqa: BLE001
            LOGGER.warning("Browser render failed for %s: %s", url, exc)
            return None

    def close(self) -> None:
        return None


def build_industry_financial_dataset(
    *,
    input_csv_path: Path,
    download_status_path: Path,
    output_dir: Path,
) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    input_frame = _load_industry_input_frame(input_csv_path)
    status_rows = load_download_status_records(download_status_path)
    parser = ScreenerWorkbookParser()

    profit_loss_rows: list[dict[str, Any]] = []
    balance_sheet_rows: list[dict[str, Any]] = []
    cash_flow_rows: list[dict[str, Any]] = []
    summary_rows: list[dict[str, Any]] = []
    annual_feature_rows: list[dict[str, Any]] = []

    for row in status_rows:
        if str(row.get("status") or "") != "downloaded":
            continue
        local_path = str(row.get("local_file_path") or "").strip()
        if not local_path:
            continue
        workbook_path = Path(local_path)
        if not workbook_path.exists():
            continue

        company_id = str(row.get("company_id") or "")
        metadata = input_frame[input_frame["company_id"] == company_id]
        if metadata.empty:
            continue
        meta_record = metadata.iloc[0].to_dict()

        try:
            parsed = parser.parse(workbook_path)
        except Exception as exc:  # noqa: BLE001
            LOGGER.warning("Failed to parse workbook for %s: %s", company_id, exc)
            continue

        summary_rows.append(
            {
                **_company_meta(meta_record),
                **parsed["financial_summary"],
                "workbook_path": str(workbook_path),
            }
        )

        pnl_by_period = {str(item.get("period")): item for item in parsed["profit_loss"]}
        bs_by_period = {str(item.get("period")): item for item in parsed["balance_sheet"]}
        cf_by_period = {str(item.get("period")): item for item in parsed["cash_flow"]}

        for statement_name, rows, collector in (
            ("profit_loss", parsed["profit_loss"], profit_loss_rows),
            ("balance_sheet", parsed["balance_sheet"], balance_sheet_rows),
            ("cash_flow", parsed["cash_flow"], cash_flow_rows),
        ):
            for item in rows:
                collector.append(
                    {
                        **_company_meta(meta_record),
                        "statement_type": statement_name,
                        **item,
                    }
                )

        ordered_periods = sorted(
            [period for period in pnl_by_period if period and period != "None"],
        )
        for index, period in enumerate(ordered_periods):
            pnl = pnl_by_period.get(period, {})
            balance = bs_by_period.get(period, {})
            cash = cf_by_period.get(period, {})
            previous_pnl = pnl_by_period.get(ordered_periods[index - 1], {}) if index > 0 else {}

            sales = _to_float(pnl.get("sales"))
            pbt = _to_float(pnl.get("profit_before_tax"))
            interest = _to_float(pnl.get("interest"))
            depreciation = _to_float(pnl.get("depreciation"))
            other_income = _to_float(pnl.get("other_income"))
            net_profit = _to_float(pnl.get("net_profit"))
            ebitda = _safe_sum([pbt, interest, depreciation, -other_income if other_income is not None else None])
            networth = _safe_sum([_to_float(balance.get("equity_share_capital")), _to_float(balance.get("reserves"))])
            borrowings = _to_float(balance.get("borrowings"))
            total_assets = _to_float(balance.get("total"))
            receivables = _to_float(balance.get("receivables"))
            inventory = _to_float(balance.get("inventory"))
            cash_and_bank = _to_float(balance.get("cash_and_bank"))
            cfo = _to_float(cash.get("cash_from_operating_activity"))
            previous_sales = _to_float(previous_pnl.get("sales"))
            previous_profit = _to_float(previous_pnl.get("net_profit"))

            receivables_days = _ratio_days(receivables, sales)
            inventory_days = _ratio_days(inventory, sales)
            feature_row = {
                **_company_meta(meta_record),
                "period": period,
                "period_date": period,
                "revenue_crore": sales,
                "ebitda_margin_pct": _ratio_pct(ebitda, sales),
                "pat_margin_pct": _ratio_pct(net_profit, sales),
                "debt_to_equity": _safe_ratio(borrowings, networth),
                "interest_coverage": _safe_ratio(ebitda, interest),
                "working_capital_days": _safe_sum([receivables_days, inventory_days]),
                "receivables_days": receivables_days,
                "inventory_days": inventory_days,
                "networth_crore": networth,
                "total_borrowings_crore": borrowings,
                "total_assets_crore": total_assets,
                "cfo_to_debt": _safe_ratio(cfo, borrowings),
                "cash_to_borrowings": _safe_ratio(cash_and_bank, borrowings),
                "asset_turnover": _safe_ratio(sales, total_assets),
                "revenue_growth_pct": _growth_pct(sales, previous_sales),
                "profit_growth_pct": _growth_pct(net_profit, previous_profit),
            }
            annual_feature_rows.append(feature_row)

    profit_loss_path = output_dir / "profit_loss_annual.csv"
    balance_sheet_path = output_dir / "balance_sheet_annual.csv"
    cash_flow_path = output_dir / "cash_flow_annual.csv"
    summary_path = output_dir / "financial_summary.csv"
    features_path = output_dir / "financial_year_features.csv"
    latest_path = output_dir / "latest_financial_features.csv"

    pd.DataFrame(profit_loss_rows).to_csv(profit_loss_path, index=False)
    pd.DataFrame(balance_sheet_rows).to_csv(balance_sheet_path, index=False)
    pd.DataFrame(cash_flow_rows).to_csv(cash_flow_path, index=False)
    pd.DataFrame(summary_rows).to_csv(summary_path, index=False)

    features_frame = pd.DataFrame(annual_feature_rows)
    if not features_frame.empty:
        features_frame = features_frame.sort_values(["company_id", "period_date"])
    features_frame.to_csv(features_path, index=False)
    latest_frame = features_frame.groupby("company_id", as_index=False).tail(1) if not features_frame.empty else features_frame
    latest_frame.to_csv(latest_path, index=False)

    return {
        "financial_summary": summary_path,
        "profit_loss_annual": profit_loss_path,
        "balance_sheet_annual": balance_sheet_path,
        "cash_flow_annual": cash_flow_path,
        "financial_year_features": features_path,
        "latest_financial_features": latest_path,
    }


def build_rationale_corpus_from_credit_history(
    *,
    credit_rating_history_path: Path,
    output_dir: Path,
    request_delay_seconds: float = 1.0,
    force: bool = False,
    agency_filter: list[str] | None = None,
    merge_with_existing: bool = False,
) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    raw_docs_dir = output_dir / "raw_docs"
    raw_text_dir = output_dir / "raw_text"
    parsed_json_dir = output_dir / "parsed_json"
    raw_docs_dir.mkdir(parents=True, exist_ok=True)
    raw_text_dir.mkdir(parents=True, exist_ok=True)
    parsed_json_dir.mkdir(parents=True, exist_ok=True)

    history_frame = pd.read_csv(credit_rating_history_path)
    history_frame = history_frame.dropna(subset=["rating_update_url"]).drop_duplicates(subset=["event_id"])
    history_frame["agency_priority"] = history_frame["rating_agency"].map(_normalize_agency_key)
    if agency_filter:
        normalized_agencies = {_normalize_agency_key(value) for value in agency_filter}
        normalized_agencies.discard(None)
        history_frame = history_frame[history_frame["agency_priority"].isin(normalized_agencies)].copy()
    history_frame["browser_render_priority"] = history_frame.apply(
        lambda row: int(_url_prefers_browser_render(str(row.get("rating_update_url") or ""), str(row.get("agency_priority") or ""))),
        axis=1,
    )
    history_frame = history_frame.sort_values(["browser_render_priority", "agency_priority", "rating_date"], ascending=[False, True, False])
    target_keys = {
        (str(row.get("company_id") or ""), str(row.get("rating_update_url") or "").strip())
        for row in history_frame.to_dict(orient="records")
        if str(row.get("rating_update_url") or "").strip()
    }

    documents: list[dict[str, Any]] = []
    features: list[dict[str, Any]] = []
    rating_events: list[dict[str, Any]] = []
    parser_messages: list[dict[str, Any]] = []
    refreshed_keys: set[tuple[str, str]] = set()
    processed_message_keys: set[tuple[str, str]] = set()

    with httpx.Client(headers={"User-Agent": "Mozilla/5.0"}, timeout=60.0, follow_redirects=True) as client:
        with _BrowserTextRenderer() as browser_renderer:
            for row in history_frame.to_dict(orient="records"):
                url = str(row.get("rating_update_url") or "").strip()
                if not url:
                    continue
                company_id = str(row.get("company_id") or "")
                row_key = (company_id, url)
                cache_key = f"{row.get('company_id')}__{_stable_hash(url)}"
                parsed_json_path = parsed_json_dir / f"{cache_key}.json"

                if parsed_json_path.exists() and not force:
                    payload = json.loads(parsed_json_path.read_text(encoding="utf-8"))
                else:
                    try:
                        payload = _parse_remote_rationale_document(
                            client=client,
                            url=url,
                            company_name=str(row.get("company_name") or ""),
                            agency_hint=_normalize_agency_key(row.get("rating_agency")),
                            cache_key=cache_key,
                            raw_docs_dir=raw_docs_dir,
                            raw_text_dir=raw_text_dir,
                            browser_renderer=browser_renderer,
                        )
                        parsed_json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
                    except Exception as exc:  # noqa: BLE001
                        parser_messages.append(
                            {
                                "company_id": company_id,
                                "company_name": row.get("company_name"),
                                "rating_update_url": url,
                                "severity": "error",
                                "message": str(exc),
                                "field_name": "document_parse",
                                "parser_name": None,
                            }
                        )
                        processed_message_keys.add(row_key)
                        continue
                    time.sleep(request_delay_seconds)
                refreshed_keys.add(row_key)
                processed_message_keys.add(row_key)

                document_row = payload["document"]
                document_row["company_id"] = company_id
                document_row["rating_update_url"] = url
                documents.append(document_row)

                feature_row = payload["features"]
                feature_row["company_id"] = company_id
                feature_row["rating_update_url"] = url
                features.append(feature_row)

                for event in payload["rating_events"]:
                    event["company_id"] = company_id
                    event["rating_update_url"] = url
                    norm = normalize_rating_label(str(event.get("agency_name") or ""), str(event.get("long_term_rating") or event.get("current_rating") or ""))
                    event["normalized_long_term_label"] = norm.normalized_label
                    event["normalized_long_term_rank"] = norm.rating_rank_numeric
                    event["normalized_scale_type"] = norm.scale_type
                    event["is_withdrawn_normalized"] = norm.is_withdrawn
                    event["is_issuer_not_cooperating_normalized"] = norm.is_issuer_not_cooperating
                    rating_events.append(event)

                for message in payload.get("warnings", []) + payload.get("errors", []):
                    parser_messages.append(
                        {
                            "company_id": company_id,
                            "company_name": row.get("company_name"),
                            "rating_update_url": url,
                            **message,
                        }
                    )

    documents_path = output_dir / "rationale_documents.csv"
    features_path = output_dir / "rationale_features.csv"
    events_path = output_dir / "rating_events.csv"
    messages_path = output_dir / "parser_messages.csv"
    summary_path = output_dir / "agency_rationale_summary.csv"
    phrase_path = output_dir / "agency_rationale_phrases.csv"
    report_path = output_dir / "agency_rationale_research.md"

    documents_frame = pd.DataFrame(documents)
    feature_frame = pd.DataFrame(features)
    event_frame = pd.DataFrame(rating_events)
    parser_messages_frame = pd.DataFrame(parser_messages)

    if merge_with_existing and target_keys:
        documents_frame = _merge_target_rows(
            existing_path=documents_path,
            new_frame=documents_frame,
            replace_keys=refreshed_keys,
            key_columns=("company_id", "rating_update_url"),
        )
        feature_frame = _merge_target_rows(
            existing_path=features_path,
            new_frame=feature_frame,
            replace_keys=refreshed_keys,
            key_columns=("company_id", "rating_update_url"),
        )
        event_frame = _merge_target_rows(
            existing_path=events_path,
            new_frame=event_frame,
            replace_keys=refreshed_keys,
            key_columns=("company_id", "rating_update_url"),
        )
        parser_messages_frame = _merge_target_rows(
            existing_path=messages_path,
            new_frame=parser_messages_frame,
            replace_keys=processed_message_keys,
            key_columns=("company_id", "rating_update_url"),
        )

    documents_frame.to_csv(documents_path, index=False)
    feature_frame.to_csv(features_path, index=False)
    event_frame.to_csv(events_path, index=False)
    parser_messages_frame.to_csv(messages_path, index=False)

    summary_frame, phrase_frame = _build_rationale_summary_frames(feature_frame)
    summary_frame.to_csv(summary_path, index=False)
    phrase_frame.to_csv(phrase_path, index=False)
    report_path.write_text(_render_rationale_research_report(summary_frame, phrase_frame), encoding="utf-8")

    return {
        "rationale_documents": documents_path,
        "rationale_features": features_path,
        "rating_events": events_path,
        "parser_messages": messages_path,
        "agency_rationale_summary": summary_path,
        "agency_rationale_phrases": phrase_path,
        "agency_rationale_research": report_path,
    }


def build_rating_training_dataset(
    *,
    financial_features_path: Path,
    rating_events_path: Path,
    rationale_features_path: Path | None = None,
    context_features_path: Path | None = None,
    output_dir: Path,
    min_days_before_rating: int = 90,
) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    features_frame = pd.read_csv(financial_features_path)
    events_frame = pd.read_csv(rating_events_path)
    rationale_frame = pd.read_csv(rationale_features_path) if rationale_features_path and rationale_features_path.exists() else pd.DataFrame()
    context_frame = (
        normalize_context_frame(pd.read_csv(context_features_path))
        if context_features_path and context_features_path.exists()
        else pd.DataFrame()
    )

    training_path = output_dir / "agency_training_dataset.csv"
    exclusions_path = output_dir / "agency_training_exclusions.csv"
    summary_path = output_dir / "agency_training_summary.csv"

    if features_frame.empty or events_frame.empty:
        pd.DataFrame().to_csv(training_path, index=False)
        pd.DataFrame().to_csv(exclusions_path, index=False)
        pd.DataFrame().to_csv(summary_path, index=False)
        return {
            "agency_training_dataset": training_path,
            "agency_training_exclusions": exclusions_path,
            "agency_training_summary": summary_path,
        }

    features_frame["period_date"] = pd.to_datetime(features_frame["period_date"], errors="coerce")
    events_frame["rating_date"] = pd.to_datetime(events_frame["rating_date"], errors="coerce")
    events_frame["agency_name"] = events_frame["agency_name"].map(_normalize_agency_key)
    events_frame["eligibility_status"] = events_frame.apply(_event_eligibility_status, axis=1)
    rationale_lookup = _prepare_rationale_lookup(rationale_frame)

    merged_rows, exclusion_rows = _assemble_training_rows(
        features_frame=features_frame,
        events_frame=events_frame,
        rationale_lookup=rationale_lookup,
        context_frame=context_frame,
        min_days_before_rating=min_days_before_rating,
    )

    training_frame = pd.DataFrame(merged_rows)
    training_frame.to_csv(training_path, index=False)
    pd.DataFrame(exclusion_rows).to_csv(exclusions_path, index=False)
    _build_training_summary(training_frame, exclusion_rows).to_csv(summary_path, index=False)
    return {
        "agency_training_dataset": training_path,
        "agency_training_exclusions": exclusions_path,
        "agency_training_summary": summary_path,
    }


def train_agency_specific_models(
    *,
    training_dataset_path: Path,
    output_dir: Path,
) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    model_dir = output_dir / "models"
    model_dir.mkdir(parents=True, exist_ok=True)

    training_frame = pd.read_csv(training_dataset_path)
    metrics_rows: list[dict[str, Any]] = []
    model_index_rows: list[dict[str, Any]] = []

    if training_frame.empty:
        metrics_path = output_dir / "agency_model_metrics.csv"
        index_path = output_dir / "agency_model_index.csv"
        pd.DataFrame().to_csv(metrics_path, index=False)
        pd.DataFrame().to_csv(index_path, index=False)
        return {"agency_model_metrics": metrics_path, "agency_model_index": index_path, "models_dir": model_dir}

    confusion_dir = output_dir / "confusion_matrices"
    confusion_dir.mkdir(parents=True, exist_ok=True)

    for agency_name in TARGET_AGENCIES:
        group = training_frame[training_frame["agency_name"] == agency_name].copy()
        dataset = group.dropna(subset=["normalized_long_term_label"]).copy()
        model_path = model_dir / f"{agency_name}_rating_simulator.pkl"
        confusion_path = confusion_dir / f"{agency_name}_confusion_matrix.csv"

        if dataset.empty:
            metrics_rows.append(
                {
                    "agency_name": agency_name,
                    "status": "no_training_data",
                    "training_rows": 0,
                    "distinct_ratings": 0,
                    "evaluation_mode": "not_available",
                    "evaluation_rows": 0,
                    "exact_match_accuracy": np.nan,
                    "within_one_notch_accuracy": np.nan,
                    "confusion_matrix_path": str(confusion_path),
                    "model_path": "",
                }
            )
            pd.DataFrame().to_csv(confusion_path, index=False)
            continue

        dataset = _ensure_model_feature_columns(dataset)
        active_numeric_features = _select_active_numeric_features(dataset)
        active_categorical_features = _select_active_categorical_features(dataset)
        selected_numeric_features = [
            *active_numeric_features,
            *RATIONALE_BINARY_FEATURES,
            *RATIONALE_COUNT_FEATURES,
            *DERIVED_MODEL_FEATURES,
        ]
        X = dataset[[*selected_numeric_features, *active_categorical_features]].copy()
        y = dataset["normalized_long_term_label"].astype(str)
        y_rank = pd.to_numeric(dataset["normalized_long_term_rank"], errors="coerce")
        class_counts = y.value_counts()
        evaluation_mode = "in_sample"
        label_order = [label for label in LONG_TERM_ORDER if label in set(y.astype(str))]

        if y.nunique() == 1:
            evaluation_pipeline = _build_classifier_pipeline(
                use_dummy=True,
                numeric_features=active_numeric_features,
                categorical_features=active_categorical_features,
            )
            evaluation_pipeline.fit(X, y)
            evaluation_regressor = None
            blend_weights = {"classifier": 1.0, "rank_regressor": 0.0}
            eval_actual = y.to_numpy()
            eval_pred, _ = _predict_rating_outputs(
                classifier_pipeline=evaluation_pipeline,
                rank_regressor=evaluation_regressor,
                X=X,
                label_order=label_order,
                blend_weights=blend_weights,
            )
        else:
            can_holdout = len(dataset) >= 10 and int(class_counts.min()) >= 2
            if can_holdout:
                evaluation_mode = "holdout"
                X_train, X_test, y_train, y_test, y_rank_train, _y_rank_test = train_test_split(
                    X,
                    y,
                    y_rank,
                    test_size=0.25,
                    random_state=42,
                    stratify=y,
                )
                evaluation_pipeline = _build_classifier_pipeline(
                    use_dummy=False,
                    numeric_features=active_numeric_features,
                    categorical_features=active_categorical_features,
                )
                evaluation_pipeline.fit(X_train, y_train)
                evaluation_regressor = _build_rank_regressor_pipeline(
                    numeric_features=active_numeric_features,
                    categorical_features=active_categorical_features,
                )
                evaluation_regressor.fit(X_train, y_rank_train)
                blend_weights = {"classifier": 0.65, "rank_regressor": 0.35}
                eval_actual = y_test.to_numpy()
                eval_pred, _ = _predict_rating_outputs(
                    classifier_pipeline=evaluation_pipeline,
                    rank_regressor=evaluation_regressor,
                    X=X_test,
                    label_order=label_order,
                    blend_weights=blend_weights,
                )
            else:
                evaluation_pipeline = _build_classifier_pipeline(
                    use_dummy=False,
                    numeric_features=active_numeric_features,
                    categorical_features=active_categorical_features,
                )
                evaluation_pipeline.fit(X, y)
                evaluation_regressor = _build_rank_regressor_pipeline(
                    numeric_features=active_numeric_features,
                    categorical_features=active_categorical_features,
                )
                evaluation_regressor.fit(X, y_rank)
                blend_weights = {"classifier": 0.65, "rank_regressor": 0.35}
                eval_actual = y.to_numpy()
                eval_pred, _ = _predict_rating_outputs(
                    classifier_pipeline=evaluation_pipeline,
                    rank_regressor=evaluation_regressor,
                    X=X,
                    label_order=label_order,
                    blend_weights=blend_weights,
                )

        exact_accuracy = float(accuracy_score(eval_actual, eval_pred)) if len(eval_actual) else np.nan
        within_one_accuracy = _within_one_notch_accuracy(eval_actual, eval_pred)
        confusion_frame = _build_confusion_matrix_frame(eval_actual, eval_pred)
        confusion_frame.to_csv(confusion_path, index=False)

        final_pipeline = _build_classifier_pipeline(
            use_dummy=(y.nunique() == 1),
            numeric_features=active_numeric_features,
            categorical_features=active_categorical_features,
        )
        final_pipeline.fit(X, y)
        final_regressor = None
        if y.nunique() > 1 and y_rank.notna().sum() >= 8:
            final_regressor = _build_rank_regressor_pipeline(
                numeric_features=active_numeric_features,
                categorical_features=active_categorical_features,
            )
            final_regressor.fit(X, y_rank)
        feature_stats = _summarize_training_feature_stats(dataset)
        artifact = {
            "agency_name": agency_name,
            "pipeline": final_pipeline,
            "classification_pipeline": final_pipeline,
            "rank_regressor": final_regressor,
            "numeric_features": selected_numeric_features,
            "categorical_features": active_categorical_features,
            "label_order": label_order,
            "probability_blend_weights": blend_weights,
            "training_rows": len(dataset),
            "distinct_ratings": int(y.nunique()),
            "evaluation": {
                "status": "trained",
                "evaluation_mode": evaluation_mode,
                "evaluation_rows": int(len(eval_actual)),
                "exact_match_accuracy": round(exact_accuracy, 4) if not np.isnan(exact_accuracy) else np.nan,
                "within_one_notch_accuracy": round(within_one_accuracy, 4) if not np.isnan(within_one_accuracy) else np.nan,
                "confusion_matrix_path": str(confusion_path),
            },
            "feature_stats": feature_stats,
        }
        with model_path.open("wb") as handle:
            pickle.dump(artifact, handle)

        metrics_rows.append(
            {
                "agency_name": agency_name,
                "status": "trained",
                "training_rows": len(dataset),
                "distinct_ratings": int(y.nunique()),
                "evaluation_mode": evaluation_mode,
                "evaluation_rows": int(len(eval_actual)),
                "exact_match_accuracy": round(exact_accuracy, 4) if not np.isnan(exact_accuracy) else np.nan,
                "within_one_notch_accuracy": round(within_one_accuracy, 4) if not np.isnan(within_one_accuracy) else np.nan,
                "confusion_matrix_path": str(confusion_path),
                "model_path": str(model_path),
            }
        )
        model_index_rows.append(
            {
                "agency_name": agency_name,
                "model_path": str(model_path),
                "training_rows": len(dataset),
                "distinct_ratings": int(y.nunique()),
            }
        )

    metrics_path = output_dir / "agency_model_metrics.csv"
    index_path = output_dir / "agency_model_index.csv"
    pd.DataFrame(metrics_rows).to_csv(metrics_path, index=False)
    pd.DataFrame(model_index_rows).to_csv(index_path, index=False)
    return {"agency_model_metrics": metrics_path, "agency_model_index": index_path, "models_dir": model_dir}


def simulate_unrated_companies(
    *,
    latest_financial_features_path: Path,
    rating_events_path: Path,
    model_dir: Path,
    output_dir: Path,
    training_dataset_path: Path | None = None,
    training_exclusions_path: Path | None = None,
    financial_history_path: Path | None = None,
    context_features_path: Path | None = None,
) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    financial_history_frame = pd.read_csv(financial_history_path) if financial_history_path and financial_history_path.exists() else pd.DataFrame()
    features_frame = pd.read_csv(latest_financial_features_path)
    events_frame = pd.read_csv(rating_events_path) if rating_events_path.exists() else pd.DataFrame()
    context_frame = (
        normalize_context_frame(pd.read_csv(context_features_path))
        if context_features_path and context_features_path.exists()
        else pd.DataFrame()
    )
    training_frame = pd.read_csv(training_dataset_path) if training_dataset_path and training_dataset_path.exists() else pd.DataFrame()
    exclusions_frame = (
        pd.read_csv(training_exclusions_path)
        if training_exclusions_path and training_exclusions_path.exists()
        else pd.DataFrame()
    )

    rated_company_ids = set()
    if not events_frame.empty:
        events_frame["agency_name"] = events_frame["agency_name"].map(_normalize_agency_key)
        long_term_events = events_frame[
            (events_frame["normalized_scale_type"] == "long_term")
            & events_frame["normalized_long_term_rank"].notna()
            & ~events_frame["is_withdrawn"].fillna(False)
            & ~events_frame["is_issuer_not_cooperating"].fillna(False)
            & ~events_frame["is_withdrawn_normalized"].fillna(False)
            & ~events_frame["is_issuer_not_cooperating_normalized"].fillna(False)
        ]
        rated_company_ids = set(long_term_events["company_id"].dropna().astype(str))

    simulation_rows: list[dict[str, Any]] = []
    validation_rows: list[dict[str, Any]] = []
    excluded_rows: list[dict[str, Any]] = []
    rating_history_lookup = _prepare_company_rating_history(events_frame)
    benchmark_lookup = _prepare_industry_benchmark_lookup(financial_history_frame) if not financial_history_frame.empty else {}
    trajectory_lookup = _prepare_scale_trajectory_lookup(financial_history_frame) if not financial_history_frame.empty else {}
    context_lookup = _prepare_context_lookup(context_frame)

    for model_path in sorted(model_dir.glob("*_rating_simulator.pkl")):
        artifact = load_model_artifact(model_path)
        agency_name = artifact["agency_name"]

        if not training_frame.empty:
            validation_frame = training_frame[training_frame["agency_name"] == agency_name].copy()
            if not validation_frame.empty:
                validation_frame = _ensure_model_feature_columns(validation_frame)
                validation_rows.extend(
                    _score_prediction_frame(
                        frame=validation_frame,
                        artifact=artifact,
                        population_type="validation",
                    )
                )

        if financial_history_frame.empty:
            population_frame = features_frame.copy()
        else:
            population_frame = _build_latest_company_feature_frame(
                features_frame=financial_history_frame,
                agency_name=agency_name,
                benchmark_lookup=benchmark_lookup,
                trajectory_lookup=trajectory_lookup,
                rating_history_lookup=rating_history_lookup,
                context_lookup=context_lookup,
            )
        population_frame = _ensure_model_feature_columns(population_frame)
        unrated_frame = population_frame[~population_frame["company_id"].astype(str).isin(rated_company_ids)].copy()
        if unrated_frame.empty:
            continue

        simulation_rows.extend(
            _score_prediction_frame(
                frame=unrated_frame.copy(),
                artifact=artifact,
                population_type="simulation",
            )
        )

    if not exclusions_frame.empty:
        for row in exclusions_frame.to_dict(orient="records"):
            agency_name = _normalize_agency_key(row.get("agency_name"))
            if agency_name not in TARGET_AGENCIES:
                continue
            excluded_rows.append(
                {
                    "company_id": row.get("company_id"),
                    "company_name": row.get("company_name"),
                    "agency": agency_name,
                    "predicted_rating": None,
                    "rating_range": None,
                    "confidence": 0.0,
                    "actual_rating": _string(row.get("long_term_rating")) or _string(row.get("current_rating")),
                    "deviation": None,
                    "key_features": json.dumps([str(row.get("eligibility_status") or "excluded")]),
                    "population_type": "validation_excluded",
                    "prediction_status": str(row.get("eligibility_status") or "excluded"),
                    "financial_period": None,
                    "probability_distribution_json": "{}",
                    "top_probability": 0.0,
                    "data_completeness": 0.0,
                    "feature_coverage": 0.0,
                    "confidence_label": "low",
                }
            )

    combined_frame = pd.DataFrame([*validation_rows, *simulation_rows, *excluded_rows])
    if not combined_frame.empty:
        combined_frame = combined_frame.sort_values(["population_type", "agency", "company_name"], na_position="last")

    results_path = output_dir / "simulation_results.csv"
    validation_path = output_dir / "rated_company_validation_predictions.csv"
    simulations_path = output_dir / "unrated_company_simulations.csv"

    combined_frame.to_csv(results_path, index=False)
    validation_frame = combined_frame[combined_frame["population_type"] == "validation"].copy() if not combined_frame.empty else pd.DataFrame()
    validation_frame.to_csv(validation_path, index=False)

    legacy_unrated = combined_frame[combined_frame["population_type"] == "simulation"].copy() if not combined_frame.empty else pd.DataFrame()
    if not legacy_unrated.empty:
        legacy_unrated["simulated_rating"] = legacy_unrated["predicted_rating"]
        legacy_unrated["confidence_score"] = legacy_unrated["confidence"]
    legacy_unrated.to_csv(simulations_path, index=False)

    return {
        "simulation_results": results_path,
        "rated_company_validation_predictions": validation_path,
        "unrated_company_simulations": simulations_path,
    }


def _load_industry_input_frame(input_csv_path: Path) -> pd.DataFrame:
    companies = load_input_companies(input_csv_path)
    frame = pd.read_csv(input_csv_path)
    frame = frame.iloc[: len(companies)].copy()
    frame["company_id"] = [company.company_id for company in companies]
    frame["nse_code"] = [company.nse_code for company in companies]
    frame["bse_code"] = [company.bse_code for company in companies]
    frame = frame.rename(
        columns={
            "Name": "company_name",
            "Industry Group": "industry_group",
            "Industry": "sub_industry",
        }
    )
    return frame


def _parse_remote_rationale_document(
    *,
    client: httpx.Client,
    url: str,
    company_name: str,
    agency_hint: str | None,
    cache_key: str,
    raw_docs_dir: Path,
    raw_text_dir: Path,
    browser_renderer: _BrowserTextRenderer | None = None,
) -> dict[str, Any]:
    content_url = url
    response = client.get(url)
    response.raise_for_status()
    content_type = response.headers.get("content-type", "").lower()

    if _looks_like_pdf(url, content_type):
        suffix = Path(urlsplit(url).path).suffix or ".pdf"
        doc_path = raw_docs_dir / f"{cache_key}{suffix}"
        doc_path.write_bytes(response.content)
        extracted = extract_pdf_text(doc_path)
        text = extracted.text
        source_path = doc_path
        extractor_used = extracted.extractor_used
        text_hash = extracted.text_hash
        agency_name = agency_hint or detect_agency_name(doc_path.name, text)
    else:
        html_text = response.text
        browser_preferred = _url_prefers_browser_render(str(response.url), agency_hint)
        if not browser_preferred:
            pdf_url = extract_pdf_url_from_html(html_text, base_url=str(response.url))
            if pdf_url and pdf_url != url:
                return _parse_remote_rationale_document(
                    client=client,
                    url=pdf_url,
                    company_name=company_name,
                    agency_hint=agency_hint,
                    cache_key=cache_key,
                    raw_docs_dir=raw_docs_dir,
                    raw_text_dir=raw_text_dir,
                )
        html_path = raw_docs_dir / f"{cache_key}.html"
        html_path.write_text(html_text, encoding="utf-8")
        text = normalize_multiline_text(BeautifulSoup(html_text, "lxml").get_text("\n", strip=True))
        agency_name = agency_hint or _detect_agency_from_url(url) or detect_agency_name(html_path.name, text)
        if _should_render_html_in_browser(url=str(response.url), agency_name=agency_name, extracted_text=text):
            rendered_text = _render_html_text_with_browser(str(response.url), browser_renderer)
            if rendered_text:
                text = rendered_text
                extractor_used = "browser_rendered_html"
            else:
                extractor_used = "html_text"
        else:
            extractor_used = "html_text"
        source_path = html_path
        text_hash = compute_text_hash(text)
        content_url = str(response.url)

    if agency_name not in SUPPORTED_AGENCIES:
        raise ValueError(f"Unsupported or undetected agency {agency_name!r} for {url}")

    raw_text_path = raw_text_dir / f"{cache_key}.txt"
    raw_text_path.write_text(text, encoding="utf-8")
    parser = get_parser(agency_name)
    bundle = parser.parse(
        pdf_path=source_path,
        source_file=source_path.name,
        text=text,
        text_hash=text_hash,
        extractor_used=extractor_used,
    )
    payload = bundle.model_dump(mode="json")
    payload["rationale_document"]["source_url"] = content_url
    payload["rationale_document"]["raw_text_path"] = str(raw_text_path)
    return {
        "document": payload["rationale_document"],
        "features": payload["rationale_features"],
        "rating_events": payload["rating_events"],
        "warnings": payload["warnings"],
        "errors": payload["errors"],
    }


def _build_rationale_summary_frames(feature_frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    if feature_frame.empty:
        return pd.DataFrame(), pd.DataFrame()

    flag_columns = [column for column in feature_frame.columns if column.startswith("has_")]
    summary_rows: list[dict[str, Any]] = []
    phrase_rows: list[dict[str, Any]] = []

    for agency_name, group in feature_frame.groupby("agency_name"):
        total = len(group)
        for column in flag_columns:
            count = int(group[column].fillna(False).astype(bool).sum())
            if count:
                summary_rows.append(
                    {
                        "agency_name": agency_name,
                        "signal_type": column,
                        "mentions": count,
                        "mention_rate": round(count / total, 4),
                    }
                )

        strength_counter = Counter()
        weakness_counter = Counter()
        for _, row in group.iterrows():
            for item in _ensure_list(row.get("strengths_json")):
                strength_counter[item] += 1
            for item in _ensure_list(row.get("weaknesses_json")):
                weakness_counter[item] += 1

        for phrase, count in strength_counter.most_common(10):
            phrase_rows.append({"agency_name": agency_name, "phrase_type": "strength", "phrase": phrase, "mentions": count})
        for phrase, count in weakness_counter.most_common(10):
            phrase_rows.append({"agency_name": agency_name, "phrase_type": "weakness", "phrase": phrase, "mentions": count})

    return pd.DataFrame(summary_rows), pd.DataFrame(phrase_rows)


def _render_rationale_research_report(summary_frame: pd.DataFrame, phrase_frame: pd.DataFrame) -> str:
    if summary_frame.empty and phrase_frame.empty:
        return "# Agency rationale research\n\nNo rationale features were available."

    lines = ["# Agency rationale research", ""]
    agencies = sorted(set(summary_frame.get("agency_name", [])) | set(phrase_frame.get("agency_name", [])))
    for agency_name in agencies:
        lines.append(f"## {agency_name}")
        agency_signals = summary_frame[summary_frame["agency_name"] == agency_name].sort_values("mentions", ascending=False).head(10)
        if not agency_signals.empty:
            lines.append("")
            lines.append("Top repeated qualitative signals:")
            for _, row in agency_signals.iterrows():
                lines.append(f"- `{row['signal_type']}` mentioned {int(row['mentions'])} times ({row['mention_rate']:.0%}).")

        agency_phrases = phrase_frame[phrase_frame["agency_name"] == agency_name]
        if not agency_phrases.empty:
            lines.append("")
            lines.append("Repeated strength / weakness phrases:")
            for _, row in agency_phrases.head(10).iterrows():
                lines.append(f"- `{row['phrase_type']}`: {row['phrase']} ({int(row['mentions'])})")
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def _should_render_html_in_browser(*, url: str, agency_name: str | None, extracted_text: str) -> bool:
    host = urlsplit(url).netloc.lower()
    text = extracted_text or ""
    if agency_name == "india_ratings":
        return "Loading..." in text or len(text.split()) < 80
    if "bcrisp.in" in host:
        return True
    return False


def _url_prefers_browser_render(url: str, agency_name: str | None) -> bool:
    host = urlsplit(url).netloc.lower()
    return agency_name == "india_ratings" or "bcrisp.in" in host


def _render_html_text_with_browser(url: str, browser_renderer: _BrowserTextRenderer | None) -> str | None:
    if browser_renderer is None:
        return None
    return browser_renderer.render_text(url)


def _merge_target_rows(
    *,
    existing_path: Path,
    new_frame: pd.DataFrame,
    replace_keys: set[tuple[str, str]],
    key_columns: tuple[str, str],
) -> pd.DataFrame:
    if not existing_path.exists():
        return new_frame

    existing_frame = pd.read_csv(existing_path)
    if existing_frame.empty:
        return new_frame

    first_key, second_key = key_columns
    if first_key not in existing_frame.columns or second_key not in existing_frame.columns:
        return pd.concat([existing_frame, new_frame], ignore_index=True, sort=False)

    if replace_keys:
        existing_keys = list(
            zip(
                existing_frame[first_key].fillna("").astype(str),
                existing_frame[second_key].fillna("").astype(str),
                strict=False,
            )
        )
        keep_mask = [key not in replace_keys for key in existing_keys]
        existing_frame = existing_frame.loc[keep_mask].copy()

    if new_frame.empty:
        return existing_frame

    return pd.concat([existing_frame, new_frame], ignore_index=True, sort=False)


def _build_classifier_pipeline(
    *,
    use_dummy: bool,
    numeric_features: list[str] | None = None,
    categorical_features: list[str] | None = None,
) -> Pipeline:
    numeric_features = numeric_features or NUMERIC_MODEL_FEATURES
    categorical_features = categorical_features or CATEGORICAL_MODEL_FEATURES
    preprocessor = ColumnTransformer(
        transformers=[
            ("num", Pipeline([("imputer", SimpleImputer(strategy="median"))]), numeric_features),
            (
                "indicator",
                Pipeline([("imputer", SimpleImputer(strategy="constant", fill_value=0))]),
                [*RATIONALE_BINARY_FEATURES, *RATIONALE_COUNT_FEATURES, *DERIVED_MODEL_FEATURES],
            ),
            (
                "cat",
                Pipeline(
                    [
                        ("imputer", SimpleImputer(strategy="constant", fill_value="Unknown")),
                        ("onehot", OneHotEncoder(handle_unknown="ignore")),
                    ]
                ),
                categorical_features,
            ),
        ]
    )
    estimator = (
        DummyClassifier(strategy="most_frequent")
        if use_dummy
        else ExtraTreesClassifier(
            n_estimators=600,
            random_state=42,
            min_samples_leaf=1,
            class_weight="balanced",
        )
    )
    return Pipeline([("preprocess", preprocessor), ("model", estimator)])


def _build_rank_regressor_pipeline(
    *,
    numeric_features: list[str] | None = None,
    categorical_features: list[str] | None = None,
) -> Pipeline:
    numeric_features = numeric_features or NUMERIC_MODEL_FEATURES
    categorical_features = categorical_features or CATEGORICAL_MODEL_FEATURES
    preprocessor = ColumnTransformer(
        transformers=[
            ("num", Pipeline([("imputer", SimpleImputer(strategy="median"))]), numeric_features),
            (
                "indicator",
                Pipeline([("imputer", SimpleImputer(strategy="constant", fill_value=0))]),
                [*RATIONALE_BINARY_FEATURES, *RATIONALE_COUNT_FEATURES, *DERIVED_MODEL_FEATURES],
            ),
            (
                "cat",
                Pipeline(
                    [
                        ("imputer", SimpleImputer(strategy="constant", fill_value="Unknown")),
                        ("onehot", OneHotEncoder(handle_unknown="ignore")),
                    ]
                ),
                categorical_features,
            ),
        ]
    )
    estimator = ExtraTreesRegressor(
        n_estimators=600,
        random_state=42,
        min_samples_leaf=2,
    )
    return Pipeline([("preprocess", preprocessor), ("model", estimator)])


def _event_eligibility_status(row: pd.Series) -> str:
    if row.get("normalized_scale_type") != "long_term":
        return "non_long_term_rating"
    if pd.isna(row.get("normalized_long_term_rank")) or not _string(row.get("normalized_long_term_label")):
        return "missing_normalized_long_term_rating"
    if _to_bool(row.get("is_withdrawn")) or _to_bool(row.get("is_withdrawn_normalized")):
        return "withdrawn_rating"
    if _to_bool(row.get("is_issuer_not_cooperating")) or _to_bool(row.get("is_issuer_not_cooperating_normalized")):
        return "issuer_not_cooperating"
    if pd.isna(row.get("rating_date")):
        return "missing_rating_date"
    return "eligible"


def _prepare_rationale_lookup(rationale_frame: pd.DataFrame) -> dict[str, dict[str, Any]]:
    if rationale_frame.empty:
        return {}
    working = rationale_frame.copy()
    working["agency_name"] = working["agency_name"].map(_normalize_agency_key)

    for column in RATIONALE_BINARY_FEATURES:
        if column not in working.columns:
            working[column] = False
        working[column] = working[column].apply(_to_bool)

    for column in ("strengths_json", "weaknesses_json", "sensitivities_up_json", "sensitivities_down_json", "qualitative_summary"):
        if column not in working.columns:
            working[column] = ""

    working["strengths_count"] = working["strengths_json"].apply(lambda value: len(_ensure_list(value)))
    working["weaknesses_count"] = working["weaknesses_json"].apply(lambda value: len(_ensure_list(value)))
    working["sensitivities_up_count"] = working["sensitivities_up_json"].apply(lambda value: len(_ensure_list(value)))
    working["sensitivities_down_count"] = working["sensitivities_down_json"].apply(lambda value: len(_ensure_list(value)))
    working["qualitative_summary_length"] = working["qualitative_summary"].fillna("").astype(str).str.len()

    lookup: dict[str, dict[str, Any]] = {}
    for row in working.to_dict(orient="records"):
        lookup[str(row.get("rationale_doc_id") or "")] = row
    return lookup


def _assemble_training_rows(
    *,
    features_frame: pd.DataFrame,
    events_frame: pd.DataFrame,
    rationale_lookup: dict[str, dict[str, Any]],
    context_frame: pd.DataFrame,
    min_days_before_rating: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    aligned_event_cache: list[dict[str, Any]] = []
    exclusion_rows: list[dict[str, Any]] = []
    benchmark_lookup = _prepare_industry_benchmark_lookup(features_frame)
    trajectory_lookup = _prepare_scale_trajectory_lookup(features_frame)
    context_lookup = _prepare_context_lookup(context_frame)

    for event in events_frame.to_dict(orient="records"):
        if event.get("agency_name") not in TARGET_AGENCIES:
            exclusion_rows.append(_event_exclusion_row(event, "unsupported_agency"))
            continue
        if event.get("eligibility_status") != "eligible":
            exclusion_rows.append(_event_exclusion_row(event, str(event.get("eligibility_status"))))
            continue

        history_window = _select_financial_history_window(
            features_frame=features_frame,
            company_id=event.get("company_id"),
            as_of_date=event.get("rating_date"),
            min_days_before_rating=min_days_before_rating,
        )
        if history_window.empty:
            exclusion_rows.append(_event_exclusion_row(event, f"missing_{min_days_before_rating}d_financial_alignment"))
            continue

        aligned_event_cache.append(
            {
                "event": event,
                "financial_history": history_window,
                "financial_profile": _build_financial_window_features(history_window),
                "rationale": rationale_lookup.get(str(event.get("rationale_doc_id") or ""), {}),
            }
        )

    history_lookup = _prepare_rating_history_lookup(aligned_event_cache)
    merged_rows: list[dict[str, Any]] = []
    for cached in aligned_event_cache:
        event = cached["event"]
        financial_profile = cached["financial_profile"]
        latest_feature = cached["financial_history"].sort_values("period_date").iloc[-1].to_dict()
        benchmark_features = _build_industry_benchmark_features(
            financial_profile=financial_profile,
            latest_feature=latest_feature,
            benchmark_lookup=benchmark_lookup,
        )
        trajectory_features = _build_scale_peer_trajectory_features(
            financial_profile=financial_profile,
            latest_feature=latest_feature,
            trajectory_lookup=trajectory_lookup,
            exclude_company_id=event.get("company_id"),
        )
        prior_rating_features = _build_prior_rating_features(
            event=event,
            financial_profile=financial_profile,
            history_lookup=history_lookup,
        )
        context_features = _lookup_context_features(
            context_lookup=context_lookup,
            company_id=event.get("company_id"),
            as_of_date=event.get("rating_date"),
        )
        merged_rows.append(
            _build_training_row(
                event=event,
                financial_history=cached["financial_history"],
                rationale=cached["rationale"],
                extra_features={**benchmark_features, **trajectory_features, **prior_rating_features, **context_features},
            )
        )

    return merged_rows, exclusion_rows


def _event_exclusion_row(event: dict[str, Any], status: str) -> dict[str, Any]:
    return {
        "company_id": event.get("company_id"),
        "company_name": event.get("company_name"),
        "agency_name": event.get("agency_name"),
        "rating_event_id": event.get("rating_event_id"),
        "rationale_doc_id": event.get("rationale_doc_id"),
        "eligibility_status": status,
        "current_rating": event.get("current_rating"),
        "long_term_rating": event.get("long_term_rating"),
        "rating_date": _iso_date(event.get("rating_date")),
    }


def _select_financial_history_window(
    *,
    features_frame: pd.DataFrame,
    company_id: Any,
    as_of_date: Any,
    min_days_before_rating: int = 0,
    max_periods: int = 4,
) -> pd.DataFrame:
    if as_of_date is None or pd.isna(as_of_date):
        return pd.DataFrame()
    company_features = features_frame[features_frame["company_id"] == company_id].copy()
    if company_features.empty:
        return pd.DataFrame()
    cutoff_date = pd.Timestamp(as_of_date) - pd.Timedelta(days=min_days_before_rating)
    company_features = company_features[company_features["period_date"] <= cutoff_date].copy()
    if company_features.empty:
        return pd.DataFrame()
    company_features = company_features.sort_values("period_date")
    return company_features.tail(max_periods).copy()


def _build_financial_window_features(history_window: pd.DataFrame) -> dict[str, Any]:
    if history_window.empty:
        return {}

    ordered = history_window.sort_values("period_date").copy()
    latest = ordered.iloc[-1]
    window_span_days = 0
    if len(ordered) > 1 and pd.notna(ordered.iloc[0]["period_date"]) and pd.notna(ordered.iloc[-1]["period_date"]):
        window_span_days = int((ordered.iloc[-1]["period_date"] - ordered.iloc[0]["period_date"]).days)

    row: dict[str, Any] = {
        "matched_financial_period": latest.get("period"),
        "period_date": latest.get("period_date"),
        "history_periods_available": int(len(ordered)),
        "financial_window_span_days": window_span_days,
    }

    for feature in EXTENDED_FINANCIAL_FEATURES:
        series = pd.to_numeric(ordered[feature], errors="coerce") if feature in ordered.columns else pd.Series(dtype=float)
        row[feature] = _to_float(latest.get(feature))
        row[f"{feature}_avg3y"] = round(float(series.tail(3).mean()), 4) if series.notna().any() else None
        row[f"{feature}_delta1y"] = _series_delta(series, 1)
        row[f"{feature}_delta2y"] = _series_delta(series, 2)
        row[f"{feature}_std3y"] = _series_std(series)
        row[f"{feature}_slope3y"] = _series_slope(series)

    profitability_delta = _to_float(row.get("ebitda_margin_pct_delta1y"))
    leverage_delta = _to_float(row.get("debt_to_equity_delta1y"))
    coverage_delta = _to_float(row.get("interest_coverage_delta1y"))
    working_capital_delta = _to_float(row.get("working_capital_days_delta1y"))
    revenue_delta = _to_float(row.get("revenue_crore_delta1y"))
    networth_delta = _to_float(row.get("networth_crore_delta1y"))

    row["profitability_trend_positive"] = int((profitability_delta or 0.0) > 0.0)
    row["leverage_trend_improving"] = int(leverage_delta is not None and leverage_delta < 0.0)
    row["coverage_trend_improving"] = int((coverage_delta or 0.0) > 0.0)
    row["working_capital_trend_improving"] = int(working_capital_delta is not None and working_capital_delta < 0.0)
    row["scale_growth_positive"] = int((revenue_delta or 0.0) > 0.0)
    row["networth_growth_positive"] = int((networth_delta or 0.0) > 0.0)
    row["data_completeness"] = _financial_data_completeness(row)
    return row


def _series_delta(series: pd.Series, periods_back: int) -> float | None:
    clean = series.dropna()
    if len(clean) <= periods_back:
        return None
    return round(float(clean.iloc[-1] - clean.iloc[-(periods_back + 1)]), 4)


def _series_std(series: pd.Series) -> float | None:
    clean = series.tail(3).dropna()
    if len(clean) < 2:
        return None
    return round(float(clean.std(ddof=0)), 4)


def _series_slope(series: pd.Series) -> float | None:
    clean = series.tail(3).dropna()
    if len(clean) < 2:
        return None
    x_values = np.arange(len(clean), dtype=float)
    slope, _ = np.polyfit(x_values, clean.astype(float).to_numpy(), 1)
    return round(float(slope), 4)


def _prepare_industry_benchmark_lookup(features_frame: pd.DataFrame) -> dict[tuple[str, str], pd.DataFrame]:
    if features_frame.empty:
        return {}
    working = features_frame.copy()
    lookup: dict[tuple[str, str], pd.DataFrame] = {}
    for (sub_industry, period), group in working.groupby(["sub_industry", "period"], dropna=False):
        lookup[(str(sub_industry or ""), str(period or ""))] = group.copy()
    return lookup


def _build_industry_benchmark_features(
    *,
    financial_profile: dict[str, Any],
    latest_feature: dict[str, Any],
    benchmark_lookup: dict[tuple[str, str], pd.DataFrame],
) -> dict[str, Any]:
    peer_group = benchmark_lookup.get((str(latest_feature.get("sub_industry") or ""), str(latest_feature.get("period") or "")))
    rows: dict[str, Any] = {feature: None for feature in BENCHMARK_NUMERIC_FEATURES}
    if peer_group is None or peer_group.empty:
        return rows

    rows["industry_peer_sample_size"] = int(len(peer_group))
    metric_map = {
        "industry_revenue": "revenue_crore",
        "industry_ebitda_margin": "ebitda_margin_pct",
        "industry_pat_margin": "pat_margin_pct",
        "industry_debt_to_equity": "debt_to_equity",
        "industry_interest_coverage": "interest_coverage",
        "industry_working_capital_days": "working_capital_days",
    }
    for prefix, source_column in metric_map.items():
        company_value = _to_float(financial_profile.get(source_column))
        peer_series = pd.to_numeric(peer_group[source_column], errors="coerce").dropna() if source_column in peer_group.columns else pd.Series(dtype=float)
        if company_value is None or peer_series.empty:
            continue
        rows[f"{prefix}_gap_to_median"] = round(float(company_value - float(peer_series.median())), 4)
        rows[f"{prefix}_percentile"] = round(float((peer_series <= company_value).mean()), 4)
    return rows


def _prepare_scale_trajectory_lookup(features_frame: pd.DataFrame) -> dict[str, pd.DataFrame]:
    if features_frame.empty:
        return {}
    working = features_frame.copy()
    working["period_date"] = pd.to_datetime(working["period_date"], errors="coerce")
    episodes: list[dict[str, Any]] = []

    for company_id, group in working.groupby("company_id", dropna=False):
        ordered = group.sort_values("period_date").reset_index(drop=True)
        if len(ordered) < 3:
            continue
        for index in range(len(ordered) - 2):
            start = ordered.iloc[index]
            future_index = min(index + 3, len(ordered) - 1)
            future = ordered.iloc[future_index]
            start_date = pd.Timestamp(start.get("period_date"))
            future_date = pd.Timestamp(future.get("period_date"))
            if pd.isna(start_date) or pd.isna(future_date) or future_date <= start_date:
                continue
            years_forward = float((future_date - start_date).days) / 365.25
            if years_forward < 1.75:
                continue
            episodes.append(
                {
                    "company_id": str(company_id or ""),
                    "sub_industry": str(start.get("sub_industry") or ""),
                    "start_period_date": start_date,
                    "start_revenue_crore": _to_float(start.get("revenue_crore")),
                    "start_ebitda_margin_pct": _to_float(start.get("ebitda_margin_pct")),
                    "start_debt_to_equity": _to_float(start.get("debt_to_equity")),
                    "start_interest_coverage": _to_float(start.get("interest_coverage")),
                    "forward_revenue_cagr": _safe_cagr(
                        _to_float(start.get("revenue_crore")),
                        _to_float(future.get("revenue_crore")),
                        years_forward,
                    ),
                    "forward_ebitda_margin_change": _difference(
                        future.get("ebitda_margin_pct"),
                        start.get("ebitda_margin_pct"),
                    ),
                    "forward_debt_to_equity_change": _difference(
                        future.get("debt_to_equity"),
                        start.get("debt_to_equity"),
                    ),
                    "forward_interest_coverage_change": _difference(
                        future.get("interest_coverage"),
                        start.get("interest_coverage"),
                    ),
                    "forward_years": round(years_forward, 4),
                }
            )

    if not episodes:
        return {}
    episode_frame = pd.DataFrame(episodes)
    lookup: dict[str, pd.DataFrame] = {}
    for sub_industry, group in episode_frame.groupby("sub_industry", dropna=False):
        lookup[str(sub_industry or "")] = group.copy()
    return lookup


def _build_scale_peer_trajectory_features(
    *,
    financial_profile: dict[str, Any],
    latest_feature: dict[str, Any],
    trajectory_lookup: dict[str, pd.DataFrame],
    exclude_company_id: Any = None,
) -> dict[str, Any]:
    rows: dict[str, Any] = {feature: None for feature in TRAJECTORY_BENCHMARK_NUMERIC_FEATURES}
    rows["scale_peer_sample_size"] = 0

    episodes = trajectory_lookup.get(str(latest_feature.get("sub_industry") or ""))
    target_revenue = _to_float(financial_profile.get("revenue_crore")) or _to_float(latest_feature.get("revenue_crore"))
    if episodes is None or episodes.empty or target_revenue is None or target_revenue <= 0:
        return rows

    cohort = episodes.copy()
    if exclude_company_id is not None:
        cohort = cohort[cohort["company_id"].astype(str) != str(exclude_company_id)]
    as_of_date = pd.Timestamp(latest_feature.get("period_date"))
    if pd.notna(as_of_date):
        cohort = cohort[cohort["start_period_date"] <= as_of_date]
    cohort = cohort[pd.to_numeric(cohort["start_revenue_crore"], errors="coerce").fillna(0) > 0].copy()
    if cohort.empty:
        return rows

    revenue_series = pd.to_numeric(cohort["start_revenue_crore"], errors="coerce")
    cohort["revenue_distance"] = np.abs(np.log(revenue_series / float(target_revenue)))
    band = cohort[revenue_series.between(float(target_revenue) * 0.5, float(target_revenue) * 2.0)].copy()
    if not band.empty:
        cohort = band
    cohort = cohort.nsmallest(min(len(cohort), 25), "revenue_distance").copy()
    if cohort.empty:
        return rows

    rows["scale_peer_sample_size"] = int(len(cohort))
    rows["scale_peer_forward_revenue_cagr"] = _median_numeric(cohort, "forward_revenue_cagr")
    rows["scale_peer_forward_ebitda_margin_change"] = _median_numeric(cohort, "forward_ebitda_margin_change")
    rows["scale_peer_forward_debt_to_equity_change"] = _median_numeric(cohort, "forward_debt_to_equity_change")
    rows["scale_peer_forward_interest_coverage_change"] = _median_numeric(cohort, "forward_interest_coverage_change")
    rows["scale_peer_revenue_position_pct"] = round(float((revenue_series.loc[cohort.index] <= float(target_revenue)).mean()), 4)

    current_margin = _to_float(financial_profile.get("ebitda_margin_pct"))
    current_leverage = _to_float(financial_profile.get("debt_to_equity"))
    current_coverage = _to_float(financial_profile.get("interest_coverage"))
    rows["scale_peer_ebitda_margin_gap_to_median"] = _difference(current_margin, _median_numeric(cohort, "start_ebitda_margin_pct"))
    rows["scale_peer_debt_to_equity_gap_to_median"] = _difference(current_leverage, _median_numeric(cohort, "start_debt_to_equity"))
    rows["scale_peer_interest_coverage_gap_to_median"] = _difference(current_coverage, _median_numeric(cohort, "start_interest_coverage"))
    return rows


def _prepare_rating_history_lookup(aligned_event_cache: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    lookup: dict[str, list[dict[str, Any]]] = {}
    for item in aligned_event_cache:
        company_id = str(item["event"].get("company_id") or "")
        lookup.setdefault(company_id, []).append(item)
    for company_id in lookup:
        lookup[company_id] = sorted(
            lookup[company_id],
            key=lambda item: pd.Timestamp(item["event"].get("rating_date")),
        )
    return lookup


def _build_prior_rating_features(
    *,
    event: dict[str, Any],
    financial_profile: dict[str, Any],
    history_lookup: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    rows: dict[str, Any] = {
        "prior_agency_rating_available": 0,
        "prior_any_rating_available": 0,
        **{feature: None for feature in PRIOR_RATING_NUMERIC_FEATURES},
    }
    company_history = history_lookup.get(str(event.get("company_id") or ""), [])
    current_date = pd.Timestamp(event.get("rating_date"))
    prior_any = None
    prior_agency = None
    for item in company_history:
        item_event = item["event"]
        item_date = pd.Timestamp(item_event.get("rating_date"))
        if pd.isna(item_date) or item_date >= current_date:
            break
        prior_any = item
        if item_event.get("agency_name") == event.get("agency_name"):
            prior_agency = item

    if prior_agency is not None:
        rows["prior_agency_rating_available"] = 1
        rows["prior_agency_rating_rank"] = _to_float(prior_agency["event"].get("normalized_long_term_rank"))
        rows["months_since_prior_agency_rating"] = _months_between(current_date, pd.Timestamp(prior_agency["event"].get("rating_date")))
        rows.update(_financial_change_features(financial_profile, prior_agency["financial_profile"], prefix="since_prior_agency"))

    if prior_any is not None:
        rows["prior_any_rating_available"] = 1
        rows["prior_any_rating_rank"] = _to_float(prior_any["event"].get("normalized_long_term_rank"))
        rows["months_since_prior_any_rating"] = _months_between(current_date, pd.Timestamp(prior_any["event"].get("rating_date")))
        rows.update(_financial_change_features(financial_profile, prior_any["financial_profile"], prefix="since_prior_any"))

    return rows


def _financial_change_features(
    current_profile: dict[str, Any],
    prior_profile: dict[str, Any],
    *,
    prefix: str,
) -> dict[str, Any]:
    current_revenue = _to_float(current_profile.get("revenue_crore"))
    prior_revenue = _to_float(prior_profile.get("revenue_crore"))
    return {
        f"{prefix}_revenue_growth_pct": _growth_pct(current_revenue, prior_revenue),
        f"{prefix}_ebitda_margin_change": _difference(current_profile.get("ebitda_margin_pct"), prior_profile.get("ebitda_margin_pct")),
        f"{prefix}_debt_to_equity_change": _difference(current_profile.get("debt_to_equity"), prior_profile.get("debt_to_equity")),
        f"{prefix}_interest_coverage_change": _difference(current_profile.get("interest_coverage"), prior_profile.get("interest_coverage")),
        f"{prefix}_working_capital_days_change": _difference(current_profile.get("working_capital_days"), prior_profile.get("working_capital_days")),
    }


def _difference(current_value: Any, prior_value: Any) -> float | None:
    current_float = _to_float(current_value)
    prior_float = _to_float(prior_value)
    if current_float is None or prior_float is None:
        return None
    return round(current_float - prior_float, 4)


def _safe_cagr(start_value: float | None, end_value: float | None, years: float) -> float | None:
    if start_value is None or end_value is None or years <= 0 or start_value <= 0 or end_value <= 0:
        return None
    try:
        return round((((float(end_value) / float(start_value)) ** (1.0 / float(years))) - 1.0) * 100.0, 4)
    except (ZeroDivisionError, ValueError, OverflowError):
        return None


def _median_numeric(frame: pd.DataFrame, column: str) -> float | None:
    if column not in frame.columns:
        return None
    series = pd.to_numeric(frame[column], errors="coerce").dropna()
    if series.empty:
        return None
    return round(float(series.median()), 4)


def _prepare_context_lookup(context_frame: pd.DataFrame) -> dict[str, pd.DataFrame]:
    if context_frame.empty:
        return {}
    working = normalize_context_frame(context_frame)
    working["as_of_date"] = pd.to_datetime(working["as_of_date"], errors="coerce")
    lookup: dict[str, pd.DataFrame] = {}
    for company_id, group in working.groupby("company_id", dropna=False):
        lookup[str(company_id or "")] = group.sort_values("as_of_date").copy()
    return lookup


def _lookup_context_features(
    *,
    context_lookup: dict[str, pd.DataFrame],
    company_id: Any,
    as_of_date: Any,
) -> dict[str, Any]:
    rows: dict[str, Any] = {
        **{feature: None for feature in OPTIONAL_CONTEXT_NUMERIC_FEATURES},
        **{feature: 0 for feature in OPTIONAL_CONTEXT_BINARY_FEATURES},
    }
    context_rows = context_lookup.get(str(company_id or ""))
    if context_rows is None or context_rows.empty:
        rows["context_coverage"] = 0.0
        return rows

    cutoff_date = pd.Timestamp(as_of_date) if as_of_date is not None and not pd.isna(as_of_date) else None
    matched_rows = context_rows
    if cutoff_date is not None and context_rows["as_of_date"].notna().any():
        eligible = context_rows[context_rows["as_of_date"] <= cutoff_date]
        if not eligible.empty:
            matched_rows = eligible
    matched_rows = matched_rows.sort_values("as_of_date").copy()

    merged_row: dict[str, Any] = {}
    for feature in OPTIONAL_CONTEXT_NUMERIC_FEATURES:
        if feature not in matched_rows.columns:
            continue
        series = pd.to_numeric(matched_rows[feature], errors="coerce").dropna()
        merged_row[feature] = float(series.iloc[-1]) if not series.empty else None
    for feature in OPTIONAL_CONTEXT_BINARY_FEATURES:
        if feature not in matched_rows.columns:
            continue
        merged_row[feature] = bool(matched_rows[feature].apply(_to_bool).any())

    for feature in OPTIONAL_CONTEXT_NUMERIC_FEATURES:
        rows[feature] = _to_float(merged_row.get(feature))

    rows["promoter_delinquency_flag"] = int(
        _to_bool(merged_row.get("promoter_delinquency_flag"))
        or ((_to_float(merged_row.get("promoter_delinquency_count")) or 0.0) > 0.0)
    )
    rows["criminal_case_flag"] = int(
        _to_bool(merged_row.get("criminal_case_flag"))
        or ((_to_float(merged_row.get("criminal_case_count")) or 0.0) > 0.0)
    )
    rows["plan_submission_available"] = int(_to_bool(merged_row.get("plan_submission_available")))
    rows["plan_on_track_flag"] = int(_to_bool(merged_row.get("plan_on_track_flag")))
    rows["public_risk_flag"] = int(
        _to_bool(merged_row.get("public_risk_flag"))
        or ((_to_float(merged_row.get("public_risk_score")) or 0.0) >= 4.0)
    )
    revenue_plan = _to_float(merged_row.get("projected_revenue_cagr_5y"))
    industry_revenue_plan = _to_float(merged_row.get("industry_expected_revenue_cagr_5y"))
    margin_plan = _to_float(merged_row.get("projected_ebitda_margin_pct_5y"))
    industry_margin_plan = _to_float(merged_row.get("industry_expected_ebitda_margin_pct_5y"))
    rows["growth_plan_vs_industry_gap_pct"] = _difference(revenue_plan, industry_revenue_plan)
    rows["margin_plan_vs_industry_gap_pct"] = _difference(margin_plan, industry_margin_plan)
    plan_gap = _to_float(rows.get("growth_plan_vs_industry_gap_pct"))
    rows["plan_aggressiveness_score"] = round(max(0.0, plan_gap or 0.0), 4) if plan_gap is not None else None
    rows["growth_plan_aggressive_flag"] = int(plan_gap is not None and plan_gap > 5.0)
    rows["context_coverage"] = _context_feature_coverage(rows)
    return rows


def _prepare_company_rating_history(events_frame: pd.DataFrame) -> dict[str, list[dict[str, Any]]]:
    if events_frame.empty:
        return {}
    working = events_frame.copy()
    working["agency_name"] = working["agency_name"].map(_normalize_agency_key)
    working["rating_date"] = pd.to_datetime(working["rating_date"], errors="coerce")
    working["eligibility_status"] = working.apply(_event_eligibility_status, axis=1)
    working = working[working["eligibility_status"] == "eligible"].copy()
    lookup: dict[str, list[dict[str, Any]]] = {}
    for company_id, group in working.groupby("company_id", dropna=False):
        lookup[str(company_id or "")] = sorted(group.to_dict(orient="records"), key=lambda row: pd.Timestamp(row.get("rating_date")))
    return lookup


def _build_prior_population_features(
    *,
    company_id: Any,
    agency_name: str,
    as_of_date: Any,
    current_financial_profile: dict[str, Any],
    rating_history_lookup: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    rows: dict[str, Any] = {
        "prior_agency_rating_available": 0,
        "prior_any_rating_available": 0,
        **{feature: None for feature in PRIOR_RATING_NUMERIC_FEATURES},
    }
    company_history = rating_history_lookup.get(str(company_id or ""))
    if not company_history:
        return rows

    cutoff_date = pd.Timestamp(as_of_date) if as_of_date is not None and not pd.isna(as_of_date) else None
    prior_any = None
    prior_agency = None
    for item in company_history:
        rating_date = pd.Timestamp(item.get("rating_date"))
        if cutoff_date is not None and (pd.isna(rating_date) or rating_date >= cutoff_date):
            break
        prior_any = item
        if item.get("agency_name") == agency_name:
            prior_agency = item

    if prior_agency is not None:
        rows["prior_agency_rating_available"] = 1
        rows["prior_agency_rating_rank"] = _to_float(prior_agency.get("normalized_long_term_rank"))
        rows["months_since_prior_agency_rating"] = _months_between(cutoff_date, pd.Timestamp(prior_agency.get("rating_date"))) if cutoff_date is not None else None
    if prior_any is not None:
        rows["prior_any_rating_available"] = 1
        rows["prior_any_rating_rank"] = _to_float(prior_any.get("normalized_long_term_rank"))
        rows["months_since_prior_any_rating"] = _months_between(cutoff_date, pd.Timestamp(prior_any.get("rating_date"))) if cutoff_date is not None else None
    return rows


def _months_between(current_date: pd.Timestamp, prior_date: pd.Timestamp) -> float | None:
    if pd.isna(current_date) or pd.isna(prior_date):
        return None
    return round(float((current_date - prior_date).days) / 30.4375, 2)


def _apply_context_and_peer_derivatives(row: dict[str, Any]) -> None:
    projected_revenue = _to_float(row.get("projected_revenue_cagr_5y"))
    projected_margin = _to_float(row.get("projected_ebitda_margin_pct_5y"))
    scale_peer_revenue = _to_float(row.get("scale_peer_forward_revenue_cagr"))
    scale_peer_margin = _to_float(row.get("scale_peer_forward_ebitda_margin_change"))
    row["projected_revenue_cagr_vs_scale_peers_gap"] = _difference(projected_revenue, scale_peer_revenue)
    row["projected_margin_vs_scale_peers_gap"] = _difference(projected_margin, scale_peer_margin)


def _build_training_row(
    *,
    event: dict[str, Any],
    financial_history: pd.DataFrame,
    rationale: dict[str, Any],
    extra_features: dict[str, Any] | None = None,
) -> dict[str, Any]:
    financial_profile = _build_financial_window_features(financial_history)
    matched_period_date = financial_profile.get("period_date")
    row: dict[str, Any] = {
        "company_id": event.get("company_id"),
        "company_name": event.get("company_name"),
        "agency_name": _normalize_agency_key(event.get("agency_name")),
        "rating_event_id": event.get("rating_event_id"),
        "rationale_doc_id": event.get("rationale_doc_id"),
        "rating_date": _iso_date(event.get("rating_date")),
        "current_rating": event.get("current_rating"),
        "long_term_rating": event.get("long_term_rating"),
        "previous_rating": event.get("previous_rating"),
        "normalized_long_term_label": event.get("normalized_long_term_label"),
        "normalized_long_term_rank": event.get("normalized_long_term_rank"),
        "sub_industry": financial_history.iloc[-1].get("sub_industry") if not financial_history.empty else None,
        "matched_financial_period": financial_profile.get("matched_financial_period"),
        "standalone_or_consolidated": rationale.get("standalone_or_consolidated"),
        "liquidity_label": rationale.get("liquidity_label"),
        "days_from_financial_period": int((event["rating_date"] - matched_period_date).days) if matched_period_date is not None else None,
        "data_completeness": financial_profile.get("data_completeness"),
        "feature_coverage": _rationale_feature_coverage(rationale),
    }
    row.update(financial_profile)
    if extra_features:
        row.update(extra_features)
    _apply_context_and_peer_derivatives(row)
    row["context_coverage"] = _context_feature_coverage(row)
    for feature in NUMERIC_MODEL_FEATURES:
        row.setdefault(feature, None)
    for feature in RATIONALE_BINARY_FEATURES:
        row[feature] = _to_bool(rationale.get(feature))
    for feature in RATIONALE_COUNT_FEATURES:
        row[feature] = _to_float(rationale.get(feature))
    return row


def _build_training_summary(training_frame: pd.DataFrame, exclusion_rows: list[dict[str, Any]]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    if not training_frame.empty:
        for agency_name, group in training_frame.groupby("agency_name"):
            rows.append(
                {
                    "agency_name": agency_name,
                    "row_type": "eligible_training_rows",
                    "rows": int(len(group)),
                }
            )
    if exclusion_rows:
        exclusion_frame = pd.DataFrame(exclusion_rows)
        for (agency_name, status), count in exclusion_frame.groupby(["agency_name", "eligibility_status"]).size().items():
            rows.append(
                {
                    "agency_name": agency_name,
                    "row_type": str(status),
                    "rows": int(count),
                }
            )
    return pd.DataFrame(rows)


def _build_latest_company_feature_frame(
    *,
    features_frame: pd.DataFrame,
    agency_name: str,
    benchmark_lookup: dict[tuple[str, str], pd.DataFrame] | None = None,
    trajectory_lookup: dict[str, pd.DataFrame] | None = None,
    rating_history_lookup: dict[str, list[dict[str, Any]]] | None = None,
    context_lookup: dict[str, pd.DataFrame] | None = None,
) -> pd.DataFrame:
    if features_frame.empty:
        return pd.DataFrame()
    working = features_frame.copy()
    working["period_date"] = pd.to_datetime(working["period_date"], errors="coerce")
    benchmark_lookup = benchmark_lookup or {}
    trajectory_lookup = trajectory_lookup or {}
    rating_history_lookup = rating_history_lookup or {}
    context_lookup = context_lookup or {}
    rows: list[dict[str, Any]] = []
    for _, company_history in working.groupby("company_id", dropna=False):
        history_window = company_history.sort_values("period_date").tail(4).copy()
        if history_window.empty:
            continue
        latest = history_window.iloc[-1]
        financial_profile = _build_financial_window_features(history_window)
        row = {
            "company_id": latest.get("company_id"),
            "company_name": latest.get("company_name"),
            "nse_code": latest.get("nse_code"),
            "bse_code": latest.get("bse_code"),
            "industry_group": latest.get("industry_group"),
            "sub_industry": latest.get("sub_industry"),
            "period": latest.get("period"),
            "matched_financial_period": latest.get("period"),
        }
        row.update(financial_profile)
        row.update(
            _build_industry_benchmark_features(
                financial_profile=financial_profile,
                latest_feature=latest.to_dict(),
                benchmark_lookup=benchmark_lookup,
            )
        )
        row.update(
            _build_scale_peer_trajectory_features(
                financial_profile=financial_profile,
                latest_feature=latest.to_dict(),
                trajectory_lookup=trajectory_lookup,
                exclude_company_id=latest.get("company_id"),
            )
        )
        row.update(
            _build_prior_population_features(
                company_id=latest.get("company_id"),
                agency_name=agency_name,
                as_of_date=latest.get("period_date"),
                current_financial_profile=financial_profile,
                rating_history_lookup=rating_history_lookup,
            )
        )
        row.update(
            _lookup_context_features(
                context_lookup=context_lookup,
                company_id=latest.get("company_id"),
                as_of_date=latest.get("period_date"),
            )
        )
        _apply_context_and_peer_derivatives(row)
        rows.append(row)
    return pd.DataFrame(rows)


def _ensure_model_feature_columns(frame: pd.DataFrame) -> pd.DataFrame:
    working = frame.copy()
    for column in NUMERIC_MODEL_FEATURES:
        if column not in working.columns:
            working[column] = np.nan
    for column in RATIONALE_BINARY_FEATURES:
        if column not in working.columns:
            working[column] = 0
        working[column] = working[column].apply(_to_bool).astype(int)
    for column in RATIONALE_COUNT_FEATURES:
        if column not in working.columns:
            working[column] = 0.0
        working[column] = pd.to_numeric(working[column], errors="coerce").fillna(0.0)
    for column in DERIVED_MODEL_FEATURES:
        if column not in working.columns:
            if column == "data_completeness":
                working[column] = working.apply(_financial_data_completeness, axis=1)
            elif column == "feature_coverage":
                working[column] = working.apply(_rationale_feature_coverage, axis=1)
            elif column == "context_coverage":
                working[column] = working.apply(_context_feature_coverage, axis=1)
            else:
                working[column] = 0.0
        if column in TREND_BINARY_FEATURES:
            working[column] = working[column].apply(_to_bool).astype(int)
        if column in PRIOR_RATING_BINARY_FEATURES or column in OPTIONAL_CONTEXT_BINARY_FEATURES:
            working[column] = working[column].apply(_to_bool).astype(int)
    for column in CATEGORICAL_MODEL_FEATURES:
        if column not in working.columns:
            working[column] = "Unknown"
        working[column] = working[column].fillna("Unknown").replace("", "Unknown")
    if "matched_financial_period" not in working.columns and "period" in working.columns:
        working["matched_financial_period"] = working["period"]
    return working


def _financial_data_completeness(row: pd.Series | dict[str, Any]) -> float:
    latest_coverage = _feature_group_coverage(row, CORE_FINANCIAL_FEATURES)
    rolling_avg_coverage = _feature_group_coverage(row, [f"{feature}_avg3y" for feature in CORE_FINANCIAL_FEATURES])
    rolling_trend_coverage = _feature_group_coverage(
        row,
        [
            f"{feature}_delta1y"
            for feature in (
                "revenue_crore",
                "ebitda_margin_pct",
                "pat_margin_pct",
                "debt_to_equity",
                "interest_coverage",
                "working_capital_days",
                "networth_crore",
                "total_borrowings_crore",
            )
        ],
    )
    history_depth = min((_to_float(row.get("history_periods_available")) or 0.0) / 4.0, 1.0)
    score = (0.55 * latest_coverage) + (0.2 * rolling_avg_coverage) + (0.15 * rolling_trend_coverage) + (0.1 * history_depth)
    return round(score, 4)


def _feature_group_coverage(row: pd.Series | dict[str, Any], features: list[str]) -> float:
    if not features:
        return 0.0
    available = 0
    for feature in features:
        value = row.get(feature) if hasattr(row, "get") else None
        if _to_float(value) is not None:
            available += 1
    return available / len(features)


def _select_active_numeric_features(frame: pd.DataFrame) -> list[str]:
    return [
        feature
        for feature in NUMERIC_MODEL_FEATURES
        if feature in frame.columns and pd.to_numeric(frame[feature], errors="coerce").notna().any()
    ]


def _select_active_categorical_features(frame: pd.DataFrame) -> list[str]:
    active: list[str] = []
    for feature in CATEGORICAL_MODEL_FEATURES:
        if feature not in frame.columns:
            continue
        series = frame[feature].fillna("Unknown").astype(str).str.strip().replace("", "Unknown")
        if series.nunique(dropna=False) > 1 or (not series.empty and series.iloc[0] != "Unknown"):
            active.append(feature)
    return active


def _rationale_feature_coverage(row: pd.Series | dict[str, Any]) -> float:
    signals = 0
    total = 7
    if any(_to_bool(row.get(feature)) for feature in RATIONALE_BINARY_FEATURES):
        signals += 1
    if _string(row.get("liquidity_label")):
        signals += 1
    if _string(row.get("standalone_or_consolidated")):
        signals += 1
    if (_to_float(row.get("strengths_count")) or 0) > 0:
        signals += 1
    if (_to_float(row.get("weaknesses_count")) or 0) > 0:
        signals += 1
    if (_to_float(row.get("sensitivities_up_count")) or 0) > 0:
        signals += 1
    if (_to_float(row.get("sensitivities_down_count")) or 0) > 0:
        signals += 1
    return round(signals / total, 4)


def _context_feature_coverage(row: pd.Series | dict[str, Any]) -> float:
    signals = 0
    total = 8
    if _to_float(row.get("promoter_bureau_score")) is not None or (_to_float(row.get("promoter_delinquency_count")) or 0) > 0:
        signals += 1
    if (_to_float(row.get("criminal_case_count")) or 0) > 0 or _to_bool(row.get("criminal_case_flag")):
        signals += 1
    if _to_float(row.get("regulatory_risk_score")) is not None or _to_float(row.get("governance_risk_score")) is not None:
        signals += 1
    if _to_float(row.get("projected_revenue_cagr_5y")) is not None or _to_bool(row.get("plan_submission_available")):
        signals += 1
    if _to_float(row.get("industry_expected_revenue_cagr_5y")) is not None or _to_float(row.get("industry_expected_ebitda_margin_pct_5y")) is not None:
        signals += 1
    if _to_float(row.get("execution_track_record_score")) is not None or _to_float(row.get("plan_progress_score")) is not None:
        signals += 1
    if (_to_float(row.get("public_risk_score")) or 0) > 0 or _to_bool(row.get("public_risk_flag")):
        signals += 1
    if (_to_float(row.get("promoter_adverse_hits")) or 0) > 0 or (_to_float(row.get("industry_outlook_score")) is not None):
        signals += 1
    return round(signals / total, 4)


def _within_one_notch_accuracy(actual_labels: np.ndarray, predicted_labels: np.ndarray) -> float:
    if len(actual_labels) == 0:
        return np.nan
    actual_ranks = np.array([LONG_TERM_ORDER.index(label) + 1 for label in actual_labels])
    predicted_ranks = np.array([LONG_TERM_ORDER.index(label) + 1 for label in predicted_labels])
    return float(np.mean(np.abs(predicted_ranks - actual_ranks) <= 1))


def _build_confusion_matrix_frame(actual_labels: np.ndarray, predicted_labels: np.ndarray) -> pd.DataFrame:
    if len(actual_labels) == 0:
        return pd.DataFrame()
    label_set = [label for label in LONG_TERM_ORDER if label in set(actual_labels) | set(predicted_labels)]
    matrix = confusion_matrix(actual_labels, predicted_labels, labels=label_set)
    frame = pd.DataFrame(matrix, columns=label_set)
    frame.insert(0, "actual_rating", label_set)
    return frame


def _summarize_training_feature_stats(dataset: pd.DataFrame) -> dict[str, Any]:
    stats: dict[str, Any] = {"numeric_quantiles": {}}
    for feature in NUMERIC_MODEL_FEATURES:
        series = pd.to_numeric(dataset[feature], errors="coerce")
        if series.notna().any():
            stats["numeric_quantiles"][feature] = {
                "q25": round(float(series.quantile(0.25)), 4),
                "q75": round(float(series.quantile(0.75)), 4),
            }
    return stats


def _predict_rating_outputs(
    *,
    classifier_pipeline: Pipeline,
    rank_regressor: Pipeline | None,
    X: pd.DataFrame,
    label_order: list[str],
    blend_weights: dict[str, float] | None = None,
) -> tuple[np.ndarray, list[dict[str, float]]]:
    blend_weights = blend_weights or {"classifier": 0.65, "rank_regressor": 0.35}
    classifier_probabilities = classifier_pipeline.predict_proba(X)
    classes = [str(label) for label in classifier_pipeline.named_steps["model"].classes_]
    rank_predictions = rank_regressor.predict(X) if rank_regressor is not None else [None] * len(X)

    predicted_labels: list[str] = []
    probability_maps: list[dict[str, float]] = []
    for index in range(len(X)):
        classifier_map = {
            label: float(probability)
            for label, probability in zip(classes, classifier_probabilities[index], strict=False)
        }
        if rank_regressor is not None:
            regressor_map = _rank_prediction_to_probability_map(float(rank_predictions[index]), label_order)
            combined = _combine_probability_maps(
                classifier_map=classifier_map,
                regressor_map=regressor_map,
                classifier_weight=float(blend_weights.get("classifier", 0.65)),
                regressor_weight=float(blend_weights.get("rank_regressor", 0.35)),
            )
        else:
            combined = _normalize_probability_map(classifier_map)
        ordered_map = {
            label: round(float(probability), 4)
            for label, probability in sorted(combined.items(), key=lambda item: item[1], reverse=True)
        }
        probability_maps.append(ordered_map)
        predicted_labels.append(next(iter(ordered_map)) if ordered_map else classes[0])
    return np.array(predicted_labels), probability_maps


def _rank_prediction_to_probability_map(predicted_rank: float, label_order: list[str]) -> dict[str, float]:
    if not label_order:
        return {}
    sigma = 1.15
    weights: dict[str, float] = {}
    for label in label_order:
        label_rank = LONG_TERM_ORDER.index(label) + 1
        distance = predicted_rank - label_rank
        weights[label] = float(np.exp(-((distance**2) / (2 * sigma**2))))
    return _normalize_probability_map(weights)


def _combine_probability_maps(
    *,
    classifier_map: dict[str, float],
    regressor_map: dict[str, float],
    classifier_weight: float,
    regressor_weight: float,
) -> dict[str, float]:
    all_labels = set(classifier_map) | set(regressor_map)
    combined = {
        label: (classifier_weight * float(classifier_map.get(label, 0.0))) + (regressor_weight * float(regressor_map.get(label, 0.0)))
        for label in all_labels
    }
    return _normalize_probability_map(combined)


def _normalize_probability_map(probability_map: dict[str, float]) -> dict[str, float]:
    total = sum(max(0.0, float(value)) for value in probability_map.values())
    if total <= 0:
        return probability_map
    return {label: float(value) / total for label, value in probability_map.items()}


def _score_prediction_frame(
    *,
    frame: pd.DataFrame,
    artifact: dict[str, Any],
    population_type: str,
) -> list[dict[str, Any]]:
    pipeline: Pipeline = artifact["pipeline"]
    rank_regressor: Pipeline | None = artifact.get("rank_regressor")
    working = _ensure_model_feature_columns(frame)
    X = working[[*artifact["numeric_features"], *artifact["categorical_features"]]].copy()
    predicted_labels, probability_maps = _predict_rating_outputs(
        classifier_pipeline=pipeline,
        rank_regressor=rank_regressor,
        X=X,
        label_order=list(artifact.get("label_order") or []),
        blend_weights=artifact.get("probability_blend_weights"),
    )
    rows: list[dict[str, Any]] = []

    for index, (_, record) in enumerate(working.iterrows()):
        probability_map = probability_maps[index]
        predicted_rating = str(predicted_labels[index])
        top_probability = max(probability_map.values()) if probability_map else 0.0
        data_completeness = _financial_data_completeness(record)
        feature_coverage = _rationale_feature_coverage(record)
        confidence = _blend_prediction_confidence(
            probability_confidence=top_probability,
            data_completeness=data_completeness,
            feature_coverage=feature_coverage,
            context_coverage=_context_feature_coverage(record),
            history_depth=min((_to_float(record.get("history_periods_available")) or 0.0) / 4.0, 1.0),
        )
        actual_rating = _string(record.get("normalized_long_term_label"))
        actual_rank = LONG_TERM_ORDER.index(actual_rating) + 1 if actual_rating in LONG_TERM_ORDER else None
        predicted_rank = LONG_TERM_ORDER.index(predicted_rating) + 1 if predicted_rating in LONG_TERM_ORDER else None
        deviation = predicted_rank - actual_rank if actual_rank is not None and predicted_rank is not None else None
        rows.append(
            {
                "company_id": record.get("company_id"),
                "company_name": record.get("company_name"),
                "agency": artifact["agency_name"],
                "predicted_rating": predicted_rating,
                "rating_range": " / ".join(list(probability_map)[:2]) if probability_map else None,
                "confidence": round(confidence, 4),
                "actual_rating": actual_rating,
                "deviation": deviation,
                "key_features": json.dumps(_derive_key_features(record, artifact.get("feature_stats", {}))),
                "population_type": population_type,
                "prediction_status": "predicted",
                "financial_period": record.get("matched_financial_period") or record.get("period"),
                "probability_distribution_json": json.dumps(probability_map),
                "feature_snapshot_json": json.dumps(_serialize_feature_snapshot(record)),
                "top_probability": round(top_probability, 4),
                "data_completeness": round(data_completeness, 4),
                "feature_coverage": round(feature_coverage, 4),
                "confidence_label": _confidence_label(confidence),
            }
        )
    return rows


def _blend_prediction_confidence(
    *,
    probability_confidence: float,
    data_completeness: float,
    feature_coverage: float,
    context_coverage: float = 0.0,
    history_depth: float = 0.0,
) -> float:
    score = (
        (0.42 * probability_confidence)
        + (0.2 * data_completeness)
        + (0.1 * feature_coverage)
        + (0.13 * history_depth)
        + (0.15 * context_coverage)
    )
    return max(0.05, min(0.99, round(score, 6)))


def _derive_key_features(record: pd.Series, feature_stats: dict[str, Any]) -> list[str]:
    cues: list[str] = []
    quantiles = feature_stats.get("numeric_quantiles", {})

    for feature in ("ebitda_margin_pct", "interest_coverage", "cash_to_borrowings", "asset_turnover"):
        value = _to_float(record.get(feature))
        feature_quantiles = quantiles.get(feature, {})
        if value is None or not feature_quantiles:
            continue
        if value >= feature_quantiles.get("q75", value + 1):
            cues.append(_friendly_numeric_feature_label(feature, high=True))

    for feature in ("debt_to_equity", "working_capital_days", "receivables_days", "inventory_days"):
        value = _to_float(record.get(feature))
        feature_quantiles = quantiles.get(feature, {})
        if value is None or not feature_quantiles:
            continue
        if value >= feature_quantiles.get("q75", value + 1):
            cues.append(_friendly_numeric_feature_label(feature, high=False))

    for feature in RATIONALE_BINARY_FEATURES:
        if _to_bool(record.get(feature)):
            cues.append(RATIONALE_SIGNAL_LABELS.get(feature, feature))

    if _string(record.get("liquidity_label")):
        cues.append(f"liquidity: {record.get('liquidity_label')}")
    if _string(record.get("standalone_or_consolidated")):
        cues.append(str(record.get("standalone_or_consolidated")).lower())

    if _to_bool(record.get("profitability_trend_positive")):
        cues.append("profitability improving")
    if _to_bool(record.get("leverage_trend_improving")):
        cues.append("leverage improving")
    if _to_bool(record.get("coverage_trend_improving")):
        cues.append("coverage improving")
    if _to_bool(record.get("working_capital_trend_improving")):
        cues.append("working capital cycle improving")
    if (_to_float(record.get("history_periods_available")) or 0) >= 3:
        cues.append("multi-year financial history available")
    if (_to_float(record.get("prior_agency_rating_rank")) or 0) > 0:
        cues.append("past agency rating available")
    if (_to_float(record.get("industry_interest_coverage_percentile")) or 0) >= 0.75:
        cues.append("coverage stronger than industry median")
    if (_to_float(record.get("industry_ebitda_margin_percentile")) or 0) >= 0.75:
        cues.append("margins stronger than industry peers")
    if (_to_float(record.get("industry_working_capital_days_percentile")) or 0) >= 0.75:
        cues.append("working capital weaker than industry peers")
    if (_to_float(record.get("scale_peer_forward_revenue_cagr")) or 0) > 0:
        cues.append("listed peer trajectories available at similar scale")
    if (_to_float(record.get("projected_revenue_cagr_vs_scale_peers_gap")) or 0) > 5:
        cues.append("projected growth exceeds listed peer trajectories")
    if _to_bool(record.get("promoter_delinquency_flag")):
        cues.append("promoter bureau stress")
    if _to_bool(record.get("criminal_case_flag")):
        cues.append("legal or criminal case flag")
    if _to_bool(record.get("public_risk_flag")) or (_to_float(record.get("public_risk_score")) or 0) >= 4:
        cues.append("public-domain risk signals detected")
    if _to_bool(record.get("growth_plan_aggressive_flag")):
        cues.append("growth plan appears aggressive")
    if _to_bool(record.get("plan_on_track_flag")):
        cues.append("management plan execution on track")

    if not cues:
        cues.append("financial profile only; limited rationale coverage")
    return cues[:5]


def _serialize_feature_snapshot(record: pd.Series) -> dict[str, Any]:
    snapshot_fields = [
        "revenue_crore",
        "ebitda_margin_pct",
        "pat_margin_pct",
        "debt_to_equity",
        "interest_coverage",
        "working_capital_days",
        "receivables_days",
        "inventory_days",
        "networth_crore",
        "total_borrowings_crore",
        "industry_revenue_percentile",
        "industry_ebitda_margin_percentile",
        "industry_debt_to_equity_percentile",
        "industry_interest_coverage_percentile",
        "industry_working_capital_days_percentile",
        "scale_peer_sample_size",
        "scale_peer_forward_revenue_cagr",
        "scale_peer_forward_ebitda_margin_change",
        "scale_peer_ebitda_margin_gap_to_median",
        "projected_revenue_cagr_vs_scale_peers_gap",
        "prior_agency_rating_rank",
        "prior_any_rating_rank",
        "months_since_prior_agency_rating",
        "months_since_prior_any_rating",
        "promoter_bureau_score",
        "promoter_delinquency_count",
        "promoter_adverse_hits",
        "criminal_case_count",
        "regulatory_risk_score",
        "governance_risk_score",
        "projected_revenue_cagr_5y",
        "industry_expected_revenue_cagr_5y",
        "public_negative_news_hits",
        "fraud_signal_hits",
        "regulatory_action_hits",
        "insolvency_signal_hits",
        "litigation_signal_hits",
        "public_risk_score",
        "industry_outlook_score",
        "plan_progress_score",
        "context_coverage",
    ]
    snapshot: dict[str, Any] = {}
    for field in snapshot_fields:
        value = record.get(field)
        if isinstance(value, (np.integer, np.floating)):
            snapshot[field] = None if np.isnan(value) else float(value)
        elif isinstance(value, pd.Timestamp):
            snapshot[field] = value.isoformat()
        else:
            snapshot[field] = value
    for field in ("prior_agency_rating_available", "prior_any_rating_available", "promoter_delinquency_flag", "criminal_case_flag", "plan_submission_available", "plan_on_track_flag", "growth_plan_aggressive_flag", "public_risk_flag"):
        snapshot[field] = bool(_to_bool(record.get(field)))
    return snapshot


def _friendly_numeric_feature_label(feature: str, *, high: bool) -> str:
    labels = {
        "ebitda_margin_pct": "healthy EBITDA margins",
        "interest_coverage": "strong interest coverage",
        "cash_to_borrowings": "cash buffers support debt service",
        "asset_turnover": "healthy asset turnover",
        "debt_to_equity": "elevated leverage",
        "working_capital_days": "stretched working capital cycle",
        "receivables_days": "high receivable days",
        "inventory_days": "high inventory holding",
    }
    return labels.get(feature, feature if high else f"pressure on {feature}")


def _iso_date(value: Any) -> str | None:
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return None
    if hasattr(value, "date"):
        try:
            return value.date().isoformat()
        except AttributeError:
            pass
    text = str(value).strip()
    return text or None


def _company_meta(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "company_id": record.get("company_id"),
        "company_name": record.get("company_name"),
        "nse_code": _string(record.get("nse_code")),
        "bse_code": _string(record.get("bse_code")),
        "industry_group": record.get("industry_group"),
        "sub_industry": record.get("sub_industry"),
    }


def _ratio_pct(numerator: float | None, denominator: float | None) -> float | None:
    ratio = _safe_ratio(numerator, denominator)
    return round(ratio * 100.0, 4) if ratio is not None else None


def _ratio_days(numerator: float | None, denominator: float | None) -> float | None:
    ratio = _safe_ratio(numerator, denominator)
    return round(ratio * 365.0, 4) if ratio is not None else None


def _safe_ratio(numerator: float | None, denominator: float | None) -> float | None:
    if numerator is None or denominator in {None, 0}:
        return None
    return round(float(numerator) / float(denominator), 6)


def _safe_sum(values: list[float | None]) -> float | None:
    clean = [value for value in values if value is not None]
    if not clean:
        return None
    return round(float(sum(clean)), 6)


def _growth_pct(current: float | None, previous: float | None) -> float | None:
    if current is None or previous in {None, 0}:
        return None
    return round(((float(current) - float(previous)) / abs(float(previous))) * 100.0, 4)


def _to_float(value: Any) -> float | None:
    try:
        if value is None or (isinstance(value, float) and np.isnan(value)):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _ensure_list(value: Any) -> list[str]:
    if value is None or value == "":
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            if isinstance(parsed, list):
                return [str(item).strip() for item in parsed if str(item).strip()]
        except json.JSONDecodeError:
            try:
                parsed = literal_eval(value)
                if isinstance(parsed, list):
                    return [str(item).strip() for item in parsed if str(item).strip()]
            except (ValueError, SyntaxError):
                return [value.strip()] if value.strip() else []
    return [str(value).strip()] if str(value).strip() else []


def _normalize_agency_key(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip().lower().replace("&", "and")
    text = "".join(character if character.isalnum() else "_" for character in text)
    text = "_".join(part for part in text.split("_") if part)
    if text in AGENCY_ALIAS_MAP:
        return AGENCY_ALIAS_MAP[text]
    if "fitch" in text or ("india" in text and "rating" in text):
        return "india_ratings"
    if text.startswith("care"):
        return "care"
    if text.startswith("smera") or text.startswith("acuite"):
        return "acuite"
    return text


def _detect_agency_from_url(url: str) -> str | None:
    host = urlsplit(url).netloc.lower()
    if "crisil" in host:
        return "crisil"
    if "care" in host:
        return "care"
    if "icra" in host:
        return "icra"
    if "indiaratings" in host or "fitchratings" in host or "fitch" in host:
        return "india_ratings"
    if "acuite" in host or "smera" in host:
        return "acuite"
    if "brickwork" in host:
        return "brickwork"
    if "infomerics" in host:
        return "infomerics"
    return None


def _looks_like_pdf(url: str, content_type: str) -> bool:
    return ".pdf" in url.lower() or "application/pdf" in content_type


def _stable_hash(value: str) -> str:
    return hashlib.sha1(value.encode("utf-8")).hexdigest()[:16]


def _confidence_label(score: float) -> str:
    if score >= 0.75:
        return "high"
    if score >= 0.5:
        return "medium"
    return "low"


def _to_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return False
    if isinstance(value, (int, np.integer)):
        return bool(value)
    text = str(value).strip().lower()
    return text in {"true", "1", "yes", "y"}


def _string(value: Any) -> str | None:
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return None
    text = str(value).strip()
    return text or None


def load_model_artifact(model_path: Path) -> dict[str, Any]:
    with model_path.open("rb") as handle:
        return pickle.load(handle)
