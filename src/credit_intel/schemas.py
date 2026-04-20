from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class CreditIntelModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="allow")


class MatchedDatasetCompany(CreditIntelModel):
    company_id: str
    company_name: str
    normalized_name: str
    match_confidence: float | None = None
    cin: str | None = None
    pan: str | None = None
    listing_status: str | None = None
    status: str | None = None
    city: str | None = None
    state: str | None = None
    products: str | None = None
    sector: str | None = None
    business_type: str | None = None
    financial_year: str | None = None
    latest_balance_sheet: str | None = None
    standalone_or_consolidated: str | None = None
    total_revenue_crore: float | None = None
    ebitda_crore: float | None = None
    pat_crore: float | None = None
    networth_crore: float | None = None
    total_borrowings_crore: float | None = None
    long_term_liabilities_crore: float | None = None
    paid_up_capital_crore: float | None = None
    revenue_growth_pct: float | None = None
    ebitda_margin_pct: float | None = None
    pat_margin_pct: float | None = None
    debt_to_equity: float | None = None
    debt_to_ebitda: float | None = None
    interest_coverage: float | None = None
    receivables_days: float | None = None
    inventory_days: float | None = None
    current_ratio: float | None = None
    roe_pct: float | None = None
    roce_pct: float | None = None
    credit_rated_flag: bool | None = None
    latest_ratings_text: str | None = None
    email: str | None = None
    phone: str | None = None
    website: str | None = None
    address: str | None = None
    raw_row: dict[str, Any] = Field(default_factory=dict)


class FinancialSummary(CreditIntelModel):
    revenue_crore: float | None = None
    ebitda_margin_pct: float | None = None
    pat_margin_pct: float | None = None
    debt_to_equity: float | None = None
    interest_coverage: float | None = None
    working_capital_days: float | None = None
    receivables_days: float | None = None
    inventory_days: float | None = None
    current_price: float | None = None
    market_cap_crore: float | None = None
    networth_crore: float | None = None
    total_borrowings_crore: float | None = None
    source: str | None = None
    statement_period: str | None = None


class RatingHistoryEntry(CreditIntelModel):
    rating_date: str | None = None
    agency_name: str | None = None
    rating: str | None = None
    outlook: str | None = None
    rating_action: str | None = None
    source_url: str | None = None
    current_rating_text: str | None = None
    rationale_summary: str | None = None
    source: str | None = None


class RatingInsight(CreditIntelModel):
    rating_available_flag: bool = False
    rating_status: str = "not_available"
    agency_name: str | None = None
    rating: str | None = None
    outlook: str | None = None
    rating_date: str | None = None
    rating_action: str | None = None
    history: list[RatingHistoryEntry] = Field(default_factory=list)
    rationale_features: dict[str, Any] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)


class TredsInsight(CreditIntelModel):
    tred_presence_flag: bool = False
    tred_platforms_detected: list[str] = Field(default_factory=list)
    tred_signal_strength: str = "low"
    tred_raw_mentions: list[str] = Field(default_factory=list)
    estimated_treds_limit_crore: float | None = None
    estimation_confidence: str | None = None
    method_used: str | None = None


class ListedInsight(CreditIntelModel):
    listed_status: str = "unknown"
    screener_url: str | None = None
    screener_match_confidence: float | None = None
    workbook_path: str | None = None
    workbook_available: bool = False
    source: str | None = None


class AdvisoryInsight(CreditIntelModel):
    advisory_notes: list[str] = Field(default_factory=list)


class RationaleSection(CreditIntelModel):
    heading: str
    body: str


class CompanyCreditProfile(CreditIntelModel):
    company_name: str
    requested_name: str
    company_id: str | None = None
    industry: str | None = None
    listed_status: str = "unknown"
    turnover_crore: float | None = None
    matched_company: MatchedDatasetCompany | None = None
    below_threshold_flag: bool = False
    threshold_reason: str | None = None
    listed_insight: ListedInsight | None = None
    financial_summary: FinancialSummary = Field(default_factory=FinancialSummary)
    rating_insight: RatingInsight = Field(default_factory=RatingInsight)
    treds_insight: TredsInsight = Field(default_factory=TredsInsight)
    simulation_required_flag: bool = False
    advisory_insight: AdvisoryInsight = Field(default_factory=AdvisoryInsight)
    rationale_sections: list[RationaleSection] = Field(default_factory=list)
    rationale_draft: str | None = None
    financial_tables: dict[str, list[dict[str, Any]]] = Field(default_factory=dict)
    processing_notes: list[str] = Field(default_factory=list)
    processed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class BatchProcessRequest(CreditIntelModel):
    company_names: list[str]


class BatchProcessResponse(CreditIntelModel):
    batch_id: str
    company_count: int
    profiles: list[CompanyCreditProfile]
    workbook_path: str | None = None
