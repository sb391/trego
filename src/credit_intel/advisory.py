from __future__ import annotations

from .schemas import AdvisoryInsight, FinancialSummary, RatingInsight, TredsInsight


class AdvisoryService:
    def build(
        self,
        financial_summary: FinancialSummary,
        rating_insight: RatingInsight,
        treds_insight: TredsInsight,
    ) -> AdvisoryInsight:
        notes: list[str] = []
        if (financial_summary.receivables_days or 0) > 120:
            notes.append("Receivable days are elevated; improve collections and tighten working-capital controls.")
        if (financial_summary.debt_to_equity or 0) > 2.0:
            notes.append("Leverage appears high; evaluate deleveraging and debt-structure optimization.")
        if (financial_summary.ebitda_margin_pct or 0) < 10.0:
            notes.append("Margins are thin; focus on pricing discipline, mix improvement, and cost control.")
        if not rating_insight.rating_available_flag:
            notes.append("No external rating found; manual credit underwriting and internal simulation should be prioritized.")
        if treds_insight.method_used == "model":
            notes.append("TReDS capacity is estimated from financial proxies; validate with banker or platform data before use.")
        return AdvisoryInsight(advisory_notes=notes)
