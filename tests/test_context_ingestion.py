from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.credit_intel.context_ingestion import build_context_feature_dataset, normalize_context_frame


def test_normalize_context_frame_maps_aliases() -> None:
    frame = pd.DataFrame(
        [
            {
                "Company Code": "ALPHA_01",
                "Name": "Alpha Agro",
                "As Of": "2025-03-31",
                "Bureau Score": "712",
                "Criminal Flag": "yes",
                "Plan Progress Score": "7.5",
                "Source": "probe42_context",
            }
        ]
    )

    normalized = normalize_context_frame(frame)

    row = normalized.iloc[0]
    assert row["company_id"] == "ALPHA_01"
    assert row["company_name"] == "Alpha Agro"
    assert row["promoter_bureau_score"] == 712
    assert bool(row["criminal_case_flag"]) is True
    assert row["plan_progress_score"] == 7.5
    assert row["source_type"] == "probe42_context"


def test_build_context_feature_dataset_writes_outputs(tmp_path: Path) -> None:
    input_path = tmp_path / "context.csv"
    output_dir = tmp_path / "outputs"
    pd.DataFrame(
        [
            {
                "company_id": "ALPHA_01",
                "company_name": "Alpha Agro",
                "as_of_date": "2025-03-31",
                "promoter_bureau_score": 705,
            }
        ]
    ).to_csv(input_path, index=False)

    outputs = build_context_feature_dataset(
        input_path=input_path,
        output_dir=output_dir,
    )

    context_frame = pd.read_csv(outputs["context_features"])
    assert len(context_frame) == 1
    assert "promoter_bureau_score" in context_frame.columns
