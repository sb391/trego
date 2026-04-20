from __future__ import annotations

import json
import logging
import time
from dataclasses import replace
from pathlib import Path
from typing import Any

import httpx
import pandas as pd

from ..config import AppConfig
from ..io_utils import build_company_id, company_name_tokens, normalize_company_name
from ..models import CorporateRecord
from ..schemas.crosswalks import LONG_TERM_ORDER, normalize_rating_label
from ..screener_matcher import candidate_from_payload, choose_best_match
from .config import CreditIntelConfig
from .financial_ingestion import build_financial_dataset_from_manifest
from .rating_discovery import RatingDiscoveryService
from .rating_repository import ExistingRatingRepository
from .schemas import CompanyCreditProfile, RatingHistoryEntry, RatingInsight
from .simulation_pipeline import _score_prediction_frame, load_model_artifact, simulate_unrated_companies


LOGGER = logging.getLogger(__name__)
DEFAULT_RANGE_TARGET = 0.75
DEFAULT_RANGE_FALLBACK_HALFWIDTH = 5
PUBLISHED_RANGE_MAX_HALFWIDTH = 2
PUBLISHED_RANGE_MIN_MASS_BY_HALFWIDTH = {
    0: 0.46,
    1: 0.62,
    2: 0.76,
}
PUBLISHED_RANGE_MIN_CONFIDENCE_BY_HALFWIDTH = {
    0: 0.68,
    1: 0.63,
    2: 0.58,
}
PUBLISHED_RANGE_MIN_TOP_PROB_BY_HALFWIDTH = {
    0: 0.42,
    1: 0.32,
    2: 0.24,
}
DEFAULT_AGENCY_RANGE_HALFWIDTHS = {
    "crisil": 2,
    "care": 8,
    "icra": 7,
    "india_ratings": 12,
    "acuite": 5,
    "brickwork": 10,
    "infomerics": 5,
}

AGENCY_NORMALIZATION = {
    "crisil": "crisil",
    "crisil ratings": "crisil",
    "care": "care",
    "care ratings": "care",
    "careedge": "care",
    "icra": "icra",
    "india ratings": "india_ratings",
    "india ratings and research": "india_ratings",
    "ind": "india_ratings",
    "fitch": "india_ratings",
    "acuite": "acuite",
    "acuite ratings": "acuite",
    "brickwork": "brickwork",
    "brickwork ratings": "brickwork",
    "infomerics": "infomerics",
    "ivr": "infomerics",
}


def run_external_simulation_benchmark(
    *,
    input_paths: list[Path],
    output_dir: Path,
    model_base_dir: Path,
    force_rating_refresh: bool = False,
    rating_validation_mode: str = "legacy",
) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = output_dir / "input_manifest.csv"
    financials_dir = output_dir / "financials"
    simulations_dir = output_dir / "simulations"
    reports_dir = output_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    manifest_rows = [{"file_path": str(path.expanduser().resolve()), "provider": "generic_excel"} for path in input_paths]
    pd.DataFrame(manifest_rows).to_csv(manifest_path, index=False)

    financial_outputs = build_financial_dataset_from_manifest(
        manifest_path=manifest_path,
        output_dir=financials_dir,
    )

    summary_frame = pd.read_csv(financial_outputs["financial_summary"])
    latest_features_frame = pd.read_csv(financial_outputs["latest_financial_features"])
    financial_parameters_frame = pd.read_csv(financial_outputs["financial_parameters_annual"])
    listed_status_path = reports_dir / "listed_status.csv"
    listed_status_frame = _discover_listed_status(
        companies_frame=_build_company_master(
            summary_frame=summary_frame,
            latest_features_frame=latest_features_frame,
            financial_parameters_frame=financial_parameters_frame,
        ),
        output_path=listed_status_path,
        force_refresh=False,
    )
    deduped_companies = _build_company_master(
        summary_frame=summary_frame,
        latest_features_frame=latest_features_frame,
        financial_parameters_frame=financial_parameters_frame,
    )
    deduped_companies = _normalize_merge_keys(deduped_companies, ["company_id", "company_name"])
    listed_status_frame = _normalize_merge_keys(listed_status_frame, ["company_id", "company_name"])
    deduped_companies = deduped_companies.merge(listed_status_frame, on=["company_id", "company_name"], how="left")

    company_master_path = reports_dir / "company_master.csv"
    deduped_companies.to_csv(company_master_path, index=False)

    simulation_outputs = simulate_unrated_companies(
        latest_financial_features_path=financial_outputs["latest_financial_features"],
        financial_history_path=financial_outputs["financial_year_features"],
        rating_events_path=model_base_dir / "rationales" / "rating_events.csv",
        model_dir=model_base_dir / "models" / "models",
        output_dir=simulations_dir,
    )

    actual_ratings_path = reports_dir / "actual_rating_discovery.csv"
    actual_ratings_frame = _discover_actual_ratings(
        companies_frame=deduped_companies,
        output_path=actual_ratings_path,
        force_refresh=force_rating_refresh,
        rating_validation_mode=rating_validation_mode,
    )
    actual_ratings_frame = _normalize_merge_keys(actual_ratings_frame, ["company_id", "company_name"])
    agency_strength_frame = _build_agency_strength_frame(model_base_dir / "models" / "agency_model_metrics.csv")
    agency_strength_path = reports_dir / "agency_strength.csv"
    agency_strength_frame.to_csv(agency_strength_path, index=False)

    simulation_frame = pd.read_csv(simulation_outputs["simulation_results"])
    simulation_frame = simulation_frame[simulation_frame["population_type"] == "simulation"].copy()
    benchmark_frame = _build_benchmark_frame(
        companies_frame=deduped_companies,
        actual_ratings_frame=actual_ratings_frame,
        simulation_frame=simulation_frame,
        model_metrics_path=model_base_dir / "models" / "agency_model_metrics.csv",
    )
    range_policy = _calibrate_agency_range_policy(benchmark_frame, target_coverage=DEFAULT_RANGE_TARGET)
    range_policy_path = reports_dir / "agency_range_calibration.csv"
    range_policy.to_csv(range_policy_path, index=False)

    agency_ranges = _build_agency_range_frame(
        companies_frame=deduped_companies,
        actual_ratings_frame=actual_ratings_frame,
        simulation_frame=simulation_frame,
        range_policy_frame=range_policy,
        agency_strength_frame=agency_strength_frame,
    )
    agency_ranges_path = reports_dir / "agency_wise_rating_ranges.csv"
    agency_ranges.to_csv(agency_ranges_path, index=False)

    range_benchmark = _build_company_range_benchmark(agency_ranges)
    range_benchmark_path = reports_dir / "company_rating_range_benchmark.csv"
    range_benchmark.to_csv(range_benchmark_path, index=False)

    range_summary = _build_range_summary(agency_ranges)
    range_summary_path = reports_dir / "agency_range_benchmark_summary.csv"
    range_summary.to_csv(range_summary_path, index=False)

    benchmark_csv_path = reports_dir / "company_rating_benchmark.csv"
    benchmark_frame.to_csv(benchmark_csv_path, index=False)

    agency_summary = _build_agency_summary(benchmark_frame)
    agency_summary_path = reports_dir / "agency_benchmark_summary.csv"
    agency_summary.to_csv(agency_summary_path, index=False)

    workbook_path = reports_dir / "external_company_rating_benchmark.xlsx"
    with pd.ExcelWriter(workbook_path, engine="openpyxl") as writer:
        benchmark_frame.to_excel(writer, sheet_name="company_benchmark", index=False)
        range_benchmark.to_excel(writer, sheet_name="company_range_benchmark", index=False)
        agency_ranges.to_excel(writer, sheet_name="agency_ranges", index=False)
        range_policy.to_excel(writer, sheet_name="range_calibration", index=False)
        range_summary.to_excel(writer, sheet_name="range_summary", index=False)
        simulation_frame.to_excel(writer, sheet_name="agency_predictions", index=False)
        actual_ratings_frame.to_excel(writer, sheet_name="actual_rating_discovery", index=False)
        agency_summary.to_excel(writer, sheet_name="agency_summary", index=False)
        deduped_companies.to_excel(writer, sheet_name="company_master", index=False)
    single_sheet_path = reports_dir / "external_company_rating_single_sheet.xlsx"
    _write_single_sheet_underwriting_workbook(range_benchmark, single_sheet_path, sheet_name="underwriting_view")

    return {
        "manifest": manifest_path,
        "company_master": company_master_path,
        "actual_rating_discovery": actual_ratings_path,
        "company_rating_benchmark": benchmark_csv_path,
        "agency_benchmark_summary": agency_summary_path,
        "listed_status": listed_status_path,
        "agency_strength": agency_strength_path,
        "agency_range_calibration": range_policy_path,
        "agency_wise_rating_ranges": agency_ranges_path,
        "company_rating_range_benchmark": range_benchmark_path,
        "agency_range_benchmark_summary": range_summary_path,
        "single_sheet_benchmark_workbook": single_sheet_path,
        "benchmark_workbook": workbook_path,
        **financial_outputs,
        **simulation_outputs,
    }


