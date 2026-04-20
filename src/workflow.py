from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from .config import AppConfig
from .io_utils import (
    CREDIT_RATING_FAILURE_COLUMNS,
    FAILED_DOWNLOAD_COLUMNS,
    build_input_company_frame,
    delete_row_by_company_id,
    load_csv_frame,
    load_checkpoint,
    load_download_status_records,
    load_input_companies,
    replace_credit_rating_records,
    reset_phase_one_artifacts,
    save_checkpoint,
    upsert_credit_rating_failure,
    upsert_credit_rating_status,
    upsert_ambiguous_match,
    upsert_download_status,
    upsert_failed_download,
    write_excel_workbook,
)
from .models import (
    AmbiguousMatchRecord,
    CreditRatingLink,
    CreditRatingRecord,
    CreditRatingFailureRecord,
    CreditRatingStatusRecord,
    DownloadStatusRecord,
    FailedDownloadRecord,
)
from .screener_credit_ratings import CreditRatingsWorkflowError, ScreenerCreditRatingsBrowser
from .screener_download import (
    AuthenticationRequiredError,
    DownloadWorkflowError,
    ScreenerDownloadBrowser,
    build_download_filename,
    build_download_status_update,
    file_already_downloaded,
    is_pending_download_status,
)
from .screener_matcher import choose_best_match
from .screener_search import ScreenerSearchBrowser


logger = logging.getLogger(__name__)


def run_phase_one(
    *,
    input_path: Path,
    config: AppConfig,
    limit: int | None = None,
    resume: bool = False,
) -> dict[str, int]:
    if not resume:
        reset_phase_one_artifacts(config)

    checkpoint = load_checkpoint(config.checkpoint_path) if resume else {
        "processed_company_ids": [],
        "matched_urls": {},
        "downloaded_company_ids": [],
        "updated_at": None,
    }
    processed_ids = set(checkpoint.get("processed_company_ids", []))
    matched_urls = dict(checkpoint.get("matched_urls", {}))

    companies = load_input_companies(input_path)
    if limit is not None:
        companies = companies[:limit]

    summary = {
        "processed": 0,
        "matched": 0,
        "ambiguous": 0,
        "failed": 0,
        "skipped": 0,
    }

    with ScreenerSearchBrowser(config) as search_browser:
        for company in companies:
            if resume and company.company_id in processed_ids:
                logger.info("Skipping %s because it is already present in checkpoint.", company.company_id)
                summary["skipped"] += 1
                continue

            try:
                candidates = search_browser.search(company.search_name)
                decision = choose_best_match(
                    company,
                    candidates,
                    auto_threshold=config.similarity_auto_threshold,
                    ambiguity_gap_threshold=config.ambiguity_gap_threshold,
                )
                _persist_decision(decision, config)
                if decision.status == "matched" and decision.matched_candidate is not None:
                    matched_urls[company.company_id] = decision.matched_candidate.url
                    summary["matched"] += 1
                elif decision.status == "ambiguous":
                    summary["ambiguous"] += 1
                else:
                    summary["failed"] += 1
                processed_ids.add(company.company_id)
                summary["processed"] += 1
            except Exception as exc:  # noqa: BLE001
                logger.exception("Failed during search workflow for %s", company.company_id)
                failure = FailedDownloadRecord(
                    company_id=company.company_id,
                    company_name=company.company_name,
                    stage_failed="search",
                    error_message=str(exc),
                    retry_count=0,
                    timestamp=_utc_now(),
                )
                upsert_failed_download(config.failed_downloads_path, failure)
                status = DownloadStatusRecord(
                    company_id=company.company_id,
                    company_name=company.company_name,
                    nse_code=company.nse_code,
                    bse_code=company.bse_code,
                    screener_url=None,
                    local_file_path=None,
                    status="search_failed",
                    downloaded_at=None,
                    validation_status="not_started",
                    notes=str(exc),
                )
                upsert_download_status(config.download_status_path, status)
                summary["failed"] += 1
                summary["processed"] += 1
                checkpoint_payload = {
                    "processed_company_ids": sorted(processed_ids),
                    "matched_urls": matched_urls,
                    "updated_at": _utc_now(),
                }
                save_checkpoint(config.checkpoint_path, checkpoint_payload)
                continue

            checkpoint_payload = {
                "processed_company_ids": sorted(processed_ids),
                "matched_urls": matched_urls,
                "updated_at": _utc_now(),
            }
            save_checkpoint(config.checkpoint_path, checkpoint_payload)

    return summary


