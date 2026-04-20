from __future__ import annotations

from pathlib import Path

from src.parsers.infomerics_parser import InfomericsParser


INFOMERICS_SAMPLE_TEXT = """
Amir Chand Jagdish Kumar Exports Limited July 29, 2025
Detailed Rationale
Short Term
Bank Facilities
795.00
IVR A1
Simple
"""

INFOMERICS_TABLE_TEXT = """
K.M. Sugar Mills Limited
March 31, 2026
Ratings
Security/ Facility Amount
(Rs. crore) Current Ratings Previous Ratings Rating
Action
Complexity
Indicator
Long Term Bank
Facilities
287.31
IVR A-; RWDI
(IVR Single A Minus placed on
Rating Watch with Developing
Implications)
IVR A-; Stable
(IVR Single A Minus with Stable
Outlook)
Rating placed on
watch with
developing
implications
Simple
Short Term Bank
Facilities 7.00
IVR A2+
(IVR A Two Plus placed on Rating
Watch with Developing
Implications)
IVR A2+
(IVR A Two Plus)
Rating placed on
watch with
developing
implications
Simple
Total
294.31
Detailed Rationale
"""

INFOMERICS_DATE_SPACE_TEXT = """
Amir Chand Jagdish Kumar (Exports) Limited
February 15 , 2022
Ratings
Instrument Facility
Amount
(Rs. crore)
Ratings
Rating
Action
Complexity
Indicator
Long term Bank
Facilities - Cash
Credit
135.00
IVR A-/ Stable
(IVR Single A Minus with Stable outlook)
Reaffirmed
Simple
Total
135.00
Detailed Rationale
"""


def test_infomerics_parser_keeps_short_term_scale() -> None:
    bundle = InfomericsParser().parse(
        pdf_path=Path("/tmp/Infomerics_AmirChand.pdf"),
        source_file="Infomerics_AmirChand.pdf",
        text=INFOMERICS_SAMPLE_TEXT,
        text_hash="infomerics123456",
        extractor_used="unit_test",
    )

    assert len(bundle.rating_events) == 1
    assert bundle.rating_events[0].short_term_rating == "A1"
    assert bundle.rating_events[0].long_term_rating is None


def test_infomerics_parser_extracts_multiline_current_and_previous_ratings() -> None:
    bundle = InfomericsParser().parse(
        pdf_path=Path("/tmp/Infomerics_KM_Sugar.pdf"),
        source_file="Infomerics_KM_Sugar.pdf",
        text=INFOMERICS_TABLE_TEXT,
        text_hash="infomericskm123",
        extractor_used="unit_test",
    )

    assert len(bundle.rating_events) == 2
    assert bundle.rating_events[0].long_term_rating == "A-"
    assert bundle.rating_events[0].previous_rating == "IVR A-; Stable"
    assert bundle.rating_events[1].short_term_rating == "A2+"


def test_infomerics_parser_handles_space_before_comma_in_date() -> None:
    bundle = InfomericsParser().parse(
        pdf_path=Path("/tmp/Infomerics_AmirChand_2022.pdf"),
        source_file="Infomerics_AmirChand_2022.pdf",
        text=INFOMERICS_DATE_SPACE_TEXT,
        text_hash="infomericsdate123",
        extractor_used="unit_test",
    )

    assert bundle.rationale_document.doc_date.isoformat() == "2022-02-15"
    assert len(bundle.rating_events) == 1
    assert bundle.rating_events[0].long_term_rating == "A-"