def build_live_company_simulation(
    *,
    profile: CompanyCreditProfile,
    model_base_dir: Path = Path("outputs/agri_food_other_products/simulation_model"),
    range_policy_path: Path | None = None,
) -> dict[str, Any]:
    metrics_path = model_base_dir / "models" / "agency_model_metrics.csv"
    agency_strength = _build_agency_strength_frame(metrics_path)
    range_policy = _load_or_build_live_range_policy(range_policy_path, agency_strength)
    companies_frame = pd.DataFrame([_profile_to_company_row(profile)])
    actual_frame = pd.DataFrame([_profile_to_actual_rating_row(profile)])
    simulation_frame = _score_live_company_predictions(profile=profile, metrics_path=metrics_path)
    if simulation_frame.empty:
        return {
            "required_flag": profile.simulation_required_flag,
            "status": "Simulation unavailable",
            "simulated_rating": None,
            "rating_range": None,
            "confidence_label": "low",
            "method_used": "agency_models_unavailable",
            "notes": ["Agency model artifacts were not available for this company."],
            "agency_ranges": [],
        }

    agency_ranges = _build_agency_range_frame(
        companies_frame=companies_frame,
        actual_ratings_frame=actual_frame,
        simulation_frame=simulation_frame,
        range_policy_frame=range_policy,
        agency_strength_frame=agency_strength,
    )
    company_selection = _build_company_range_benchmark(agency_ranges).iloc[0].to_dict()
    return {
        "required_flag": profile.simulation_required_flag,
        "status": "Simulation completed" if profile.simulation_required_flag else "External rating available; simulation computed for comparison",
        "simulated_rating": company_selection.get("simulated_rating"),
        "rating_range": company_selection.get("published_range"),
        "confidence_label": company_selection.get("range_confidence_label"),
        "range_confidence_score": company_selection.get("range_confidence_score"),
        "range_usability_label": company_selection.get("range_usability_label"),
        "simulation_actionability": company_selection.get("simulation_actionability"),
        "ca_review_priority": company_selection.get("ca_review_priority"),
        "selected_agency_reason": company_selection.get("selected_agency_reason"),
        "selected_agency": company_selection.get("simulated_rating_agency"),
        "history_available_flag": company_selection.get("history_available_flag"),
        "rating_history_summary": company_selection.get("rating_history_summary"),
        "manual_review_required_flag": company_selection.get("manual_review_required_flag"),
        "manual_review_reason": company_selection.get("manual_review_reason"),
        "internal_calibrated_range": company_selection.get("calibrated_range"),
        "method_used": "agency_specific_range_selection",
        "notes": _build_live_simulation_notes(company_selection),
        "agency_ranges": agency_ranges.to_dict(orient="records"),
    }


def _build_company_master(
    *,
    summary_frame: pd.DataFrame,
    latest_features_frame: pd.DataFrame,
    financial_parameters_frame: pd.DataFrame,
) -> pd.DataFrame:
    working = summary_frame.copy()
    parameters = financial_parameters_frame.copy()
    if not parameters.empty:
        parameters["period"] = pd.to_datetime(parameters["period"], errors="coerce")
        parameters = parameters.sort_values(["company_id", "period"]).groupby("company_id", as_index=False).tail(1)
        parameters = parameters.rename(
            columns={
                "credit_rated_flag": "dataset_credit_rated_flag",
                "latest_ratings_text": "dataset_latest_ratings_text",
                "total_open_charges": "dataset_total_open_charges",
            }
        )
        working = working.merge(
            parameters[
                [
                    "company_id",
                    "dataset_credit_rated_flag",
                    "dataset_latest_ratings_text",
                    "dataset_total_open_charges",
                    "whether_exporter",
                ]
            ],
            on="company_id",
            how="left",
        )

    if not latest_features_frame.empty:
        latest_features = latest_features_frame[
            [
                "company_id",
                "period",
                "period_date",
                "revenue_growth_pct",
                "roe_pct",
                "roce_pct",
                "current_ratio",
                "cfo_to_debt",
                "asset_turnover",
            ]
        ].copy()
        working = working.merge(latest_features, on="company_id", how="left")

    working["dedupe_key"] = working["company_id"].fillna(working["company_name"]).astype(str)
    if "period_date" in working.columns:
        working["period_date"] = pd.to_datetime(working["period_date"], errors="coerce")
    working = working.sort_values(
        ["dedupe_key", "critical_feature_coverage_pct", "period_date", "revenue_crore"],
        ascending=[True, False, False, False],
        na_position="last",
    )
    working = working.groupby("dedupe_key", as_index=False).head(1).copy()
    return working.drop(columns=["dedupe_key"])


def _discover_actual_ratings(
    *,
    companies_frame: pd.DataFrame,
    output_path: Path,
    force_refresh: bool,
    rating_validation_mode: str,
) -> pd.DataFrame:
    config = replace(CreditIntelConfig(), request_delay_seconds=0.5)
    config.ensure_directories()
    repository = ExistingRatingRepository(Path("outputs/agri_food_other_products/credit_rating_history.csv"))
    service = RatingDiscoveryService(config, repository)

    existing_frame = pd.read_csv(output_path) if output_path.exists() and not force_refresh else pd.DataFrame()
    if not existing_frame.empty and "company_id" in existing_frame.columns:
        existing_lookup = {str(row["company_id"]): row for row in existing_frame.to_dict(orient="records")}
    else:
        existing_lookup = {}

    rows: list[dict[str, Any]] = []
    for row in companies_frame.to_dict(orient="records"):
        company_id = str(row.get("company_id") or row.get("company_name"))
        if company_id in existing_lookup:
            rows.append(existing_lookup[company_id])
            continue

        company_name = str(row.get("company_name") or "").strip()
        dataset_rating_text = _string(row.get("dataset_latest_ratings_text"))
        LOGGER.info("Discovering latest rating for %s", company_name)
        online_probe_performed = False
        allow_dataset_fallback = rating_validation_mode != "cra_only"
        if company_name:
            online_probe_performed = True
            try:
                insight = service.discover(
                    company_name,
                    dataset_rating_text=dataset_rating_text,
                    mode=rating_validation_mode,
                    use_repository=False,
                    allow_dataset_fallback=allow_dataset_fallback,
                )
            except Exception as exc:  # noqa: BLE001
                LOGGER.warning("Rating discovery failed for %s and will be marked unavailable: %s", company_name, exc)
                insight = RatingInsight(notes=[f"CRA discovery error: {exc}"])
        else:
            insight = RatingInsight(notes=["Missing company name; CRA validation skipped."])
        source = _history_source(insight.history, insight.notes)
        hint_agency_key, hint_rating, hint_rank = _parse_dataset_hint(dataset_rating_text)

        actual_agency = insight.agency_name
        actual_rating = insight.rating
        agency_key = _normalize_agency(insight.agency_name or dataset_rating_text)
        normalization = normalize_rating_label(agency_key or "crisil", insight.rating or dataset_rating_text or "")

        if allow_dataset_fallback and source == "dataset_hint" and hint_rating:
            actual_agency = actual_agency or _pretty_agency_name(hint_agency_key)
            agency_key = hint_agency_key or agency_key
            actual_rating = hint_rating
            normalization = normalize_rating_label(agency_key or "crisil", dataset_rating_text or hint_rating)
            normalization.rating_rank_numeric = hint_rank

        rows.append(
            {
                "company_id": company_id,
                "company_name": company_name,
                "actual_rating_available_flag": bool(actual_rating),
                "online_probe_performed": online_probe_performed,
                "actual_rating": actual_rating,
                "actual_rating_date": insight.rating_date,
                "actual_rating_agency": actual_agency,
                "actual_rating_agency_key": agency_key,
                "actual_rating_action": insight.rating_action,
                "actual_outlook": insight.outlook,
                "actual_rating_source_url": _history_source_url(insight.history),
                "actual_rating_source": source,
                "actual_rating_notes": " | ".join(insight.notes or []),
                "actual_rating_history_count": len(insight.history or []),
                "actual_rating_history_json": json.dumps([entry.model_dump() for entry in insight.history], ensure_ascii=True),
                "actual_rating_history_summary": " | ".join(
                    filter(
                        None,
                        [
                            " | ".join(filter(None, [entry.rating_date, entry.agency_name, entry.rating]))
                            for entry in (insight.history or [])[:10]
                        ],
                    )
                ),
                "rating_validation_mode": rating_validation_mode,
                "actual_rating_rank": normalization.rating_rank_numeric,
                "actual_normalized_rating": normalization.normalized_label,
                "dataset_latest_ratings_text": dataset_rating_text,
            }
        )

        pd.DataFrame(rows).to_csv(output_path, index=False)

    frame = pd.DataFrame(rows)
    frame.to_csv(output_path, index=False)
    return frame


