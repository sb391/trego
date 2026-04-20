from __future__ import annotations

from typing import Any

from pydantic import Field

from .schemas import CreditIntelModel, FinancialSummary, RatingHistoryEntry, RationaleSection


class ReportLinks(CreditIntelModel):
    excel_url: str
    pdf_url: str
    word_url: str


class TrendPoint(CreditIntelModel):
    label: str
    value: float | None = None


class FinancialsView(CreditIntelModel):
    summary: FinancialSummary = Field(default_factory=FinancialSummary)
    tables: dict[str, list[dict[str, Any]]] = Field(default_factory=dict)
    trend_series: dict[str, list[TrendPoint]] = Field(default_factory=dict)


class RatingsView(CreditIntelModel):
    available_flag: bool = False
    status: str = "not_available"
    rating: str | None = None
    agency: str | None = None
    outlook: str | None = None
    rating_date: str | None = None
    rating_action: str | None = None
    history: list[RatingHistoryEntry] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class TredsView(CreditIntelModel):
    presence_flag: bool = False
    status: str = "No signal"
    platforms: list[str] = Field(default_factory=list)
    signal_strength: str = "low"
    estimated_limit_crore: float | None = None
    estimation_confidence: str | None = None
    method_used: str | None = None
    raw_mentions: list[str] = Field(default_factory=list)


class SimulationView(CreditIntelModel):
    required_flag: bool = False
    status: str = "Not required"
    simulated_rating: str | None = None
    rating_range: str | None = None
    confidence_label: str | None = None
    confidence_score: float | None = None
    selected_agency: str | None = None
    range_usability_label: str | None = None
    simulation_actionability: str | None = None
    ca_review_priority: str | None = None
    selected_agency_reason: str | None = None
    rating_history_summary: str | None = None
    method_used: str | None = None
    notes: list[str] = Field(default_factory=list)


class RiskIndicatorView(CreditIntelModel):
    label: str = "Review"
    tone: str = "neutral"
    reasons: list[str] = Field(default_factory=list)


class AdvisoryView(CreditIntelModel):
    notes: list[str] = Field(default_factory=list)
    rationale_sections: list[RationaleSection] = Field(default_factory=list)
    rationale_draft: str | None = None
    processing_notes: list[str] = Field(default_factory=list)


class CompanyDashboardView(CreditIntelModel):
    company_id: str | None = None
    company_name: str
    requested_name: str
    industry: str | None = None
    listed_status: str = "unknown"
    revenue: float | None = None
    turnover_crore: float | None = None
    below_threshold_flag: bool = False
    processed_at: str | None = None
    financials: FinancialsView = Field(default_factory=FinancialsView)
    ratings: RatingsView = Field(default_factory=RatingsView)
    tred: TredsView = Field(default_factory=TredsView)
    simulation: SimulationView = Field(default_factory=SimulationView)
    advisory: AdvisoryView = Field(default_factory=AdvisoryView)
    risk_indicator: RiskIndicatorView = Field(default_factory=RiskIndicatorView)
    downloads: ReportLinks


class PortfolioBatchView(CreditIntelModel):
    batch_id: str
    company_count: int
    companies: list[CompanyDashboardView] = Field(default_factory=list)
    batch_excel_url: str | None = None
    batch_zip_url: str | None = None
    workbook_path: str | None = None
    mock_mode: bool = False
