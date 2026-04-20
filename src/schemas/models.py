from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class BaseSchema(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)


class Company(BaseSchema):
    company_id: str
    company_name: str
    industry: str | None = None
    sub_industry: str | None = None
    isin: str | None = None
    bse_code: str | None = None
    nse_code: str | None = None


class RatingEvent(BaseSchema):
    rating_event_id: str
    company_name: str
    agency_name: str
    rating_date: date | None = None
    instrument_type: str | None = None
    facility_amount: float | None = None
    long_term_rating: str | None = None
    short_term_rating: str | None = None
    outlook: str | None = None
    watch_status: str | None = None
    rating_action: str | None = None
    previous_rating: str | None = None
    current_rating: str | None = None
    rating_rank_numeric: int | None = None
    is_withdrawn: bool = False
    is_issuer_not_cooperating: bool = False
    rationale_doc_id: str


class RationaleDocument(BaseSchema):
    rationale_doc_id: str
    company_name: str | None = None
    agency_name: str | None = None
    doc_date: date | None = None
    source_file: str
    pdf_path: str
    parsed_status: str = "not_started"
    document_type: str | None = None
    text_hash: str


class RationaleFeatures(BaseSchema):
    rationale_doc_id: str
    agency_name: str
    company_name: str
    analytical_approach: str | None = None
    standalone_or_consolidated: str | None = None
    liquidity_label: str | None = None
    has_management_strength: bool = False
    has_group_support: bool = False
    has_scale_constraint: bool = False
    has_working_capital_pressure: bool = False
    has_liquidity_adequate: bool = False
    has_liquidity_stretched: bool = False
    has_regulatory_risk: bool = False
    has_fx_risk: bool = False
    has_customer_concentration: bool = False
    has_product_diversification: bool = False
    has_export_risk: bool = False
    has_capex_risk: bool = False
    has_margin_pressure: bool = False
    has_leverage_improvement: bool = False
    has_turnaround_story: bool = False
    has_non_cooperation_flag: bool = False
    has_contingent_liability_risk: bool = False
    has_msa_dependency: bool = False
    has_capacity_expansion: bool = False
    has_niche_complex_portfolio: bool = False
    has_strong_roce: bool = False
    has_net_cash_position: bool = False
    strengths_json: list[str] = Field(default_factory=list)
    weaknesses_json: list[str] = Field(default_factory=list)
    sensitivities_up_json: list[str] = Field(default_factory=list)
    sensitivities_down_json: list[str] = Field(default_factory=list)
    qualitative_summary: str | None = None


class ParserMessage(BaseSchema):
    severity: str
    message: str
    field_name: str | None = None
    parser_name: str | None = None


class ParsedRationaleBundle(BaseSchema):
    company: Company
    rationale_document: RationaleDocument
    rationale_features: RationaleFeatures
    rating_events: list[RatingEvent] = Field(default_factory=list)
    key_financial_indicators: dict[str, Any] = Field(default_factory=dict)
    sections: dict[str, str] = Field(default_factory=dict)
    parser_name: str
    raw_text_path: str | None = None
    extracted_text_method: str | None = None
    warnings: list[ParserMessage] = Field(default_factory=list)
    errors: list[ParserMessage] = Field(default_factory=list)
    parsed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
