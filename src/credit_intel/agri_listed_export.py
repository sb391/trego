from __future__ import annotations

import logging
import re
import shutil
import time
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

import fitz
import httpx
import pandas as pd
from bs4 import BeautifulSoup

from ..config import AppConfig
from ..io_utils import build_company_id, normalize_company_name
from ..utils.pdf import extract_pdf_text
from ..utils.text import sanitize_filename
from .config import CreditIntelConfig
from .external_simulation_benchmark import (
    _build_agency_range_frame,
    _build_agency_strength_frame,
    _build_company_range_benchmark,
    _load_or_build_live_range_policy,
    _normalize_merge_keys,
)
from .rating_discovery import RatingDiscoveryService
from .rating_repository import ExistingRatingRepository
from .simulation_pipeline import simulate_unrated_companies


LOGGER = logging.getLogger(__name__)

DEFAULT_SOURCE_ROOT = Path("outputs/agri_food_other_products")
DEFAULT_MODEL_BASE_DIR = Path("outputs/agri_food_other_products/simulation_model")
DEFAULT_OUTPUT_DIR = Path("outputs/agri_listed_250cr_profitable")
DEFAULT_REPORT_STEM = "agri_listed_250cr_profitable"
DEFAULT_RANGE_POLICY_PATH = Path(
    "outputs/credit_intel/external_simulation_benchmark_agri_cra_only/reports/agency_range_calibration.csv"
)

KNOWN_COMPANY_SECRETARY_OVERRIDES: dict[str, dict[str, Any]] = {
    "Kriti_Nutrients__KRITINUT": {
        "company_secretary_name": "Raj Kumar Bhawsar",
        "company_secretary_source_type": "manual_override",
        "company_secretary_source_url": None,
        "company_secretary_notes": "Manually verified from cached annual report page 47.",
        "annual_report_url": None,
        "annual_report_label": "Cached annual report",
    },
    "Ambar_Protein__519471": {
        "company_secretary_name": "Mehul Ashokkumar Mehta",
        "company_secretary_source_type": "manual_override",
        "company_secretary_source_url": None,
        "company_secretary_notes": "Manually verified from cached annual report page 33.",
        "annual_report_url": None,
        "annual_report_label": "Cached annual report",
    },
    "Triven_Engg_Ind__TRIVENI": {
        "company_secretary_name": "Geeta Bhalla",
        "company_secretary_source_type": "manual_override",
        "company_secretary_source_url": None,
        "company_secretary_notes": "Manually verified from cached annual report page 1.",
        "annual_report_url": None,
        "annual_report_label": "Cached annual report",
    },
    "Dwarikesh_Sugar__DWARKESH": {
        "company_secretary_name": "B. J. Maheshwari",
        "company_secretary_source_type": "manual_override",
        "company_secretary_source_url": None,
        "company_secretary_notes": "Manually verified from cached annual report page 5.",
        "annual_report_url": None,
        "annual_report_label": "Cached annual report",
    },
    "Jay_Shree_Tea__JAYSREETEA": {
        "company_secretary_name": "R. K. Ganeriwala",
        "company_secretary_source_type": "manual_override",
        "company_secretary_source_url": None,
        "company_secretary_notes": "Manually verified from cached annual report page 1.",
        "annual_report_url": None,
        "annual_report_label": "Cached annual report",
    },
}


def run_industry_listed_export(
    *,
    source_root: Path = DEFAULT_SOURCE_ROOT,
    model_base_dir: Path = DEFAULT_MODEL_BASE_DIR,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    report_stem: str = DEFAULT_REPORT_STEM,
    force_ratings: bool = False,
    force_cs: bool = False,
) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    reports_dir = output_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    company_excels_dir = output_dir / "company_excels"
    company_excels_dir.mkdir(parents=True, exist_ok=True)
    cache_dir = output_dir / "cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    cs_cache_dir = cache_dir / "company_secretary_docs"
    cs_cache_dir.mkdir(parents=True, exist_ok=True)

    eligible = _load_eligible_agri_companies(source_root=source_root)
    _copy_individual_workbooks(eligible, target_dir=company_excels_dir)

    ratings_latest_path = reports_dir / "cra_latest_ratings.csv"
    ratings_history_path = reports_dir / "cra_rating_history.csv"
    ratings_latest, ratings_history = _discover_latest_cra_ratings(
        companies_frame=eligible,
        source_root=source_root,
        latest_output_path=ratings_latest_path,
        history_output_path=ratings_history_path,
        force=force_ratings,
    )

    cs_output_path = reports_dir / "company_secretary_details.csv"
    company_secretaries = _extract_company_secretaries(
        companies_frame=eligible,
        output_path=cs_output_path,
        cache_dir=cs_cache_dir,
        force=force_cs,
    )

    simulation_selection = _build_simulation_selection_for_companies(
        companies_frame=eligible,
        actual_ratings_frame=ratings_latest,
        source_root=source_root,
        model_base_dir=model_base_dir,
        simulation_output_dir=cache_dir / "live_simulations",
    )

    final_frame = _build_final_master_frame(
        companies_frame=eligible,
        ratings_latest_frame=ratings_latest,
        company_secretaries_frame=company_secretaries,
        simulation_selection_frame=simulation_selection,
        company_excels_dir=company_excels_dir,
    )

    financial_subset_outputs = _write_filtered_financial_tables(
        eligible_company_ids=set(final_frame["company_id"].astype(str).tolist()),
        source_root=source_root,
        output_dir=reports_dir,
    )

    eligible_companies_csv = reports_dir / "eligible_companies_master.csv"
    final_frame.to_csv(eligible_companies_csv, index=False)

    workbook_path = reports_dir / f"{report_stem}_master.xlsx"
    _write_consolidated_workbook(
        master_frame=final_frame,
        ratings_history_frame=ratings_history,
        company_secretaries_frame=company_secretaries,
        output_path=workbook_path,
    )

    single_sheet_workbook = reports_dir / f"{report_stem}_single_sheet.xlsx"
    with pd.ExcelWriter(single_sheet_workbook, engine="openpyxl") as writer:
        final_frame.to_excel(writer, sheet_name="eligible_companies", index=False)

    return {
        "eligible_companies_csv": eligible_companies_csv,
        "eligible_companies_workbook": workbook_path,
        "eligible_companies_single_sheet_workbook": single_sheet_workbook,
        "cra_latest_ratings_csv": ratings_latest_path,
        "cra_rating_history_csv": ratings_history_path,
        "company_secretary_csv": cs_output_path,
        "company_excels_dir": company_excels_dir,
        **financial_subset_outputs,
    }


