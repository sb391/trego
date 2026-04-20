from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import quote

from .config import CreditIntelConfig
from .schemas import CompanyCreditProfile, RatingHistoryEntry
from .ui_schemas import (
    AdvisoryView,
    CompanyDashboardView,
    FinancialsView,
    PortfolioBatchView,
    RatingsView,
    ReportLinks,
    RiskIndicatorView,
    SimulationView,
    TredsView,
    TrendPoint,
)


def build_company_dashboard_view(
    profile: CompanyCreditProfile,
    *,
    config: CreditIntelConfig | None = None,
) -> CompanyDashboardView:
    app_config = config or CreditIntelConfig()
    rating_history = profile.rating_insight.history or [
        RatingHistoryEntry(
            rating_date=profile.rating_insight.rating_date,
            agency_name=profile.rating_insight.agency_name,
            rating=profile.rating_insight.rating,
            outlook=profile.rating_insight.outlook,
            rating_action=profile.rating_insight.rating_action,
            source="profile_summary",
        )
    ]
    rating_history = [entry for entry in rating_history if entry.rating or entry.agency_name or entry.rating_date]

    return CompanyDashboardView(
        company_id=profile.company_id,
        company_name=profile.company_name,
        requested_name=profile.requested_name,
        industry=profile.industry,
        listed_status=profile.listed_status,
        revenue=profile.financial_summary.revenue_crore,
        turnover_crore=profile.turnover_crore,
        below_threshold_flag=profile.below_threshold_flag,
        processed_at=profile.processed_at.isoformat(),
        financials=FinancialsView(
            summary=profile.financial_summary,
            tables=profile.financial_tables,
            trend_series=_build_trend_series(profile),
        ),
        ratings=RatingsView(
            available_flag=profile.rating_insight.rating_available_flag,
            status=profile.rating_insight.rating_status,
            rating=profile.rating_insight.rating,
            agency=profile.rating_insight.agency_name,
            outlook=profile.rating_insight.outlook,
            rating_date=profile.rating_insight.rating_date,
            rating_action=profile.rating_insight.rating_action,
            history=rating_history,
            notes=profile.rating_insight.notes,
        ),
        tred=TredsView(
            presence_flag=profile.treds_insight.tred_presence_flag,
            status=_build_treds_status(profile),
            platforms=profile.treds_insight.tred_platforms_detected,
            signal_strength=profile.treds_insight.tred_signal_strength,
            estimated_limit_crore=profile.treds_insight.estimated_treds_limit_crore,
            estimation_confidence=profile.treds_insight.estimation_confidence,
            method_used=profile.treds_insight.method_used,
            raw_mentions=profile.treds_insight.tred_raw_mentions,
        ),
        simulation=_build_simulation_view(profile),
        advisory=AdvisoryView(
            notes=profile.advisory_insight.advisory_notes,
            rationale_sections=profile.rationale_sections,
            rationale_draft=profile.rationale_draft,
            processing_notes=profile.processing_notes,
        ),
        risk_indicator=_build_risk_indicator(profile),
        downloads=_build_report_links(profile.company_name, app_config),
    )


def build_portfolio_batch_view(
    *,
    batch_id: str,
    profiles: list[CompanyCreditProfile],
    workbook_path: str | None = None,
    config: CreditIntelConfig | None = None,
    mock_mode: bool = False,
) -> PortfolioBatchView:
    app_config = config or CreditIntelConfig()
    return PortfolioBatchView(
        batch_id=batch_id,
        company_count=len(profiles),
        companies=[build_company_dashboard_view(profile, config=app_config) for profile in profiles],
        batch_excel_url=f"/api/ui/reports/portfolio.xlsx?batch_id={batch_id}",
        batch_zip_url=f"/api/ui/reports/portfolio.zip?batch_id={batch_id}",
        workbook_path=workbook_path,
        mock_mode=mock_mode,
    )


def load_mock_dashboard_views(
    *,
    config: CreditIntelConfig | None = None,
    limit: int = 5,
) -> list[CompanyDashboardView]:
    app_config = config or CreditIntelConfig()
    sample_path = app_config.sample_profiles_path
    if not sample_path.exists():
        return []
    payload = json.loads(sample_path.read_text(encoding="utf-8"))
    profiles = [CompanyCreditProfile.model_validate(item) for item in payload[:limit]]
    return [build_company_dashboard_view(profile, config=app_config) for profile in profiles]


def find_mock_dashboard_view(identifier: str, *, config: CreditIntelConfig | None = None) -> CompanyDashboardView | None:
    normalized = identifier.strip().lower()
    for company in load_mock_dashboard_views(config=config, limit=25):
        if normalized in {
            (company.company_id or "").lower(),
            company.company_name.lower(),
            company.requested_name.lower(),
        }:
            return company
    return None


def _build_report_links(company_name: str, config: CreditIntelConfig) -> ReportLinks:
    encoded_name = quote(company_name)
    return ReportLinks(
        excel_url=f"/api/ui/reports/company.xlsx?company_name={encoded_name}",
        pdf_url=f"/api/ui/reports/company.pdf?company_name={encoded_name}",
        word_url=f"/api/ui/reports/company.docx?company_name={encoded_name}",
    )


