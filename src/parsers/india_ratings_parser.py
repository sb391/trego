from __future__ import annotations

import re

from ..utils import compact_spaces, normalize_multiline_text, parse_amount_to_crore
from .base import BaseAgencyParser
from .common import build_rating_event


INDIA_RATINGS_ACTION_PATTERN = re.compile(
    r"\b(Affirmed|Assigned|Upgraded|Downgraded|Withdrawn|Maintained(?:\s+in\s+[^.;]+)?|Reaffirmed|Removed[^.;]*)\b",
    flags=re.I,
)
INDIA_RATINGS_SINGLE_LINE_ROW = re.compile(
    r"^(?P<instrument>.+?)\s+(?P<amount>INR\s*[\d,]+(?:\.\d+)?)\s+(?P<rest>.+)$",
    flags=re.I,
)


class IndiaRatingsParser(BaseAgencyParser):
    agency_name = "india_ratings"
    parser_name = "india_ratings_parser"

    def extract_rating_events(self, *, text, sections, rationale_doc_id, company_name, rating_date):
        lines = [compact_spaces(line) for line in normalize_multiline_text(text).splitlines() if compact_spaces(line)]
        table_lines = self._extract_table_lines(lines)
        events = []
        if table_lines:
            current: list[str] = []
            for line in table_lines:
                if self._is_table_header(line):
                    continue
                current.append(line)
                if INDIA_RATINGS_ACTION_PATTERN.match(line) or INDIA_RATINGS_SINGLE_LINE_ROW.match(line):
                    event = self._parse_row(
                        current,
                        rationale_doc_id=rationale_doc_id,
                        company_name=company_name,
                        rating_date=rating_date,
                        event_index=len(events) + 1,
                    )
                    if event:
                        events.append(event)
                    current = []
        if events:
            return events

        withdrawn_event = self._extract_discontinued_issuer_rating_event(
            text=text,
            rationale_doc_id=rationale_doc_id,
            company_name=company_name,
            rating_date=rating_date,
        )
        return [withdrawn_event] if withdrawn_event else []

    def _extract_table_lines(self, lines: list[str]) -> list[str]:
        capture = False
        table_lines: list[str] = []
        for line in lines:
            lowered = line.lower()
            if line in {"Details of Instruments", "Instrument Type", "Instrument"}:
                capture = True
                continue
            elif any(
                phrase in lowered
                for phrase in (
                    "instrument-wise rating actions are as follows",
                    "the instrument-wise rating actions are as follows",
                    "has taken the following rating actions on",
                    "has taken the following rating actions on ",
                )
            ):
                capture = True
                continue
            if not capture:
                continue
            if (
                line in {"Analytical Approach", "Detailed Rationale of the Rating Action", "Contact", "About the Company", "Key Rating Drivers"}
                or line.upper().startswith("ANALYTICAL APPROACH")
            ):
                break
            table_lines.append(line)
        return table_lines

    def _is_table_header(self, line: str) -> bool:
        normalized = compact_spaces(line).lower()
        header_labels = {
            "instrument type",
            "instrument description",
            "date of issuance",
            "coupon rate",
            "coupon rate (%)",
            "maturity date",
            "size of issue (million)",
            "rating assigned along with outlook/watch",
            "rating/outlook",
            "rating action",
            "instrument",
            "type",
            "size of issue",
            "rating",
            "action",
            "current ratings/",
            "outlook",
            "current",
            "rated",
            "limits",
            "limits (million)",
            "rating type",
            "historical rating/outlook",
        }
        return (
            normalized in header_labels
            or re.fullmatch(r"\(?million\)?", normalized, flags=re.I) is not None
            or normalized.startswith("*inr")
        )

    def _parse_row(self, row_lines: list[str], *, rationale_doc_id: str, company_name: str, rating_date, event_index: int):
        single_line_match = INDIA_RATINGS_SINGLE_LINE_ROW.match(row_lines[0])
        if single_line_match:
            rating_and_action = compact_spaces(single_line_match.group("rest"))
            action_match = INDIA_RATINGS_ACTION_PATTERN.search(rating_and_action)
            if not action_match:
                return None
            rating_text = compact_spaces(rating_and_action[: action_match.start()])
            action_text = compact_spaces(rating_and_action[action_match.start() :])
            if not rating_text.upper().startswith("IND "):
                return None
            return build_rating_event(
                rationale_doc_id=rationale_doc_id,
                company_name=company_name,
                agency_name=self.agency_name,
                rating_date=rating_date,
                instrument_type=single_line_match.group("instrument"),
                facility_amount=parse_amount_to_crore(single_line_match.group("amount"), unit_hint="million"),
                current_rating=rating_text,
                rating_action=action_text,
                event_index=event_index,
            )

        if len(row_lines) < 3:
            return None
        instrument_parts: list[str] = []
        for line in row_lines:
            if (
                line == "-"
                or "INR" in line
                or re.search(r"\bIND\b", line, flags=re.I)
                or INDIA_RATINGS_ACTION_PATTERN.search(line)
            ):
                break
            instrument_parts.append(line)

        instrument_type = compact_spaces(" ".join(instrument_parts)) if instrument_parts else row_lines[0]
        amount_line = next((line for line in row_lines if "INR" in line and re.search(r"\d", line)), None)
        rating_line = next((line for line in row_lines if re.search(r"\bIND\b", line, flags=re.I)), None)
        action_line = row_lines[-1]
        if not rating_line or not INDIA_RATINGS_ACTION_PATTERN.search(action_line):
            return None
        return build_rating_event(
            rationale_doc_id=rationale_doc_id,
            company_name=company_name,
            agency_name=self.agency_name,
            rating_date=rating_date,
            instrument_type=instrument_type,
            facility_amount=parse_amount_to_crore(amount_line, unit_hint="million") if amount_line else None,
            current_rating=rating_line,
            rating_action=action_line,
            event_index=event_index,
        )

    def _extract_discontinued_issuer_rating_event(self, *, text: str, rationale_doc_id: str, company_name: str, rating_date):
        normalized = normalize_multiline_text(text)
        if "discontinued voluntary disclosure of issuer ratings" not in normalized.lower():
            return None
        match = re.search(
            rf"outstanding voluntary issuer rating disclosure of {re.escape(company_name)} at (?P<rating>IND\s+[A-Z0-9+\-./ ]+) stands withdrawn",
            normalized,
            flags=re.I,
        )
        if not match:
            return None
        rating_text = compact_spaces(match.group("rating"))
        return build_rating_event(
            rationale_doc_id=rationale_doc_id,
            company_name=company_name,
            agency_name=self.agency_name,
            rating_date=rating_date,
            instrument_type="Issuer rating disclosure",
            facility_amount=None,
            current_rating=f"{rating_text}; Withdrawn",
            rating_action="Withdrawn",
            event_index=1,
        )
