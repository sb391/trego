from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import pandas as pd

from .financial_document_parser import parse_financial_document


LOGGER = logging.getLogger(__name__)

CRITICAL_FEATURE_COLUMNS = [
    "revenue_crore",
    "ebitda_margin_pct",
    "pat_margin_pct",
    "debt_to_equity",
    "interest_coverage",
    "networth_crore",
    "total_borrowings_crore",
    "current_ratio",
    "receivables_days",
    "inventory_days",
]


def build_financial_dataset_from_manifest(
    *,
    manifest_path: Path,
    output_dir: Path,
    parsed_json_dir: Path | None = None,
) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    if parsed_json_dir is None:
        parsed_json_dir = output_dir / "parsed_documents"
    parsed_json_dir.mkdir(parents=True, exist_ok=True)

    manifest_frame = pd.read_csv(manifest_path)
    if manifest_frame.empty:
        raise ValueError(f"Manifest has no rows: {manifest_path}")
    if "file_path" not in manifest_frame.columns:
        raise ValueError("Manifest must contain a file_path column.")

    profit_loss_rows: list[dict[str, Any]] = []
    balance_sheet_rows: list[dict[str, Any]] = []
    cash_flow_rows: list[dict[str, Any]] = []
    ratio_rows: list[dict[str, Any]] = []
    financial_parameter_rows: list[dict[str, Any]] = []
    summary_rows: list[dict[str, Any]] = []
    annual_feature_rows: list[dict[str, Any]] = []
    status_rows: list[dict[str, Any]] = []

    for row_index, row in enumerate(manifest_frame.to_dict(orient="records"), start=1):
        file_path = Path(str(row.get("file_path") or "")).expanduser()
        provider_name = str(row.get("provider") or "").strip() or None
        company_id = str(row.get("company_id") or "").strip() or f"row_{row_index:04d}"
        if not file_path.exists():
            status_rows.append(
                {
                    "company_id": company_id,
                    "file_path": str(file_path),
                    "provider": provider_name,
                    "status": "missing_file",
                    "notes": "Input file does not exist.",
                }
            )
            continue

        try:
            parsed = parse_financial_document(file_path, provider_name=provider_name)
        except Exception as exc:  # noqa: BLE001
            LOGGER.warning("Failed to parse %s: %s", file_path, exc)
            status_rows.append(
                {
                    "company_id": company_id,
                    "file_path": str(file_path),
                    "provider": provider_name,
                    "status": "parse_failed",
                    "notes": str(exc),
                }
            )
            continue

        parsed_json_path = parsed_json_dir / f"{company_id}.json"
        parsed_json_path.write_text(json.dumps(parsed, indent=2, default=str), encoding="utf-8")

        document_meta = dict(row)
        document_meta.update(
            {
                "company_id": company_id,
                "file_path": str(file_path),
                "provider": str((parsed.get("meta") or {}).get("source_provider") or provider_name or ""),
            }
        )

        for payload_index, company_payload in enumerate(_iter_company_payloads(parsed), start=1):
            company_meta = _merge_company_meta(document_meta, company_payload, payload_index)
            company_feature_rows = _build_annual_feature_rows(company_meta, company_payload)
            latest_feature_row = company_feature_rows[-1] if company_feature_rows else {}
            summary_row = {
                **_company_meta(company_meta),
                **company_payload["financial_summary"],
                "provider": company_meta.get("provider"),
                "document_path": str(file_path),
                "parsed_json_path": str(parsed_json_path),
                "raw_provider": company_meta.get("provider"),
            }
            summary_row.update(_quality_fields(latest_feature_row or summary_row))
            summary_row["statement_granularity"] = _statement_granularity(company_payload)
            summary_rows.append(summary_row)

            for statement_name, rows, collector in (
                ("profit_loss", company_payload.get("profit_loss", []), profit_loss_rows),
                ("balance_sheet", company_payload.get("balance_sheet", []), balance_sheet_rows),
                ("cash_flow", company_payload.get("cash_flow", []), cash_flow_rows),
                ("ratios", company_payload.get("ratios", []), ratio_rows),
                ("financial_parameters", company_payload.get("financial_parameters", []), financial_parameter_rows),
            ):
                for item in rows:
                    collector.append(
                        {
                            **_company_meta(company_meta),
                            "provider": company_meta.get("provider"),
                            "statement_type": statement_name,
                            **item,
                        }
                    )

            annual_feature_rows.extend(company_feature_rows)
            quality = _quality_fields(latest_feature_row or summary_row)
            status_rows.append(
                {
                    "company_id": company_meta.get("company_id"),
                    "company_name": company_meta.get("company_name"),
                    "file_path": str(file_path),
                    "provider": company_meta.get("provider"),
                    "status": "parsed",
                    "statement_granularity": summary_row["statement_granularity"],
                    "critical_feature_coverage_pct": quality["critical_feature_coverage_pct"],
                    "simulation_readiness": quality["simulation_readiness"],
                    "notes": quality["accuracy_impact_note"],
                }
            )

    output_paths = {
        "financial_summary": output_dir / "financial_summary.csv",
        "profit_loss_annual": output_dir / "profit_loss_annual.csv",
        "balance_sheet_annual": output_dir / "balance_sheet_annual.csv",
        "cash_flow_annual": output_dir / "cash_flow_annual.csv",
        "ratios_annual": output_dir / "ratios_annual.csv",
        "financial_parameters_annual": output_dir / "financial_parameters_annual.csv",
        "financial_year_features": output_dir / "financial_year_features.csv",
        "latest_financial_features": output_dir / "latest_financial_features.csv",
        "document_parse_status": output_dir / "document_parse_status.csv",
    }

    pd.DataFrame(summary_rows).to_csv(output_paths["financial_summary"], index=False)
    pd.DataFrame(profit_loss_rows).to_csv(output_paths["profit_loss_annual"], index=False)
    pd.DataFrame(balance_sheet_rows).to_csv(output_paths["balance_sheet_annual"], index=False)
    pd.DataFrame(cash_flow_rows).to_csv(output_paths["cash_flow_annual"], index=False)
    pd.DataFrame(ratio_rows).to_csv(output_paths["ratios_annual"], index=False)
    pd.DataFrame(financial_parameter_rows).to_csv(output_paths["financial_parameters_annual"], index=False)
    pd.DataFrame(status_rows).to_csv(output_paths["document_parse_status"], index=False)

    features_frame = pd.DataFrame(annual_feature_rows)
    if not features_frame.empty:
        features_frame = features_frame.sort_values(["company_id", "period_date"])
    features_frame.to_csv(output_paths["financial_year_features"], index=False)
    latest_frame = features_frame.groupby("company_id", as_index=False).tail(1) if not features_frame.empty else features_frame
    latest_frame.to_csv(output_paths["latest_financial_features"], index=False)
    return output_paths


