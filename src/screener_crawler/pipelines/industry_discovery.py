from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

from ..http import RobotsDisallowedError, RobotsPolicy, ScreenerHttpClient
from ..models import FetchedPage, IndustryOverviewRecord, ParsedIndustriesOverview
from ..parsers import parse_industries_overview


logger = logging.getLogger(__name__)

INDUSTRY_MASTER_COLUMNS = [
    "industry_name",
    "industry_url",
    "industry_slug",
    "screener_hierarchy_code",
    "number_of_companies",
    "total_market_cap",
    "median_market_cap",
    "median_pe",
    "weighted_avg_sales_growth",
    "weighted_avg_opm",
    "weighted_avg_roce",
    "median_1y_return",
    "discovered_at",
]


def fetch_industries_overview_page(
    client: ScreenerHttpClient,
    overview_url: str,
    *,
    robots_policy: RobotsPolicy,
    raw_html_path: Path | None = None,
) -> FetchedPage:
    if not robots_policy.can_fetch(overview_url):
        raise RobotsDisallowedError(f"robots.txt blocks {overview_url}")

    response = client.fetch(overview_url)
    fetched_page = FetchedPage(url=str(response.url), html=response.text, page_number=1)

    if raw_html_path is not None:
        raw_html_path.parent.mkdir(parents=True, exist_ok=True)
        raw_html_path.write_text(response.text, encoding="utf-8")
        logger.info("Saved industries overview HTML to %s", raw_html_path)

    return fetched_page


def save_industry_master_csv(
    industries: list[IndustryOverviewRecord],
    output_path: Path,
) -> pd.DataFrame:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    frame = pd.DataFrame([industry.to_dict() for industry in industries], columns=INDUSTRY_MASTER_COLUMNS)
    frame.to_csv(output_path, index=False)
    logger.info("Saved industry master CSV to %s", output_path)
    return frame


def discover_industries(
    client: ScreenerHttpClient,
    robots_policy: RobotsPolicy,
    *,
    overview_url: str,
    raw_html_path: Path,
    output_csv_path: Path,
) -> tuple[ParsedIndustriesOverview, pd.DataFrame]:
    fetched_page = fetch_industries_overview_page(
        client,
        overview_url,
        robots_policy=robots_policy,
        raw_html_path=raw_html_path,
    )
    parsed = parse_industries_overview(
        fetched_page.html,
        overview_url=fetched_page.url,
    )
    frame = save_industry_master_csv(parsed.industries, output_csv_path)
    return parsed, frame