def run_agri_listed_export(
    *,
    source_root: Path = DEFAULT_SOURCE_ROOT,
    model_base_dir: Path = DEFAULT_MODEL_BASE_DIR,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    force_ratings: bool = False,
    force_cs: bool = False,
) -> dict[str, Path]:
    return run_industry_listed_export(
        source_root=source_root,
        model_base_dir=model_base_dir,
        output_dir=output_dir,
        report_stem=DEFAULT_REPORT_STEM,
        force_ratings=force_ratings,
        force_cs=force_cs,
    )


def _load_eligible_agri_companies(*, source_root: Path) -> pd.DataFrame:
    latest_features = pd.read_csv(source_root / "simulation_model/financials/latest_financial_features.csv")
    financial_summary = pd.read_csv(source_root / "simulation_model/financials/financial_summary.csv")
    profit_loss = pd.read_csv(source_root / "simulation_model/financials/profit_loss_annual.csv")
    download_status = pd.read_csv(source_root / "download_status.csv")

    latest_features = _normalize_merge_keys(latest_features, ["company_id", "company_name"])
    financial_summary = _normalize_merge_keys(financial_summary, ["company_id", "company_name"])
    profit_loss = _normalize_merge_keys(profit_loss, ["company_id", "company_name"])
    download_status = _normalize_merge_keys(download_status, ["company_id", "company_name"])

    profit_loss["period"] = pd.to_datetime(profit_loss["period"], errors="coerce")
    latest_profit = (
        profit_loss.sort_values(["company_id", "period"])
        .groupby("company_id", as_index=False)
        .tail(1)[["company_id", "net_profit", "period"]]
        .rename(columns={"period": "latest_profit_period"})
    )

    merged = latest_features.merge(
        financial_summary[
            [
                "company_id",
                "current_price",
                "market_cap_crore",
                "statement_period",
                "workbook_path",
            ]
        ],
        on="company_id",
        how="left",
    )
    merged = merged.merge(latest_profit, on="company_id", how="left")
    merged = merged.merge(
        download_status[["company_id", "screener_url", "local_file_path", "status"]],
        on="company_id",
        how="left",
    )

    filtered = merged[
        (pd.to_numeric(merged["revenue_crore"], errors="coerce") > 250.0)
        & (pd.to_numeric(merged["net_profit"], errors="coerce") > 0.0)
        & merged["screener_url"].notna()
    ].copy()

    filtered["listed_status"] = "listed"
    filtered["listed_flag"] = True
    filtered["credit_rating_status"] = "pending"
    filtered["simulation_required_flag"] = False
    filtered = filtered.sort_values(["sub_industry", "revenue_crore", "company_name"], ascending=[True, False, True])
    return filtered.reset_index(drop=True)


def _copy_individual_workbooks(companies_frame: pd.DataFrame, *, target_dir: Path) -> None:
    target_dir.mkdir(parents=True, exist_ok=True)
    for row in companies_frame.to_dict(orient="records"):
        source_path = Path(str(row.get("local_file_path") or row.get("workbook_path") or ""))
        if not source_path.exists():
            LOGGER.warning("Workbook missing for %s at %s", row.get("company_name"), source_path)
            continue
        destination = target_dir / source_path.name
        if destination.exists():
            continue
        shutil.copy2(source_path, destination)


