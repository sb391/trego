from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.credit_intel.simulation_pipeline import build_rating_training_dataset


def test_training_dataset_includes_scale_peer_trajectory_features(tmp_path: Path) -> None:
    features_path = tmp_path / "financial_features.csv"
    rating_events_path = tmp_path / "rating_events.csv"
    rationale_features_path = tmp_path / "rationale_features.csv"

    pd.DataFrame(
        [
            {
                "company_id": "target",
                "company_name": "Target Agro",
                "sub_industry": "Other Agricultural Products",
                "period": "2022-03-31",
                "period_date": "2022-03-31",
                "revenue_crore": 100,
                "ebitda_margin_pct": 10,
                "pat_margin_pct": 4,
                "debt_to_equity": 1.2,
                "interest_coverage": 2.0,
                "working_capital_days": 120,
                "receivables_days": 60,
                "inventory_days": 42,
                "networth_crore": 70,
                "total_borrowings_crore": 45,
            },
            {
                "company_id": "target",
                "company_name": "Target Agro",
                "sub_industry": "Other Agricultural Products",
                "period": "2023-03-31",
                "period_date": "2023-03-31",
                "revenue_crore": 115,
                "ebitda_margin_pct": 10.5,
                "pat_margin_pct": 4.2,
                "debt_to_equity": 1.15,
                "interest_coverage": 2.2,
                "working_capital_days": 116,
                "receivables_days": 58,
                "inventory_days": 40,
                "networth_crore": 77,
                "total_borrowings_crore": 46,
            },
            {
                "company_id": "target",
                "company_name": "Target Agro",
                "sub_industry": "Other Agricultural Products",
                "period": "2024-03-31",
                "period_date": "2024-03-31",
                "revenue_crore": 132,
                "ebitda_margin_pct": 11.1,
                "pat_margin_pct": 4.8,
                "debt_to_equity": 1.05,
                "interest_coverage": 2.7,
                "working_capital_days": 111,
                "receivables_days": 54,
                "inventory_days": 37,
                "networth_crore": 85,
                "total_borrowings_crore": 44,
            },
            {
                "company_id": "peer",
                "company_name": "Peer Agro",
                "sub_industry": "Other Agricultural Products",
                "period": "2020-03-31",
                "period_date": "2020-03-31",
                "revenue_crore": 110,
                "ebitda_margin_pct": 9.0,
                "pat_margin_pct": 3.5,
                "debt_to_equity": 1.4,
                "interest_coverage": 1.8,
                "working_capital_days": 128,
                "receivables_days": 63,
                "inventory_days": 45,
                "networth_crore": 68,
                "total_borrowings_crore": 48,
            },
            {
                "company_id": "peer",
                "company_name": "Peer Agro",
                "sub_industry": "Other Agricultural Products",
                "period": "2021-03-31",
                "period_date": "2021-03-31",
                "revenue_crore": 125,
                "ebitda_margin_pct": 9.5,
                "pat_margin_pct": 3.9,
                "debt_to_equity": 1.3,
                "interest_coverage": 2.0,
                "working_capital_days": 123,
                "receivables_days": 60,
                "inventory_days": 44,
                "networth_crore": 75,
                "total_borrowings_crore": 47,
            },
            {
                "company_id": "peer",
                "company_name": "Peer Agro",
                "sub_industry": "Other Agricultural Products",
                "period": "2022-03-31",
                "period_date": "2022-03-31",
                "revenue_crore": 143,
                "ebitda_margin_pct": 10.0,
                "pat_margin_pct": 4.3,
                "debt_to_equity": 1.2,
                "interest_coverage": 2.4,
                "working_capital_days": 118,
                "receivables_days": 57,
                "inventory_days": 41,
                "networth_crore": 83,
                "total_borrowings_crore": 46,
            },
            {
                "company_id": "peer",
                "company_name": "Peer Agro",
                "sub_industry": "Other Agricultural Products",
                "period": "2023-03-31",
                "period_date": "2023-03-31",
                "revenue_crore": 167,
                "ebitda_margin_pct": 10.8,
                "pat_margin_pct": 4.9,
                "debt_to_equity": 1.1,
                "interest_coverage": 2.9,
                "working_capital_days": 112,
                "receivables_days": 53,
                "inventory_days": 39,
                "networth_crore": 93,
                "total_borrowings_crore": 45,
            },
            {
                "company_id": "peer",
                "company_name": "Peer Agro",
                "sub_industry": "Other Agricultural Products",
                "period": "2024-03-31",
                "period_date": "2024-03-31",
                "revenue_crore": 192,
                "ebitda_margin_pct": 11.4,
                "pat_margin_pct": 5.4,
                "debt_to_equity": 1.0,
                "interest_coverage": 3.2,
                "working_capital_days": 108,
                "receivables_days": 50,
                "inventory_days": 36,
                "networth_crore": 105,
                "total_borrowings_crore": 44,
            },
        ]
    ).to_csv(features_path, index=False)

    pd.DataFrame(
        [
            {
                "rating_event_id": "event_1",
                "company_id": "target",
                "company_name": "Target Agro",
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
            }
        ]
    ).to_csv(rating_events_path, index=False)

    pd.DataFrame([{"rationale_doc_id": "doc_1", "agency_name": "care", "company_name": "Target Agro"}]).to_csv(
        rationale_features_path,
        index=False,
    )

    outputs = build_rating_training_dataset(
        financial_features_path=features_path,
        rating_events_path=rating_events_path,
        rationale_features_path=rationale_features_path,
        output_dir=tmp_path / "training",
        min_days_before_rating=90,
    )

    training_frame = pd.read_csv(outputs["agency_training_dataset"])
    row = training_frame.iloc[0]
    assert row["scale_peer_sample_size"] > 0
    assert pd.notna(row["scale_peer_forward_revenue_cagr"])
