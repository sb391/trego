from __future__ import annotations

from pathlib import Path

from src.credit_intel.simulation_pipeline import _should_render_html_in_browser
from src.parsers.brickwork_parser import BrickworkParser
from src.parsers.care_parser import CareParser
from src.parsers.icra_parser import IcraParser
from src.parsers.india_ratings_parser import IndiaRatingsParser
from src.utils.text import find_first_date, parse_date_string


CARE_TEXT = """
Press Release
Ambar Protein Industries Limited
July 05,2024
Facilities/Instruments Amount (₹ crore) Rating1 Rating Action
Long Term Bank Facilities 13.54 (Reduced from 15.14) CARE BB+; Stable Reaffirmed
Long Term / Short Term Bank Facilities 5.00 CARE BB+; Stable / CARE A4+ Reaffirmed
Details of instruments/facilities in Annexure-1.
"""

CARE_OLD_LAYOUT_TEXT = """
Press Release
DCM Shriram Industries Limited
April 09, 2026
Facilities/Instruments Amount (₹ crore) Rating1 Rating Action
Long-term bank facilities 441.79 (Reduced from 598.29) CARE A-; Stable Downgraded from CARE A+ and removed from Rating Watch with Negative Implications; Stable outlook assigned
Short-term bank facilities 11.00 (Reduced from 155.92) CARE A2+ Downgraded from CARE A1+ and removed from Rating Watch with Negative Implications
Fixed deposit 15.00 CARE A-; Stable Downgraded from CARE A+ and removed from Rating Watch with Negative Implications; Stable outlook assigned
Long-term bank facilities - - Withdrawn
Details of instruments/facilities in Annexure-1.
"""

CARE_CREDIT_UPDATE_TEXT = """
CARE Ratings Ltd.
Press Release
Credit update-Adani Wilmar Limited
January 09, 2025
Updates
As per stock exchange announcement on December 30, 2024, Adani Wilmar Limited (AWL; rated CARE AA-; Stable / CARE A1+) announced changes to shareholding.
Please refer to the following link for the previous detailed rationale that captures key rating drivers and rating sensitivities: Click here
"""

ICRA_TEXT = """
December 22, 2025
AVT Natural Products Limited: Ratings reaffirmed; rated amount enhanced
Summary of rating action
Long-term - Fund based - Term loans 8.00 4.15 [ICRA]A+ (Stable); reaffirmed
Long-term - Fund based - Cash credit 74.50 95.00 [ICRA]A+ (Stable); reaffirmed and assigned for enhanced amount
Short-term - Non-fund based limits 13.76 15.33 [ICRA]A1+; reaffirmed and assigned for enhanced amount
Total 98.88 114.48
Rationale
"""

INDIA_RATINGS_TEXT = """
India Ratings Rates Avadh Sugar & Energy's Additional Bank Facilities at 'IND A+'/Stable; Affirms Existing Ratings
Mar 10, 2025 | Avadh Sugar & Energy Limited|Sugar
Details of Instruments
Instrument Type
Date of Issuance
Coupon Rate
Maturity Date
Size of Issue (million)
Rating Assigned along with Outlook/Watch
Rating Action
Term loan
-
-
31 March 2029
INR5,490.6 (reduced from INR5,531.1)
IND A+/Stable
Affirmed
Fund-based working capital limit*
-
-
-
INR11,250
IND A+/Stable/IND A1
Affirmed
Analytical Approach
"""

INDIA_RATINGS_SINGLE_LINE_COMPACT_TEXT = """
India Ratings Affirms Nath Bio-Genes (India)'s Bank Loan Facilities at ‘IND BBB+'/Stable
Aug 11, 2025 | Nath Bio-Genes (India) Limited|Animal Feed
Details of Instruments
Instrument Type
Date of Issuance
Coupon Rate
Maturity Date
Size of Issue (million)
Rating assigned along with Outlook/Watch
Rating Action
Bank loan facilities - - - INR1,050 IND BBB+/Stable/IND A2 Affirmed
Analytical Approach
"""

INDIA_RATINGS_NON_COOP_TEXT = """
India Ratings Maintains Andrew Yule & Company Ltd in Non-Cooperating Category
Sep 12, 2024 | Andrew Yule & Company Ltd|Tea & Coffee
Details of Instruments
Instrument Type
Date of Issuance
Coupon Rate
Maturity Date
Size of Issue (million)
Rating/Outlook
Rating Action
Fund Based Working Capital Limit INR 374.4 IND C(ISSUER NOT COOPERATING) Maintained in non-cooperating category
Non-Fund Based Working Capital Limit INR 27.6 IND A4(ISSUER NOT COOPERATING) Maintained in non-cooperating category
Detailed Rationale of the Rating Action
"""

