from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.credit_intel.industry_export import build_screener_company_url, bootstrap_download_status_from_input_csv
from src.credit_intel.simulation_pipeline import (
    _build_financial_window_features,
    build_rating_training_dataset,
    simulate_unrated_companies,
    train_agency_specific_models,
)


def test_build_screener_company_url_prefers_nse_code() -> None:
    assert build_screener_company_url("ABCFOOD", "123456") == "https://www.screener.in/company/ABCFOOD/"
    assert build_screener_company_url(None, "123456") == "https://www.screener.in/company/123456/"


def test_bootstrap_download_status_from_input_csv(tmp_path: Path) -> None:
    input_path = tmp_path / "industry.csv"
    output_path = tmp_path / "download_status.csv"
    pd.DataFrame(
        [
            {
                "Name": "Alpha Agro",
                "BSE Code": "543210",
                "NSE Code": "ALPHAAGRO",
                "ISIN Code": "INE000A01010",
                "Industry Group": "Agricultural Food & other Products",
                "Industry": "Other Agricultural Products",
            },
            {
                "Name": "Beta Agro",
                "BSE Code": "",
                "NSE Code": "",
                "ISIN Code": "INE000B01010",
                "Industry Group": "Agricultural Food & other Products",
                "Industry": "Edible Oil",
            },
        ]
    ).to_csv(input_path, index=False)

    count = bootstrap_download_status_from_input_csv(input_path=input_path, output_path=output_path)

    assert count == 2
    frame = pd.read_csv(output_path)
    assert frame.loc[0, "status"] == "matched_ready_for_download"
    assert frame.loc[0, "screener_url"] == "https://www.screener.in/company/ALPHAAGRO/"
    assert frame.loc[1, "status"] == "missing_company_code"


def test_training_and_simulation_pipeline_round_trip(tmp_path: Path) -> None:
    features_path = tmp_path / "financial_features.csv"
    rating_events_path = tmp_path / "rating_events.csv"
    rationale_features_path = tmp_path / "rationale_features.csv"

    feature_rows = []
    event_rows = []
    rationale_rows = []
    for index in range(12):
        company_id = f"company_{index}"
        rationale_doc_id = f"doc_{index}"
        feature_rows.append(
            {
                "company_id": company_id,
                "company_name": f"Company {index}",
                "sub_industry": "Other Agricultural Products",
                "period": "2025-03-31",
                "period_date": "2025-03-31",
                "revenue_crore": 100 + index * 10,
                "ebitda_margin_pct": 8 + index * 0.5,
                "pat_margin_pct": 3 + index * 0.2,
                "debt_to_equity": 1.5 - index * 0.05,
                "interest_coverage": 2 + index * 0.2,
                "working_capital_days": 120 - index,
                "receivables_days": 60 - index * 0.5,
                "inventory_days": 30 - index * 0.25,
                "networth_crore": 80 + index * 6,
                "total_borrowings_crore": 40 + index * 2,
                "cash_to_borrowings": 0.2 + index * 0.01,
                "asset_turnover": 1.0 + index * 0.03,
            }
        )
        event_rows.append(
            {
                "rating_event_id": f"event_{index}",
                "company_id": company_id,
                "company_name": f"Company {index}",
                "agency_name": "care",
                "rating_date": "2025-07-01",
                "rationale_doc_id": rationale_doc_id,
                "current_rating": "CARE A",
                "long_term_rating": "CARE A" if index < 6 else "CARE A+",
                "normalized_long_term_label": "A" if index < 6 else "A+",
                "normalized_long_term_rank": 6 if index < 6 else 5,
                "normalized_scale_type": "long_term",
                "is_withdrawn": False,
                "is_issuer_not_cooperating": False,
                "is_withdrawn_normalized": False,
                "is_issuer_not_cooperating_normalized": False,
            }
        )
        rationale_rows.append(
            {
                "rationale_doc_id": rationale_doc_id,
                "agency_name": "care",
                "company_name": f"Company {index}",
                "liquidity_label": "Adequate" if index % 2 == 0 else "Stretched",
                "standalone_or_consolidated": "Standalone",
                "has_management_strength": True,
                "has_working_capital_pressure": index % 3 == 0,
                "has_liquidity_adequate": index % 2 == 0,
                "has_margin_pressure": index % 4 == 0,
                "strengths_json": "['Promoter experience']",
                "weaknesses_json": "['Working capital intensity']",
                "sensitivities_up_json": "['Margin improvement']",
                "sensitivities_down_json": "['Leverage increase']",
                "qualitative_summary": "Sample rationale summary",
            }
        )

    event_rows.append(
        {
            "rating_event_id": "event_excluded",
            "company_id": "company_0",
            "company_name": "Company 0",
            "agency_name": "care",
            "rating_date": "2025-07-01",
            "rationale_doc_id": "doc_0",
            "current_rating": "CARE A4",
            "long_term_rating": "",
            "normalized_long_term_label": "",
            "normalized_long_term_rank": "",
            "normalized_scale_type": "short_term",
            "is_withdrawn": False,
            "is_issuer_not_cooperating": False,
            "is_withdrawn_normalized": False,
            "is_issuer_not_cooperating_normalized": False,
        }
    )

    pd.DataFrame(feature_rows).to_csv(features_path, index=False)
    pd.DataFrame(event_rows).to_csv(rating_events_path, index=False)
    pd.DataFrame(rationale_rows).to_csv(rationale_features_path, index=False)

    training_outputs = build_rating_training_dataset(
        financial_features_path=features_path,
        rating_events_path=rating_events_path,
        rationale_features_path=rationale_features_path,
        output_dir=tmp_path / "training",
    )
    model_outputs = train_agency_specific_models(
        training_dataset_path=training_outputs["agency_training_dataset"],
        output_dir=tmp_path / "models",
    )

    latest_features_path = tmp_path / "latest_features.csv"
    pd.DataFrame(
        [
            {
                "company_id": "unrated_company",
                "company_name": "Unrated Company",
                "sub_industry": "Other Agricultural Products",
                "period": "2025-03-31",
                "revenue_crore": 180,
                "ebitda_margin_pct": 11.0,
                "pat_margin_pct": 4.8,
                "debt_to_equity": 0.9,
                "interest_coverage": 3.2,
                "working_capital_days": 95,
                "receivables_days": 45,
                "inventory_days": 22,
                "networth_crore": 135,
                "total_borrowings_crore": 54,
                "cash_to_borrowings": 0.35,
                "asset_turnover": 1.25,
            }
        ]
    ).to_csv(latest_features_path, index=False)

    simulation_outputs = simulate_unrated_companies(
        latest_financial_features_path=latest_features_path,
        rating_events_path=tmp_path / "empty_rating_events.csv",
        model_dir=model_outputs["models_dir"],
        output_dir=tmp_path / "simulations",
        training_dataset_path=training_outputs["agency_training_dataset"],
        training_exclusions_path=training_outputs["agency_training_exclusions"],
    )

    training_frame = pd.read_csv(training_outputs["agency_training_dataset"])
    assert not training_frame.empty
    assert "feature_coverage" in training_frame.columns
    assert "prior_agency_rating_rank" in training_frame.columns
    assert "industry_revenue_percentile" in training_frame.columns
    assert "context_coverage" in training_frame.columns
    exclusions = pd.read_csv(training_outputs["agency_training_exclusions"])
    assert "non_long_term_rating" in set(exclusions["eligibility_status"])

    metrics = pd.read_csv(model_outputs["agency_model_metrics"])
    care_metrics = metrics[metrics["agency_name"] == "care"].iloc[0]
    assert care_metrics["status"] == "trained"

    simulations = pd.read_csv(simulation_outputs["simulation_results"])
    assert not simulations.empty
    assert {"validation", "simulation"} <= set(simulations["population_type"])
    assert set(simulations["agency"]) == {"care"}
    simulated_row = simulations[simulations["population_type"] == "simulation"].iloc[0]
    assert simulated_row["predicted_rating"] in {"A+", "A"}
    assert simulated_row["rating_range"]
    assert simulated_row["probability_distribution_json"]
    assert simulated_row["confidence"] > 0