def _build_annual_feature_rows(meta_record: dict[str, Any], parsed: dict[str, Any]) -> list[dict[str, Any]]:
    pnl_by_period = {str(item.get("period")): item for item in parsed.get("profit_loss", [])}
    bs_by_period = {str(item.get("period")): item for item in parsed.get("balance_sheet", [])}
    cf_by_period = {str(item.get("period")): item for item in parsed.get("cash_flow", [])}
    ratios_by_period = {str(item.get("period")): item for item in parsed.get("ratios", [])}

    periods = sorted(
        {
            period
            for period in [*pnl_by_period.keys(), *bs_by_period.keys(), *cf_by_period.keys(), *ratios_by_period.keys()]
            if period and period != "None"
        }
    )

    rows: list[dict[str, Any]] = []
    for index, period in enumerate(periods):
        pnl = pnl_by_period.get(period, {})
        balance = bs_by_period.get(period, {})
        cash = cf_by_period.get(period, {})
        ratios = ratios_by_period.get(period, {})
        previous_pnl = pnl_by_period.get(periods[index - 1], {}) if index > 0 else {}

        sales = _to_float(pnl.get("sales"))
        operating_profit = _to_float(pnl.get("operating_profit"))
        interest = _to_float(pnl.get("interest"))
        net_profit = _to_float(pnl.get("net_profit"))
        networth = _safe_sum([
            _to_float(balance.get("equity_share_capital")),
            _to_float(balance.get("reserves")),
            _to_float(balance.get("other_equity")),
        ])
        borrowings = _to_float(balance.get("borrowings"))
        total_assets = _to_float(balance.get("total"))
        receivables_days = _to_float(ratios.get("receivables_days")) or _ratio_days(_to_float(balance.get("receivables")), sales)
        inventory_days = _to_float(ratios.get("inventory_days")) or _ratio_days(_to_float(balance.get("inventory")), sales)
        payables_days = _to_float(ratios.get("payables_days"))
        cfo = _to_float(cash.get("cash_from_operating_activity"))
        previous_sales = _to_float(previous_pnl.get("sales"))
        previous_profit = _to_float(previous_pnl.get("net_profit"))

        row = {
            **_company_meta(meta_record),
            "provider": meta_record.get("provider"),
            "period": period,
            "period_date": period,
            "revenue_crore": sales,
            "ebitda_margin_pct": _to_float(ratios.get("ebitda_margin_pct")) or _ratio_pct(operating_profit, sales),
            "pat_margin_pct": _to_float(ratios.get("pat_margin_pct")) or _ratio_pct(net_profit, sales),
            "debt_to_equity": _to_float(ratios.get("debt_to_equity")) or _safe_ratio(borrowings, networth),
            "interest_coverage": _to_float(ratios.get("interest_coverage")) or _safe_ratio(operating_profit, interest),
            "working_capital_days": _working_capital_days(receivables_days, inventory_days, payables_days),
            "receivables_days": receivables_days,
            "inventory_days": inventory_days,
            "networth_crore": networth,
            "total_borrowings_crore": borrowings,
            "total_assets_crore": total_assets,
            "cfo_to_debt": _safe_ratio(cfo, borrowings),
            "cash_to_borrowings": _safe_ratio(_to_float(balance.get("cash_and_bank")), borrowings),
            "asset_turnover": _safe_ratio(sales, total_assets),
            "current_ratio": _to_float(ratios.get("current_ratio")),
            "roe_pct": _to_float(ratios.get("roe_pct")),
            "roce_pct": _to_float(ratios.get("roce_pct")),
            "revenue_growth_pct": _to_float(ratios.get("revenue_growth_pct")) or _growth_pct(sales, previous_sales),
            "profit_growth_pct": _growth_pct(net_profit, previous_profit),
        }
        row.update(_quality_fields(row))
        rows.append(row)
    return rows


