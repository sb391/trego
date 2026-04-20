from __future__ import annotations

import re

from ..utils import compact_spaces, normalize_multiline_text, parse_amount_to_crore
from .base import BaseAgencyParser
from .common import build_rating_event, extract_rating_action


CARE_INSTRUMENT_PATTERN = re.compile(
    r"^(?P<instrument>"
    r"(?:Long(?:\s*-\s*|\s+)term(?:\s*/\s*Short(?:\s*-\s*|\s+)term)?"
    r"|Short(?:\s*-\s*|\s+)term(?:\s*/\s*Long(?:\s*-\s*|\s+)term)?"
    r"|Fixed deposits?"
    r"|Commercial paper"
    r"|Non[- ]convertible debentures?"
    r"|Optionally(?:\s+Fully)?\s+Convertible\s+Debentures?"
    r"|Debentures?"
    r"|Issuer rating)"
    r"(?:\s+bank)?(?:\s+facilities?|\s+facility|\s+limits?)?"
    r"(?:\s*-\s*[A-Za-z0-9()/]+(?:\s+[A-Za-z0-9()/]+)*)*"
    r")\b",
    flags=re.I,
)
CARE_INLINE_RATING_PATTERN = re.compile(
    r"(?P<company>[A-Z][A-Za-z0-9&.,'() -]+?)\s*\((?:[^)]*?\brated\s+)(?P<rating>CARE\s+[A-Z0-9+;/ .()'-]+)\)",
    flags=re.I | re.S,
)
CARE_ACTION_PATTERN = re.compile(
    r"\b(Upgraded|Reaffirmed|Downgraded|Assigned|Withdrawn|Revised|Removed|Continues to remain)\b",
    flags=re.I,
)


class CareParser(BaseAgencyParser):
    agency_name = "care"
    parser_name = "care_parser"

    def extract_rating_events(self, *, text, sections, rationale_doc_id, company_name, rating_date):
        table_block = self._extract_table_block(text)
        events = []
        if table_block:
            for row in self._collect_rows(table_block):
                event = self._parse_row(
                    row=row,
                    rationale_doc_id=rationale_doc_id,
                    company_name=company_name,
                    rating_date=rating_date,
                    event_index=len(events) + 1,
                )
                if event:
                    events.append(event)
        if events:
            return events

        inline_event = self._extract_inline_credit_update_event(
            text=text,
            rationale_doc_id=rationale_doc_id,
            company_name=company_name,
            rating_date=rating_date,
        )
        return [inline_event] if inline_event else []

    def _extract_table_block(self, text: str) -> str | None:
        normalized = normalize_multiline_text(text)
        start_match = re.search(r"(Facilities(?:/Instruments)?|Instruments?|Ratings)\s+Amount", normalized, flags=re.I)
        if not start_match:
            return None
        body = normalized[start_match.end() :].strip()
        end_match = re.search(
            r"(Details of instruments/facilities|Details of instruments|Details of facilities|Rationale and key rating drivers|Detailed description of the key rating drivers|Rationale)",
            body,
            flags=re.I,
        )
        return body[: end_match.start()].strip() if end_match else body

    def _collect_rows(self, table_block: str) -> list[str]:
        rows: list[str] = []
        current: list[str] = []
        for raw_line in table_block.splitlines():
            line = compact_spaces(raw_line)
            if not line or line.startswith(("Amount", "Rating1", "Ratings1", "Rating Action")):
                continue
            if CARE_INSTRUMENT_PATTERN.match(line):
                if current:
                    rows.append(" ".join(current))
                current = [line]
            elif current:
                current.append(line)
        if current:
            rows.append(" ".join(current))
        return rows

    def _parse_row(self, *, row: str, rationale_doc_id: str, company_name: str, rating_date, event_index: int):
        match = CARE_INSTRUMENT_PATTERN.match(row)
        if not match:
            return None
        instrument_type = compact_spaces(match.group("instrument"))

        remainder = compact_spaces(row[match.end() :])
        amount_match = re.match(r"(?P<amount>(?:\d[\d.,]*|-)(?:\s*\([^)]*\))?)\s+(?P<rest>.+)$", remainder)
        amount = parse_amount_to_crore(amount_match.group("amount")) if amount_match else None
        rest = amount_match.group("rest") if amount_match else remainder
        rest = compact_spaces(rest)
        rest_without_placeholders = rest.lstrip("- ").strip()

        current_rating: str | None
        action_text: str | None
        previous_rating: str | None = None

        if rest_without_placeholders.lower().startswith("withdrawn"):
            current_rating = "Withdrawn"
            action_text = rest_without_placeholders
        else:
            action_match = CARE_ACTION_PATTERN.search(rest)
            if action_match:
                current_rating = compact_spaces(rest[: action_match.start()])
                action_text = compact_spaces(rest[action_match.start() :])
            else:
                current_rating = rest
                action_text = extract_rating_action(rest)

            previous_match = re.search(
                r"\bfrom\s+(?P<previous>CARE\s+[A-Z0-9+;/ .()*:-]+?)(?=(?:\s+and\b|\s*;|$))",
                action_text or "",
                flags=re.I,
            )
            if previous_match:
                previous_rating = compact_spaces(previous_match.group("previous"))

            if current_rating in {"-", ""} and action_text and "withdraw" in action_text.lower():
                current_rating = "Withdrawn"

        return build_rating_event(
            rationale_doc_id=rationale_doc_id,
            company_name=company_name,
            agency_name=self.agency_name,
            rating_date=rating_date,
            instrument_type=instrument_type,
            facility_amount=amount,
            current_rating=current_rating,
            previous_rating=previous_rating,
            rating_action=action_text,
            event_index=event_index,
        )

    def _extract_inline_credit_update_event(self, *, text: str, rationale_doc_id: str, company_name: str, rating_date):
        normalized = normalize_multiline_text(text)
        company_pattern = re.escape(company_name)
        match = re.search(
            rf"{company_pattern}\s*\((?:[^)]*?\brated\s+)(?P<rating>CARE\s+[A-Z0-9+;/ .()'-]+)\)",
            normalized,
            flags=re.I | re.S,
        )
        if not match:
            company_tokens = self._token_set(company_name)
            best_match = None
            best_score = 0
            for candidate in CARE_INLINE_RATING_PATTERN.finditer(normalized):
                score = len(company_tokens & self._token_set(candidate.group("company")))
                if score > best_score:
                    best_match = candidate
                    best_score = score
            if best_match and best_score >= 2:
                match = best_match
        if not match:
            return None
        return build_rating_event(
            rationale_doc_id=rationale_doc_id,
            company_name=company_name,
            agency_name=self.agency_name,
            rating_date=rating_date,
            instrument_type="Credit update",
            facility_amount=None,
            current_rating=compact_spaces(match.group("rating")),
            rating_action="Credit update",
            event_index=1,
        )

    @staticmethod
    def _token_set(value: str) -> set[str]:
        return {token for token in re.findall(r"[A-Za-z]{3,}", value.lower())}
