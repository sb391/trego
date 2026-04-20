from __future__ import annotations

import argparse
import json
import logging
from datetime import datetime
from pathlib import Path

import pandas as pd

from .config import AppConfig
from .credit_intel.agri_listed_export import run_agri_listed_export
from .credit_intel.context_ingestion import build_context_feature_dataset
from .credit_intel.external_simulation_benchmark import run_external_simulation_benchmark
from .credit_intel.industry_export import DEFAULT_AGRI_INDUSTRY_URL
from .credit_intel.financial_document_parser import parse_financial_document
from .credit_intel.financial_ingestion import build_financial_dataset_from_manifest
from .credit_intel.industry_pipeline import run_industry_credit_model_pipeline
from .credit_intel.industry_screening_package import (
    DEFAULT_COMBINED_OUTPUT_DIR,
    DEFAULT_MULTI_OUTPUT_DIR,
    DEFAULT_SIMULATION_MODEL_BASE_DIR,
    INDUSTRY_PACKAGE_PRESETS,
    build_combined_industry_underwriting_report,
    run_industry_screening_package,
    run_preset_industry_screening_packages,
)
from .credit_intel.model_diagnostics import run_agency_model_diagnostics
from .credit_intel.public_intelligence import build_public_intelligence_dataset
from .credit_intel.simulation_rationale import build_simulation_rationale_reports
from .io_utils import configure_file_logging, ensure_runtime_directories
from .pipelines.parse_rationales import parse_rating_rationales
from .workflow import run_phase_one, run_phase_three_credit_ratings, run_phase_two_downloads


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m src.cli",
        description="Browser automation workflow for Screener company search and Excel export.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser(
        "run",
        help="Phase 1: load input CSV, search Screener, score candidates, and log ambiguous matches.",
    )
    run_parser.add_argument("--input", required=True, help="Path to the input CSV.")
    run_parser.add_argument("--limit", type=int, default=None, help="Optional limit for test runs.")
    run_parser.add_argument("--resume", action="store_true", help="Resume from checkpoint.json.")
    run_parser.add_argument(
        "--review-ambiguous",
        action="store_true",
        help="Reserved for a later phase. Phase 1 still logs ambiguous matches and skips them.",
    )
    run_parser.add_argument(
        "--headless",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Run Chromium headless or headed.",
    )
    run_parser.add_argument(
        "--log-level",
        default="INFO",
        help="Logging level such as INFO or DEBUG.",
    )
    run_parser.set_defaults(func=run_command)

    download_parser = subparsers.add_parser(
        "download",
        help="Phase 2: open matched Screener pages and download Excel workbooks.",
    )
    download_parser.add_argument("--limit", type=int, default=None, help="Optional limit for test runs.")
    download_parser.add_argument("--resume", action="store_true", help="Resume using checkpoint.json.")
    download_parser.add_argument("--force", action="store_true", help="Re-download even if the file already exists.")
    download_parser.add_argument(
        "--headless",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Run Chromium headless or headed.",
    )
    download_parser.add_argument(
        "--interactive-login",
        action="store_true",
        help="Open a headed browser and let a human log in before downloads begin.",
    )
    download_parser.add_argument(
        "--log-level",
        default="INFO",
        help="Logging level such as INFO or DEBUG.",
    )
    download_parser.set_defaults(func=download_command)

    credit_ratings_parser = subparsers.add_parser(
        "credit-ratings",
        help="Phase 3: extract historical credit rating logs from Screener company document links.",
    )
    credit_ratings_parser.add_argument("--input", required=True, help="Path to the input CSV.")
    credit_ratings_parser.add_argument("--limit", type=int, default=None, help="Optional limit for test runs.")
    credit_ratings_parser.add_argument("--resume", action="store_true", help="Resume using credit_ratings_checkpoint.json.")
    credit_ratings_parser.add_argument("--force", action="store_true", help="Reprocess companies even if already checkpointed.")
    credit_ratings_parser.add_argument(
        "--headless",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Run Chromium headless or headed.",
    )
    credit_ratings_parser.add_argument(
        "--log-level",
        default="INFO",
        help="Logging level such as INFO or DEBUG.",
    )
    credit_ratings_parser.set_defaults(func=credit_ratings_command)

    validate_parser = subparsers.add_parser(
        "validate-downloads",
        help="Reserved for Phase 2 workbook validation.",
    )
    validate_parser.set_defaults(func=not_implemented_command)

    retry_parser = subparsers.add_parser(
        "retry-failures",
        help="Reserved for Phase 2 retrying failed workbook downloads.",
    )
    retry_parser.set_defaults(func=not_implemented_command)

    rationale_parser = subparsers.add_parser(
        "parse-rationales",
        help="Step 1: parse local rating-rationale PDFs into structured JSON/CSV outputs.",
    )
    rationale_parser.add_argument(
        "--input-dir",
        default="data/input/rating_rationales",
        help="Directory containing local rationale PDFs.",
    )
    rationale_parser.add_argument(
        "--output-dir",
        default="output",
        help="Directory for parsed JSON, raw text, and flattened CSV files.",
    )
    rationale_parser.add_argument(
        "--log-level",
        default="INFO",
        help="Logging level such as INFO or DEBUG.",
    )
    rationale_parser.set_defaults(func=parse_rationales_command)

    parse_financial_parser = subparsers.add_parser(
        "parse-financial-document",
        help="Parse a local financial document such as a Screener workbook or Probe42 PDF into canonical JSON.",
    )
    parse_financial_parser.add_argument("--input", required=True, help="Path to the local workbook or PDF.")
    parse_financial_parser.add_argument(
        "--provider",
        default=None,
        help="Optional provider override such as screener, probe42, scoreme, or finray.",
    )
    parse_financial_parser.add_argument(
        "--output",
        default="outputs/credit_intel/parsed_financial_document.json",
        help="Path for the canonical parsed JSON output.",
    )
    parse_financial_parser.add_argument(
        "--log-level",
        default="INFO",
        help="Logging level such as INFO or DEBUG.",
    )
    parse_financial_parser.set_defaults(func=parse_financial_document_command)

    financial_dataset_parser = subparsers.add_parser(
        "build-financial-dataset",
        help="Build canonical annual financial tables from a manifest of local Screener/Probe42 files.",
    )
    financial_dataset_parser.add_argument("--manifest", required=True, help="CSV manifest with at least file_path.")
    financial_dataset_parser.add_argument(
        "--output-dir",
        default="outputs/credit_intel/financial_ingestion",
        help="Directory for canonical CSV outputs.",
    )
    financial_dataset_parser.add_argument(
        "--log-level",
        default="INFO",
        help="Logging level such as INFO or DEBUG.",
    )
    financial_dataset_parser.set_defaults(func=build_financial_dataset_command)

    external_benchmark_parser = subparsers.add_parser(
        "benchmark-external-simulation",
        help="Ingest external Excel financials, discover latest online ratings, and compare them with agency-wise simulations.",
    )
    external_benchmark_parser.add_argument(
        "--input",
        nargs="+",
        required=True,
        help="One or more Excel files containing company financial snapshots.",
    )
    external_benchmark_parser.add_argument(
        "--output-dir",
        default="outputs/credit_intel/external_simulation_benchmark",
        help="Directory for parsed financials, simulations, and comparison reports.",
    )
    external_benchmark_parser.add_argument(
        "--model-base-dir",
        default="outputs/agri_food_other_products/simulation_model",
        help="Base directory containing agri model rationales and trained agency simulators.",
    )
    external_benchmark_parser.add_argument(
        "--force-rating-refresh",
        action="store_true",
        help="Ignore cached online rating discovery output and re-run web discovery.",
    )
    external_benchmark_parser.add_argument(
        "--rating-validation-mode",
        choices=["legacy", "cra_first", "cra_only"],
        default="legacy",
        help="How to validate actual ratings: legacy mixed discovery, CRA-first with dataset fallback, or CRA-only.",
    )
    external_benchmark_parser.add_argument(
        "--log-level",
        default="INFO",
        help="Logging level such as INFO or DEBUG.",
    )
    external_benchmark_parser.set_defaults(func=benchmark_external_simulation_command)

    context_dataset_parser = subparsers.add_parser(
        "build-context-dataset",
        help="Normalize optional promoter / bureau / governance / management-plan inputs into canonical context features.",
    )
    context_dataset_parser.add_argument("--input", required=True, help="Path to a CSV, Excel, or JSON context file.")
    context_dataset_parser.add_argument(
        "--output-dir",
        default="outputs/credit_intel/context_features",
        help="Directory for canonical context feature outputs.",
    )
    context_dataset_parser.add_argument(
        "--log-level",
        default="INFO",
        help="Logging level such as INFO or DEBUG.",
    )
    context_dataset_parser.set_defaults(func=build_context_dataset_command)

    public_intelligence_parser = subparsers.add_parser(
        "build-public-intelligence",
        help="Build cached public-risk and industry-outlook context features from company names using web search.",
    )
    public_intelligence_parser.add_argument(
        "--input",
        required=True,
        help="CSV or Excel file with company_name/company_id and optionally sub_industry or industry columns.",
    )
    public_intelligence_parser.add_argument(
        "--output-dir",
        default="outputs/credit_intel/public_intelligence",
        help="Directory for public intelligence context outputs.",
    )
    public_intelligence_parser.add_argument("--limit", type=int, default=None, help="Optional company limit for test runs.")
    public_intelligence_parser.add_argument(
        "--log-level",
        default="INFO",
        help="Logging level such as INFO or DEBUG.",
    )
    public_intelligence_parser.set_defaults(func=build_public_intelligence_command)

    simulation_report_parser = subparsers.add_parser(
        "build-simulation-rationales",
        help="Generate detailed simulation rationale and improvement-action rows from simulation results.",
    )
    simulation_report_parser.add_argument(
        "--simulation-results",
        default="outputs/agri_food_other_products/simulation_model/simulations/simulation_results.csv",
        help="Path to simulation_results.csv.",
    )
    simulation_report_parser.add_argument(
        "--output-dir",
        default="outputs/agri_food_other_products/simulation_model/reports",
        help="Directory for simulation rationale outputs.",
    )
    simulation_report_parser.add_argument(
        "--log-level",
        default="INFO",
        help="Logging level such as INFO or DEBUG.",
    )
    simulation_report_parser.set_defaults(func=build_simulation_rationales_command)

    diagnostics_parser = subparsers.add_parser(
        "model-diagnostics",
        help="Run agency-wise simulation diagnostics and 3-month-lag validation on the agri model outputs.",
    )
    diagnostics_parser.add_argument(
        "--simulation-model-dir",
        default="outputs/agri_food_other_products/simulation_model",
        help="Base directory containing financials, rationales, models, and simulations outputs.",
    )
    diagnostics_parser.add_argument(
        "--output-dir",
        default="outputs/agri_food_other_products/simulation_model/diagnostics",
        help="Directory for diagnostic CSV and markdown outputs.",
    )
    diagnostics_parser.add_argument(
        "--min-days-before-rating",
        type=int,
        default=90,
        help="Minimum lag between matched financial period and rating date for validation.",
    )
    diagnostics_parser.add_argument(
        "--log-level",
        default="INFO",
        help="Logging level such as INFO or DEBUG.",
    )
    diagnostics_parser.set_defaults(func=model_diagnostics_command)

    industry_model_parser = subparsers.add_parser(
        "industry-credit-model",
        help="Export a Screener industry, download company workbooks, extract rating histories, and train agency-specific simulators.",
    )
    industry_model_parser.add_argument(
        "--industry-url",
        default=DEFAULT_AGRI_INDUSTRY_URL,
        help="Screener industry page URL. Defaults to Agricultural Food & other Products Companies.",
    )
    industry_model_parser.add_argument(
        "--industry-csv",
        default="data/input/agricultural-food-other-products.csv",
        help="Where to save the exported Screener industry CSV.",
    )
    industry_model_parser.add_argument(
        "--data-dir",
        default="data",
        help="Base data directory for downloads, logs, and Playwright storage state.",
    )
    industry_model_parser.add_argument(
        "--outputs-dir",
        default="outputs/agri_food_other_products",
        help="Dedicated outputs directory for this industry run.",
    )
    industry_model_parser.add_argument(
        "--context-features",
        default=None,
        help="Optional canonical context_features.csv to incorporate promoter, governance, and business-plan signals.",
    )
    industry_model_parser.add_argument(
        "--build-public-intelligence",
        action="store_true",
        help="Build cached public-risk and industry-outlook context from backend web discovery and merge it into context features.",
    )
    industry_model_parser.add_argument("--resume", action="store_true", help="Resume downloads and ratings if prior artifacts exist.")
    industry_model_parser.add_argument(
        "--interactive-login",
        action="store_true",
        help="Open a headed browser and capture Screener login before export/downloads.",
    )
    industry_model_parser.add_argument("--skip-downloads", action="store_true", help="Skip workbook download phase.")
    industry_model_parser.add_argument("--skip-ratings", action="store_true", help="Skip Screener rating-history extraction phase.")
    industry_model_parser.add_argument("--force-export", action="store_true", help="Re-export the industry CSV even if it already exists.")
    industry_model_parser.add_argument("--force-rationales", action="store_true", help="Re-fetch and re-parse CRA rationale documents.")
    industry_model_parser.add_argument(
        "--rationale-agencies",
        nargs="+",
        default=None,
        help="Optional subset of CRA agencies to refresh, for example care icra india_ratings brickwork.",
    )
    industry_model_parser.add_argument(
        "--merge-existing-rationales",
        action="store_true",
        help="Merge refreshed rationale rows into the existing corpus instead of replacing the full rationale CSV set.",
    )
    industry_model_parser.add_argument(
        "--headless",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Run Chromium headless or headed.",
    )
    industry_model_parser.add_argument(
        "--log-level",
        default="INFO",
        help="Logging level such as INFO or DEBUG.",
    )
    industry_model_parser.set_defaults(func=industry_credit_model_command)

    agri_listed_parser = subparsers.add_parser(
        "export-agri-listed-screening",
        help="Export listed agri companies with revenue >250 Cr and positive PAT, plus CRA-native ratings, CS details, and unrated simulations.",
    )
    agri_listed_parser.add_argument(
        "--source-root",
        default="outputs/agri_food_other_products",
        help="Source directory containing the agri downloads, credit histories, and financial outputs.",
    )
    agri_listed_parser.add_argument(
        "--model-base-dir",
        default="outputs/agri_food_other_products/simulation_model",
        help="Base directory containing the current agri simulation outputs.",
    )
    agri_listed_parser.add_argument(
        "--output-dir",
        default="outputs/agri_listed_250cr_profitable",
        help="Directory where the filtered company excels and consolidated workbook will be written.",
    )
    agri_listed_parser.add_argument("--force-ratings", action="store_true", help="Re-run CRA-native latest rating discovery.")
    agri_listed_parser.add_argument("--force-cs", action="store_true", help="Re-run Company Secretary extraction.")
    agri_listed_parser.add_argument(
        "--log-level",
        default="INFO",
        help="Logging level such as INFO or DEBUG.",
    )
    agri_listed_parser.set_defaults(func=export_agri_listed_screening_command)

    industry_screening_parser = subparsers.add_parser(
        "export-industry-screening",
        help="Run the full listed-screening package for one Screener industry.",
    )
    industry_screening_parser.add_argument("--industry-name", required=True, help="Industry display name.")
    industry_screening_parser.add_argument("--industry-url", required=True, help="Screener industry page URL.")
    industry_screening_parser.add_argument(
        "--output-dir",
        required=True,
        help="Directory where the industry package will be written.",
    )
    industry_screening_parser.add_argument(
        "--model-base-dir",
        default=str(DEFAULT_SIMULATION_MODEL_BASE_DIR),
        help="Base directory containing the currently approved simulation model artifacts.",
    )
    industry_screening_parser.add_argument(
        "--interactive-login",
        action="store_true",
        help="Open a headed browser and allow manual Screener login before exports/downloads.",
    )
    industry_screening_parser.add_argument(
        "--headless",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Run Chromium headless or headed.",
    )
    industry_screening_parser.add_argument("--force-export", action="store_true", help="Re-export the industry CSV from Screener.")
    industry_screening_parser.add_argument("--force-downloads", action="store_true", help="Re-download company workbooks.")
    industry_screening_parser.add_argument("--force-ratings", action="store_true", help="Re-run CRA native rating discovery for eligible companies.")
    industry_screening_parser.add_argument("--force-cs", action="store_true", help="Re-run Company Secretary extraction.")
    industry_screening_parser.add_argument(
        "--log-level",
        default="INFO",
        help="Logging level such as INFO or DEBUG.",
    )
    industry_screening_parser.set_defaults(func=export_industry_screening_command)

    multi_industry_screening_parser = subparsers.add_parser(
        "export-multi-industry-screening",
        help="Run the full listed-screening package for one or more preset Screener industries.",
    )
    multi_industry_screening_parser.add_argument(
        "--industry",
        action="append",
        choices=sorted(INDUSTRY_PACKAGE_PRESETS.keys()),
        help="Preset industry key. Repeat to target specific presets. Defaults to all supported presets.",
    )
    multi_industry_screening_parser.add_argument(
        "--base-output-dir",
        default=str(DEFAULT_MULTI_OUTPUT_DIR),
        help="Base directory under which per-industry package folders will be created.",
    )
    multi_industry_screening_parser.add_argument(
        "--model-base-dir",
        default=str(DEFAULT_SIMULATION_MODEL_BASE_DIR),
        help="Base directory containing the currently approved simulation model artifacts.",
    )
    multi_industry_screening_parser.add_argument(
        "--interactive-login",
        action="store_true",
        help="Open a headed browser and allow manual Screener login before exports/downloads.",
    )
    multi_industry_screening_parser.add_argument(
        "--headless",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Run Chromium headless or headed.",
    )
    multi_industry_screening_parser.add_argument("--force-export", action="store_true", help="Re-export each industry CSV from Screener.")
    multi_industry_screening_parser.add_argument("--force-downloads", action="store_true", help="Re-download company workbooks.")
    multi_industry_screening_parser.add_argument("--force-ratings", action="store_true", help="Re-run CRA native rating discovery for eligible companies.")
    multi_industry_screening_parser.add_argument("--force-cs", action="store_true", help="Re-run Company Secretary extraction.")
    multi_industry_screening_parser.add_argument(
        "--log-level",
        default="INFO",
        help="Logging level such as INFO or DEBUG.",
    )
    multi_industry_screening_parser.set_defaults(func=export_multi_industry_screening_command)

    combined_industry_parser = subparsers.add_parser(
        "export-combined-industry-underwriting",
        help="Combine completed industry screening packages into one cross-industry underwriting workbook.",
    )
    combined_industry_parser.add_argument(
        "--industry",
        action="append",
        choices=sorted(INDUSTRY_PACKAGE_PRESETS.keys()),
        help="Preset industry key to include. Repeat to target a subset. Defaults to all supported presets.",
    )
    combined_industry_parser.add_argument(
        "--base-output-dir",
        default=str(DEFAULT_MULTI_OUTPUT_DIR),
        help="Base directory where the per-industry package folders already exist.",
    )
    combined_industry_parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_COMBINED_OUTPUT_DIR),
        help="Directory where the combined cross-industry workbook should be written.",
    )
    combined_industry_parser.add_argument(
        "--log-level",
        default="INFO",
        help="Logging level such as INFO or DEBUG.",
    )
    combined_industry_parser.set_defaults(func=export_combined_industry_underwriting_command)

    return parser


