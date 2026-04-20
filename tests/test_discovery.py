from screener_crawler.discovery import (
    build_paginated_url,
    extract_company_slug,
    parse_industry_companies,
)
from screener_crawler.http import RobotsPolicy


SAMPLE_HTML = """
<html>
  <body>
    <h1>Dairy Products Companies</h1>
    <div class="sub" data-page-info>14 results found: Showing page 1 of 1</div>
    <div class="responsive-holder fill-card-width" data-page-results>
      <table class="data-table">
        <tbody>
          <tr>
            <th>S.No.</th>
            <th>Name</th>
            <th>CMP Rs.</th>
            <th>P/E</th>
            <th>Mar Cap Rs.Cr.</th>
            <th>Div Yld %</th>
            <th>NP Qtr Rs.Cr.</th>
            <th>Qtr Profit Var %</th>
            <th>Sales Qtr Rs.Cr.</th>
            <th>Qtr Sales Var %</th>
            <th>ROCE %</th>
          </tr>
          <tr data-row-company-id="1287">
            <td class="text">1.</td>
            <td class="text"><a href="/company/HATSUN/" target="_blank">Hatsun Agro</a></td>
            <td>902.05</td>
            <td>52.18</td>
            <td>20093.01</td>
            <td>0.67</td>
            <td>67.14</td>
            <td>64.00</td>
            <td>2314.63</td>
            <td>15.17</td>
            <td>13.12</td>
          </tr>
          <tr data-row-company-id="1274883">
            <td class="text">2.</td>
            <td class="text"><a href="/company/DODLA/consolidated/" target="_blank">Dodla Dairy</a></td>
            <td>1030.85</td>
            <td></td>
            <td>6218.89</td>
            <td>0.49</td>
            <td>68.74</td>
            <td>17.08</td>
            <td>1025.04</td>
            <td>13.74</td>
            <td></td>
          </tr>
        </tbody>
      </table>
    </div>
  </body>
</html>
"""


def test_parse_industry_companies_extracts_expected_fields() -> None:
    parsed = parse_industry_companies(
        SAMPLE_HTML,
        industry_url="https://www.screener.in/market/IN04/IN0401/IN040104/IN040104002/",
        discovered_at="2026-04-04T00:00:00+00:00",
    )

    assert parsed.industry_slug == "dairy_products"
    assert parsed.industry_name == "Dairy Products"
    assert parsed.pagination.total_results == 14
    assert parsed.pagination.current_page == 1
    assert parsed.pagination.total_pages == 1
    assert len(parsed.companies) == 2

    first_company = parsed.companies[0]
    assert first_company.industry_slug == "dairy_products"
    assert first_company.company_name == "Hatsun Agro"
    assert first_company.company_page_url == "https://www.screener.in/company/HATSUN/"
    assert first_company.company_slug == "HATSUN"
    assert first_company.listing_rank == 1
    assert first_company.cmp == 902.05
    assert first_company.market_cap == 20093.01
    assert first_company.pe == 52.18
    assert first_company.dividend_yield == 0.67
    assert first_company.roce == 13.12
    assert first_company.quarterly_sales == 2314.63
    assert first_company.quarterly_sales_growth == 15.17
    assert first_company.quarterly_profit == 67.14
    assert first_company.quarterly_profit_growth == 64.0
    assert first_company.promoter_holding is None
    assert first_company.discovered_at == "2026-04-04T00:00:00+00:00"


def test_parse_industry_companies_handles_blanks_and_consolidated_urls() -> None:
    parsed = parse_industry_companies(
        SAMPLE_HTML,
        industry_url="https://www.screener.in/market/IN04/IN0401/IN040104/IN040104002/",
    )

    second_company = parsed.companies[1]
    assert second_company.company_slug == "DODLA"
    assert second_company.pe is None
    assert second_company.roce is None
    assert second_company.promoter_holding is None


def test_build_paginated_url_overrides_existing_page_param() -> None:
    paged_url = build_paginated_url(
        "https://www.screener.in/market/IN04/IN0401/IN040104/?page=3",
        page_number=2,
    )
    assert paged_url == "https://www.screener.in/market/IN04/IN0401/IN040104/?page=2"


def test_extract_company_slug_from_url() -> None:
    assert extract_company_slug("https://www.screener.in/company/519152/") == "519152"


def test_robots_policy_honors_wildcard_page_rule() -> None:
    robots_text = """
    User-agent: *
    Disallow: /*?page=
    """
    policy = RobotsPolicy.from_text(robots_text, user_agent="ScreenerIndustryCrawler/0.1")

    assert policy.can_fetch("https://www.screener.in/market/IN04/IN0401/IN040104/") is True
    assert policy.can_fetch("https://www.screener.in/market/IN04/IN0401/IN040104/?page=2") is False
