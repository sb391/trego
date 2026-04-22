#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = ROOT / "outputs" / "consolidated_listed_250cr_profitable" / "reports" / "consolidated_106_companies_master.csv"
DEFAULT_OUTPUT = ROOT / "frontend" / "supabase" / "seeds" / "agri_master"


def clean(value: str | None) -> str | None:
  if value is None:
    return None
  stripped = value.strip()
  return stripped or None


def to_number(value: str | None) -> float | None:
  text = clean(value)
  if text is None:
    return None
  try:
    return float(text)
  except ValueError:
    return None


def to_bool(value: str | None) -> bool | None:
  text = (clean(value) or "").lower()
  if not text:
    return None
  return text in {"1", "true", "yes", "y"}


def normalize_company_name(value: str | None) -> str:
  text = clean(value) or ""
  normalized = re.sub(r"[^a-z0-9]+", " ", text.lower())
  return re.sub(r"\s+", " ", normalized).strip()


def write_json(path: Path, payload: Any) -> None:
  path.write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")


def build_payload(source_file: Path) -> dict[str, Any]:
  companies: list[dict[str, Any]] = []
  financials: list[dict[str, Any]] = []
  ratings: list[dict[str, Any]] = []
  simulations: list[dict[str, Any]] = []
  secretaries: list[dict[str, Any]] = []
  master_rows: list[dict[str, Any]] = []

  with source_file.open(newline="", encoding="utf-8") as handle:
    reader = csv.DictReader(handle)

    for row in reader:
      company_id = clean(row.get("company_id")) or normalize_company_name(row.get("company_name")).replace(" ", "_")
      company_name = clean(row.get("company_name")) or company_id
      normalized_name = normalize_company_name(company_name)

      company = {
        "company_id": company_id,
        "company_name": company_name,
        "normalized_company_name": normalized_name,
        "nse_code": clean(row.get("nse_code")),
        "bse_code": clean(row.get("bse_code")),
        "screener_url": clean(row.get("screener_url")),
        "company_workbook_path": clean(row.get("company_workbook_path")),
        "source_batch": clean(row.get("source_batch")),
        "industry_key": clean(row.get("industry_key")),
        "industry_name": clean(row.get("industry_name")),
        "industry_group": clean(row.get("industry_group")),
        "sub_industry": clean(row.get("sub_industry")),
        "annual_report_url": clean(row.get("annual_report_url")),
        "annual_report_label": clean(row.get("annual_report_label")),
      }
      companies.append(company)

      financials.append({
        "company_id": company_id,
        "period": clean(row.get("period")),
        "revenue_crore": to_number(row.get("revenue_crore")),
        "net_profit": to_number(row.get("net_profit")),
        "ebitda_margin_pct": to_number(row.get("ebitda_margin_pct")),
        "pat_margin_pct": to_number(row.get("pat_margin_pct")),
        "debt_to_equity": to_number(row.get("debt_to_equity")),
        "interest_coverage": to_number(row.get("interest_coverage")),
        "working_capital_days": to_number(row.get("working_capital_days")),
        "receivables_days": to_number(row.get("receivables_days")),
        "inventory_days": to_number(row.get("inventory_days")),
        "networth_crore": to_number(row.get("networth_crore")),
        "total_borrowings_crore": to_number(row.get("total_borrowings_crore")),
        "total_assets_crore": to_number(row.get("total_assets_crore")),
        "current_price": to_number(row.get("current_price")),
        "market_cap_crore": to_number(row.get("market_cap_crore")),
        "revenue_growth_pct": to_number(row.get("revenue_growth_pct")),
        "profit_growth_pct": to_number(row.get("profit_growth_pct")),
        "is_latest": True,
      })

      if clean(row.get("latest_cra_rating_status")) or clean(row.get("latest_cra_rating")):
        ratings.append({
          "company_id": company_id,
          "rating_status": clean(row.get("latest_cra_rating_status")),
          "agency": clean(row.get("latest_cra_rating_agency")),
          "rating": clean(row.get("latest_cra_rating")),
          "rating_date": clean(row.get("latest_cra_rating_date")),
          "rating_month_year": clean(row.get("latest_cra_rating_month_year")),
          "source": clean(row.get("latest_cra_rating_source")),
          "source_url": clean(row.get("latest_cra_rating_source_url")),
          "history_count": int(float(row.get("cra_history_count"))) if clean(row.get("cra_history_count")) else None,
          "is_latest": True,
        })

      if clean(row.get("simulated_rating")) or clean(row.get("published_range")) or clean(row.get("calibrated_range")):
        simulations.append({
          "company_id": company_id,
          "simulation_required_flag": to_bool(row.get("simulation_required_flag")),
          "simulated_rating_agency": clean(row.get("simulated_rating_agency")),
          "simulated_rating": clean(row.get("simulated_rating")),
          "calibrated_range": clean(row.get("calibrated_range")),
          "published_range": clean(row.get("published_range")),
          "range_confidence_label": clean(row.get("range_confidence_label")),
          "range_usability_label": clean(row.get("range_usability_label")),
          "ca_review_priority": clean(row.get("ca_review_priority")),
          "manual_review_required_flag": to_bool(row.get("manual_review_required_flag")),
          "manual_review_reason": clean(row.get("manual_review_reason")),
          "is_latest": True,
        })

      if clean(row.get("company_secretary_name")) or clean(row.get("company_secretary_contact_details")):
        secretaries.append({
          "company_id": company_id,
          "name": clean(row.get("company_secretary_name")),
          "contact_details": clean(row.get("company_secretary_contact_details")),
          "source_type": clean(row.get("company_secretary_source_type")),
          "source_url": clean(row.get("company_secretary_source_url")),
          "notes": clean(row.get("company_secretary_notes")),
          "annual_report_url": clean(row.get("annual_report_url")),
          "annual_report_label": clean(row.get("annual_report_label")),
          "is_latest": True,
        })

      master_rows.append({
        **row,
        "company_id": company_id,
        "company_name": company_name,
        "normalized_company_name": normalized_name,
        "revenue_crore": to_number(row.get("revenue_crore")),
        "net_profit": to_number(row.get("net_profit")),
        "ebitda_margin_pct": to_number(row.get("ebitda_margin_pct")),
        "pat_margin_pct": to_number(row.get("pat_margin_pct")),
        "debt_to_equity": to_number(row.get("debt_to_equity")),
        "interest_coverage": to_number(row.get("interest_coverage")),
        "working_capital_days": to_number(row.get("working_capital_days")),
        "receivables_days": to_number(row.get("receivables_days")),
        "inventory_days": to_number(row.get("inventory_days")),
        "networth_crore": to_number(row.get("networth_crore")),
        "total_borrowings_crore": to_number(row.get("total_borrowings_crore")),
        "total_assets_crore": to_number(row.get("total_assets_crore")),
        "current_price": to_number(row.get("current_price")),
        "market_cap_crore": to_number(row.get("market_cap_crore")),
        "revenue_growth_pct": to_number(row.get("revenue_growth_pct")),
        "profit_growth_pct": to_number(row.get("profit_growth_pct")),
        "simulation_required_flag": to_bool(row.get("simulation_required_flag")),
        "manual_review_required_flag": to_bool(row.get("manual_review_required_flag")),
        "listed_status": "Listed" if clean(row.get("nse_code")) or clean(row.get("bse_code")) else "Unlisted",
      })

  return {
    "agri_companies": companies,
    "agri_financial_snapshots": financials,
    "agri_actual_ratings": ratings,
    "agri_simulations": simulations,
    "agri_company_secretaries": secretaries,
    "agri_company_master_rows": master_rows,
    "manifest": {
      "source_file": str(source_file),
      "company_count": len(companies),
      "financial_snapshot_count": len(financials),
      "rating_count": len(ratings),
      "simulation_count": len(simulations),
      "secretary_count": len(secretaries),
    },
  }


def main() -> None:
  parser = argparse.ArgumentParser(description="Prepare normalized agri master import payloads for Supabase.")
  parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE, help="Path to the consolidated agri master CSV")
  parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT, help="Directory for normalized JSON outputs")
  args = parser.parse_args()

  payload = build_payload(args.source)
  args.output_dir.mkdir(parents=True, exist_ok=True)

  for key, value in payload.items():
    write_json(args.output_dir / f"{key}.json", value)

  print(f"Wrote normalized import payloads to {args.output_dir}")


if __name__ == "__main__":
  main()
