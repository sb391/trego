from __future__ import annotations

import argparse
import logging
from pathlib import Path

from .company_extraction import (
    build_datasets_from_company_json,
    load_companies_master,
    process_company_target,
    resolve_company_target,
)
from .config import (
    CrawlerSettings,
    DEFAULT_INDUSTRIES_OVERVIEW_URL,
)
from .discovery import discover_companies_from_industry_master
from .http import ScreenerHttpClient, load_robots_policy
from .logging_utils import configure_logging
from .pipelines import discover_industries


logger = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="screener-crawler",
        description="Screener crawler for all-industry discovery, company discovery, and company financial extraction.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    discover = subparsers.add_parser(
        "discover-companies",
        help="Fetch industry company listings from industry_master.csv and build companies_master.csv",
    )
    discover.add_argument(
        "--industry",
        default=None,
        help="Optional industry_slug from industry_master.csv to limit discovery to one industry.",
    )
    discover.add_argument(
        "--industry-master-csv",
        default="data/processed/industry_master.csv",
        help="Path to industry_master.csv produced by discover-industries.",
    )
    discover.add_argument(
        "--raw-html-dir",
        default="data/raw/industries/company_listings",
        help="Directory for raw industry listing HTML snapshots.",
    )
    discover.add_argument(
        "--per-industry-dir",
        default="data/intermediate/companies",
        help="Directory for optional per-industry company CSV files.",
    )
    discover.add_argument(
        "--output-csv",
        default="data/processed/companies_master.csv",
        help="Path for the processed companies master CSV.",
    )
    discover.add_argument(
        "--delay-seconds",
        type=float,
        default=2.0,
        help="Polite delay between HTTP requests.",
    )
    discover.add_argument(
        "--timeout-seconds",
        type=float,
        default=30.0,
        help="HTTP timeout per request.",
    )
    discover.add_argument(
        "--log-level",
        default="INFO",
        help="Logging level, for example INFO or DEBUG.",
    )
    discover.set_defaults(func=run_discover_companies)

    discover_industries_parser = subparsers.add_parser(
        "discover-industries",
        help="Fetch Screener Industries Overview and build industry_master.csv",
    )
    discover_industries_parser.add_argument(
        "--overview-url",
        default=DEFAULT_INDUSTRIES_OVERVIEW_URL,
        help="Industries overview URL. Defaults to Screener Industries Overview.",
    )
    discover_industries_parser.add_argument(
        "--raw-html-path",
        default="data/raw/industries/industries_overview.html",
        help="Path for the industries overview raw HTML snapshot.",
    )
    discover_industries_parser.add_argument(
        "--output-csv",
        default="data/processed/industry_master.csv",
        help="Path for the processed industry master CSV.",
    )
    discover_industries_parser.add_argument(
        "--delay-seconds",
        type=float,
        default=2.0,
        help="Polite delay between HTTP requests.",
    )
    discover_industries_parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=30.0,
        help="HTTP timeout per request.",
    )
    discover_industries_parser.add_argument(
        "--log-level",
        default="INFO",
        help="Logging level, for example INFO or DEBUG.",
    )
    discover_industries_parser.set_defaults(func=run_discover_industries)

    fetch_company = subparsers.add_parser(
        "fetch-company",
        help="Fetch one company page, persist raw HTML/JSON, and rebuild processed datasets.",
    )
    fetch_company.add_argument("identifier", help="Company slug from companies_master.csv or a Screener company URL.")
    add_phase_two_common_args(fetch_company)
    fetch_company.set_defaults(func=run_fetch_company)

    fetch_all = subparsers.add_parser(
        "fetch-all",
        help="Fetch all companies from companies_master.csv and rebuild processed datasets.",
    )
    fetch_all.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional limit for debugging.",
    )
    add_phase_two_common_args(fetch_all)
    fetch_all.set_defaults(func=run_fetch_all)

    build_dataset = subparsers.add_parser(
        "build-dataset",
        help="Build processed CSV datasets from saved company JSON artifacts.",
    )
    build_dataset.add_argument(
        "--json-dir",
        default="data/intermediate/company_json",
        help="Directory containing per-company JSON artifacts.",
    )
    build_dataset.add_argument(
        "--output-dir",
        default="data/processed",
        help="Directory for processed CSV datasets.",
    )
    build_dataset.add_argument(
        "--log-level",
        default="INFO",
        help="Logging level, for example INFO or DEBUG.",
    )
    build_dataset.set_defaults(func=run_build_dataset)

    return parser