def _discover_latest_cra_ratings(
    *,
    companies_frame: pd.DataFrame,
    source_root: Path,
    latest_output_path: Path,
    history_output_path: Path,
    force: bool,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    config = CreditIntelConfig()
    config.ensure_directories()
    source_history_path = source_root / "credit_rating_history.csv"
    repository = ExistingRatingRepository(source_history_path)
    service = RatingDiscoveryService(config, repository)

    screener_history = pd.read_csv(source_history_path) if source_history_path.exists() else pd.DataFrame()
    download_status_path = source_root / "download_status.csv"
    download_status = pd.read_csv(download_status_path) if download_status_path.exists() else pd.DataFrame()
    screener_lookup: dict[str, dict[str, Any]] = {}
    screener_history_lookup: dict[str, list[dict[str, Any]]] = {}
    download_status_lookup: dict[str, dict[str, Any]] = {}
    if not screener_history.empty and "company_id" in screener_history.columns:
        screener_history = _normalize_merge_keys(screener_history, ["company_id", "company_name"])
        screener_history["rating_date_parsed"] = pd.to_datetime(screener_history.get("rating_date"), errors="coerce")
        screener_history = screener_history.sort_values(
            ["company_id", "rating_date_parsed", "rating_date"],
            ascending=[True, False, False],
        )
        for company_id, group in screener_history.groupby("company_id", dropna=False):
            company_key = str(company_id)
            records = group.to_dict(orient="records")
            screener_history_lookup[company_key] = records
            screener_lookup[company_key] = records[0]
    if not download_status.empty and "company_id" in download_status.columns:
        download_status = _normalize_merge_keys(download_status, ["company_id", "company_name"])
        download_status_lookup = {
            str(record["company_id"]): record for record in download_status.to_dict(orient="records")
        }

    existing_latest = pd.read_csv(latest_output_path) if latest_output_path.exists() and not force else pd.DataFrame()
    existing_history = pd.read_csv(history_output_path) if history_output_path.exists() and not force else pd.DataFrame()
    existing_lookup = {
        str(row["company_id"]): row for row in existing_latest.to_dict(orient="records")
    } if not existing_latest.empty and "company_id" in existing_latest.columns else {}

    latest_rows: list[dict[str, Any]] = []
    history_rows: list[dict[str, Any]] = existing_history.to_dict(orient="records") if not existing_history.empty else []
    screener_name_cache: dict[str, str | None] = {}

    for row in companies_frame.to_dict(orient="records"):
        company_id = str(row["company_id"])
        company_name = str(row["company_name"])
        existing_latest_row = existing_lookup.get(company_id)
        if _should_reuse_existing_latest(existing_latest_row):
            latest_rows.append(_with_rating_medium(existing_latest_row))
            continue

        cached_latest = screener_lookup.get(company_id)
        if cached_latest:
            latest_rows.append(
                {
                    "company_id": company_id,
                    "company_name": company_name,
                    "latest_cra_rating_status": "Rated",
                    "latest_cra_rating_agency": cached_latest.get("rating_agency"),
                    "latest_cra_rating": cached_latest.get("rating"),
                    "latest_cra_rating_date": cached_latest.get("rating_date"),
                    "latest_cra_rating_month_year": _month_year(cached_latest.get("rating_date")),
                    "latest_cra_rating_source_url": cached_latest.get("rating_update_url"),
                    "latest_cra_rating_source": cached_latest.get("extraction_method") or cached_latest.get("source") or "screener_documents",
                    "latest_cra_rating_medium": "screener.in",
                    "cra_history_count": len(screener_history_lookup.get(company_id, [])),
                }
            )
            for idx, entry in enumerate(screener_history_lookup.get(company_id, [])):
                history_rows.append(
                    {
                        "company_id": company_id,
                        "company_name": company_name,
                        "history_rank": idx + 1,
                        "rating_date": entry.get("rating_date"),
                        "rating_month_year": _month_year(entry.get("rating_date")),
                        "rating_agency": entry.get("rating_agency"),
                        "rating": entry.get("rating"),
                        "outlook": entry.get("outlook"),
                        "rating_action": entry.get("rating_action"),
                        "source_url": entry.get("rating_update_url"),
                        "source": entry.get("extraction_method") or entry.get("source") or "screener_documents",
                        "source_medium": "screener.in",
                    }
                )
            pd.DataFrame(latest_rows).to_csv(latest_output_path, index=False)
            pd.DataFrame(history_rows).to_csv(history_output_path, index=False)
            continue

        status_row = download_status_lookup.get(company_id, {})
        screener_url = str(row.get("screener_url") or status_row.get("screener_url") or "").strip() or None
        screener_legal_name = _fetch_screener_legal_name(screener_url, screener_name_cache)
        search_names = _build_rating_search_names(
            company_name,
            str(status_row.get("company_name") or "").strip() or None,
            screener_legal_name,
        )

        LOGGER.info("CRA-native rating discovery for %s", company_name)
        insight = None
        for search_name in search_names:
            try:
                insight = service.discover(
                    search_name,
                    aliases=search_names,
                    mode="cra_only",
                    use_repository=False,
                    allow_dataset_fallback=False,
                )
            except Exception as exc:  # noqa: BLE001
                LOGGER.warning("CRA-native discovery failed for %s via %s: %s", company_name, search_name, exc)
                insight = None
            if insight and insight.rating_available_flag:
                break

        if insight and insight.rating_available_flag:
            latest_entry = insight.history[0] if insight.history else None
            latest_rows.append(
                {
                    "company_id": company_id,
                    "company_name": company_name,
                    "latest_cra_rating_status": "Rated",
                    "latest_cra_rating_agency": latest_entry.agency_name if latest_entry else insight.agency_name,
                    "latest_cra_rating": latest_entry.rating if latest_entry else insight.rating,
                    "latest_cra_rating_date": latest_entry.rating_date if latest_entry else insight.rating_date,
                    "latest_cra_rating_month_year": _month_year(latest_entry.rating_date if latest_entry else insight.rating_date),
                    "latest_cra_rating_source_url": latest_entry.source_url if latest_entry else None,
                    "latest_cra_rating_source": latest_entry.source if latest_entry else "cra_native_site_search",
                    "latest_cra_rating_medium": "cra_crawl",
                    "cra_history_count": len(insight.history),
                }
            )
            for idx, entry in enumerate(insight.history):
                history_rows.append(
                    {
                        "company_id": company_id,
                        "company_name": company_name,
                        "history_rank": idx + 1,
                        "rating_date": entry.rating_date,
                        "rating_month_year": _month_year(entry.rating_date),
                        "rating_agency": entry.agency_name,
                        "rating": entry.rating,
                        "outlook": entry.outlook,
                        "rating_action": entry.rating_action,
                        "source_url": entry.source_url,
                        "source": entry.source,
                        "source_medium": "cra_crawl",
                    }
                )
        else:
            latest_rows.append(
                {
                    "company_id": company_id,
                    "company_name": company_name,
                    "latest_cra_rating_status": "Not Rated",
                    "latest_cra_rating_agency": None,
                    "latest_cra_rating": "Not Rated",
                    "latest_cra_rating_date": None,
                    "latest_cra_rating_month_year": None,
                    "latest_cra_rating_source_url": None,
                    "latest_cra_rating_source": "not_found",
                    "latest_cra_rating_medium": "not_found",
                    "cra_history_count": 0,
                }
            )

        pd.DataFrame(latest_rows).to_csv(latest_output_path, index=False)
        pd.DataFrame(history_rows).to_csv(history_output_path, index=False)
        time.sleep(0.5)

    latest_frame = pd.DataFrame(latest_rows).sort_values(["latest_cra_rating_status", "company_name"], ascending=[True, True])
    history_frame = pd.DataFrame(history_rows).sort_values(["company_name", "rating_date"], ascending=[True, False])
    latest_frame.to_csv(latest_output_path, index=False)
    history_frame.to_csv(history_output_path, index=False)
    return latest_frame, history_frame


def _should_reuse_existing_latest(existing_row: dict[str, Any] | None) -> bool:
    if not existing_row:
        return False
    return str(existing_row.get("latest_cra_rating_status") or "").strip().lower() == "rated"


def _with_rating_medium(row: dict[str, Any]) -> dict[str, Any]:
    enriched = dict(row)
    enriched["latest_cra_rating_medium"] = _derive_rating_medium(enriched.get("latest_cra_rating_source"))
    return enriched


def _derive_rating_medium(source: Any) -> str:
    source_text = str(source or "").strip().lower()
    if "screener" in source_text:
        return "screener.in"
    if source_text and source_text != "not_found":
        return "cra_crawl"
    return "not_found"


def _build_rating_search_names(*names: str | None) -> list[str]:
    ordered: list[str] = []
    seen: set[str] = set()
    for raw_name in names:
        candidate = " ".join(str(raw_name or "").split())
        normalized = normalize_company_name(candidate)
        if not candidate or not normalized or normalized in seen:
            continue
        ordered.append(candidate)
        seen.add(normalized)
    return ordered


def _fetch_screener_legal_name(screener_url: str | None, cache: dict[str, str | None]) -> str | None:
    if not screener_url:
        return None
    if screener_url in cache:
        return cache[screener_url]
    try:
        with httpx.Client(headers={"User-Agent": "Mozilla/5.0"}, timeout=30.0, follow_redirects=True) as client:
            response = client.get(screener_url)
            response.raise_for_status()
    except Exception as exc:  # noqa: BLE001
        LOGGER.debug("Unable to fetch Screener legal name from %s: %s", screener_url, exc)
        cache[screener_url] = None
        return None
    soup = BeautifulSoup(response.text, "lxml")
    header = soup.find("h1")
    legal_name = " ".join(header.get_text(" ", strip=True).split()) if header else None
    cache[screener_url] = legal_name or None
    return cache[screener_url]


def _extract_company_secretaries(
    *,
    companies_frame: pd.DataFrame,
    output_path: Path,
    cache_dir: Path,
    force: bool,
) -> pd.DataFrame:
    existing = pd.read_csv(output_path) if output_path.exists() and not force else pd.DataFrame()
    existing_lookup = {
        str(row["company_id"]): row for row in existing.to_dict(orient="records")
    } if not existing.empty and "company_id" in existing.columns else {}
    rows: list[dict[str, Any]] = []

    with httpx.Client(headers={"User-Agent": "Mozilla/5.0"}, timeout=45.0, follow_redirects=True) as client:
        for row in companies_frame.to_dict(orient="records"):
            company_id = str(row["company_id"])
            if company_id in existing_lookup:
                rows.append(existing_lookup[company_id])
                continue

            company_name = str(row["company_name"])
            screener_url = str(row.get("screener_url") or "")
            LOGGER.info("Extracting Company Secretary for %s", company_name)
            try:
                details = _extract_company_secretary_for_company(
                    client=client,
                    company_name=company_name,
                    company_id=company_id,
                    screener_url=screener_url,
                    cache_dir=cache_dir,
                )
            except Exception as exc:  # noqa: BLE001
                LOGGER.warning("Company Secretary extraction failed for %s: %s", company_name, exc)
                details = {
                    "company_secretary_name": None,
                    "company_secretary_contact_details": None,
                    "company_secretary_source_type": "error",
                    "company_secretary_source_url": None,
                    "company_secretary_notes": str(exc),
                    "annual_report_url": None,
                    "annual_report_label": None,
                }

            row_details = details.copy()
            row_details.update(KNOWN_COMPANY_SECRETARY_OVERRIDES.get(company_id, {}))
            rows.append(
                {
                    "company_id": company_id,
                    "company_name": company_name,
                    **row_details,
                }
            )
            pd.DataFrame(rows).to_csv(output_path, index=False)
            time.sleep(0.4)

    frame = pd.DataFrame(rows).sort_values("company_name")
    frame.to_csv(output_path, index=False)
    return frame


def _extract_company_secretary_for_company(
    *,
    client: httpx.Client,
    company_name: str,
    company_id: str,
    screener_url: str,
    cache_dir: Path,
) -> dict[str, Any]:
    cached_annual_report = cache_dir / f"{sanitize_filename(company_id)}__annual_report.pdf"
    if cached_annual_report.exists():
        cs_name, notes = _extract_company_secretary_from_pdf(cached_annual_report)
        if cs_name:
            contact_details = _extract_company_secretary_contact_details_from_pdf(cached_annual_report, cs_name)
            return {
                "company_secretary_name": cs_name,
                "company_secretary_contact_details": contact_details,
                "company_secretary_source_type": "annual_report_cache",
                "company_secretary_source_url": None,
                "company_secretary_notes": notes,
                "annual_report_url": None,
                "annual_report_label": "Cached annual report",
            }

    response = client.get(screener_url)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "lxml")
    sections = _parse_document_sections(soup, base_url=str(response.url))

    annual_reports = sections.get("annual reports", [])
    if annual_reports:
        label, annual_report_url = annual_reports[0]
        pdf_path = _download_document(client, annual_report_url, cache_dir / f"{sanitize_filename(company_id)}__annual_report.pdf")
        cs_name, notes = _extract_company_secretary_from_pdf(pdf_path)
        if cs_name:
            contact_details = _extract_company_secretary_contact_details_from_pdf(pdf_path, cs_name)
            return {
                "company_secretary_name": cs_name,
                "company_secretary_contact_details": contact_details,
                "company_secretary_source_type": "annual_report",
                "company_secretary_source_url": annual_report_url,
                "company_secretary_notes": notes,
                "annual_report_url": annual_report_url,
                "annual_report_label": label,
            }

    for heading in ("announcements", "corporate actions"):
        for label, doc_url in sections.get(heading, []):
            lowered = label.lower()
            if "secretary" not in lowered and "compliance officer" not in lowered and "appointment" not in lowered and "resignation" not in lowered:
                continue
            source_path = None
            if doc_url.lower().endswith(".pdf"):
                source_path = _download_document(client, doc_url, cache_dir / f"{sanitize_filename(company_id)}__announcement.pdf")
                cs_name, notes = _extract_company_secretary_from_pdf(source_path)
                contact_details = _extract_company_secretary_contact_details_from_pdf(source_path, cs_name) if cs_name else None
            else:
                ann_response = client.get(doc_url)
                ann_response.raise_for_status()
                announcement_text = BeautifulSoup(ann_response.text, "lxml").get_text(" ", strip=True)
                cs_name, notes = _extract_company_secretary_from_text(announcement_text)
                contact_details = _extract_company_secretary_contact_details_from_text(announcement_text, cs_name) if cs_name else None
            if cs_name:
                return {
                    "company_secretary_name": cs_name,
                    "company_secretary_contact_details": contact_details,
                    "company_secretary_source_type": "announcement",
                    "company_secretary_source_url": doc_url,
                    "company_secretary_notes": f"{heading}: {label}. {notes or ''}".strip(),
                    "annual_report_url": annual_reports[0][1] if annual_reports else None,
                    "annual_report_label": annual_reports[0][0] if annual_reports else None,
                }

    return {
        "company_secretary_name": None,
        "company_secretary_contact_details": None,
        "company_secretary_source_type": "not_found",
        "company_secretary_source_url": annual_reports[0][1] if annual_reports else None,
        "company_secretary_notes": "No Company Secretary could be extracted from the latest annual report or matching announcements.",
        "annual_report_url": annual_reports[0][1] if annual_reports else None,
        "annual_report_label": annual_reports[0][0] if annual_reports else None,
    }


