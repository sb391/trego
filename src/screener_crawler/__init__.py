"""Screener crawler package."""

from .company_extraction import (
    build_datasets_from_company_json,
    fetch_company_page,
    parse_balance_sheet_table,
    parse_cash_flow_table,
    parse_company_identity,
    parse_profit_loss_table,
    parse_quarterly_results_table,
    parse_ratios_table,
    parse_shareholding_pattern,
    save_company_json,
)
from .discovery import (
    discover_companies_from_industry_master,
    fetch_industry_page,
    parse_industry_companies,
    save_companies_master_csv,
)
from .parsers import parse_industries_overview
from .pipelines import discover_industries, fetch_industries_overview_page, save_industry_master_csv

__all__ = [
    "build_datasets_from_company_json",
    "discover_companies_from_industry_master",
    "discover_industries",
    "fetch_company_page",
    "fetch_industry_page",
    "fetch_industries_overview_page",
    "parse_balance_sheet_table",
    "parse_cash_flow_table",
    "parse_company_identity",
    "parse_industry_companies",
    "parse_industries_overview",
    "parse_profit_loss_table",
    "parse_quarterly_results_table",
    "parse_ratios_table",
    "parse_shareholding_pattern",
    "save_companies_master_csv",
    "save_industry_master_csv",
    "save_company_json",
]
