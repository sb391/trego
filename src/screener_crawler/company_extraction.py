from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlsplit

import pandas as pd
from bs4 import BeautifulSoup

from .config import PARSER_VERSION, SCREENER_BASE_URL
from .discovery import extract_company_slug
from .http import RobotsDisallowedError, RobotsPolicy, ScreenerHttpClient
from .models import FetchedPage
from .normalize import normalize_period_value, normalize_scalar_value, safe_divide
from .parsers.company import (
    parse_balance_sheet_table,
    parse_cash_flow_table,
    parse_company_identity,
    parse_profit_loss_table,
    parse_quarterly_results_table,
    parse_ratios_table,
    parse_shareholding_pattern,
)
from .parsers.company.common import select_growth_value
from .utils.slugging import slugify_label


logger = logging.getLogger(__name__)

FINANCIAL_SUMMARY_COLUMNS = [
    "company_name",
    "company_slug",
    "industry_slug",
    "industry_name",
    "ticker",
    "nse_symbol",
    "bse_code",
    "company_url",
    "statement_scope",
    "broad_sector",
    "sector",
    "broad_industry",
    "industry",
    "current_price",
    "market_cap",
    "book_value",
    "face_value",
    "pe",
    "pb",
    "roce",
    "roe",
    "debt_to_equity",
    "dividend_yield",
    "sales_growth",
    "profit_growth",
    "stock_pe",
    "return_on_equity",
    "return_on_capital_employed",
]

SECTION_BASE_COLUMNS = [
    "company_name",
    "company_slug",
    "industry_slug",
    "industry_name",
    "company_url",
    "source_url",
    "statement_scope",
    "period_label",
    "period_key",
    "period",
    "period_type",
]

PROFIT_LOSS_COLUMNS = SECTION_BASE_COLUMNS + [
    "revenue",
    "sales",
    "expenses",
    "operating_profit",
    "opm_percent",
    "other_income",
    "interest",
    "depreciation",
    "profit_before_tax",
    "tax",
    "tax_percent",
    "net_profit",
    "eps",
    "dividend_payout_percent",
]

BALANCE_SHEET_COLUMNS = SECTION_BASE_COLUMNS + [
    "equity_share_capital",
    "reserves",
    "borrowings",
    "other_liabilities",
    "total_liabilities",
    "fixed_assets",
    "cwip",
    "investments",
    "other_assets",
    "total_assets",
]

CASH_FLOW_COLUMNS = SECTION_BASE_COLUMNS + [
    "cash_from_operating_activity",
    "cash_from_investing_activity",
    "cash_from_financing_activity",
    "net_cash_flow",
]

RATIOS_COLUMNS = SECTION_BASE_COLUMNS + [
    "debtor_days",
    "inventory_days",
    "days_payable",
    "cash_conversion_cycle",
    "working_capital_days",
    "roce",
    "roe",
    "interest_coverage",
    "asset_turnover",
    "debtor_turnover",
    "inventory_turnover",
]

QUARTERLY_RESULTS_COLUMNS = SECTION_BASE_COLUMNS + [
    "sales",
    "expenses",
    "operating_profit",
    "opm_percent",
    "other_income",
    "interest",
    "depreciation",
    "profit_before_tax",
    "tax",
    "tax_percent",
    "net_profit",
    "eps",
]

SHAREHOLDING_COLUMNS = SECTION_BASE_COLUMNS + [
    "holding_period_type",
    "promoters",
    "fii",
    "dii",
    "public",
    "number_of_shareholders",
]

RAW_METADATA_COLUMNS = [
    "company_name",
    "company_slug",
    "industry_slug",
    "company_url",
    "industry_name",
    "statement_scope",
    "scraped_at",
    "source_url",
    "parser_version",
    "parsing_status",
    "missing_sections",
    "raw_html_path",
    "json_path",
    "notes",
]