def run_phase_two_downloads(
    *,
    config: AppConfig,
    limit: int | None = None,
    resume: bool = False,
    force: bool = False,
    interactive_login: bool = False,
) -> dict[str, int]:
    checkpoint = load_checkpoint(config.checkpoint_path)
    downloaded_ids = set(checkpoint.get("downloaded_company_ids", []))
    matched_urls = dict(checkpoint.get("matched_urls", {}))
    processed_ids = set(checkpoint.get("processed_company_ids", []))

    targets = [
        row
        for row in load_download_status_records(config.download_status_path)
        if is_pending_download_status(row, force=force)
    ]
    if limit is not None:
        targets = targets[:limit]

    summary = {
        "processed": 0,
        "downloaded": 0,
        "skipped": 0,
        "failed": 0,
    }

    with ScreenerDownloadBrowser(
        config,
        storage_state_path=config.storage_state_path,
        interactive_login=interactive_login,
    ) as download_browser:
        for row in targets:
            company_id = str(row.get("company_id") or "")
            company_name = str(row.get("company_name") or "")
            screener_url = str(row.get("screener_url") or "")

            if resume and company_id in downloaded_ids and not force:
                logger.info("Skipping %s because it is already marked downloaded in checkpoint.", company_id)
                summary["skipped"] += 1
                continue

            if file_already_downloaded(row, config.downloads_dir) and not force:
                logger.info("Skipping %s because a local workbook already exists.", company_id)
                status = DownloadStatusRecord(
                    company_id=company_id,
                    company_name=company_name,
                    nse_code=_string_or_none(row.get("nse_code")),
                    bse_code=_string_or_none(row.get("bse_code")),
                    screener_url=screener_url,
                    local_file_path=_resolve_existing_download_path(row, config),
                    status="downloaded",
                    downloaded_at=_string_or_none(row.get("downloaded_at")),
                    validation_status=_string_or_none(row.get("validation_status")) or "not_started",
                    notes="Existing file retained; use --force to re-download.",
                )
                upsert_download_status(config.download_status_path, status)
                delete_row_by_company_id(config.failed_downloads_path, FAILED_DOWNLOAD_COLUMNS, company_id)
                downloaded_ids.add(company_id)
                summary["skipped"] += 1
                _save_download_checkpoint(config, downloaded_ids, processed_ids, matched_urls)
                continue

            try:
                result = download_browser.download_company_workbook(
                    company_name=company_name,
                    nse_code=_string_or_none(row.get("nse_code")),
                    bse_code=_string_or_none(row.get("bse_code")),
                    screener_url=screener_url,
                    downloads_dir=config.downloads_dir,
                    force=force,
                )
                status = build_download_status_update(row, result)
                upsert_download_status(config.download_status_path, status)
                delete_row_by_company_id(config.failed_downloads_path, FAILED_DOWNLOAD_COLUMNS, company_id)
                downloaded_ids.add(company_id)
                summary["downloaded"] += 1
            except AuthenticationRequiredError as exc:
                logger.exception("Authentication required during export for %s", company_id)
                _persist_download_failure(
                    row,
                    config=config,
                    stage_failed="download_auth",
                    status="auth_required",
                    message=str(exc),
                )
                summary["failed"] += 1
            except DownloadWorkflowError as exc:
                logger.exception("Download workflow failed for %s", company_id)
                _persist_download_failure(
                    row,
                    config=config,
                    stage_failed="download",
                    status="download_failed",
                    message=str(exc),
                )
                summary["failed"] += 1
            except Exception as exc:  # noqa: BLE001
                logger.exception("Unexpected error during download for %s", company_id)
                _persist_download_failure(
                    row,
                    config=config,
                    stage_failed="download_unexpected",
                    status="download_failed",
                    message=str(exc),
                )
                summary["failed"] += 1

            summary["processed"] += 1
            _save_download_checkpoint(config, downloaded_ids, processed_ids, matched_urls)

    return summary


