from __future__ import annotations

from typing import Any

from bs4 import BeautifulSoup

from ...normalize import canonicalize_metric_key
from .common import integer_from_row_map, parse_basic_table, value_from_row_map


SHAREHOLDING_ALIASES = {
    "promoters": ("promoters", "promoter"),
    "fii": ("fiis", "fii", "foreign_institutions"),
    "dii": ("diis", "dii", "domestic_institutions"),
    "public": ("public",),
    "number_of_shareholders": ("no_of_shareholders", "number_of_shareholders"),
}


def parse_shareholding_pattern(soup: BeautifulSoup, base_context: dict[str, Any]) -> dict[str, Any]:
    section = soup.select_one("section#shareholding")
    if section is None:
        raise ValueError("Unable to locate section #shareholding")

    tables = {
        "quarterly": section.select_one("#quarterly-shp table.data-table"),
        "yearly": section.select_one("#yearly-shp table.data-table"),
    }
    if tables["quarterly"] is None and tables["yearly"] is None:
        raise ValueError("Unable to locate shareholding tables.")

    parsed_tables: dict[str, Any] = {}
    records: list[dict[str, Any]] = []
    for period_type, table in tables.items():
        if table is None:
            continue

        parsed_table = parse_basic_table(table)
        parsed_tables[period_type] = parsed_table
        row_map = {canonicalize_metric_key(row["label"]): row["values"] for row in parsed_table["rows"]}

        for index, period in enumerate(parsed_table["periods"]):
            records.append(
                {
                    **base_context,
                    "period_label": period["label"],
                    "period_key": period["key"],
                    "holding_period_type": period_type,
                    "promoters": value_from_row_map(row_map, SHAREHOLDING_ALIASES["promoters"], index),
                    "fii": value_from_row_map(row_map, SHAREHOLDING_ALIASES["fii"], index),
                    "dii": value_from_row_map(row_map, SHAREHOLDING_ALIASES["dii"], index),
                    "public": value_from_row_map(row_map, SHAREHOLDING_ALIASES["public"], index),
                    "number_of_shareholders": integer_from_row_map(
                        row_map,
                        SHAREHOLDING_ALIASES["number_of_shareholders"],
                        index,
                    ),
                }
            )

    return {
        "tables": parsed_tables,
        "records": records,
    }
