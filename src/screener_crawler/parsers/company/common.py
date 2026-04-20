from __future__ import annotations

from typing import Any

from bs4 import BeautifulSoup, Tag

from ...normalize import (
    canonicalize_metric_key,
    clean_row_label,
    clean_text,
    normalize_cell_text,
    parse_integer_value,
    parse_numeric_value,
    parse_scope_from_text,
    parse_unit_from_text,
)


def get_required_section(soup: BeautifulSoup, section_id: str) -> Tag:
    section = soup.select_one(f"section#{section_id}")
    if section is None:
        raise ValueError(f"Unable to locate section #{section_id}")
    return section


def parse_basic_table(table: Tag) -> dict[str, Any]:
    header_cells = table.select("thead tr th")
    if len(header_cells) <= 1:
        raise ValueError("Table is missing period headers.")

    periods = []
    for header in header_cells[1:]:
        label = clean_text(header.get_text(" ", strip=True))
        periods.append(
            {
                "label": label,
                "key": header.get("data-date-key") or label,
            }
        )

    rows: list[dict[str, Any]] = []
    for row in table.select("tbody > tr"):
        cells = row.find_all(["td", "th"], recursive=False)
        if len(cells) <= 1:
            continue
        label = clean_row_label(cells[0].get_text(" ", strip=True))
        values = [normalize_cell_text(cell.get_text(" ", strip=True)) for cell in cells[1:]]
        if not label:
            continue
        if len(values) < len(periods):
            values.extend([None] * (len(periods) - len(values)))
        rows.append(
            {
                "label": label,
                "key": canonicalize_metric_key(label),
                "values": values[: len(periods)],
            }
        )

    return {
        "periods": periods,
        "rows": rows,
    }


def parse_matrix_section(section: Tag) -> dict[str, Any]:
    title_node = section.select_one("h2")
    subtitle_node = section.select_one("p.sub")
    table = section.select_one(".responsive-holder table.data-table")
    if table is None:
        raise ValueError("Unable to locate data table.")

    parsed_table = parse_basic_table(table)
    subtitle_text = subtitle_node.get_text(" ", strip=True) if subtitle_node else None
    return {
        "title": clean_text(title_node.get_text(" ", strip=True) if title_node else None),
        "statement_scope": parse_scope_from_text(subtitle_text),
        "units": parse_unit_from_text(subtitle_text),
        "periods": parsed_table["periods"],
        "rows": parsed_table["rows"],
    }


def build_period_records(
    base_context: dict[str, Any],
    section_data: dict[str, Any],
    aliases: dict[str, tuple[str, ...]],
) -> list[dict[str, Any]]:
    row_map = {row["key"]: row["values"] for row in section_data["rows"]}
    records: list[dict[str, Any]] = []
    for index, period in enumerate(section_data["periods"]):
        record = {
            **base_context,
            "period_label": period["label"],
            "period_key": period["key"],
        }
        for target_field, alias_values in aliases.items():
            record[target_field] = value_from_row_map(row_map, alias_values, index)
        records.append(record)
    return records


def value_from_row_map(
    row_map: dict[str, list[str | None]],
    aliases: tuple[str, ...],
    index: int,
) -> float | None:
    for alias in aliases:
        values = row_map.get(alias)
        if values is None or index >= len(values):
            continue
        numeric_value = parse_numeric_value(values[index])
        if numeric_value is not None:
            return numeric_value
    return None


def integer_from_row_map(
    row_map: dict[str, list[str | None]],
    aliases: tuple[str, ...],
    index: int,
) -> int | None:
    for alias in aliases:
        values = row_map.get(alias)
        if values is None or index >= len(values):
            continue
        integer_value = parse_integer_value(values[index])
        if integer_value is not None:
            return integer_value
    return None


def parse_ranges_tables(section: Tag) -> dict[str, dict[str, float | None]]:
    tables: dict[str, dict[str, float | None]] = {}
    for table in section.select("table.ranges-table"):
        header = table.select_one("th")
        if header is None:
            continue
        title = clean_text(header.get_text(" ", strip=True))
        values: dict[str, float | None] = {}
        for row in table.select("tr")[1:]:
            cells = row.find_all(["td", "th"])
            if len(cells) != 2:
                continue
            key = clean_text(cells[0].get_text(" ", strip=True)).rstrip(":")
            values[key] = parse_numeric_value(cells[1].get_text(" ", strip=True))
        tables[title] = values
    return tables


def select_growth_value(growth_table: dict[str, float | None]) -> float | None:
    for key in ("TTM", "Last Year", "3 Years", "5 Years", "10 Years", "1 Year"):
        if key in growth_table and growth_table[key] is not None:
            return growth_table[key]
    return None