def _write_single_sheet_underwriting_workbook(frame: pd.DataFrame, output_path: Path, *, sheet_name: str) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        frame.to_excel(writer, sheet_name=sheet_name, index=False)


def _normalize_merge_keys(frame: pd.DataFrame, keys: list[str]) -> pd.DataFrame:
    normalized = frame.copy()
    for key in keys:
        if key in normalized.columns:
            normalized[key] = normalized[key].fillna("").astype(str)
    return normalized


def _discover_listed_status(
    *,
    companies_frame: pd.DataFrame,
    output_path: Path,
    force_refresh: bool,
) -> pd.DataFrame:
    config = AppConfig(headless=True)
    existing_frame = pd.read_csv(output_path) if output_path.exists() and not force_refresh else pd.DataFrame()
    if not existing_frame.empty and "company_id" in existing_frame.columns:
        existing_lookup = {str(row["company_id"]): row for row in existing_frame.to_dict(orient="records")}
    else:
        existing_lookup = {}

    rows: list[dict[str, Any]] = []
    with httpx.Client(headers={"User-Agent": "Mozilla/5.0"}, timeout=20.0, follow_redirects=True) as client:
        for row_index, row in enumerate(companies_frame.to_dict(orient="records")):
            company_id = str(row.get("company_id") or row.get("company_name"))
            if company_id in existing_lookup:
                rows.append(existing_lookup[company_id])
                continue

            company_name = _string(row.get("company_name")) or ""
            corporate = CorporateRecord(
                row_index=row_index,
                company_id=company_id or build_company_id(company_name, None, None, row_index),
                company_name=company_name,
                search_name=company_name,
                normalized_name=normalize_company_name(company_name),
                normalized_tokens=company_name_tokens(company_name),
                nse_code=None,
                bse_code=None,
                isin_code=None,
                industry_group=_string(row.get("industry_group")),
                industry=_string(row.get("sub_industry")),
            )

            try:
                response = client.get(f"{config.base_url}api/company/search/", params={"q": company_name})
                response.raise_for_status()
                payload = response.json()
                if not isinstance(payload, list):
                    payload = []
            except Exception as exc:  # noqa: BLE001
                LOGGER.warning("Screener listed-status lookup failed for %s: %s", company_name, exc)
                payload = []

            candidates = [
                candidate_from_payload(item, rank=index + 1, base_url=config.base_url)
                for index, item in enumerate(payload[: config.max_candidates])
                if isinstance(item, dict)
            ]
            decision = choose_best_match(
                corporate,
                candidates,
                auto_threshold=max(config.similarity_auto_threshold, 0.9),
                ambiguity_gap_threshold=config.ambiguity_gap_threshold,
            )

            if decision.status == "matched" and decision.matched_candidate is not None:
                listed_status = "listed"
                listed_flag: bool | None = True
                screener_url = decision.matched_candidate.url
                confidence = decision.confidence
                notes = decision.reason
            elif candidates:
                listed_status = "unlisted"
                listed_flag = False
                screener_url = None
                confidence = decision.confidence
                notes = f"Screener search returned candidates, but none matched confidently. {decision.reason}"
            else:
                listed_status = "unlisted"
                listed_flag = False
                screener_url = None
                confidence = 0.0
                notes = "No Screener company candidate was returned for this company name."

            rows.append(
                {
                    "company_id": company_id,
                    "company_name": company_name,
                    "listed_status": listed_status,
                    "listed_flag": listed_flag,
                    "listed_confidence": confidence,
                    "screener_url": screener_url,
                    "listed_status_notes": notes,
                }
            )
            if len(rows) % 25 == 0:
                pd.DataFrame(rows).to_csv(output_path, index=False)
            time.sleep(0.35)

    frame = pd.DataFrame(rows)
    frame.to_csv(output_path, index=False)
    return frame


def _build_benchmark_frame(
    *,
    companies_frame: pd.DataFrame,
    actual_ratings_frame: pd.DataFrame,
    simulation_frame: pd.DataFrame,
    model_metrics_path: Path,
) -> pd.DataFrame:
    model_metrics = pd.read_csv(model_metrics_path) if model_metrics_path.exists() else pd.DataFrame()
    strong_agencies = set(
        model_metrics.loc[model_metrics.get("training_rows", 0) >= 20, "agency_name"].astype(str).tolist()
    )
    if not strong_agencies:
        strong_agencies = set(simulation_frame["agency"].astype(str).unique()) if not simulation_frame.empty else set()

    prediction_lookup = {
        (str(row.get("company_id")), str(row.get("agency"))): row
        for row in simulation_frame.to_dict(orient="records")
    }

    best_prediction_lookup: dict[str, dict[str, Any]] = {}
    for company_id, group in simulation_frame.groupby("company_id", dropna=False):
        filtered = group[group["agency"].isin(strong_agencies)].copy()
        if filtered.empty:
            filtered = group.copy()
        filtered = filtered.sort_values(["confidence", "top_probability"], ascending=False, na_position="last")
        best_prediction_lookup[str(company_id)] = filtered.iloc[0].to_dict()

    benchmark_rows: list[dict[str, Any]] = []
    merged = companies_frame.merge(actual_ratings_frame, on=["company_id", "company_name"], how="left")

    for row in merged.to_dict(orient="records"):
        company_id = str(row.get("company_id"))
        actual_agency_key = _normalize_agency(row.get("actual_rating_agency_key") or row.get("actual_rating_agency"))
        matched_prediction = prediction_lookup.get((company_id, actual_agency_key)) if actual_agency_key else None
        best_prediction = best_prediction_lookup.get(company_id)
        chosen_prediction = matched_prediction or best_prediction or {}

        predicted_rating = _string(chosen_prediction.get("predicted_rating"))
        predicted_agency = _string(chosen_prediction.get("agency"))
        predicted_rank = _rank_from_rating(predicted_rating)
        actual_rank = _to_float(row.get("actual_rating_rank"))
        deviation = abs(predicted_rank - actual_rank) if predicted_rank is not None and actual_rank is not None else None

        benchmark_rows.append(
            {
                "company_id": company_id,
                "company_name": row.get("company_name"),
                "industry_group": row.get("industry_group"),
                "sub_industry": row.get("sub_industry"),
                "revenue_crore": row.get("revenue_crore"),
                "ebitda_margin_pct": row.get("ebitda_margin_pct"),
                "debt_to_equity": row.get("debt_to_equity"),
                "interest_coverage": row.get("interest_coverage"),
                "simulation_readiness": row.get("simulation_readiness"),
                "critical_feature_coverage_pct": row.get("critical_feature_coverage_pct"),
                "dataset_latest_ratings_text": row.get("dataset_latest_ratings_text"),
                "actual_rating_available_flag": row.get("actual_rating_available_flag"),
                "actual_rating_agency": row.get("actual_rating_agency"),
                "actual_rating_agency_key": actual_agency_key,
                "actual_rating": row.get("actual_normalized_rating") or row.get("actual_rating"),
                "actual_rating_date": row.get("actual_rating_date"),
                "actual_outlook": row.get("actual_outlook"),
                "actual_rating_source": row.get("actual_rating_source"),
                "actual_rating_source_url": row.get("actual_rating_source_url"),
                "actual_rating_history_count": row.get("actual_rating_history_count"),
                "actual_rating_history_summary": row.get("actual_rating_history_summary"),
                "rating_validation_mode": row.get("rating_validation_mode"),
                "simulated_rating_agency": predicted_agency,
                "simulated_rating": predicted_rating,
                "simulation_range": chosen_prediction.get("rating_range"),
                "simulation_confidence": chosen_prediction.get("confidence"),
                "simulation_confidence_label": chosen_prediction.get("confidence_label"),
                "simulation_top_probability": chosen_prediction.get("top_probability"),
                "matched_actual_agency_prediction_flag": bool(matched_prediction),
                "exact_match": bool(deviation == 0) if deviation is not None else None,
                "within_1_notch": bool(deviation is not None and deviation <= 1) if deviation is not None else None,
                "notch_deviation": deviation,
                "probability_distribution_json": chosen_prediction.get("probability_distribution_json"),
                "key_features": chosen_prediction.get("key_features"),
                "prediction_status": chosen_prediction.get("prediction_status"),
            }
        )

    benchmark_frame = pd.DataFrame(benchmark_rows)
    benchmark_frame = benchmark_frame.sort_values(
        ["actual_rating_available_flag", "company_name"],
        ascending=[False, True],
        na_position="last",
    )
    return benchmark_frame


