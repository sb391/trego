from __future__ import annotations

import logging
import shutil
from pathlib import Path
from typing import Any

import pandas as pd

from ..config import AppConfig
from ..io_utils import ensure_runtime_directories
from ..workflow import run_phase_three_credit_ratings, run_phase_two_downloads
from .context_ingestion import normalize_context_frame
from .industry_export import (
    DEFAULT_AGRI_INDUSTRY_URL,
    ScreenerIndustryExportBrowser,
    bootstrap_download_status_from_input_csv,
)
from .public_intelligence import build_public_intelligence_dataset
from .simulation_pipeline import (
    build_industry_financial_dataset,
    build_rating_training_dataset,
    build_rationale_corpus_from_credit_history,
    simulate_unrated_companies,
    train_agency_specific_models,
)
from .simulation_rationale import build_simulation_rationale_reports


LOGGER = logging.getLogger(__name__)


def run_industry_credit_model_pipeline(
    *,
    app_config: AppConfig,
    industry_url: str = DEFAULT_AGRI_INDUSTRY_URL,
    industry_csv_path: Path,
    resume: bool = False,
    interactive_login: bool = False,
    force_export: bool = False,
    force_rationales: bool = False,
    rationale_agencies: list[str] | None = None,
    merge_existing_rationales: bool = False,
    skip_downloads: bool = False,
    skip_ratings: bool = False,
    context_features_path: Path | None = None,
    build_public_intelligence: bool = False,
) -> dict[str, Any]:
    ensure_runtime_directories(app_config)

    with ScreenerIndustryExportBrowser(
        app_config,
        storage_state_path=app_config.storage_state_path,
        interactive_login=interactive_login,
    ) as browser:
        browser.export_industry_csv(
            industry_url=industry_url,
            output_path=industry_csv_path,
            force=force_export,
        )

    if not resume or not app_config.download_status_path.exists():
        bootstrapped = bootstrap_download_status_from_input_csv(
            input_path=industry_csv_path,
            output_path=app_config.download_status_path,
        )
    else:
        bootstrapped = None

    download_summary = None
    if not skip_downloads:
        download_summary = run_phase_two_downloads(
            config=app_config,
            limit=None,
            resume=resume,
            force=False,
            interactive_login=interactive_login,
        )

    ratings_summary = None
    if not skip_ratings:
        ratings_summary = run_phase_three_credit_ratings(
            input_path=industry_csv_path,
            config=app_config,
            limit=None,
            resume=resume,
            force=False,
        )

    simulation_root = Path(app_config.outputs_dir) / "simulation_model"
    context_dir = simulation_root / "context"
    context_dir.mkdir(parents=True, exist_ok=True)
    canonical_context_path = context_dir / "context_features.csv"
    if context_features_path and context_features_path.exists():
        if context_features_path.resolve() != canonical_context_path.resolve():
            shutil.copy2(context_features_path, canonical_context_path)
    elif not canonical_context_path.exists():
        canonical_context_path = context_dir / "context_features.csv"
    financial_outputs = build_industry_financial_dataset(
        input_csv_path=industry_csv_path,
        download_status_path=app_config.download_status_path,
        output_dir=simulation_root / "financials",
    )
    public_intelligence_outputs = None
    if build_public_intelligence:
        latest_features_frame = pd.read_csv(financial_outputs["latest_financial_features"])
        public_intelligence_outputs = build_public_intelligence_dataset(
            companies_frame=latest_features_frame,
            output_dir=simulation_root / "public_intelligence",
        )
        public_context_frame = pd.read_csv(public_intelligence_outputs["public_intelligence_context"])
        if canonical_context_path.exists():
            existing_context_frame = pd.read_csv(canonical_context_path)
            merged_context_frame = pd.concat([existing_context_frame, public_context_frame], ignore_index=True)
        else:
            merged_context_frame = public_context_frame
        normalize_context_frame(merged_context_frame).to_csv(canonical_context_path, index=False)
    rationale_outputs = build_rationale_corpus_from_credit_history(
        credit_rating_history_path=app_config.credit_rating_history_path,
        output_dir=simulation_root / "rationales",
        request_delay_seconds=1.0,
        force=force_rationales,
        agency_filter=rationale_agencies,
        merge_with_existing=merge_existing_rationales,
    )
    training_outputs = build_rating_training_dataset(
        financial_features_path=financial_outputs["financial_year_features"],
        rating_events_path=rationale_outputs["rating_events"],
        rationale_features_path=rationale_outputs["rationale_features"],
        context_features_path=canonical_context_path,
        output_dir=simulation_root / "training",
    )
    model_outputs = train_agency_specific_models(
        training_dataset_path=training_outputs["agency_training_dataset"],
        output_dir=simulation_root / "models",
    )
    simulation_outputs = simulate_unrated_companies(
        latest_financial_features_path=financial_outputs["latest_financial_features"],
        financial_history_path=financial_outputs["financial_year_features"],
        rating_events_path=rationale_outputs["rating_events"],
        context_features_path=canonical_context_path,
        model_dir=model_outputs["models_dir"],
        output_dir=simulation_root / "simulations",
        training_dataset_path=training_outputs["agency_training_dataset"],
        training_exclusions_path=training_outputs["agency_training_exclusions"],
    )
    rationale_report_outputs = build_simulation_rationale_reports(
        simulation_results_path=simulation_outputs["simulation_results"],
        output_dir=simulation_root / "reports",
    )

    return {
        "industry_csv_path": str(industry_csv_path),
        "bootstrapped_download_rows": bootstrapped,
        "download_summary": download_summary,
        "ratings_summary": ratings_summary,
        "financial_outputs": {key: str(value) for key, value in financial_outputs.items()},
        "public_intelligence_outputs": {key: str(value) for key, value in public_intelligence_outputs.items()} if public_intelligence_outputs else None,
        "rationale_outputs": {key: str(value) for key, value in rationale_outputs.items()},
        "training_outputs": {key: str(value) for key, value in training_outputs.items()},
        "model_outputs": {key: str(value) for key, value in model_outputs.items()},
        "simulation_outputs": {key: str(value) for key, value in simulation_outputs.items()},
        "simulation_report_outputs": {key: str(value) for key, value in rationale_report_outputs.items()},
    }