INDIA_RATINGS_HISTORICAL_TEXT = """
India Ratings Assigns Dhampur Sugar Mills' Proposed CP ‘IND A1+'; Affirms Existing Ratings
Jan 08, 2024 | Dhampur Sugar Mills Limited|Sugar
This announcement rectifies the version published on 20 November 2023 to correctly state that India Ratings continues to take a consolidated rating approach for Dhampur Sugar Mills Limited. The amended version is as follows:
India Ratings and Research (Ind-Ra) has taken the following rating actions on Dhampur Sugar Mills Limited (DSML) and its debt:
Instrument Type
Coupon Rate
Date of Issuance
Maturity Date
Size of Issue (million)
Rating/Outlook
Rating Action
Long-term issuer rating
-
-
-
-
IND AA-/Stable
Affirmed
Proposed commercial paper (CP)#
-
-
-
INR2,000
IND A1+
Assigned
Fund-based working capital limit
-
-
-
INR8,100*
IND AA-/Stable/IND A1+
Affirmed
Non-fund-based working capital limit
-
-
-
INR1,250*
IND AA-/Stable/IND A1+
Affirmed
Term loan
-
-
31 March 2030
INR2,568.2
IND AA-/Stable
Affirmed
Fixed deposit (FD)
-
-
-
INR400
IND AA-/Stable
Affirmed
ANALYTICAL APPROACH: Ind-Ra continues to take a consolidated view of DSML.
"""

INDIA_RATINGS_DISCONTINUED_ISSUER_TEXT = """
India Ratings Discontinues Voluntary Issuer Rating Disclosure due to Regulatory Requirements; All Outstanding Instrument Rating Remain Unaffected for Nath Bio-Genes (India) Limited
Sep 22, 2023 | Nath Bio-Genes (India) Limited|Animal Feed
India Ratings and Research (Ind-Ra) has discontinued voluntary disclosure of issuer ratings in its rating action commentaries (RACs), due to the regulatory requirement.
Following the revision in assigning issuer rating practice, the outstanding voluntary issuer rating disclosure of Nath Bio-Genes (India) Limited at IND BBB- stands withdrawn.
"""

BRICKWORK_TEXT = """
RATING RATIONALE
27 August 2021
Ruchi Soya Industries Limited
Particulars:
Facility
Amount (Rs. Crs)
Tenure
Rating*
Previous
Present
Previous (May 2020)^
Present
Fund based
CC/WCDL
Term Loans
ECL
800.00
2400.00
-
1095.00
2372.83
54.96
Long
Term
BWR BBB+/Stable
BWR A-/Stable
(Upgrade)
Short term Loan
95.25
-
Short
Term
BWR A3+
Rating Withdrawn**
Non Fund Based
BG/LC
Proposed standby LC
(350.00)
-
(550.00)
100.00
Short
Term
BWR A3+
BWR A2+
(Upgrade)
Total
3295.25
3622.79
RATING ACTION / OUTLOOK
"""


def test_parse_date_string_handles_missing_space_after_comma() -> None:
    assert parse_date_string("July 05,2024").isoformat() == "2024-07-05"


def test_find_first_date_handles_missing_space_after_comma() -> None:
    assert find_first_date("Press Release\nAmbar Protein Industries Limited\nJuly 05,2024").isoformat() == "2024-07-05"


def test_find_first_date_handles_month_year_by_defaulting_to_first_day() -> None:
    assert find_first_date("Bombay Super Hybrid Seeds Private Limited\nDecember 2015").isoformat() == "2015-12-01"


def test_care_parser_extracts_long_and_mixed_rows() -> None:
    bundle = CareParser().parse(
        pdf_path=Path("/tmp/care.pdf"),
        source_file="care.pdf",
        text=CARE_TEXT,
        text_hash="carehash",
        extractor_used="unit_test",
    )
    assert len(bundle.rating_events) == 2
    assert bundle.rating_events[0].long_term_rating == "BB+"
    assert bundle.rating_events[1].short_term_rating == "A4+"


def test_care_parser_extracts_hyphenated_rows_and_withdrawn_entry() -> None:
    bundle = CareParser().parse(
        pdf_path=Path("/tmp/care_old.pdf"),
        source_file="care_old.pdf",
        text=CARE_OLD_LAYOUT_TEXT,
        text_hash="careoldhash",
        extractor_used="unit_test",
    )
    assert len(bundle.rating_events) == 4
    assert bundle.rating_events[0].previous_rating == "CARE A+"
    assert bundle.rating_events[1].short_term_rating == "A2+"
    assert bundle.rating_events[-1].is_withdrawn


def test_care_parser_extracts_credit_update_inline_rating() -> None:
    bundle = CareParser().parse(
        pdf_path=Path("/tmp/care_credit_update.pdf"),
        source_file="care_credit_update.pdf",
        text=CARE_CREDIT_UPDATE_TEXT,
        text_hash="carecreditupdate",
        extractor_used="unit_test",
    )
    assert len(bundle.rating_events) == 1
    assert bundle.rating_events[0].long_term_rating == "AA-"
    assert bundle.rating_events[0].short_term_rating == "A1+"


