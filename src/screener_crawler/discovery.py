from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

import pandas as pd
from bs4 import BeautifulSoup

from .config import SCREENER_BASE_URL
from .http import RobotsDisallowedError, RobotsPolicy, ScreenerHttpClient
from .models import CompanyDiscoveryRecord, FetchedPage, PaginationInfo, ParsedIndustryPage
from .normalize import parse_integer_value, parse_numeric_value
from .utils.slugging import slugify_label


logger = logging.getLogger(__name__)

COMPANIES_MASTER_COLUMNS = [
    "industry_slug",
    "industry_name",
    "company_name",
    "company_page_url",
    "company_slug",
    "listing_rank",
    "cmp",
    "pe",
    "market_cap",
    "dividend_yield",
    "quarterly_profit",
    "quarterly_profit_growth",
    "quarterly_sales",
    "quarterly_sales_growth",
    "roce",
    "promoter_holding",
    "industry_url",
    "discovered_at",
]


def fetch_industry_page(
    client: ScreenerHttpClient,
    industry_url: str,
    *,
    robots_policy: RobotsPolicy,
    raw_html_path: Path | None = None,
    page_number: int = 1,
) -> FetchedPage:
    if not robots_policy.can_fetch(industry_url):
        raise RobotsDisallowedError(f"robots.txt blocks {industry_url}")

    response = client.fetch(industry_url)
    fetched_page = FetchedPage(url=str(response.url), html=response.text, page_number=page_number)

    if raw_html_path is not None:
        raw_html_path.parent.mkdir(parents=True, exist_ok=True)
        raw_html_path.write_text(response.text, encoding="utf-8")
        logger.info("Saved industry HTML snapshot to %s", raw_html_path)

    return fetched_page


def fetch_industry_pages(
    client: ScreenerHttpClient,
    *,
    industry_url: str,
    industry_slug: str,
    robots_policy: RobotsPolicy,
    raw_html_dir: Path | None = None,
) -> tuple[list[FetchedPage], PaginationInfo]:
    first_raw_path = build_industry_raw_html_path(raw_html_dir, industry_slug, page_number=1) if raw_html_dir else None
    first_page = fetch_industry_page(
        client,
        industry_url,
        robots_policy=robots_policy,
        raw_html_path=first_raw_path,
        page_number=1,
    )
    first_page_soup = BeautifulSoup(first_page.html, "lxml")
    pagination = parse_pagination_info(first_page_soup)
    pages = [first_page]

    if pagination.total_pages > 1:
        logger.warning(
            "Pagination detected for %s (%s pages). Additional pages are fetched only when robots.txt permits them.",
            industry_slug,
            pagination.total_pages,
        )

    for page_number in range(2, pagination.total_pages + 1):
        page_url = build_paginated_url(industry_url, page_number)
        if not robots_policy.can_fetch(page_url):
            logger.warning(
                "Skipping %s page %s because robots.txt blocks %s",
                industry_slug,
                page_number,
                page_url,
            )
            break

        raw_path = build_industry_raw_html_path(raw_html_dir, industry_slug, page_number=page_number) if raw_html_dir else None
        pages.append(
            fetch_industry_page(
                client,
                page_url,
                robots_policy=robots_policy,
                raw_html_path=raw_path,
                page_number=page_number,
            )
        )

    return pages, pagination


