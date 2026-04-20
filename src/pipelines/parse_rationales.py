from __future__ import annotations

import argparse
import logging
from pathlib import Path
from typing import Any

from ..output import (
    bundle_to_document_row,
    bundle_to_error_rows,
    bundle_to_event_rows,
    bundle_to_feature_row,
    ensure_output_layout,
    write_csv_rows,
    write_parsed_json,
    write_raw_text,
)
from ..parsers import get_parser
from ..utils import detect_agency_name, extract_pdf_text


LOGGER = logging.getLogger(__name__)

DOCUMENT_COLUMNS = [
    "rationale_doc_id",
    "company_name",
    "agency_name",
    "doc_date",
    "source_file",
    "pdf_path",
    "parsed_status",
    "document_type",
    "text_hash",
    "parser_name",
    "parsed_json_path",
    "raw_text_path",
    "extracted_text_method",
    "warning_count",
    "error_count",
    "missing_company_name",
    "missing_agency_name",
    "missing_rating_date",
    "fields_extracted_successfully",
]

RATING_EVENT_COLUMNS = [
    "rating_event_id",
    "rationale_doc_id",
    "company_name",
    "agency_name",
    "rating_date",
    "instrument_type",
    "facility_amount",
    "current_rating",
    "previous_rating",
    "long_term_rating",
    "short_term_rating",
    "outlook",
    "watch_status",
    "rating_action",
    "rating_rank_numeric",
    "is_withdrawn",
    "is_issuer_not_cooperating",
]

FEATURE_COLUMNS = [
    "rationale_doc_id",
    "agency_name",
    "company_name",
    "analytical_approach",
    "standalone_or_consolidated",
    "liquidity_label",
    "has_management_strength",
    "has_group_support",
    "has_scale_constraint",
    "has_working_capital_pressure",
    "has_liquidity_adequate",
    "has_liquidity_stretched",
    "has_regulatory_risk",
    "has_fx_risk",
    "has_customer_concentration",
    "has_product_diversification",
    "has_export_risk",
    "has_capex_risk",
    "has_margin_pressure",
    "has_leverage_improvement",
    "has_turnaround_story",
    "has_non_cooperation_flag",
    "has_contingent_liability_risk",
    "has_msa_dependency",
    "has_capacity_expansion",
    "has_niche_complex_portfolio",
    "has_strong_roce",
    "has_net_cash_position",
    "strengths_json",
    "weaknesses_json",
    "sensitivities_up_json",
    "sensitivities_down_json",
    "qualitative_summary",
]

PARSER_ERROR_COLUMNS = [
    "rationale_doc_id",
    "source_file",
    "company_name",
    "agency_name",
    "parser_name",
    "severity",
    "field_name",
    "message",
]


def parse_rating_rationales(input_dir: Path, output_dir: Path) -> dict[str, Any]:
    output_paths = ensure_output_layout(output_dir)
    documents_rows: list[dict[str, Any]] = []
    features_rows: list[dict[str, Any]] = []
    event_rows: list[dict[str, Any]] = []
    parser_error_rows: list[dict[str, Any]] = []
    parsed_files: list[str] = []

    for pdf_path in sorted(input_dir.glob("*.pdf")):
        LOGGER.info("Parsing %s", pdf_path.name)
        try:
            extracted = extract_pdf_text(pdf_path)
            agency_name = detect_agency_name(pdf_path.name, extracted.text)
            parser = get_parser(agency_name)
            bundle = parser.parse(
                pdf_path=pdf_path,
                source_file=pdf_path.name,
                text=extracted.text,
                text_hash=extracted.text_hash,
                extractor_used=extracted.extractor_used,
            )
            raw_text_path = write_raw_text(bundle, text=extracted.text, output_paths=output_paths)
            bundle.raw_text_path = str(raw_text_path)
            parsed_json_path = write_parsed_json(bundle, output_paths=output_paths)

            documents_rows.append(bundle_to_document_row(bundle, parsed_json_path=parsed_json_path))
            features_rows.append(bundle_to_feature_row(bundle))
            event_rows.extend(bundle_to_event_rows(bundle))
            parser_error_rows.extend(bundle_to_error_rows(bundle))
            parsed_files.append(pdf_path.name)
        except Exception as exc:  # noqa: BLE001
            LOGGER.exception("Failed to parse %s", pdf_path.name)
            parser_error_rows.append(
                {
                    "rationale_doc_id": None,
                    "source_file": pdf_path.name,
                    "company_name": None,
                    "agency_name": None,
                    "parser_name": None,
                    "severity": "error",
                    "field_name": None,
                    "message": str(exc),
                }
            )
            documents_rows.append(
                {
                    "rationale_doc_id": None,
                    "company_name": None,
                    "agency_name": None,
                    "doc_date": None,
                    "source_file": pdf_path.name,
                    "pdf_path": str(pdf_path),
                    "parsed_status": "failed",
                    "document_type": None,
                    "text_hash": None,
                    "parser_name": None,
                    "parsed_json_path": None,
                    "raw_text_path": None,
                    "extracted_text_method": None,
                    "warning_count": 0,
                    "error_count": 1,
                    "missing_company_name": True,
                    "missing_agency_name": True,
                    "missing_rating_date": True,
                    "fields_extracted_successfully": "[]",
                }
            )

    write_csv_rows(documents_rows, output_paths.documents_csv, preferred_columns=DOCUMENT_COLUMNS)
    write_csv_rows(event_rows, output_paths.rating_events_csv, preferred_columns=RATING_EVENT_COLUMNS)
    write_csv_rows(features_rows, output_paths.rationale_features_csv, preferred_columns=FEATURE_COLUMNS)
    write_csv_rows(parser_error_rows, output_paths.parser_errors_csv, preferred_columns=PARSER_ERROR_COLUMNS)

    return {
        "input_dir": str(input_dir.resolve()),
        "output_dir": str(output_dir.resolve()),
        "parsed_files": parsed_files,
        "documents_count": len(documents_rows),
        "rating_events_count": len(event_rows),
        "rationale_features_count": len(features_rows),
        "parser_messages_count": len(parser_error_rows),
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m src.pipelines.parse_rationales",
        description="Parse local rating rationale PDFs into structured canonical outputs.",
    )
    parser.add_argument(
        "--input-dir",
        default="data/input/rating_rationales",
        help="Directory containing agency rationale PDFs.",
    )
    parser.add_argument(
        "--output-dir",
        default="output",
        help="Directory where raw text, JSON, and CSV outputs will be written.",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        help="Logging level such as INFO or DEBUG.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    logging.basicConfig(level=getattr(logging, str(args.log_level).upper(), logging.INFO))
    summary = parse_rating_rationales(Path(args.input_dir), Path(args.output_dir))
    print(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
