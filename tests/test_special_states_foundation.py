from __future__ import annotations

from pathlib import Path

from src.parsers.acuite_parser import AcuiteParser
from src.parsers.icra_parser import IcraParser


ICRA_INC_TEXT = """
May 29, 2024
Aarey Drugs & Pharmaceuticals Limited: Continues to remain under issuer Non-Cooperating category
Summary of rating action
Long Term-Fund Based-Cash Credit 30.00 30.00 [ICRA]B+ (Stable); ISSUER NOT COOPERATING*; Rating continues to remain under 'Issuer Not Cooperating' category
Short Term-Non Fund Based-Others 15.00 15.00 [ICRA]A4; ISSUER NOT COOPERATING*; Rating continues to remain under 'Issuer Not Cooperating' category
Rationale
ICRA has kept the Long-Term and Short-Term ratings in the 'Issuer Not Cooperating' category.
Analytical approach
Consolidation/Standalone Standalone
"""

ICRA_SINGLE_AMOUNT_TEXT = """
November 24, 2025
Dalmia Bharat Sugar and Industries Limited: [ICRA]A1+ assigned
Summary of rating action
Instrument* Current rated amount
(Rs. crore) Rating action
Short term - Commercial paper 500.00 [ICRA]A1+; assigned
Total 500.00
Rationale
"""

ICRA_OLD_SINGLE_AMOUNT_LAYOUT = """
April 05, 2017
Bombay Super Hybrid Seeds Private Limited
Rating Action
Instrument* Rated Amount
(in crore)
Rating Action
Fund-based Cash Credit 8.00 [ICRA]B+ (Stable) reaffirmed
Fund-based Term Loan 2.21 [ICRA]B+ (Stable) reaffirmed
Fund-based EPC/PCFC/FBD* (0.50) [ICRA]A4 reaffirmed
Unallocated Limits 0.29 [ICRA]B+ (Stable)/A4 reaffirmed
Total 10.50
Rationale
"""

ICRA_MONTH_YEAR_ONLY_DATE_TEXT = """
Bombay Super Hybrid Seeds Private Limited
Instrument Amount Rating Action
Cash Credit Limits Rs. 4.90 crore [ICRA]B+ assigned
December 2015
"""


ACUITE_WITHDRAWN_TEXT = """
Press Release
AAREY DRUGS AND PHARMACEUTICALS LIMITED
March 04, 2025
Product Quantum (Rs. Cr) Long Term Rating Short Term Rating
Bank Loan Ratings 54.44 ACUITE BBB- | Stable | Downgraded -
Bank Loan Ratings 5.06 Not Applicable | Withdrawn -
Bank Loan Ratings 11.50 - ACUITE A3 | Downgraded
Bank Loan Ratings 8.55 - Not Applicable | Withdrawn
Total Outstanding Quantum (Rs. Cr) 65.94 - -
Rating Rationale
Acuite has downgraded the long-term rating to 'ACUITE BBB-' and the short-term rating to 'ACUITE A3'.
"""


def test_icra_parser_flags_issuer_not_cooperating() -> None:
    bundle = IcraParser().parse(
        pdf_path=Path("/tmp/ICRA_Aarey.pdf"),
        source_file="ICRA_Aarey.pdf",
        text=ICRA_INC_TEXT,
        text_hash="hashhashhash1",
        extractor_used="unit_test",
    )
    assert len(bundle.rating_events) == 2
    assert all(event.is_issuer_not_cooperating for event in bundle.rating_events)


def test_icra_parser_extracts_single_amount_summary_rows() -> None:
    bundle = IcraParser().parse(
        pdf_path=Path("/tmp/ICRA_Dalmia.pdf"),
        source_file="ICRA_Dalmia.pdf",
        text=ICRA_SINGLE_AMOUNT_TEXT,
        text_hash="hashhashhash3",
        extractor_used="unit_test",
    )
    assert len(bundle.rating_events) == 1
    assert bundle.rating_events[0].short_term_rating == "A1+"
    assert bundle.rating_events[0].facility_amount == 500.0


def test_icra_parser_extracts_old_single_amount_layout() -> None:
    bundle = IcraParser().parse(
        pdf_path=Path("/tmp/ICRA_Bombay.pdf"),
        source_file="ICRA_Bombay.pdf",
        text=ICRA_OLD_SINGLE_AMOUNT_LAYOUT,
        text_hash="hashhashhash4",
        extractor_used="unit_test",
    )
    assert len(bundle.rating_events) == 4
    assert any(event.long_term_rating == "B+" for event in bundle.rating_events)
    assert any(event.short_term_rating == "A4" for event in bundle.rating_events)


def test_icra_parser_infers_month_year_date_as_first_of_month() -> None:
    bundle = IcraParser().parse(
        pdf_path=Path("/tmp/ICRA_Bombay_month_year.pdf"),
        source_file="ICRA_Bombay_month_year.pdf",
        text=ICRA_MONTH_YEAR_ONLY_DATE_TEXT,
        text_hash="hashhashhash5",
        extractor_used="unit_test",
    )
    assert bundle.rationale_document.doc_date.isoformat() == "2015-12-01"


def test_acuite_parser_flags_withdrawn_rows() -> None:
    bundle = AcuiteParser().parse(
        pdf_path=Path("/tmp/Acuite_Aarey.pdf"),
        source_file="Acuite_Aarey.pdf",
        text=ACUITE_WITHDRAWN_TEXT,
        text_hash="hashhashhash2",
        extractor_used="unit_test",
    )
    assert len(bundle.rating_events) >= 4
    assert any(event.is_withdrawn for event in bundle.rating_events)
