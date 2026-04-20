from __future__ import annotations

import pytest

from src.utils.pdf import detect_agency_name


@pytest.mark.parametrize(
    ("source_file", "text", "expected"),
    [
        ("Crisil_Medicamen.pdf", "Crisil Ratings Limited Rating Rationale", "crisil"),
        ("Care_sample.pdf", "CARE Ratings Ltd. Press Release", "care"),
        ("IndiaRatings_sample.pdf", "India Ratings and Research (Ind-Ra)", "india_ratings"),
        ("Acuite_sample.pdf", "Acuité Ratings & Research Limited", "acuite"),
        ("Brickwork_sample.pdf", "Brickwork Ratings RATING RATIONALE", "brickwork"),
        ("Infomerics_sample.pdf", "Infomerics Ratings Ratings", "infomerics"),
        ("ICRA_sample.pdf", "www.icra.in Summary of rating action", "icra"),
    ],
)
def test_detect_agency_name(source_file: str, text: str, expected: str) -> None:
    assert detect_agency_name(source_file, text) == expected