def run_command(args: argparse.Namespace) -> int:
    config = AppConfig(headless=args.headless)
    ensure_runtime_directories(config)
    log_name = datetime.now().strftime("phase1_%Y%m%d_%H%M%S.log")
    configure_file_logging(config.logs_dir / log_name, args.log_level)
    if args.review_ambiguous:
        print("Phase 1 note: --review-ambiguous is not interactive yet; ambiguous rows will be logged and skipped.")

    summary = run_phase_one(
        input_path=Path(args.input),
        config=config,
        limit=args.limit,
        resume=args.resume,
    )
    print(summary)
    return 0


def download_command(args: argparse.Namespace) -> int:
    config = AppConfig(headless=args.headless)
    ensure_runtime_directories(config)
    log_name = datetime.now().strftime("phase2_download_%Y%m%d_%H%M%S.log")
    configure_file_logging(config.logs_dir / log_name, args.log_level)

    summary = run_phase_two_downloads(
        config=config,
        limit=args.limit,
        resume=args.resume,
        force=args.force,
        interactive_login=args.interactive_login,
    )
    print(summary)
    print(f"Download directory: {config.downloads_dir.resolve()}")
    sample_path = config.downloads_dir / "Aarey_Drugs__AAREYDRUGS.xlsx"
    print(f"Sample saved path: {sample_path.resolve()}")
    return 0


