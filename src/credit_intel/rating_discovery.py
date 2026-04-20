from __future__ import annotations

import json
import logging
import re
import time
from pathlib import Path
from typing import Any, Literal
from urllib.parse import quote, urljoin, urlsplit

import httpx
import pandas as pd
from bs4 import BeautifulSoup

from ..credit_rating_parser import extract_rating_from_text, normalize_text
from ..io_utils import company_name_tokens, normalize_company_name
from ..parsers import get_parser
from ..schemas import normalize_outlook
from ..schemas.crosswalks import normalize_rating_label
from ..utils.pdf import detect_agency_name, extract_pdf_text
from ..utils.text import sanitize_filename
from .config import CreditIntelConfig
from .rating_repository import ExistingRatingRepository, parse_rating_text
from .schemas import RatingHistoryEntry, RatingInsight
from .search_engine import SearchEngineClient


LOGGER = logging.getLogger(__name__)

DiscoveryMode = Literal["legacy", "cra_first", "cra_only"]

CRA_DOMAINS = {
    "crisil.com": "crisil",
    "crisilratings.com": "crisil",
    "careratings.com": "care",
    "careedge.in": "care",
    "icra.in": "icra",
    "indiaratings.co.in": "india_ratings",
    "acuite.in": "acuite",
    "connect.acuite.in": "acuite",
    "brickworkratings.com": "brickwork",
    "bcrisp.in": "brickwork",
    "infomerics.com": "infomerics",
}

AGENCY_DOMAINS = {
    "crisil": ("crisilratings.com",),
    "care": ("careratings.com", "careedge.in"),
    "icra": ("icra.in",),
    "india_ratings": ("indiaratings.co.in",),
    "acuite": ("connect.acuite.in", "acuite.in"),
    "brickwork": ("brickworkratings.com", "bcrisp.in"),
    "infomerics": ("infomerics.com",),
}

CRA_DISCOVERY_ORDER = ("care", "icra", "acuite", "crisil", "india_ratings", "brickwork", "infomerics")

RELEVANT_URL_HINTS = (
    ".pdf",
    "getrationalreportfilepdf",
    "viewratingrationale",
    "ratingdetails",
    "rating-details",
    "fcompany-details",
    "company-details",
    "uploads/newsfiles/",
    "pressrelease/",
    "ratingdocs/",
)

RATING_TOKEN_PATTERN = r"(AAA|AA\+|AA-|AA|A\+|A-|A|BBB\+|BBB-|BBB|BB\+|BB-|BB|B\+|B-|B|C\+|C|D|A1\+|A1|A2\+|A2|A3|A4)"


