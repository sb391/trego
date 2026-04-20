from __future__ import annotations

from typing import Iterable

from .schemas import CompanyCreditProfile, RationaleSection


class CreditNarrativeService:
    def build(self, profile: CompanyCreditProfile) -> tuple[list[RationaleSection], str]:
        sections = [
            self._company_snapshot(profile),
            self._financial_assessment(profile),
            self._rating_position(profile),
            self._treds_view(profile),
            self._advisory_view(profile),
            self._data_provenance(profile),
        ]
        filtered_sections = [section for section in sections if section is not None]
        draft = "\n\n".join(f"{section.heading}\n{section.body}" for section in filtered_sections)
        return filtered_sections, draft

    def _company_snapshot(self, profile: CompanyCreditProfile) -> RationaleSection:
        matched = profile.matched_company
        location = ", ".join(part for part in [matched.city if matched else None, matched.state if matched else None] if part)
        business_type = matched.business_type if matched else None
        overview_bits = [
            f"{profile.company_name} is currently classified as {profile.listed_status}.",
            _metric_sentence("The latest turnover considered by the platform is", profile.turnover_crore, "crore."),
            f"The company is mapped to the industry bucket '{profile.industry}'." if profile.industry else None,
            f"Business type is identified as {business_type}." if business_type else None,
            f"Operating location in the reference dataset is {location}." if location else None,
            profile.threshold_reason if profile.below_threshold_flag and profile.threshold_reason else None,
        ]
        return RationaleSection(
            heading="Company Snapshot",
            body=_join_sentences(overview_bits),
        )

    def _financial_assessment(self, profile: CompanyCreditProfile) -> RationaleSection:
        summary = profile.financial_summary
        lines = [
            _metric_sentence("Revenue available for assessment is", summary.revenue_crore, "crore."),
            _metric_sentence("EBITDA margin is", summary.ebitda_margin_pct, "%."),
            _metric_sentence("PAT margin is", summary.pat_margin_pct, "%."),
            _metric_sentence("Debt to equity is", summary.debt_to_equity, "x."),
            _metric_sentence("Interest coverage is", summary.interest_coverage, "x."),
            _metric_sentence("Working capital days are", summary.working_capital_days, "days."),
            _metric_sentence("Receivables days are", summary.receivables_days, "days."),
            _metric_sentence("Inventory days are", summary.inventory_days, "days."),
            _metric_sentence("Borrowings captured in the current view are", summary.total_borrowings_crore, "crore."),
            f"The primary financial source in this run is '{summary.source}'." if summary.source else None,
            f"The latest statement period referenced is {summary.statement_period}." if summary.statement_period else None,
        ]
        return RationaleSection(
            heading="Financial Assessment",
            body=_join_sentences(lines) or "A complete financial snapshot was not available for this run.",
        )

    def _rating_position(self, profile: CompanyCreditProfile) -> RationaleSection:
        rating = profile.rating_insight
        if rating.rating_available_flag:
            history_count = len(rating.history) if rating.history else 1
            lines = [
                f"An external rating is available from {rating.agency_name or 'a recognized agency'}.",
                f"The latest rating considered is {rating.rating}." if rating.rating else None,
                f"The outlook is {rating.outlook}." if rating.outlook else None,
                f"The rating date used is {rating.rating_date}." if rating.rating_date else None,
                f"The latest rating action is '{rating.rating_action}'." if rating.rating_action else None,
                f"The platform has preserved {history_count} rating event(s) for context.",
                *rating.notes,
            ]
        else:
            lines = [
                "No external rating was confirmed in the current run.",
                "The platform has flagged this case for simulated internal credit assessment in a later phase."
                if profile.simulation_required_flag
                else None,
                *rating.notes,
            ]
        return RationaleSection(
            heading="Credit Rating Position",
            body=_join_sentences(lines),
        )

    def _treds_view(self, profile: CompanyCreditProfile) -> RationaleSection:
        treds = profile.treds_insight
        lines = [
            f"TReDS signal strength is assessed as {treds.tred_signal_strength}.",
            f"The workflow used the '{treds.method_used}' method." if treds.method_used else None,
            f"Detected platforms include {', '.join(treds.tred_platforms_detected)}."
            if treds.tred_platforms_detected
            else "No direct TReDS platform mention was detected in the public search layer.",
            _metric_sentence("The estimated TReDS limit is", treds.estimated_treds_limit_crore, "crore.")
            if treds.method_used == "model"
            else None,
            f"Estimation confidence is {treds.estimation_confidence}." if treds.estimation_confidence else None,
        ]
        return RationaleSection(
            heading="TReDS View",
            body=_join_sentences(lines),
        )

    def _advisory_view(self, profile: CompanyCreditProfile) -> RationaleSection:
        notes = profile.advisory_insight.advisory_notes
        if notes:
            body = " ".join(f"Advisory {index + 1}: {note}" for index, note in enumerate(notes))
        else:
            body = "No rule-based advisory trigger was generated from the currently available data."
        return RationaleSection(
            heading="Advisory View",
            body=body,
        )

    def _data_provenance(self, profile: CompanyCreditProfile) -> RationaleSection:
        listed = profile.listed_insight
        lines: list[str | None] = [
            f"Listed/unlisted resolution source: {listed.source}." if listed and listed.source else None,
            f"Screener workbook was available at {listed.workbook_path}."
            if listed and listed.workbook_available and listed.workbook_path
            else "No Screener workbook was attached to this run."
            if listed
            else None,
            *profile.processing_notes,
        ]
        return RationaleSection(
            heading="Data Provenance",
            body=_join_sentences(lines) or "No additional provenance note was recorded.",
        )


def _metric_sentence(prefix: str, value: float | int | None, suffix: str) -> str | None:
    if value is None:
        return None
    return f"{prefix} {value:,.2f} {suffix}".replace(" %.", "%.").replace(" x.", "x.")


def _join_sentences(lines: Iterable[str | None]) -> str:
    return " ".join(line.strip() for line in lines if line and line.strip())