def run_discover_companies(args: argparse.Namespace) -> int:
    configure_logging(args.log_level)
    settings = CrawlerSettings(
        delay_seconds=args.delay_seconds,
        timeout_seconds=args.timeout_seconds,
        processed_csv_path=Path(args.output_csv),
    )

    with ScreenerHttpClient(
        user_agent=settings.user_agent,
        timeout_seconds=settings.timeout_seconds,
        delay_seconds=settings.delay_seconds,
        max_retries=settings.max_retries,
    ) as client:
        robots_policy = load_robots_policy(client, DEFAULT_INDUSTRIES_OVERVIEW_URL)
        frame, summary = discover_companies_from_industry_master(
            client,
            robots_policy,
            industry_master_path=Path(args.industry_master_csv),
            output_csv_path=settings.processed_csv_path,
            raw_html_dir=Path(args.raw_html_dir),
            per_industry_dir=Path(args.per_industry_dir) if args.per_industry_dir else None,
            industry_slug=args.industry,
        )

    logger.info(
        "Company discovery summary: industries_targeted=%s industries_processed=%s companies_found=%s industries_with_blocked_pagination=%s",
        summary["industries_targeted"],
        summary["industries_processed"],
        summary["companies_found"],
        summary["industries_with_blocked_pagination"],
    )
    if not frame.empty:
        sample_frame = frame.head(5).fillna("")
        logger.info("Sample 5 companies:\n%s", sample_frame.to_string(index=False))
    return 0


def run_discover_industries(args: argparse.Namespace) -> int:
    configure_logging(args.log_level)
    settings = CrawlerSettings(
        delay_seconds=args.delay_seconds,
        timeout_seconds=args.timeout_seconds,
        industries_raw_html_path=Path(args.raw_html_path),
        industry_master_csv_path=Path(args.output_csv),
    )

    with ScreenerHttpClient(
        user_agent=settings.user_agent,
        timeout_seconds=settings.timeout_seconds,
        delay_seconds=settings.delay_seconds,
        max_retries=settings.max_retries,
    ) as client:
        robots_policy = load_robots_policy(client, args.overview_url)
        parsed, frame = discover_industries(
            client,
            robots_policy,
            overview_url=args.overview_url,
            raw_html_path=settings.industries_raw_html_path,
            output_csv_path=settings.industry_master_csv_path,
        )

    logger.info("Total industries found: %s", len(parsed.industries))
    if parsed.industries:
        sample_frame = frame.head(5).fillna("")
        logger.info("Sample 5 industries:\n%s", sample_frame.to_string(index=False))
    return 0


def add_phase_two_common_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--input-csv",
        default="data/processed/companies_master.csv",
        help="Path to Phase 1 companies master CSV.",
    )
    parser.add_argument(
        "--raw-html-dir",
        default="data/raw/company_pages",
        help="Directory for raw company HTML snapshots.",
    )
    parser.add_argument(
        "--json-dir",
        default="data/intermediate/company_json",
        help="Directory for intermediate company JSON artifacts.",
    )
    parser.add_argument(
        "--output-dir",
        default="data/processed",
        help="Directory for processed section CSVs.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-fetch and overwrite existing company artifacts.",
    )
    parser.add_argument(
        "--delay-seconds",
        type=float,
        default=2.0,
        help="Polite delay between HTTP requests.",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=30.0,
        help="HTTP timeout per request.",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        help="Logging level, for example INFO or DEBUG.",
    )


