from __future__ import annotations

import hashlib
import logging
import time
from typing import Any
from urllib.parse import urlencode

import httpx
from bs4 import BeautifulSoup

from .cache import load_json, save_json, search_cache_path
from .config import CreditIntelConfig


LOGGER = logging.getLogger(__name__)


class SearchEngineClient:
    def __init__(self, config: CreditIntelConfig) -> None:
        self.config = config
        self._duckduckgo_enabled = True

    def search(self, query: str, *, max_results: int | None = None) -> list[dict[str, Any]]:
        cache_key = hashlib.sha1(query.encode("utf-8")).hexdigest()
        cache_path = search_cache_path(self.config, cache_key)
        cached = load_json(cache_path)
        if cached:
            return list(cached.get("results", []))

        if not self.config.enable_web_discovery:
            return []

        time.sleep(self.config.request_delay_seconds)
        LOGGER.info("Search query: %s", query)
        with httpx.Client(
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=30.0,
            follow_redirects=True,
        ) as client:
            results = self._search_duckduckgo(client, query, max_results=max_results) if self._duckduckgo_enabled else []
            if not results:
                results = self._search_bing(client, query, max_results=max_results)

        save_json(cache_path, {"query": query, "results": results})
        return results

    def _search_duckduckgo(self, client: httpx.Client, query: str, *, max_results: int | None = None) -> list[dict[str, Any]]:
        params = urlencode({"q": query})
        url = f"https://html.duckduckgo.com/html/?{params}"
        try:
            response = client.get(url)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            LOGGER.warning("DuckDuckGo search failed for %s: %s", query, exc)
            if exc.response.status_code == 403:
                self._duckduckgo_enabled = False
            return []

        soup = BeautifulSoup(response.text, "lxml")
        results: list[dict[str, Any]] = []
        for result in soup.select(".result"):
            anchor = result.select_one(".result__title a") or result.select_one("a.result__a")
            if not anchor:
                continue
            snippet = result.select_one(".result__snippet")
            results.append(
                {
                    "title": anchor.get_text(" ", strip=True),
                    "url": anchor.get("href"),
                    "snippet": snippet.get_text(" ", strip=True) if snippet else None,
                    "search_engine": "duckduckgo",
                }
            )
            if len(results) >= (max_results or self.config.max_search_results):
                break
        return results

    def _search_bing(self, client: httpx.Client, query: str, *, max_results: int | None = None) -> list[dict[str, Any]]:
        params = urlencode({"q": query})
        url = f"https://www.bing.com/search?{params}"
        try:
            response = client.get(url)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            LOGGER.warning("Bing search failed for %s: %s", query, exc)
            return []

        soup = BeautifulSoup(response.text, "lxml")
        results: list[dict[str, Any]] = []
        for result in soup.select("li.b_algo"):
            anchor = result.select_one("h2 a")
            if not anchor:
                continue
            snippet = result.select_one(".b_caption p")
            results.append(
                {
                    "title": anchor.get_text(" ", strip=True),
                    "url": anchor.get("href"),
                    "snippet": snippet.get_text(" ", strip=True) if snippet else None,
                    "search_engine": "bing",
                }
            )
            if len(results) >= (max_results or self.config.max_search_results):
                break
        return results
