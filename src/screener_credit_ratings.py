from __future__ import annotations

import hashlib
import logging
import time
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from urllib.parse import urlsplit
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup
from playwright.sync_api import Browser, BrowserContext, Page, Playwright, sync_playwright
from pypdf import PdfReader
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_fixed

from .config import AppConfig
from .credit_rating_parser import (
    ParsedRatingResult,
    extract_pdf_url_from_html,
    extract_rating_from_text,
    normalize_text,
    parse_rating_update_metadata,
)
from .models import CreditRatingLink, CreditRatingRecord


logger = logging.getLogger(__name__)


class CreditRatingsWorkflowError(RuntimeError):
    """Raised when the credit rating workflow cannot complete reliably."""


class DocumentFetchError(CreditRatingsWorkflowError):
    """Raised when a linked rating document cannot be parsed."""


class ScreenerCreditRatingsBrowser:
    def __init__(
        self,
        config: AppConfig,
        *,
        storage_state_path: Path | None = None,
    ) -> None:
        self.config = config
        self.storage_state_path = storage_state_path
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None
        self._client: httpx.Client | None = None

    def __enter__(self) -> "ScreenerCreditRatingsBrowser":
        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch(headless=self.config.headless)
        context_kwargs: dict[str, object] = {}
        if self.storage_state_path and self.storage_state_path.exists():
            context_kwargs["storage_state"] = str(self.storage_state_path)
        self._context = self._browser.new_context(**context_kwargs)
        self._page = self._context.new_page()
        self._client = httpx.Client(
            follow_redirects=True,
            timeout=60,
            headers={"User-Agent": "Mozilla/5.0"},
        )
        return self

    def __exit__(self, exc_type, exc, exc_tb) -> None:
        if self._client is not None:
            self._client.close()
        if self._context is not None:
            self._context.close()
        if self._browser is not None:
            self._browser.close()
        if self._playwright is not None:
            self._playwright.stop()

    @property
    def page(self) -> Page:
        if self._page is None:
            raise CreditRatingsWorkflowError("Browser page is not initialized.")
        return self._page

    @property
    def context(self) -> BrowserContext:
        if self._context is None:
            raise CreditRatingsWorkflowError("Browser context is not initialized.")
        return self._context

    @property
    def client(self) -> httpx.Client:
        if self._client is None:
            raise CreditRatingsWorkflowError("HTTP client is not initialized.")
        return self._client

    @retry(
        retry=retry_if_exception_type(CreditRatingsWorkflowError),
        wait=wait_fixed(8),
        stop=stop_after_attempt(3),
        reraise=True,
    )
    def collect_company_rating_links(
        self,
        *,
        company_id: str,
        company_name: str,
        nse_code: str | None,
        bse_code: str | None,
        screener_url: str,
    ) -> list[CreditRatingLink]:
        page = self.page
        logger.info("Opening Screener company page for credit ratings: %s", company_name)
        page.goto(screener_url, wait_until="domcontentloaded", timeout=self.config.company_page_timeout_ms)
        page.wait_for_timeout(1500)
        page_title = page.title().strip().lower()
        h1_text = page.locator("h1").first.inner_text().strip().lower() if page.locator("h1").count() else ""
        if "too many requests" in page_title or "too many requests" in h1_text:
            raise CreditRatingsWorkflowError(f"Screener rate limited credit-rating lookup for {company_name} at {screener_url}")

        link_locator = page.locator(self.config.credit_rating_link_selector)
        count = link_locator.count()
        logger.info("Found %s credit rating link(s) on %s", count, company_name)
        if count == 0:
            time.sleep(self.config.inter_company_sleep_seconds)
            return []

        links: list[CreditRatingLink] = []
        seen_urls: set[str] = set()
        current_year = datetime.now().year
        for index in range(count):
            item = link_locator.nth(index)
            href = item.get_attribute("href")
            label = normalize_text(item.inner_text())
            if not href or href in seen_urls:
                continue
            seen_urls.add(href)

            metadata = parse_rating_update_metadata(label, current_year=current_year)
            links.append(
                CreditRatingLink(
                    event_id=_build_event_id(company_id, href),
                    company_id=company_id,
                    company_name=company_name,
                    nse_code=nse_code,
                    bse_code=bse_code,
                    screener_url=screener_url,
                    rating_update_url=href,
                    rating_date=metadata.rating_date,
                    rating_date_display=metadata.rating_date_display,
                    rating_agency=metadata.rating_agency,
                    notes=metadata.notes,
                )
            )

        time.sleep(min(self.config.inter_company_sleep_seconds, 1.0))
        return links

    def extract_rating_record(self, link: CreditRatingLink) -> CreditRatingRecord:
        logger.info("Extracting credit rating for %s from %s", link.company_name, link.rating_update_url)
        result = self._extract_document_rating(link.rating_update_url, agency=link.rating_agency)
        return CreditRatingRecord(
            event_id=link.event_id,
            company_id=link.company_id,
            company_name=link.company_name,
            nse_code=link.nse_code,
            bse_code=link.bse_code,
            screener_url=link.screener_url,
            rating_update_url=link.rating_update_url,
            rating_date=link.rating_date,
            rating_date_display=link.rating_date_display,
            rating_agency=link.rating_agency,
            rating=result.rating,
            rating_scale=result.rating_scale,
            extraction_method=result.extraction_method,
            extracted_at=_utc_now(),
            notes=_merge_notes(link.notes, result.notes),
        )

    def _extract_document_rating(self, url: str, *, agency: str | None) -> ParsedRatingResult:
        if _looks_like_pdf(url):
            pdf_text = self._fetch_pdf_text(url)
            return extract_rating_from_text(pdf_text, agency=agency)

        host = urlsplit(url).netloc.lower()
        if "crisil.com" in host:
            return self._extract_from_httpx_html(url, agency=agency)
        if "careratings.com" in host or "acuite.in" in host:
            pdf_text = self._fetch_pdf_text(url)
            return extract_rating_from_text(pdf_text, agency=agency)
        if "indiaratings.co.in" in host:
            return self._extract_from_playwright_html(url, agency=agency)
        if "icra.in" in host:
            return self._extract_from_icra(url, agency=agency)

        result = self._extract_from_httpx_html(url, agency=agency)
        if result.rating is not None:
            return result
        return self._extract_from_playwright_html(url, agency=agency)

    def _extract_from_httpx_html(
        self,
        url: str,
        *,
        agency: str | None,
        allow_follow: bool = True,
    ) -> ParsedRatingResult:
        response = self.client.get(url)
        response.raise_for_status()
        html_text = response.text
        pdf_url = extract_pdf_url_from_html(html_text, base_url=str(response.url))
        if pdf_url:
            pdf_text = self._fetch_pdf_text(pdf_url)
            result = extract_rating_from_text(pdf_text, agency=agency)
            if result.rating is not None:
                result.extraction_method = "pdf_from_html"
                return result

        soup = BeautifulSoup(html_text, "lxml")
        text = soup.get_text(" ", strip=True)
        result = extract_rating_from_text(text, agency=agency)
        if result.rating is not None:
            if result.extraction_method:
                result.extraction_method = f"httpx_html_{result.extraction_method}"
            return result
        if allow_follow:
            related_url = _find_related_rationale_url(soup, base_url=str(response.url))
            if related_url and related_url != str(response.url):
                related_result = self._extract_from_httpx_html(related_url, agency=agency, allow_follow=False)
                if related_result.rating is not None:
                    if related_result.extraction_method:
                        related_result.extraction_method = f"followed_rationale_{related_result.extraction_method}"
                    related_result.notes = _merge_notes(
                        f"Followed related rationale link: {related_url}",
                        related_result.notes,
                    )
                    return related_result
        return result

    def _extract_from_playwright_html(self, url: str, *, agency: str | None) -> ParsedRatingResult:
        page = self.context.new_page()
        try:
            page.goto(url, wait_until="networkidle", timeout=self.config.credit_rating_timeout_ms)
            page.wait_for_timeout(2000)
            html_text = page.content()
            pdf_url = extract_pdf_url_from_html(html_text, base_url=page.url)
            if pdf_url:
                pdf_text = self._fetch_pdf_text(pdf_url)
                result = extract_rating_from_text(pdf_text, agency=agency)
                if result.rating is not None:
                    result.extraction_method = "playwright_pdf"
                    return result

            body_text = page.locator("body").first.inner_text(timeout=self.config.credit_rating_timeout_ms)
            result = extract_rating_from_text(body_text, agency=agency)
            if result.rating is not None and result.extraction_method:
                result.extraction_method = f"playwright_html_{result.extraction_method}"
            return result
        finally:
            page.close()

    def _extract_from_icra(self, url: str, *, agency: str | None) -> ParsedRatingResult:
        http_result = self._extract_from_httpx_html(url, agency=agency)
        if http_result.rating is not None:
            if http_result.extraction_method:
                http_result.extraction_method = f"icra_http_{http_result.extraction_method}"
            return http_result

        page = self.context.new_page()
        try:
            page.goto(url, wait_until="networkidle", timeout=self.config.credit_rating_timeout_ms)
            page.wait_for_timeout(2500)
            html_text = page.content()
            html_result = extract_rating_from_text(html_text, agency=agency)
            if html_result.rating is not None:
                if html_result.extraction_method:
                    html_result.extraction_method = f"icra_source_{html_result.extraction_method}"
                return html_result
            pdf_url = extract_pdf_url_from_html(html_text, base_url=page.url)
            if pdf_url:
                pdf_text = self._fetch_pdf_text(pdf_url)
                result = extract_rating_from_text(pdf_text, agency=agency)
                if result.rating is not None:
                    result.extraction_method = "icra_pdf"
                    return result

            body_text = page.locator("body").first.inner_text(timeout=self.config.credit_rating_timeout_ms)
            result = extract_rating_from_text(body_text, agency=agency)
            if result.rating is not None and result.extraction_method:
                result.extraction_method = f"icra_html_{result.extraction_method}"
            return result
        finally:
            page.close()

    def _fetch_pdf_text(self, url: str) -> str:
        response = self.client.get(url)
        response.raise_for_status()
        try:
            reader = PdfReader(BytesIO(response.content))
        except Exception as exc:  # noqa: BLE001
            raise DocumentFetchError(f"Unable to open PDF document at {url}") from exc

        extracted_pages = []
        for page in reader.pages:
            extracted_pages.append(page.extract_text() or "")
        text = normalize_text(" ".join(extracted_pages))
        if not text:
            raise DocumentFetchError(f"No extractable text found in PDF document at {url}")
        return text


def _build_event_id(company_id: str, rating_update_url: str) -> str:
    digest = hashlib.sha1(f"{company_id}|{rating_update_url}".encode("utf-8")).hexdigest()[:12]
    return f"{company_id}__{digest}"


def _looks_like_pdf(url: str) -> bool:
    return ".pdf" in url.lower()


def _merge_notes(*values: str | None) -> str | None:
    parts = [value.strip() for value in values if value and value.strip()]
    return " ".join(parts) or None


def _find_related_rationale_url(soup: BeautifulSoup, *, base_url: str) -> str | None:
    for anchor in soup.find_all("a", href=True):
        href = anchor["href"]
        text = normalize_text(anchor.get_text(" ", strip=True))
        compact_text = text.replace(" ", "").lower()
        absolute = urljoin(base_url, href)
        if "ratingdocs" in href.lower() and "click" in compact_text:
            return absolute
    return None


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