def _parse_document_sections(soup: BeautifulSoup, *, base_url: str) -> dict[str, list[tuple[str, str]]]:
    sections: dict[str, list[tuple[str, str]]] = {}
    for container in soup.select("div.documents"):
        heading = container.select_one("h3")
        heading_text = heading.get_text(" ", strip=True).lower() if heading else "documents"
        items: list[tuple[str, str]] = []
        for anchor in container.select("a[href]"):
            label = " ".join(anchor.get_text(" ", strip=True).split())
            href = urljoin(base_url, anchor.get("href"))
            if label and href:
                items.append((label, href))
        if items:
            sections[heading_text] = items
    return sections


def _download_document(client: httpx.Client, url: str, target_path: Path) -> Path:
    target_path.parent.mkdir(parents=True, exist_ok=True)
    if not target_path.exists():
        response = client.get(url, timeout=90.0)
        response.raise_for_status()
        target_path.write_bytes(response.content)
    return target_path


def _extract_company_secretary_from_pdf(pdf_path: Path) -> tuple[str | None, str | None]:
    quick_name, quick_notes = _extract_company_secretary_with_pymupdf(pdf_path)
    if quick_name:
        return quick_name, quick_notes

    extracted = extract_pdf_text(pdf_path)
    return _extract_company_secretary_from_text(extracted.text)