def run_fetch_company(args: argparse.Namespace) -> int:
    configure_logging(args.log_level)
    target = resolve_company_target(args.identifier, Path(args.input_csv))
    settings = CrawlerSettings(
        delay_seconds=args.delay_seconds,
        timeout_seconds=args.timeout_seconds,
    )

    with ScreenerHttpClient(
        user_agent=settings.user_agent,
        timeout_seconds=settings.timeout_seconds,
        delay_seconds=settings.delay_seconds,
        max_retries=settings.max_retries,
    ) as client:
        robots_policy = load_robots_policy(client, target["company_page_url"])
        result = process_company_target(
            target,
            client=client,
            robots_policy=robots_policy,
            raw_html_dir=Path(args.raw_html_dir),
            json_dir=Path(args.json_dir),
            force=args.force,
        )

    frames = build_datasets_from_company_json(
        json_dir=Path(args.json_dir),
        output_dir=Path(args.output_dir),
    )
    logger.info("Company fetch status: %s", result["status"])
    logger.info("financial_summary rows: %s", len(frames["financial_summary"]))
    logger.info("time_series_financials rows: %s", len(frames["time_series_financials"]))
    return 0


def run_fetch_all(args: argparse.Namespace) -> int:
    configure_logging(args.log_level)
    settings = CrawlerSettings(
        delay_seconds=args.delay_seconds,
        timeout_seconds=args.timeout_seconds,
    )
    companies = load_companies_master(Path(args.input_csv))
    if args.limit is not None:
        companies = companies[: args.limit]

    processed = 0
    skipped = 0
    errored = 0
    with ScreenerHttpClient(
        user_agent=settings.user_agent,
        timeout_seconds=settings.timeout_seconds,
        delay_seconds=settings.delay_seconds,
        max_retries=settings.max_retries,
    ) as client:
        robots_policy = load_robots_policy(client, "https://www.screener.in/")
        for company in companies:
            result = process_company_target(
                company,
                client=client,
                robots_policy=robots_policy,
                raw_html_dir=Path(args.raw_html_dir),
                json_dir=Path(args.json_dir),
                force=args.force,
            )
            if result["status"] == "skipped":
                skipped += 1
            elif result["status"] == "error":
                errored += 1
            else:
                processed += 1

    frames = build_datasets_from_company_json(
        json_dir=Path(args.json_dir),
        output_dir=Path(args.output_dir),
    )
    logger.info(
        "Fetch summary: processed=%s skipped=%s errored=%s",
        processed,
        skipped,
        errored,
    )
    logger.info(
        "Dataset rows: summary=%s profit_loss=%s balance_sheet=%s cash_flow=%s ratios=%s quarterly=%s shareholding=%s time_series=%s metadata=%s errors=%s",
        len(frames["financial_summary"]),
        len(frames["profit_loss"]),
        len(frames["balance_sheet"]),
        len(frames["cash_flow"]),
        len(frames["ratios"]),
        len(frames["quarterly_results"]),
        len(frames["shareholding_pattern"]),
        len(frames["time_series_financials"]),
        len(frames["raw_metadata"]),
        len(frames["crawl_errors"]),
    )
    return 0


def run_build_dataset(args: argparse.Namespace) -> int:
    configure_logging(args.log_level)
    frames = build_datasets_from_company_json(
        json_dir=Path(args.json_dir),
        output_dir=Path(args.output_dir),
    )
    logger.info(
        "Dataset rows: summary=%s profit_loss=%s balance_sheet=%s cash_flow=%s ratios=%s quarterly=%s shareholding=%s time_series=%s metadata=%s errors=%s",
        len(frames["financial_summary"]),
        len(frames["profit_loss"]),
        len(frames["balance_sheet"]),
        len(frames["cash_flow"]),
        len(frames["ratios"]),
        len(frames["quarterly_results"]),
        len(frames["shareholding_pattern"]),
        len(frames["time_series_financials"]),
        len(frames["raw_metadata"]),
        len(frames["crawl_errors"]),
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)
