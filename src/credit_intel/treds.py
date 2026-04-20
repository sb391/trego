from __future__ import annotations

from typing import Iterable

from .config import CreditIntelConfig
from .schemas import FinancialSummary, RatingInsight, TredsInsight
from .search_engine import SearchEngineClient


PLATFORM_MAP = {
    "rxil": "RXIL",
    "m1xchange": "M1xchange",
    "invoicemart": "Invoicemart",
    "kredx": "KredX",
    "treds": "TReDS",
    "invoice discounting": "Invoice Discounting",
}


class TredsInsightService:
    def __init__(self, config: CreditIntelConfig) -> None:
        self.config = config
        self.search_client = SearchEngineClient(config)

    def build(self, company_name: str, financial_summary: FinancialSummary, rating_insight: RatingInsight) -> TredsInsight:
        query = f'{company_name} ("TReDS" OR "RXIL" OR "M1xchange" OR "Invoicemart" OR "KredX" OR "invoice discounting")'
        mentions = self.search_client.search(query, max_results=self.config.treds_search_limit)
        platforms = self._detect_platforms(mentions)
        signal_strength = self._signal_strength(platforms, mentions)
        raw_mentions = [self._format_mention(item) for item in mentions[:5]]

        if signal_strength in {"high", "medium"}:
            return TredsInsight(
                tred_presence_flag=True,
                tred_platforms_detected=platforms,
                tred_signal_strength=signal_strength,
                tred_raw_mentions=raw_mentions,
                method_used="proxy",
            )

        estimated_limit, confidence = self._estimate_limit(financial_summary, rating_insight)
        return TredsInsight(
            tred_presence_flag=False,
            tred_platforms_detected=platforms,
            tred_signal_strength=signal_strength,
            tred_raw_mentions=raw_mentions,
            estimated_treds_limit_crore=estimated_limit,
            estimation_confidence=confidence,
            method_used="model",
        )

    def _detect_platforms(self, mentions: Iterable[dict]) -> list[str]:
        detected: list[str] = []
        for mention in mentions:
            haystack = " ".join(
                [
                    str(mention.get("title") or ""),
                    str(mention.get("snippet") or ""),
                    str(mention.get("url") or ""),
                ]
            ).lower()
            for token, label in PLATFORM_MAP.items():
                if token in haystack and label not in detected:
                    detected.append(label)
        return detected

    def _signal_strength(self, platforms: list[str], mentions: list[dict]) -> str:
        if platforms:
            return "high"
        mention_blob = " ".join(self._format_mention(item).lower() for item in mentions)
        if "treds" in mention_blob or "invoice discounting" in mention_blob:
            return "medium"
        return "low"

    def _estimate_limit(self, financial_summary: FinancialSummary, rating_insight: RatingInsight) -> tuple[float | None, str]:
        revenue = financial_summary.revenue_crore
        receivables_days = financial_summary.receivables_days
        if revenue is None or receivables_days is None:
            return None, "low"

        utilization = self.config.default_treds_utilization_factor
        if receivables_days > 120:
            utilization += 0.05
        elif receivables_days < 60:
            utilization -= 0.05

        rating = (rating_insight.rating or "").upper()
        if rating.startswith(("AAA", "AA", "A1")):
            utilization += 0.05
        elif rating.startswith(("BB", "B", "C", "D")):
            utilization -= 0.05

        utilization = min(max(utilization, self.config.min_treds_utilization_factor), self.config.max_treds_utilization_factor)
        estimated = round(revenue * (receivables_days / 365.0) * utilization, 2)
        confidence = "medium" if rating_insight.rating_available_flag else "low"
        return estimated, confidence

    def _format_mention(self, mention: dict) -> str:
        title = str(mention.get("title") or "").strip()
        snippet = str(mention.get("snippet") or "").strip()
        url = str(mention.get("url") or "").strip()
        return " | ".join(part for part in [title, snippet, url] if part)
