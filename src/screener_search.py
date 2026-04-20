from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import parse_qs, unquote, urlsplit

from playwright.sync_api import Browser, BrowserContext, Page, Playwright, sync_playwright
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_fixed

from .config import AppConfig, SEARCH_API_PATH, SEARCH_INPUT_SELECTOR
from .models import SearchCandidate
from .screener_matcher import candidate_from_payload


logger = logging.getLogger(__name__)
VISIBLE_SEARCH_INPUT_SELECTOR = f"{SEARCH_INPUT_SELECTOR}:visible"


class SearchAutomationError(RuntimeError):
    """Raised when browser search automation cannot complete reliably."""


@dataclass(slots=True)
class CapturedSearchResponse:
    query: str | None
    url: str
    payload: list[dict[str, Any]]


class ScreenerSearchBrowser:
    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None

    def __enter__(self) -> "ScreenerSearchBrowser":
        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch(headless=self.config.headless)
        self._context = self._browser.new_context()
        self._page = self._context.new_page()
        self._page.goto(self.config.base_url, wait_until="domcontentloaded", timeout=60000)
        self._page.wait_for_selector(VISIBLE_SEARCH_INPUT_SELECTOR, timeout=self.config.search_timeout_ms)
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
            raise SearchAutomationError("Browser page is not initialized.")
        return self._page

    def search(self, query: str) -> list[SearchCandidate]:
        captured = self._search_via_typeahead(query)
        candidates = [
            candidate_from_payload(payload, rank=index + 1, base_url=self.config.base_url)
            for index, payload in enumerate(captured.payload[: self.config.max_candidates])
        ]
        logger.info("Search for %r returned %s candidate(s)", query, len(candidates))
        return candidates

    @retry(
        retry=retry_if_exception_type(SearchAutomationError),
        wait=wait_fixed(2),
        stop=stop_after_attempt(3),
        reraise=True,
    )
    def _search_via_typeahead(self, query: str) -> CapturedSearchResponse:
        page = self.page
        self._ensure_search_surface()
        search_input = page.locator(VISIBLE_SEARCH_INPUT_SELECTOR).first
        normalized_query = query.strip().casefold()

        def matches_query(response) -> bool:  # type: ignore[no-untyped-def]
            if SEARCH_API_PATH not in response.url:
                return False
            parsed_query = parse_qs(urlsplit(response.url).query).get("q", [None])[0]
            if not parsed_query:
                return False
            return unquote(parsed_query).strip().casefold() == normalized_query

        with page.expect_response(matches_query, timeout=self.config.search_timeout_ms) as response_info:
            search_input.click()
            search_input.fill("")
            search_input.type(query, delay=self.config.search_delay_ms)

        response = response_info.value
        try:
            payload = response.json()
        except Exception as exc:  # noqa: BLE001
            raise SearchAutomationError(f"Unable to decode search response for query {query!r}") from exc
        if not isinstance(payload, list):
            raise SearchAutomationError(f"Unexpected search response shape for query {query!r}")

        parsed_query = parse_qs(urlsplit(response.url).query).get("q", [None])[0]
        final_response = CapturedSearchResponse(
            query=unquote(parsed_query) if parsed_query else None,
            url=response.url,
            payload=payload,
        )
        page.wait_for_timeout(self.config.search_settle_ms)
        time.sleep(self.config.inter_company_sleep_seconds)
        return final_response

    def _ensure_search_surface(self) -> None:
        page = self.page
        page.goto(self.config.base_url, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_selector(VISIBLE_SEARCH_INPUT_SELECTOR, timeout=self.config.search_timeout_ms)
