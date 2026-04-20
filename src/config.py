from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


BASE_URL = "https://www.screener.in/"
SEARCH_INPUT_SELECTOR = 'input[data-company-search="true"]'
SEARCH_API_PATH = "/api/company/search/"
EXPORT_BUTTON_SELECTOR = 'button[aria-label="Export to Excel"]'
CREDIT_RATING_LINK_SELECTOR = 'a:has-text("Rating update")'
REFERENCE_SHEET_NAMES = (
    "Profit & Loss",
    "Quarters",
    "Balance Sheet",
    "Cash Flow",
    "Customization",
    "Data Sheet",
)


@dataclass(slots=True, frozen=True)
class AppConfig:
    base_url: str = BASE_URL
    headless: bool = True
    search_delay_ms: int = 140
    search_settle_ms: int = 1400
    search_timeout_ms: int = 15000
    company_page_timeout_ms: int = 30000
    export_timeout_ms: int = 30000
    credit_rating_timeout_ms: int = 30000
    export_button_selector: str = EXPORT_BUTTON_SELECTOR
    credit_rating_link_selector: str = CREDIT_RATING_LINK_SELECTOR
    inter_company_sleep_seconds: float = 3.0
    inter_document_sleep_seconds: float = 1.2
    similarity_auto_threshold: float = 0.86
    ambiguity_gap_threshold: float = 0.08
    max_candidates: int = 8
    data_dir: Path = Path("data")
    outputs_dir: Path = Path("outputs")

    @property
    def downloads_dir(self) -> Path:
        return self.data_dir / "downloads"

    @property
    def logs_dir(self) -> Path:
        return self.data_dir / "logs"

    @property
    def review_dir(self) -> Path:
        return self.data_dir / "review"

    @property
    def state_dir(self) -> Path:
        return self.data_dir / "state"

    @property
    def checkpoint_path(self) -> Path:
        return self.state_dir / "checkpoint.json"

    @property
    def storage_state_path(self) -> Path:
        return self.state_dir / "playwright_storage_state.json"

    @property
    def download_status_path(self) -> Path:
        return self.outputs_dir / "download_status.csv"

    @property
    def ambiguous_matches_path(self) -> Path:
        return self.outputs_dir / "ambiguous_matches.csv"

    @property
    def failed_downloads_path(self) -> Path:
        return self.outputs_dir / "failed_downloads.csv"

    @property
    def credit_rating_history_path(self) -> Path:
        return self.outputs_dir / "credit_rating_history.csv"

    @property
    def credit_rating_status_path(self) -> Path:
        return self.outputs_dir / "credit_rating_status.csv"

    @property
    def credit_rating_failures_path(self) -> Path:
        return self.outputs_dir / "credit_rating_failures.csv"

    @property
    def credit_rating_checkpoint_path(self) -> Path:
        return self.state_dir / "credit_ratings_checkpoint.json"