def credit_ratings_command(args: argparse.Namespace) -> int:
    config = AppConfig(headless=args.headless)
    ensure_runtime_directories(config)
    log_name = datetime.now().strftime("phase3_credit_ratings_%Y%m%d_%H%M%S.log")
    configure_file_logging(config.logs_dir / log_name, args.log_level)

    summary = run_phase_three_credit_ratings(
        input_path=Path(args.input),
        config=config,
        limit=args.limit,
        resume=args.resume,
        force=args.force,
    )
    print(summary)
    csv_path = config.outputs_dir / f"{Path(args.input).stem}_with_credit_ratings.csv"
    xlsx_path = config.outputs_dir / f"{Path(args.input).stem}_with_credit_ratings.xlsx"
    print(f"Credit rating history CSV: {csv_path.resolve()}")
    print(f"Credit rating history workbook: {xlsx_path.resolve()}")
    return 0


def parse_rationales_command(args: argparse.Namespace) -> int:
    logging.basicConfig(level=getattr(logging, str(args.log_level).upper(), logging.INFO))
    summary = parse_rating_rationales(Path(args.input_dir), Path(args.output_dir))
    print(summary)
    return 0


def parse_financial_document_command(args: argparse.Namespace) -> int:
    logging.basicConfig(level=getattr(logging, str(args.log_level).upper(), logging.INFO))
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    parsed = parse_financial_document(Path(args.input), provider_name=args.provider)
    output_path.write_text(json.dumps(parsed, indent=2, default=str), encoding="utf-8")
    print(f"Parsed financial document JSON: {output_path.resolve()}")
    return 0


