from __future__ import annotations

from typing import Any
from urllib.parse import urlsplit

from bs4 import BeautifulSoup

from ...discovery import extract_company_slug
from ...normalize import clean_text, parse_nse_symbol, parse_numeric_value, parse_statement_scope_from_url, safe_divide


SUMMARY_TOP_RATIO_MAP = {
    "market_cap": ("market_cap",),
    "current_price": ("current_price",),
    "book_value": ("book_value",),
    "face_value": ("face_value",),
    "roe": ("roe", "roe_percent"),
    "roce": ("roce", "roce_percent"),
    "stock_pe": ("stock_p_e", "stock_pe", "p_e", "pe"),
    "dividend_yield": ("dividend_yield",),
}


def parse_company_identity(soup: BeautifulSoup, source_url: str) -> dict[str, Any]:
    title_node = soup.select_one("#top h1")
    company_name = clean_text(title_node.get_text(" ", strip=True) if title_node else None)
    if not company_name:
        raise ValueError("Unable to determine company name.")

    market_links = parse_market_links(soup)
    hierarchy = parse_industry_hierarchy(soup)
    top_ratios = parse_top_ratios(soup)

    current_price = first_metric_value(top_ratios, SUMMARY_TOP_RATIO_MAP["current_price"])
    book_value = first_metric_value(top_ratios, SUMMARY_TOP_RATIO_MAP["book_value"])
    stock_pe = first_metric_value(top_ratios, SUMMARY_TOP_RATIO_MAP["stock_pe"])
    roe = first_metric_value(top_ratios, SUMMARY_TOP_RATIO_MAP["roe"])
    roce = first_metric_value(top_ratios, SUMMARY_TOP_RATIO_MAP["roce"])
    industry_name = hierarchy.get("industry")

    return {
        "company_name": company_name,
        "company_slug": extract_company_slug(source_url),
        "ticker": market_links["nse_symbol"] or market_links["bse_code"] or extract_company_slug(source_url),
        "nse_symbol": market_links["nse_symbol"],
        "bse_code": market_links["bse_code"],
        "company_url": source_url,
        "statement_scope": parse_statement_scope_from_url(source_url),
        "industry_name": industry_name,
        "broad_sector": hierarchy.get("broad_sector"),
        "sector": hierarchy.get("sector"),
        "broad_industry": hierarchy.get("broad_industry"),
        "industry": industry_name,
        "current_price": current_price,
        "market_cap": first_metric_value(top_ratios, SUMMARY_TOP_RATIO_MAP["market_cap"]),
        "book_value": book_value,
        "face_value": first_metric_value(top_ratios, SUMMARY_TOP_RATIO_MAP["face_value"]),
        "roe": roe,
        "roce": roce,
        "pe": stock_pe,
        "pb": safe_divide(current_price, book_value),
        "debt_to_equity": None,
        "dividend_yield": first_metric_value(top_ratios, SUMMARY_TOP_RATIO_MAP["dividend_yield"]),
        "sales_growth": None,
        "profit_growth": None,
        "stock_pe": stock_pe,
        "return_on_equity": roe,
        "return_on_capital_employed": roce,
        "top_ratios": top_ratios,
    }


def parse_top_ratios(soup: BeautifulSoup) -> dict[str, float | None]:
    from ...normalize import canonicalize_metric_key

    ratios: dict[str, float | None] = {}
    for item in soup.select("#top-ratios li"):
        name_node = item.select_one(".name")
        if name_node is None:
            continue
        name = canonicalize_metric_key(name_node.get_text(" ", strip=True))
        value_node = item.select_one(".value")
        value = parse_numeric_value(value_node.get_text(" ", strip=True) if value_node else None)
        ratios[name] = value
    return ratios


def parse_market_links(soup: BeautifulSoup) -> dict[str, str | None]:
    nse_symbol: str | None = None
    bse_code: str | None = None

    for link in soup.select(".company-links a[href]"):
        href = link.get("href", "")
        if "nseindia.com" in href and nse_symbol is None:
            nse_symbol = parse_nse_symbol(href)
        if "bseindia.com" in href and bse_code is None:
            digits = [part for part in urlsplit(href).path.split("/") if part.isdigit()]
            if digits:
                bse_code = digits[-1]

    return {
        "nse_symbol": nse_symbol,
        "bse_code": bse_code,
    }


def parse_industry_hierarchy(soup: BeautifulSoup) -> dict[str, str | None]:
    hierarchy = {
        "broad_sector": None,
        "sector": None,
        "broad_industry": None,
        "industry": None,
    }
    for link in soup.select("#peers a[title]"):
        title = clean_text(link.get("title")).lower()
        value = clean_text(link.get_text(" ", strip=True))
        if title == "broad sector":
            hierarchy["broad_sector"] = value
        elif title == "sector":
            hierarchy["sector"] = value
        elif title == "broad industry":
            hierarchy["broad_industry"] = value
        elif title == "industry":
            hierarchy["industry"] = value
    return hierarchy


def first_metric_value(metrics: dict[str, float | None], aliases: tuple[str, ...]) -> float | None:
    for alias in aliases:
        if alias in metrics and metrics[alias] is not None:
            return metrics[alias]
    return None