def run_phase_three_credit_ratings(
    *,
    input_path: Path,
    config: AppConfig,
    limit: int | None = None,
    resume: bool = False,
    force: bool = False,
) -> dict[str, int]:
    if not resume:
        for path in (
            config.credit_rating_history_path,
            config.credit_rating_status_path,
            config.credit_rating_failures_path,
            config.credit_rating_checkpoint_path,
        ):
            if path.exists():
                path.unlink()

    checkpoint = load_checkpoint(config.credit_rating_checkpoint_path) if resume else {
        "processed_company_ids": [],
        "updated_at": None,
    }
    processed_ids = set(checkpoint.get("processed_company_ids", []))

    companies = load_input_companies(input_path)
    if limit is not None:
        companies = companies[:limit]

    download_rows = {
        str(row.get("company_id") or ""): row
        for row in load_download_status_records(config.download_status_path)
    }

    summary = {
        "processed": 0,
        "extracted": 0,
        "partial": 0,
        "no_ratings": 0,
        "unresolved_matches": 0,
        "failed": 0,
        "skipped": 0,
    }

    with ScreenerCreditRatingsBrowser(
        config,
        storage_state_path=config.storage_state_path,
    ) as credit_browser:
        for company in companies:
            if resume and company.company_id in processed_ids and not force:
                logger.info("Skipping %s because credit ratings are already checkpointed.", company.company_id)
                summary["skipped"] += 1
                continue

            status_row = download_rows.get(company.company_id, {})
            screener_url = _string_or_none(status_row.get("screener_url"))

            if not screener_url:
                replace_credit_rating_records(config.credit_rating_history_path, company.company_id, [])
                delete_row_by_company_id(config.credit_rating_failures_path, CREDIT_RATING_FAILURE_COLUMNS, company.company_id)
                upsert_credit_rating_status(
                    config.credit_rating_status_path,
                    CreditRatingStatusRecord(
                        company_id=company.company_id,
                        company_name=company.company_name,
                        nse_code=company.nse_code,
                        bse_code=company.bse_code,
                        screener_url=None,
                        status="skipped_missing_match",
                        ratings_found=0,
                        updated_at=_utc_now(),
                        notes="No matched Screener URL was available in download_status.csv.",
                    ),
                )
                summary["unresolved_matches"] += 1
                summary["processed"] += 1
                processed_ids.add(company.company_id)
                _save_credit_rating_checkpoint(config, processed_ids)
                continue

            try:
                links = credit_browser.collect_company_rating_links(
                    company_id=company.company_id,
                    company_name=company.company_name,
                    nse_code=company.nse_code,
                    bse_code=company.bse_code,
                    screener_url=screener_url,
                )
                if not links:
                    replace_credit_rating_records(config.credit_rating_history_path, company.company_id, [])
                    delete_row_by_company_id(config.credit_rating_failures_path, CREDIT_RATING_FAILURE_COLUMNS, company.company_id)
                    upsert_credit_rating_status(
                        config.credit_rating_status_path,
                        CreditRatingStatusRecord(
                            company_id=company.company_id,
                            company_name=company.company_name,
                            nse_code=company.nse_code,
                            bse_code=company.bse_code,
                            screener_url=screener_url,
                            status="no_credit_ratings",
                            ratings_found=0,
                            updated_at=_utc_now(),
                            notes="No Screener credit rating links were present on the company page.",
                        ),
                    )
                    summary["no_ratings"] += 1
                else:
                    records = []
                    failures: list[str] = []
                    for link in links:
                        try:
                            records.append(credit_browser.extract_rating_record(link))
                        except Exception as exc:  # noqa: BLE001
                            logger.exception("Failed to extract rating update for %s", link.event_id)
                            failures.append(f"{link.rating_update_url}: {exc}")
                            records.append(_blank_credit_rating_record(link, str(exc)))

                    replace_credit_rating_records(config.credit_rating_history_path, company.company_id, records)

                    resolved_count = sum(1 for record in records if record.rating)
                    if failures:
                        upsert_credit_rating_failure(
                            config.credit_rating_failures_path,
                            CreditRatingFailureRecord(
                                company_id=company.company_id,
                                company_name=company.company_name,
                                rating_update_url=None,
                                stage_failed="rating_document",
                                error_message=" | ".join(failures[:5]),
                                retry_count=0,
                                timestamp=_utc_now(),
                            ),
                        )
                    else:
                        delete_row_by_company_id(
                            config.credit_rating_failures_path,
                            CREDIT_RATING_FAILURE_COLUMNS,
                            company.company_id,
                        )

                    status_value = "rating_history_extracted"
                    notes = f"Extracted {resolved_count} of {len(records)} rating update(s)."
                    if resolved_count < len(records):
                        status_value = "rating_history_partial"
                    upsert_credit_rating_status(
                        config.credit_rating_status_path,
                        CreditRatingStatusRecord(
                            company_id=company.company_id,
                            company_name=company.company_name,
                            nse_code=company.nse_code,
                            bse_code=company.bse_code,
                            screener_url=screener_url,
                            status=status_value,
                            ratings_found=len(records),
                            updated_at=_utc_now(),
                            notes=notes,
                        ),
                    )
                    if status_value == "rating_history_extracted":
                        summary["extracted"] += 1
                    else:
                        summary["partial"] += 1

                processed_ids.add(company.company_id)
                summary["processed"] += 1
                _save_credit_rating_checkpoint(config, processed_ids)
            except CreditRatingsWorkflowError as exc:
                logger.exception("Credit rating workflow failed for %s", company.company_id)
                replace_credit_rating_records(config.credit_rating_history_path, company.company_id, [])
                upsert_credit_rating_failure(
                    config.credit_rating_failures_path,
                    CreditRatingFailureRecord(
                        company_id=company.company_id,
                        company_name=company.company_name,
                        rating_update_url=None,
                        stage_failed="company_credit_ratings",
                        error_message=str(exc),
                        retry_count=0,
                        timestamp=_utc_now(),
                    ),
                )
                upsert_credit_rating_status(
                    config.credit_rating_status_path,
                    CreditRatingStatusRecord(
                        company_id=company.company_id,
                        company_name=company.company_name,
                        nse_code=company.nse_code,
                        bse_code=company.bse_code,
                        screener_url=screener_url,
                        status="rating_extraction_failed",
                        ratings_found=0,
                        updated_at=_utc_now(),
                        notes=str(exc),
                    ),
                )
                processed_ids.add(company.company_id)
                summary["processed"] += 1
                summary["failed"] += 1
                _save_credit_rating_checkpoint(config, processed_ids)
            except Exception as exc:  # noqa: BLE001
                logger.exception("Unexpected credit rating error for %s", company.company_id)
                replace_credit_rating_records(config.credit_rating_history_path, company.company_id, [])
                upsert_credit_rating_failure(
                    config.credit_rating_failures_path,
                    CreditRatingFailureRecord(
                        company_id=company.company_id,
                        company_name=company.company_name,
                        rating_update_url=None,
                        stage_failed="credit_ratings_unexpected",
                        error_message=str(exc),
                        retry_count=0,
                        timestamp=_utc_now(),
                    ),
                )
                upsert_credit_rating_status(
                    config.credit_rating_status_path,
                    CreditRatingStatusRecord(
                        company_id=company.company_id,
                        company_name=company.company_name,
                        nse_code=company.nse_code,
                        bse_code=company.bse_code,
                        screener_url=screener_url,
                        status="rating_extraction_failed",
                        ratings_found=0,
                        updated_at=_utc_now(),
                        notes=str(exc),
                    ),
                )
                processed_ids.add(company.company_id)
                summary["processed"] += 1
                summary["failed"] += 1
                _save_credit_rating_checkpoint(config, processed_ids)

    _build_credit_rating_outputs(input_path=input_path, config=config)
    return summary