def build_financial_dataset_command(args: argparse.Namespace) -> int:
    logging.basicConfig(level=getattr(logging, str(args.log_level).upper(), logging.INFO))
    outputs = build_financial_dataset_from_manifest(
        manifest_path=Path(args.manifest),
        output_dir=Path(args.output_dir),
    )
    for label, path in outputs.items():
        print(f"{label}: {path.resolve()}")
    return 0


def benchmark_external_simulation_command(args: argparse.Namespace) -> int:
    logging.basicConfig(level=getattr(logging, str(args.log_level).upper(), logging.INFO))
    outputs = run_external_simulation_benchmark(
        input_paths=[Path(path) for path in args.input],
        output_dir=Path(args.output_dir),
        model_base_dir=Path(args.model_base_dir),
        force_rating_refresh=args.force_rating_refresh,
        rating_validation_mode=args.rating_validation_mode,
    )
    for label, path in outputs.items():
        print(f"{label}: {path.resolve()}")
    return 0


def build_context_dataset_command(args: argparse.Namespace) -> int:
    logging.basicConfig(level=getattr(logging, str(args.log_level).upper(), logging.INFO))
    outputs = build_context_feature_dataset(
        input_path=Path(args.input),
        output_dir=Path(args.output_dir),
    )
    for label, path in outputs.items():
        print(f"{label}: {path.resolve()}")
    return 0