def _extract_company_secretary_contact_details_from_pdf(pdf_path: Path, company_secretary_name: str | None) -> str | None:
    try:
        document = fitz.open(pdf_path)
    except Exception:  # noqa: BLE001
        return None

    relevant_snippets: list[str] = []
    name_tokens = [
        token.lower()
        for token in re.findall(r"[A-Za-z][A-Za-z\.']+", company_secretary_name or "")
        if len(token) > 1
    ]
    for page_number in range(document.page_count):
        text = document.load_page(page_number).get_text("text") or ""
        if not text:
            continue
        page_contacts = _extract_company_secretary_contact_details_from_text(text, company_secretary_name)
        if page_contacts:
            relevant_snippets.append(page_contacts)
            continue

        lowered = text.lower()
        if name_tokens and not any(token in lowered for token in name_tokens):
            continue
        if "secretary" not in lowered and "compliance officer" not in lowered:
            continue
        page_level_contacts = _extract_contact_details(text)
        if page_level_contacts:
            relevant_snippets.append(page_level_contacts)

    if not relevant_snippets:
        return None
    return _merge_contact_details(relevant_snippets)


def _extract_company_secretary_with_pymupdf(pdf_path: Path) -> tuple[str | None, str | None]:
    try:
        document = fitz.open(pdf_path)
    except Exception as exc:  # noqa: BLE001
        return None, f"pymupdf failed: {exc}"

    page_count = document.page_count
    page_numbers = list(range(min(page_count, 80)))
    tail_pages = [page_count - offset - 1 for offset in range(min(page_count, 15))]
    for page_number in tail_pages:
        if page_number not in page_numbers:
            page_numbers.append(page_number)

    for page_number in page_numbers:
        text = document.load_page(page_number).get_text("text") or ""
        if "secretary" not in text.lower() and "acs-" not in text.lower() and "compliance officer" not in text.lower():
            continue
        name, notes = _extract_company_secretary_from_text(text)
        if name:
            return name, f"{notes or ''} page={page_number + 1}".strip()
    return None, None


def _extract_company_secretary_contact_details_from_text(
    text: str,
    company_secretary_name: str | None,
) -> str | None:
    normalized_text = text.replace("\r", "\n")
    lines = [
        " ".join(line.split())
        for line in normalized_text.splitlines()
        if line and line.strip()
    ]
    if not lines:
        return None

    name_tokens = [
        token.lower()
        for token in re.findall(r"[A-Za-z][A-Za-z\.']+", company_secretary_name or "")
        if len(token) > 1
    ]

    snippets: list[str] = []
    for index, line in enumerate(lines):
        lowered = line.lower()
        line_is_anchor = False
        if company_secretary_name and company_secretary_name.lower() in lowered:
            line_is_anchor = True
        elif any(token in lowered for token in name_tokens) and (
            "secretary" in lowered or "compliance officer" in lowered
        ):
            line_is_anchor = True
        elif "company secretary" in lowered or "compliance officer" in lowered:
            line_is_anchor = True

        if not line_is_anchor:
            continue

        snippet = "\n".join(lines[max(0, index - 6) : min(len(lines), index + 7)])
        contacts = _extract_contact_details(snippet)
        if contacts:
            snippets.append(contacts)

    if not snippets:
        contacts = _extract_contact_details(normalized_text)
        return contacts
    return _merge_contact_details(snippets)


