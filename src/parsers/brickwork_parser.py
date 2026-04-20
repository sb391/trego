from __future__ import annotations

import re

from ..utils import compact_spaces, normalize_multiline_text
from .base import BaseAgencyParser
from .common import build_rating_event


BRICKWORK_RATING_TOKEN = re.compile(
    r"BWR\s+[A-Z0-9+\-]+(?:\s*/\s*(?:Stable|Negative|Positive))?(?:\s*\((?:Stable|Negative|Positive|Withdrawal|ISSUER NOT COOPERATING[^)]*)\))?",
    flags=re.I,
)


class BrickworkParser(BaseAgencyParser):
    agency_name = "brickwork"
    parser_name = "brickwork_parser"

    def extract_rating_events(self, *, text, sections, rationale_doc_id, company_name, rating_date):
        normalized = normalize_multiline_text(text)
        collapsed = " ".join(normalized.split())
        events = []

        for term_label, instrument_type, stop_pattern in (
            ("Long Term", "Long Term", r"(?:Short term|Short Term|Non Fund Based|Fund Based|Total|Grand Total|RATING ACTION|Rating Action|www\.brickworkratings|Page \d|$)"),
            ("Short Term", "Short Term", r"(?:Non Fund Based|Fund Based|Total|Grand Total|RATING ACTION|Rating Action|www\.brickworkratings|Page \d|$)"),
        ):
            body_match = re.search(rf"{term_label}\s+(?P<body>.*?)(?={stop_pattern})", collapsed, flags=re.I)
            if not body_match:
                continue
            event = self._build_event_from_body(
                body=body_match.group("body"),
                instrument_type=instrument_type,
                rationale_doc_id=rationale_doc_id,
                company_name=company_name,
                rating_date=rating_date,
                event_index=len(events) + 1,
            )
            if event:
                events.append(event)

        if not events:
            events.extend(
                self._fallback_from_rating_action(
                    collapsed=collapsed,
                    rationale_doc_id=rationale_doc_id,
                    company_name=company_name,
                    rating_date=rating_date,
                )
            )
        return events

    def _build_event_from_body(
        self,
        *,
        body: str,
        instrument_type: str,
        rationale_doc_id: str,
        company_name: str,
        rating_date,
        event_index: int,
    ):
        rating_tokens = [compact_spaces(match.group(0)).replace(" /", "/").replace("/ ", "/") for match in BRICKWORK_RATING_TOKEN.finditer(body)]
        if not rating_tokens:
            return None

        previous_rating = rating_tokens[0] if len(rating_tokens) > 1 else None
        if len(rating_tokens) > 1:
            current_rating = rating_tokens[1]
        elif re.search(r"withdraw", body, flags=re.I):
            current_rating = "Withdrawn"
        else:
            current_rating = rating_tokens[0]

        if re.search(r"issuer not cooperating|best available information", body, flags=re.I) and "ISSUER NOT COOPERATING" not in current_rating.upper():
            current_rating = f"{current_rating}; ISSUER NOT COOPERATING"

        action_match = re.search(r"\b(Upgrade|Upgraded|Downgrade|Downgraded|Reaffirmed|Withdrawal|Withdrawn|Assigned)\b", body, flags=re.I)
        action_text = action_match.group(0).title() if action_match else None

        return build_rating_event(
            rationale_doc_id=rationale_doc_id,
            company_name=company_name,
            agency_name=self.agency_name,
            rating_date=rating_date,
            instrument_type=instrument_type,
            facility_amount=None,
            current_rating=current_rating,
            previous_rating=previous_rating,
            rating_action=action_text,
            event_index=event_index,
        )

    def _fallback_from_rating_action(self, *, collapsed: str, rationale_doc_id: str, company_name: str, rating_date):
        action_match = re.search(
            r"\bat\s+BWR\s+(?P<long>[A-Z0-9+\-]+)\s*/\s*(?:(?P<outlook>Stable|Negative|Positive)\s*/)?(?P<short>A[1-4]\+?|D)\b",
            collapsed,
            flags=re.I,
        )
        if not action_match:
            return []

        long_rating = f"BWR {action_match.group('long')}"
        if action_match.group("outlook"):
            long_rating = f"{long_rating}/{action_match.group('outlook').title()}"
        if re.search(r"issuer not cooperating|best available information", collapsed, flags=re.I):
            long_rating = f"{long_rating}; ISSUER NOT COOPERATING"
        short_rating = f"BWR {action_match.group('short').upper()}"
        if re.search(r"issuer not cooperating|best available information", collapsed, flags=re.I):
            short_rating = f"{short_rating}; ISSUER NOT COOPERATING"

        return [
            build_rating_event(
                rationale_doc_id=rationale_doc_id,
                company_name=company_name,
                agency_name=self.agency_name,
                rating_date=rating_date,
                instrument_type="Long Term",
                facility_amount=None,
                current_rating=long_rating,
                rating_action="Reaffirmed",
                event_index=1,
            ),
            build_rating_event(
                rationale_doc_id=rationale_doc_id,
                company_name=company_name,
                agency_name=self.agency_name,
                rating_date=rating_date,
                instrument_type="Short Term",
                facility_amount=None,
                current_rating=short_rating,
                rating_action="Reaffirmed",
                event_index=2,
            ),
        ]