def _calibrate_agency_range_policy(benchmark_frame: pd.DataFrame, *, target_coverage: float) -> pd.DataFrame:
    rated = benchmark_frame[
        benchmark_frame["actual_rating_available_flag"].astype(str).str.lower().isin(["true", "1"])
        & benchmark_frame["matched_actual_agency_prediction_flag"].fillna(False)
        & benchmark_frame["simulated_rating"].notna()
        & benchmark_frame["actual_rating"].notna()
    ].copy()
    rows: list[dict[str, Any]] = []
    max_halfwidth = len(LONG_TERM_ORDER) - 1
    for agency, group in rated.groupby("actual_rating_agency_key", dropna=False):
        selected_halfwidth = DEFAULT_RANGE_FALLBACK_HALFWIDTH
        selected_coverage = 0.0
        target_met = False
        for halfwidth in range(max_halfwidth + 1):
            coverage = _coverage_for_halfwidth(group, halfwidth)
            if coverage >= target_coverage:
                selected_halfwidth = halfwidth
                selected_coverage = coverage
                target_met = True
                break
            if coverage >= selected_coverage:
                selected_halfwidth = halfwidth
                selected_coverage = coverage
        rows.append(
            {
                "agency": agency,
                "companies_compared": int(len(group)),
                "target_coverage": target_coverage,
                "selected_halfwidth_notches": selected_halfwidth,
                "selected_range_width_notches": int((selected_halfwidth * 2) + 1),
                "coverage_at_selected_range": round(selected_coverage, 4),
                "target_met": target_met,
                "policy_note": (
                    "Smallest contiguous range meeting target coverage."
                    if target_met
                    else "Target coverage not reached; using the widest observed practical range."
                ),
            }
        )
    return pd.DataFrame(rows).sort_values("agency")


def _build_agency_range_frame(
    *,
    companies_frame: pd.DataFrame,
    actual_ratings_frame: pd.DataFrame,
    simulation_frame: pd.DataFrame,
    range_policy_frame: pd.DataFrame,
    agency_strength_frame: pd.DataFrame,
) -> pd.DataFrame:
    companies = companies_frame.copy()
    actual = actual_ratings_frame.copy()
    merged = companies.merge(actual, on=["company_id", "company_name"], how="left")
    company_lookup = {
        str(row["company_id"]): row
        for row in merged.to_dict(orient="records")
    }
    policy_lookup = {
        str(row["agency"]): int(row["selected_halfwidth_notches"])
        for row in range_policy_frame.to_dict(orient="records")
    }
    strength_lookup = {
        str(row["agency"]): row
        for row in agency_strength_frame.to_dict(orient="records")
    }
    rows: list[dict[str, Any]] = []
    for sim_row in simulation_frame.to_dict(orient="records"):
        company_id = str(sim_row.get("company_id"))
        company = company_lookup.get(company_id, {})
        agency = _string(sim_row.get("agency"))
        predicted_rating = _string(sim_row.get("predicted_rating"))
        halfwidth = policy_lookup.get(agency or "", DEFAULT_RANGE_FALLBACK_HALFWIDTH)
        width_notches = int((halfwidth * 2) + 1)
        lower_label, upper_label, lower_rank, upper_rank = _range_bounds(predicted_rating, halfwidth)
        probability_map = _parse_probability_map(sim_row.get("probability_distribution_json"))
        calibrated_range_mass = _range_probability_mass(probability_map, lower_rank, upper_rank)
        critical_coverage = _to_float(company.get("critical_feature_coverage_pct"))
        data_completeness = _to_float(sim_row.get("data_completeness"))
        feature_coverage = _to_float(sim_row.get("feature_coverage"))
        history_available = bool(_to_float(company.get("actual_rating_history_count")) or _string(company.get("actual_rating")))
        history_summary = _build_rating_history_summary(
            agency_name=_string(company.get("actual_rating_agency")),
            rating=_string(company.get("actual_normalized_rating") or company.get("actual_rating")),
            rating_date=_string(company.get("actual_rating_date")),
            dataset_latest_ratings_text=_string(company.get("actual_rating_history_summary") or company.get("dataset_latest_ratings_text")),
        )
        strength_row = strength_lookup.get(agency or "", {})
        agency_strength_score = _to_float(strength_row.get("agency_strength_score")) or 0.35
        calibrated_range_confidence = _range_confidence_score(
            simulation_confidence=_to_float(sim_row.get("confidence")) or 0.0,
            range_probability_mass=calibrated_range_mass,
            critical_feature_coverage_pct=critical_coverage,
            data_completeness=data_completeness,
            feature_coverage=feature_coverage,
            history_available=history_available,
            range_width_notches=width_notches,
            agency_strength_score=agency_strength_score,
        )
        published_range = _choose_published_range(
            predicted_rating=predicted_rating,
            probability_map=probability_map,
            simulation_confidence=_to_float(sim_row.get("confidence")) or 0.0,
            top_probability=_to_float(sim_row.get("top_probability")) or 0.0,
            critical_feature_coverage_pct=critical_coverage,
            data_completeness=data_completeness,
            feature_coverage=feature_coverage,
            history_available=history_available,
            agency_strength_score=agency_strength_score,
        )
        range_confidence = float(published_range["range_confidence_score"])
        range_usability = str(published_range["range_usability_label"])
        selection_priority = _selection_priority_score(
            range_confidence_score=range_confidence,
            width_trust=_range_width_trust(int(published_range["published_range_width_notches"] or width_notches)),
            agency_strength_score=agency_strength_score,
            history_available=history_available,
        )
        actual_agency = _normalize_agency(company.get("actual_rating_agency_key") or company.get("actual_rating_agency"))
        actual_rank = _to_float(company.get("actual_rating_rank"))
        range_hit = None
        calibrated_range_hit = None
        if actual_agency and agency and actual_agency == agency and actual_rank is not None and lower_rank is not None and upper_rank is not None:
            calibrated_range_hit = bool(lower_rank <= actual_rank <= upper_rank)
        published_lower_rank = published_range.get("published_range_lower_rank")
        published_upper_rank = published_range.get("published_range_upper_rank")
        if (
            actual_agency
            and agency
            and actual_agency == agency
            and actual_rank is not None
            and published_lower_rank is not None
            and published_upper_rank is not None
        ):
            range_hit = bool(published_lower_rank <= actual_rank <= published_upper_rank)
        rows.append(
            {
                "company_id": company_id,
                "company_name": company.get("company_name") or sim_row.get("company_name"),
                "listed_status": company.get("listed_status"),
                "listed_flag": company.get("listed_flag"),
                "screener_url": company.get("screener_url"),
                "industry_group": company.get("industry_group"),
                "sub_industry": company.get("sub_industry"),
                "revenue_crore": company.get("revenue_crore"),
                "ebitda_margin_pct": company.get("ebitda_margin_pct"),
                "debt_to_equity": company.get("debt_to_equity"),
                "interest_coverage": company.get("interest_coverage"),
                "simulation_readiness": company.get("simulation_readiness"),
                "critical_feature_coverage_pct": critical_coverage,
                "dataset_latest_ratings_text": company.get("dataset_latest_ratings_text"),
                "history_available_flag": history_available,
                "rating_history_summary": history_summary,
                "actual_rating_available_flag": company.get("actual_rating_available_flag"),
                "actual_rating_agency": company.get("actual_rating_agency"),
                "actual_rating_agency_key": actual_agency,
                "actual_rating": company.get("actual_normalized_rating") or company.get("actual_rating"),
                "actual_rating_date": company.get("actual_rating_date"),
                "actual_rating_source": company.get("actual_rating_source"),
                "actual_rating_source_url": company.get("actual_rating_source_url"),
                "actual_rating_history_count": company.get("actual_rating_history_count"),
                "actual_rating_history_summary": company.get("actual_rating_history_summary"),
                "rating_validation_mode": company.get("rating_validation_mode"),
                "simulated_rating_agency": agency,
                "simulated_rating": predicted_rating,
                "simulation_range": sim_row.get("rating_range"),
                "calibrated_range_target_coverage": DEFAULT_RANGE_TARGET,
                "calibrated_range_halfwidth_notches": halfwidth,
                "calibrated_range_width_notches": width_notches,
                "calibrated_range": _format_range(lower_label, upper_label),
                "calibrated_range_lower": lower_label,
                "calibrated_range_upper": upper_label,
                "calibrated_range_probability_mass": round(calibrated_range_mass, 4),
                "calibrated_range_confidence_score": round(calibrated_range_confidence, 4),
                "published_range": published_range["published_range"],
                "published_range_lower": published_range["published_range_lower"],
                "published_range_upper": published_range["published_range_upper"],
                "published_range_halfwidth_notches": published_range["published_range_halfwidth_notches"],
                "published_range_width_notches": published_range["published_range_width_notches"],
                "published_range_probability_mass": round(float(published_range["range_probability_mass"]), 4),
                "published_range_confidence_score": round(float(published_range["range_confidence_score"]), 4),
                "manual_review_required_flag": bool(published_range["manual_review_required_flag"]),
                "manual_review_reason": published_range["manual_review_reason"],
                "agency_strength_score": round(agency_strength_score, 4),
                "range_confidence_score": round(range_confidence, 4),
                "range_confidence_label": _confidence_label(range_confidence),
                "range_usability_label": range_usability,
                "directional_only_flag": bool(published_range["manual_review_required_flag"]),
                "selection_priority_score": round(selection_priority, 4),
                "simulation_actionability": _simulation_actionability_label(range_usability, range_confidence, history_available),
                "ca_review_priority": _ca_review_priority_label(range_usability, range_confidence, history_available),
                "range_hit_against_actual": range_hit,
                "calibrated_range_hit_against_actual": calibrated_range_hit,
                "simulation_confidence": sim_row.get("confidence"),
                "simulation_confidence_label": sim_row.get("confidence_label"),
                "simulation_top_probability": sim_row.get("top_probability"),
                "probability_distribution_json": sim_row.get("probability_distribution_json"),
                "key_features": sim_row.get("key_features"),
                "prediction_status": sim_row.get("prediction_status"),
            }
        )
    frame = pd.DataFrame(rows)
    return frame.sort_values(["company_name", "simulated_rating_agency"])