def build_public_intelligence_command(args: argparse.Namespace) -> int:
    logging.basicConfig(level=getattr(logging, str(args.log_level).upper(), logging.INFO))
    input_path = Path(args.input)
    suffix = input_path.suffix.lower()
    if suffix == ".csv":
        companies_frame = pd.read_csv(input_path)
    elif suffix in {".xlsx", ".xls"}:
        companies_frame = pd.read_excel(input_path)
    else:
        raise SystemExit(f"Unsupported input format for public intelligence build: {input_path}")
    outputs = build_public_intelligence_dataset(
        companies_frame=companies_frame,
        output_dir=Path(args.output_dir),
        limit=args.limit,
    )
    for label, path in outputs.items():
        print(f"{label}: {path.resolve()}")
    return 0


def build_simulation_rationales_command(args: argparse.Namespace) -> int:
    logging.basicConfig(level=getattr(logging, str(args.log_level).upper(), logging.INFO))
    outputs = build_simulation_rationale_reports(
        simulation_results_path=Path(args.simulation_results),
        output_dir=Path(args.output_dir),
    )
    for label, path in outputs.items():
        print(f"{label}: {path.resolve()}")
    return 0


def model_diagnostics_command(args: argparse.Namespace) -> int:
    logging.basicConfig(level=getattr(logging, str(args.log_level).upper(), logging.INFO))
    outputs = run_agency_model_diagnostics(
        simulation_model_dir=Path(args.simulation_model_dir),
        output_dir=Path(args.output_dir),
        min_days_before_rating=args.min_days_before_rating,
    )
    for label, path in outputs.items():
        print(f"{label}: {path.resolve()}")
    return 0


