from pathlib import Path

from src.models import DownloadResult
from src.screener_download import (
    build_download_filename,
    build_download_status_update,
    file_already_downloaded,
    is_pending_download_status,
)


def test_build_download_filename_prefers_nse_code() -> None:
    assert build_download_filename("Sun Pharma Industries", "SUNPHARMA", "524715") == "Sun_Pharma_Industries__SUNPHARMA.xlsx"
    assert build_download_filename("Abbott India", None, "500488") == "Abbott_India__500488.xlsx"


def test_is_pending_download_status_honors_force_and_status() -> None:
    row = {
        "company_name": "Sun Pharma Industries",
        "status": "matched_ready_for_download",
        "screener_url": "https://www.screener.in/company/SUNPHARMA/consolidated/",
        "local_file_path": None,
    }
    assert is_pending_download_status(row, force=False) is True
    assert is_pending_download_status({**row, "status": "download_failed"}, force=False) is True
    assert is_pending_download_status({**row, "status": "auth_required"}, force=False) is True
    assert is_pending_download_status({**row, "status": "downloaded"}, force=False) is False
    assert is_pending_download_status({**row, "status": "downloaded"}, force=True) is True


def test_file_already_downloaded_checks_existing_target(tmp_path: Path) -> None:
    downloads_dir = tmp_path / "downloads"
    downloads_dir.mkdir()
    path = downloads_dir / "Sun_Pharma_Industries__SUNPHARMA.xlsx"
    path.write_bytes(b"test")

    row = {
        "company_name": "Sun Pharma Industries",
        "nse_code": "SUNPHARMA",
        "bse_code": "524715",
        "local_file_path": None,
    }
    assert file_already_downloaded(row, downloads_dir) is True


def test_build_download_status_update_maps_result_fields() -> None:
    row = {
        "company_id": "Sun_Pharma_Industries__SUNPHARMA",
        "company_name": "Sun Pharma Industries",
        "nse_code": "SUNPHARMA",
        "bse_code": "524715",
    }
    result = DownloadResult(
        company_id="Sun_Pharma_Industries__SUNPHARMA",
        company_name="Sun Pharma Industries",
        screener_url="https://www.screener.in/company/SUNPHARMA/consolidated/",
        status="downloaded",
        local_file_path="/tmp/Sun_Pharma_Industries__SUNPHARMA.xlsx",
        downloaded_at="2026-04-05T12:00:00+00:00",
        validation_status="not_started",
        notes="Workbook downloaded successfully",
    )

    status = build_download_status_update(row, result)

    assert status.company_id == "Sun_Pharma_Industries__SUNPHARMA"
    assert status.local_file_path == "/tmp/Sun_Pharma_Industries__SUNPHARMA.xlsx"
    assert status.status == "downloaded"
