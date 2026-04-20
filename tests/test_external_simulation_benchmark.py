from __future__ import annotations

import pandas as pd

from src.credit_intel.external_simulation_benchmark import (
    _build_agency_range_frame,
    _build_company_range_benchmark,
    _build_range_summary,
    _calibrate_agency_range_policy,
)


def test_calibrate_agency_range_policy_picks_smallest_target_meeting_band() -> None:
    benchmark = pd.DataFrame(
        [
            {
                "company_id": "c1",
                "company_name": "Alpha",
                "actual_rating_available_flag": True,
                "matched_actual_agency_prediction_flag": True,
                "simulated_rating": "BBB",
                "actual_rating": "BBB",
                "actual_rating_agency_key": "crisil",
            },
            {
                "company_id": "c2",
                "company_name": "Beta",
                "actual_rating_available_flag": True,
                "matched_actual_agency_prediction_flag": True,
                "simulated_rating": "BBB",
                "actual_rating": "BBB-",
                "actual_rating_agency_key": "crisil",
            },
            {
                "company_id": "c3",
                "company_name": "Gamma",
                "actual_rating_available_flag": True,
                "matched_actual_agency_prediction_flag": True,
                "simulated_rating": "BBB",
                "actual_rating": "BB+",
                "actual_rating_agency_key": "crisil",
            },
        ]
    )

    policy = _calibrate_agency_range_policy(benchmark, target_coverage=0.75)

    row = policy.iloc[0]
    assert row["agency"] == "crisil"
    assert row["selected_halfwidth_notches"] == 2
    assert row["coverage_at_selected_range"] == 1.0
    assert bool(row["target_met"]) is True


def test_agency_range_frame_and_company_selection_include_range_confidence() -> None:
    companies = pd.DataFrame(
        [
            {
                "company_id": "c1",
                "company_name": "Alpha Foods",
                "industry_group": "Agri",
                "sub_industry": "Edible Oils",
                "revenue_crore": 120.0,
                "ebitda_margin_pct": 8.5,
                "debt_to_equity": 1.2,
                "interest_coverage": 2.4,
                "simulation_readiness": "high",
                "critical_feature_coverage_pct": 100.0,
                "dataset_latest_ratings_text": "CRISIL BBB",
                "listed_status": "unlisted",
                "listed_flag": False,
                "screener_url": None,
            }
        ]
    )
    actual = pd.DataFrame(
        [
            {
                "company_id": "c1",
                "company_name": "Alpha Foods",
                "actual_rating_available_flag": True,
                "actual_rating_agency": "CRISIL",
                "actual_rating_agency_key": "crisil",
                "actual_rating": "BBB",
                "actual_normalized_rating": "BBB",
                "actual_rating_rank": 9,
                "actual_rating_date": "2025-03-31",
                "actual_rating_source": "dataset_hint",
                "actual_rating_source_url": None,
            }
        ]
    )
    simulations = pd.DataFrame(
        [
            {
                "company_id": "c1",
                "company_name": "Alpha Foods",
                "agency": "crisil",
                "predicted_rating": "BBB",
                "rating_range": "BBB / BBB-",
                "confidence": 0.42,
                "top_probability": 0.65,
                "probability_distribution_json": '{"BBB": 0.65, "BBB-": 0.2, "BB+": 0.15}',
                "data_completeness": 1.0,
                "feature_coverage": 1.0,
                "confidence_label": "low",
                "key_features": "[]",
                "prediction_status": "predicted",
            },
            {
                "company_id": "c1",
                "company_name": "Alpha Foods",
                "agency": "care",
                "predicted_rating": "BB+",
                "rating_range": "BB+ / BBB-",
                "confidence": 0.31,
                "top_probability": 0.44,
                "probability_distribution_json": '{"BB+": 0.44, "BBB-": 0.35, "BBB": 0.21}',
                "data_completeness": 1.0,
                "feature_coverage": 1.0,
                "confidence_label": "low",
                "key_features": "[]",
                "prediction_status": "predicted",
            },
        ]
    )
    policy = pd.DataFrame(
        [
            {"agency": "crisil", "selected_halfwidth_notches": 1},
            {"agency": "care", "selected_halfwidth_notches": 3},
        ]
    )
    agency_strength = pd.DataFrame(
        [
            {"agency": "crisil", "agency_strength_score": 0.82},
            {"agency": "care", "agency_strength_score": 0.66},
        ]
    )

    agency_ranges = _build_agency_range_frame(
        companies_frame=companies,
        actual_ratings_frame=actual,
        simulation_frame=simulations,
        range_policy_frame=policy,
        agency_strength_frame=agency_strength,
    )
    company_range = _build_company_range_benchmark(agency_ranges)
    range_summary = _build_range_summary(agency_ranges)

    crisil_row = agency_ranges[agency_ranges["simulated_rating_agency"] == "crisil"].iloc[0]
    assert crisil_row["calibrated_range"] == "BBB+ to BBB-"
    assert crisil_row["published_range"] == "BBB"
    assert bool(crisil_row["range_hit_against_actual"]) is True
    assert crisil_row["range_confidence_score"] > 0.5
    assert crisil_row["range_usability_label"] == "focused"
    assert crisil_row["simulation_actionability"] in {"high", "medium"}
    assert bool(crisil_row["manual_review_required_flag"]) is False

    selected = company_range.iloc[0]
    assert selected["simulated_rating_agency"] == "crisil"
    assert selected["published_range"] == "BBB"
    assert selected["selected_agency_reason"] == "matched_historical_agency"

    overall = range_summary[range_summary["agency"] == "overall"].iloc[0]
    assert overall["range_hit_accuracy"] == 1.0