def industry_credit_model_command(args: argparse.Namespace) -> int:
    config = AppConfig(
        headless=args.headless,
        data_dir=Path(args.data_dir),
        outputs_dir=Path(args.outputs_dir),
    )
    ensure_runtime_directories(config)
    log_name = datetime.now().strftime("industry_credit_model_%Y%m%d_%H%M%S.log")
    configure_file_logging(config.logs_dir / log_name, args.log_level)

    summary = run_industry_credit_model_pipeline(
        app_config=config,
        industry_url=args.industry_url,
        industry_csv_path=Path(args.industry_csv),
        resume=args.resume,
        interactive_login=args.interactive_login,
        force_export=args.force_export,
        force_rationales=args.force_rationales,
        rationale_agencies=args.rationale_agencies,
        merge_existing_rationales=args.merge_existing_rationales,
        skip_downloads=args.skip_downloads,
        skip_ratings=args.skip_ratings,
        context_features_path=Path(args.context_features) if args.context_features else None,
        build_public_intelligence=args.build_public_intelligence,
    )
    print(summary)
    return 0


def export_agri_listed_screening_command(args: argparse.Namespace) -> int:
    logging.basicConfig(level=getattr(logging, str(args.log_level).upper(), logging.INFO))
    outputs = run_agri_listed_export(
        source_root=Path(args.source_root),
        model_base_dir=Path(args.model_base_dir),
        output_dir=Path(args.output_dir),
        force_ratings=args.force_ratings,
        force_cs=args.force_cs,
    )
    for label, path in outputs.items():
        print(f"{label}: {path.resolve()}")
    return 0