class RatingDiscoveryService:
    def __init__(self, config: CreditIntelConfig, repository: ExistingRatingRepository) -> None:
        self.config = config
        self.repository = repository
        self.search_client = SearchEngineClient(config)
        self._brickwork_search_cache: dict[str, list[tuple[str, str]]] = {}

    def discover(
        self,
        company_name: str,
        *,
        dataset_rating_text: str | None = None,
        mode: DiscoveryMode = "legacy",
        use_repository: bool | None = None,
        allow_dataset_fallback: bool | None = None,
    ) -> RatingInsight:
        use_repository = (mode == "legacy") if use_repository is None else use_repository
        allow_dataset_fallback = (mode != "cra_only") if allow_dataset_fallback is None else allow_dataset_fallback

        if use_repository:
            cached = self.repository.lookup(company_name)
            if cached and cached.rating_available_flag:
                return cached

        history = (
            self._discover_from_cra_domains(company_name, include_domain_search_fallback=(mode == "cra_first"))
            if mode != "legacy"
            else self._discover_from_web(company_name)
        )
        if history:
            latest = history[0]
            return RatingInsight(
                rating_available_flag=bool(latest.rating),
                rating_status="available" if latest.rating else "not_available",
                agency_name=latest.agency_name,
                rating=latest.rating,
                outlook=latest.outlook,
                rating_date=latest.rating_date,
                rating_action=latest.rating_action,
                history=history,
                notes=[
                    "Discovered via CRA-domain validation workflow."
                    if mode != "legacy"
                    else "Discovered via search-engine-guided CRA document parsing."
                ],
            )

        if allow_dataset_fallback:
            fallback = parse_rating_text(dataset_rating_text)
            if fallback.rating_available_flag:
                fallback.notes.append("CRA validation returned no parseable CRA document; dataset hint used.")
                return fallback

        if mode == "cra_only":
            return RatingInsight(notes=["CRA-only discovery returned no parseable CRA document."])
        return RatingInsight()

    def _discover_from_cra_domains(
        self,
        company_name: str,
        *,
        include_domain_search_fallback: bool,
    ) -> list[RatingHistoryEntry]:
        parsed_entries: list[RatingHistoryEntry] = []
        seen_urls: set[str] = set()

        for agency_name in CRA_DISCOVERY_ORDER:
            candidates = self._native_search_candidates(company_name, agency_name)
            for candidate in candidates:
                direct_entry = candidate.get("entry")
                direct_key = str(candidate.get("direct_key") or "")
                if direct_entry is not None:
                    if direct_key and direct_key in seen_urls:
                        continue
                    try:
                        if isinstance(direct_entry, RatingHistoryEntry):
                            parsed_entries.append(direct_entry)
                        elif isinstance(direct_entry, dict):
                            parsed_entries.append(RatingHistoryEntry.model_validate(direct_entry))
                    except Exception as exc:  # noqa: BLE001
                        LOGGER.warning("CRA native direct-entry discovery failed for %s via %s: %s", company_name, direct_key or agency_name, exc)
                        continue
                    if direct_key:
                        seen_urls.add(direct_key)
                    continue

                url = candidate["url"]
                if url in seen_urls:
                    continue
                try:
                    entries = self._parse_candidate_entries(
                        company_name,
                        url,
                        candidate.get("agency") or agency_name,
                        source_label=candidate.get("source_label") or "cra_native_site_search",
                    )
                except Exception as exc:  # noqa: BLE001
                    LOGGER.warning("CRA native discovery failed for %s via %s: %s", company_name, url, exc)
                    continue
                parsed_entries.extend(entries)
                seen_urls.add(url)

        if include_domain_search_fallback:
            for result in self._discover_from_cra_domain_search(company_name):
                url = str(result.get("url") or "")
                if not url or url in seen_urls:
                    continue
                agency_name = self._agency_from_url(url)
                if not agency_name:
                    continue
                try:
                    entries = self._parse_candidate_entries(
                        company_name,
                        url,
                        agency_name,
                        source_label="cra_domain_search",
                    )
                except Exception as exc:  # noqa: BLE001
                    LOGGER.warning("CRA domain search discovery failed for %s via %s: %s", company_name, url, exc)
                    continue
                parsed_entries.extend(entries)
                seen_urls.add(url)

        return self._dedupe_entries(parsed_entries)

    def _discover_from_web(self, company_name: str) -> list[RatingHistoryEntry]:
        query = f'{company_name} credit rating Crisil Care ICRA India Ratings Acuite Brickwork Infomerics'
        results = self.search_client.search(query, max_results=self.config.rating_search_limit)
        parsed_entries: list[RatingHistoryEntry] = []
        for result in results:
            url = str(result.get("url") or "")
            if not url:
                continue
            agency_name = self._agency_from_url(url)
            if not agency_name and ".pdf" not in url.lower():
                continue
            try:
                parsed_entries.extend(
                    self._parse_candidate_entries(
                        company_name,
                        url,
                        agency_name,
                        source_label="cra_web_discovery",
                    )
                )
            except Exception as exc:  # noqa: BLE001
                LOGGER.warning("Rating discovery failed for %s via %s: %s", company_name, url, exc)
                continue
            time.sleep(self.config.request_delay_seconds)
        return self._dedupe_entries(parsed_entries)

    def _discover_from_cra_domain_search(self, company_name: str) -> list[dict[str, Any]]:
        query = f'"{company_name}" credit rating Crisil Care ICRA "India Ratings" Acuite Brickwork Infomerics'
        results = self.search_client.search(query, max_results=max(self.config.rating_search_limit * 2, 12))
        filtered: list[dict[str, Any]] = []
        for result in results:
            url = str(result.get("url") or "")
            title = str(result.get("title") or "")
            snippet = str(result.get("snippet") or "")
            if not url or not self._agency_from_url(url):
                continue
            if not self._search_result_matches_company(company_name, title, snippet, url):
                continue
            filtered.append(result)
        return filtered

    def _native_search_candidates(self, company_name: str, agency_name: str) -> list[dict[str, str]]:
        variants = self._search_variants(company_name)
        candidates: list[dict[str, str]] = []
        seen: set[str] = set()
        with httpx.Client(headers={"User-Agent": "Mozilla/5.0"}, timeout=30.0, follow_redirects=True) as client:
            for variant in variants:
                if agency_name == "care":
                    try:
                        payload = self._care_search_payload(client, variant)
                    except Exception as exc:  # noqa: BLE001
                        LOGGER.debug("CARE native search failed for %s via %s: %s", company_name, variant, exc)
                        payload = {}
                    for item in payload.get("data", []):
                        candidate_name = str(item.get("CompanyName") or "")
                        if self._candidate_name_score(company_name, candidate_name) < 0.72:
                            continue
                        company_id = str(item.get("CompanyID") or "").strip()
                        if company_id:
                            url = f"https://www.careratings.com/search?Id={company_id}"
                            if url not in seen:
                                candidates.append({"url": url, "agency": "care", "source_label": "care_native_site_search"})
                                seen.add(url)
                    for item in payload.get("report", []):
                        title = str(item.get("title") or "")
                        if self._candidate_name_score(company_name, title) < 0.4 and not self._title_contains_target_tokens(company_name, title):
                            continue
                        pdf_name = str(item.get("pdf") or "").strip()
                        if pdf_name:
                            url = urljoin("https://www.careratings.com/", f"uploads/newsfiles/{pdf_name}")
                            if url not in seen:
                                candidates.append({"url": url, "agency": "care", "source_label": "care_native_site_search"})
                                seen.add(url)
                elif agency_name == "icra":
                    try:
                        response = client.post(
                            "https://www.icra.in/Rating/GetRatingCompanys",
                            data={"Term": variant},
                            headers={"X-Requested-With": "XMLHttpRequest"},
                        )
                        response.raise_for_status()
                        payload = response.json()
                    except Exception as exc:  # noqa: BLE001
                        LOGGER.debug("ICRA native search failed for %s via %s: %s", company_name, variant, exc)
                        payload = []
                    for item in payload or []:
                        candidate_name = str(item.get("label") or "")
                        if self._candidate_name_score(company_name, candidate_name) < 0.72:
                            continue
                        company_id = str(item.get("id") or "").strip()
                        if company_id:
                            encoded_name = quote(candidate_name, safe="")
                            url = f"https://www.icra.in/Rating/RatingDetails?CompanyId={company_id}&CompanyName={encoded_name}"
                            if url not in seen:
                                candidates.append({"url": url, "agency": "icra", "source_label": "icra_native_site_search"})
                                seen.add(url)
                elif agency_name == "acuite":
                    try:
                        response = client.get(
                            "https://connect.acuite.in/search/result",
                            params={"query": variant},
                            headers={"X-Requested-With": "XMLHttpRequest"},
                        )
                        response.raise_for_status()
                        payload = response.json()
                    except Exception as exc:  # noqa: BLE001
                        LOGGER.debug("Acuite native search failed for %s via %s: %s", company_name, variant, exc)
                        payload = []
                    for item in payload or []:
                        candidate_name = str(item.get("Company_Name") or "")
                        if self._candidate_name_score(company_name, candidate_name) < 0.78:
                            continue
                        company_code = str(item.get("Company_Code") or "").strip()
                        if company_code:
                            url = f"https://connect.acuite.in/company-details/{company_code}"
                            if url not in seen:
                                candidates.append({"url": url, "agency": "acuite", "source_label": "acuite_native_site_search"})
                                seen.add(url)
                elif agency_name == "crisil":
                    try:
                        payload = self._crisil_search_payload(client, variant)
                    except Exception as exc:  # noqa: BLE001
                        LOGGER.debug("CRISIL native search failed for %s via %s: %s", company_name, variant, exc)
                        payload = {}
                    for company_code, docs in payload.items():
                        if not isinstance(docs, list):
                            continue
                        candidate_name = str((docs[0] or {}).get("companyName") or "")
                        if self._candidate_name_score(company_name, candidate_name) < 0.72:
                            continue
                        factsheet_url = f"https://www.crisilratings.com/en/home/our-business/ratings/company-factsheet.{company_code}.html"
                        if factsheet_url not in seen:
                            candidates.append({"url": factsheet_url, "agency": "crisil", "source_label": "crisil_native_site_search"})
                            seen.add(factsheet_url)
                elif agency_name == "india_ratings":
                    for entry in self._india_ratings_entries(client, company_name, variant):
                        direct_key = f"india_ratings:{entry.get('source_url') or entry.get('rating_date') or entry.get('rating')}"
                        if direct_key not in seen:
                            candidates.append(
                                {
                                    "agency": "india_ratings",
                                    "source_label": "india_ratings_native_site_search",
                                    "entry": entry,
                                    "direct_key": direct_key,
                                }
                            )
                            seen.add(direct_key)
                elif agency_name == "brickwork":
                    for entry in self._brickwork_entries(client, company_name, variant):
                        direct_key = f"brickwork:{entry.get('source_url') or entry.get('rating_date') or entry.get('rating')}"
                        if direct_key not in seen:
                            candidates.append(
                                {
                                    "agency": "brickwork",
                                    "source_label": "brickwork_native_site_search",
                                    "entry": entry,
                                    "direct_key": direct_key,
                                }
                            )
                            seen.add(direct_key)
                elif agency_name == "infomerics":
                    for entry in self._infomerics_entries(client, company_name, variant):
                        direct_key = f"infomerics:{entry.get('source_url') or entry.get('rating_date') or entry.get('rating')}"
                        if direct_key not in seen:
                            candidates.append(
                                {
                                    "agency": "infomerics",
                                    "source_label": "infomerics_native_site_search",
                                    "entry": entry,
                                    "direct_key": direct_key,
                                }
                            )
                            seen.add(direct_key)

                if candidates:
                    break

        return candidates

    def _care_search_payload(self, client: httpx.Client, query: str) -> dict[str, Any]:
        response = client.get(
            "https://www.careratings.com/header/searchlist",
            params={"cinput": query},
            headers={"X-Requested-With": "XMLHttpRequest"},
        )
        response.raise_for_status()
        payload = response.json()
        return payload if isinstance(payload, dict) else {}

    def _crisil_search_payload(self, client: httpx.Client, query: str) -> dict[str, Any]:
        filters = {"company_name": query}
        response = client.get(
            "https://www.crisilratings.com/content/crisilratings/en/home/our-business/ratings/credit-ratings-list/jcr:content/wrapper_100_par/columncontrol_copy/container-100-1/ratingresultlisting.results.json",
            params={"cmd": "CR", "start": 0, "limit": 10, "filters": json.dumps(filters)},
        )
        response.raise_for_status()
        payload = response.json()
        docs = payload.get("docs")
        if isinstance(docs, str):
            try:
                docs = json.loads(docs)
            except json.JSONDecodeError:
                docs = {}
        return docs if isinstance(docs, dict) else {}

    def _india_ratings_entries(self, client: httpx.Client, company_name: str, query: str) -> list[dict[str, Any]]:
        entries: list[dict[str, Any]] = []
        issuer_ids: list[int] = []
        try:
            response = client.get(
                "https://www.indiaratings.co.in/home/GetSearchIssuerData",
                params={"searchKey": query, "noOfShowEntry": 10},
                headers={"X-Requested-With": "XMLHttpRequest"},
            )
            response.raise_for_status()
            payload = response.json()
        except Exception as exc:  # noqa: BLE001
            LOGGER.debug("India Ratings issuer search failed for %s via %s: %s", company_name, query, exc)
            payload = []
        for item in payload or []:
            candidate_name = str(item.get("name") or item.get("issuerName") or "")
            if self._candidate_name_score(company_name, candidate_name) < 0.72:
                continue
            issuer_id = item.get("issuerID")
            if issuer_id is not None:
                try:
                    issuer_ids.append(int(issuer_id))
                except (TypeError, ValueError):
                    continue
        issuer_ids = list(dict.fromkeys(issuer_ids))
        for issuer_id in issuer_ids[:3]:
            for page_number in range(4):
                try:
                    response = client.get(
                        "https://www.indiaratings.co.in/home/GetIssuerPressReleases",
                        params={"issuerId": issuer_id, "pageNumber": page_number, "noofshowentry": 25},
                        headers={"X-Requested-With": "XMLHttpRequest"},
                    )
                    response.raise_for_status()
                    payload = response.json()
                except Exception as exc:  # noqa: BLE001
                    LOGGER.debug("India Ratings press release fetch failed for issuer %s: %s", issuer_id, exc)
                    break
                if not payload:
                    break
                for item in payload:
                    entry = self._india_ratings_entry_from_payload(company_name, item)
                    if entry:
                        entries.append(entry)
        return entries

    def _india_ratings_entry_from_payload(self, company_name: str, item: dict[str, Any]) -> dict[str, Any] | None:
        candidate_name = str(item.get("issuerName") or "")
        if candidate_name and self._candidate_name_score(company_name, candidate_name) < 0.72:
            return None
        text_parts = [
            str(item.get("pressReleaseTitle") or ""),
            str(item.get("overview") or ""),
            str(item.get("currentRatings") or ""),
            str(item.get("detailedRationaleOfRatingAction") or ""),
        ]
        text = normalize_text(" ".join(part for part in text_parts if part))
        rating_value = self._extract_prefixed_rating_label(text, prefix_pattern=r"IND(?:\s*RA)?", agency_name="india_ratings")
        if not rating_value:
            parsed = extract_rating_from_text(text, agency="india_ratings")
            rating_value = parsed.rating
        if not rating_value:
            return None
        press_release_id = item.get("pressReleaseID")
        source_url = (
            f"https://www.indiaratings.co.in/pressrelease/{press_release_id}"
            if press_release_id is not None
            else "https://www.indiaratings.co.in/"
        )
        return {
            "agency_name": "India Ratings",
            "rating": rating_value,
            "outlook": normalize_outlook(text),
            "rating_date": self._coerce_iso_date(item.get("effectiveDate")) or self._coerce_iso_date(item.get("prDate")),
            "rating_action": self._extract_rating_action(text),
            "source_url": source_url,
            "current_rating_text": str(item.get("currentRatings") or item.get("pressReleaseTitle") or ""),
            "rationale_summary": str(item.get("overview") or ""),
            "source": "india_ratings_native_site_search",
        }

    def _brickwork_company_urls(self, client: httpx.Client, query: str) -> list[tuple[str, str]]:
        query_key = query.strip().lower()
        if query_key in self._brickwork_search_cache:
            return self._brickwork_search_cache[query_key]

        try:
            response = client.get("https://www.brickworkratings.com/CreditRatings.aspx")
            response.raise_for_status()
        except Exception as exc:  # noqa: BLE001
            LOGGER.debug("Brickwork search bootstrap failed for %s: %s", query, exc)
            self._brickwork_search_cache[query_key] = []
            return []

        soup = BeautifulSoup(response.text, "lxml")
        form_data: dict[str, str] = {}
        for input_tag in soup.select("input[name]"):
            input_type = (input_tag.get("type") or "").lower()
            name_attr = input_tag.get("name")
            if input_type in {"hidden", "text"} and name_attr:
                form_data[name_attr] = input_tag.get("value", "")
        form_data["ctl00$ContentPlaceHolder1$txtSearch"] = query
        form_data["ctl00$ContentPlaceHolder1$btnSearch"] = "Search"
        try:
            search_response = client.post("https://www.brickworkratings.com/CreditRatings.aspx", data=form_data)
            search_response.raise_for_status()
        except Exception as exc:  # noqa: BLE001
            LOGGER.debug("Brickwork search submit failed for %s: %s", query, exc)
            self._brickwork_search_cache[query_key] = []
            return []

        results_soup = BeautifulSoup(search_response.text, "lxml")
        results: list[tuple[str, str]] = []
        for anchor in results_soup.find_all("a", href=True):
            href = str(anchor.get("href") or "")
            if "CompanyInstrument.aspx" not in href:
                continue
            company_label = " ".join(anchor.get_text(" ", strip=True).split())
            if not company_label:
                continue
            results.append((company_label, urljoin("https://www.brickworkratings.com/", href)))
        self._brickwork_search_cache[query_key] = results
        return results

    def _brickwork_entries(self, client: httpx.Client, company_name: str, query: str) -> list[dict[str, Any]]:
        entries: list[dict[str, Any]] = []
        for candidate_name, company_url in self._brickwork_company_urls(client, query):
            if self._candidate_name_score(company_name, candidate_name) < 0.72:
                continue
            try:
                response = client.get(company_url)
                response.raise_for_status()
            except Exception as exc:  # noqa: BLE001
                LOGGER.debug("Brickwork company page fetch failed for %s via %s: %s", company_name, company_url, exc)
                continue
            linked_urls = self._extract_html_candidate_urls(
                response.text,
                base_url=str(response.url),
                agency_hint="brickwork",
                company_name=company_name,
            )
            for linked_url in linked_urls:
                try:
                    rationale_response = client.get(linked_url)
                    rationale_response.raise_for_status()
                except Exception as exc:  # noqa: BLE001
                    LOGGER.debug("Brickwork rationale fetch failed for %s via %s: %s", company_name, linked_url, exc)
                    continue
                entry = self._brickwork_entry_from_html(rationale_response.text, source_url=str(rationale_response.url))
                if entry:
                    entries.append(entry)
        return entries

    def _brickwork_entry_from_html(self, html_text: str, *, source_url: str) -> dict[str, Any] | None:
        text = normalize_text(BeautifulSoup(html_text, "lxml").get_text(" ", strip=True))
        rating_value = self._extract_prefixed_rating_label(text, prefix_pattern=r"BWR", agency_name="brickwork")
        if not rating_value:
            return None
        return {
            "agency_name": "Brickwork",
            "rating": rating_value,
            "outlook": normalize_outlook(text),
            "rating_date": self._extract_date_from_text(text),
            "rating_action": self._extract_rating_action(text),
            "source_url": source_url,
            "current_rating_text": text[:500],
            "rationale_summary": text[:500],
            "source": "brickwork_native_site_search",
        }

    def _infomerics_entries(self, client: httpx.Client, company_name: str, query: str) -> list[dict[str, Any]]:
        try:
            response = client.get(
                "https://cms.infomerics.com/api/companies/autocomplete",
                params={"query": query},
                headers={"Accept": "application/json"},
            )
            response.raise_for_status()
            payload = response.json()
        except Exception as exc:  # noqa: BLE001
            LOGGER.debug("Infomerics autocomplete failed for %s via %s: %s", company_name, query, exc)
            payload = []

        entries: list[dict[str, Any]] = []
        for item in payload or []:
            candidate_name = str(item.get("CompanyName") or "")
            if self._candidate_name_score(company_name, candidate_name) < 0.72:
                continue
            slug = str(item.get("slug") or "").strip()
            if not slug:
                continue
            try:
                response = client.get(
                    f"https://cms.infomerics.com/api/companies/{slug}",
                    headers={"Accept": "application/json"},
                )
                response.raise_for_status()
                company_payload = response.json()
            except Exception as exc:  # noqa: BLE001
                LOGGER.debug("Infomerics company payload failed for %s via %s: %s", company_name, slug, exc)
                continue

            actual_company_name = str(((company_payload.get("company") or {}).get("CompanyName")) or candidate_name)
            if self._candidate_name_score(company_name, actual_company_name) < 0.72:
                continue
            for instrument in company_payload.get("companyInstrument") or []:
                raw_rating = str(instrument.get("Rating") or "")
                rating_value = self._extract_prefixed_rating_label(raw_rating, prefix_pattern=r"IVR", agency_name="infomerics")
                if not rating_value:
                    parsed = extract_rating_from_text(raw_rating, agency="infomerics")
                    rating_value = parsed.rating
                if not rating_value:
                    continue
                outlook_title = str(((instrument.get("outlook") or {}).get("Title")) or "").strip()
                if outlook_title.lower() in {"nil", "-", "na", "n/a"}:
                    outlook_title = ""
                document = ((instrument.get("LenderDetail") or {}).get("Document")) or {}
                document_file = document.get("DocumentFile") or {}
                source_url = str(document_file.get("url") or f"https://www.infomerics.com/pressrelease/{slug}")
                entries.append(
                    {
                        "agency_name": "Infomerics",
                        "rating": rating_value,
                        "outlook": outlook_title or normalize_outlook(raw_rating),
                        "rating_date": self._coerce_iso_date(instrument.get("Date")),
                        "rating_action": self._extract_rating_action(raw_rating),
                        "source_url": source_url,
                        "current_rating_text": raw_rating,
                        "rationale_summary": str(instrument.get("InstrumentTitle") or ""),
                        "source": "infomerics_native_site_search",
                    }
                )
        return entries

    def _coerce_iso_date(self, value: Any) -> str | None:
        text = str(value).strip() if value is not None else ""
        if not text:
            return None
        parsed = pd.to_datetime(text, errors="coerce")
        if parsed is None or pd.isna(parsed):
            return None
        return pd.Timestamp(parsed).date().isoformat()

    def _extract_rating_action(self, text: str | None) -> str | None:
        normalized = normalize_text(text or "")
        patterns = [
            r"\b(Affirmed|Reaffirmed|Upgraded|Downgraded|Assigned|Withdrawn|Migrated|Suspended|Continues|Continued|Revised|Placed on watch)\b",
        ]
        for pattern in patterns:
            match = re.search(pattern, normalized, flags=re.I)
            if match:
                return match.group(1).title()
        return None

    def _parse_candidate_entries(
        self,
        company_name: str,
        url: str,
        agency_hint: str | None,
        *,
        source_label: str,
        depth: int = 0,
        visited: set[str] | None = None,
    ) -> list[RatingHistoryEntry]:
        visited = visited or set()
        if url in visited or depth > 1:
            return []
        visited.add(url)

        if url.lower().endswith(".pdf"):
            entry = self._parse_pdf(company_name, url, agency_hint)
            if entry:
                entry.source_url = self._canonicalize_url(entry.source_url)
                entry.source = source_label
                return [entry]
            return []

        with httpx.Client(headers={"User-Agent": "Mozilla/5.0"}, timeout=30.0, follow_redirects=True) as client:
            response = client.get(url)
            response.raise_for_status()
            html_text = response.text

        entries: list[RatingHistoryEntry] = []
        linked_urls = self._extract_html_candidate_urls(html_text, base_url=str(response.url), agency_hint=agency_hint, company_name=company_name)
        for linked_url in linked_urls:
            try:
                entries.extend(
                    self._parse_candidate_entries(
                        company_name,
                        linked_url,
                        agency_hint,
                        source_label=source_label,
                        depth=depth + 1,
                        visited=visited,
                    )
                )
            except Exception as exc:  # noqa: BLE001
                LOGGER.debug("Skipping linked CRA candidate %s for %s: %s", linked_url, company_name, exc)

        text = BeautifulSoup(html_text, "lxml").get_text(" ", strip=True)
        text = normalize_text(text)
        parsed = extract_rating_from_text(text, agency=agency_hint)
        if parsed.rating:
            entries.append(
                RatingHistoryEntry(
                    agency_name=agency_hint or self._agency_from_url(url),
                    rating=parsed.rating,
                    outlook=normalize_outlook(text),
                    rating_date=self._extract_date_from_text(text),
                    rating_action=None,
                    source_url=self._canonicalize_url(url),
                    current_rating_text=parsed.notes,
                    source=source_label,
                )
            )
        return self._dedupe_entries(entries)

    def _parse_pdf(self, company_name: str, url: str, agency_hint: str | None) -> RatingHistoryEntry | None:
        safe_name = sanitize_filename(company_name)
        suffix = Path(urlsplit(url).path).suffix or ".pdf"
        target_path = self.config.rating_doc_cache_dir / f"{safe_name}__{abs(hash(url))}{suffix}"
        if not target_path.exists():
            with httpx.Client(headers={"User-Agent": "Mozilla/5.0"}, timeout=45.0, follow_redirects=True) as client:
                response = client.get(url)
                response.raise_for_status()
                target_path.write_bytes(response.content)

        extracted = extract_pdf_text(target_path)
        agency = agency_hint or detect_agency_name(target_path.name, extracted.text)
        parser = get_parser(agency)
        bundle = parser.parse(
            pdf_path=target_path,
            source_file=target_path.name,
            text=extracted.text,
            text_hash=extracted.text_hash,
            extractor_used=extracted.extractor_used,
        )
        event = next((event for event in bundle.rating_events if event.long_term_rating or event.short_term_rating), None)
        if not event:
            return None
        rating_value = event.long_term_rating or event.short_term_rating
        return RatingHistoryEntry(
            rating_date=event.rating_date.isoformat() if event.rating_date else (bundle.rationale_document.doc_date.isoformat() if bundle.rationale_document.doc_date else None),
            agency_name=bundle.rationale_document.agency_name,
            rating=rating_value,
            outlook=event.outlook,
            rating_action=event.rating_action,
            source_url=self._canonicalize_url(url),
            current_rating_text=event.current_rating,
            rationale_summary=bundle.rationale_features.qualitative_summary,
            source="cra_pdf_parser",
        )

    def _extract_html_candidate_urls(
        self,
        html_text: str,
        *,
        base_url: str,
        agency_hint: str | None,
        company_name: str,
    ) -> list[str]:
        soup = BeautifulSoup(html_text, "lxml")
        candidates: list[str] = []
        seen: set[str] = set()

        def add(url: str | None, anchor_text: str | None = None) -> None:
            if not url:
                return
            if "${" in url or "%7B" in url or "%24%7B" in url.lower():
                return
            absolute = urljoin(base_url, url)
            split = urlsplit(absolute)
            if split.scheme == "http" and self._agency_from_url(absolute):
                absolute = split._replace(scheme="https").geturl()
            if re.search(r"GetRationalReportFilePdf\?id=\s*$", absolute, flags=re.I):
                return
            if absolute in seen:
                return
            if not self._is_relevant_cra_link(absolute, agency_hint):
                return
            anchor_text = anchor_text or ""
            if absolute.lower().endswith(".pdf"):
                relevant_text = f"{absolute} {anchor_text}"
                if not self._title_contains_target_tokens(company_name, relevant_text) and not any(
                    token in absolute.lower() for token in ("rating", "rationale", "pressrelease", "docs", "newsfiles")
                ):
                    return
            seen.add(absolute)
            candidates.append(absolute)

        for anchor in soup.find_all("a", href=True):
            add(anchor.get("href"), anchor.get_text(" ", strip=True))

        for match in re.findall(r"https?://[^\s\"'<>]+", html_text):
            add(match)
        for match in re.findall(r"(?:/[^\"'<>\\s]+(?:\\.pdf|GetRationalReportFilePdf[^\"'<>\\s]*|ViewRatingRationale[^\"'<>\\s]*|fcompany-details/[^\"'<>\\s]+|company-details/\\d+|uploads/newsfiles/[^\"'<>\\s]+))", html_text, flags=re.I):
            add(match)

        return candidates[:20]

    def _agency_from_url(self, url: str) -> str | None:
        host = urlsplit(url).netloc.lower()
        for domain, agency in CRA_DOMAINS.items():
            if domain in host:
                return agency
        return None

    def _is_relevant_cra_link(self, url: str, agency_hint: str | None) -> bool:
        agency = self._agency_from_url(url)
        if agency_hint and agency and agency != agency_hint:
            return False
        if agency_hint and not agency:
            host = urlsplit(url).netloc.lower()
            for domain in AGENCY_DOMAINS.get(agency_hint, ()):
                if domain in host:
                    break
            else:
                return False
        lower_url = url.lower()
        return any(hint in lower_url for hint in RELEVANT_URL_HINTS)

    def _search_variants(self, company_name: str) -> list[str]:
        variants = [company_name.strip()]
        compact = " ".join(company_name_tokens(company_name))
        if compact and compact not in variants:
            variants.append(compact)
        tokens = compact.split()
        if len(tokens) > 3:
            shortened = " ".join(tokens[:3])
            if shortened not in variants:
                variants.append(shortened)
        return [variant for variant in variants if variant]

    def _candidate_name_score(self, target_name: str, candidate_name: str) -> float:
        target = normalize_company_name(target_name)
        candidate = normalize_company_name(candidate_name)
        if not target or not candidate:
            return 0.0
        if target == candidate:
            return 1.0
        target_tokens = set(company_name_tokens(target_name))
        candidate_tokens = set(company_name_tokens(candidate_name))
        if not target_tokens or not candidate_tokens:
            return 0.0
        overlap = len(target_tokens & candidate_tokens)
        if overlap == 0:
            return 0.0
        coverage = overlap / len(target_tokens)
        precision = overlap / len(candidate_tokens)
        prefix_bonus = 0.1 if candidate.startswith(target) or target.startswith(candidate) else 0.0
        return round(min(1.0, (0.7 * coverage) + (0.3 * precision) + prefix_bonus), 4)

    def _title_contains_target_tokens(self, target_name: str, text: str) -> bool:
        target_tokens = set(company_name_tokens(target_name))
        text_tokens = set(company_name_tokens(text))
        if not target_tokens or not text_tokens:
            return False
        return len(target_tokens & text_tokens) >= max(1, min(2, len(target_tokens)))

    def _search_result_matches_company(self, company_name: str, title: str, snippet: str, url: str) -> bool:
        combined = " ".join(part for part in (title, snippet, urlsplit(url).path) if part)
        score = self._candidate_name_score(company_name, combined)
        return score >= 0.35 or self._title_contains_target_tokens(company_name, combined)

    def _extract_date_from_text(self, text: str) -> str | None:
        patterns = (
            r"\b(\d{1,2}\s+[A-Za-z]{3,9}\s+\d{4})\b",
            r"\b(\d{1,2}-[A-Za-z]{3}-\d{4})\b",
            r"\b([A-Za-z]{3,9}\s+\d{1,2},\s+\d{4})\b",
            r"\b(\d{1,2}[A-Za-z]{3,9}\d{4})\b",
        )
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                try:
                    parsed = pd.to_datetime(match.group(1), errors="coerce")
                except Exception:  # noqa: BLE001
                    parsed = None
                if parsed is not None and not pd.isna(parsed):
                    return parsed.date().isoformat()
                return match.group(1)
        return None

    def _dedupe_entries(self, entries: list[RatingHistoryEntry]) -> list[RatingHistoryEntry]:
        entries = [entry for entry in entries if entry.rating]
        entries.sort(key=self._entry_sort_key, reverse=True)
        unique: list[RatingHistoryEntry] = []
        seen = set()
        for entry in entries:
            key = (
                entry.rating_date,
                normalize_company_name(entry.agency_name or ""),
                entry.rating,
                normalize_company_name(entry.current_rating_text or ""),
            )
            if key in seen:
                continue
            unique.append(entry)
            seen.add(key)
        return unique

    def _entry_sort_key(self, entry: RatingHistoryEntry) -> tuple[str, str]:
        date_text = entry.rating_date or ""
        try:
            parsed = pd.to_datetime(date_text, errors="coerce")
        except Exception:  # noqa: BLE001
            parsed = None
        sortable = parsed.date().isoformat() if parsed is not None and not pd.isna(parsed) else date_text
        return sortable, entry.rating or ""

    def _canonicalize_url(self, url: str | None) -> str | None:
        if not url:
            return url
        split = urlsplit(url)
        if not split.fragment:
            return url
        return split._replace(fragment="").geturl()

    def _extract_prefixed_rating_label(self, text: str | None, *, prefix_pattern: str, agency_name: str) -> str | None:
        normalized = normalize_text(text or "")
        match = re.search(
            rf"\b{prefix_pattern}\s*[-:/]?\s*{RATING_TOKEN_PATTERN}(?=[^A-Za-z0-9]|$)",
            normalized,
            flags=re.I,
        )
        if not match:
            return None
        raw_rating = re.sub(r"\s+", "", match.group(1).upper())
        normalized_rating = normalize_rating_label(agency_name, raw_rating)
        return normalized_rating.normalized_label or raw_rating
