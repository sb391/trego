from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..config import AppConfig
from ..io_utils import build_company_id, company_name_tokens, normalize_company_name, sanitize_filename
from ..models import CorporateRecord
from ..screener_download import ScreenerDownloadBrowser, build_download_filename
from ..screener_matcher import choose_best_match
from ..screener_search import ScreenerSearchBrowser
from .cache import load_json, profile_cache_path, save_json
from .config import CreditIntelConfig
from .dataset import AgricultureDatasetService
from .external_simulation_benchmark import build_live_company_simulation
from .exporter import CreditProfileExcelExporter, CreditProfileWordExporter
from .narrative import CreditNarrativeService
from .rating_discovery import RatingDiscoveryService
from .rating_repository import ExistingRatingRepository, parse_rating_text
from .schemas import CompanyCreditProfile, FinancialSummary, ListedInsight, MatchedDatasetCompany
from .treds import TredsInsightService
from .advisory import AdvisoryService
from .workbook_parser import ScreenerWorkbookParser


LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class ScreenerMatch:
    listed_status: str
    screener_url: str | None
    confidence: float | None
    source: str


class CreditIntelligenceOrchestrator:
    def __init__(self, config: CreditIntelConfig | None = None) -> None:
        self.config = config or CreditIntelConfig()
        self.config.ensure_directories()
        self.dataset_service = AgricultureDatasetService(self.config)
        self.rating_repository = ExistingRatingRepository(Path("outputs/credit_rating_history.csv"))
        self.rating_discovery = RatingDiscoveryService(self.config, self.rating_repository)
        self.treds_service = TredsInsightService(self.config)
        self.advisory_service = AdvisoryService()
        self.narrative_service = CreditNarrativeService()
        self.workbook_parser = ScreenerWorkbookParser()
        self.exporter = CreditProfileExcelExporter(self.config)
        self.word_exporter = CreditProfileWordExporter(self.config)
        self.browser_config = AppConfig(headless=True)

    def process_company(self, company_name: str, *, force_refresh: bool = False) -> CompanyCreditProfile:
        cache_key = sanitize_filename(normalize_company_name(company_name) or company_name)
        cache_path = profile_cache_path(self.config, cache_key)
        if cache_path.exists() and not force_refresh:
            cached = load_json(cache_path)
            if cached:
                profile = CompanyCreditProfile.model_validate(cached)
                updated_cache = False
                if not _profile_has_live_simulation(profile):
                    self._attach_live_simulation(profile)
                    updated_cache = True
                if not profile.rationale_sections and not profile.rationale_draft:
                    self._attach_rationale(profile)
                    updated_cache = True
                if updated_cache:
                    save_json(cache_path, profile.model_dump(mode="json"))
                return profile

        matched = self.dataset_service.match_company(company_name)
        if matched is None:
            profile = CompanyCreditProfile(
                company_name=company_name,
                requested_name=company_name,
                processing_notes=["No match found in the agriculture company master dataset."],
                simulation_required_flag=True,
            )
            self._attach_rationale(profile)
            save_json(cache_path, profile.model_dump(mode="json"))
            return profile

        profile = CompanyCreditProfile(
            company_name=matched.company_name,
            requested_name=company_name,
            company_id=matched.company_id,
            industry=matched.sector,
            listed_status=matched.listing_status or "unknown",
            turnover_crore=matched.total_revenue_crore,
            matched_company=matched,
        )

        if (matched.total_revenue_crore or 0) < self.config.turnover_threshold_crore:
            profile.below_threshold_flag = True
            profile.threshold_reason = f"Turnover below threshold of {self.config.turnover_threshold_crore:.0f} crore."
            profile.financial_summary = self._financial_summary_from_dataset(matched)
            profile.rating_insight = parse_rating_text(matched.latest_ratings_text)
            profile.treds_insight = self.treds_service.build(profile.company_name, profile.financial_summary, profile.rating_insight)
            profile.advisory_insight = self.advisory_service.build(profile.financial_summary, profile.rating_insight, profile.treds_insight)
            profile.simulation_required_flag = not profile.rating_insight.rating_available_flag
            profile.processing_notes.append("Deep processing skipped because turnover is below threshold.")
            self._attach_live_simulation(profile)
            self._attach_rationale(profile)
            save_json(cache_path, profile.model_dump(mode="json"))
            return profile

        screener_match = self._resolve_listed_status(matched)
        profile.listed_status = screener_match.listed_status
        profile.listed_insight = ListedInsight(
            listed_status=screener_match.listed_status,
            screener_url=screener_match.screener_url,
            screener_match_confidence=screener_match.confidence,
            source=screener_match.source,
        )

        if screener_match.listed_status == "listed":
            workbook_path = self._ensure_screener_workbook(matched, screener_match.screener_url)
            if workbook_path:
                parsed_workbook = self.workbook_parser.parse(workbook_path)
                workbook_summary = FinancialSummary.model_validate(parsed_workbook["financial_summary"])
                dataset_summary = self._financial_summary_from_dataset(matched, source="agriculture_dataset_fallback")
                profile.financial_summary = self._merge_financial_summaries(workbook_summary, dataset_summary)
                profile.financial_tables = {
                    "profit_loss": parsed_workbook["profit_loss"],
                    "quarterly_results": parsed_workbook["quarterly_results"],
                    "balance_sheet": parsed_workbook["balance_sheet"],
                    "cash_flow": parsed_workbook["cash_flow"],
                }
                profile.listed_insight.workbook_path = str(workbook_path)
                profile.listed_insight.workbook_available = True
            else:
                profile.financial_summary = self._financial_summary_from_dataset(matched, source="agriculture_dataset_fallback")
                profile.processing_notes.append("Screener workbook not available; dataset financial summary used.")
        else:
            profile.financial_summary = self._financial_summary_from_dataset(matched)

        profile.rating_insight = self.rating_discovery.discover(profile.company_name, dataset_rating_text=matched.latest_ratings_text)
        profile.treds_insight = self.treds_service.build(profile.company_name, profile.financial_summary, profile.rating_insight)
        profile.advisory_insight = self.advisory_service.build(profile.financial_summary, profile.rating_insight, profile.treds_insight)
        profile.simulation_required_flag = not profile.rating_insight.rating_available_flag
        self._attach_live_simulation(profile)
        self._attach_rationale(profile)

        save_json(cache_path, profile.model_dump(mode="json"))
        return profile

    def process_batch(self, company_names: list[str], *, force_refresh: bool = False) -> list[CompanyCreditProfile]:
        return [self.process_company(company_name, force_refresh=force_refresh) for company_name in company_names if company_name.strip()]

    def export_company_profile(self, profile: CompanyCreditProfile) -> Path:
        return self.exporter.export_company(profile)

    def export_company_word_profile(self, profile: CompanyCreditProfile) -> Path:
        return self.word_exporter.export_company(profile)

    def export_batch_profiles(self, profiles: list[CompanyCreditProfile]) -> Path:
        batch_id = hashlib.sha1("|".join(profile.company_name for profile in profiles).encode("utf-8")).hexdigest()[:12]
        return self.exporter.export_batch(batch_id, profiles)

    def default_sample_company_names(self, *, limit: int = 5) -> list[str]:
        return self.dataset_service.get_default_sample_companies(limit=limit)

    def _merge_financial_summaries(
        self,
        primary: FinancialSummary,
        fallback: FinancialSummary,
    ) -> FinancialSummary:
        payload = fallback.model_dump()
        payload.update({key: value for key, value in primary.model_dump().items() if value is not None})
        return FinancialSummary.model_validate(payload)

    def _attach_rationale(self, profile: CompanyCreditProfile) -> None:
        sections, draft = self.narrative_service.build(profile)
        profile.rationale_sections = sections
        profile.rationale_draft = draft

    def _attach_live_simulation(self, profile: CompanyCreditProfile) -> None:
        try:
            profile.simulation = build_live_company_simulation(profile=profile)
        except Exception as exc:  # noqa: BLE001
            LOGGER.warning("Live simulation failed for %s: %s", profile.company_name, exc)
            profile.processing_notes.append("Live simulation payload could not be generated.")

    def _financial_summary_from_dataset(self, matched: MatchedDatasetCompany, *, source: str = "agriculture_dataset") -> FinancialSummary:
        working_capital_days = None
        if matched.receivables_days is not None and matched.inventory_days is not None:
            working_capital_days = round(matched.receivables_days + matched.inventory_days, 2)
        return FinancialSummary(
            revenue_crore=matched.total_revenue_crore,
            ebitda_margin_pct=matched.ebitda_margin_pct,
            pat_margin_pct=matched.pat_margin_pct,
            debt_to_equity=matched.debt_to_equity,
            interest_coverage=matched.interest_coverage,
            working_capital_days=working_capital_days,
            receivables_days=matched.receivables_days,
            inventory_days=matched.inventory_days,
            networth_crore=matched.networth_crore,
            total_borrowings_crore=matched.total_borrowings_crore,
            source=source,
            statement_period=matched.latest_balance_sheet,
        )

    def _resolve_listed_status(self, matched: MatchedDatasetCompany) -> ScreenerMatch:
        dataset_status = (matched.listing_status or "unknown").lower()
        if not self.config.enable_live_screener_lookup:
            source = "dataset_listing_status"
            return ScreenerMatch(
                listed_status="listed" if dataset_status == "listed" else "unlisted",
                screener_url=None,
                confidence=matched.match_confidence,
                source=source,
            )

        record = CorporateRecord(
            row_index=0,
            company_id=build_company_id(matched.company_name, None, None, 0),
            company_name=matched.company_name,
            search_name=matched.company_name,
            normalized_name=normalize_company_name(matched.company_name),
            normalized_tokens=company_name_tokens(matched.company_name),
            nse_code=None,
            bse_code=None,
            isin_code=None,
            industry_group=matched.sector,
            industry=matched.business_type,
        )
        try:
            with ScreenerSearchBrowser(self.browser_config) as search_browser:
                candidates = search_browser.search(matched.company_name)
            decision = choose_best_match(
                record,
                candidates,
                auto_threshold=self.browser_config.similarity_auto_threshold,
                ambiguity_gap_threshold=self.browser_config.ambiguity_gap_threshold,
            )
            if decision.status == "matched" and decision.matched_candidate is not None:
                return ScreenerMatch(
                    listed_status="listed",
                    screener_url=decision.matched_candidate.url,
                    confidence=decision.confidence,
                    source="screener_search",
                )
        except Exception as exc:  # noqa: BLE001
            LOGGER.warning("Screener live lookup failed for %s: %s", matched.company_name, exc)

        return ScreenerMatch(
            listed_status="listed" if dataset_status == "listed" else "unlisted",
            screener_url=None,
            confidence=matched.match_confidence,
            source="dataset_listing_status_fallback",
        )

    def _ensure_screener_workbook(self, matched: MatchedDatasetCompany, screener_url: str | None) -> Path | None:
        candidate = self._find_existing_workbook(matched.company_name)
        if candidate:
            return candidate
        if not screener_url:
            return None

        storage_state = self.browser_config.storage_state_path
        if not storage_state.exists():
            return None

        target_name = build_download_filename(matched.company_name, None, matched.cin)
        target_path = self.config.workbook_cache_dir / target_name
        try:
            with ScreenerDownloadBrowser(
                self.browser_config,
                storage_state_path=storage_state,
                interactive_login=False,
            ) as download_browser:
                download_browser.download_company_workbook(
                    company_name=matched.company_name,
                    nse_code=None,
                    bse_code=matched.cin,
                    screener_url=screener_url,
                    downloads_dir=self.config.workbook_cache_dir,
                    force=False,
                )
        except Exception as exc:  # noqa: BLE001
            LOGGER.warning("Unable to download Screener workbook for %s: %s", matched.company_name, exc)
            return None
        return target_path if target_path.exists() else None

    def _find_existing_workbook(self, company_name: str) -> Path | None:
        normalized = normalize_company_name(company_name).replace(" ", "")
        search_dirs = [Path("data/downloads"), self.config.workbook_cache_dir]
        for directory in search_dirs:
            if not directory.exists():
                continue
            for path in directory.glob("*.xlsx"):
                if normalize_company_name(path.stem).replace(" ", "").startswith(normalized[:18]):
                    return path
        return None


def _profile_has_live_simulation(profile: CompanyCreditProfile) -> bool:
    extra_payload = profile.model_extra or {}
    raw_simulation = extra_payload.get("simulation") if isinstance(extra_payload, dict) else None
    return isinstance(raw_simulation, dict) and bool(raw_simulation.get("rating_range"))