def parse_industry_companies(
    html: str,
    industry_url: str,
    *,
    industry_slug: str | None = None,
    industry_name: str | None = None,
    discovered_at: str | None = None,
) -> ParsedIndustryPage:
    soup = BeautifulSoup(html, "lxml")
    pagination = parse_pagination_info(soup)
    parsed_industry_name = industry_name or parse_industry_name(soup)
    parsed_industry_slug = industry_slug or slugify_label(parsed_industry_name)
    discovered_at_value = discovered_at or datetime.now(timezone.utc).isoformat()

    table = soup.select_one("[data-page-results] table")
    if table is None:
        raise ValueError("Unable to locate industry results table.")

    header_row = table.find("tr")
    if header_row is None:
        raise ValueError("Unable to locate results header row.")

    headers = [canonicalize_header(th.get_text(" ", strip=True)) for th in header_row.find_all("th")]
    header_indexes = {header: index for index, header in enumerate(headers)}

    rows = table.select("tr[data-row-company-id]")
    companies: list[CompanyDiscoveryRecord] = []
    for row in rows:
        cells = row.find_all("td", recursive=False)
        if not cells:
            continue

        name_cell = _cell_at(cells, header_indexes.get("name"))
        link = name_cell.find("a", href=True) if name_cell is not None else None
        if link is None:
            continue

        company_url = urljoin(SCREENER_BASE_URL, link["href"])
        companies.append(
            CompanyDiscoveryRecord(
                industry_slug=parsed_industry_slug,
                industry_name=parsed_industry_name,
                company_name=link.get_text(" ", strip=True),
                company_page_url=company_url,
                company_slug=extract_company_slug(company_url),
                listing_rank=parse_integer_value(_cell_text(cells, header_indexes.get("listing_rank"))),
                cmp=parse_numeric_value(_cell_text(cells, header_indexes.get("cmp"))),
                pe=parse_numeric_value(_cell_text(cells, header_indexes.get("pe"))),
                market_cap=parse_numeric_value(_cell_text(cells, header_indexes.get("market_cap"))),
                dividend_yield=parse_numeric_value(_cell_text(cells, header_indexes.get("dividend_yield"))),
                quarterly_profit=parse_numeric_value(_cell_text(cells, header_indexes.get("quarterly_profit"))),
                quarterly_profit_growth=parse_numeric_value(
                    _cell_text(cells, header_indexes.get("quarterly_profit_growth"))
                ),
                quarterly_sales=parse_numeric_value(_cell_text(cells, header_indexes.get("quarterly_sales"))),
                quarterly_sales_growth=parse_numeric_value(
                    _cell_text(cells, header_indexes.get("quarterly_sales_growth"))
                ),
                roce=parse_numeric_value(_cell_text(cells, header_indexes.get("roce"))),
                promoter_holding=parse_numeric_value(_cell_text(cells, header_indexes.get("promoter_holding"))),
                industry_url=industry_url,
                discovered_at=discovered_at_value,
            )
        )

    return ParsedIndustryPage(
        industry_slug=parsed_industry_slug,
        industry_name=parsed_industry_name,
        industry_url=industry_url,
        pagination=pagination,
        companies=companies,
    )


def save_companies_master_csv(
    companies: list[CompanyDiscoveryRecord],
    output_path: Path,
) -> pd.DataFrame:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    frame = pd.DataFrame([company.to_dict() for company in companies], columns=COMPANIES_MASTER_COLUMNS)
    frame.to_csv(output_path, index=False)
    logger.info("Saved companies master CSV to %s", output_path)
    return frame


def save_industry_companies_csv(
    companies: list[CompanyDiscoveryRecord],
    output_path: Path,
) -> pd.DataFrame:
    return save_companies_master_csv(companies, output_path)


