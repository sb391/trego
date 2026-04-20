from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest
from openpyxl import Workbook

from src.credit_intel.financial_document_parser import detect_financial_provider, parse_financial_document
from src.credit_intel.financial_ingestion import build_financial_dataset_from_manifest


SAMPLE_PROBE42_PDF = Path("/Users/sysadm/Downloads/Financials_TNPRPF_Probe 42 (1).pdf")
SAMPLE_TRADES_XLSX = Path("/Users/sysadm/Downloads/Trades_Company Data (1).xlsx")
SAMPLE_ELASTIC_XLSX = Path("/Users/sysadm/Downloads/Elastic Run Agri Comodities520 (1) (1).xlsx")


def test_detect_financial_provider_probe42_from_text() -> None:
    provider = detect_financial_provider(
        Path("financials.pdf"),
        extracted_text="Probe42.in generated financial report by Probe Information Services Private Limited",
    )
    assert provider == "probe42"


@pytest.mark.skipif(not SAMPLE_TRADES_XLSX.exists(), reason="Trades sample workbook is not available in this environment.")
def test_detect_financial_provider_generic_excel_for_non_screener_workbook() -> None:
    provider = detect_financial_provider(SAMPLE_TRADES_XLSX)
    assert provider == "generic_excel"


@pytest.mark.skipif(not SAMPLE_PROBE42_PDF.exists(), reason="Probe42 sample PDF is not available in this environment.")
def test_probe42_parser_extracts_multi_year_financials() -> None:
    parsed = parse_financial_document(SAMPLE_PROBE42_PDF)

    assert parsed["meta"]["company_name"] == "TAMILNADU PADDY & RICE PROCESSING FEDERATION"
    assert parsed["meta"]["listing_status"] == "Unlisted"
    assert parsed["financial_summary"]["source"] == "probe42_pdf"
    assert parsed["financial_summary"]["revenue_crore"] == pytest.approx(1936.77)
    assert parsed["financial_summary"]["debt_to_equity"] == pytest.approx(4.5)
    assert parsed["financial_summary"]["statement_period"] == "2025-03-31"
    assert parsed["balance_sheet"][0]["period"] == "2015-03-31"
    assert parsed["balance_sheet"][-1]["period"] == "2025-03-31"
    assert parsed["balance_sheet"][-1]["borrowings"] == pytest.approx(138.26)
    assert len(parsed["profit_loss"]) == 11
    assert len(parsed["balance_sheet"]) == 11
    assert parsed["cash_flow"][0]["period"] == "2020-03-31"
    assert len(parsed["cash_flow"]) == 6
    assert len(parsed["ratios"]) == 11


@pytest.mark.skipif(not SAMPLE_ELASTIC_XLSX.exists(), reason="Elastic sample workbook is not available in this environment.")
def test_generic_excel_parser_extracts_multiple_companies_and_quality_fields() -> None:
    parsed = parse_financial_document(SAMPLE_ELASTIC_XLSX)

    assert parsed["meta"]["source_provider"] == "generic_excel"
    assert parsed["meta"]["company_count"] > 100
    companies = parsed["companies"]
    fore_agro = next(item for item in companies if item["meta"]["company_name"] == "FORE AGRO PRIVATE LIMITED")
    summary = fore_agro["financial_summary"]

    assert summary["revenue_crore"] == pytest.approx(98.72)
    assert summary["ebitda_margin_pct"] == pytest.approx(11.96)
    assert summary["debt_to_equity"] == pytest.approx(2.32)
    assert summary["statement_period"] == "2025-03-31"
    assert fore_agro["profit_loss"][0]["sales"] == pytest.approx(98.72)
    assert fore_agro["balance_sheet"][0]["borrowings"] == pytest.approx(46.76)
    assert fore_agro["ratios"][0]["interest_coverage"] == pytest.approx(4.18)


@pytest.mark.skipif(not SAMPLE_PROBE42_PDF.exists(), reason="Probe42 sample PDF is not available in this environment.")
def test_build_financial_dataset_from_manifest_supports_probe42(tmp_path: Path) -> None:
    manifest_path = tmp_path / "manifest.csv"
    pd.DataFrame(
        [
            {
                "company_id": "tnprpf",
                "company_name": "TAMILNADU PADDY & RICE PROCESSING FEDERATION",
                "provider": "probe42",
                "file_path": str(SAMPLE_PROBE42_PDF),
                "industry_group": "Food and Beverages",
                "sub_industry": "Staple Food",
            }
        ]
    ).to_csv(manifest_path, index=False)

    outputs = build_financial_dataset_from_manifest(
        manifest_path=manifest_path,
        output_dir=tmp_path / "parsed_output",
    )

    summary = pd.read_csv(outputs["financial_summary"])
    features = pd.read_csv(outputs["financial_year_features"])

    assert outputs["latest_financial_features"].exists()
    assert summary.iloc[0]["company_id"] == "tnprpf"
    assert summary.iloc[0]["source"] == "probe42_pdf"
    assert summary.iloc[0]["revenue_crore"] == pytest.approx(1936.77)
    latest_feature = features.sort_values("period_date").iloc[-1]
    assert latest_feature["provider"] == "probe42"
    assert latest_feature["period_date"] == "2025-03-31"
    assert latest_feature["debt_to_equity"] == pytest.approx(4.5)


@pytest.mark.skipif(not SAMPLE_TRADES_XLSX.exists(), reason="Trades sample workbook is not available in this environment.")
def test_build_financial_dataset_from_manifest_expands_generic_excel_workbook(tmp_path: Path) -> None:
    manifest_path = tmp_path / "manifest.csv"
    pd.DataFrame(
        [
            {
                "provider": "generic_excel",
                "file_path": str(SAMPLE_TRADES_XLSX),
                "industry_group": "Agriculture",
            }
        ]
    ).to_csv(manifest_path, index=False)

    outputs = build_financial_dataset_from_manifest(
        manifest_path=manifest_path,
        output_dir=tmp_path / "parsed_output",
    )

    summary = pd.read_csv(outputs["financial_summary"])
    fore = summary.loc[summary["company_name"] == "SANTOSH STARCH PRODUCTS LIMITED"].iloc[0]
    assert len(summary) > 10
    assert fore["provider"] == "generic_excel"
    assert fore["critical_feature_coverage_pct"] >= 80.0
    assert fore["simulation_readiness"] == "high"


def test_sparse_generic_excel_snapshot_warns_about_missing_features(tmp_path: Path) -> None:
    workbook_path = tmp_path / "sparse.xlsx"
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Sheet1"
    sheet.append(["Company Name", "Financial Year", "Total Revenue *"])
    sheet.append(["Sparse Agro Private Limited", "2024-2025", 12.5])
    workbook.save(workbook_path)

    manifest_path = tmp_path / "manifest.csv"
    pd.DataFrame([{"provider": "generic_excel", "file_path": str(workbook_path)}]).to_csv(manifest_path, index=False)
    outputs = build_financial_dataset_from_manifest(manifest_path=manifest_path, output_dir=tmp_path / "output")

    summary = pd.read_csv(outputs["financial_summary"])
    row = summary.iloc[0]
    assert row["simulation_readiness"] == "low"
    assert row["critical_feature_coverage_pct"] < 30.0
    assert "directional" in row["accuracy_impact_note"].lower()