def _load_or_build_live_range_policy(range_policy_path: Path | None, agency_strength_frame: pd.DataFrame) -> pd.DataFrame:
    if range_policy_path and range_policy_path.exists():
        frame = pd.read_csv(range_policy_path)
        if not frame.empty and "agency" in frame.columns and "selected_halfwidth_notches" in frame.columns:
            return frame
    rows = []
    for agency in agency_strength_frame["agency"].tolist():
        rows.append(
            {
                "agency": agency,
                "companies_compared": None,
                "target_coverage": DEFAULT_RANGE_TARGET,
                "selected_halfwidth_notches": DEFAULT_AGENCY_RANGE_HALFWIDTHS.get(str(agency), DEFAULT_RANGE_FALLBACK_HALFWIDTH),
                "selected_range_width_notches": (DEFAULT_AGENCY_RANGE_HALFWIDTHS.get(str(agency), DEFAULT_RANGE_FALLBACK_HALFWIDTH) * 2) + 1,
                "coverage_at_selected_range": None,
                "target_met": None,
                "policy_note": "Loaded from default live calibration policy.",
            }
        )
    return pd.DataFrame(rows)


def _build_company_range_benchmark(agency_ranges: pd.DataFrame) -> pd.DataFrame:
    strong_agencies = {"crisil", "care", "icra", "india_ratings", "infomerics"}
    selected_rows: list[dict[str, Any]] = []
    for company_id, group in agency_ranges.groupby("company_id", dropna=False):
        group = group.copy()
        actual_rating_available = group["actual_rating_available_flag"].astype(str).str.lower().isin(["true", "1"]).any()
        actual_agency = _normalize_agency(group["actual_rating_agency_key"].dropna().iloc[0] if group["actual_rating_agency_key"].notna().any() else None)
        chosen = pd.DataFrame()
        selection_reason = "best_trustworthy_agency"
        if actual_rating_available and actual_agency:
            chosen = group[group["simulated_rating_agency"] == actual_agency]
            selection_reason = "matched_historical_agency"
        if chosen.empty:
            filtered = group[group["simulated_rating_agency"].isin(strong_agencies)].copy()
            if filtered.empty:
                filtered = group.copy()
            chosen = filtered.sort_values(
                ["manual_review_required_flag", "selection_priority_score", "range_confidence_score", "simulation_confidence", "published_range_probability_mass"],
                ascending=[True, False, False, False, False],
                na_position="last",
            ).head(1)
        row = chosen.iloc[0].to_dict()
        row["selected_agency_reason"] = selection_reason
        selected_rows.append(row)
    return pd.DataFrame(selected_rows).sort_values(["history_available_flag", "company_name"], ascending=[False, True])


def _build_range_summary(agency_ranges: pd.DataFrame) -> pd.DataFrame:
    rated = agency_ranges[
        agency_ranges["actual_rating_available_flag"].astype(str).str.lower().isin(["true", "1"])
        & agency_ranges["range_hit_against_actual"].notna()
    ].copy()
    rows: list[dict[str, Any]] = []
    for agency, group in rated.groupby("simulated_rating_agency", dropna=False):
        publishable = group[group["range_hit_against_actual"].notna()].copy()
        rows.append(
            {
                "agency": agency,
                "companies_compared": int(len(group)),
                "publishable_share": round(float(group["manual_review_required_flag"].fillna(False).eq(False).mean()), 4),
                "range_hit_accuracy": round(float(pd.to_numeric(publishable["range_hit_against_actual"], errors="coerce").mean()), 4) if not publishable.empty else None,
                "avg_range_confidence_score": round(float(pd.to_numeric(group["range_confidence_score"], errors="coerce").mean()), 4),
                "avg_range_probability_mass": round(float(pd.to_numeric(group["published_range_probability_mass"], errors="coerce").mean()), 4),
                "avg_published_range_width_notches": round(float(pd.to_numeric(group["published_range_width_notches"], errors="coerce").mean()), 2),
                "manual_review_share": round(float(pd.to_numeric(group["manual_review_required_flag"], errors="coerce").mean()), 4),
            }
        )
    if not rated.empty:
        publishable = rated[rated["range_hit_against_actual"].notna()].copy()
        rows.append(
            {
                "agency": "overall",
                "companies_compared": int(len(rated)),
                "publishable_share": round(float(rated["manual_review_required_flag"].fillna(False).eq(False).mean()), 4),
                "range_hit_accuracy": round(float(pd.to_numeric(publishable["range_hit_against_actual"], errors="coerce").mean()), 4) if not publishable.empty else None,
                "avg_range_confidence_score": round(float(pd.to_numeric(rated["range_confidence_score"], errors="coerce").mean()), 4),
                "avg_range_probability_mass": round(float(pd.to_numeric(rated["published_range_probability_mass"], errors="coerce").mean()), 4),
                "avg_published_range_width_notches": round(float(pd.to_numeric(rated["published_range_width_notches"], errors="coerce").mean()), 2),
                "manual_review_share": round(float(pd.to_numeric(rated["manual_review_required_flag"], errors="coerce").mean()), 4),
            }
        )
    return pd.DataFrame(rows).sort_values("agency")


