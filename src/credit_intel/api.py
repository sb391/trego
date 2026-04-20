from __future__ import annotations

import io
import json
import logging
import shutil
from pathlib import Path
from typing import Any

import pandas as pd
from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from .config import CreditIntelConfig
from .orchestrator import CreditIntelligenceOrchestrator
from .schemas import BatchProcessRequest, BatchProcessResponse, CompanyCreditProfile
from .ui_exports import PresentationReportExporter
from .ui_schemas import CompanyDashboardView, PortfolioBatchView
from .ui_wrapper import (
    build_company_dashboard_view,
    build_portfolio_batch_view,
    find_mock_dashboard_view,
    load_mock_dashboard_views,
)


LOGGER = logging.getLogger(__name__)
CONFIG = CreditIntelConfig()
ORCHESTRATOR = CreditIntelligenceOrchestrator(CONFIG)
UI_EXPORTER = PresentationReportExporter(CONFIG)
UI_BATCHES: dict[str, list[CompanyDashboardView]] = {}

app = FastAPI(title=CONFIG.api_title, version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict[str, Any]:
    return {"status": "ok"}


@app.get("/api/companies/samples")
def sample_company_names(limit: int = 5) -> dict[str, Any]:
    return {"company_names": ORCHESTRATOR.default_sample_company_names(limit=limit)}


@app.get("/api/ui/samples")
def ui_samples(limit: int = 5) -> dict[str, Any]:
    mock_profiles = load_mock_dashboard_views(config=CONFIG, limit=limit)
    if mock_profiles:
        return {"companies": mock_profiles, "mock_mode": True}
    company_names = ORCHESTRATOR.default_sample_company_names(limit=limit)
    profiles = ORCHESTRATOR.process_batch(company_names)
    return {
        "companies": [build_company_dashboard_view(profile, config=CONFIG) for profile in profiles],
        "mock_mode": False,
    }


@app.get("/company/{company_id}", response_model=CompanyDashboardView)
@app.get("/api/company/{company_id}", response_model=CompanyDashboardView)
def company_dashboard(company_id: str, force_refresh: bool = False, mock: bool = False) -> CompanyDashboardView:
    if mock:
        mock_view = find_mock_dashboard_view(company_id, config=CONFIG)
        if mock_view is not None:
            return mock_view
    profile = ORCHESTRATOR.process_company(company_id, force_refresh=force_refresh)
    return build_company_dashboard_view(profile, config=CONFIG)


@app.post("/api/companies/process", response_model=CompanyCreditProfile)
def process_company(payload: dict[str, Any]) -> CompanyCreditProfile:
    company_name = str(payload.get("company_name") or "").strip()
    force_refresh = bool(payload.get("force_refresh") or False)
    if not company_name:
        raise HTTPException(status_code=400, detail="company_name is required")
    return ORCHESTRATOR.process_company(company_name, force_refresh=force_refresh)


@app.post("/api/ui/portfolio/process", response_model=PortfolioBatchView)
def process_ui_portfolio(payload: BatchProcessRequest) -> PortfolioBatchView:
    profiles = ORCHESTRATOR.process_batch(payload.company_names)
    workbook_path = ORCHESTRATOR.export_batch_profiles(profiles)
    batch_view = build_portfolio_batch_view(
        batch_id=workbook_path.stem,
        profiles=profiles,
        workbook_path=str(workbook_path),
        config=CONFIG,
    )
    _register_ui_batch(batch_view)
    return batch_view


@app.post("/api/companies/batch", response_model=BatchProcessResponse)
def process_batch(payload: BatchProcessRequest) -> BatchProcessResponse:
    profiles = ORCHESTRATOR.process_batch(payload.company_names)
    workbook_path = ORCHESTRATOR.export_batch_profiles(profiles)
    return BatchProcessResponse(
        batch_id=workbook_path.stem,
        company_count=len(profiles),
        profiles=profiles,
        workbook_path=str(workbook_path),
    )


@app.post("/api/companies/upload", response_model=BatchProcessResponse)
async def upload_company_list(file: UploadFile = File(...)) -> BatchProcessResponse:
    content = await file.read()
    if file.filename is None:
        raise HTTPException(status_code=400, detail="Uploaded file must have a name.")
    suffix = Path(file.filename).suffix.lower()
    if suffix == ".csv":
        frame = pd.read_csv(io.BytesIO(content))
    elif suffix in {".xlsx", ".xls"}:
        frame = pd.read_excel(io.BytesIO(content))
    else:
        raise HTTPException(status_code=400, detail="Only CSV or Excel uploads are supported.")

    if frame.empty:
        raise HTTPException(status_code=400, detail="Uploaded file was empty.")

    company_column = next((column for column in frame.columns if "company" in str(column).lower() or "name" in str(column).lower()), frame.columns[0])
    company_names = frame[company_column].dropna().astype(str).tolist()
    profiles = ORCHESTRATOR.process_batch(company_names)
    workbook_path = ORCHESTRATOR.export_batch_profiles(profiles)
    return BatchProcessResponse(
        batch_id=workbook_path.stem,
        company_count=len(profiles),
        profiles=profiles,
        workbook_path=str(workbook_path),
    )


@app.post("/api/ui/portfolio/upload", response_model=PortfolioBatchView)
async def upload_ui_portfolio(file: UploadFile = File(...)) -> PortfolioBatchView:
    company_names = await _extract_company_names_from_upload(file)
    profiles = ORCHESTRATOR.process_batch(company_names)
    workbook_path = ORCHESTRATOR.export_batch_profiles(profiles)
    batch_view = build_portfolio_batch_view(
        batch_id=workbook_path.stem,
        profiles=profiles,
        workbook_path=str(workbook_path),
        config=CONFIG,
    )
    _register_ui_batch(batch_view)
    return batch_view


@app.get("/api/download/company")
def download_company(company_name: str) -> FileResponse:
    profile = ORCHESTRATOR.process_company(company_name)
    workbook_path = ORCHESTRATOR.export_company_profile(profile)
    return FileResponse(
        workbook_path,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=workbook_path.name,
    )


@app.get("/api/download/company-word")
def download_company_word(company_name: str) -> FileResponse:
    profile = ORCHESTRATOR.process_company(company_name)
    document_path = ORCHESTRATOR.export_company_word_profile(profile)
    return FileResponse(
        document_path,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=document_path.name,
    )


@app.get("/api/ui/reports/company.xlsx")
def download_company_ui_excel(company_name: str) -> FileResponse:
    profile = ORCHESTRATOR.process_company(company_name)
    company = build_company_dashboard_view(profile, config=CONFIG)
    workbook_path = UI_EXPORTER.export_excel(company)
    return FileResponse(
        workbook_path,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=workbook_path.name,
    )


@app.get("/api/ui/reports/company.docx")
def download_company_ui_word(company_name: str) -> FileResponse:
    profile = ORCHESTRATOR.process_company(company_name)
    company = build_company_dashboard_view(profile, config=CONFIG)
    document_path = UI_EXPORTER.export_word(company)
    return FileResponse(
        document_path,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=document_path.name,
    )


@app.get("/api/ui/reports/company.pdf")
def download_company_ui_pdf(company_name: str) -> FileResponse:
    profile = ORCHESTRATOR.process_company(company_name)
    company = build_company_dashboard_view(profile, config=CONFIG)
    document_path = UI_EXPORTER.export_pdf(company)
    return FileResponse(
        document_path,
        media_type="application/pdf",
        filename=document_path.name,
    )


@app.get("/api/ui/reports/portfolio.xlsx")
def download_portfolio_ui_excel(batch_id: str = Query(...)) -> FileResponse:
    companies = UI_BATCHES.get(batch_id)
    if not companies:
        raise HTTPException(status_code=404, detail="Portfolio batch not found in UI session")
    workbook_path = UI_EXPORTER.export_portfolio_excel(batch_id, companies)
    return FileResponse(
        workbook_path,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=workbook_path.name,
    )


@app.get("/api/ui/reports/portfolio.zip")
def download_portfolio_ui_zip(batch_id: str = Query(...)) -> FileResponse:
    companies = UI_BATCHES.get(batch_id)
    if not companies:
        raise HTTPException(status_code=404, detail="Portfolio batch not found in UI session")
    archive_path = UI_EXPORTER.export_portfolio_zip(batch_id, companies)
    return FileResponse(
        archive_path,
        media_type="application/zip",
        filename=archive_path.name,
    )


@app.get("/api/download/batch/{batch_id}")
def download_batch(batch_id: str) -> FileResponse:
    workbook_path = CONFIG.batch_exports_dir / f"{batch_id}.xlsx"
    if not workbook_path.exists():
        raise HTTPException(status_code=404, detail="Batch workbook not found")
    return FileResponse(
        workbook_path,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=workbook_path.name,
    )


@app.post("/api/samples/generate")
def generate_samples(limit: int = 5) -> JSONResponse:
    company_names = ORCHESTRATOR.default_sample_company_names(limit=limit)
    profiles = ORCHESTRATOR.process_batch(company_names)
    workbook_path = ORCHESTRATOR.export_batch_profiles(profiles)
    shutil.copyfile(workbook_path, CONFIG.sample_workbook_path)
    CONFIG.sample_profiles_path.write_text(
        json.dumps([profile.model_dump(mode="json") for profile in profiles], indent=2),
        encoding="utf-8",
    )
    return JSONResponse(
        {
            "company_names": company_names,
            "profiles_path": str(CONFIG.sample_profiles_path),
            "workbook_path": str(CONFIG.sample_workbook_path),
        }
    )


async def _extract_company_names_from_upload(file: UploadFile) -> list[str]:
    content = await file.read()
    if file.filename is None:
        raise HTTPException(status_code=400, detail="Uploaded file must have a name.")
    suffix = Path(file.filename).suffix.lower()
    if suffix == ".csv":
        frame = pd.read_csv(io.BytesIO(content))
    elif suffix in {".xlsx", ".xls"}:
        frame = pd.read_excel(io.BytesIO(content))
    else:
        raise HTTPException(status_code=400, detail="Only CSV or Excel uploads are supported.")

    if frame.empty:
        raise HTTPException(status_code=400, detail="Uploaded file was empty.")

    company_column = next(
        (column for column in frame.columns if "company" in str(column).lower() or "name" in str(column).lower()),
        frame.columns[0],
    )
    return frame[company_column].dropna().astype(str).tolist()


def _register_ui_batch(batch_view: PortfolioBatchView) -> None:
    UI_BATCHES[batch_view.batch_id] = batch_view.companies