def test_build_financial_window_features_adds_trends() -> None:
    history = pd.DataFrame(
        [
            {
                "period": "2022-03-31",
                "period_date": "2022-03-31",
                "revenue_crore": 100,
                "ebitda_margin_pct": 10,
                "pat_margin_pct": 4,
                "debt_to_equity": 1.4,
                "interest_coverage": 2.1,
                "working_capital_days": 125,
                "receivables_days": 60,
                "inventory_days": 65,
                "networth_crore": 75,
                "total_borrowings_crore": 48,
                "total_assets_crore": 130,
                "cfo_to_debt": 0.18,
                "cash_to_borrowings": 0.12,
                "asset_turnover": 0.8,
                "revenue_growth_pct": 5,
                "profit_growth_pct": 2,
            },
            {
                "period": "2023-03-31",
                "period_date": "2023-03-31",
                "revenue_crore": 120,
                "ebitda_margin_pct": 11,
                "pat_margin_pct": 4.5,
                "debt_to_equity": 1.2,
                "interest_coverage": 2.5,
                "working_capital_days": 118,
                "receivables_days": 57,
                "inventory_days": 61,
                "networth_crore": 82,
                "total_borrowings_crore": 46,
                "total_assets_crore": 136,
                "cfo_to_debt": 0.2,
                "cash_to_borrowings": 0.15,
                "asset_turnover": 0.88,
                "revenue_growth_pct": 20,
                "profit_growth_pct": 8,
            },
            {
                "period": "2024-03-31",
                "period_date": "2024-03-31",
                "revenue_crore": 150,
                "ebitda_margin_pct": 12,
                "pat_margin_pct": 5.2,
                "debt_to_equity": 1.0,
                "interest_coverage": 3.1,
                "working_capital_days": 111,
                "receivables_days": 53,
                "inventory_days": 58,
                "networth_crore": 94,
                "total_borrowings_crore": 43,
                "total_assets_crore": 144,
                "cfo_to_debt": 0.27,
                "cash_to_borrowings": 0.19,
                "asset_turnover": 0.97,
                "revenue_growth_pct": 25,
                "profit_growth_pct": 14,
            },
        ]
    )
    history["period_date"] = pd.to_datetime(history["period_date"])

    row = _build_financial_window_features(history)

    assert row["matched_financial_period"] == "2024-03-31"
    assert row["history_periods_available"] == 3
    assert row["revenue_crore_avg3y"] == 123.3333
    assert row["revenue_crore_delta1y"] == 30.0
    assert row["debt_to_equity_delta1y"] == -0.2
    assert row["profitability_trend_positive"] == 1
    assert row["leverage_trend_improving"] == 1
    assert row["working_capital_trend_improving"] == 1


