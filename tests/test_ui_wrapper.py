from __future__ import annotations

from pathlib import Path
import zipfile

from src.credit_intel.config import CreditIntelConfig
from src.credit_intel.schemas import AdvisoryInsight, CompanyCreditProfile, FinancialSummary, RatingInsight, TredsInsight
from src.credit_intel.ui_exports import PresentationReportExporter
from src.credit_intel.ui_wrapper import build_company_dashboard_view, build_portfolio_batch_view


def _build_profile() -> CompanyCreditProfile:
    return CompanyCreditProfile(
        company_name="Demo Agro Limited",
        requested_name="Demo Agro Limited",
        company_id="demo-1",
        industry="Edible Oil",
        listed_status="listed",
        turnover_crore=512.4,
        financial_summary=FinancialSummary(
            revenue_crore=512.4,
            ebitda_margin_pct=8.6,
            pat_margin_pct=3.2,
            debt_to_equity=0.84,
            interest_coverage=3.1,
            working_capital_days=92.0,
        ),
        rating_insight=RatingInsight(
            rating_available_flag=True,
            rating_status="available",
            agency_name="CRISIL",
            rating="BBB+",
            outlook="Stable",
            rating_date="2025-07-02",
            rating_action="Reaffirmed",
        ),
        treds_insight=TredsInsight(
            tred_presence_flag=True,
            tred_platforms_detected=["RXIL"],
            tred_signal_strength="high",
            estimated_treds_limit_crore=74.2,
            estimation_confidence="high",
            method_used="proxy",
            tred_raw_mentions=["RXIL participation disclosed"],
        ),
        simulation_required_flag=False,
        advisory_insight=AdvisoryInsight(advisory_notes=["Maintain leverage discipline."]),
        rationale_draft="Demo rationale.",
        financial_tables={
            "profit_loss": [
                {"period": "2024-03-31", "sales": 480.0, "net_profit": 14.1, "opm_percent": 7.8},
                {"period": "2025-03-31", "sales": 512.4, "net_profit": 16.4, "opm_percent": 8.6},
            ]
        },
        processing_notes=["Demo note."],
    )


def test_build_company_dashboard_view_exposes_downloads() -> None:
    view = build_company_dashboard_view(_build_profile(), config=CreditIntelConfig())
    assert view.company_name == "Demo Agro Limited"
    assert view.downloads.excel_url.endswith("company.xlsx?company_name=Demo%20Agro%20Limited")
    assert view.financials.trend_series["revenue"][-1].value == 512.4
    assert view.ratings.rating == "BBB+"


def test_build_portfolio_batch_view_exposes_batch_report_links() -> None:
    config = CreditIntelConfig()
    batch = build_portfolio_batch_view(batch_id="batch-123", profiles=[_build_profile()], config=config)
    assert batch.batch_excel_url == "/api/ui/reports/portfolio.xlsx?batch_id=batch-123"
    assert batch.batch_zip_url == "/api/ui/reports/portfolio.zip?batch_id=batch-123"


def test_presentation_report_exporter_generates_files(tmp_path: Path) -> None:
    config = CreditIntelConfig(data_dir=tmp_path / "data", outputs_dir=tmp_path / "outputs")
    config.ensure_directories()
    company = build_company_dashboard_view(_build_profile(), config=config)
    exporter = PresentationReportExporter(config)

    excel_path = exporter.export_excel(company)
    word_path = exporter.export_word(company)
    pdf_path = exporter.export_pdf(company)

    assert excel_path.exists()
    assert word_path.exists()
    assert pdf_path.exists()


def test_presentation_report_exporter_generates_portfolio_excel_and_zip(tmp_path: Path) -> None:
    config = CreditIntelConfig(data_dir=tmp_path / "data", outputs_dir=tmp_path / "outputs")
    config.ensure_directories()
    exporter = PresentationReportExporter(config)
    companies = [
        build_company_dashboard_view(_build_profile(), config=config),
        build_company_dashboard_view(
            _build_profile().model_copy(update={"company_name": "Demo Agro Foods", "company_id": "demo-2"}),
            config=config,
        ),
    ]

    workbook_path = exporter.export_portfolio_excel("batch-portfolio", companies)
    archive_path = exporter.export_portfolio_zip("batch-portfolio", companies)

    assert workbook_path.exists()
    assert archive_path.exists()

    with zipfile.ZipFile(archive_path) as archive:
        members = set(archive.namelist())

    assert "portfolio_reports/summary.xlsx" in members
    assert any(member.endswith("__dashboard.pdf") for member in members)
    assert any(member.endswith("__dashboard.docx") for member in members)
