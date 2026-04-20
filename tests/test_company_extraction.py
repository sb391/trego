import json
from pathlib import Path

from bs4 import BeautifulSoup

from screener_crawler.company_extraction import (
    build_datasets_from_company_json,
    build_company_artifact_id,
    extract_company_data,
    parse_balance_sheet_table,
    parse_cash_flow_table,
    parse_company_identity,
    parse_profit_loss_table,
    parse_quarterly_results_table,
    parse_ratios_table,
    parse_shareholding_pattern,
)
from screener_crawler.normalize import parse_numeric_value


SAMPLE_COMPANY_HTML = """
<html>
  <body>
    <section id="top" class="card card-large">
      <h1>Example Dairy Ltd</h1>
      <div class="company-links">
        <a href="https://www.bseindia.com/stock-share-price/example-dairy-ltd/EXAMPLE/123456/">BSE: 123456</a>
        <a href="https://www.nseindia.com/get-quotes/equity?symbol=EXDAIRY">NSE: EXDAIRY</a>
      </div>
      <div class="company-ratios">
        <ul id="top-ratios">
          <li><span class="name">Market Cap</span><span class="value"><span class="number">1,234</span> Cr.</span></li>
          <li><span class="name">Current Price</span><span class="value"><span class="number">456</span></span></li>
          <li><span class="name">Stock P/E</span><span class="value"><span class="number">12.5</span></span></li>
          <li><span class="name">Book Value</span><span class="value"><span class="number">114</span></span></li>
          <li><span class="name">Dividend Yield</span><span class="value"><span class="number">1.20</span> %</span></li>
          <li><span class="name">ROCE</span><span class="value"><span class="number">18.0</span> %</span></li>
          <li><span class="name">ROE</span><span class="value"><span class="number">15.0</span> %</span></li>
          <li><span class="name">Face Value</span><span class="value"><span class="number">10.0</span></span></li>
        </ul>
      </div>
    </section>
    <section id="peers">
      <p class="sub">
        <a title="Broad Sector">Fast Moving Consumer Goods</a>
        <a title="Sector">Fast Moving Consumer Goods</a>
        <a title="Broad Industry">Food Products</a>
        <a title="Industry">Dairy Products</a>
      </p>
    </section>
    <section id="profit-loss" class="card card-large">
      <h2>Profit &amp; Loss</h2>
      <p class="sub">Standalone Figures in Rs. Crores</p>
      <div class="responsive-holder fill-card-width">
        <table class="data-table">
          <thead>
            <tr>
              <th></th>
              <th data-date-key="2024-03-31">Mar 2024</th>
              <th data-date-key="2025-03-31">Mar 2025</th>
              <th data-date-key="TTM">TTM</th>
            </tr>
          </thead>
          <tbody>
            <tr><td>Sales</td><td>100</td><td>120</td><td>150</td></tr>
            <tr><td>Expenses</td><td>80</td><td>95</td><td>110</td></tr>
            <tr><td>Operating Profit</td><td>20</td><td>25</td><td>40</td></tr>
            <tr><td>OPM %</td><td>20%</td><td>21%</td><td>27%</td></tr>
            <tr><td>Other Income</td><td>1</td><td>2</td><td>3</td></tr>
            <tr><td>Interest</td><td>4</td><td>3</td><td>2</td></tr>
            <tr><td>Depreciation</td><td>5</td><td>6</td><td>7</td></tr>
            <tr><td>Profit before tax</td><td>12</td><td>18</td><td>34</td></tr>
            <tr><td>Tax %</td><td>25%</td><td>24%</td><td>26%</td></tr>
            <tr><td>Net Profit</td><td>9</td><td>14</td><td>25</td></tr>
            <tr><td>EPS in Rs</td><td>2.5</td><td>3.1</td><td>4.2</td></tr>
            <tr><td>Dividend Payout %</td><td>10%</td><td>20%</td><td></td></tr>
          </tbody>
        </table>
      </div>
      <table class="ranges-table">
        <tr><th colspan="2">Compounded Sales Growth</th></tr>
        <tr><td>5 Years:</td><td>8%</td></tr>
        <tr><td>TTM:</td><td>12%</td></tr>
      </table>
      <table class="ranges-table">
        <tr><th colspan="2">Compounded Profit Growth</th></tr>
        <tr><td>5 Years:</td><td>10%</td></tr>
        <tr><td>TTM:</td><td>15%</td></tr>
      </table>
    </section>
    <section id="balance-sheet" class="card card-large">
      <h2>Balance Sheet</h2>
      <p class="sub">Standalone Figures in Rs. Crores</p>
      <div class="responsive-holder fill-card-width">
        <table class="data-table">
          <thead>
            <tr>
              <th></th>
              <th data-date-key="2024-03-31">Mar 2024</th>
              <th data-date-key="2025-03-31">Mar 2025</th>
            </tr>
          </thead>
          <tbody>
            <tr><td>Equity Capital</td><td>10</td><td>10</td></tr>
            <tr><td>Reserves</td><td>100</td><td>120</td></tr>
            <tr><td>Borrowings</td><td>50</td><td>40</td></tr>
            <tr><td>Other Liabilities</td><td>30</td><td>35</td></tr>
            <tr><td>Total Liabilities</td><td>190</td><td>205</td></tr>
            <tr><td>Fixed Assets</td><td>80</td><td>90</td></tr>
            <tr><td>CWIP</td><td>5</td><td>7</td></tr>
            <tr><td>Investments</td><td>10</td><td>12</td></tr>
            <tr><td>Other Assets</td><td>95</td><td>96</td></tr>
            <tr><td>Total Assets</td><td>190</td><td>205</td></tr>
          </tbody>
        </table>
      </div>
    </section>
    <section id="cash-flow" class="card card-large">
      <h2>Cash Flows</h2>
      <p class="sub">Standalone Figures in Rs. Crores</p>
      <div class="responsive-holder fill-card-width">
        <table class="data-table">
          <thead>
            <tr>
              <th></th>
              <th data-date-key="2024-03-31">Mar 2024</th>
              <th data-date-key="2025-03-31">Mar 2025</th>
            </tr>
          </thead>
          <tbody>
            <tr><td>Cash from Operating Activity</td><td>18</td><td>22</td></tr>
            <tr><td>Cash from Investing Activity</td><td>-10</td><td>-8</td></tr>
            <tr><td>Cash from Financing Activity</td><td>-2</td><td>-4</td></tr>
            <tr><td>Net Cash Flow</td><td>6</td><td>10</td></tr>
          </tbody>
        </table>
      </div>
    </section>
    <section id="ratios" class="card card-large">
      <h2>Ratios</h2>
      <p class="sub">Standalone Figures in Rs. Crores</p>
      <div class="responsive-holder fill-card-width">
        <table class="data-table">
          <thead>
            <tr>
              <th></th>
              <th data-date-key="2024-03-31">Mar 2024</th>
              <th data-date-key="2025-03-31">Mar 2025</th>
            </tr>
          </thead>
          <tbody>
            <tr><td>Debtor Days</td><td>5</td><td>6</td></tr>
            <tr><td>Inventory Days</td><td>40</td><td>35</td></tr>
            <tr><td>Days Payable</td><td>15</td><td>14</td></tr>
            <tr><td>Cash Conversion Cycle</td><td>30</td><td>27</td></tr>
            <tr><td>Working Capital Days</td><td>25</td><td>24</td></tr>
            <tr><td>ROCE %</td><td>16%</td><td>18%</td></tr>
          </tbody>
        </table>
      </div>
    </section>
    <section id="quarters" class="card card-large">
      <h2>Quarterly Results</h2>
      <p class="sub">Standalone Figures in Rs. Crores</p>
      <div class="responsive-holder fill-card-width">
        <table class="data-table">
          <thead>
            <tr>
              <th></th>
              <th data-date-key="2024-12-31">Dec 2024</th>
              <th data-date-key="2025-03-31">Mar 2025</th>
            </tr>
          </thead>
          <tbody>
            <tr><td>Sales</td><td>28</td><td>31</td></tr>
            <tr><td>Expenses</td><td>22</td><td>24</td></tr>
            <tr><td>Operating Profit</td><td>6</td><td>7</td></tr>
            <tr><td>OPM %</td><td>21%</td><td>23%</td></tr>
            <tr><td>Other Income</td><td>0</td><td>1</td></tr>
            <tr><td>Interest</td><td>1</td><td>1</td></tr>
            <tr><td>Depreciation</td><td>1</td><td>1</td></tr>
            <tr><td>Profit before tax</td><td>4</td><td>6</td></tr>
            <tr><td>Tax %</td><td>25%</td><td>25%</td></tr>
            <tr><td>Net Profit</td><td>3</td><td>4</td></tr>
            <tr><td>EPS in Rs</td><td>0.8</td><td>1.0</td></tr>
          </tbody>
        </table>
      </div>
    </section>
    <section id="shareholding" class="card card-large">
      <h2>Shareholding Pattern</h2>
      <div id="quarterly-shp">
        <div class="responsive-holder fill-card-width">
          <table class="data-table">
            <thead>
              <tr><th></th><th>Mar 2025</th><th>Jun 2025</th></tr>
            </thead>
            <tbody>
              <tr><td>Promoters</td><td>60%</td><td>61%</td></tr>
              <tr><td>FIIs</td><td>5%</td><td>6%</td></tr>
              <tr><td>DIIs</td><td>10%</td><td>11%</td></tr>
              <tr><td>Public</td><td>25%</td><td>22%</td></tr>
              <tr><td>No. of Shareholders</td><td>10,000</td><td>11,000</td></tr>
            </tbody>
          </table>
        </div>
      </div>
      <div id="yearly-shp" class="hidden">
        <div class="responsive-holder fill-card-width">
          <table class="data-table">
            <thead>
              <tr><th></th><th>Mar 2024</th></tr>
            </thead>
            <tbody>
              <tr><td>Promoters</td><td>59%</td></tr>
              <tr><td>FIIs</td><td>4%</td></tr>
              <tr><td>DIIs</td><td>9%</td></tr>
              <tr><td>Public</td><td>28%</td></tr>
              <tr><td>No. of Shareholders</td><td>9,000</td></tr>
            </tbody>
          </table>
        </div>
      </div>
    </section>
  </body>
</html>
"""