CRAWL_ERROR_COLUMNS = [
    "company_name",
    "company_slug",
    "source_url",
    "stage",
    "error_type",
    "error_message",
    "occurred_at",
    "parser_version",
    "parsing_status",
    "raw_html_path",
    "json_path",
    "notes",
]

TIME_SERIES_FINANCIALS_COLUMNS = [
    "company_slug",
    "company_name",
    "industry_slug",
    "statement_type",
    "metric_name",
    "period",
    "period_type",
    "value",
]

TIME_SERIES_CONFIG = {
    "profit_loss": {
        "default_period_type": "annual",
        "metric_fields": [
            "revenue",
            "sales",
            "expenses",
            "operating_profit",
            "opm_percent",
            "other_income",
            "interest",
            "depreciation",
            "profit_before_tax",
            "tax",
            "tax_percent",
            "net_profit",
            "eps",
            "dividend_payout_percent",
        ],
    },
    "balance_sheet": {
        "default_period_type": "annual",
        "metric_fields": [
            "equity_share_capital",
            "reserves",
            "borrowings",
            "other_liabilities",
            "total_liabilities",
            "fixed_assets",
            "cwip",
            "investments",
            "other_assets",
            "total_assets",
        ],
    },
    "cash_flow": {
        "default_period_type": "annual",
        "metric_fields": [
            "cash_from_operating_activity",
            "cash_from_investing_activity",
            "cash_from_financing_activity",
            "net_cash_flow",
        ],
    },
    "ratios": {
        "default_period_type": "annual",
        "metric_fields": [
            "debtor_days",
            "inventory_days",
            "days_payable",
            "cash_conversion_cycle",
            "working_capital_days",
            "roce",
            "roe",
            "interest_coverage",
            "asset_turnover",
            "debtor_turnover",
            "inventory_turnover",
        ],
    },
    "quarterly_results": {
        "default_period_type": "quarterly",
        "metric_fields": [
            "sales",
            "expenses",
            "operating_profit",
            "opm_percent",
            "other_income",
            "interest",
            "depreciation",
            "profit_before_tax",
            "tax",
            "tax_percent",
            "net_profit",
            "eps",
        ],
    },
    "shareholding_pattern": {
        "default_period_type": "quarterly",
        "metric_fields": [
            "promoters",
            "fii",
            "dii",
            "public",
            "number_of_shareholders",
        ],
    },
}


def fetch_company_page(
    client: ScreenerHttpClient,
    company_url: str,
    *,
    robots_policy: RobotsPolicy,
    raw_html_path: Path,
) -> FetchedPage:
    if not robots_policy.can_fetch(company_url):
        raise RobotsDisallowedError(f"robots.txt blocks {company_url}")

    response = client.fetch(company_url)
    raw_html_path.parent.mkdir(parents=True, exist_ok=True)
    raw_html_path.write_text(response.text, encoding="utf-8")
    logger.info("Saved raw company HTML to %s", raw_html_path)
    return FetchedPage(url=str(response.url), html=response.text, page_number=1)