def discover_industry_companies(
    client: ScreenerHttpClient,
    robots_policy: RobotsPolicy,
    *,
    industry_url: str,
    raw_html_path: Path,
    output_csv_path: Path,
    industry_slug: str | None = None,
    industry_name: str | None = None,
) -> tuple[ParsedIndustryPage, pd.DataFrame]:
    target_slug = industry_slug or slugify_label(industry_name or industry_url)
    pages, pagination = fetch_industry_pages(
        client,
        industry_url=industry_url,
        industry_slug=target_slug,
        robots_policy=robots_policy,
        raw_html_dir=raw_html_path.parent,
    )
    discovered_at = datetime.now(timezone.utc).isoformat()

    all_companies: list[CompanyDiscoveryRecord] = []
    parsed_first_page: ParsedIndustryPage | None = None
    for fetched_page in pages:
        parsed_page = parse_industry_companies(
            fetched_page.html,
            industry_url=industry_url,
            industry_slug=industry_slug,
            industry_name=industry_name,
            discovered_at=discovered_at,
        )
        if parsed_first_page is None:
            parsed_first_page = parsed_page
        all_companies.extend(parsed_page.companies)

    if parsed_first_page is None:
        raise ValueError(f"No pages were parsed for {industry_url}")

    final_parsed = ParsedIndustryPage(
        industry_slug=parsed_first_page.industry_slug,
        industry_name=parsed_first_page.industry_name,
        industry_url=industry_url,
        pagination=pagination,
        companies=deduplicate_companies(all_companies),
    )
    frame = save_companies_master_csv(final_parsed.companies, output_csv_path)
    return final_parsed, frame


def discover_companies_from_industry_master(
    client: ScreenerHttpClient,
    robots_policy: RobotsPolicy,
    *,
    industry_master_path: Path,
    output_csv_path: Path,
    raw_html_dir: Path,
    per_industry_dir: Path | None = None,
    industry_slug: str | None = None,
) -> tuple[pd.DataFrame, dict[str, int]]:
    targets = resolve_industry_targets(industry_master_path, industry_slug=industry_slug)
    if not targets:
        raise ValueError("No industries matched the requested filters.")

    discovered_companies: list[CompanyDiscoveryRecord] = []
    blocked_pagination_count = 0
    for target in targets:
        target_slug = str(target["industry_slug"])
        target_name = str(target["industry_name"])
        target_url = str(target["industry_url"])
        discovered_at = datetime.now(timezone.utc).isoformat()

        pages, pagination = fetch_industry_pages(
            client,
            industry_url=target_url,
            industry_slug=target_slug,
            robots_policy=robots_policy,
            raw_html_dir=raw_html_dir,
        )

        if pagination.total_pages > len(pages):
            blocked_pagination_count += 1

        industry_companies: list[CompanyDiscoveryRecord] = []
        for page in pages:
            parsed_page = parse_industry_companies(
                page.html,
                industry_url=target_url,
                industry_slug=target_slug,
                industry_name=target_name,
                discovered_at=discovered_at,
            )
            industry_companies.extend(parsed_page.companies)

        unique_industry_companies = deduplicate_companies(industry_companies)
        if per_industry_dir is not None:
            save_industry_companies_csv(
                unique_industry_companies,
                per_industry_dir / f"{target_slug}.csv",
            )
        discovered_companies.extend(unique_industry_companies)

    unique_master_companies = deduplicate_companies(discovered_companies)
    frame = save_companies_master_csv(unique_master_companies, output_csv_path)
    summary = {
        "industries_targeted": len(targets),
        "industries_processed": len(targets),
        "companies_found": len(unique_master_companies),
        "industries_with_blocked_pagination": blocked_pagination_count,
    }
    return frame, summary


def load_industry_master(industry_master_path: Path) -> list[dict[str, object]]:
    frame = pd.read_csv(industry_master_path)
    return frame.to_dict(orient="records")


def resolve_industry_targets(
    industry_master_path: Path,
    *,
    industry_slug: str | None = None,
) -> list[dict[str, object]]:
    industries = load_industry_master(industry_master_path)
    if industry_slug is None:
        return industries

    normalized = industry_slug.strip().lower()
    matched = [
        industry
        for industry in industries
        if str(industry.get("industry_slug", "")).strip().lower() == normalized
    ]
    if matched:
        return matched

    raise ValueError(f"Industry slug not found in {industry_master_path}: {industry_slug}")


def build_industry_raw_html_path(raw_html_dir: Path | None, industry_slug: str, *, page_number: int) -> Path:
    if raw_html_dir is None:
        raise ValueError("raw_html_dir is required to build industry raw HTML paths.")
    suffix = "" if page_number == 1 else f"__page_{page_number}"
    return raw_html_dir / f"{industry_slug}{suffix}.html"