def base_context() -> dict[str, str]:
    return {
        "company_name": "Example Dairy Ltd",
        "company_slug": "EXAMPLE",
        "industry_slug": "dairy_products",
        "industry_name": "Dairy Products",
        "company_url": "https://www.screener.in/company/EXAMPLE/",
        "source_url": "https://www.screener.in/company/EXAMPLE/",
        "statement_scope": "standalone",
    }


def test_parse_numeric_value_handles_currency_percent_and_commas() -> None:
    assert parse_numeric_value("₹ 1,234 Cr.") == 1234.0
    assert parse_numeric_value("15%") == 15.0
    assert parse_numeric_value("(10)") == -10.0
    assert parse_numeric_value("NaN") is None
    assert parse_numeric_value("-") is None


def test_parse_company_identity_extracts_summary_fields() -> None:
    soup = BeautifulSoup(SAMPLE_COMPANY_HTML, "lxml")
    identity = parse_company_identity(soup, "https://www.screener.in/company/EXAMPLE/")

    assert identity["company_name"] == "Example Dairy Ltd"
    assert identity["ticker"] == "EXDAIRY"
    assert identity["industry_name"] == "Dairy Products"
    assert identity["industry"] == "Dairy Products"
    assert identity["current_price"] == 456.0
    assert identity["market_cap"] == 1234.0
    assert round(identity["pb"], 2) == 4.0


