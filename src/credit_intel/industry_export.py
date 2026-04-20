from __future__ import annotations

import logging
from dataclasses import asdict
from pathlib import Path

from playwright.sync_api import Browser, BrowserContext, Download, Page, Playwright, TimeoutError, sync_playwright

from ..config import AppConfig
from ..io_utils import load_input_companies, write_records_csv
from ..models import DownloadStatusRecord


LOGGER = logging.getLogger(__name__)

INDUSTRY_EXPORT_SELECTOR = "text=Export"
DEFAULT_AGRI_INDUSTRY_URL = "https://www.screener.in/market/IN04/IN0401/IN040101/"


class IndustryExportError(RuntimeError):
    """Raised when the Screener industry export flow fails."""


class ScreenerIndustryExportBrowser:
    def __init__(
        self,
        config: AppConfig,
        *,
        storage_state_path: Path | None = None,
        interactive_login: bool = False,
    ) -> None:
        self.config = config
        self.storage_state_path = storage_state_path
        self.interactive_login = interactive_login
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None

    def __enter__(self) -> "ScreenerIndustryExportBrowser":
        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch(headless=self.config.headless)
        context_kwargs: dict[str, object] = {"accept_downloads": True}
        if self.storage_state_path and self.storage_state_path.exists():
            context_kwargs["storage_state"] = str(self.storage_state_path)
        self._context = self._browser.new_context(**context_kwargs)
        self._page = self._context.new_page()

        if self.interactive_login:
            self._capture_login_state()
        return self

    def __exit__(self, exc_type, exc, exc_tb) -> None:
        if self._context is not None:
            self._context.close()
        if self._browser is not None:
            self._browser.close()
        if self._playwright is not None:
            self._playwright.stop()

    @property
    def page(self) -> Page:
        if self._page is None:
            raise IndustryExportError("Browser page is not initialized.")
        return self._page

    def export_industry_csv(
        self,
        *,
        industry_url: str,
        output_path: Path,
        force: bool = False,
    ) -> Path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        if output_path.exists() and not force:
            return output_path

        page = self.page
        LOGGER.info("Opening Screener industry page: %s", industry_url)
        page.goto(industry_url, wait_until="domcontentloaded", timeout=self.config.company_page_timeout_ms)
        page.wait_for_timeout(2000)

        locator = page.locator(INDUSTRY_EXPORT_SELECTOR).first
        if locator.count() == 0:
            raise IndustryExportError(f"Export control was not found on {industry_url}")

        try:
            with page.expect_download(timeout=self.config.export_timeout_ms) as download_info:
                locator.click(timeout=10000)
            download = download_info.value
        except TimeoutError as exc:
            raise IndustryExportError(f"Timed out waiting for industry export download from {industry_url}") from exc

        self._save_download(download, output_path)
        LOGGER.info("Saved industry export to %s", output_path)
        return output_path

    def _save_download(self, download: Download, output_path: Path) -> None:
        download.save_as(str(output_path))
        if not output_path.exists():
            raise IndustryExportError(f"Downloaded industry export was not saved to {output_path}")

    def _capture_login_state(self) -> None:
        if self.config.headless:
            raise IndustryExportError("Interactive login requires headed mode. Re-run with --no-headless.")
        page = self.page
        page.goto(self.config.base_url, wait_until="domcontentloaded", timeout=self.config.company_page_timeout_ms)
        print("Complete Screener login in the opened browser, then press Enter here to continue.")
        input()
        if self.storage_state_path is not None:
            self.storage_state_path.parent.mkdir(parents=True, exist_ok=True)
            assert self._context is not None
            self._context.storage_state(path=str(self.storage_state_path))
            LOGGER.info("Saved Playwright storage state to %s", self.storage_state_path)


def build_screener_company_url(nse_code: str | None, bse_code: str | None) -> str | None:
    code = (nse_code or bse_code or "").strip()
    if not code:
        return None
    return f"https://www.screener.in/company/{code}/"


def bootstrap_download_status_from_input_csv(
    *,
    input_path: Path,
    output_path: Path,
) -> int:
    companies = load_input_companies(input_path)
    records: list[dict[str, object]] = []
    for company in companies:
        screener_url = build_screener_company_url(company.nse_code, company.bse_code)
        record = DownloadStatusRecord(
            company_id=company.company_id,
            company_name=company.company_name,
            nse_code=company.nse_code,
            bse_code=company.bse_code,
            screener_url=screener_url,
            local_file_path=None,
            status="matched_ready_for_download" if screener_url else "missing_company_code",
            downloaded_at=None,
            validation_status="not_started",
            notes="Bootstrapped directly from Screener industry export codes." if screener_url else "No NSE/BSE code was available in the industry export.",
        )
        records.append(asdict(record))

    write_records_csv(
        output_path,
        records,
        [
            "company_id",
            "company_name",
            "nse_code",
            "bse_code",
            "screener_url",
            "local_file_path",
            "status",
            "downloaded_at",
            "validation_status",
            "notes",
        ],
    )
    return len(records)