def parse_industry_name(soup: BeautifulSoup) -> str:
    heading = soup.find("h1")
    if heading is not None:
        title = heading.get_text(" ", strip=True)
        return re.sub(r"\s+Companies$", "", title).strip()

    breadcrumb_items = soup.select("nav a, .breadcrumb a")
    if breadcrumb_items:
        return breadcrumb_items[-1].get_text(" ", strip=True)
    raise ValueError("Unable to determine industry name from page.")


def parse_pagination_info(soup: BeautifulSoup) -> PaginationInfo:
    page_info = soup.select_one("[data-page-info]")
    if page_info is None:
        raise ValueError("Unable to locate page summary block.")

    text = page_info.get_text(" ", strip=True)
    match = re.search(
        r"(?P<total>\d+)\s+results\s+found:\s+Showing\s+page\s+(?P<current>\d+)\s+of\s+(?P<pages>\d+)",
        text,
        flags=re.IGNORECASE,
    )
    if match is None:
        raise ValueError(f"Unable to parse pagination info from: {text!r}")

    return PaginationInfo(
        total_results=int(match.group("total")),
        current_page=int(match.group("current")),
        total_pages=int(match.group("pages")),
    )


def canonicalize_header(text: str) -> str:
    normalized = re.sub(r"\s+", " ", text).strip().lower()
    normalized = normalized.replace(".", "")
    collapsed = normalized.replace(" ", "")

    if normalized.startswith("s no") or collapsed == "sno":
        return "listing_rank"
    if normalized == "name":
        return "name"
    if normalized.startswith("cmp"):
        return "cmp"
    if normalized.startswith("p/e") or normalized == "pe":
        return "pe"
    if normalized.startswith("mar cap"):
        return "market_cap"
    if normalized.startswith("div yld") or normalized.startswith("dividend yield"):
        return "dividend_yield"
    if normalized.startswith("np qtr"):
        return "quarterly_profit"
    if normalized.startswith("qtr profit var"):
        return "quarterly_profit_growth"
    if normalized.startswith("sales qtr"):
        return "quarterly_sales"
    if normalized.startswith("qtr sales var"):
        return "quarterly_sales_growth"
    if normalized.startswith("roce"):
        return "roce"
    if normalized.startswith("promoter"):
        return "promoter_holding"

    return normalized


def build_paginated_url(industry_url: str, page_number: int) -> str:
    parts = urlsplit(industry_url)
    query_params = dict(parse_qsl(parts.query, keep_blank_values=True))
    query_params["page"] = str(page_number)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query_params), parts.fragment))


def deduplicate_companies(companies: list[CompanyDiscoveryRecord]) -> list[CompanyDiscoveryRecord]:
    seen_keys: set[tuple[str, str]] = set()
    unique_companies: list[CompanyDiscoveryRecord] = []
    for company in companies:
        key = (company.industry_slug, company.company_page_url)
        if key in seen_keys:
            continue
        seen_keys.add(key)
        unique_companies.append(company)
    return unique_companies


def extract_company_slug(company_url: str) -> str:
    path_parts = [part for part in urlsplit(company_url).path.split("/") if part]
    try:
        company_index = path_parts.index("company")
    except ValueError as exc:
        raise ValueError(f"Unable to extract company slug from URL: {company_url}") from exc

    if company_index + 1 >= len(path_parts):
        raise ValueError(f"Unable to extract company slug from URL: {company_url}")

    return path_parts[company_index + 1]


def _cell_text(cells: list, index: int | None) -> str | None:
    cell = _cell_at(cells, index)
    if cell is None:
        return None
    return cell.get_text(" ", strip=True)


def _cell_at(cells: list, index: int | None):
    if index is None:
        return None
    if index >= len(cells):
        return None
    return cells[index]