def _score_live_company_predictions(*, profile: CompanyCreditProfile, metrics_path: Path) -> pd.DataFrame:
    if not metrics_path.exists():
        return pd.DataFrame()
    metrics = pd.read_csv(metrics_path)
    rows: list[dict[str, Any]] = []
    base_record = _profile_to_live_feature_row(profile)
    for metric in metrics.to_dict(orient="records"):
        if _string(metric.get("status")) != "trained":
            continue
        agency = _string(metric.get("agency_name"))
        model_path = Path(str(metric.get("model_path")))
        if not agency or not model_path.exists():
            continue
        artifact = load_model_artifact(model_path)
        record = dict(base_record)
        _inject_prior_rating_features(record, profile, agency)
        scored = _score_prediction_frame(
            frame=pd.DataFrame([record]),
            artifact=artifact,
            population_type="simulation",
        )
        if scored:
            rows.extend(scored)
    return pd.DataFrame(rows)


def _build_agency_strength_frame(model_metrics_path: Path) -> pd.DataFrame:
    metrics = pd.read_csv(model_metrics_path) if model_metrics_path.exists() else pd.DataFrame()
    if metrics.empty:
        return pd.DataFrame(columns=["agency", "agency_strength_score", "training_rows", "within_one_notch_accuracy", "exact_match_accuracy"])
    max_training_rows = max(float(pd.to_numeric(metrics["training_rows"], errors="coerce").max() or 1.0), 1.0)
    rows: list[dict[str, Any]] = []
    for row in metrics.to_dict(orient="records"):
        agency = _string(row.get("agency_name"))
        if not agency:
            continue
        training_rows = _to_float(row.get("training_rows")) or 0.0
        within_one = _to_float(row.get("within_one_notch_accuracy")) or 0.0
        exact = _to_float(row.get("exact_match_accuracy")) or 0.0
        status_score = 1.0 if _string(row.get("status")) == "trained" else 0.0
        training_score = min(training_rows / max_training_rows, 1.0)
        strength = (
            (within_one * 0.4)
            + (exact * 0.2)
            + (training_score * 0.3)
            + (status_score * 0.1)
        )
        rows.append(
            {
                "agency": agency,
                "training_rows": training_rows,
                "within_one_notch_accuracy": within_one,
                "exact_match_accuracy": exact,
                "agency_strength_score": round(min(max(strength, 0.0), 1.0), 4),
            }
        )
    return pd.DataFrame(rows).sort_values("agency")


def _profile_to_company_row(profile: CompanyCreditProfile) -> dict[str, Any]:
    matched = profile.matched_company
    summary = profile.financial_summary
    return {
        "company_id": profile.company_id or build_company_id(profile.company_name, None, None, 0),
        "company_name": profile.company_name,
        "listed_status": profile.listed_status,
        "listed_flag": profile.listed_status == "listed",
        "screener_url": profile.listed_insight.screener_url if profile.listed_insight else None,
        "industry_group": matched.sector if matched else profile.industry,
        "sub_industry": matched.business_type if matched else profile.industry,
        "revenue_crore": summary.revenue_crore,
        "ebitda_margin_pct": summary.ebitda_margin_pct,
        "debt_to_equity": summary.debt_to_equity,
        "interest_coverage": summary.interest_coverage,
        "simulation_readiness": "high" if _live_core_financial_coverage_pct(summary) >= 75 else ("medium" if _live_core_financial_coverage_pct(summary) >= 50 else "low"),
        "critical_feature_coverage_pct": _live_core_financial_coverage_pct(summary),
        "dataset_latest_ratings_text": matched.latest_ratings_text if matched else None,
    }


def _profile_to_actual_rating_row(profile: CompanyCreditProfile) -> dict[str, Any]:
    history = profile.rating_insight.history or []
    latest = history[0] if history else RatingHistoryEntry(
        agency_name=profile.rating_insight.agency_name,
        rating=profile.rating_insight.rating,
        rating_date=profile.rating_insight.rating_date,
        source=profile.rating_insight.rating_status,
    )
    actual_rating = _string(latest.rating or profile.rating_insight.rating)
    actual_agency = _string(latest.agency_name or profile.rating_insight.agency_name)
    actual_agency_key = _normalize_agency(actual_agency)
    normalization = normalize_rating_label(actual_agency_key or "crisil", actual_rating or "")
    return {
        "company_id": profile.company_id or build_company_id(profile.company_name, None, None, 0),
        "company_name": profile.company_name,
        "actual_rating_available_flag": bool(actual_rating),
        "actual_rating_agency": actual_agency,
        "actual_rating_agency_key": actual_agency_key,
        "actual_rating": actual_rating,
        "actual_normalized_rating": normalization.normalized_label,
        "actual_rating_rank": normalization.rating_rank_numeric,
        "actual_rating_date": latest.rating_date or profile.rating_insight.rating_date,
        "actual_rating_source": latest.source or profile.rating_insight.rating_status,
        "actual_rating_source_url": latest.source_url,
    }


def _profile_to_live_feature_row(profile: CompanyCreditProfile) -> dict[str, Any]:
    matched = profile.matched_company
    summary = profile.financial_summary
    working_capital_days = summary.working_capital_days
    if working_capital_days is None and summary.receivables_days is not None and summary.inventory_days is not None:
        working_capital_days = round(float(summary.receivables_days) + float(summary.inventory_days), 4)
    row: dict[str, Any] = {
        "company_id": profile.company_id or build_company_id(profile.company_name, None, None, 0),
        "company_name": profile.company_name,
        "sub_industry": (matched.business_type if matched and matched.business_type else profile.industry) or "Unknown",
        "period": summary.statement_period,
        "matched_financial_period": summary.statement_period,
        "liquidity_label": "Unknown",
        "standalone_or_consolidated": (matched.standalone_or_consolidated if matched else None) or "Unknown",
        "revenue_crore": summary.revenue_crore,
        "ebitda_margin_pct": summary.ebitda_margin_pct,
        "pat_margin_pct": summary.pat_margin_pct,
        "debt_to_equity": summary.debt_to_equity,
        "interest_coverage": summary.interest_coverage,
        "working_capital_days": working_capital_days,
        "receivables_days": summary.receivables_days,
        "inventory_days": summary.inventory_days,
        "networth_crore": summary.networth_crore or (matched.networth_crore if matched else None),
        "total_borrowings_crore": summary.total_borrowings_crore or (matched.total_borrowings_crore if matched else None),
        "current_ratio": matched.current_ratio if matched else None,
        "cfo_to_debt": None,
        "cash_to_borrowings": None,
        "asset_turnover": None,
        "revenue_growth_pct": matched.revenue_growth_pct if matched else None,
        "profit_growth_pct": None,
        "history_periods_available": 1 if summary.statement_period else 0,
        "critical_feature_coverage_pct": _live_core_financial_coverage_pct(summary),
    }
    return row