def _extract_contact_details(text: str) -> str | None:
    email_pattern = re.compile(r"\b[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[A-Za-z]{2,}\b")
    phone_pattern = re.compile(r"(?:(?:\+?91[-\s]?)?(?:\(?0?\d{2,5}\)?[-\s]?)?\d[\d\-\s]{6,14}\d)")

    lines = [line.strip() for line in text.splitlines() if line and line.strip()]
    emails = []
    seen_emails: set[str] = set()
    for line in lines or [text]:
        if "@" not in line and "email" not in line.lower():
            continue
        for email in email_pattern.findall(line):
            lowered = email.lower()
            if lowered not in seen_emails:
                seen_emails.add(lowered)
                emails.append(email)

    phones = []
    seen_phones: set[str] = set()
    phone_keywords = ("phone", "tel", "telephone", "mobile", "mob", "contact", "ph.")
    for line in lines:
        lowered_line = line.lower()
        if not any(keyword in lowered_line for keyword in phone_keywords):
            continue
        for match in phone_pattern.findall(line):
            candidate = " ".join(str(match).split())
            digits_only = re.sub(r"\D", "", candidate)
            if len(digits_only) < 8 or len(digits_only) > 13:
                continue
            if re.fullmatch(r"\d{1,2}[-/]\d{1,2}[-/]\d{4}", candidate):
                continue
            number_groups = re.findall(r"\d+", candidate)
            if len(number_groups) >= 5:
                continue
            if "acs" in lowered_line or "cin" in lowered_line:
                continue
            if digits_only in seen_phones:
                continue
            seen_phones.add(digits_only)
            phones.append(candidate)

    parts: list[str] = []
    if emails:
        parts.append("Email: " + ", ".join(emails[:2]))
    if phones:
        parts.append("Phone: " + ", ".join(phones[:2]))
    if not parts:
        return None
    return " | ".join(parts)


def _merge_contact_details(values: list[str]) -> str | None:
    emails: list[str] = []
    phones: list[str] = []
    seen_email: set[str] = set()
    seen_phone: set[str] = set()
    for value in values:
        if not value:
            continue
        for part in value.split("|"):
            part = part.strip()
            if part.lower().startswith("email:"):
                for email in [item.strip() for item in part.split(":", 1)[1].split(",") if item.strip()]:
                    lowered = email.lower()
                    if lowered not in seen_email:
                        seen_email.add(lowered)
                        emails.append(email)
            elif part.lower().startswith("phone:"):
                for phone in [item.strip() for item in part.split(":", 1)[1].split(",") if item.strip()]:
                    digits_only = re.sub(r"\D", "", phone)
                    if digits_only not in seen_phone:
                        seen_phone.add(digits_only)
                        phones.append(phone)
    parts: list[str] = []
    if emails:
        parts.append("Email: " + ", ".join(emails[:2]))
    if phones:
        parts.append("Phone: " + ", ".join(phones[:2]))
    if not parts:
        return None
    return " | ".join(parts)


def _extract_company_secretary_from_text(text: str) -> tuple[str | None, str | None]:
    normalized_text = text.replace("\r", "\n")
    lines = [
        " ".join(line.split())
        for line in normalized_text.splitlines()
        if line and line.strip()
    ]
    windows = lines[:]
    windows.extend(
        f"{lines[index]} {lines[index + 1]}"
        for index in range(len(lines) - 1)
    )

    title_patterns = [
        re.compile(r"(?i)\bcompany secretary(?:\s*&\s*compliance officer)?\b"),
        re.compile(r"(?i)\bcompliance officer\b"),
    ]

    for window in windows:
        if "secretary" not in window.lower() and "compliance officer" not in window.lower():
            continue
        candidate = _extract_company_secretary_candidate(window, title_patterns=title_patterns)
        if candidate:
            return candidate, "Matched title-context candidate"

    acs_patterns = [
        r"(?i)\b(?:Mr\.?|Mrs\.?|Ms\.?|Shri|Smt\.?)?\s*([A-Z][A-Za-z\.']*(?:\s+[A-Z][A-Za-z\.']*){1,4})\s*\(ACS[-\s]*\d+",
        r"(?i)\b([A-Z][A-Za-z\.']*(?:\s+[A-Z][A-Za-z\.']*){1,4})\s+ACS[-\s]*\d+",
    ]
    for pattern in acs_patterns:
        for match in re.finditer(pattern, normalized_text):
            cleaned = _clean_person_name(match.group(1))
            if cleaned:
                return cleaned, f"Matched ACS candidate: {pattern}"
    return None, None


def _clean_person_name(value: str | None) -> str | None:
    if not value:
        return None
    cleaned = " ".join(str(value).replace("\n", " ").split())
    cleaned = re.sub(r"(?i)^appointment of\s+", "", cleaned)
    cleaned = re.sub(r"(?i)^x\s+", "", cleaned)
    cleaned = re.sub(r"\b(Mr|Mrs|Ms|Shri|Sri|Smt)\.?\s*", "", cleaned, flags=re.I).strip(" ,:-")
    cleaned = re.sub(r"\(.*?\)", "", cleaned).strip(" ,:-")
    cleaned = re.sub(r"\s+", " ", cleaned)
    if not cleaned:
        return None
    blocked_tokens = {
        "above",
        "a",
        "as",
        "also",
        "and",
        "appointed",
        "authorization",
        "bankers",
        "board",
        "cfo",
        "chartered",
        "chemicals",
        "chief",
        "cin",
        "cs",
        "company",
        "compliance",
        "cum",
        "corporate",
        "director",
        "encl",
        "energy",
        "e",
        "executive",
        "financial",
        "for",
        "governance",
        "group",
        "has",
        "independent",
        "industries",
        "infrastructure",
        "limited",
        "m",
        "managing",
        "may",
        "members",
        "membership",
        "mp",
        "no",
        "obtained",
        "october",
        "of",
        "secretary",
        "officer",
        "peer",
        "place",
        "plc",
        "please",
        "practicing",
        "practising",
        "president",
        "qualified",
        "relationship",
        "registered",
        "report",
        "resigned",
        "reviewed",
        "sales",
        "sector",
        "shall",
        "solicitors",
        "stakeholders",
        "report",
        "overview",
        "sr",
        "statutory",
        "such",
        "take",
        "the",
        "to",
        "vice",
        "w",
        "wef",
        "who",
        "write",
    }
    words = [word for word in cleaned.split() if word]
    if len(words) < 2 or len(words) > 6:
        return None
    if any(word.lower() in blocked_tokens for word in words):
        return None
    if any(any(char.isdigit() for char in word) for word in words):
        return None
    normalized_words: list[str] = []
    for word in words:
        if len(word) == 1 and word.isalpha():
            normalized_words.append(word.upper())
        elif word.isupper() or word.islower() or (
            sum(1 for char in word if char.isupper()) > 1
            and sum(1 for char in word if char.islower()) > 1
        ):
            normalized_words.append(word.capitalize())
        else:
            normalized_words.append(word)
    return " ".join(normalized_words)


