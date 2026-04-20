from __future__ import annotations

import json
import logging
import math
import re
import unicodedata
from csv import DictReader
from dataclasses import asdict
from pathlib import Path
from typing import Iterable

import pandas as pd

from .config import AppConfig
from .models import (
    AmbiguousMatchRecord,
    CreditRatingFailureRecord,
    CreditRatingRecord,
    CreditRatingStatusRecord,
    CorporateRecord,
    DownloadStatusRecord,
    FailedDownloadRecord,
)


logger = logging.getLogger(__name__)

LEGAL_SUFFIX_TOKENS = {
    "ltd",
    "limited",
    "private",
    "pvt",
    "public",
    "co",
    "company",
    "corp",
    "corporation",
    "inc",
    "incorporated",
    "llp",
    "plc",
}

DOWNLOAD_STATUS_COLUMNS = [
    "company_id",
    "company_name",
    "nse_code",
    "bse_code",
    "screener_url",
    "local_file_path",
    "status",
    "downloaded_at",
    "validation_status",
    "notes",
]

AMBIGUOUS_MATCH_COLUMNS = [
    "company_id",
    "intended_name",
    "nse_code",
    "bse_code",
    "search_query",
    "candidate_1",
    "candidate_2",
    "candidate_3",
    "reason",
]

FAILED_DOWNLOAD_COLUMNS = [
    "company_id",
    "company_name",
    "stage_failed",
    "error_message",
    "retry_count",
    "timestamp",
]

CREDIT_RATING_HISTORY_COLUMNS = [
    "event_id",
    "company_id",
    "company_name",
    "nse_code",
    "bse_code",
    "screener_url",
    "rating_update_url",
    "rating_date",
    "rating_date_display",
    "rating_agency",
    "rating",
    "rating_scale",
    "extraction_method",
    "extracted_at",
    "notes",
]

CREDIT_RATING_STATUS_COLUMNS = [
    "company_id",
    "company_name",
    "nse_code",
    "bse_code",
    "screener_url",
    "status",
    "ratings_found",
    "updated_at",
    "notes",
]

CREDIT_RATING_FAILURE_COLUMNS = [
    "company_id",
    "company_name",
    "rating_update_url",
    "stage_failed",
    "error_message",
    "retry_count",
    "timestamp",
]


def ensure_runtime_directories(config: AppConfig) -> None:
    for path in (
        config.data_dir,
        config.downloads_dir,
        config.logs_dir,
        config.review_dir,
        config.state_dir,
        config.outputs_dir,
    ):
        path.mkdir(parents=True, exist_ok=True)


def reset_phase_one_artifacts(config: AppConfig) -> None:
    for path in (
        config.download_status_path,
        config.ambiguous_matches_path,
        config.failed_downloads_path,
        config.checkpoint_path,
    ):
        if path.exists():
            path.unlink()


def normalize_company_name(value: str | None) -> str:
    if value is None:
        return ""
    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    normalized = normalized.lower().replace("&", " and ")
    normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized


def company_name_tokens(value: str | None) -> tuple[str, ...]:
    normalized = normalize_company_name(value)
    tokens = [token for token in normalized.split() if token and token not in LEGAL_SUFFIX_TOKENS]
    return tuple(tokens)


