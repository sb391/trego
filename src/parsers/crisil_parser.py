from __future__ import annotations

import re

from ..utils import compact_spaces, normalize_multiline_text, parse_amount_to_crore
from .base import BaseAgencyParser
from .common import build_rating_event


CRISIL_RATING_PATTERN = re.compile(
    r"CRISIL\s+(?:AAA|AA\+|AA-|AA|A1\+|A1|A2\+|A2|A3\+|A3|A4\+|A4|A\+|A-|BBB\+|BBB-|BBB|BB\+|BB-|BB|B\+|B-|C\+|A|B|C|D)"
    r"(?:/\s*(?:Stable|Positive|Negative))?"
    r"(?:/\s*CRISIL\s+(?:A1\+|A1|A2\+|A2|A3\+|A3|A4\+|A4))?",
    flags=re.I,
)
CRISIL_LONG_ONLY_PATTERN = re.compile(r"CRISIL\s+(?:AAA|AA\+|AA-|AA|A\+|A-|BBB\+|BBB-|BBB|BB\+|BB-|BB|B\+|B-|C\+|A|B|C|D)(?:/\s*(?:Stable|Positive|Negative))?", flags=re.I)
CRISIL_SHORT_ONLY_PATTERN = re.compile(r"CRISIL\s+(?:A1\+|A1|A2\+|A2|A3\+|A3|A4\+|A4)", flags=re.I)