def test_section_parsers_build_records() -> None:
    soup = BeautifulSoup(SAMPLE_COMPANY_HTML, "lxml")

    profit_loss = parse_profit_loss_table(soup, base_context())
    balance_sheet = parse_balance_sheet_table(soup, base_context())
    cash_flow = parse_cash_flow_table(soup, base_context())
    ratios = parse_ratios_table(soup, base_context())
    quarterly = parse_quarterly_results_table(soup, base_context())
    shareholding = parse_shareholding_pattern(soup, base_context())

    assert profit_loss["records"][-1]["sales"] == 150.0
    assert profit_loss["records"][-1]["tax_percent"] == 26.0
    assert profit_loss["records"][-1]["profit_before_tax"] == 34.0
    assert profit_loss["records"][1]["dividend_payout_percent"] == 20.0
    assert balance_sheet["records"][-1]["borrowings"] == 40.0
    assert cash_flow["records"][-1]["net_cash_flow"] == 10.0
    assert ratios["records"][-1]["cash_conversion_cycle"] == 27.0
    assert ratios["records"][-1]["debtor_turnover"] is None
    assert quarterly["records"][-1]["net_profit"] == 4.0
    assert quarterly["records"][-1]["opm_percent"] == 23.0
    assert shareholding["records"][0]["holding_period_type"] == "quarterly"
    assert shareholding["records"][0]["promoters"] == 60.0
    assert shareholding["records"][-1]["number_of_shareholders"] == 9000


