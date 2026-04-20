from __future__ import annotations

import re

from ..utils import compact_spaces, normalize_multiline_text, parse_amount_to_crore
from .base import BaseAgencyParser
from .common import build_rating_event, extract_rating_action


class AcuiteParser(BaseAgencyParser):
    agency_name = "acuite"
    parser_name = "acuite_parser"

    def extract_rating_events(self, *, text, sections, rationale_doc_id, company_name, rating_date):
        lines = [compact_spaces(line) for line in normalize_multiline_text(text).splitlines()]
        rows: list[str] = []
        in_table = False
        current_row: str | None = None

        for line in lines:
            if line.startswith("Product Quantum"):
                in_table = True
                continue
            if not in_table:
                continue
            if line.startswith(("Total Outstanding Quantum", "Rating Rationale", "Unsupported Rating")):
                break
            if line.startswith("Bank Loan Ratings"):
                if current_row:
                    rows.append(current_row)
                current_row = line
                continue
            if current_row and line:
                current_row = f"{current_row} {line}"

        if current_row:
            rows.append(current_row)

        events = []
        for row in rows:
            match = re.search(r"Bank Loan Ratings\s+(\d+(?:\.\d+)?)\s+(.*)$", row, flags=re.I)
            if not match:
                continue
            amount = parse_amount_to_crore(match.group(1))
            remainder = match.group(2)
            short_rating_match = re.search(
                r"(?<![A-Z0-9])(ACUITE\s+(?:A1\+|A1|A2\+|A2|A3\+|A3|A4\+|A4|D))(?![A-Z0-9])",
                remainder.upper(),
                flags=re.I,
            )
            current_rating_match = re.search(
                r"(?<![A-Z0-9])(ACUITE\s+(?:AAA|AA\+|AA-|AA|A\+|A-|BBB\+|BBB-|BBB|BB\+|BB-|BB|B\+|B-|C\+|A|B|C|D)(?:\s*\|\s*(?:STABLE|POSITIVE|NEGATIVE|DEVELOPING))?)(?![A-Z0-9])",
                remainder.upper(),
                flags=re.I,
            )

            current_rating = short_rating_match.group(1) if short_rating_match else None
            if not current_rating and current_rating_match:
                current_rating = current_rating_match.group(1)
            if not current_rating and "Withdrawn" in remainder:
                current_rating = "Withdrawn"

            events.append(
                build_rating_event(
                    rationale_doc_id=rationale_doc_id,
                    company_name=company_name,
                    agency_name=self.agency_name,
                    rating_date=rating_date,
                    instrument_type="Bank Loan Ratings",
                    facility_amount=amount,
                    current_rating=current_rating,
                    rating_action=(extract_rating_action(remainder) or "Withdrawn") if "Withdrawn" in remainder else extract_rating_action(remainder),
                    event_index=len(events) + 1,
                )
            )
        return events