def _iter_company_payloads(parsed: dict[str, Any]) -> list[dict[str, Any]]:
    companies = parsed.get("companies")
    if isinstance(companies, list) and companies:
        return [item for item in companies if isinstance(item, dict)]
    return [parsed]


def _merge_company_meta(document_meta: dict[str, Any], payload: dict[str, Any], payload_index: int) -> dict[str, Any]:
    parsed_meta = dict(payload.get("meta") or {})
    company_id = str(
        parsed_meta.get("company_id")
        or document_meta.get("company_id")
        or f"row_{payload_index:04d}"
    ).strip()
    company_name = parsed_meta.get("company_name") or document_meta.get("company_name")
    return {
        **document_meta,
        **parsed_meta,
        "company_id": company_id,
        "company_name": company_name,
        "industry_group": document_meta.get("industry_group") or parsed_meta.get("industry"),
        "sub_industry": document_meta.get("sub_industry") or parsed_meta.get("segment") or parsed_meta.get("industry"),
        "nse_code": document_meta.get("nse_code"),
        "bse_code": document_meta.get("bse_code"),
        "provider": parsed_meta.get("source_provider") or document_meta.get("provider"),
    }


def _quality_fields(record: dict[str, Any]) -> dict[str, Any]:
    present = [column for column in CRITICAL_FEATURE_COLUMNS if _to_float(record.get(column)) is not None]
    missing = [column for column in CRITICAL_FEATURE_COLUMNS if column not in present]
    coverage_pct = round((len(present) / len(CRITICAL_FEATURE_COLUMNS)) * 100.0, 2)
    if coverage_pct >= 80:
        readiness = "high"
        note = "Most core financial drivers are available; simulation accuracy should hold up better."
    elif coverage_pct >= 60:
        readiness = "medium"
        note = "Some core financial drivers are missing; simulation can still run, but confidence and accuracy may reduce."
    else:
        readiness = "low"
        note = "Many core financial drivers are missing; treat simulated output as directional and review manually."
    return {
        "critical_feature_coverage_pct": coverage_pct,
        "critical_feature_count_present": len(present),
        "critical_feature_count_total": len(CRITICAL_FEATURE_COLUMNS),
        "missing_critical_features": json.dumps(missing),
        "simulation_readiness": readiness,
        "accuracy_impact_note": note,
    }


def _statement_granularity(parsed: dict[str, Any]) -> str:
    periods = set()
    for section in ("profit_loss", "balance_sheet", "cash_flow", "ratios"):
        for item in parsed.get(section, []):
            period = str(item.get("period") or "").strip()
            if period:
                periods.add(period)
    if len(periods) >= 3:
        return "multi_year_statement"
    if len(periods) == 1:
        return "latest_snapshot"
    if periods:
        return "limited_history"
    return "summary_only"


def _company_meta(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "company_id": record.get("company_id"),
        "company_name": record.get("company_name"),
        "nse_code": _string(record.get("nse_code")),
        "bse_code": _string(record.get("bse_code")),
        "industry_group": record.get("industry_group"),
        "sub_industry": record.get("sub_industry"),
    }


def _string(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _ratio_pct(numerator: float | None, denominator: float | None) -> float | None:
    ratio = _safe_ratio(numerator, denominator)
    return round(ratio * 100.0, 4) if ratio is not None else None


def _ratio_days(numerator: float | None, denominator: float | None) -> float | None:
    ratio = _safe_ratio(numerator, denominator)
    return round(ratio * 365.0, 4) if ratio is not None else None


def _safe_ratio(numerator: float | None, denominator: float | None) -> float | None:
    if numerator is None or denominator in {None, 0}:
        return None
    return round(float(numerator) / float(denominator), 6)


def _safe_sum(values: list[float | None]) -> float | None:
    clean = [value for value in values if value is not None]
    if not clean:
        return None
    return round(float(sum(clean)), 6)


def _growth_pct(current: float | None, previous: float | None) -> float | None:
    if current is None or previous in {None, 0}:
        return None
    return round(((float(current) - float(previous)) / abs(float(previous))) * 100.0, 4)


def _to_float(value: Any) -> float | None:
    try:
        if value is None or (isinstance(value, float) and pd.isna(value)):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _working_capital_days(
    receivables_days: float | None,
    inventory_days: float | None,
    payables_days: float | None,
) -> float | None:
    if receivables_days is None and inventory_days is None:
        return None
    if payables_days is not None:
        return round(float(receivables_days or 0.0) + float(inventory_days or 0.0) - float(payables_days), 4)
    return round(float(receivables_days or 0.0) + float(inventory_days or 0.0), 4)
