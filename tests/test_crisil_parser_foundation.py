from __future__ import annotations

from pathlib import Path

from src.parsers.crisil_parser import CrisilParser


CRISIL_SAMPLE_TEXT = """
Rating Rationale December 01, 2025 | Mumbai
Medicamen Biotech Limited Ratings reaffirmed at 'Crisil BBB- / Stable / Crisil A3 ' Rating Action Total Bank Loan Facilities Rated Rs.42 Crore Long Term Rating Crisil BBB-/Stable (Reaffirmed) Short Term Rating Crisil A3 (Reaffirmed)

Detailed Rationale Crisil Ratings has reaffirmed its 'Crisil BBB-/Stable/Crisil A3' ratings on the bank facilities of Medicamen Biotech Ltd.
Analytical Approach Crisil Ratings has combined the business and financial risk profiles of MBL and its subsidiary.
Key Rating Drivers - Strengths Strong track record in the pharmaceutical industry: The promoters have experience of around three decades in the pharmaceuticals industry.
Key Rating Drivers - Weaknesses Modest scale of operations: Temporary disturbances in the overseas market has kept the group's scale of operations modest.
Liquidity Adequate Bank limit utilisation averaged 70.16% for the 12 months through October 2025.
Rating sensitivity factors Upwards factors • Growth in revenue to over Rs 200 crore and stable operating margin. Downward factors • Stretch in working capital cycle and moderation in profitability.
"""

CRISIL_BULLETIN_TEXT = """
Credit Bulletin
February 21, 2025 | Mumbai
Update on Gulshan Polyols Limited
Annexure - Details of Bank Lenders & Facilities
Facility
Amount (Rs.Crore)
Name of Lender
Rating
Cash Credit
130
State Bank of India
Crisil A/Stable
Cash Credit
100
The Hongkong and Shanghai Banking Corporation Limited
Crisil A/Stable
Long Term Loan
156.92
State Bank of India
Crisil A/Stable
Non-Fund Based Limit
40
State Bank of India
Crisil A1
Criteria Details
"""

CRISIL_WITHDRAWN_TEXT = """
Rating Rationale
October 28, 2021 | Mumbai
Flex Foods Limited
Rating migrated to 'CRISIL BB+/Stable'; Rating Withdrawn
Rating Action
Total Bank Loan Facilities Rated
Rs.9 Crore
Long Term Rating
&
CRISIL BB+/Stable (Migrated from 'CRISIL BB+/Stable ISSUER NOT COOPERATING*'; Rating Withdrawn)
Detailed Rationale
"""

CRISIL_FIXED_DEPOSIT_TEXT = """
Rating Rationale
February 02, 2023 | Mumbai
The Sukhjit Starch and Chemicals Limited
Rating Action
Total Bank Loan Facilities Rated
Rs.380 Crore
Long Term Rating
CRISIL A+/Stable
Short Term Rating
CRISIL A1
Rs.80 Crore Fixed Deposits
CRISIL A+/Stable
Detailed Rationale
"""

CRISIL_LEGACY_TEXT = """
May 27, 2011
Mumbai
CRISIL downgrades ratings on Raj Agro Mills to D/P5; ratings suspended
Rs.100.0 Million Cash Credit Limit
D (Downgraded from B+/Stable and Suspended)
Rs.120.0 Million Term Loan
D (Downgraded from B+/Stable and Suspended)
Rs.145.0 Million Letter of Credit
P5 (Downgraded from P4 and Suspended)
"""


def test_crisil_parser_happy_path() -> None:
    parser = CrisilParser()
    bundle = parser.parse(
        pdf_path=Path("/tmp/Crisil_Medicamen.pdf"),
        source_file="Crisil_Medicamen.pdf",
        text=CRISIL_SAMPLE_TEXT,
        text_hash="abc123def456",
        extractor_used="unit_test",
    )

    assert bundle.company.company_name == "Medicamen Biotech Limited"
    assert bundle.rationale_document.agency_name == "crisil"
    assert bundle.rationale_document.doc_date.isoformat() == "2025-12-01"
    assert len(bundle.rating_events) == 2
    assert bundle.rating_events[0].long_term_rating == "BBB-"
    assert bundle.rating_events[1].short_term_rating == "A3"
    assert bundle.rationale_features.liquidity_label == "Adequate"
    assert bundle.rationale_features.strengths_json
    assert bundle.rationale_features.weaknesses_json


def test_crisil_parser_extracts_credit_bulletin_annexure_ratings() -> None:
    bundle = CrisilParser().parse(
        pdf_path=Path("/tmp/Crisil_Gulshan.pdf"),
        source_file="Crisil_Gulshan.pdf",
        text=CRISIL_BULLETIN_TEXT,
        text_hash="crisilgulshan123",
        extractor_used="unit_test",
    )

    assert len(bundle.rating_events) == 3
    cash_credit = next(event for event in bundle.rating_events if event.instrument_type == "Cash Credit")
    assert cash_credit.long_term_rating == "A"
    assert cash_credit.facility_amount == 230.0
    assert any(event.short_term_rating == "A1" for event in bundle.rating_events)


def test_crisil_parser_extracts_withdrawn_top_label_rating() -> None:
    bundle = CrisilParser().parse(
        pdf_path=Path("/tmp/Crisil_FlexFoods.pdf"),
        source_file="Crisil_FlexFoods.pdf",
        text=CRISIL_WITHDRAWN_TEXT,
        text_hash="crisillabel123",
        extractor_used="unit_test",
    )

    assert len(bundle.rating_events) == 1
    assert bundle.rating_events[0].long_term_rating == "BB+"
    assert bundle.rating_events[0].is_withdrawn


def test_crisil_parser_extracts_fixed_deposit_row() -> None:
    bundle = CrisilParser().parse(
        pdf_path=Path("/tmp/Crisil_Sukhjit.pdf"),
        source_file="Crisil_Sukhjit.pdf",
        text=CRISIL_FIXED_DEPOSIT_TEXT,
        text_hash="crisilsukhjit123",
        extractor_used="unit_test",
    )

    assert len(bundle.rating_events) == 3
    fixed_deposit = next(event for event in bundle.rating_events if event.instrument_type == "Fixed Deposits")
    assert fixed_deposit.long_term_rating == "A+"
    assert fixed_deposit.facility_amount == 80.0


def test_crisil_parser_extracts_legacy_million_rows_and_p_scale() -> None:
    bundle = CrisilParser().parse(
        pdf_path=Path("/tmp/Crisil_RajAgro.pdf"),
        source_file="Crisil_RajAgro.pdf",
        text=CRISIL_LEGACY_TEXT,
        text_hash="crisillegacy123",
        extractor_used="unit_test",
    )

    assert bundle.company.company_name == "Raj Agro Mills"
    assert len(bundle.rating_events) == 3
    assert any(event.instrument_type == "Cash Credit Limit" and event.long_term_rating == "D" for event in bundle.rating_events)
    assert any(event.instrument_type == "Letter of Credit" and event.short_term_rating == "P5" for event in bundle.rating_events)
