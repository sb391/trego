from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd


def build_simulation_rationale_reports(
    *,
    simulation_results_path: Path,
    output_dir: Path,
) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    simulation_frame = pd.read_csv(simulation_results_path)
    report_path = output_dir / "simulation_rationale_reports.csv"

    if simulation_frame.empty:
        pd.DataFrame().to_csv(report_path, index=False)
        return {"simulation_rationale_reports": report_path}

    rows: list[dict[str, Any]] = []
    for row in simulation_frame.to_dict(orient="records"):
        snapshot = _load_snapshot(row.get("feature_snapshot_json"))
        rating = str(row.get("predicted_rating") or "")
        company_name = str(row.get("company_name") or "")
        agency = str(row.get("agency") or "")
        observations = _build_key_observations(snapshot)
        actions = _build_improvement_actions(snapshot)
        rationale = (
            f"{company_name} is simulated at {rating or 'an estimated rating'} under the {agency} lens. "
            f"The result is driven by {', '.join(observations[:3]) if observations else 'the currently available financial and qualitative signals'}."
        ).strip()
        rows.append(
            {
                "company_id": row.get("company_id"),
                "company_name": company_name,
                "agency": agency,
                "predicted_rating": rating,
                "rating_range": row.get("rating_range"),
                "confidence": row.get("confidence"),
                "population_type": row.get("population_type"),
                "rationale_summary": rationale,
                "key_observations_json": json.dumps(observations),
                "improvement_actions_json": json.dumps(actions),
            }
        )

    pd.DataFrame(rows).to_csv(report_path, index=False)
    return {"simulation_rationale_reports": report_path}


def _load_snapshot(value: Any) -> dict[str, Any]:
    if not value:
        return {}
    if isinstance(value, dict):
        return value
    try:
        parsed = json.loads(str(value))
        return parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError:
        return {}


def _build_key_observations(snapshot: dict[str, Any]) -> list[str]:
    observations: list[str] = []
    if _to_float(snapshot.get("interest_coverage")) is not None and float(snapshot["interest_coverage"]) >= 3:
        observations.append("healthy debt servicing capacity")
    if _to_float(snapshot.get("debt_to_equity")) is not None and float(snapshot["debt_to_equity"]) > 1.5:
        observations.append("elevated leverage pressure")
    if _to_float(snapshot.get("working_capital_days")) is not None and float(snapshot["working_capital_days"]) > 140:
        observations.append("stretched working capital cycle")
    if _to_float(snapshot.get("industry_ebitda_margin_percentile")) is not None and float(snapshot["industry_ebitda_margin_percentile"]) >= 0.75:
        observations.append("margins stronger than industry peers")
    if _to_float(snapshot.get("industry_interest_coverage_percentile")) is not None and float(snapshot["industry_interest_coverage_percentile"]) >= 0.75:
        observations.append("coverage stronger than peer set")
    if bool(snapshot.get("prior_agency_rating_available")):
        observations.append("historical agency rating track record available")
    if bool(snapshot.get("promoter_delinquency_flag")):
        observations.append("promoter bureau behavior indicates delinquency stress")
    if bool(snapshot.get("criminal_case_flag")):
        observations.append("legal or criminal case information requires caution")
    if bool(snapshot.get("growth_plan_aggressive_flag")):
        observations.append("five-year plan appears more aggressive than industry expectations")
    if bool(snapshot.get("plan_on_track_flag")):
        observations.append("management plan execution appears on track")
    if _to_float(snapshot.get("scale_peer_forward_revenue_cagr")) is not None:
        observations.append("listed peers at similar scale provide a usable growth benchmark")
    if _to_float(snapshot.get("projected_revenue_cagr_vs_scale_peers_gap")) is not None and float(snapshot["projected_revenue_cagr_vs_scale_peers_gap"]) > 5:
        observations.append("the submitted growth path looks aggressive versus listed peers at comparable scale")
    if bool(snapshot.get("public_risk_flag")) or ((_to_float(snapshot.get("public_risk_score")) or 0) >= 4):
        observations.append("public-domain adverse-risk signals need careful manual review")
    if _to_float(snapshot.get("regulatory_risk_score")) is not None and float(snapshot["regulatory_risk_score"]) >= 7:
        observations.append("regulatory risk appears elevated")
    return observations or ["limited signals outside the core financial profile"]


def _build_improvement_actions(snapshot: dict[str, Any]) -> list[str]:
    actions: list[str] = []
    if _to_float(snapshot.get("debt_to_equity")) is not None and float(snapshot["debt_to_equity"]) > 1.25:
        actions.append("Prioritize deleveraging and align new borrowing with visible cash generation.")
    if _to_float(snapshot.get("interest_coverage")) is not None and float(snapshot["interest_coverage"]) < 2.0:
        actions.append("Improve operating cash generation or reduce finance cost to strengthen interest coverage.")
    if _to_float(snapshot.get("working_capital_days")) is not None and float(snapshot["working_capital_days"]) > 120:
        actions.append("Tighten receivable collections and inventory discipline to improve working capital efficiency.")
    if bool(snapshot.get("promoter_delinquency_flag")):
        actions.append("Resolve promoter-level bureau delinquencies and maintain clean repayment conduct.")
    if bool(snapshot.get("criminal_case_flag")):
        actions.append("Address legal-governance issues proactively and strengthen disclosure around management integrity.")
    if bool(snapshot.get("growth_plan_aggressive_flag")):
        actions.append("Rebase the five-year business plan to more realistic industry growth assumptions and funding capacity.")
    if _to_float(snapshot.get("projected_revenue_cagr_vs_scale_peers_gap")) is not None and float(snapshot["projected_revenue_cagr_vs_scale_peers_gap"]) > 5:
        actions.append("Benchmark management projections against how listed peers historically grew from a similar revenue scale.")
    if bool(snapshot.get("public_risk_flag")) or ((_to_float(snapshot.get("public_risk_score")) or 0) >= 4):
        actions.append("Resolve or clarify public-domain adverse signals through legal, compliance, and disclosure documentation before approaching rating agencies.")
    if _to_float(snapshot.get("plan_progress_score")) is not None and float(snapshot["plan_progress_score"]) < 5:
        actions.append("Improve execution discipline against the stated business plan before pursuing a higher rating trajectory.")
    return actions or ["Maintain current leverage, coverage, and liquidity discipline while improving disclosure depth."]


def _to_float(value: Any) -> float | None:
    try:
        if value is None or (isinstance(value, float) and pd.isna(value)):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None
