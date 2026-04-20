from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from pathlib import Path

from playwright.sync_api import Browser, BrowserContext, Download, Page, Playwright, TimeoutError, sync_playwright
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_fixed

from .config import AppConfig
from .io_utils import sanitize_filename
from .models import DownloadResult, DownloadStatusRecord


logger = logging.getLogger(__name__)


class DownloadWorkflowError(RuntimeError):
    """Raised when the export workflow fails."""


class AuthenticationRequiredError(DownloadWorkflowError):
    """Raised when Screener redirects export requests to login or registration."""


class ExportButtonNotFoundError(DownloadWorkflowError):
    """Raised when the export control is unavailable on the company page."""


def _should_retry_download_exception(error: BaseException) -> bool:
    return isinstance(error, DownloadWorkflowError) and not isinstance(
        error,
        (AuthenticationRequiredError, ExportButtonNotFoundError),
    )


def build_download_filename(company_name: str, nse_code: str | None, bse_code: str | None) -> str:
    stem = sanitize_filename(company_name)
    code = nse_code or bse_code or "NO_CODE"
    return f"{stem}__{code}.xlsx"


def is_pending_download_status(row: dict[str, object], *, force: bool) -> bool:
    status = str(row.get("status") or "").strip()
    screener_url = str(row.get("screener_url") or "").strip()
    local_file_path = str(row.get("local_file_path") or "").strip()

    if not screener_url:
        return False
    if force:
        return status in {"matched_ready_for_download", "downloaded", "download_failed", "auth_required"}
    return status in {"matched_ready_for_download", "download_failed", "auth_required"} and not local_file_path


def file_already_downloaded(row: dict[str, object], downloads_dir: Path) -> bool:
    local_path = str(row.get("local_file_path") or "").strip()
    if local_path:
        candidate = Path(local_path)
        if candidate.exists():
            return True

    expected_path = downloads_dir / build_download_filename(
        str(row.get("company_name") or ""),
        _string_or_none(row.get("nse_code")),
        _string_or_none(row.get("bse_code")),
    )
    return expected_path.exists()


class ScreenerDownloadBrowser:
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

    def __enter__(self) -> "ScreenerDownloadBrowser":
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
            raise DownloadWorkflowError("Browser page is not initialized.")
        return self._page

    @retry(
        retry=retry_if_exception(_should_retry_download_exception),
        wait=wait_fixed(3),
        stop=stop_after_attempt(2),
        reraise=True,
    )
    def download_company_workbook(
        self,
        *,
        company_name: str,
        nse_code: str | None,
        bse_code: str | None,
        screener_url: str,
        downloads_dir: Path,
        force: bool,
    ) -> DownloadResult:
        page = self.page
        downloads_dir.mkdir(parents=True, exist_ok=True)
        target_path = downloads_dir / build_download_filename(company_name, nse_code, bse_code)

        logger.info("Opening company page for %s at %s", company_name, screener_url)
        page.goto(screener_url, wait_until="domcontentloaded", timeout=self.config.company_page_timeout_ms)
        page.wait_for_timeout(1500)

        button = page.locator(self.config.export_button_selector).first
        if button.count() == 0:
            raise ExportButtonNotFoundError(f"Export button not found on {screener_url}")
        logger.info("Found Export to Excel button for %s", company_name)

        if target_path.exists() and not force:
            logger.info("Skipping download for %s because %s already exists", company_name, target_path)
            return DownloadResult(
                company_id="",
                company_name=company_name,
                screener_url=screener_url,
                status="downloaded",
                local_file_path=str(target_path),
                downloaded_at=None,
                validation_status="not_started",
                notes="Existing file retained; use --force to re-download.",
            )

        try:
            with page.expect_download(timeout=self.config.export_timeout_ms) as download_info:
                logger.info("Starting export click for %s", company_name)
                button.click(timeout=10000)
            logger.info("Download started for %s", company_name)
            download = download_info.value
        except TimeoutError as exc:
            auth_url = page.url
            if "/login/" in auth_url or "/register/" in auth_url:
                raise AuthenticationRequiredError(
                    f"Export redirected to authentication at {auth_url}. Use a logged-in browser state."
                ) from exc
            raise DownloadWorkflowError(
                f"Timed out waiting for Excel download from {screener_url}"
            ) from exc

        self._save_download(download, target_path, company_name)
        time.sleep(self.config.inter_company_sleep_seconds)
        return DownloadResult(
            company_id="",
            company_name=company_name,
            screener_url=screener_url,
            status="downloaded",
            local_file_path=str(target_path),
            downloaded_at=_utc_now(),
            validation_status="not_started",
            notes=f"Workbook downloaded successfully as {target_path.name}",
        )

    def _save_download(self, download: Download, target_path: Path, company_name: str) -> None:
        logger.info("Saving download for %s to %s", company_name, target_path)
        download.save_as(str(target_path))
        if not target_path.exists() or target_path.suffix.lower() != ".xlsx":
            raise DownloadWorkflowError(f"Downloaded file was not saved correctly at {target_path}")
        logger.info("Download completed for %s at %s", company_name, target_path)

    def _capture_login_state(self) -> None:
        if self.config.headless:
            raise DownloadWorkflowError("Interactive login requires headed mode. Re-run with --no-headless.")
        page = self.page
        page.goto(self.config.base_url, wait_until="domcontentloaded", timeout=self.config.company_page_timeout_ms)
        print("Complete Screener login in the opened browser, then press Enter here to continue.")
        input()
        if self.storage_state_path is not None:
            self.storage_state_path.parent.mkdir(parents=True, exist_ok=True)
            assert self._context is not None
            self._context.storage_state(path=str(self.storage_state_path))
            logger.info("Saved Playwright storage state to %s", self.storage_state_path)


def build_download_status_update(
    row: dict[str, object],
    result: DownloadResult,
) -> DownloadStatusRecord:
    return DownloadStatusRecord(
        company_id=str(row.get("company_id") or ""),
        company_name=str(row.get("company_name") or ""),
        nse_code=_string_or_none(row.get("nse_code")),
        bse_code=_string_or_none(row.get("bse_code")),
        screener_url=result.screener_url,
        local_file_path=result.local_file_path,
        status=result.status,
        downloaded_at=result.downloaded_at,
        validation_status=result.validation_status,
        notes=result.notes,
    )


def _string_or_none(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