def _build_credit_rating_outputs(*, input_path: Path, config: AppConfig) -> None:
    input_frame = build_input_company_frame(input_path)
    history_frame = load_csv_frame(config.credit_rating_history_path)

    export_columns = list(input_frame.columns) + ["rating_date", "rating_agency", "rating"]
    if history_frame.empty:
        enriched = input_frame.iloc[0:0].copy()
        enriched["rating_date"] = pd.Series(dtype="object")
        enriched["rating_agency"] = pd.Series(dtype="object")
        enriched["rating"] = pd.Series(dtype="object")
    else:
        history_subset = history_frame[["company_id", "rating_date", "rating_agency", "rating"]].copy()
        enriched = history_subset.merge(input_frame, on="company_id", how="left")
    enriched = enriched[export_columns]

    csv_path = config.outputs_dir / f"{input_path.stem}_with_credit_ratings.csv"
    xlsx_path = config.outputs_dir / f"{input_path.stem}_with_credit_ratings.xlsx"
    enriched.to_csv(csv_path, index=False)
    write_excel_workbook(
        xlsx_path,
        {
            "credit_ratings": enriched,
        },
    )


def _blank_credit_rating_record(link: CreditRatingLink, message: str) -> CreditRatingRecord:
    return CreditRatingRecord(
        event_id=link.event_id,
        company_id=link.company_id,
        company_name=link.company_name,
        nse_code=link.nse_code,
        bse_code=link.bse_code,
        screener_url=link.screener_url,
        rating_update_url=link.rating_update_url,
        rating_date=link.rating_date,
        rating_date_display=link.rating_date_display,
        rating_agency=link.rating_agency,
        rating=None,
        rating_scale=None,
        extraction_method=None,
        extracted_at=_utc_now(),
        notes=" ".join(part for part in [link.notes, message] if part),
    )


