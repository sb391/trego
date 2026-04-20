from screener_crawler.parsers.industry_overview import extract_hierarchy_code, parse_industries_overview


SAMPLE_OVERVIEW_HTML = """
<html>
  <body>
    <div class="card card-large">
      <h1>Industries Overview</h1>
      <div class="responsive-holder fill-card-width">
        <table class="striped data-table">
          <tbody>
            <tr>
              <th class="text">S.No.</th>
              <th class="text"><a href="?order=asc">Industry</a></th>
              <th><a href="?sort=company_count&amp;order=desc">No. of Companies</a></th>
              <th><a href="?sort=total_market_cap&amp;order=desc">Total Market Cap.</a></th>
              <th><a href="?sort=avg_market_cap&amp;order=desc">Median Market Cap.</a></th>
              <th><a href="?sort=median_pe&amp;order=desc">Median P/E</a></th>
              <th><a href="?sort=avg_sales_growth&amp;order=desc">Wtd. Avg Sales Growth</a></th>
              <th><a href="?sort=avg_opm&amp;order=desc">Wtd. Avg OPM</a></th>
              <th><a href="?sort=avg_roce&amp;order=desc">Wtd. Avg ROCE</a></th>
              <th><a href="?sort=avg_return_over_1year&amp;order=desc">Median 1Y Return</a></th>
            </tr>
            <tr>
              <td class="text ink-600">1.</td>
              <td class="text"><a href="/market/IN04/IN0401/IN040104/IN040104002/" class="font-weight-500">Dairy Products</a></td>
              <td>14</td>
              <td>41,780</td>
              <td>2,658</td>
              <td>22</td>
              <td>12<span class="sub">%</span></td>
              <td>14<span class="sub">%</span></td>
              <td>15<span class="sub">%</span></td>
              <td>4<span class="sub">%</span></td>
            </tr>
            <tr>
              <th class="text">S.No.</th>
              <th class="text"><a href="?order=asc">Industry</a></th>
              <th><a href="?sort=company_count&amp;order=desc">No. of Companies</a></th>
              <th><a href="?sort=total_market_cap&amp;order=desc">Total Market Cap.</a></th>
              <th><a href="?sort=avg_market_cap&amp;order=desc">Median Market Cap.</a></th>
              <th><a href="?sort=median_pe&amp;order=desc">Median P/E</a></th>
              <th><a href="?sort=avg_sales_growth&amp;order=desc">Wtd. Avg Sales Growth</a></th>
              <th><a href="?sort=avg_opm&amp;order=desc">Wtd. Avg OPM</a></th>
              <th><a href="?sort=avg_roce&amp;order=desc">Wtd. Avg ROCE</a></th>
              <th><a href="?sort=avg_return_over_1year&amp;order=desc">Median 1Y Return</a></th>
            </tr>
            <tr>
              <td class="text ink-600">2.</td>
              <td class="text"><a href="/market/IN04/IN0401/IN040104/IN040104001/" class="font-weight-500">Animal Feed</a></td>
              <td>6</td>
              <td>29,019</td>
              <td>600</td>
              <td>25</td>
              <td>9<span class="sub">%</span></td>
              <td>11<span class="sub">%</span></td>
              <td>21<span class="sub">%</span></td>
              <td>32<span class="sub">%</span></td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </body>
</html>
"""


def test_parse_industries_overview_extracts_rows_and_metrics() -> None:
    parsed = parse_industries_overview(
        SAMPLE_OVERVIEW_HTML,
        overview_url="https://www.screener.in/market/",
        discovered_at="2026-04-04T00:00:00+00:00",
    )

    assert len(parsed.industries) == 2
    assert parsed.industries[0].industry_name == "Dairy Products"
    assert parsed.industries[0].industry_slug == "dairy_products"
    assert parsed.industries[0].screener_hierarchy_code == "IN04/IN0401/IN040104/IN040104002"
    assert parsed.industries[0].number_of_companies == 14
    assert parsed.industries[0].total_market_cap == 41780.0
    assert parsed.industries[0].weighted_avg_roce == 15.0
    assert parsed.industries[0].median_1y_return == 4.0


def test_extract_hierarchy_code_returns_none_for_non_market_url() -> None:
    assert extract_hierarchy_code("https://www.screener.in/company/HATSUN/") is None
