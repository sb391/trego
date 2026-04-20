from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.model_selection import LeaveOneGroupOut

from ..schemas.crosswalks import LONG_TERM_ORDER
from .simulation_pipeline import (
    CATEGORICAL_MODEL_FEATURES,
    DERIVED_MODEL_FEATURES,
    MODEL_NUMERIC_FEATURES,
    RATIONALE_BINARY_FEATURES,
    RATIONALE_COUNT_FEATURES,
    TARGET_AGENCIES,
    _blend_prediction_confidence,
    _build_classifier_pipeline,
    _build_rank_regressor_pipeline,
    _build_training_row,
    _assemble_training_rows,
    _confidence_label,
    _derive_key_features,
    _ensure_model_feature_columns,
    _event_eligibility_status,
    _financial_data_completeness,
    _normalize_agency_key,
    _predict_rating_outputs,
    _prepare_rationale_lookup,
    _rationale_feature_coverage,
    _select_active_categorical_features,
    _select_active_numeric_features,
    _summarize_training_feature_stats,
    _to_float,
    _within_one_notch_accuracy,
    load_model_artifact,
)


def run_agency_model_diagnostics(
    *,
    simulation_model_dir: Path,
    output_dir: Path,
    min_days_before_rating: int = 90,
) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)

    financial_features_path = simulation_model_dir / "financials" / "financial_year_features.csv"
    rating_events_path = simulation_model_dir / "rationales" / "rating_events.csv"
    rationale_features_path = simulation_model_dir / "rationales" / "rationale_features.csv"
    context_features_path = simulation_model_dir / "context" / "context_features.csv"
    model_index_path = simulation_model_dir / "models" / "agency_model_index.csv"
    rationale_summary_path = simulation_model_dir / "rationales" / "agency_rationale_summary.csv"

    lagged_dataset_path = output_dir / "agency_training_dataset_3m_lag.csv"
    exclusions_path = output_dir / "agency_training_exclusions_3m_lag.csv"
    event_results_path = output_dir / "agency_validation_event_results_3m_lag.csv"
    company_results_path = output_dir / "agency_validation_company_results_3m_lag.csv"
    summary_path = output_dir / "agency_validation_summary_3m_lag.csv"
    feature_importance_path = output_dir / "agency_feature_importance_summary.csv"
    feature_report_path = output_dir / "simulation_feature_learning_report.md"

    lagged_dataset, exclusions = _build_lagged_training_dataset(
        financial_features_path=financial_features_path,
        rating_events_path=rating_events_path,
        rationale_features_path=rationale_features_path,
        context_features_path=context_features_path,
        min_days_before_rating=min_days_before_rating,
    )
    lagged_dataset.to_csv(lagged_dataset_path, index=False)
    exclusions.to_csv(exclusions_path, index=False)

    event_results, agency_summary = _evaluate_agencies_with_group_holdout(lagged_dataset)
    event_results.to_csv(event_results_path, index=False)
    company_results = _build_company_level_summary(event_results)
    company_results.to_csv(company_results_path, index=False)
    agency_summary.to_csv(summary_path, index=False)

    feature_importance = _extract_agency_feature_importance(model_index_path)
    feature_importance.to_csv(feature_importance_path, index=False)

    rationale_summary = pd.read_csv(rationale_summary_path) if rationale_summary_path.exists() else pd.DataFrame()
    feature_report_path.write_text(
        _render_feature_learning_report(
            lagged_dataset=lagged_dataset,
            agency_summary=agency_summary,
            feature_importance=feature_importance,
            rationale_summary=rationale_summary,
            exclusions=exclusions,
            min_days_before_rating=min_days_before_rating,
        ),
        encoding="utf-8",
    )

    return {
        "lagged_training_dataset": lagged_dataset_path,
        "lagged_training_exclusions": exclusions_path,
        "validation_event_results": event_results_path,
        "validation_company_results": company_results_path,
        "validation_summary": summary_path,
        "feature_importance_summary": feature_importance_path,
        "feature_learning_report": feature_report_path,
    }