def _save_credit_rating_checkpoint(config: AppConfig, processed_ids: set[str]) -> None:
    save_checkpoint(
        config.credit_rating_checkpoint_path,
        {
            "processed_company_ids": sorted(processed_ids),
            "updated_at": _utc_now(),
        },
    )


def _persist_decision(decision, config: AppConfig) -> None:  # type: ignore[no-untyped-def]
    company = decision.company
    matched_url = decision.matched_candidate.url if decision.matched_candidate else None

    if decision.status == "matched":
        notes = decision.reason
        if decision.scored_candidates:
            notes = f"{decision.reason} Reasons: {', '.join(decision.scored_candidates[0].reasons)}"
        status = DownloadStatusRecord(
            company_id=company.company_id,
            company_name=company.company_name,
            nse_code=company.nse_code,
            bse_code=company.bse_code,
            screener_url=matched_url,
            local_file_path=None,
            status="matched_ready_for_download",
            downloaded_at=None,
            validation_status="not_started",
            notes=notes,
        )
        upsert_download_status(config.download_status_path, status)
        return

    if decision.status == "ambiguous":
        top_candidates = [score.candidate for score in decision.scored_candidates[:3]]
        ambiguous = AmbiguousMatchRecord(
            company_id=company.company_id,
            intended_name=company.company_name,
            nse_code=company.nse_code,
            bse_code=company.bse_code,
            search_query=decision.search_query,
            candidate_1=_candidate_label(top_candidates, 0),
            candidate_2=_candidate_label(top_candidates, 1),
            candidate_3=_candidate_label(top_candidates, 2),
            reason=decision.reason,
        )
        upsert_ambiguous_match(config.ambiguous_matches_path, ambiguous)
        status = DownloadStatusRecord(
            company_id=company.company_id,
            company_name=company.company_name,
            nse_code=company.nse_code,
            bse_code=company.bse_code,
            screener_url=None,
            local_file_path=None,
            status="ambiguous_match",
            downloaded_at=None,
            validation_status="not_started",
            notes=decision.reason,
        )
        upsert_download_status(config.download_status_path, status)
        return

    failure = FailedDownloadRecord(
        company_id=company.company_id,
        company_name=company.company_name,
        stage_failed="matching",
        error_message=decision.reason,
        retry_count=0,
        timestamp=_utc_now(),
    )
    upsert_failed_download(config.failed_downloads_path, failure)
    status = DownloadStatusRecord(
        company_id=company.company_id,
        company_name=company.company_name,
        nse_code=company.nse_code,
        bse_code=company.bse_code,
        screener_url=None,
        local_file_path=None,
        status=decision.status,
        downloaded_at=None,
        validation_status="not_started",
        notes=decision.reason,
    )
    upsert_download_status(config.download_status_path, status)


