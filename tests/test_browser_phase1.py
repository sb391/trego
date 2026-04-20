from pathlib import Path

import pandas as pd

from src.io_utils import build_company_id, load_input_companies, normalize_code, normalize_company_name
from src.models import CorporateRecord
from src.screener_matcher import candidate_from_payload, choose_best_match, extract_company_slug


def test_normalize_company_name_and_code() -> None:
    assert normalize_company_name("Sun Pharma. Inds Ltd.") == "sun pharma inds ltd"
    assert normalize_code(500087.0) == "500087"
    assert normalize_code(" sunpharma ") == "SUNPHARMA"
    assert normalize_code(float("nan")) is None


def test_build_company_id_prefers_nse_then_bse() -> None:
    assert build_company_id("Sun Pharma Industries", "SUNPHARMA", "500087", 0) == "Sun_Pharma_Industries__SUNPHARMA"
    assert build_company_id("Abbott India", None, "500488", 1) == "Abbott_India__500488"


def test_load_input_companies_deduplicates_rows(tmp_path: Path) -> None:
    frame = pd.DataFrame(
        [
            {"Name": "Sun Pharma Industries", "NSE Code": "SUNPHARMA", "BSE Code": 500087.0},
            {"Name": "Sun Pharma Industries", "NSE Code": "SUNPHARMA", "BSE Code": 500087.0},
            {"Name": "Abbott India", "NSE Code": "ABBOTINDIA", "BSE Code": 500488.0},
        ]
    )
    input_path = tmp_path / "input.csv"
    frame.to_csv(input_path, index=False)

    records = load_input_companies(input_path)

    assert len(records) == 2
    assert records[0].company_id == "Sun_Pharma_Industries__SUNPHARMA"
    assert records[1].company_id == "Abbott_India__ABBOTINDIA"


def test_candidate_parsing_extracts_slug_and_absolute_url() -> None:
    candidate = candidate_from_payload(
        {
            "id": 3245,
            "name": "Sun Pharmaceutical Industries Ltd",
            "url": "/company/SUNPHARMA/consolidated/",
        },
        rank=1,
    )

    assert candidate.company_slug == "SUNPHARMA"
    assert candidate.url == "https://www.screener.in/company/SUNPHARMA/consolidated/"
    assert extract_company_slug(candidate.url) == "SUNPHARMA"


def test_choose_best_match_prefers_nse_code_match() -> None:
    company = CorporateRecord(
        row_index=0,
        company_id="Sun_Pharma_Industries__SUNPHARMA",
        company_name="Sun Pharma Industries",
        search_name="Sun Pharma Industries",
        normalized_name="sun pharma industries",
        normalized_tokens=("sun", "pharma", "industries"),
        nse_code="SUNPHARMA",
        bse_code="500087",
        isin_code=None,
        industry_group=None,
        industry=None,
    )
    candidates = [
        candidate_from_payload(
            {
                "id": 3244,
                "name": "Sun Pharma Advanced Research Company Ltd",
                "url": "/company/SPARC/",
            },
            rank=1,
        ),
        candidate_from_payload(
            {
                "id": 3245,
                "name": "Sun Pharmaceutical Industries Ltd",
                "url": "/company/SUNPHARMA/consolidated/",
            },
            rank=2,
        ),
    ]

    decision = choose_best_match(company, candidates, auto_threshold=0.86, ambiguity_gap_threshold=0.08)

    assert decision.status == "matched"
    assert decision.matched_candidate is not None
    assert decision.matched_candidate.company_slug == "SUNPHARMA"
    assert "NSE code" in decision.reason


def test_choose_best_match_marks_close_candidates_as_ambiguous() -> None:
    company = CorporateRecord(
        row_index=0,
        company_id="Aarti_Pharma__AARTIPHARM",
        company_name="Aarti Pharma",
        search_name="Aarti Pharma",
        normalized_name="aarti pharma",
        normalized_tokens=("aarti", "pharma"),
        nse_code=None,
        bse_code=None,
        isin_code=None,
        industry_group=None,
        industry=None,
    )
    candidates = [
        candidate_from_payload(
            {
                "id": 1,
                "name": "Aarti Pharma Labs Ltd",
                "url": "/company/AARTIPHARM/",
            },
            rank=1,
        ),
        candidate_from_payload(
            {
                "id": 2,
                "name": "Aarti Pharmachem Ltd",
                "url": "/company/AARTIPHARMACHEM/",
            },
            rank=2,
        ),
    ]

    decision = choose_best_match(company, candidates, auto_threshold=0.95, ambiguity_gap_threshold=0.10)

    assert decision.status == "ambiguous"
    assert decision.matched_candidate is None
    assert decision.scored_candidates[0].total_score >= decision.scored_candidates[1].total_score