def test_manual_review_required_when_no_narrow_range_meets_thresholds() -> None:
    companies = pd.DataFrame(
        [
            {
                "company_id": "c1",
                "company_name": "Diffuse Agro",
                "industry_group": "Agri",
                "sub_industry": "Staples",
                "revenue_crore": 80.0,
                "ebitda_margin_pct": 6.4,
                "debt_to_equity": 1.8,
                "interest_coverage": 1.7,
                "simulation_readiness": "medium",
                "critical_feature_coverage_pct": 70.0,
                "dataset_latest_ratings_text": None,
                "listed_status": "unlisted",
                "listed_flag": False,
                "screener_url": None,
            }
        ]
    )
    actual = pd.DataFrame(
        [
            {
                "company_id": "c1",
                "company_name": "Diffuse Agro",
                "actual_rating_available_flag": False,
                "actual_rating_agency": None,
                "actual_rating_agency_key": None,
                "actual_rating": None,
                "actual_normalized_rating": None,
                "actual_rating_rank": None,
                "actual_rating_date": None,
                "actual_rating_source": "not_found",
                "actual_rating_source_url": None,
            }
        ]
    )
    simulations = pd.DataFrame(
        [
            {
                "company_id": "c1",
                "company_name": "Diffuse Agro",
                "agency": "care",
                "predicted_rating": "BBB-",
                "rating_range": "BBB- / BB+",
                "confidence": 0.22,
                "top_probability": 0.19,
                "probability_distribution_json": '{"BBB-": 0.19, "BB+": 0.18, "BBB": 0.17, "BB": 0.16, "A-": 0.15, "BBB+": 0.15}',
                "data_completeness": 0.62,
                "feature_coverage": 0.58,
                "confidence_label": "low",
                "key_features": "[]",
                "prediction_status": "predicted",
            }
        ]
    )
    policy = pd.DataFrame([{"agency": "care", "selected_halfwidth_notches": 8}])
    agency_strength = pd.DataFrame([{"agency": "care", "agency_strength_score": 0.52}])

    agency_ranges = _build_agency_range_frame(
        companies_frame=companies,
        actual_ratings_frame=actual,
        simulation_frame=simulations,
        range_policy_frame=policy,
        agency_strength_frame=agency_strength,
    )

    row = agency_ranges.iloc[0]
    assert row["published_range"] is None
    assert bool(row["manual_review_required_flag"]) is True
    assert row["range_usability_label"] == "manual_review_required"
    assert row["simulation_actionability"] == "manual_review_required"