def extract_company_data(
    html: str,
    *,
    source_url: str,
    raw_html_path: Path,
    json_path: Path,
    crawl_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    soup = BeautifulSoup(html, "lxml")
    identity = parse_company_identity(soup, source_url)
    crawl_context = crawl_context or {}
    industry_name = crawl_context.get("industry_name") or identity.get("industry_name")
    industry_slug = crawl_context.get("industry_slug") or (
        slugify_label(industry_name) if industry_name else None
    )
    identity["industry_name"] = industry_name
    identity["industry_slug"] = industry_slug
    base_context = {
        "company_name": identity["company_name"],
        "company_slug": identity["company_slug"],
        "industry_slug": identity.get("industry_slug"),
        "industry_name": identity.get("industry_name"),
        "company_url": identity["company_url"],
        "source_url": source_url,
        "statement_scope": identity["statement_scope"],
    }

    errors: list[dict[str, Any]] = []
    missing_sections: list[str] = []
    sections: dict[str, Any] = {}
    section_parsers = {
        "profit_loss": parse_profit_loss_table,
        "balance_sheet": parse_balance_sheet_table,
        "cash_flow": parse_cash_flow_table,
        "ratios": parse_ratios_table,
        "quarterly_results": parse_quarterly_results_table,
        "shareholding_pattern": parse_shareholding_pattern,
    }

    for section_name, parser in section_parsers.items():
        try:
            sections[section_name] = parser(soup, base_context)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Failed to parse %s for %s", section_name, source_url)
            missing_sections.append(section_name)
            errors.append(
                build_error_record(
                    company_name=identity["company_name"],
                    company_slug=identity["company_slug"],
                    source_url=source_url,
                    stage=section_name,
                    error=exc,
                    raw_html_path=raw_html_path,
                    json_path=json_path,
                    parsing_status="partial",
                    notes=f"Section parse failed: {section_name}",
                )
            )

    summary = finalize_financial_summary(identity, sections)
    parsing_status = "success" if not errors and not missing_sections else "partial"
    scraped_at = datetime.now(timezone.utc).isoformat()

    metadata = {
        "company_name": summary["company_name"],
        "company_slug": summary["company_slug"],
        "industry_slug": summary.get("industry_slug"),
        "company_url": summary["company_url"],
        "industry_name": summary.get("industry_name"),
        "statement_scope": summary["statement_scope"],
        "scraped_at": scraped_at,
        "source_url": source_url,
        "parser_version": PARSER_VERSION,
        "parsing_status": parsing_status,
        "missing_sections": json.dumps(missing_sections),
        "raw_html_path": str(raw_html_path),
        "json_path": str(json_path),
        "notes": build_metadata_notes(summary, missing_sections),
    }

    return {
        "financial_summary": summary,
        "profit_loss": sections.get("profit_loss", {}),
        "balance_sheet": sections.get("balance_sheet", {}),
        "cash_flow": sections.get("cash_flow", {}),
        "ratios": sections.get("ratios", {}),
        "quarterly_results": sections.get("quarterly_results", {}),
        "shareholding_pattern": sections.get("shareholding_pattern", {}),
        "raw_metadata": metadata,
        "errors": errors,
    }


def finalize_financial_summary(summary: dict[str, Any], sections: dict[str, Any]) -> dict[str, Any]:
    result = dict(summary)

    balance_records = sections.get("balance_sheet", {}).get("records", [])
    latest_balance = balance_records[-1] if balance_records else {}
    equity_base = (latest_balance.get("equity_share_capital") or 0) + (latest_balance.get("reserves") or 0)
    result["debt_to_equity"] = safe_divide(latest_balance.get("borrowings"), equity_base)

    growth_tables = sections.get("profit_loss", {}).get("growth_tables", {})
    result["sales_growth"] = select_growth_value(growth_tables.get("Compounded Sales Growth", {}))
    result["profit_growth"] = select_growth_value(growth_tables.get("Compounded Profit Growth", {}))
    result["pe"] = result.get("pe") or result.get("stock_pe")
    result["return_on_equity"] = result.get("return_on_equity") or result.get("roe")
    result["return_on_capital_employed"] = (
        result.get("return_on_capital_employed") or result.get("roce")
    )
    result["industry_name"] = result.get("industry_name") or result.get("industry")
    if not result.get("industry_slug") and result.get("industry_name"):
        result["industry_slug"] = slugify_label(result["industry_name"])
    return result


def build_metadata_notes(summary: dict[str, Any], missing_sections: list[str]) -> str:
    notes: list[str] = []
    derived_fields = [
        field
        for field in ("pb", "debt_to_equity", "sales_growth", "profit_growth")
        if summary.get(field) is not None
    ]
    if derived_fields:
        notes.append(f"Derived fields populated: {', '.join(derived_fields)}")
    if missing_sections:
        notes.append(f"Missing sections: {', '.join(missing_sections)}")
    return "; ".join(notes)


def build_company_artifact_id(company_slug: str, company_url: str) -> str:
    normalized_slug = company_slug.lower()
    path = urlsplit(company_url).path.lower()
    if "/consolidated/" in path:
        return f"{normalized_slug}__consolidated"
    return normalized_slug


def save_company_json(payload: dict[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    logger.info("Saved company JSON to %s", output_path)


def save_company_error(payload: dict[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    logger.info("Saved company error JSON to %s", output_path)


def build_error_record(
    *,
    company_name: str | None,
    company_slug: str | None,
    source_url: str,
    stage: str,
    error: Exception,
    raw_html_path: Path | None,
    json_path: Path | None,
    parsing_status: str,
    notes: str = "",
) -> dict[str, Any]:
    return {
        "company_name": company_name,
        "company_slug": company_slug,
        "source_url": source_url,
        "stage": stage,
        "error_type": type(error).__name__,
        "error_message": str(error),
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        "parser_version": PARSER_VERSION,
        "parsing_status": parsing_status,
        "raw_html_path": str(raw_html_path) if raw_html_path else None,
        "json_path": str(json_path) if json_path else None,
        "notes": notes,
    }


def process_company_target(
    target: dict[str, Any],
    *,
    client: ScreenerHttpClient,
    robots_policy: RobotsPolicy,
    raw_html_dir: Path,
    json_dir: Path,
    force: bool,
) -> dict[str, Any]:
    company_url = str(target["company_page_url"])
    company_slug = str(target["company_slug"])
    artifact_id = build_company_artifact_id(company_slug, company_url)
    raw_html_path = raw_html_dir / f"{artifact_id}.html"
    json_path = json_dir / f"{artifact_id}.json"
    error_path = json_dir / f"{artifact_id}.error.json"

    if json_path.exists() and not force:
        logger.info("Skipping %s because %s already exists", company_slug, json_path)
        return {"status": "skipped", "company_slug": company_slug, "json_path": str(json_path)}

    try:
        fetched_page = fetch_company_page(
            client,
            company_url,
            robots_policy=robots_policy,
            raw_html_path=raw_html_path,
        )
        payload = extract_company_data(
            fetched_page.html,
            source_url=fetched_page.url,
            raw_html_path=raw_html_path,
            json_path=json_path,
            crawl_context=target,
        )
        save_company_json(payload, json_path)
        if error_path.exists():
            error_path.unlink()
        return {
            "status": payload["raw_metadata"]["parsing_status"],
            "company_slug": company_slug,
            "json_path": str(json_path),
        }
    except Exception as exc:  # noqa: BLE001
        logger.exception("Failed to process company %s", company_url)
        error_payload = build_error_record(
            company_name=target.get("company_name"),
            company_slug=company_slug,
            source_url=company_url,
            stage="fetch_company",
            error=exc,
            raw_html_path=raw_html_path if raw_html_path.exists() else None,
            json_path=json_path,
            parsing_status="error",
            notes="Fetch or full-page parse failed.",
        )
        save_company_error(error_payload, error_path)
        return {"status": "error", "company_slug": company_slug, "error_path": str(error_path)}


def load_companies_master(input_csv: Path) -> list[dict[str, Any]]:
    frame = pd.read_csv(input_csv)
    return frame.to_dict(orient="records")


def resolve_company_target(identifier: str, companies_master_path: Path) -> dict[str, Any]:
    companies = load_companies_master(companies_master_path)
    if identifier.startswith("http://") or identifier.startswith("https://"):
        company_url = identifier
        return {
            "company_name": None,
            "company_page_url": company_url,
            "company_slug": extract_company_slug(company_url),
        }

    normalized = identifier.strip().lower()
    for company in companies:
        if str(company["company_slug"]).lower() == normalized:
            return company

    company_url = urljoin(SCREENER_BASE_URL, f"/company/{identifier.upper()}/")
    return {
        "company_name": None,
        "company_page_url": company_url,
        "company_slug": identifier.upper(),
    }


def write_csv(records: list[dict[str, Any]], output_path: Path, columns: list[str]) -> pd.DataFrame:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    frame = pd.DataFrame(records)
    if frame.empty:
        frame = pd.DataFrame(columns=columns)
    else:
        for column in columns:
            if column not in frame.columns:
                frame[column] = None
        frame = frame[columns]
    frame.to_csv(output_path, index=False)
    logger.info("Saved %s", output_path)
    return frame


def normalize_financial_summary_record(record: dict[str, Any]) -> dict[str, Any]:
    normalized = {key: normalize_scalar_value(value) for key, value in dict(record).items()}
    normalized["industry_name"] = normalized.get("industry_name") or normalized.get("industry")
    if not normalized.get("industry_slug") and normalized.get("industry_name"):
        normalized["industry_slug"] = slugify_label(str(normalized["industry_name"]))
    normalized["pe"] = normalized.get("pe") or normalized.get("stock_pe")
    normalized["return_on_equity"] = normalized.get("return_on_equity") or normalized.get("roe")
    normalized["return_on_capital_employed"] = (
        normalized.get("return_on_capital_employed") or normalized.get("roce")
    )
    return normalized


def normalize_metadata_record(
    metadata: dict[str, Any],
    *,
    financial_summary: dict[str, Any],
    json_path: Path,
) -> dict[str, Any]:
    normalized = {key: normalize_scalar_value(value) for key, value in dict(metadata).items()}
    normalized["company_name"] = normalized.get("company_name") or financial_summary.get("company_name")
    normalized["company_slug"] = normalized.get("company_slug") or financial_summary.get("company_slug")
    normalized["industry_slug"] = normalized.get("industry_slug") or financial_summary.get("industry_slug")
    normalized["company_url"] = normalized.get("company_url") or financial_summary.get("company_url")
    normalized["industry_name"] = (
        normalized.get("industry_name")
        or financial_summary.get("industry_name")
        or financial_summary.get("industry")
    )
    normalized["source_url"] = normalized.get("source_url") or financial_summary.get("company_url")
    normalized["statement_scope"] = (
        normalized.get("statement_scope") or financial_summary.get("statement_scope")
    )
    normalized["parser_version"] = normalized.get("parser_version") or PARSER_VERSION
    normalized["parsing_status"] = normalized.get("parsing_status") or "success"
    normalized["missing_sections"] = normalized.get("missing_sections") or "[]"
    normalized["json_path"] = normalized.get("json_path") or str(json_path)
    normalized["notes"] = normalized.get("notes") or ""
    return normalized


def normalize_error_record(record: dict[str, Any], *, json_path: Path) -> dict[str, Any]:
    normalized = {key: normalize_scalar_value(value) for key, value in dict(record).items()}
    normalized["parser_version"] = normalized.get("parser_version") or PARSER_VERSION
    normalized["parsing_status"] = normalized.get("parsing_status") or "error"
    normalized["json_path"] = normalized.get("json_path") or str(json_path)
    normalized["notes"] = normalized.get("notes") or ""
    return normalized


def normalize_section_record(
    record: dict[str, Any],
    *,
    financial_summary: dict[str, Any],
    default_period_type: str,
) -> dict[str, Any]:
    normalized = {key: normalize_scalar_value(value) for key, value in dict(record).items()}
    normalized["company_name"] = normalized.get("company_name") or financial_summary.get("company_name")
    normalized["company_slug"] = normalized.get("company_slug") or financial_summary.get("company_slug")
    normalized["industry_slug"] = normalized.get("industry_slug") or financial_summary.get("industry_slug")
    normalized["industry_name"] = normalized.get("industry_name") or financial_summary.get("industry_name")
    normalized["company_url"] = normalized.get("company_url") or financial_summary.get("company_url")
    normalized["source_url"] = normalized.get("source_url") or financial_summary.get("company_url")
    normalized["statement_scope"] = (
        normalized.get("statement_scope") or financial_summary.get("statement_scope")
    )

    period_fields = normalize_period_value(
        normalized.get("period_label"),
        normalized.get("period_key"),
        default_period_type=normalized.get("holding_period_type") or default_period_type,
    )
    normalized["period"] = period_fields["period"]
    normalized["period_type"] = period_fields["period_type"]
    return normalized


def normalize_section_records(
    records: list[dict[str, Any]],
    *,
    financial_summary: dict[str, Any],
    default_period_type: str,
) -> list[dict[str, Any]]:
    return [
        normalize_section_record(
            record,
            financial_summary=financial_summary,
            default_period_type=default_period_type,
        )
        for record in records
    ]


def build_time_series_records(
    *,
    statement_type: str,
    section_records: list[dict[str, Any]],
    metric_fields: list[str],
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for row in section_records:
        for metric_name in metric_fields:
            value = normalize_scalar_value(row.get(metric_name))
            if value is None:
                continue
            records.append(
                {
                    "company_slug": row.get("company_slug"),
                    "company_name": row.get("company_name"),
                    "industry_slug": row.get("industry_slug"),
                    "statement_type": statement_type,
                    "metric_name": metric_name,
                    "period": row.get("period"),
                    "period_type": row.get("period_type"),
                    "value": value,
                }
            )
    return records


def build_datasets_from_company_json(
    *,
    json_dir: Path,
    output_dir: Path,
) -> dict[str, pd.DataFrame]:
    summary_records: list[dict[str, Any]] = []
    profit_loss_records: list[dict[str, Any]] = []
    balance_sheet_records: list[dict[str, Any]] = []
    cash_flow_records: list[dict[str, Any]] = []
    ratios_records: list[dict[str, Any]] = []
    quarterly_records: list[dict[str, Any]] = []
    shareholding_records: list[dict[str, Any]] = []
    time_series_records: list[dict[str, Any]] = []
    metadata_records: list[dict[str, Any]] = []
    error_records: list[dict[str, Any]] = []

    for path in sorted(json_dir.glob("*.json")):
        if path.name.endswith(".error.json"):
            payload = json.loads(path.read_text(encoding="utf-8"))
            error_records.append(normalize_error_record(payload, json_path=path))
            continue

        payload = json.loads(path.read_text(encoding="utf-8"))
        financial_summary = normalize_financial_summary_record(payload["financial_summary"])
        summary_records.append(financial_summary)
        metadata_records.append(
            normalize_metadata_record(
                payload.get("raw_metadata", {}),
                financial_summary=financial_summary,
                json_path=path,
            )
        )

        normalized_profit_loss = normalize_section_records(
            payload.get("profit_loss", {}).get("records", []),
            financial_summary=financial_summary,
            default_period_type=TIME_SERIES_CONFIG["profit_loss"]["default_period_type"],
        )
        profit_loss_records.extend(normalized_profit_loss)
        time_series_records.extend(
            build_time_series_records(
                statement_type="profit_loss",
                section_records=normalized_profit_loss,
                metric_fields=TIME_SERIES_CONFIG["profit_loss"]["metric_fields"],
            )
        )

        normalized_balance_sheet = normalize_section_records(
            payload.get("balance_sheet", {}).get("records", []),
            financial_summary=financial_summary,
            default_period_type=TIME_SERIES_CONFIG["balance_sheet"]["default_period_type"],
        )
        balance_sheet_records.extend(normalized_balance_sheet)
        time_series_records.extend(
            build_time_series_records(
                statement_type="balance_sheet",
                section_records=normalized_balance_sheet,
                metric_fields=TIME_SERIES_CONFIG["balance_sheet"]["metric_fields"],
            )
        )

        normalized_cash_flow = normalize_section_records(
            payload.get("cash_flow", {}).get("records", []),
            financial_summary=financial_summary,
            default_period_type=TIME_SERIES_CONFIG["cash_flow"]["default_period_type"],
        )
        cash_flow_records.extend(normalized_cash_flow)
        time_series_records.extend(
            build_time_series_records(
                statement_type="cash_flow",
                section_records=normalized_cash_flow,
                metric_fields=TIME_SERIES_CONFIG["cash_flow"]["metric_fields"],
            )
        )

        normalized_ratios = normalize_section_records(
            payload.get("ratios", {}).get("records", []),
            financial_summary=financial_summary,
            default_period_type=TIME_SERIES_CONFIG["ratios"]["default_period_type"],
        )
        ratios_records.extend(normalized_ratios)
        time_series_records.extend(
            build_time_series_records(
                statement_type="ratios",
                section_records=normalized_ratios,
                metric_fields=TIME_SERIES_CONFIG["ratios"]["metric_fields"],
            )
        )

        normalized_quarterly = normalize_section_records(
            payload.get("quarterly_results", {}).get("records", []),
            financial_summary=financial_summary,
            default_period_type=TIME_SERIES_CONFIG["quarterly_results"]["default_period_type"],
        )
        quarterly_records.extend(normalized_quarterly)
        time_series_records.extend(
            build_time_series_records(
                statement_type="quarterly_results",
                section_records=normalized_quarterly,
                metric_fields=TIME_SERIES_CONFIG["quarterly_results"]["metric_fields"],
            )
        )

        normalized_shareholding = normalize_section_records(
            payload.get("shareholding_pattern", {}).get("records", []),
            financial_summary=financial_summary,
            default_period_type=TIME_SERIES_CONFIG["shareholding_pattern"]["default_period_type"],
        )
        normalized_shareholding = [
            record
            for record in normalized_shareholding
            if record.get("holding_period_type") == "quarterly"
        ]
        shareholding_records.extend(normalized_shareholding)
        time_series_records.extend(
            build_time_series_records(
                statement_type="shareholding_pattern",
                section_records=normalized_shareholding,
                metric_fields=TIME_SERIES_CONFIG["shareholding_pattern"]["metric_fields"],
            )
        )

        error_records.extend(
            normalize_error_record(record, json_path=path) for record in payload.get("errors", [])
        )

    return {
        "financial_summary": write_csv(
            summary_records,
            output_dir / "financial_summary.csv",
            FINANCIAL_SUMMARY_COLUMNS,
        ),
        "profit_loss": write_csv(
            profit_loss_records,
            output_dir / "profit_loss.csv",
            PROFIT_LOSS_COLUMNS,
        ),
        "balance_sheet": write_csv(
            balance_sheet_records,
            output_dir / "balance_sheet.csv",
            BALANCE_SHEET_COLUMNS,
        ),
        "cash_flow": write_csv(
            cash_flow_records,
            output_dir / "cash_flow.csv",
            CASH_FLOW_COLUMNS,
        ),
        "ratios": write_csv(
            ratios_records,
            output_dir / "ratios.csv",
            RATIOS_COLUMNS,
        ),
        "quarterly_results": write_csv(
            quarterly_records,
            output_dir / "quarterly_results.csv",
            QUARTERLY_RESULTS_COLUMNS,
        ),
        "shareholding_pattern": write_csv(
            shareholding_records,
            output_dir / "shareholding_pattern.csv",
            SHAREHOLDING_COLUMNS,
        ),
        "time_series_financials": write_csv(
            time_series_records,
            output_dir / "time_series_financials.csv",
            TIME_SERIES_FINANCIALS_COLUMNS,
        ),
        "raw_metadata": write_csv(
            metadata_records,
            output_dir / "raw_metadata.csv",
            RAW_METADATA_COLUMNS,
        ),
        "crawl_errors": write_csv(
            error_records,
            output_dir / "crawl_errors.csv",
            CRAWL_ERROR_COLUMNS,
        ),
    }