def sanitize_filename(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    normalized = re.sub(r"[^A-Za-z0-9]+", "_", normalized).strip("_")
    return normalized or "company"


def normalize_code(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, float):
        if math.isnan(value):
            return None
        if value.is_integer():
            return str(int(value))
    text = str(value).strip()
    if not text or text.lower() in {"nan", "none", "null"}:
        return None
    if text.endswith(".0") and text[:-2].isdigit():
        text = text[:-2]
    return text.upper()


def build_company_id(name: str, nse_code: str | None, bse_code: str | None, row_index: int) -> str:
    stem = sanitize_filename(name)
    code = nse_code or bse_code or str(row_index)
    return f"{stem}__{code}"


def load_input_companies(input_path: Path) -> list[CorporateRecord]:
    frame = pd.read_csv(input_path)
    records: list[CorporateRecord] = []
    seen_ids: set[str] = set()

    for row_index, row in frame.reset_index().iterrows():
        company_name = str(row.get("Name", "")).strip()
        if not company_name:
            continue

        nse_code = normalize_code(row.get("NSE Code"))
        bse_code = normalize_code(row.get("BSE Code"))
        company_id = build_company_id(company_name, nse_code, bse_code, row_index)
        if company_id in seen_ids:
            logger.info("Skipping duplicate input row for %s", company_id)
            continue

        record = CorporateRecord(
            row_index=row_index,
            company_id=company_id,
            company_name=company_name,
            search_name=company_name,
            normalized_name=normalize_company_name(company_name),
            normalized_tokens=company_name_tokens(company_name),
            nse_code=nse_code,
            bse_code=bse_code,
            isin_code=normalize_code(row.get("ISIN Code")),
            industry_group=_string_or_none(row.get("Industry Group")),
            industry=_string_or_none(row.get("Industry")),
        )
        records.append(record)
        seen_ids.add(company_id)

    return records


def load_checkpoint(checkpoint_path: Path) -> dict[str, object]:
    if not checkpoint_path.exists():
        return {
            "processed_company_ids": [],
            "matched_urls": {},
            "downloaded_company_ids": [],
            "updated_at": None,
        }
    return json.loads(checkpoint_path.read_text(encoding="utf-8"))


def save_checkpoint(checkpoint_path: Path, payload: dict[str, object]) -> None:
    checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
    checkpoint_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def write_records_csv(
    output_path: Path,
    records: Iterable[dict[str, object]],
    columns: list[str],
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    frame = pd.DataFrame(list(records))
    if frame.empty:
        frame = pd.DataFrame(columns=columns)
    else:
        for column in columns:
            if column not in frame.columns:
                frame[column] = None
        frame = frame[columns]
    frame.to_csv(output_path, index=False)


def load_existing_rows(output_path: Path, key_field: str) -> dict[str, dict[str, object]]:
    if not output_path.exists():
        return {}
    rows: dict[str, dict[str, object]] = {}
    with output_path.open(encoding="utf-8") as handle:
        reader = DictReader(handle)
        for record in reader:
            key = str(record.get(key_field, "")).strip()
            if key:
                if key_field == "company_id" and "__" not in key:
                    logger.warning("Skipping malformed %s row with key %r from %s", key_field, key, output_path)
                    continue
                rows[key] = {
                    column: (value if value != "" else None)
                    for column, value in record.items()
                }
    return rows


def upsert_download_status(output_path: Path, status_record: DownloadStatusRecord) -> None:
    existing = load_existing_rows(output_path, "company_id")
    existing[status_record.company_id] = asdict(status_record)
    write_records_csv(output_path, existing.values(), DOWNLOAD_STATUS_COLUMNS)


def upsert_ambiguous_match(output_path: Path, record: AmbiguousMatchRecord) -> None:
    existing = load_existing_rows(output_path, "company_id")
    existing[record.company_id] = asdict(record)
    write_records_csv(output_path, existing.values(), AMBIGUOUS_MATCH_COLUMNS)


def upsert_failed_download(output_path: Path, record: FailedDownloadRecord) -> None:
    existing = load_existing_rows(output_path, "company_id")
    existing[record.company_id] = asdict(record)
    write_records_csv(output_path, existing.values(), FAILED_DOWNLOAD_COLUMNS)


def upsert_credit_rating_status(output_path: Path, record: CreditRatingStatusRecord) -> None:
    existing = load_existing_rows(output_path, "company_id")
    existing[record.company_id] = asdict(record)
    write_records_csv(output_path, existing.values(), CREDIT_RATING_STATUS_COLUMNS)


def upsert_credit_rating_failure(output_path: Path, record: CreditRatingFailureRecord) -> None:
    existing = load_existing_rows(output_path, "company_id")
    existing[record.company_id] = asdict(record)
    write_records_csv(output_path, existing.values(), CREDIT_RATING_FAILURE_COLUMNS)


def replace_rows_for_field(
    output_path: Path,
    *,
    field_name: str,
    field_value: str,
    rows: Iterable[dict[str, object]],
    columns: list[str],
) -> None:
    existing_rows = []
    if output_path.exists():
        with output_path.open(encoding="utf-8") as handle:
            reader = DictReader(handle)
            for record in reader:
                if str(record.get(field_name, "")).strip() != field_value:
                    existing_rows.append(
                        {
                            column: (value if value != "" else None)
                            for column, value in record.items()
                        }
                    )
    existing_rows.extend(rows)
    write_records_csv(output_path, existing_rows, columns)


def replace_credit_rating_records(output_path: Path, company_id: str, records: Iterable[CreditRatingRecord]) -> None:
    replace_rows_for_field(
        output_path,
        field_name="company_id",
        field_value=company_id,
        rows=(asdict(record) for record in records),
        columns=CREDIT_RATING_HISTORY_COLUMNS,
    )


def delete_row_by_company_id(output_path: Path, columns: list[str], company_id: str) -> None:
    existing = load_existing_rows(output_path, "company_id")
    if company_id not in existing:
        return
    del existing[company_id]
    write_records_csv(output_path, existing.values(), columns)


def load_download_status_records(output_path: Path) -> list[dict[str, object]]:
    if not output_path.exists():
        return []
    with output_path.open(encoding="utf-8") as handle:
        reader = DictReader(handle)
        rows = []
        for row in reader:
            company_id = str(row.get("company_id") or "").strip()
            if company_id and "__" not in company_id:
                logger.warning("Skipping malformed company_id row %r from %s", company_id, output_path)
                continue
            rows.append(
                {
                    key: normalize_code(value) if key in {"nse_code", "bse_code"} else (value if value != "" else None)
                    for key, value in row.items()
                }
            )
    return rows


def load_csv_frame(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path)


def build_input_company_frame(input_path: Path) -> pd.DataFrame:
    frame = pd.read_csv(input_path)
    company_ids = []
    for row_index, row in frame.reset_index().iterrows():
        company_ids.append(
            build_company_id(
                str(row.get("Name", "")).strip(),
                normalize_code(row.get("NSE Code")),
                normalize_code(row.get("BSE Code")),
                row_index,
            )
        )
    enriched = frame.copy()
    enriched["company_id"] = company_ids
    return enriched


def write_excel_workbook(path: Path, sheets: dict[str, pd.DataFrame]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        for sheet_name, frame in sheets.items():
            frame.to_excel(writer, sheet_name=sheet_name[:31], index=False)


def configure_file_logging(log_path: Path, level: str) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    handlers = [
        logging.StreamHandler(),
        logging.FileHandler(log_path, encoding="utf-8"),
    ]
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        handlers=handlers,
        force=True,
    )


def _string_or_none(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    text = str(value).strip()
    return text or None