def _build_treds_status(profile: CompanyCreditProfile) -> str:
    if profile.treds_insight.tred_presence_flag:
        return "Observed"
    if profile.treds_insight.method_used:
        return "Estimated"
    return "No signal"


def _build_simulation_view(profile: CompanyCreditProfile) -> SimulationView:
    extra_payload = profile.model_extra or {}
    raw_simulation = extra_payload.get("simulation") if isinstance(extra_payload, dict) else None
    if isinstance(raw_simulation, dict):
        return SimulationView.model_validate(
            {
                "required_flag": raw_simulation.get("required_flag", profile.simulation_required_flag),
                "status": raw_simulation.get("status") or ("Simulation required" if profile.simulation_required_flag else "Not required"),
                "simulated_rating": raw_simulation.get("simulated_rating"),
                "rating_range": raw_simulation.get("rating_range"),
                "confidence_label": raw_simulation.get("confidence_label"),
                "confidence_score": raw_simulation.get("range_confidence_score"),
                "selected_agency": raw_simulation.get("selected_agency"),
                "range_usability_label": raw_simulation.get("range_usability_label"),
                "simulation_actionability": raw_simulation.get("simulation_actionability"),
                "ca_review_priority": raw_simulation.get("ca_review_priority"),
                "selected_agency_reason": raw_simulation.get("selected_agency_reason"),
                "rating_history_summary": raw_simulation.get("rating_history_summary"),
                "method_used": raw_simulation.get("method_used"),
                "notes": raw_simulation.get("notes") or [],
            }
        )

    notes: list[str] = []
    if profile.simulation_required_flag:
        notes.append("Backend marked this company for simulation because no current rating was available.")
        notes.append("This UI layer is display-only and does not calculate the simulated rating.")
    else:
        notes.append("Existing external rating is available, so simulation is not required.")

    return SimulationView(
        required_flag=profile.simulation_required_flag,
        status="Simulation required" if profile.simulation_required_flag else "Not required",
        simulated_rating=None,
        rating_range="Awaiting backend model output" if profile.simulation_required_flag else profile.rating_insight.rating,
        confidence_label=None,
        confidence_score=None,
        selected_agency=None,
        range_usability_label=None,
        simulation_actionability=None,
        ca_review_priority=None,
        selected_agency_reason=None,
        rating_history_summary=None,
        method_used="backend_black_box" if profile.simulation_required_flag else "external_rating_present",
        notes=notes,
    )


def _build_risk_indicator(profile: CompanyCreditProfile) -> RiskIndicatorView:
    reasons: list[str] = []
    if profile.threshold_reason:
        reasons.append(profile.threshold_reason)
    if not profile.rating_insight.rating_available_flag and profile.simulation_required_flag:
        reasons.append("External rating unavailable in current response.")
    if profile.treds_insight.tred_signal_strength:
        reasons.append(f"TReDS signal: {profile.treds_insight.tred_signal_strength}.")
    reasons.extend(profile.processing_notes[:2])

    outlook = (profile.rating_insight.outlook or "").lower()
    if profile.below_threshold_flag:
        return RiskIndicatorView(label="Below Threshold", tone="neutral", reasons=reasons)
    if "negative" in outlook or "watch" in outlook:
        return RiskIndicatorView(label="Watch", tone="high", reasons=reasons)
    if profile.simulation_required_flag and not profile.rating_insight.rating_available_flag:
        return RiskIndicatorView(label="Needs Simulation", tone="medium", reasons=reasons)
    if profile.rating_insight.rating_available_flag:
        return RiskIndicatorView(label="Rated", tone="low", reasons=reasons)
    return RiskIndicatorView(label="Review", tone="neutral", reasons=reasons)


def _build_trend_series(profile: CompanyCreditProfile) -> dict[str, list[TrendPoint]]:
    profit_loss_rows = list(profile.financial_tables.get("profit_loss", []))
    if not profit_loss_rows:
        return {}

    revenue_points = _extract_series(profit_loss_rows, ("period", "date", "year"), ("sales", "revenue"))
    profit_points = _extract_series(profit_loss_rows, ("period", "date", "year"), ("net_profit", "profit_after_tax"))
    opm_points = _extract_series(profit_loss_rows, ("period", "date", "year"), ("opm_percent", "opm"))

    output: dict[str, list[TrendPoint]] = {}
    if revenue_points:
        output["revenue"] = revenue_points
    if profit_points:
        output["net_profit"] = profit_points
    if opm_points:
        output["opm_percent"] = opm_points
    return output


def _extract_series(
    rows: list[dict[str, object]],
    label_keys: tuple[str, ...],
    value_keys: tuple[str, ...],
) -> list[TrendPoint]:
    points: list[TrendPoint] = []
    for row in rows[-10:]:
        label = next((str(row.get(key) or "").strip() for key in label_keys if row.get(key)), "")
        value = next((_to_float(row.get(key)) for key in value_keys if row.get(key) is not None), None)
        if label:
            points.append(TrendPoint(label=label, value=value))
    return points


def _to_float(value: object) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