def _inject_prior_rating_features(record: dict[str, Any], profile: CompanyCreditProfile, agency_name: str) -> None:
    history = profile.rating_insight.history or []
    history_rows = [entry for entry in history if entry.rating or entry.agency_name]
    for feature in [
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
    ]:
        record.setdefault(feature, None)
    record["prior_agency_rating_available"] = 0
    record["prior_any_rating_available"] = 0
    if not history_rows:
        return
    first_any = history_rows[0]
    any_agency_key = _normalize_agency(first_any.agency_name)
    any_norm = normalize_rating_label(any_agency_key or "crisil", first_any.rating or "")
    if any_norm.rating_rank_numeric is not None:
        record["prior_any_rating_available"] = 1
        record["prior_any_rating_rank"] = float(any_norm.rating_rank_numeric)
        months_since_any = _months_since_date(first_any.rating_date)
        if months_since_any is not None:
            record["months_since_prior_any_rating"] = months_since_any

    same_agency = next(
        (
            entry
            for entry in history_rows
            if _normalize_agency(entry.agency_name) == agency_name
        ),
        None,
    )
    if same_agency:
        same_norm = normalize_rating_label(agency_name, same_agency.rating or "")
        if same_norm.rating_rank_numeric is not None:
            record["prior_agency_rating_available"] = 1
            record["prior_agency_rating_rank"] = float(same_norm.rating_rank_numeric)
            months_since_agency = _months_since_date(same_agency.rating_date)
            if months_since_agency is not None:
                record["months_since_prior_agency_rating"] = months_since_agency


def _months_since_date(value: str | None) -> float | None:
    text = _string(value)
    if not text:
        return None
    timestamp = pd.to_datetime(text, errors="coerce")
    if pd.isna(timestamp):
        return None
    now = pd.Timestamp.utcnow().tz_localize(None)
    ts = pd.Timestamp(timestamp).tz_localize(None) if getattr(timestamp, "tzinfo", None) is not None else pd.Timestamp(timestamp)
    delta_days = max((now - ts).days, 0)
    return round(delta_days / 30.4375, 2)


def _live_core_financial_coverage_pct(summary: Any) -> float:
    features = [
        summary.revenue_crore,
        summary.ebitda_margin_pct,
        summary.pat_margin_pct,
        summary.debt_to_equity,
        summary.interest_coverage,
        summary.working_capital_days,
        summary.receivables_days,
        summary.inventory_days,
        summary.networth_crore,
        summary.total_borrowings_crore,
    ]
    present = sum(1 for value in features if value is not None and not pd.isna(value))
    return round((present / len(features)) * 100.0, 2)


def _build_live_simulation_notes(selected_row: dict[str, Any]) -> list[str]:
    notes = [
        f"Selected agency: {selected_row.get('simulated_rating_agency') or 'unknown'}.",
        f"Published range: {selected_row.get('published_range') or 'manual review required'}.",
        f"Range usability: {selected_row.get('range_usability_label') or 'unknown'}.",
        f"CA review priority: {selected_row.get('ca_review_priority') or 'unknown'}.",
    ]
    if selected_row.get("rating_history_summary"):
        notes.append(f"Rating history context: {selected_row['rating_history_summary']}.")
    if selected_row.get("manual_review_required_flag"):
        notes.append(selected_row.get("manual_review_reason") or "Narrow publishable range could not be supported confidently.")
        if selected_row.get("calibrated_range"):
            notes.append(f"Internal benchmark-only calibrated band: {selected_row['calibrated_range']}.")
    return notes


def _build_agency_summary(benchmark_frame: pd.DataFrame) -> pd.DataFrame:
    rated = benchmark_frame[
        benchmark_frame["actual_rating_available_flag"].astype(str).str.lower().isin(["true", "1"])
        & benchmark_frame["matched_actual_agency_prediction_flag"].fillna(False)
        & benchmark_frame["simulated_rating"].notna()
        & benchmark_frame["actual_rating"].notna()
    ].copy()
    if rated.empty:
        return pd.DataFrame(
            [
                {
                    "agency": "none",
                    "companies_compared": 0,
                    "exact_match_accuracy": None,
                    "within_1_notch_accuracy": None,
                    "mean_notch_deviation": None,
                }
            ]
        )

    rows: list[dict[str, Any]] = []
    for agency, group in rated.groupby("actual_rating_agency_key", dropna=False):
        rows.append(
            {
                "agency": agency,
                "companies_compared": int(len(group)),
                "exact_match_accuracy": round(float(group["exact_match"].fillna(False).mean()), 4),
                "within_1_notch_accuracy": round(float(group["within_1_notch"].fillna(False).mean()), 4),
                "mean_notch_deviation": round(float(pd.to_numeric(group["notch_deviation"], errors="coerce").mean()), 4),
            }
        )
    rows.append(
        {
            "agency": "overall",
            "companies_compared": int(len(rated)),
            "exact_match_accuracy": round(float(rated["exact_match"].fillna(False).mean()), 4),
            "within_1_notch_accuracy": round(float(rated["within_1_notch"].fillna(False).mean()), 4),
            "mean_notch_deviation": round(float(pd.to_numeric(rated["notch_deviation"], errors="coerce").mean()), 4),
        }
    )
    return pd.DataFrame(rows).sort_values(["agency"])


def _normalize_agency(value: Any) -> str | None:
    text = _string(value)
    if not text:
        return None
    normalized = text.lower().strip()
    for key, mapped in AGENCY_NORMALIZATION.items():
        if key in normalized:
            return mapped
    return normalized.replace(" ", "_")


def _pretty_agency_name(value: str | None) -> str | None:
    if value == "india_ratings":
        return "India Ratings"
    if not value:
        return None
    return value.replace("_", " ").title()


def _parse_dataset_hint(value: str | None) -> tuple[str | None, str | None, int | None]:
    text = _string(value)
    if not text:
        return None, None, None
    agency_key = _normalize_agency(text)
    normalization = normalize_rating_label(agency_key or "crisil", text)
    return agency_key, normalization.normalized_label, normalization.rating_rank_numeric


def _history_source_url(history: list[Any]) -> str | None:
    if not history:
        return None
    first = history[0]
    if isinstance(first, dict):
        return _string(first.get("source_url"))
    return _string(getattr(first, "source_url", None))


def _history_source(history: list[Any], notes: list[str] | None) -> str:
    if history:
        first = history[0]
        if isinstance(first, dict):
            source = _string(first.get("source"))
        else:
            source = _string(getattr(first, "source", None))
        if source:
            return source
    note_text = " ".join(notes or []).lower()
    if "dataset hint" in note_text or "agriculture master dataset" in note_text:
        return "dataset_hint"
    if "search-engine-guided" in note_text:
        return "cra_web_discovery"
    if "cached screener-derived" in note_text:
        return "cached_history"
    return "not_found"


def _rank_from_rating(value: Any) -> float | None:
    rating = _string(value)
    if not rating:
        return None
    normalization = normalize_rating_label("crisil", rating)
    return float(normalization.rating_rank_numeric) if normalization.rating_rank_numeric is not None else None


def _string(value: Any) -> str | None:
    if value is None or pd.isna(value):
        return None
    text = str(value).strip()
    return text or None


def _to_float(value: Any) -> float | None:
    if value is None or pd.isna(value):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _coverage_for_halfwidth(frame: pd.DataFrame, halfwidth: int) -> float:
    hits: list[bool] = []
    for row in frame.to_dict(orient="records"):
        predicted_rank = _rank_from_rating(row.get("simulated_rating"))
        actual_rank = _rank_from_rating(row.get("actual_rating"))
        hits.append(
            predicted_rank is not None
            and actual_rank is not None
            and abs(predicted_rank - actual_rank) <= halfwidth
        )
    return float(sum(hits) / len(hits)) if hits else 0.0


def _range_bounds(predicted_rating: str | None, halfwidth: int) -> tuple[str | None, str | None, int | None, int | None]:
    predicted_rank = _rank_from_rating(predicted_rating)
    if predicted_rank is None:
        return None, None, None, None
    lower_rank = max(1, int(predicted_rank - halfwidth))
    upper_rank = min(len(LONG_TERM_ORDER), int(predicted_rank + halfwidth))
    return (
        LONG_TERM_ORDER[lower_rank - 1],
        LONG_TERM_ORDER[upper_rank - 1],
        lower_rank,
        upper_rank,
    )


