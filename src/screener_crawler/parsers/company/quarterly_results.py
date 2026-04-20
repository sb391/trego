from __future__ import annotations

from typing import Any

from bs4 import BeautifulSoup

from .common import build_period_records, get_required_section, parse_matrix_section


QUARTERLY_RESULTS_ALIASES = {
    "sales": ("sales", "revenue"),
    "expenses": ("expenses",),
    "operating_profit": ("operating_profit",),
    "opm_percent": ("opm", "opm_percent"),
    "other_income": ("other_income",),
    "interest": ("interest",),
    "depreciation": ("depreciation",),
    "profit_before_tax": ("profit_before_tax", "pbt"),
    "tax": ("tax", "tax_percent"),
    "tax_percent": ("tax", "tax_percent"),
    "net_profit": ("net_profit",),
    "eps": ("eps_in_rs", "eps"),
}


def parse_quarterly_results_table(soup: BeautifulSoup, base_context: dict[str, Any]) -> dict[str, Any]:
    section = get_required_section(soup, "quarters")
    matrix = parse_matrix_section(section)
    records = build_period_records(base_context, matrix, QUARTERLY_RESULTS_ALIASES)
    return {
        "section": matrix,
        "records": records,
    }