def test_training_dataset_populates_prior_rating_features(tmp_path: Path) -> None:
    features_path = tmp_path / "financial_features.csv"
    rating_events_path = tmp_path / "rating_events.csv"
    rationale_features_path = tmp_path / "rationale_features.csv"

    pd.DataFrame(
        [
            {
                "company_id": "alpha",
                "company_name": "Alpha Agro",
                "sub_industry": "Other Agricultural Products",
                "period": "2023-03-31",
                "period_date": "2023-03-31",
                "revenue_crore": 100,
                "ebitda_margin_pct": 10,
                "pat_margin_pct": 4,
                "debt_to_equity": 1.2,
                "interest_coverage": 2.4,
                "working_capital_days": 120,
                "receivables_days": 60,
                "inventory_days": 40,
                "networth_crore": 70,
                "total_borrowings_crore": 45,
            },
            {
                "company_id": "alpha",
                "company_name": "Alpha Agro",
                "sub_industry": "Other Agricultural Products",
                "period": "2024-03-31",
                "period_date": "2024-03-31",
                "revenue_crore": 130,
                "ebitda_margin_pct": 11.5,
                "pat_margin_pct": 5,
                "debt_to_equity": 1.0,
                "interest_coverage": 3.0,
                "working_capital_days": 110,
                "receivables_days": 54,
                "inventory_days": 36,
                "networth_crore": 82,
                "total_borrowings_crore": 43,
            },
            {
                "company_id": "beta",
                "company_name": "Beta Agro",
                "sub_industry": "Other Agricultural Products",
                "period": "2024-03-31",
                "period_date": "2024-03-31",
                "revenue_crore": 95,
                "ebitda_margin_pct": 8,
                "pat_margin_pct": 3.5,
                "debt_to_equity": 1.5,
                "interest_coverage": 2.0,
                "working_capital_days": 135,
                "receivables_days": 70,
                "inventory_days": 50,
                "networth_crore": 60,
                "total_borrowings_crore": 48,
            },
        ]
    ).to_csv(features_path, index=False)

    pd.DataFrame(
        [
            {
                "rating_event_id": "event_1",
                "company_id": "alpha",
                "company_name": "Alpha Agro",
                "agency_name": "care",
                "rating_date": "2024-08-01",
                "rationale_doc_id": "doc_1",
                "current_rating": "CARE BBB",
                "long_term_rating": "CARE BBB",
                "normalized_long_term_label": "BBB",
                "normalized_long_term_rank": 8,
                "normalized_scale_type": "long_term",
                "is_withdrawn": False,
                "is_issuer_not_cooperating": False,
                "is_withdrawn_normalized": False,
                "is_issuer_not_cooperating_normalized": False,
            },
            {
                "rating_event_id": "event_2",
                "company_id": "alpha",
                "company_name": "Alpha Agro",
                "agency_name": "care",
                "rating_date": "2025-08-01",
                "rationale_doc_id": "doc_2",
                "current_rating": "CARE BBB+",
                "long_term_rating": "CARE BBB+",
                "normalized_long_term_label": "BBB+",
                "normalized_long_term_rank": 7,
                "normalized_scale_type": "long_term",
                "is_withdrawn": False,
                "is_issuer_not_cooperating": False,
                "is_withdrawn_normalized": False,
                "is_issuer_not_cooperating_normalized": False,
            },
        ]
    ).to_csv(rating_events_path, index=False)

    pd.DataFrame(
        [
            {"rationale_doc_id": "doc_1", "agency_name": "care", "company_name": "Alpha Agro"},
            {"rationale_doc_id": "doc_2", "agency_name": "care", "company_name": "Alpha Agro"},
        ]
    ).to_csv(rationale_features_path, index=False)

    outputs = build_rating_training_dataset(
        financial_features_path=features_path,
        rating_events_path=rating_events_path,
        rationale_features_path=rationale_features_path,
        output_dir=tmp_path / "training",
        min_days_before_rating=90,
    )

    training_frame = pd.read_csv(outputs["agency_training_dataset"]).sort_values("rating_date")
    second_row = training_frame.iloc[-1]
    assert second_row["prior_agency_rating_available"] == 1
    assert second_row["prior_agency_rating_rank"] == 8
    assert second_row["industry_peer_sample_size"] >= 1