def _format_range(lower_label: str | None, upper_label: str | None) -> str | None:
    if not lower_label or not upper_label:
        return None
    if lower_label == upper_label:
        return lower_label
    return f"{lower_label} to {upper_label}"


def _parse_probability_map(value: Any) -> dict[str, float]:
    text = _string(value)
    if not text:
        return {}
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return {}
    if not isinstance(payload, dict):
        return {}
    result: dict[str, float] = {}
    for key, item in payload.items():
        try:
            result[str(key)] = float(item)
        except (TypeError, ValueError):
            continue
    return result


def _range_probability_mass(probability_map: dict[str, float], lower_rank: int | None, upper_rank: int | None) -> float:
    if lower_rank is None or upper_rank is None:
        return 0.0
    mass = 0.0
    for label, value in probability_map.items():
        rank = _rank_from_rating(label)
        if rank is not None and lower_rank <= rank <= upper_rank:
            mass += value
    return min(max(mass, 0.0), 1.0)


def _choose_published_range(
    *,
    predicted_rating: str | None,
    probability_map: dict[str, float],
    simulation_confidence: float,
    top_probability: float,
    critical_feature_coverage_pct: float | None,
    data_completeness: float | None,
    feature_coverage: float | None,
    history_available: bool,
    agency_strength_score: float,
) -> dict[str, Any]:
    best_candidate: dict[str, Any] | None = None
    for halfwidth in range(PUBLISHED_RANGE_MAX_HALFWIDTH + 1):
        lower_label, upper_label, lower_rank, upper_rank = _range_bounds(predicted_rating, halfwidth)
        width_notches = int((halfwidth * 2) + 1)
        probability_mass = _range_probability_mass(probability_map, lower_rank, upper_rank)
        confidence_score = _range_confidence_score(
            simulation_confidence=simulation_confidence,
            range_probability_mass=probability_mass,
            critical_feature_coverage_pct=critical_feature_coverage_pct,
            data_completeness=data_completeness,
            feature_coverage=feature_coverage,
            history_available=history_available,
            range_width_notches=width_notches,
            agency_strength_score=agency_strength_score,
        )
        candidate = {
            "published_range": _format_range(lower_label, upper_label),
            "published_range_lower": lower_label,
            "published_range_upper": upper_label,
            "published_range_lower_rank": lower_rank,
            "published_range_upper_rank": upper_rank,
            "published_range_halfwidth_notches": halfwidth,
            "published_range_width_notches": width_notches,
            "range_probability_mass": probability_mass,
            "range_confidence_score": confidence_score,
        }
        if best_candidate is None:
            best_candidate = candidate
        else:
            best_score = (best_candidate["range_confidence_score"] * 0.58) + (best_candidate["range_probability_mass"] * 0.42)
            candidate_score = (confidence_score * 0.58) + (probability_mass * 0.42)
            if candidate_score > best_score:
                best_candidate = candidate
        if (
            probability_mass >= PUBLISHED_RANGE_MIN_MASS_BY_HALFWIDTH[halfwidth]
            and confidence_score >= PUBLISHED_RANGE_MIN_CONFIDENCE_BY_HALFWIDTH[halfwidth]
            and top_probability >= PUBLISHED_RANGE_MIN_TOP_PROB_BY_HALFWIDTH[halfwidth]
        ):
            usability = "focused" if width_notches <= 3 else "workable"
            return {
                **candidate,
                "manual_review_required_flag": False,
                "manual_review_reason": None,
                "range_usability_label": usability,
            }

    if best_candidate is None:
        return {
            "published_range": None,
            "published_range_lower": None,
            "published_range_upper": None,
            "published_range_lower_rank": None,
            "published_range_upper_rank": None,
            "published_range_halfwidth_notches": None,
            "published_range_width_notches": None,
            "range_probability_mass": 0.0,
            "range_confidence_score": 0.0,
            "manual_review_required_flag": True,
            "manual_review_reason": "Model output was too weak to support a narrow 1-5 notch published range.",
            "range_usability_label": "manual_review_required",
        }

    return {
        **best_candidate,
        "published_range": None,
        "published_range_lower": None,
        "published_range_upper": None,
        "published_range_lower_rank": None,
        "published_range_upper_rank": None,
        "manual_review_required_flag": True,
        "manual_review_reason": (
            f"Best narrow band {best_candidate['published_range']} did not meet the minimum confidence/mass thresholds; manual review required."
        ),
        "range_usability_label": "manual_review_required",
    }


def _range_confidence_score(
    *,
    simulation_confidence: float,
    range_probability_mass: float,
    critical_feature_coverage_pct: float | None,
    data_completeness: float | None,
    feature_coverage: float | None,
    history_available: bool,
    range_width_notches: int,
    agency_strength_score: float,
) -> float:
    coverage_inputs = [
        value
        for value in [
            (critical_feature_coverage_pct / 100.0) if critical_feature_coverage_pct is not None else None,
            data_completeness,
            feature_coverage,
        ]
        if value is not None
    ]
    coverage_score = sum(coverage_inputs) / len(coverage_inputs) if coverage_inputs else 0.5
    history_score = 1.0 if history_available else 0.45
    width_trust = _range_width_trust(range_width_notches)
    score = (
        (simulation_confidence * 0.23)
        + (range_probability_mass * 0.18)
        + (coverage_score * 0.16)
        + (history_score * 0.1)
        + (width_trust * 0.23)
        + (agency_strength_score * 0.1)
    )
    return min(max(score, 0.0), 1.0)


def _confidence_label(score: float) -> str:
    if score >= 0.75:
        return "high"
    if score >= 0.5:
        return "medium"
    return "low"


def _range_width_trust(range_width_notches: int) -> float:
    if range_width_notches <= 5:
        return 1.0
    if range_width_notches <= 7:
        return 0.85
    if range_width_notches <= 9:
        return 0.72
    if range_width_notches <= 11:
        return 0.58
    if range_width_notches <= 13:
        return 0.45
    if range_width_notches <= 15:
        return 0.33
    if range_width_notches <= 17:
        return 0.25
    return 0.12


def _range_usability_label(range_width_notches: int, range_confidence_score: float) -> str:
    if range_width_notches <= 5 and range_confidence_score >= 0.55:
        return "focused"
    if range_width_notches <= 11 and range_confidence_score >= 0.4:
        return "workable"
    return "directional_only"


def _selection_priority_score(
    *,
    range_confidence_score: float,
    width_trust: float,
    agency_strength_score: float,
    history_available: bool,
) -> float:
    history_boost = 1.0 if history_available else 0.7
    score = (
        (range_confidence_score * 0.5)
        + (width_trust * 0.25)
        + (agency_strength_score * 0.25)
    ) * history_boost
    return min(max(score, 0.0), 1.0)


def _simulation_actionability_label(range_usability_label: str, range_confidence_score: float, history_available: bool) -> str:
    if range_usability_label == "manual_review_required":
        return "manual_review_required"
    if range_usability_label == "focused" and range_confidence_score >= 0.6 and history_available:
        return "high"
    if range_usability_label in {"focused", "workable"} and range_confidence_score >= 0.45:
        return "medium"
    return "low"


def _ca_review_priority_label(range_usability_label: str, range_confidence_score: float, history_available: bool) -> str:
    if range_usability_label in {"directional_only", "manual_review_required"} or range_confidence_score < 0.4:
        return "high"
    if not history_available or range_confidence_score < 0.55:
        return "medium"
    return "low"


def _build_rating_history_summary(
    *,
    agency_name: str | None,
    rating: str | None,
    rating_date: str | None,
    dataset_latest_ratings_text: str | None,
) -> str | None:
    if agency_name and rating and rating_date:
        return f"{agency_name} {rating} on {rating_date}"
    if agency_name and rating:
        return f"{agency_name} {rating} (date unavailable)"
    if dataset_latest_ratings_text:
        return dataset_latest_ratings_text
    return None
