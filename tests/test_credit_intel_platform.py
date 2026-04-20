from __future__ import annotations

from pathlib import Path

import pandas as pd
from fastapi.testclient import TestClient

from src.credit_intel.api import app
from src.credit_intel.dataset import AgricultureDatasetService
from src.credit_intel.config import CreditIntelConfig
from src.credit_intel.orchestrator import CreditIntelligenceOrchestrator
from src.credit_intel.workbook_parser import ScreenerWorkbookParser


def test_agriculture_dataset_has_unique_columns_and_financial_metrics() -> None:
    service = AgricultureDatasetService(CreditIntelConfig())
    frame = service.frame

    assert not frame.columns.duplicated().any()

    fore_agro = frame.loc[frame["company_name"] == "FORE AGRO PRIVATE LIMITED"].iloc[0]
    assert fore_agro["turnover_crore"] == 98.72
    assert fore_agro["ebitda_margin_pct"] == 11.96
    assert fore_agro["pat_margin_pct"] == 5.77


def test_screener_workbook_parser_extracts_summary() -> None:
    workbook = Path("/Users/sysadm/Desktop/Crawler/data/downloads/Sun_Pharma_Inds__SUNPHARMA.xlsx")
    parsed = ScreenerWorkbookParser().parse(workbook)

    assert parsed["financial_summary"]["revenue_crore"] is not None
    assert parsed["financial_summary"]["source"] == "screener_workbook"
    assert parsed["profit_loss"]
    assert parsed["balance_sheet"]
    assert parsed["cash_flow"]


def test_orchestrator_builds_below_threshold_profile_without_network() -> None:
    config = CreditIntelConfig(enable_web_discovery=False, outputs_dir=Path("outputs"), data_dir=Path("data"))
    orchestrator = CreditIntelligenceOrchestrator(config)

    profile = orchestrator.process_company("FORE AGRO PRIVATE LIMITED", force_refresh=True)

    assert profile.company_name == "FORE AGRO PRIVATE LIMITED"
    assert profile.below_threshold_flag is True
    assert profile.financial_summary.revenue_crore == 98.72
    assert profile.treds_insight.method_used == "model"
    assert profile.rationale_sections
    assert profile.rationale_draft
    simulation = (profile.model_extra or {}).get("simulation")
    assert simulation is not None
    assert simulation["rating_range"]
    assert simulation["selected_agency"]
    assert simulation["range_usability_label"] in {"focused", "workable", "directional_only"}
    assert simulation["ca_review_priority"] in {"low", "medium", "high"}

    word_path = orchestrator.export_company_word_profile(profile)
    assert word_path.exists()
    assert word_path.suffix == ".docx"

    workbook_path = orchestrator.export_company_profile(profile)
    assert workbook_path.exists()
    workbook = pd.ExcelFile(workbook_path)
    assert "Underwriting View" in workbook.sheet_names


def test_credit_intel_api_health_and_samples() -> None:
    client = TestClient(app)

    health = client.get("/api/health")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"

    samples = client.get("/api/companies/samples?limit=3")
    assert samples.status_code == 200
    assert len(samples.json()["company_names"]) == 3

    company_word = client.get("/api/download/company-word", params={"company_name": "FORE AGRO PRIVATE LIMITED"})
    assert company_word.status_code == 200
    assert company_word.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
