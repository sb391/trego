from __future__ import annotations

import logging
import shutil
from pathlib import Path
from typing import Any

import pandas as pd

from ..config import AppConfig
from ..io_utils import ensure_runtime_directories, sanitize_filename
from ..workflow import run_phase_three_credit_ratings, run_phase_two_downloads
from .agri_listed_export import run_industry_listed_export
from .industry_export import ScreenerIndustryExportBrowser, bootstrap_download_status_from_input_csv
from .simulation_pipeline import build_industry_financial_dataset


LOGGER = logging.getLogger(__name__)

DEFAULT_SIMULATION_MODEL_BASE_DIR = Path("outputs/agri_food_other_products/simulation_model")
DEFAULT_MULTI_OUTPUT_DIR = Path("outputs")
DEFAULT_COMBINED_OUTPUT_DIR = Path("outputs/multi_industry_listed_250cr_profitable")
GLOBAL_STORAGE_STATE_PATH = Path("data/state/playwright_storage_state.json")

INDUSTRY_PACKAGE_PRESETS: dict[str, dict[str, str]] = {
    "animal_feed": {
        "industry_name": "Animal Feed",
        "industry_url": "https://www.screener.in/market/IN04/IN0401/IN040104/IN040104001/",
    },
    "pesticides_agrochemicals": {
        "industry_name": "Pesticides & Agrochemicals",
        "industry_url": "https://www.screener.in/market/IN01/IN0101/IN010102/IN010102002/",
    },
    "other_food_products": {
        "industry_name": "Other Food Products",
        "industry_url": "https://www.screener.in/market/IN04/IN0401/IN040104/IN040104003/",
    },
    "fertilizers": {
        "industry_name": "Fertilizers",
        "industry_url": "https://www.screener.in/market/IN01/IN0101/IN010102/IN010102001/",
    },
}


def build_industry_package_root(*, base_output_dir: Path, industry_name: str) -> Path:
    slug = sanitize_filename(industry_name).lower()
    return base_output_dir / f"{slug}_listed_250cr_profitable"


