from src.credit_rating_parser import (
    extract_pdf_url_from_html,
    extract_rating_from_text,
    parse_rating_update_metadata,
)


def test_parse_rating_update_metadata_infers_current_year() -> None:
    metadata = parse_rating_update_metadata("Rating update\n17 Mar from crisil", current_year=2026)

    assert metadata.rating_date == "2026-03-17"
    assert metadata.rating_date_display == "17 Mar"
    assert metadata.rating_agency == "crisil"
    assert metadata.notes is not None
    assert "Year inferred as 2026" in metadata.notes


def test_extract_rating_from_text_prefers_long_term_rating() -> None:
    text = """
    Sun Pharmaceutical Industries Limited
    Ratings reaffirmed at 'Crisil AAA / Stable / Crisil A1+'
    Long Term Rating Crisil AAA/Stable (Reaffirmed)
    Short Term Rating Crisil A1+ (Reaffirmed)
    """

    result = extract_rating_from_text(text, agency="crisil")

    assert result.rating == "AAA"
    assert result.rating_scale == "long_term"
    assert result.extraction_method is not None


def test_extract_rating_from_text_handles_india_ratings_format() -> None:
    text = """
    India Ratings and Research has upgraded Alivus Life Sciences Limited's long-term rating
    to 'IND AA' from 'IND AA-' with a Stable Outlook while affirming the short-term rating at 'IND A1+'.
    Rating Assigned along with Outlook/Watch
    IND AA/Stable/IND A1+
    """

    result = extract_rating_from_text(text, agency="fitch")

    assert result.rating == "AA"
    assert result.rating_scale == "long_term"


def test_extract_pdf_url_from_html_finds_icra_pdf_link() -> None:
    html = """
    <script>
    $('#DownloadRatingReport').click(function () {
      window.location.href = "/Rating/GetRationalReportFilePdf?Id=141393";
    })
    </script>
    """

    url = extract_pdf_url_from_html(html, base_url="https://www.icra.in/Rationale/ShowRationaleReport/?Id=141393")

    assert url == "https://www.icra.in/Rating/GetRationalReportFilePdf?Id=141393"


def test_extract_pdf_url_from_html_finds_embedded_viewer_pdf_link() -> None:
    html = '<iframe src="/web/viewer.html?file=/Rating/ShowRationalReportFilePdf/137206"></iframe>'

    url = extract_pdf_url_from_html(html, base_url="https://www.icra.in/Rationale/ShowRationaleReport/?Id=137206")

    assert url == "https://www.icra.in/Rating/ShowRationalReportFilePdf/137206"