def _build_lagged_training_dataset(
    *,
    financial_features_path: Path,
    rating_events_path: Path,
    rationale_features_path: Path,
    context_features_path: Path,
    min_days_before_rating: int,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    features_frame = pd.read_csv(financial_features_path)
    events_frame = pd.read_csv(rating_events_path)
    rationale_frame = pd.read_csv(rationale_features_path) if rationale_features_path.exists() else pd.DataFrame()

    if features_frame.empty or events_frame.empty:
        return pd.DataFrame(), pd.DataFrame()

    features_frame["period_date"] = pd.to_datetime(features_frame["period_date"], errors="coerce")
    events_frame["rating_date"] = pd.to_datetime(events_frame["rating_date"], errors="coerce")
    events_frame["agency_name"] = events_frame["agency_name"].map(_normalize_agency_key)
    events_frame["eligibility_status"] = events_frame.apply(_event_eligibility_status, axis=1)
    rationale_lookup = _prepare_rationale_lookup(rationale_frame)
    context_frame = pd.read_csv(context_features_path) if context_features_path.exists() else pd.DataFrame()

    lagged_rows, exclusion_rows = _assemble_training_rows(
        features_frame=features_frame,
        events_frame=events_frame,
        rationale_lookup=rationale_lookup,
        context_frame=context_frame,
        min_days_before_rating=min_days_before_rating,
    )

    return pd.DataFrame(lagged_rows), pd.DataFrame(exclusion_rows)


def _evaluate_agencies_with_group_holdout(lagged_dataset: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    if lagged_dataset.empty:
        return pd.DataFrame(), pd.DataFrame()

    event_rows: list[dict[str, Any]] = []
    agency_rows: list[dict[str, Any]] = []

    for agency_name in TARGET_AGENCIES:
        agency_frame = lagged_dataset[lagged_dataset["agency_name"] == agency_name].copy()
        if agency_frame.empty:
            agency_rows.append(
                {
                    "agency_name": agency_name,
                    "evaluation_mode": "no_rows_after_3m_lag",
                    "rows_evaluated": 0,
                    "companies_evaluated": 0,
                    "exact_match_accuracy": np.nan,
                    "within_one_notch_accuracy": np.nan,
                    "mean_abs_notch_error": np.nan,
                    "mean_confidence": np.nan,
                }
            )
            continue

        agency_frame = _ensure_model_feature_columns(agency_frame)
        groups = agency_frame["company_id"].astype(str)
        unique_groups = groups.nunique()
        evaluation_mode = "leave_one_company_out" if unique_groups >= 2 else "in_sample_fallback_single_company"

        predicted_frames: list[pd.DataFrame] = []
        if unique_groups >= 2:
            splitter = LeaveOneGroupOut()
            for train_index, test_index in splitter.split(agency_frame, groups=groups):
                train_frame = agency_frame.iloc[train_index].copy()
                test_frame = agency_frame.iloc[test_index].copy()
                scored = _score_holdout_frame(train_frame, test_frame, agency_name, evaluation_mode)
                predicted_frames.append(scored)
        else:
            predicted_frames.append(_score_holdout_frame(agency_frame, agency_frame, agency_name, evaluation_mode))

        agency_predictions = pd.concat(predicted_frames, ignore_index=True) if predicted_frames else pd.DataFrame()
        event_rows.extend(agency_predictions.to_dict(orient="records"))
        agency_rows.append(_summarize_agency_predictions(agency_name, evaluation_mode, agency_predictions))

    return pd.DataFrame(event_rows), pd.DataFrame(agency_rows)


def _score_holdout_frame(
    train_frame: pd.DataFrame,
    test_frame: pd.DataFrame,
    agency_name: str,
    evaluation_mode: str,
) -> pd.DataFrame:
    train_working = _ensure_model_feature_columns(train_frame)
    test_working = _ensure_model_feature_columns(test_frame)

    active_numeric_features = _select_active_numeric_features(train_working)
    active_categorical_features = _select_active_categorical_features(train_working)
    selected_numeric_features = [
        *active_numeric_features,
        *RATIONALE_BINARY_FEATURES,
        *RATIONALE_COUNT_FEATURES,
        *DERIVED_MODEL_FEATURES,
    ]
    X_train = train_working[[*selected_numeric_features, *active_categorical_features]].copy()
    y_train = train_working["normalized_long_term_label"].astype(str)
    y_rank_train = pd.to_numeric(train_working["normalized_long_term_rank"], errors="coerce")

    pipeline = _build_classifier_pipeline(
        use_dummy=(y_train.nunique() == 1),
        numeric_features=active_numeric_features,
        categorical_features=active_categorical_features,
    )
    pipeline.fit(X_train, y_train)
    rank_regressor = None
    blend_weights = {"classifier": 1.0, "rank_regressor": 0.0}
    if y_train.nunique() > 1 and y_rank_train.notna().sum() >= 8:
        rank_regressor = _build_rank_regressor_pipeline(
            numeric_features=active_numeric_features,
            categorical_features=active_categorical_features,
        )
        rank_regressor.fit(X_train, y_rank_train)
        blend_weights = {"classifier": 0.65, "rank_regressor": 0.35}

    X_test = test_working[[*selected_numeric_features, *active_categorical_features]].copy()
    predicted_labels, probability_maps = _predict_rating_outputs(
        classifier_pipeline=pipeline,
        rank_regressor=rank_regressor,
        X=X_test,
        label_order=[label for label in LONG_TERM_ORDER if label in set(y_train.astype(str))],
        blend_weights=blend_weights,
    )
    feature_stats = _summarize_training_feature_stats(train_working)

    rows: list[dict[str, Any]] = []
    for index, (_, record) in enumerate(test_working.iterrows()):
        probability_map = probability_maps[index]
        predicted_rating = str(predicted_labels[index])
        actual_rating = _string(record.get("normalized_long_term_label"))
        actual_rank = LONG_TERM_ORDER.index(actual_rating) + 1 if actual_rating in LONG_TERM_ORDER else None
        predicted_rank = LONG_TERM_ORDER.index(predicted_rating) + 1 if predicted_rating in LONG_TERM_ORDER else None
        deviation = predicted_rank - actual_rank if actual_rank is not None and predicted_rank is not None else None
        top_probability = max(probability_map.values()) if probability_map else 0.0
        data_completeness = _financial_data_completeness(record)
        feature_coverage = _rationale_feature_coverage(record)
        confidence = _blend_prediction_confidence(
            probability_confidence=top_probability,
            data_completeness=data_completeness,
            feature_coverage=feature_coverage,
            context_coverage=_to_float(record.get("context_coverage")) or 0.0,
            history_depth=min((_to_float(record.get("history_periods_available")) or 0.0) / 4.0, 1.0),
        )
        rows.append(
            {
                "agency_name": agency_name,
                "evaluation_mode": evaluation_mode,
                "company_id": record.get("company_id"),
                "company_name": record.get("company_name"),
                "rating_event_id": record.get("rating_event_id"),
                "rating_date": record.get("rating_date"),
                "matched_financial_period": record.get("matched_financial_period"),
                "days_from_financial_period": record.get("days_from_financial_period"),
                "actual_rating": actual_rating,
                "predicted_rating": predicted_rating,
                "rating_range": " / ".join(list(probability_map)[:2]) if probability_map else None,
                "deviation": deviation,
                "exact_match": bool(actual_rating == predicted_rating) if actual_rating else False,
                "within_one_notch": (abs(deviation) <= 1) if deviation is not None else False,
                "confidence": round(confidence, 4),
                "confidence_label": _confidence_label(confidence),
                "top_probability": round(top_probability, 4),
                "data_completeness": round(data_completeness, 4),
                "feature_coverage": round(feature_coverage, 4),
                "probability_distribution_json": json.dumps(probability_map),
                "key_features": json.dumps(_derive_key_features(record, feature_stats)),
            }
        )
    return pd.DataFrame(rows)


def _summarize_agency_predictions(agency_name: str, evaluation_mode: str, frame: pd.DataFrame) -> dict[str, Any]:
    if frame.empty:
        return {
            "agency_name": agency_name,
            "evaluation_mode": evaluation_mode,
            "rows_evaluated": 0,
            "companies_evaluated": 0,
            "exact_match_accuracy": np.nan,
            "within_one_notch_accuracy": np.nan,
            "mean_abs_notch_error": np.nan,
            "mean_confidence": np.nan,
        }
    actual = frame["actual_rating"].astype(str).to_numpy()
    predicted = frame["predicted_rating"].astype(str).to_numpy()
    valid_deviation = pd.to_numeric(frame["deviation"], errors="coerce").dropna()
    return {
        "agency_name": agency_name,
        "evaluation_mode": evaluation_mode,
        "rows_evaluated": int(len(frame)),
        "companies_evaluated": int(frame["company_id"].nunique()),
        "exact_match_accuracy": round(float(frame["exact_match"].mean()), 4),
        "within_one_notch_accuracy": round(_within_one_notch_accuracy(actual, predicted), 4),
        "mean_abs_notch_error": round(float(valid_deviation.abs().mean()), 4) if not valid_deviation.empty else np.nan,
        "mean_confidence": round(float(frame["confidence"].mean()), 4),
    }


def _build_company_level_summary(event_results: pd.DataFrame) -> pd.DataFrame:
    if event_results.empty:
        return pd.DataFrame()
    grouped = (
        event_results.groupby(["agency_name", "company_id", "company_name"], dropna=False)
        .agg(
            events_evaluated=("rating_event_id", "count"),
            exact_match_rate=("exact_match", "mean"),
            within_one_notch_rate=("within_one_notch", "mean"),
            mean_abs_notch_error=("deviation", lambda values: pd.to_numeric(values, errors="coerce").abs().mean()),
            average_confidence=("confidence", "mean"),
            latest_rating_date=("rating_date", "max"),
        )
        .reset_index()
    )
    grouped["exact_match_rate"] = grouped["exact_match_rate"].round(4)
    grouped["within_one_notch_rate"] = grouped["within_one_notch_rate"].round(4)
    grouped["mean_abs_notch_error"] = grouped["mean_abs_notch_error"].round(4)
    grouped["average_confidence"] = grouped["average_confidence"].round(4)
    return grouped.sort_values(["agency_name", "exact_match_rate", "average_confidence"], ascending=[True, False, False])


def _extract_agency_feature_importance(model_index_path: Path) -> pd.DataFrame:
    if not model_index_path.exists():
        return pd.DataFrame()
    model_index = pd.read_csv(model_index_path)
    rows: list[dict[str, Any]] = []
    for record in model_index.to_dict(orient="records"):
        model_path = Path(str(record.get("model_path") or ""))
        if not model_path.exists():
            continue
        artifact = load_model_artifact(model_path)
        pipeline = artifact["pipeline"]
        model = pipeline.named_steps["model"]
        preprocess = pipeline.named_steps["preprocess"]
        if not hasattr(model, "feature_importances_"):
            continue
        feature_names = preprocess.get_feature_names_out()
        raw_importances = pd.DataFrame(
            {
                "feature_name": feature_names,
                "importance": model.feature_importances_,
            }
        )
        raw_importances["base_feature"] = raw_importances["feature_name"].apply(_base_feature_name)
        grouped = raw_importances.groupby("base_feature", as_index=False)["importance"].sum()
        grouped = grouped.sort_values("importance", ascending=False).head(12)
        for _, row in grouped.iterrows():
            rows.append(
                {
                    "agency_name": artifact["agency_name"],
                    "base_feature": row["base_feature"],
                    "importance": round(float(row["importance"]), 6),
                }
            )
    return pd.DataFrame(rows)


def _base_feature_name(feature_name: str) -> str:
    text = str(feature_name)
    if "__" in text:
        text = text.split("__", 1)[1]
    if "_" in text and any(text.startswith(prefix) for prefix in ("sub_industry_", "liquidity_label_", "standalone_or_consolidated_")):
        for prefix in ("sub_industry_", "liquidity_label_", "standalone_or_consolidated_"):
            if text.startswith(prefix):
                return prefix.removesuffix("_")
    return text


def _render_feature_learning_report(
    *,
    lagged_dataset: pd.DataFrame,
    agency_summary: pd.DataFrame,
    feature_importance: pd.DataFrame,
    rationale_summary: pd.DataFrame,
    exclusions: pd.DataFrame,
    min_days_before_rating: int,
) -> str:
    financial_features = [
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
        "cash_to_borrowings",
        "asset_turnover",
        "revenue_growth_pct",
        "profit_growth_pct",
        "... plus 3-year averages, 1-year / 2-year deltas, volatility, and slope features for each financial series",
    ]
    rating_carry_forward_features = [
        "prior_agency_rating_rank",
        "prior_any_rating_rank",
        "months_since_prior_agency_rating",
        "months_since_prior_any_rating",
        "since_prior_agency_revenue_growth_pct",
        "since_prior_agency_ebitda_margin_change",
        "since_prior_agency_debt_to_equity_change",
        "since_prior_agency_interest_coverage_change",
        "since_prior_agency_working_capital_days_change",
    ]
    benchmark_features = [
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
    trajectory_features = [
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
    optional_context_features = [
        "promoter_bureau_score",
        "promoter_delinquency_count",
        "criminal_case_count",
        "regulatory_risk_score",
        "governance_risk_score",
        "projected_revenue_cagr_5y",
        "projected_ebitda_margin_pct_5y",
        "industry_expected_revenue_cagr_5y",
        "execution_track_record_score",
        "plan_progress_score",
        "plan_submission_available",
        "plan_on_track_flag",
        "growth_plan_aggressive_flag",
        "promoter_adverse_hits",
        "public_negative_news_hits",
        "fraud_signal_hits",
        "regulatory_action_hits",
        "insolvency_signal_hits",
        "litigation_signal_hits",
        "public_risk_score",
        "industry_outlook_score",
        "public_risk_flag",
    ]
    rationale_features = [
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
    derived_features = [
        "sub_industry",
        "liquidity_label",
        "standalone_or_consolidated",
        "strengths_count",
        "weaknesses_count",
        "sensitivities_up_count",
        "sensitivities_down_count",
        "qualitative_summary_length",
        "days_from_financial_period",
        "data_completeness",
        "feature_coverage",
        "context_coverage",
        "history_periods_available",
        "financial_window_span_days",
        "profitability_trend_positive",
        "leverage_trend_improving",
        "coverage_trend_improving",
        "working_capital_trend_improving",
        "scale_growth_positive",
        "networth_growth_positive",
    ]

    lines = [
        "# Simulation Feature Learning Report",
        "",
        f"- Validation rule: latest financial period no later than {min_days_before_rating} days before the rating date.",
        f"- Rows retained after lag filter: {len(lagged_dataset)}",
        f"- Agencies covered after lag filter: {lagged_dataset['agency_name'].nunique() if not lagged_dataset.empty else 0}",
        f"- Excluded events due to lag/alignment or special states: {len(exclusions)}",
        "",
        "## Feature Families",
        "",
        "### Financial features",
        ", ".join(financial_features),
        "",
        "### Rationale-derived binary features",
        ", ".join(rationale_features),
        "",
        "### Prior rating carry-forward features",
        ", ".join(rating_carry_forward_features),
        "",
        "### Industry benchmark features",
        ", ".join(benchmark_features),
        "",
        "### Listed-peer trajectory features",
        ", ".join(trajectory_features),
        "",
        "### Optional contextual / subjective features",
        ", ".join(optional_context_features),
        "",
        "### Derived/context features",
        ", ".join(derived_features),
        "",
        "## Why these features were chosen",
        "",
        "- Financial ratios were kept because CRA reports repeatedly tie rating levels to profitability, leverage, coverage, liquidity, and working-capital intensity.",
        "- Rolling pre-rating windows were added because agencies typically rate on trajectory, not on a single annual snapshot. The model now sees recent average levels, volatility, and directional change.",
        "- Prior-rating carry-forward features were added because if a company was already rated, the last disclosed rating plus the financial change since then provides strong information about likely stability, upgrade momentum, or downgrade pressure.",
        "- Industry benchmark features were added because agencies implicitly judge companies relative to peers, not in isolation. Median gaps and percentiles help the model see whether a company is outperforming or lagging its sub-industry.",
        "- Listed-peer trajectory features were added because agencies often judge whether a growth plan or current financial position looks realistic relative to how comparable listed peers historically scaled up from similar size bands.",
        "- Optional contextual features were added as a structured slot for promoter bureau behavior, governance/legal issues, regulatory stress, and management plan realism. These are not always available today, but the simulator can now use them whenever they are supplied.",
        "- Rationale binary signals were kept because agencies frequently state rating drivers in stable language such as working-capital pressure, export risk, group support, capex risk, and management strength.",
        "- Data completeness and rationale feature coverage were kept because simulation confidence should fall when the input data stream is sparse, even if a prediction can still be forced.",
        "- Days from financial period, history depth, and context coverage were kept because the same rating label can mean different things depending on how stale, shallow, or one-dimensional the underlying information set was at the time of assessment.",
        "",
        "## Agency-wise validation summary",
        "",
    ]

    if not agency_summary.empty:
        for _, row in agency_summary.sort_values("agency_name").iterrows():
            lines.append(
                f"- {row['agency_name']}: rows={int(row['rows_evaluated'])}, companies={int(row['companies_evaluated'])}, "
                f"exact={_fmt(row['exact_match_accuracy'])}, within_one={_fmt(row['within_one_notch_accuracy'])}, "
                f"mean_abs_notch_error={_fmt(row['mean_abs_notch_error'])}, mode={row['evaluation_mode']}"
            )
    else:
        lines.append("- No validation rows available.")

    lines.extend(["", "## Agency-specific qualitative learnings", ""])
    if not rationale_summary.empty:
        for agency_name in sorted(rationale_summary["agency_name"].dropna().unique()):
            lines.append(f"### {agency_name}")
            top_signals = (
                rationale_summary[rationale_summary["agency_name"] == agency_name]
                .sort_values("mentions", ascending=False)
                .head(5)
            )
            for _, row in top_signals.iterrows():
                lines.append(f"- {row['signal_type']}: mentions={int(row['mentions'])}, rate={_fmt(row['mention_rate'])}")
            top_importance = (
                feature_importance[feature_importance["agency_name"] == agency_name]
                .sort_values("importance", ascending=False)
                .head(5)
            )
            if not top_importance.empty:
                lines.append("- Top model features:")
                for _, imp in top_importance.iterrows():
                    lines.append(f"  {imp['base_feature']}: {_fmt(imp['importance'])}")
            lines.append("")

    lines.extend(
        [
            "## Working hypotheses behind the model",
            "",
            "- Stronger EBITDA margins, stronger coverage, and lower leverage tend to support upward notches across agencies.",
            "- High receivable days, high inventory days, and stretched working-capital cycles tend to align with weaker outlooks or lower categories.",
            "- Group support is especially visible in ICRA and occasionally CARE-driven outcomes.",
            "- Regulatory, export, and capex-risk wording shows up repeatedly in CRISIL, CARE, and India Ratings documents, making those useful explanatory signals.",
            "- Non-cooperation and withdrawn states are handled as exclusions because they distort rank learning and are not clean long-term rating observations.",
        ]
    )
    return "\n".join(lines) + "\n"


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


def _string(value: Any) -> str | None:
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return None
    text = str(value).strip()
    return text or None


def _fmt(value: Any) -> str:
    try:
        if value is None or (isinstance(value, float) and np.isnan(value)):
            return "NA"
        return f"{float(value):.4f}"
    except (TypeError, ValueError):
        return str(value)


def load_model_artifact_fields(kind: str) -> list[str]:
    if kind == "numeric":
        return [*MODEL_NUMERIC_FEATURES]
    return [*CATEGORICAL_MODEL_FEATURES]
