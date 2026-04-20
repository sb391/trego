from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _env_flag(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(slots=True, frozen=True)
class CreditIntelConfig:
    data_dir: Path = Path("data")
    outputs_dir: Path = Path("outputs")
    agriculture_workbook_path: Path = Path("data/input/agriculture_companies.xlsx")
    turnover_threshold_crore: float = 250.0
    default_treds_utilization_factor: float = 0.45
    min_treds_utilization_factor: float = 0.30
    max_treds_utilization_factor: float = 0.60
    request_delay_seconds: float = 1.0
    max_search_results: int = 8
    rating_search_limit: int = 5
    treds_search_limit: int = 5
    public_risk_search_limit: int = 5
    industry_outlook_search_limit: int = 5
    enable_live_screener_lookup: bool = _env_flag("CREDIT_INTEL_ENABLE_LIVE_SCREENER_LOOKUP", False)
    enable_web_discovery: bool = _env_flag("CREDIT_INTEL_ENABLE_WEB_DISCOVERY", True)
    api_title: str = "Credit Intelligence Platform API"

    @property
    def base_dir(self) -> Path:
        return self.data_dir / "credit_intel"

    @property
    def cache_dir(self) -> Path:
        return self.base_dir / "cache"

    @property
    def profiles_cache_dir(self) -> Path:
        return self.cache_dir / "profiles"

    @property
    def search_cache_dir(self) -> Path:
        return self.cache_dir / "search"

    @property
    def rating_doc_cache_dir(self) -> Path:
        return self.cache_dir / "rating_docs"

    @property
    def workbook_cache_dir(self) -> Path:
        return self.cache_dir / "workbooks"

    @property
    def exports_dir(self) -> Path:
        return self.outputs_dir / "credit_intel"

    @property
    def batch_exports_dir(self) -> Path:
        return self.exports_dir / "batches"

    @property
    def word_exports_dir(self) -> Path:
        return self.exports_dir / "word_drafts"

    @property
    def sample_exports_dir(self) -> Path:
        return self.exports_dir / "samples"

    @property
    def sample_profiles_path(self) -> Path:
        return self.sample_exports_dir / "sample_profiles.json"

    @property
    def sample_workbook_path(self) -> Path:
        return self.sample_exports_dir / "agriculture_sample_batch.xlsx"

    def ensure_directories(self) -> None:
        for path in (
            self.base_dir,
            self.cache_dir,
            self.profiles_cache_dir,
            self.search_cache_dir,
            self.rating_doc_cache_dir,
            self.workbook_cache_dir,
            self.exports_dir,
            self.batch_exports_dir,
            self.word_exports_dir,
            self.sample_exports_dir,
        ):
            path.mkdir(parents=True, exist_ok=True)