def export_industry_screening_command(args: argparse.Namespace) -> int:
    logging.basicConfig(level=getattr(logging, str(args.log_level).upper(), logging.INFO))
    outputs = run_industry_screening_package(
        industry_name=args.industry_name,
        industry_url=args.industry_url,
        output_dir=Path(args.output_dir),
        model_base_dir=Path(args.model_base_dir),
        interactive_login=args.interactive_login,
        force_export=args.force_export,
        force_downloads=args.force_downloads,
        force_ratings=args.force_ratings,
        force_cs=args.force_cs,
        headless=args.headless,
    )
    printable = {
        "industry_name": outputs["industry_name"],
        "industry_url": outputs["industry_url"],
        "output_dir": str(Path(outputs["output_dir"]).resolve()),
        "industry_csv_path": str(Path(outputs["industry_csv_path"]).resolve()),
        "download_summary": outputs["download_summary"],
        "package_outputs": {label: str(path.resolve()) for label, path in outputs["package_outputs"].items()},
    }
    print(json.dumps(printable, indent=2))
    return 0


def export_multi_industry_screening_command(args: argparse.Namespace) -> int:
    logging.basicConfig(level=getattr(logging, str(args.log_level).upper(), logging.INFO))
    industry_keys = args.industry or list(INDUSTRY_PACKAGE_PRESETS.keys())
    outputs = run_preset_industry_screening_packages(
        industry_keys=industry_keys,
        base_output_dir=Path(args.base_output_dir),
        model_base_dir=Path(args.model_base_dir),
        interactive_login=args.interactive_login,
        force_export=args.force_export,
        force_downloads=args.force_downloads,
        force_ratings=args.force_ratings,
        force_cs=args.force_cs,
        headless=args.headless,
    )
    printable: list[dict[str, object]] = []
    for result in outputs:
        printable.append(
            {
                "industry_name": result["industry_name"],
                "industry_url": result["industry_url"],
                "output_dir": str(Path(result["output_dir"]).resolve()),
                "industry_csv_path": str(Path(result["industry_csv_path"]).resolve()),
                "download_summary": result["download_summary"],
                "package_outputs": {label: str(path.resolve()) for label, path in result["package_outputs"].items()},
            }
        )
    print(json.dumps(printable, indent=2))
    return 0


def export_combined_industry_underwriting_command(args: argparse.Namespace) -> int:
    logging.basicConfig(level=getattr(logging, str(args.log_level).upper(), logging.INFO))
    industry_keys = args.industry or list(INDUSTRY_PACKAGE_PRESETS.keys())
    outputs = build_combined_industry_underwriting_report(
        industry_keys=industry_keys,
        base_output_dir=Path(args.base_output_dir),
        output_dir=Path(args.output_dir),
    )
    printable = {label: str(path.resolve()) for label, path in outputs.items()}
    print(json.dumps(printable, indent=2))
    return 0


def not_implemented_command(args: argparse.Namespace) -> int:  # noqa: ARG001
    raise SystemExit("This command is reserved for a later phase and is not implemented yet.")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
