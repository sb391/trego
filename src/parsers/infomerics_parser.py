from __future__ import annotations

import re

from ..utils import compact_spaces, normalize_multiline_text, parse_amount_to_crore
from .base import BaseAgencyParser
from .common import build_rating_event


INFOMERICS_ROW_START_PATTERN = re.compile(
    r"^(Long[- ]?Term|Short[- ]?Term|Long[- ]?Term\s*/\s*Short[- ]?Term|Instrument|Security|Fund[- ]based|Non[- ]fund[- ]based|Bank Loan Ratings|Unallocated)",
    flags=re.I,
)
INFOMERICS_RATING_PATTERN = re.compile(
    r"(?:"
    r"IVR\s+(?:AAA|AA\+|AA-|AA|A1\+|A1|A2\+|A2|A3\+|A3|A4\+|A4|A\+|A-|BBB\+|BBB-|BBB|BB\+|BB-|BB|B\+|B-|C\+|A|B|C|D)"
    r"(?:\s*[;/]\s*(?:RWDI|Stable|Positive|Negative))?"
    r"(?:\s*/\s*IVR\s+(?:A1\+|A1|A2\+|A2|A3\+|A3|A4\+|A4))?"
    r"(?:\s*;\s*Withdrawn)?"
    r"|Not Applicable\s*\|\s*Withdrawn"
    r")",
    flags=re.I,
)
INFOMERICS_TABLE_END_PATTERN = re.compile(
    r"^(Detailed Rationale|Rationale|Key Rating Sensitivities|List of Key Rating Drivers|About the Company|Analytical Approach)\b",
    flags=re.I,
)


class InfomericsParser(BaseAgencyParser):
    agency_name = "infomerics"
    parser_name = "infomerics_parser"

    def extract_rating_events(self, *, text, sections, rationale_doc_id, company_name, rating_date):
        table_lines = self._extract_table_lines(text)
        events = []
        row_groups = self._collect_rows(table_lines) if table_lines else self._extract_legacy_rows(text)
        for row_lines in row_groups:
            event = self._parse_row(
                row_lines,
                rationale_doc_id=rationale_doc_id,
                company_name=company_name,
                rating_date=rating_date,
                event_index=len(events) + 1,
            )
            if event:
                events.append(event)
        return events

    def _extract_table_lines(self, text: str) -> list[str]:
        lines = [compact_spaces(line) for line in normalize_multiline_text(text).splitlines() if compact_spaces(line)]
        capture = False
        table_lines: list[str] = []
        for line in lines:
            if not capture and line == "Ratings":
                capture = True
                continue
            if not capture:
                continue
            if INFOMERICS_TABLE_END_PATTERN.match(line):
                break
            table_lines.append(line)
        return table_lines

    def _collect_rows(self, lines: list[str]) -> list[list[str]]:
        rows: list[list[str]] = []
        current: list[str] = []
        for line in lines:
            if self._is_header_line(line):
                continue
            if re.match(r"^Total\b", line, flags=re.I):
                break
            if current and self._looks_like_new_row(line) and self._row_has_amount(current) and self._row_has_rating(current):
                rows.append(current)
                current = [line]
                continue
            current.append(line)
            if re.search(r"\b(Simple|Complex)\b$", line, flags=re.I):
                rows.append(current)
                current = []
        if current and self._row_has_amount(current) and self._row_has_rating(current):
            rows.append(current)
        return rows

    def _extract_legacy_rows(self, text: str) -> list[list[str]]:
        lines = [compact_spaces(line) for line in normalize_multiline_text(text).splitlines() if compact_spaces(line)]
        rows: list[list[str]] = []
        current: list[str] = []
        for line in lines:
            if line not in {"Long Term", "Short Term"} and not current:
                continue
            if line in {"Long Term", "Short Term"} and current:
                rows.append(current)
                current = [line]
                continue
            current.append(line)
            if line == "Simple" or line.endswith("Simple"):
                rows.append(current)
                current = []
        if current and self._row_has_amount(current) and self._row_has_rating(current):
            rows.append(current)
        return rows

    def _parse_row(self, row_lines: list[str], *, rationale_doc_id: str, company_name: str, rating_date, event_index: int):
        row_text = compact_spaces(" ".join(row_lines))
        row_text = re.sub(r"\b(A[1-4])\s+\+\b", r"\1+", row_text, flags=re.I)
        row_text = re.sub(r"\s*/\s*", "/", row_text)
        row_text = re.sub(r"\s*;\s*", "; ", row_text)

        amount_match = re.match(r"^(?P<instrument>.+?)\s+(?P<amount>\d+(?:\.\d+)?)\b(?P<rest>.*)$", row_text)
        if not amount_match:
            return None

        instrument_type = compact_spaces(amount_match.group("instrument").rstrip("-/"))
        rest = compact_spaces(amount_match.group("rest"))
        simplified = compact_spaces(re.sub(r"\([^)]*\)", " ", rest))
        rating_matches = list(INFOMERICS_RATING_PATTERN.finditer(simplified))
        if not rating_matches:
            return None

        current_rating = compact_spaces(rating_matches[0].group(0))
        previous_rating = compact_spaces(rating_matches[1].group(0)) if len(rating_matches) > 1 else None
        action_start = rating_matches[1].end() if len(rating_matches) > 1 else rating_matches[0].end()
        action_text = compact_spaces(simplified[action_start:].strip(" -"))
        if action_text.lower().startswith("rating "):
            action_text = action_text[7:].strip()

        return build_rating_event(
            rationale_doc_id=rationale_doc_id,
            company_name=company_name,
            agency_name=self.agency_name,
            rating_date=rating_date,
            instrument_type=instrument_type,
            facility_amount=parse_amount_to_crore(amount_match.group("amount")),
            current_rating=current_rating,
            previous_rating=previous_rating,
            rating_action=action_text or None,
            event_index=event_index,
        )

    def _is_header_line(self, line: str) -> bool:
        normalized = line.lower()
        if normalized in {
            "instrument / facility",
            "instrument/facility amount",
            "instrument facility",
            "security/ facility amount",
            "facility amount",
            "facility",
            "amount",
            "amount (rs. crore)",
            "current ratings",
            "previous ratings",
            "ratings",
            "rating",
            "rating action",
            "complexity",
            "complexity indicator",
            "indicator",
            "(rs. crore)",
            "security/ facility",
            "action",
        }:
            return True
        return (
            "current ratings" in normalized
            or normalized == "current"
            or normalized == "previous"
            or "previous ratings" in normalized
            or "rating action" in normalized
            or "complexity indicator" in normalized
            or normalized.startswith("instrument /")
            or normalized.startswith("instrument/")
            or normalized.startswith("(rs. crore)")
        )

    def _looks_like_new_row(self, line: str) -> bool:
        return INFOMERICS_ROW_START_PATTERN.match(line) is not None

    def _row_has_amount(self, row_lines: list[str]) -> bool:
        return any(re.search(r"\d+(?:\.\d+)?", line) for line in row_lines)

    def _row_has_rating(self, row_lines: list[str]) -> bool:
        return any("IVR" in line or "Withdrawn" in line for line in row_lines)