def test_extract_company_data_derives_growth_and_debt_to_equity() -> None:
    payload = extract_company_data(
        SAMPLE_COMPANY_HTML,
        source_url="https://www.screener.in/company/EXAMPLE/",
        raw_html_path=Path("data/raw/company_pages/example.html"),
        json_path=Path("data/intermediate/company_json/example.json"),
        crawl_context={"industry_slug": "dairy_products", "industry_name": "Dairy Products"},
    )

    summary = payload["financial_summary"]
    assert summary["sales_growth"] == 12.0
    assert summary["profit_growth"] == 15.0
    assert round(summary["debt_to_equity"], 4) == round(40 / 130, 4)
    assert summary["industry_name"] == "Dairy Products"
    assert summary["industry_slug"] == "dairy_products"
    assert payload["raw_metadata"]["parsing_status"] == "success"
    assert payload["raw_metadata"]["parser_version"]
    assert "Derived fields populated" in payload["raw_metadata"]["notes"]
    assert payload["raw_metadata"]["industry_slug"] == "dairy_products"


def test_build_datasets_from_company_json_normalizes_periods_and_builds_time_series(tmp_path: Path) -> None:
    payload = extract_company_data(
        SAMPLE_COMPANY_HTML,
        source_url="https://www.screener.in/company/EXAMPLE/",
        raw_html_path=tmp_path / "raw" / "example.html",
        json_path=tmp_path / "json" / "example.json",
        crawl_context={"industry_slug": "dairy_products", "industry_name": "Dairy Products"},
    )

    json_dir = tmp_path / "company_json"
    json_dir.mkdir(parents=True, exist_ok=True)
    (json_dir / "example.json").write_text(json.dumps(payload), encoding="utf-8")

    output_dir = tmp_path / "processed"
    frames = build_datasets_from_company_json(json_dir=json_dir, output_dir=output_dir)

    financial_summary = frames["financial_summary"]
    assert financial_summary.iloc[0]["industry_slug"] == "dairy_products"

    profit_loss = frames["profit_loss"]
    annual_row = profit_loss.loc[profit_loss["period_label"] == "Mar 2025"].iloc[0]
    ttm_row = profit_loss.loc[profit_loss["period_label"] == "TTM"].iloc[0]
    assert annual_row["period"] == "2025-03-31"
    assert annual_row["period_type"] == "annual"
    assert ttm_row["period"] == "TTM"
    assert ttm_row["period_type"] == "ttm"

    quarterly = frames["quarterly_results"]
    quarter_row = quarterly.loc[quarterly["period_label"] == "Dec 2024"].iloc[0]
    assert quarter_row["period"] == "2024-12-31"
    assert quarter_row["period_type"] == "quarterly"

    shareholding = frames["shareholding_pattern"]
    assert set(shareholding["holding_period_type"].unique()) == {"quarterly"}
    shareholding_row = shareholding.loc[shareholding["period_label"] == "Mar 2025"].iloc[0]
    assert shareholding_row["period"] == "2025-03-31"
    assert shareholding_row["period_type"] == "quarterly"

    time_series = frames["time_series_financials"]
    sales_ttm = time_series.loc[
        (time_series["company_slug"] == "EXAMPLE")
        & (time_series["statement_type"] == "profit_loss")
        & (time_series["metric_name"] == "sales")
        & (time_series["period"] == "TTM")
    ].iloc[0]
    assert sales_ttm["industry_slug"] == "dairy_products"
    assert sales_ttm["period_type"] == "ttm"
    assert sales_ttm["value"] == 150.0


def test_build_company_artifact_id_distinguishes_consolidated() -> None:
    assert build_company_artifact_id("DODLA", "https://www.screener.in/company/DODLA/consolidated/") == "dodla__consolidated"
    assert build_company_artifact_id("HATSUN", "https://www.screener.in/company/HATSUN/") == "hatsun"