class CrisilParser(BaseAgencyParser):
    agency_name = "crisil"
    parser_name = "crisil_parser"

    def extract_rating_events(self, *, text, sections, rationale_doc_id, company_name, rating_date):
        normalized = normalize_multiline_text(text[:15000])
        amount_match = re.search(r"Total Bank Loan Facilities Rated\s+Rs\.?\s*(\d+(?:\.\d+)?)\s*Crore", normalized, flags=re.I)
        amount = parse_amount_to_crore(amount_match.group(1)) if amount_match else None

        events = []
        events.extend(
            self._extract_top_label_events(
                normalized=normalized,
                rationale_doc_id=rationale_doc_id,
                company_name=company_name,
                rating_date=rating_date,
                default_amount=amount,
            )
        )
        if not events:
            events.extend(
                self._extract_credit_bulletin_events(
                    normalized=normalized,
                    rationale_doc_id=rationale_doc_id,
                    company_name=company_name,
                    rating_date=rating_date,
                )
            )
        if not events:
            body_event = self._extract_body_quote_event(
                normalized=normalized,
                rationale_doc_id=rationale_doc_id,
                company_name=company_name,
                rating_date=rating_date,
                default_amount=amount,
            )
            if body_event:
                events.append(body_event)
        if not events:
            events.extend(
                self._extract_legacy_pre_2014_events(
                    normalized=normalized,
                    rationale_doc_id=rationale_doc_id,
                    company_name=company_name,
                    rating_date=rating_date,
                )
            )
        return self._dedupe_events(events)

    def _extract_top_label_events(self, *, normalized: str, rationale_doc_id: str, company_name: str, rating_date, default_amount: float | None):
        events = []
        long_value = self._extract_label_value(
            normalized,
            label="Long Term Rating",
            next_labels=("Short Term Rating", "1 crore =", "Refer to annexure", "Refer to Annexure", "Detailed Rationale", "Rs.", "Any other information"),
        )
        short_value = self._extract_label_value(
            normalized,
            label="Short Term Rating",
            next_labels=("1 crore =", "Refer to annexure", "Refer to Annexure", "Detailed Rationale", "Rs.", "Any other information"),
        )
        fixed_deposit_value = self._extract_fixed_deposit_value(normalized)

        for instrument_type, value in (
            ("Bank Loan Facilities - Long Term", long_value),
            ("Bank Loan Facilities - Short Term", short_value),
            ("Fixed Deposits", fixed_deposit_value),
        ):
            rating_text, action_text = self._split_rating_and_action(value)
            if not rating_text:
                continue
            amount = default_amount
            if instrument_type == "Fixed Deposits":
                fixed_amount_match = re.search(r"Rs\.?\s*(\d+(?:\.\d+)?)\s*Crore\s*Fixed Deposits", normalized, flags=re.I)
                amount = parse_amount_to_crore(fixed_amount_match.group(1)) if fixed_amount_match else amount
            events.append(
                build_rating_event(
                    rationale_doc_id=rationale_doc_id,
                    company_name=company_name,
                    agency_name=self.agency_name,
                    rating_date=rating_date,
                    instrument_type=instrument_type,
                    facility_amount=amount,
                    current_rating=rating_text,
                    rating_action=action_text,
                    event_index=len(events) + 1,
                )
            )
        return events

    def _extract_credit_bulletin_events(self, *, normalized: str, rationale_doc_id: str, company_name: str, rating_date):
        header_match = re.search(r"Annexure\s*-\s*Details of Bank Lenders\s*&\s*Facilities", normalized, flags=re.I)
        if not header_match:
            return []
        body = normalized[header_match.end() :].strip()
        end_match = re.search(r"(Criteria Details|Links to related criteria|Media Relations|Analytical Contacts|Customer Service Helpdesk|Note for Media:)", body, flags=re.I)
        if end_match:
            body = body[: end_match.start()].strip()
        lines = [compact_spaces(line) for line in body.splitlines() if compact_spaces(line)]
        rows: list[list[str]] = []
        current: list[str] = []
        for line in lines:
            if line in {"Facility", "Amount (Rs.Crore)", "Amount", "Name of Lender", "Rating"}:
                continue
            current.append(line)
            if CRISIL_RATING_PATTERN.search(line):
                rows.append(current)
                current = []

        aggregated: dict[tuple[str, str], float] = {}
        for row_lines in rows:
            rating_line = next((line for line in reversed(row_lines) if CRISIL_RATING_PATTERN.search(line)), None)
            if not rating_line:
                continue
            rating_match = CRISIL_RATING_PATTERN.search(rating_line)
            if not rating_match:
                continue
            rating_text = compact_spaces(rating_match.group(0))
            amount_index = next((idx for idx, line in enumerate(row_lines) if re.fullmatch(r"\d+(?:\.\d+)?", line)), None)
            if amount_index is None:
                continue
            instrument_type = compact_spaces(" ".join(row_lines[:amount_index]).strip("& "))
            amount = parse_amount_to_crore(row_lines[amount_index])
            key = (instrument_type, rating_text)
            aggregated[key] = round(aggregated.get(key, 0.0) + (amount or 0.0), 4)

        events = []
        for (instrument_type, rating_text), amount in aggregated.items():
            events.append(
                build_rating_event(
                    rationale_doc_id=rationale_doc_id,
                    company_name=company_name,
                    agency_name=self.agency_name,
                    rating_date=rating_date,
                    instrument_type=instrument_type,
                    facility_amount=amount,
                    current_rating=rating_text,
                    event_index=len(events) + 1,
                )
            )
        return events

    def _extract_body_quote_event(self, *, normalized: str, rationale_doc_id: str, company_name: str, rating_date, default_amount: float | None):
        quote_match = re.search(
            r"(?:reaffirmed|assigned|migrating|upgraded|downgraded|withdrawn)[^'.]{0,120}'(?P<rating>CRISIL[^']+)'",
            normalized,
            flags=re.I,
        )
        if not quote_match:
            return None
        rating_text = compact_spaces(quote_match.group("rating"))
        rating_match = CRISIL_RATING_PATTERN.search(rating_text)
        if not rating_match:
            return None
        return build_rating_event(
            rationale_doc_id=rationale_doc_id,
            company_name=company_name,
            agency_name=self.agency_name,
            rating_date=rating_date,
            instrument_type="Bank Loan Facilities",
            facility_amount=default_amount,
            current_rating=rating_match.group(0),
            rating_action=compact_spaces(normalized[max(0, quote_match.start() - 30) : quote_match.end()].split(rating_match.group(0))[0]) or None,
            event_index=1,
        )

    def _extract_legacy_pre_2014_events(self, *, normalized: str, rationale_doc_id: str, company_name: str, rating_date):
        lines = [compact_spaces(line.replace("�", "")) for line in normalized.splitlines() if compact_spaces(line)]
        events = []
        for index, line in enumerate(lines[:-1]):
            amount_line_match = re.match(
                r"^Rs\.?\s*(?P<amount>\d+(?:\.\d+)?)\s+Million\s+(?P<instrument>.+)$",
                line,
                flags=re.I,
            )
            if not amount_line_match:
                continue
            rating_line = lines[index + 1]
            rating_match = re.match(
                r"^(?P<rating>(?:CRISIL\s+)?(?:AAA|AA\+|AA-|AA|A\+|A-|BBB\+|BBB-|BBB|BB\+|BB-|BB|B\+|B-|C\+|A|B|C|D|P1\+|P1|P2\+|P2|P3\+|P3|P4\+|P4|P5)(?:/\s*(?:AAA|AA\+|AA-|AA|A\+|A-|BBB\+|BBB-|BBB|BB\+|BB-|BB|B\+|B-|C\+|A|B|C|D|P1\+|P1|P2\+|P2|P3\+|P3|P4\+|P4|P5))?)\s*(?P<action>\(.+\))?$",
                rating_line,
                flags=re.I,
            )
            if not rating_match:
                continue
            previous_match = re.search(r"Downgraded from ['\"]?(?P<previous>[^'\")]+)", rating_line, flags=re.I)
            events.append(
                build_rating_event(
                    rationale_doc_id=rationale_doc_id,
                    company_name=company_name,
                    agency_name=self.agency_name,
                    rating_date=rating_date,
                    instrument_type=amount_line_match.group("instrument"),
                    facility_amount=parse_amount_to_crore(amount_line_match.group("amount"), unit_hint="million"),
                    current_rating=compact_spaces(rating_match.group("rating")),
                    previous_rating=compact_spaces(previous_match.group("previous")) if previous_match else None,
                    rating_action=compact_spaces(rating_match.group("action").strip("()")) if rating_match.group("action") else None,
                    event_index=len(events) + 1,
                )
            )
        return events

    def _extract_label_value(self, normalized: str, *, label: str, next_labels: tuple[str, ...]) -> str | None:
        next_pattern = "|".join(re.escape(value) for value in next_labels)
        pattern = rf"{re.escape(label)}\s+(?P<value>.+?)(?=(?:{next_pattern})|$)"
        match = re.search(pattern, normalized, flags=re.I | re.S)
        return compact_spaces(match.group("value")) if match else None

    def _extract_fixed_deposit_value(self, normalized: str) -> str | None:
        match = re.search(
            r"Rs\.?\s*\d+(?:\.\d+)?\s*Crore\s*Fixed Deposits\s+(?P<value>.+?)(?=(?:Note:|1 crore =|Refer to annexure|Refer to Annexure|Detailed Rationale|$))",
            normalized,
            flags=re.I | re.S,
        )
        return compact_spaces(match.group("value")) if match else None

    def _split_rating_and_action(self, value: str | None) -> tuple[str | None, str | None]:
        if not value:
            return None, None
        text = compact_spaces(value.lstrip("& "))
        rating_match = CRISIL_RATING_PATTERN.search(text) or CRISIL_LONG_ONLY_PATTERN.search(text) or CRISIL_SHORT_ONLY_PATTERN.search(text)
        if not rating_match:
            return None, None
        rating_text = compact_spaces(rating_match.group(0))
        action_text = compact_spaces(text[rating_match.end() :].strip(" -&"))
        action_text = re.sub(r"^\((?P<action>[^)]*)\)$", r"\g<action>", action_text)
        if action_text and "withdrawn" in action_text.lower() and "withdrawn" not in rating_text.lower():
            rating_text = f"{rating_text}; Withdrawn"
        return rating_text, action_text or None

    def _dedupe_events(self, events):
        deduped = []
        seen = set()
        for event in events:
            key = (event.instrument_type, event.current_rating, event.facility_amount)
            if key in seen:
                continue
            seen.add(key)
            deduped.append(event)
        return deduped