def _candidate_label(candidates: list, index: int) -> str | None:  # type: ignore[no-untyped-def]
    if index >= len(candidates):
        return None
    candidate = candidates[index]
    return f"{candidate.name} | {candidate.company_slug} | {candidate.url}"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _persist_download_failure(
    row: dict[str, object],
    *,
    config: AppConfig,
    stage_failed: str,
    status: str,
    message: str,
) -> None:
    company_id = str(row.get("company_id") or "")
    company_name = str(row.get("company_name") or "")
    failure = FailedDownloadRecord(
        company_id=company_id,
        company_name=company_name,
        stage_failed=stage_failed,
        error_message=message,
        retry_count=0,
        timestamp=_utc_now(),
    )
    upsert_failed_download(config.failed_downloads_path, failure)
    status_record = DownloadStatusRecord(
        company_id=company_id,
        company_name=company_name,
        nse_code=_string_or_none(row.get("nse_code")),
        bse_code=_string_or_none(row.get("bse_code")),
        screener_url=_string_or_none(row.get("screener_url")),
        local_file_path=_string_or_none(row.get("local_file_path")),
        status=status,
        downloaded_at=_string_or_none(row.get("downloaded_at")),
        validation_status=_string_or_none(row.get("validation_status")) or "not_started",
        notes=message,
    )
    upsert_download_status(config.download_status_path, status_record)


def _save_download_checkpoint(
    config: AppConfig,
    downloaded_ids: set[str],
    processed_ids: set[str],
    matched_urls: dict[str, str],
) -> None:
    checkpoint_payload = {
        "processed_company_ids": sorted(processed_ids),
        "matched_urls": matched_urls,
        "downloaded_company_ids": sorted(downloaded_ids),
        "updated_at": _utc_now(),
    }
    save_checkpoint(config.checkpoint_path, checkpoint_payload)


def _resolve_existing_download_path(row: dict[str, object], config: AppConfig) -> str:
    local_file_path = _string_or_none(row.get("local_file_path"))
    if local_file_path and Path(local_file_path).exists():
        return local_file_path
    return str(
        config.downloads_dir
        / build_download_filename(
            str(row.get("company_name") or ""),
            _string_or_none(row.get("nse_code")),
            _string_or_none(row.get("bse_code")),
        )
    )


def _string_or_none(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