def run_industry_screening_package(
    *,
    industry_name: str,
    industry_url: str,
    output_dir: Path,
    model_base_dir: Path = DEFAULT_SIMULATION_MODEL_BASE_DIR,
    interactive_login: bool = False,
    force_export: bool = False,
    force_downloads: bool = False,
    force_ratings: bool = False,
    force_cs: bool = False,
    headless: bool = True,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    source_root = output_dir / "source_pipeline"
    source_root.mkdir(parents=True, exist_ok=True)

    config = AppConfig(
        headless=headless,
        data_dir=source_root / "runtime_data",
        outputs_dir=source_root,
    )
    ensure_runtime_directories(config)
    _seed_storage_state(config.storage_state_path)

    industry_slug = sanitize_filename(industry_name).lower()
    industry_csv_path = source_root / f"{industry_slug}.csv"

    with ScreenerIndustryExportBrowser(
        config,
        storage_state_path=config.storage_state_path,
        interactive_login=interactive_login,
    ) as browser:
        browser.export_industry_csv(
            industry_url=industry_url,
            output_path=industry_csv_path,
            force=force_export,
        )

    if not config.download_status_path.exists() or force_export:
        bootstrap_rows = bootstrap_download_status_from_input_csv(
            input_path=industry_csv_path,
            output_path=config.download_status_path,
        )
    else:
        bootstrap_rows = 0

    download_summary = run_phase_two_downloads(
        config=config,
        limit=None,
        resume=True,
        force=force_downloads,
        interactive_login=interactive_login,
    )

    credit_rating_summary = run_phase_three_credit_ratings(
        input_path=industry_csv_path,
        config=config,
        limit=None,
        resume=(
            config.credit_rating_history_path.exists()
            and config.credit_rating_status_path.exists()
            and not force_ratings
        ),
        force=force_ratings,
    )

    financial_outputs = build_industry_financial_dataset(
        input_csv_path=industry_csv_path,
        download_status_path=config.download_status_path,
        output_dir=source_root / "simulation_model" / "financials",
    )

    package_outputs = run_industry_listed_export(
        source_root=source_root,
        model_base_dir=model_base_dir,
        output_dir=output_dir,
        report_stem=industry_slug,
        force_ratings=force_ratings,
        force_cs=force_cs,
    )

    return {
        "industry_name": industry_name,
        "industry_url": industry_url,
        "output_dir": output_dir,
        "source_root": source_root,
        "industry_csv_path": industry_csv_path,
        "bootstrapped_download_rows": bootstrap_rows,
        "download_summary": download_summary,
        "credit_rating_summary": credit_rating_summary,
        "financial_outputs": financial_outputs,
        "package_outputs": package_outputs,
    }


def run_preset_industry_screening_packages(
    *,
    industry_keys: list[str],
    base_output_dir: Path = DEFAULT_MULTI_OUTPUT_DIR,
    model_base_dir: Path = DEFAULT_SIMULATION_MODEL_BASE_DIR,
    interactive_login: bool = False,
    force_export: bool = False,
    force_downloads: bool = False,
    force_ratings: bool = False,
    force_cs: bool = False,
    headless: bool = True,
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for industry_key in industry_keys:
        preset = INDUSTRY_PACKAGE_PRESETS[industry_key]
        industry_name = preset["industry_name"]
        industry_url = preset["industry_url"]
        package_root = build_industry_package_root(
            base_output_dir=base_output_dir,
            industry_name=industry_name,
        )
        LOGGER.info("Running screening package for %s", industry_name)
        results.append(
            run_industry_screening_package(
                industry_name=industry_name,
                industry_url=industry_url,
                output_dir=package_root,
                model_base_dir=model_base_dir,
                interactive_login=interactive_login,
                force_export=force_export,
                force_downloads=force_downloads,
                force_ratings=force_ratings,
                force_cs=force_cs,
                headless=headless,
            )
        )
    return results


def build_combined_industry_underwriting_report(
    *,
    industry_keys: list[str],
    base_output_dir: Path = DEFAULT_MULTI_OUTPUT_DIR,
    output_dir: Path = DEFAULT_COMBINED_OUTPUT_DIR,
) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    reports_dir = output_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    eligible_frames: list[pd.DataFrame] = []
    rating_history_frames: list[pd.DataFrame] = []
    secretary_frames: list[pd.DataFrame] = []
    financial_summary_frames: list[pd.DataFrame] = []
    latest_feature_frames: list[pd.DataFrame] = []
    financial_year_frames: list[pd.DataFrame] = []
    profit_loss_frames: list[pd.DataFrame] = []
    balance_sheet_frames: list[pd.DataFrame] = []
    cash_flow_frames: list[pd.DataFrame] = []

    for industry_key in industry_keys:
        preset = INDUSTRY_PACKAGE_PRESETS[industry_key]
        industry_name = preset["industry_name"]
        package_root = build_industry_package_root(
            base_output_dir=base_output_dir,
            industry_name=industry_name,
        )
        reports_root = package_root / "reports"

        eligible_frames.append(
            _annotate_with_industry(
                _read_csv_if_exists(reports_root / "eligible_companies_master.csv"),
                industry_key=industry_key,
                industry_name=industry_name,
            )
        )
        rating_history_frames.append(
            _annotate_with_industry(
                _read_csv_if_exists(reports_root / "cra_rating_history.csv"),
                industry_key=industry_key,
                industry_name=industry_name,
            )
        )
        secretary_frames.append(
            _annotate_with_industry(
                _read_csv_if_exists(reports_root / "company_secretary_details.csv"),
                industry_key=industry_key,
                industry_name=industry_name,
            )
        )
        financial_summary_frames.append(
            _annotate_with_industry(
                _read_csv_if_exists(reports_root / "financial_summary.csv"),
                industry_key=industry_key,
                industry_name=industry_name,
            )
        )
        latest_feature_frames.append(
            _annotate_with_industry(
                _read_csv_if_exists(reports_root / "latest_financial_features.csv"),
                industry_key=industry_key,
                industry_name=industry_name,
            )
        )
        financial_year_frames.append(
            _annotate_with_industry(
                _read_csv_if_exists(reports_root / "financial_year_features.csv"),
                industry_key=industry_key,
                industry_name=industry_name,
            )
        )
        profit_loss_frames.append(
            _annotate_with_industry(
                _read_csv_if_exists(reports_root / "profit_loss_annual.csv"),
                industry_key=industry_key,
                industry_name=industry_name,
            )
        )
        balance_sheet_frames.append(
            _annotate_with_industry(
                _read_csv_if_exists(reports_root / "balance_sheet_annual.csv"),
                industry_key=industry_key,
                industry_name=industry_name,
            )
        )
        cash_flow_frames.append(
            _annotate_with_industry(
                _read_csv_if_exists(reports_root / "cash_flow_annual.csv"),
                industry_key=industry_key,
                industry_name=industry_name,
            )
        )

    eligible_companies = _combine_frames(eligible_frames)
    rating_history = _combine_frames(rating_history_frames)
    company_secretaries = _combine_frames(secretary_frames)
    financial_summary = _combine_frames(financial_summary_frames)
    latest_financial_features = _combine_frames(latest_feature_frames)
    financial_year_features = _combine_frames(financial_year_frames)
    profit_loss_annual = _combine_frames(profit_loss_frames)
    balance_sheet_annual = _combine_frames(balance_sheet_frames)
    cash_flow_annual = _combine_frames(cash_flow_frames)

    industry_summary = _build_industry_summary(eligible_companies)

    combined_csv = reports_dir / "combined_eligible_companies_master.csv"
    eligible_companies.to_csv(combined_csv, index=False)

    single_sheet_workbook = reports_dir / "combined_industry_underwriting_single_sheet.xlsx"
    with pd.ExcelWriter(single_sheet_workbook, engine="openpyxl") as writer:
        eligible_companies.to_excel(writer, sheet_name="underwriting_view", index=False)

    master_workbook = reports_dir / "combined_industry_underwriting_master.xlsx"
    with pd.ExcelWriter(master_workbook, engine="openpyxl") as writer:
        industry_summary.to_excel(writer, sheet_name="industry_summary", index=False)
        eligible_companies.to_excel(writer, sheet_name="underwriting_view", index=False)
        rating_history.to_excel(writer, sheet_name="rating_history", index=False)
        company_secretaries.to_excel(writer, sheet_name="company_secretaries", index=False)
        financial_summary.to_excel(writer, sheet_name="financial_summary", index=False)
        latest_financial_features.to_excel(writer, sheet_name="latest_features", index=False)
        financial_year_features.to_excel(writer, sheet_name="financial_years", index=False)
        profit_loss_annual.to_excel(writer, sheet_name="profit_loss", index=False)
        balance_sheet_annual.to_excel(writer, sheet_name="balance_sheet", index=False)
        cash_flow_annual.to_excel(writer, sheet_name="cash_flow", index=False)

    industry_summary_csv = reports_dir / "industry_summary.csv"
    industry_summary.to_csv(industry_summary_csv, index=False)

    return {
        "combined_eligible_companies_csv": combined_csv,
        "combined_single_sheet_workbook": single_sheet_workbook,
        "combined_master_workbook": master_workbook,
        "industry_summary_csv": industry_summary_csv,
    }


def _seed_storage_state(target_path: Path) -> None:
    if not GLOBAL_STORAGE_STATE_PATH.exists():
        LOGGER.warning("Global Playwright storage state was not found at %s", GLOBAL_STORAGE_STATE_PATH)
        return
    target_path.parent.mkdir(parents=True, exist_ok=True)
    if not target_path.exists():
        shutil.copy2(GLOBAL_STORAGE_STATE_PATH, target_path)
        return
    if GLOBAL_STORAGE_STATE_PATH.stat().st_mtime > target_path.stat().st_mtime:
        shutil.copy2(GLOBAL_STORAGE_STATE_PATH, target_path)


def _read_csv_if_exists(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path)


def _annotate_with_industry(frame: pd.DataFrame, *, industry_key: str, industry_name: str) -> pd.DataFrame:
    if frame.empty:
        return frame
    annotated = frame.copy()
    annotated.insert(0, "industry_key", industry_key)
    annotated.insert(1, "industry_name", industry_name)
    return annotated


def _combine_frames(frames: list[pd.DataFrame]) -> pd.DataFrame:
    non_empty = [frame for frame in frames if not frame.empty]
    if not non_empty:
        return pd.DataFrame()
    return pd.concat(non_empty, ignore_index=True, sort=False)


def _build_industry_summary(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame(
            columns=[
                "industry_name",
                "companies",
                "rated",
                "not_rated",
                "simulation_required",
                "manual_review_required",
                "cs_found",
                "cs_contact_found",
            ]
        )

    working = frame.copy()
    rated_mask = working.get("latest_cra_rating_status", pd.Series(dtype="object")).fillna("").eq("Rated")
    not_rated_mask = working.get("latest_cra_rating_status", pd.Series(dtype="object")).fillna("").eq("Not Rated")
    simulation_mask = working.get("simulation_required_flag", pd.Series(dtype="object")).fillna(False).astype(bool)
    manual_mask = working.get("manual_review_required_flag", pd.Series(dtype="object")).fillna(False).astype(bool)
    cs_mask = working.get("company_secretary_name", pd.Series(dtype="object")).notna()
    cs_contact_mask = working.get("company_secretary_contact_details", pd.Series(dtype="object")).notna()

    working = working.assign(
        _rated=rated_mask,
        _not_rated=not_rated_mask,
        _simulation_required=simulation_mask,
        _manual_review=manual_mask,
        _cs_found=cs_mask,
        _cs_contact_found=cs_contact_mask,
    )

    summary = (
        working.groupby(["industry_key", "industry_name"], dropna=False)
        .agg(
            companies=("company_id", "count"),
            rated=("_rated", "sum"),
            not_rated=("_not_rated", "sum"),
            simulation_required=("_simulation_required", "sum"),
            manual_review_required=("_manual_review", "sum"),
            cs_found=("_cs_found", "sum"),
            cs_contact_found=("_cs_contact_found", "sum"),
        )
        .reset_index()
        .sort_values(["industry_name"])
    )

    totals = pd.DataFrame(
        [
            {
                "industry_key": "all",
                "industry_name": "All Industries",
                "companies": int(summary["companies"].sum()),
                "rated": int(summary["rated"].sum()),
                "not_rated": int(summary["not_rated"].sum()),
                "simulation_required": int(summary["simulation_required"].sum()),
                "manual_review_required": int(summary["manual_review_required"].sum()),
                "cs_found": int(summary["cs_found"].sum()),
                "cs_contact_found": int(summary["cs_contact_found"].sum()),
            }
        ]
    )
    return pd.concat([summary, totals], ignore_index=True)
