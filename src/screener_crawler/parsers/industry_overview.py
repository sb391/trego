from __future__ import annotations

from datetime import datetime, timezone
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup

from ..config import SCREENER_BASE_URL
from ..models import IndustryOverviewRecord, ParsedIndustriesOverview
from ..normalize import parse_integer_value, parse_numeric_value
from ..utils.slugging import slugify_label


def parse_industries_overview(
    html: str,
    *,
    overview_url: str,
    discovered_at: str | None = None,
) -> ParsedIndustriesOverview:
    soup = BeautifulSoup(html, "lxml")
    table = soup.select_one(".card.card-large table.data-table")
    if table is None:
        raise ValueError("Unable to locate industries overview table.")

    discovered_at_value = discovered_at or datetime.now(timezone.utc).isoformat()
    industries: list[IndustryOverviewRecord] = []
    for row in table.select("tr"):
        cells = row.find_all("td", recursive=False)
        if not cells:
            continue
        if len(cells) < 10:
            continue

        link = row.select_one("td.text a[href]")
        if link is None:
            continue

        industry_name = link.get_text(" ", strip=True)
        industry_url = urljoin(SCREENER_BASE_URL, link["href"])

        industries.append(
            IndustryOverviewRecord(
                industry_name=industry_name,
                industry_url=industry_url,
                industry_slug=slugify_label(industry_name),
                screener_hierarchy_code=extract_hierarchy_code(industry_url),
                number_of_companies=parse_integer_value(cells[2].get_text(" ", strip=True)),
                total_market_cap=parse_numeric_value(cells[3].get_text(" ", strip=True)),
                median_market_cap=parse_numeric_value(cells[4].get_text(" ", strip=True)),
                median_pe=parse_numeric_value(cells[5].get_text(" ", strip=True)),
                weighted_avg_sales_growth=parse_numeric_value(cells[6].get_text(" ", strip=True)),
                weighted_avg_opm=parse_numeric_value(cells[7].get_text(" ", strip=True)),
                weighted_avg_roce=parse_numeric_value(cells[8].get_text(" ", strip=True)),
                median_1y_return=parse_numeric_value(cells[9].get_text(" ", strip=True)),
                discovered_at=discovered_at_value,
            )
        )

    return ParsedIndustriesOverview(
        overview_url=overview_url,
        industries=industries,
    )


def extract_hierarchy_code(industry_url: str) -> str | None:
    path = urlsplit(industry_url).path.strip("/")
    if not path.startswith("market/"):
        return None
    code = path.removeprefix("market/").strip("/")
    return code or None
