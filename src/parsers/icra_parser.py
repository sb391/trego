from __future__ import annotations

import re

from ..utils import compact_spaces, normalize_multiline_text, parse_amount_to_crore
from .base import BaseAgencyParser
from .common import build_rating_event


ICRA_ROW_START_PATTERN = re.compile(
    r"^(Long[- ]term|Short[- ]term|Long[- ]term/ ?Short[- ]term|LT/Short Term|LT/|Fund[- ]based|Non[- ]fund[- ]based|Unallocated|Fixed Deposit Programme|Term Loan|Commercial paper|Working capital|Fund-based|Non-fund-based)\b",
    flags=re.I,
)


class IcraParser(BaseAgencyParser):
    agency_name = "icra"
    parser_name = "icra_parser"

    def extract_rating_events(self, *, text, sections, rationale_doc_id, company_name, rating_date):
        table_block = self._extract_table_block(text)
        if not table_block:
            return []

        has_previous_column = "Previous Rated Amount" in table_block or "Previous Rated\nAmount" in table_block
        events = []
        for row in self._collect_rows(table_block):
            event = self._parse_row(
                row,
                rationale_doc_id=rationale_doc_id,
                company_name=company_name,
                rating_date=rating_date,
                event_index=len(events) + 1,
                has_previous_column=has_previous_column,
            )
            if event:
                events.append(event)
        return events

    def _extract_table_block(self, text: str) -> str | None:
        normalized = normalize_multiline_text(text)
        start_match = re.search(r"(Summary of rating action|Rating Action)", normalized, flags=re.I)
        if not start_match:
            return None
        body = normalized[start_match.end() :].strip()
        header_match = re.search(
            r"(Instrument\*|Instrument\^|Instrument\s+Current rated amount|Instrument\s+Rated Amount)",
            body,
            flags=re.I,
        )
        if header_match:
            body = body[header_match.start() :].strip()
        end_match = re.search(r"(\*?\s*Instrument details|Rationale|Key rating drivers and their description)", body, flags=re.I)
        return body[: end_match.start()].strip() if end_match else body

    def _collect_rows(self, table_block: str) -> list[str]:
        rows: list[str] = []
        current: list[str] = []
        for raw_line in table_block.splitlines():
            line = compact_spaces(raw_line)
            if not line or self._is_header_line(line):
                continue
            if re.match(r"^(Total|Grand Total)\b", line, flags=re.I):
                break
            if current and ICRA_ROW_START_PATTERN.match(line) and "[ICRA]" not in current[-1]:
                rows.append(" ".join(current))
                current = [line]
                continue
            current.append(line)
            if "[ICRA]" in line:
                rows.append(" ".join(current))
                current = []
        if current and "[ICRA]" in " ".join(current):
            rows.append(" ".join(current))
        return rows

    def _parse_row(
        self,
        row: str,
        *,
        rationale_doc_id: str,
        company_name: str,
        rating_date,
        event_index: int,
        has_previous_column: bool,
    ):
        row = compact_spaces(row)
        rating_match = re.search(r"(\[ICRA\].+)$", row, flags=re.I)
        if not rating_match:
            return None
        rating_text = compact_spaces(rating_match.group(1))
        left = compact_spaces(row[: rating_match.start()])
        left_clean = compact_spaces(re.sub(r"\((?=[^)]*[A-Za-z])[^)]*\)", " ", left))
        amount_tokens = re.findall(r"\d[\d,.]*", left_clean)
        if not amount_tokens:
            return None
        amount_token = amount_tokens[-1] if has_previous_column and len(amount_tokens) >= 2 else amount_tokens[0]
        instrument_match = re.match(r"^(?P<instrument>.+?)\s+\d[\d,.]*", left_clean)
        instrument_type = compact_spaces(instrument_match.group("instrument")) if instrument_match else left_clean
        return build_rating_event(
            rationale_doc_id=rationale_doc_id,
            company_name=company_name,
            agency_name=self.agency_name,
            rating_date=rating_date,
            instrument_type=instrument_type,
            facility_amount=parse_amount_to_crore(amount_token),
            current_rating=rating_text,
            rating_action=rating_text.split(";", 1)[1].strip() if ";" in rating_text else None,
            event_index=event_index,
        )

    def _is_header_line(self, line: str) -> bool:
        return line.startswith(
            (
                "Instrument",
                "Previous Rated Amount",
                "Current Rated Amount",
                "Rated Amount",
                "Rating Action",
                "Amount rated",
                "Current rating",
                "Chronology of rating history",
                "Type Amount rated",
                "(in crore)",
            )
        )