def _extract_company_secretary_candidate(
    text: str,
    *,
    title_patterns: list[re.Pattern[str]],
) -> str | None:
    for pattern in title_patterns:
        for match in pattern.finditer(text):
            before = text[: match.start()].strip(" ,:-")
            after = text[match.end() :].strip(" ,:-")
            before_candidate = _extract_name_from_segment(before, from_end=True)
            if before_candidate:
                return before_candidate
            after_candidate = _extract_name_from_segment(after, from_end=False)
            if after_candidate:
                return after_candidate
    return None


def _extract_name_from_segment(segment: str, *, from_end: bool) -> str | None:
    if not segment:
        return None
    tokens = re.findall(r"[A-Za-z][A-Za-z\.']*", segment)
    if not tokens:
        return None

    blocked_tokens = {
        "above",
        "a",
        "accountant",
        "accomplished",
        "as",
        "also",
        "and",
        "appointed",
        "authorization",
        "bankers",
        "board",
        "cfo",
        "chartered",
        "chemicals",
        "chief",
        "cin",
        "co",
        "company",
        "corporate",
        "cum",
        "director",
        "encl",
        "energy",
        "e",
        "executive",
        "financial",
        "for",
        "governance",
        "has",
        "independent",
        "industries",
        "infrastructure",
        "limited",
        "managing",
        "may",
        "members",
        "membership",
        "no",
        "obtained",
        "office",
        "october",
        "peer",
        "place",
        "plc",
        "please",
        "practicing",
        "practising",
        "president",
        "part",
        "qualified",
        "registered",
        "report",
        "resigned",
        "reviewed",
        "sales",
        "secretary",
        "sector",
        "shall",
        "solicitors",
        "statutory",
        "such",
        "the",
        "to",
        "vice",
        "w",
        "wef",
        "who",
        "write",
    }
    honorifics = {"mr", "mrs", "ms", "shri", "sri", "smt"}

    def is_name_token(token: str) -> bool:
        lowered = token.strip(".").lower()
        if lowered in blocked_tokens:
            return False
        return bool(re.fullmatch(r"[A-Za-z][A-Za-z\.']*", token))

    iterable = reversed(tokens) if from_end else iter(tokens)
    collected: list[str] = []
    started = False
    for token in iterable:
        lowered = token.strip(".").lower()
        if lowered in honorifics:
            if started and len(collected) < 5:
                collected.append(token)
            continue
        if is_name_token(token):
            collected.append(token)
            started = True
            if len(collected) >= 5:
                break
            continue
        if started:
            break

    if not collected:
        return None

    ordered = list(reversed(collected)) if from_end else collected
    candidate = _clean_person_name(" ".join(ordered))
    if not candidate:
        return None
    if len(candidate.split()) < 2:
        return None
    return candidate


def _build_simulation_selection_for_companies(
    *,
    companies_frame: pd.DataFrame,
    actual_ratings_frame: pd.DataFrame,
    source_root: Path,
    model_base_dir: Path,
    simulation_output_dir: Path,
) -> pd.DataFrame:
    companies_frame = _normalize_merge_keys(companies_frame, ["company_id", "company_name"])
    actual_ratings_frame = _normalize_merge_keys(actual_ratings_frame, ["company_id", "company_name"])

    simulation_outputs = simulate_unrated_companies(
        latest_financial_features_path=source_root / "simulation_model/financials/latest_financial_features.csv",
        financial_history_path=source_root / "simulation_model/financials/financial_year_features.csv",
        rating_events_path=model_base_dir / "rationales/rating_events.csv",
        model_dir=model_base_dir / "models/models",
        output_dir=simulation_output_dir,
        training_dataset_path=model_base_dir / "training/agency_training_dataset.csv",
        training_exclusions_path=model_base_dir / "training/agency_training_exclusions.csv",
    )
    simulation_results = pd.read_csv(simulation_outputs["simulation_results"])
    if simulation_results.empty:
        return pd.DataFrame(
            columns=[
                "company_id",
                "company_name",
                "simulated_rating_agency",
                "simulated_rating",
                "calibrated_range",
                "published_range",
                "range_confidence_label",
                "range_usability_label",
                "ca_review_priority",
                "manual_review_required_flag",
                "manual_review_reason",
            ]
        )

    simulation_results = simulation_results[simulation_results["population_type"] == "simulation"].copy()
    simulation_results = _normalize_merge_keys(simulation_results, ["company_id", "company_name"])

    model_metrics_path = model_base_dir / "models/agency_model_metrics.csv"
    agency_strength = _build_agency_strength_frame(model_metrics_path)
    range_policy = _load_or_build_live_range_policy(
        DEFAULT_RANGE_POLICY_PATH if DEFAULT_RANGE_POLICY_PATH.exists() else None,
        agency_strength,
    )

    eligible_ids = set(companies_frame["company_id"].astype(str).tolist())
    sim_subset = simulation_results[simulation_results["company_id"].astype(str).isin(eligible_ids)].copy()
    if sim_subset.empty:
        return pd.DataFrame(
            columns=[
                "company_id",
                "company_name",
                "simulated_rating_agency",
                "simulated_rating",
                "calibrated_range",
                "published_range",
                "range_confidence_label",
                "range_usability_label",
                "ca_review_priority",
                "manual_review_required_flag",
                "manual_review_reason",
            ]
        )
    actual_subset = actual_ratings_frame.rename(
        columns={
            "latest_cra_rating_status": "actual_rating_available_flag",
            "latest_cra_rating_agency": "actual_rating_agency",
            "latest_cra_rating": "actual_rating",
            "latest_cra_rating_date": "actual_rating_date",
            "latest_cra_rating_medium": "actual_rating_medium",
            "latest_cra_rating_source": "actual_rating_source",
            "latest_cra_rating_source_url": "actual_rating_source_url",
        }
    ).copy()
    actual_subset["actual_rating_available_flag"] = actual_subset["actual_rating_available_flag"].eq("Rated")
    actual_subset["actual_rating_agency_key"] = actual_subset["actual_rating_agency"].fillna("").astype(str).str.lower().str.replace(" ", "_")
    actual_subset["actual_normalized_rating"] = actual_subset["actual_rating"]
    actual_subset["actual_rating_rank"] = pd.to_numeric(actual_subset.get("actual_rating_rank"), errors="coerce")

    agency_ranges = _build_agency_range_frame(
        companies_frame=companies_frame,
        actual_ratings_frame=actual_subset,
        simulation_frame=sim_subset,
        range_policy_frame=range_policy,
        agency_strength_frame=agency_strength,
    )
    return _build_company_range_benchmark(agency_ranges)


