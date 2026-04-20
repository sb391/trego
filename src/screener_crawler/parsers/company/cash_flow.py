from __future__ import annotations

from typing import Any

from bs4 import BeautifulSoup

from .common import build_period_records, get_required_section, parse_matrix_section


CASH_FLOW_ALIASES = {
    "cash_from_operating_activity": (
        "cash_from_operating_activity",
        "cash_from_operating_activities",
        "cash_from_operating",
    ),
    "cash_from_investing_activity": (
        "cash_from_investing_activity",
        "cash_from_investing_activities",
        "cash_from_investing",
    ),
    "cash_from_financing_activity": (
        "cash_from_financing_activity",
        "cash_from_financing_activities",
        "cash_from_financing",
    ),
    "net_cash_flow": ("net_cash_flow",),
}


def parse_cash_flow_table(soup: BeautifulSoup, base_context: dict[str, Any]) -> dict[str, Any]:
    section = get_required_section(soup, "cash-flow")
    matrix = parse_matrix_section(section)
    records = build_period_records(base_context, matrix, CASH_FLOW_ALIASES)
    return {
        "section": matrix,
        "records": records,
    }
