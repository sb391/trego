from __future__ import annotations

from typing import Any

from bs4 import BeautifulSoup

from .common import build_period_records, get_required_section, parse_matrix_section, parse_ranges_tables


PROFIT_LOSS_ALIASES = {
    "revenue": ("sales", "revenue"),
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
    "dividend_payout_percent": ("dividend_payout", "dividend_payout_percent"),
}


def parse_profit_loss_table(soup: BeautifulSoup, base_context: dict[str, Any]) -> dict[str, Any]:
    section = get_required_section(soup, "profit-loss")
    matrix = parse_matrix_section(section)
    growth_tables = parse_ranges_tables(section)
    records = build_period_records(base_context, matrix, PROFIT_LOSS_ALIASES)
    return {
        "section": matrix,
        "growth_tables": growth_tables,
        "records": records,
    }
