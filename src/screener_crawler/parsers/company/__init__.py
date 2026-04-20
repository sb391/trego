"""Section parsers for Screener company pages."""

from .balance_sheet import BALANCE_SHEET_ALIASES, parse_balance_sheet_table
from .cash_flow import CASH_FLOW_ALIASES, parse_cash_flow_table
from .identity import SUMMARY_TOP_RATIO_MAP, parse_company_identity
from .profit_loss import PROFIT_LOSS_ALIASES, parse_profit_loss_table
from .quarterly_results import QUARTERLY_RESULTS_ALIASES, parse_quarterly_results_table
from .ratios import RATIOS_ALIASES, parse_ratios_table
from .shareholding import SHAREHOLDING_ALIASES, parse_shareholding_pattern

__all__ = [
    "BALANCE_SHEET_ALIASES",
    "CASH_FLOW_ALIASES",
    "PROFIT_LOSS_ALIASES",
    "QUARTERLY_RESULTS_ALIASES",
    "RATIOS_ALIASES",
    "SHAREHOLDING_ALIASES",
    "SUMMARY_TOP_RATIO_MAP",
    "parse_balance_sheet_table",
    "parse_cash_flow_table",
    "parse_company_identity",
    "parse_profit_loss_table",
    "parse_quarterly_results_table",
    "parse_ratios_table",
    "parse_shareholding_pattern",
]