def _build_final_master_frame(
    *,
    companies_frame: pd.DataFrame,
    ratings_latest_frame: pd.DataFrame,
    company_secretaries_frame: pd.DataFrame,
    simulation_selection_frame: pd.DataFrame,
    company_excels_dir: Path,
) -> pd.DataFrame:
    companies_frame = _normalize_merge_keys(companies_frame, ["company_id", "company_name"])
    ratings_latest_frame = _normalize_merge_keys(ratings_latest_frame, ["company_id", "company_name"])
    company_secretaries_frame = _normalize_merge_keys(company_secretaries_frame, ["company_id", "company_name"])
    simulation_selection_frame = _normalize_merge_keys(simulation_selection_frame, ["company_id", "company_name"])

    merged = companies_frame.merge(ratings_latest_frame, on=["company_id", "company_name"], how="left")
    merged = merged.merge(company_secretaries_frame, on=["company_id", "company_name"], how="left")
    merged = merged.merge(
        simulation_selection_frame[
            [
                "company_id",
                "simulated_rating_agency",
                "simulated_rating",
                "calibrated_range",
                "published_range",
                "range_confidence_label",
                "range_usability_label",
                "ca_review_priority",
                "manual_review_required_flag",
                "manual_review_reason",
            ]
        ],
        on="company_id",
        how="left",
    )

    merged["latest_cra_rating_status"] = merged["latest_cra_rating_status"].fillna("Not Rated")
    merged["simulation_required_flag"] = merged["latest_cra_rating_status"].eq("Not Rated")
    rated_mask = ~merged["simulation_required_flag"]
    for column in [
        "simulated_rating_agency",
        "simulated_rating",
        "calibrated_range",
        "published_range",
        "range_confidence_label",
        "range_usability_label",
        "ca_review_priority",
        "manual_review_required_flag",
        "manual_review_reason",
    ]:
        merged.loc[rated_mask, column] = None

    merged["company_workbook_path"] = merged["local_file_path"].apply(
        lambda value: str(company_excels_dir / Path(str(value)).name) if value and not pd.isna(value) else None
    )

    final_columns = [
        "company_id",
        "company_name",
        "nse_code",
        "bse_code",
        "industry_group",
        "sub_industry",
        "screener_url",
        "company_workbook_path",
        "period",
        "revenue_crore",
        "net_profit",
        "ebitda_margin_pct",
        "pat_margin_pct",
        "debt_to_equity",
        "interest_coverage",
        "working_capital_days",
        "receivables_days",
        "inventory_days",
        "networth_crore",
        "total_borrowings_crore",
        "total_assets_crore",
        "current_price",
        "market_cap_crore",
        "revenue_growth_pct",
        "profit_growth_pct",
        "latest_cra_rating_status",
        "latest_cra_rating_agency",
        "latest_cra_rating",
        "latest_cra_rating_date",
        "latest_cra_rating_month_year",
        "latest_cra_rating_medium",
        "latest_cra_rating_source",
        "latest_cra_rating_source_url",
        "cra_history_count",
        "company_secretary_name",
        "company_secretary_contact_details",
        "company_secretary_source_type",
        "company_secretary_source_url",
        "company_secretary_notes",
        "annual_report_url",
        "annual_report_label",
        "simulation_required_flag",
        "simulated_rating_agency",
        "simulated_rating",
        "calibrated_range",
        "published_range",
        "range_confidence_label",
        "range_usability_label",
        "ca_review_priority",
        "manual_review_required_flag",
        "manual_review_reason",
    ]
    existing_columns = [column for column in final_columns if column in merged.columns]
    final_frame = merged[existing_columns].sort_values(["sub_industry", "revenue_crore", "company_name"], ascending=[True, False, True])
    return final_frame


def _write_filtered_financial_tables(
    *,
    eligible_company_ids: set[str],
    source_root: Path,
    output_dir: Path,
) -> dict[str, Path]:
    outputs: dict[str, Path] = {}
    file_names = [
        "financial_summary.csv",
        "latest_financial_features.csv",
        "financial_year_features.csv",
        "profit_loss_annual.csv",
        "balance_sheet_annual.csv",
        "cash_flow_annual.csv",
    ]
    for file_name in file_names:
        source_path = source_root / "simulation_model/financials" / file_name
        frame = pd.read_csv(source_path)
        frame["company_id"] = frame["company_id"].fillna("").astype(str)
        filtered = frame[frame["company_id"].isin(eligible_company_ids)].copy()
        output_path = output_dir / file_name
        filtered.to_csv(output_path, index=False)
        outputs[file_name.replace(".csv", "")] = output_path
    return outputs


def _write_consolidated_workbook(
    *,
    master_frame: pd.DataFrame,
    ratings_history_frame: pd.DataFrame,
    company_secretaries_frame: pd.DataFrame,
    output_path: Path,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        master_frame.to_excel(writer, sheet_name="eligible_companies", index=False)
        ratings_history_frame.to_excel(writer, sheet_name="cra_rating_history", index=False)
        company_secretaries_frame.to_excel(writer, sheet_name="company_secretaries", index=False)


def _month_year(value: Any) -> str | None:
    if value is None or pd.isna(value):
        return None
    parsed = pd.to_datetime(value, errors="coerce")
    if parsed is None or pd.isna(parsed):
        return None
    return pd.Timestamp(parsed).strftime("%b %Y")