def test_icra_parser_extracts_regular_summary_rows() -> None:
    bundle = IcraParser().parse(
        pdf_path=Path("/tmp/icra.pdf"),
        source_file="icra.pdf",
        text=ICRA_TEXT,
        text_hash="icrahash",
        extractor_used="unit_test",
    )
    assert len(bundle.rating_events) == 3
    assert bundle.rating_events[0].long_term_rating == "A+"
    assert bundle.rating_events[2].short_term_rating == "A1+"


def test_india_ratings_parser_extracts_rendered_article_rows() -> None:
    bundle = IndiaRatingsParser().parse(
        pdf_path=Path("/tmp/indiaratings.html"),
        source_file="indiaratings.html",
        text=INDIA_RATINGS_TEXT,
        text_hash="indhash",
        extractor_used="unit_test",
    )
    assert bundle.company.company_name == "Avadh Sugar & Energy Limited"
    assert len(bundle.rating_events) == 2
    assert bundle.rating_events[0].long_term_rating == "A+"
    assert bundle.rating_events[1].short_term_rating == "A1"


def test_india_ratings_parser_extracts_compact_single_line_row_with_lowercase_header() -> None:
    bundle = IndiaRatingsParser().parse(
        pdf_path=Path("/tmp/indiaratings_compact.html"),
        source_file="indiaratings_compact.html",
        text=INDIA_RATINGS_SINGLE_LINE_COMPACT_TEXT,
        text_hash="indcompact",
        extractor_used="unit_test",
    )
    assert len(bundle.rating_events) == 1
    assert bundle.rating_events[0].long_term_rating == "BBB+"
    assert bundle.rating_events[0].short_term_rating == "A2"


def test_india_ratings_parser_extracts_non_cooperation_single_line_rows() -> None:
    bundle = IndiaRatingsParser().parse(
        pdf_path=Path("/tmp/indiaratings_non_coop.html"),
        source_file="indiaratings_non_coop.html",
        text=INDIA_RATINGS_NON_COOP_TEXT,
        text_hash="indnoncoop",
        extractor_used="unit_test",
    )
    assert len(bundle.rating_events) == 2
    assert bundle.rating_events[0].long_term_rating == "C"
    assert bundle.rating_events[0].is_issuer_not_cooperating
    assert bundle.rating_events[1].short_term_rating == "A4"


def test_india_ratings_parser_extracts_historical_rating_action_layout() -> None:
    bundle = IndiaRatingsParser().parse(
        pdf_path=Path("/tmp/indiaratings_historical.html"),
        source_file="indiaratings_historical.html",
        text=INDIA_RATINGS_HISTORICAL_TEXT,
        text_hash="indhistory",
        extractor_used="unit_test",
    )
    assert len(bundle.rating_events) == 6
    assert any(event.instrument_type == "Long-term issuer rating" and event.long_term_rating == "AA-" for event in bundle.rating_events)
    assert any(event.instrument_type == "Proposed commercial paper (CP)#" and event.short_term_rating == "A1+" for event in bundle.rating_events)


def test_india_ratings_parser_extracts_discontinued_issuer_disclosure_withdrawal() -> None:
    bundle = IndiaRatingsParser().parse(
        pdf_path=Path("/tmp/indiaratings_discontinued.html"),
        source_file="indiaratings_discontinued.html",
        text=INDIA_RATINGS_DISCONTINUED_ISSUER_TEXT,
        text_hash="inddiscontinued",
        extractor_used="unit_test",
    )
    assert len(bundle.rating_events) == 1
    assert bundle.rating_events[0].long_term_rating == "BBB-"
    assert bundle.rating_events[0].is_withdrawn


def test_brickwork_parser_extracts_long_and_short_ratings() -> None:
    bundle = BrickworkParser().parse(
        pdf_path=Path("/tmp/brickwork.pdf"),
        source_file="brickwork.pdf",
        text=BRICKWORK_TEXT,
        text_hash="bwrhash",
        extractor_used="unit_test",
    )
    assert len(bundle.rating_events) >= 2
    assert any(event.long_term_rating == "A-" for event in bundle.rating_events)
    assert any(event.short_term_rating in {"A2+", "A3+"} or event.is_withdrawn for event in bundle.rating_events)


def test_rendered_html_fallback_triggers_for_india_ratings_shell() -> None:
    assert _should_render_html_in_browser(
        url="https://www.indiaratings.co.in/pressrelease/78366",
        agency_name="india_ratings",
        extracted_text="India Ratings and Research: Credit Rating and Research Agency India\nLoading...",
    )
