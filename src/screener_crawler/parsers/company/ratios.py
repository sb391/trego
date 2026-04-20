from __future__ import annotations

from typing import Any

from bs4 import BeautifulSoup

from .common import build_period_records, get_required_section, parse_matrix_section


RATIOS_ALIASES = {
    "debtor_days": ("debtor_days",),
    "inventory_days": ("inventory_days",),
    "days_payable": ("days_payable",),
    "cash_conversion_cycle": ("cash_conversion_cycle",),
    "working_capital_days": ("working_capital_days",),
    "roce": ("roce", "roce_percent"),
    "roe": ("roe", "roe_percent"),
    "interest_coverage": ("interest_coverage",),
    "asset_turnover": ("asset_turnover",),
    "debtor_turnover": ("debtor_turnover", "debtors_turnover"),
    "inventory_turnover": ("inventory_turnover",),
}


def parse_ratios_table(soup: BeautifulSoup, base_context: dict[str, Any]) -> dict[str, Any]:
    section = get_required_section(soup, "ratios")
    matrix = parse_matrix_section(section)
    records = build_period_records(base_context, matrix, RATIOS_ALIASES)
    return {
        "section": matrix,
        "records": records,
    }
