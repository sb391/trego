from __future__ import annotations

from typing import Any

from bs4 import BeautifulSoup

from .common import build_period_records, get_required_section, parse_matrix_section


BALANCE_SHEET_ALIASES = {
    "equity_share_capital": ("equity_capital", "equity_share_capital"),
    "reserves": ("reserves",),
    "borrowings": ("borrowings",),
    "other_liabilities": ("other_liabilities",),
    "total_liabilities": ("total_liabilities",),
    "fixed_assets": ("fixed_assets",),
    "cwip": ("cwip", "capital_work_in_progress"),
    "investments": ("investments",),
    "other_assets": ("other_assets",),
    "total_assets": ("total_assets",),
}


def parse_balance_sheet_table(soup: BeautifulSoup, base_context: dict[str, Any]) -> dict[str, Any]:
    section = get_required_section(soup, "balance-sheet")
    matrix = parse_matrix_section(section)
    records = build_period_records(base_context, matrix, BALANCE_SHEET_ALIASES)
    return {
        "section": matrix,
        "records": records,
    }
