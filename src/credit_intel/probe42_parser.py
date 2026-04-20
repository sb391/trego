from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import fitz

from .schemas import FinancialSummary


SECTION_TITLES = {
    "balance_sheet": "Balance Sheet - AOC-4",
    "profit_loss": "Profit & Loss - AOC-4",
    "cash_flow": "Cash Flow - AOC-4",
    "ratios": "Ratios - AOC-4",
    "financial_parameters": "Parameter (Rs. Crore)",
}

KEY_STAT_FIELDS = [
    "Registered Address",
    "Business Address",
    "Date of Incorporation",
    "Type of Entity",
    "Listing Status",
    "Website",
    "Email",
    "Phone",
    "CIN",
    "PAN",
    "Paid Up Capital",
    "Authorized Capital",
    "Sum of Charges",
    "Company Status",
    "Active Compliance",
    "Date of Last AGM",
    "LEI",
]

BALANCE_SHEET_SKIP_LABELS = {
    "Equity and Liabilities",
    "Equity",
    "Liabilities",
    "Non-current Liabilities",
    "Current Liabilities",
    "Assets",
    "Net Fixed Assets",
    "Other Non-current Assets",
    "Current Assets",
}

PROFIT_LOSS_SKIP_LABELS = {"Operating Cost"}

CASH_FLOW_SKIP_LABELS = {
    "Cash Flows from / ( Used in ) Operating Activities",
    "Cash Flows from / ( Used in ) Investing Activities",
    "Cash Flows from / ( Used in ) Financing Activities",
}

CASH_FLOW_CONTINUATIONS = {
    "Assets",
    "Liabilities",
    "Operating Activities",
    "Investing Activities",
    "Borrowings",
    "Financing Activities",
    "Effect of Exchange Rate Changes",
}

FINANCIAL_PARAMETER_CONTINUATIONS = {"AS-18"}

BALANCE_SHEET_METRIC_MAP = {
    "share capital": "equity_share_capital",
    "reserves and surplus": "reserves",
    "other equity": "other_equity",
    "total equity": "total_equity",
    "long term borrowings": "long_term_borrowings",
    "net deferred tax liabilities": "deferred_tax_liabilities",
    "other long term liabilities": "other_long_term_liabilities",
    "long term provisions": "long_term_provisions",
    "total non-current liabilities": "total_non_current_liabilities",
    "short term borrowings": "short_term_borrowings",
    "trade payables": "trade_payables",
    "other current liabilities": "other_current_liabilities",
    "short term provisions": "short_term_provisions",
    "total current liabilities": "total_current_liabilities",
    "total equity and liabilities": "total",
    "tangible assets": "tangible_assets",
    "intangible assets": "intangible_assets",
    "total net fixed assets": "fixed_assets",
    "capital work-in-progress": "capital_work_in_progress",
    "non-current investments": "investments",
    "net deferred tax assets": "deferred_tax_assets",
    "long term loans and advances": "long_term_loans_and_advances",
    "other non-current assets": "other_non_current_assets",
    "total other non-current assets": "total_other_non_current_assets",
    "current investments": "current_investments",
    "inventories": "inventory",
    "trade receivables": "receivables",
    "cash and bank balances": "cash_and_bank",
    "short term loans and advances": "short_term_loans_and_advances",
    "other current assets": "other_current_assets",
    "total current assets": "current_assets",
    "total assets": "total",
}

PROFIT_LOSS_METRIC_MAP = {
    "net revenue": "sales",
    "cost of materials consumed": "cost_of_materials_consumed",
    "purchases of stock-in-trade": "purchases_of_stock_in_trade",
    "changes in inventories finished goods": "changes_in_inventory",
    "employee benefit expense": "employee_benefit_expense",
    "other expenses": "other_expenses",
    "total operating cost": "operating_cost",
    "operating profit ebitda": "operating_profit",
    "other income": "other_income",
    "depreciation and amortization expense": "depreciation",
    "profit before interest and tax": "profit_before_interest_and_tax",
    "finance costs": "interest",
    "profit before tax and exceptional items before tax": "profit_before_tax_before_exceptional_items",
    "exceptional items before tax": "exceptional_items_before_tax",
    "profit before tax": "profit_before_tax",
    "income tax": "tax",
    "profit for the period from continuing operations": "profit_from_continuing_operations",
    "profit from discontinuing operations after tax": "profit_from_discontinuing_operations",
    "profit for the period": "net_profit",
}

CASH_FLOW_METRIC_MAP = {
    "profit before tax": "profit_before_tax",
    "adjustment for finance cost and depreciation": "adjustment_for_finance_cost_and_depreciation",
    "adjustments for current and non-current assets": "adjustments_for_assets",
    "adjustments for current and non-current liabilities": "adjustments_for_liabilities",
    "other adjustments in operating activities": "other_adjustments_in_operating_activities",
    "net cash flows from used in operating activities": "cash_from_operating_activity",
    "cash outflow from purchase of assets": "cash_outflow_purchase_of_assets",
    "cash inflow from sale of assets": "cash_inflow_sale_of_assets",
    "income from assets": "income_from_assets",
    "other adjustments in investing activities": "other_adjustments_in_investing_activities",
    "net cash flows from used in investing activities": "cash_from_investing_activity",
    "cash outflow from repayment of capital and borrowings": "cash_outflow_repayment_of_capital_and_borrowings",
    "cash inflow from raising capital and borrowings": "cash_inflow_raising_capital_and_borrowings",
    "interest and dividends paid": "interest_and_dividends_paid",
    "other adjustments in financing activities": "other_adjustments_in_financing_activities",
    "net cash flows from used in financing activities": "cash_from_financing_activity",
    "increase decrease in cash and cash equivalents before effect of exchange rate changes": "increase_in_cash_before_fx",
    "adjustments to cash and cash equivalents": "adjustments_to_cash_and_cash_equivalents",
    "net increase decrease in cash and cash equivalents": "net_cash_flow",
    "cash and cash equivalents at end of period": "cash_and_cash_equivalents_end_of_period",
}

RATIO_METRIC_MAP = {
    "revenue growth": "revenue_growth_pct",
    "gross profit margin": "gross_profit_margin_pct",
    "ebitda margin": "ebitda_margin_pct",
    "net margin": "pat_margin_pct",
    "return on equity": "roe_pct",
    "return on capital employed": "roce_pct",
    "debt ratio": "debt_ratio",
    "debt equity": "debt_to_equity",
    "interest coverage ratio": "interest_coverage",
    "current ratio": "current_ratio",
    "quick ratio": "quick_ratio",
    "inventory sales days": "inventory_days",
    "debtors sales days": "receivables_days",
    "payables sales days": "payables_days",
    "cash conversion cycle days": "cash_conversion_cycle_days",
    "sales net fixed assets": "sales_to_net_fixed_assets",
}

FINANCIAL_PARAMETER_MAP = {
    "income in foreign currency": "income_in_foreign_currency",
    "expense in foreign currency": "expense_in_foreign_currency",
    "employee benefit expense": "employee_benefit_expense",
    "number of employees": "employee_count",
    "gross value of the transaction with the related parties as per as 18": "related_party_transactions",
    "gross fixed assets including intangible assets": "gross_fixed_assets",
    "trade receivables exceeding six months": "trade_receivables_gt_six_months",
    "proposed dividend": "proposed_dividend",
    "prescribed csr expenditure": "prescribed_csr_expenditure",
    "total amount spent on csr for the financial year": "csr_spent",
}


@dataclass(slots=True)
class TableLine:
    y: float
    label: str
    values: list[str]
    text: str


class Probe42FinancialPdfParser:
    provider_name = "probe42"

    def parse(self, pdf_path: Path) -> dict[str, Any]:
        with fitz.open(pdf_path) as pdf:
            page_texts = [page.get_text("text") for page in pdf]
            meta = parse_probe42_key_statistics(page_texts[2] if len(page_texts) > 2 else "")
            statement_rows = self._collect_statement_rows(pdf)

        balance_sheet = _statement_rows_to_records(
            statement_rows.get("balance_sheet", []),
            BALANCE_SHEET_METRIC_MAP,
            postprocess=_postprocess_balance_sheet_record,
        )
        profit_loss = _statement_rows_to_records(statement_rows.get("profit_loss", []), PROFIT_LOSS_METRIC_MAP)
        cash_flow = _statement_rows_to_records(statement_rows.get("cash_flow", []), CASH_FLOW_METRIC_MAP)
        ratios = _statement_rows_to_records(statement_rows.get("ratios", []), RATIO_METRIC_MAP)
        financial_parameters = _statement_rows_to_records(
            statement_rows.get("financial_parameters", []),
            FINANCIAL_PARAMETER_MAP,
        )
        financial_summary = _build_probe42_financial_summary(
            meta=meta,
            profit_loss=profit_loss,
            balance_sheet=balance_sheet,
            ratios=ratios,
        )

        return {
            "meta": meta,
            "financial_summary": financial_summary.model_dump(),
            "profit_loss": profit_loss,
            "balance_sheet": balance_sheet,
            "cash_flow": cash_flow,
            "ratios": ratios,
            "financial_parameters": financial_parameters,
        }

    def _collect_statement_rows(self, pdf: fitz.Document) -> dict[str, list[tuple[list[str], list[tuple[str, list[str]]]]]]:
        collected: dict[str, list[tuple[list[str], list[tuple[str, list[str]]]]]] = {
            "balance_sheet": [],
            "profit_loss": [],
            "cash_flow": [],
            "ratios": [],
            "financial_parameters": [],
        }
        for page in pdf:
            lines = _extract_page_lines(page)
            index = 0
            while index < len(lines):
                detected = _detect_probe42_section(lines, index)
                if not detected:
                    index += 1
                    continue
                section_name, periods, next_index = detected
                body: list[TableLine] = []
                cursor = next_index
                while cursor < len(lines):
                    if _detect_probe42_section(lines, cursor):
                        break
                    line = lines[cursor]
                    if _is_probe42_noise_line(line.text):
                        cursor += 1
                        continue
                    body.append(line)
                    cursor += 1
                rows = _parse_probe42_section_rows(section_name, body)
                if rows:
                    collected[section_name].append((periods, rows))
                index = cursor
        return collected


def parse_probe42_key_statistics(page_text: str) -> dict[str, Any]:
    lines = [line.strip() for line in page_text.splitlines() if line.strip()]
    if not lines:
        return {}

    company_name = lines[1] if len(lines) > 1 else None
    meta: dict[str, Any] = {"company_name": company_name}

    start = _index_of(lines, "Key Statistics")
    end = _index_of(lines, "About The Company")
    if start is None:
        return meta

    block = lines[start + 1 : end if end is not None else len(lines)]
    current_key: str | None = None
    buffer: list[str] = []
    keys = set(KEY_STAT_FIELDS)
    for line in block:
        if line in keys:
            if current_key:
                meta[_normalize_meta_key(current_key)] = _coerce_meta_value(current_key, " ".join(buffer).strip())
            current_key = line
            buffer = []
            continue
        if current_key:
            buffer.append(line)
    if current_key:
        meta[_normalize_meta_key(current_key)] = _coerce_meta_value(current_key, " ".join(buffer).strip())

    industry_index = _index_of(lines, "Industry And Segment(s)")
    principal_index = _first_index_matching(lines, r"^Principal Business Activities")
    if industry_index is not None:
        industry_lines = lines[industry_index + 1 : principal_index if principal_index is not None else len(lines)]
        industry_lines = [line for line in industry_lines if line and not line.startswith("Name History")]
        if industry_lines:
            meta["segment"] = industry_lines[0]
        if len(industry_lines) > 1:
            meta["industry"] = industry_lines[1]

    meta["standalone_or_consolidated"] = "standalone"
    meta["source_provider"] = "probe42"
    return meta


def _extract_page_lines(page: fitz.Page) -> list[TableLine]:
    buckets: dict[float, list[tuple[float, str]]] = {}
    for x0, y0, _x1, _y1, text, *_rest in page.get_text("words"):
        if y0 > 760:
            continue
        buckets.setdefault(round(y0, 1), []).append((x0, text))

    raw_lines = [(y, sorted(items), " ".join(text for _, text in sorted(items))) for y, items in sorted(buckets.items())]
    header_positions_by_y: dict[float, list[float]] = {}
    for y, items, text in raw_lines:
        periods = _extract_periods_with_positions(items)
        if periods and any(title in text for title in SECTION_TITLES.values()):
            header_positions_by_y[y] = [position for position, _ in periods]
        elif periods and text.startswith("Parameter (Rs. Crore)"):
            header_positions_by_y[y] = [position for position, _ in periods]

    lines: list[TableLine] = []
    active_positions: list[float] | None = None
    for y, items, text in raw_lines:
        if y in header_positions_by_y:
            active_positions = header_positions_by_y[y]
            lines.append(TableLine(y=y, label="", values=[], text=text))
            continue
        if active_positions is None:
            lines.append(TableLine(y=y, label=text, values=[], text=text))
            continue
        label, values = _split_line_by_columns(items, active_positions)
        lines.append(TableLine(y=y, label=label, values=values, text=text))
    return lines


def _detect_probe42_section(lines: list[TableLine], index: int) -> tuple[str, list[str], int] | None:
    line = lines[index]
    if SECTION_TITLES["balance_sheet"] in line.text:
        periods = _extract_period_strings(line.text)
        return ("balance_sheet", periods, index + 1) if periods else None
    if SECTION_TITLES["profit_loss"] in line.text:
        periods = _extract_period_strings(line.text)
        return ("profit_loss", periods, index + 1) if periods else None
    if SECTION_TITLES["cash_flow"] in line.text:
        periods = _extract_period_strings(line.text)
        return ("cash_flow", periods, index + 1) if periods else None
    if SECTION_TITLES["ratios"] in line.text:
        periods = _extract_period_strings(line.text)
        return ("ratios", periods, index + 1) if periods else None
    if line.text.startswith("Parameter (Rs. Crore)"):
        periods = _extract_period_strings(line.text)
        return ("financial_parameters", periods, index + 1) if periods else None
    return None


def _parse_probe42_section_rows(section_name: str, lines: list[TableLine]) -> list[tuple[str, list[str]]]:
    skip_labels = {
        "balance_sheet": BALANCE_SHEET_SKIP_LABELS,
        "profit_loss": PROFIT_LOSS_SKIP_LABELS,
        "cash_flow": CASH_FLOW_SKIP_LABELS,
        "ratios": set(),
        "financial_parameters": set(),
    }[section_name]
    continuation_labels = {
        "balance_sheet": set(),
        "profit_loss": set(),
        "cash_flow": CASH_FLOW_CONTINUATIONS,
        "ratios": set(),
        "financial_parameters": FINANCIAL_PARAMETER_CONTINUATIONS,
    }[section_name]

    rows: list[tuple[str, list[str]]] = []
    pending: list[str] = []
    index = 0
    while index < len(lines):
        line = lines[index]
        has_values = any(value for value in line.values)
        if has_values:
            label_parts = [part for part in pending if part and part not in skip_labels]
            if line.label:
                label_parts.append(line.label)
                index += 1
            else:
                cursor = index + 1
                while cursor < len(lines) and not any(value for value in lines[cursor].values) and lines[cursor].label in continuation_labels:
                    label_parts.append(lines[cursor].label)
                    cursor += 1
                index = cursor
            combined_label = " ".join(label_parts).strip()
            if combined_label and combined_label not in skip_labels:
                rows.append((combined_label, line.values))
            pending = []
            continue

        if line.label and not _is_probe42_noise_line(line.text):
            pending.append(line.label)
        index += 1
    return rows


def _statement_rows_to_records(
    statement_groups: list[tuple[list[str], list[tuple[str, list[str]]]]],
    metric_map: dict[str, str],
    *,
    postprocess: callable | None = None,
) -> list[dict[str, Any]]:
    records_by_period: dict[str, dict[str, Any]] = {}
    for periods, rows in statement_groups:
        normalized_periods = [_normalize_period(period) for period in periods]
        period_records = [records_by_period.setdefault(period, {"period": period}) for period in normalized_periods]
        for raw_label, values in rows:
            metric_key = metric_map.get(_normalize_metric_label(raw_label))
            if not metric_key:
                continue
            for record, raw_value in zip(period_records, values, strict=False):
                record[metric_key] = _parse_probe42_value(raw_value)

    ordered_records = [records_by_period[period] for period in sorted(records_by_period)]
    if postprocess:
        ordered_records = [postprocess(record) for record in ordered_records]
    return ordered_records


def _postprocess_balance_sheet_record(record: dict[str, Any]) -> dict[str, Any]:
    long_term = _to_float(record.get("long_term_borrowings"))
    short_term = _to_float(record.get("short_term_borrowings"))
    record["borrowings"] = _safe_sum([long_term, short_term])
    return record


def _build_probe42_financial_summary(
    *,
    meta: dict[str, Any],
    profit_loss: list[dict[str, Any]],
    balance_sheet: list[dict[str, Any]],
    ratios: list[dict[str, Any]],
) -> FinancialSummary:
    latest_pnl = profit_loss[-1] if profit_loss else {}
    latest_balance = balance_sheet[-1] if balance_sheet else {}
    latest_ratios = ratios[-1] if ratios else {}

    sales = _to_float(latest_pnl.get("sales"))
    operating_profit = _to_float(latest_pnl.get("operating_profit"))
    other_income = _to_float(latest_pnl.get("other_income"))
    interest = _to_float(latest_pnl.get("interest"))
    net_profit = _to_float(latest_pnl.get("net_profit"))
    networth = _safe_sum([
        _to_float(latest_balance.get("equity_share_capital")),
        _to_float(latest_balance.get("reserves")),
        _to_float(latest_balance.get("other_equity")),
    ])
    total_borrowings = _to_float(latest_balance.get("borrowings"))

    receivables_days = _to_float(latest_ratios.get("receivables_days"))
    inventory_days = _to_float(latest_ratios.get("inventory_days"))
    payables_days = _to_float(latest_ratios.get("payables_days"))
    working_capital_days = (
        round(receivables_days + inventory_days - payables_days, 4)
        if receivables_days is not None and inventory_days is not None and payables_days is not None
        else None
    )

    return FinancialSummary(
        revenue_crore=sales,
        ebitda_margin_pct=_to_float(latest_ratios.get("ebitda_margin_pct"))
        or _ratio_pct(operating_profit, sales),
        pat_margin_pct=_to_float(latest_ratios.get("pat_margin_pct")) or _ratio_pct(net_profit, sales),
        debt_to_equity=_to_float(latest_ratios.get("debt_to_equity"))
        or _safe_ratio(total_borrowings, networth),
        interest_coverage=_to_float(latest_ratios.get("interest_coverage"))
        or _safe_ratio(_safe_sum([operating_profit, other_income]), interest),
        working_capital_days=working_capital_days,
        receivables_days=receivables_days,
        inventory_days=inventory_days,
        current_price=None,
        market_cap_crore=None,
        networth_crore=networth,
        total_borrowings_crore=total_borrowings,
        source="probe42_pdf",
        statement_period=str(latest_pnl.get("period") or latest_balance.get("period") or ""),
    )


def _extract_periods_with_positions(items: list[tuple[float, str]]) -> list[tuple[float, str]]:
    groups: list[list[tuple[float, str]]] = []
    current: list[tuple[float, str]] = []
    for x, text in items:
        if x < 250:
            continue
        if not current or x - current[-1][0] < 35:
            current.append((x, text))
        else:
            groups.append(current)
            current = [(x, text)]
    if current:
        groups.append(current)
    periods: list[tuple[float, str]] = []
    for group in groups:
        text = " ".join(token for _, token in group)
        if re.search(r"\d{4}", text):
            periods.append((group[0][0], text))
    return periods


def _split_line_by_columns(items: list[tuple[float, str]], column_positions: list[float]) -> tuple[str, list[str]]:
    threshold = column_positions[0] - 10
    midpoints = [(column_positions[index] + column_positions[index + 1]) / 2 for index in range(len(column_positions) - 1)]
    label_words: list[str] = []
    columns: list[list[str]] = [[] for _ in column_positions]
    for x, text in items:
        if x < threshold:
            label_words.append(text)
            continue
        column_index = 0
        while column_index < len(midpoints) and x >= midpoints[column_index]:
            column_index += 1
        columns[column_index].append(text)
    return " ".join(label_words).strip(), [" ".join(words).strip() for words in columns]


def _extract_period_strings(text: str) -> list[str]:
    return re.findall(r"\d{1,2} [A-Za-z]{3}, \d{4}", text)


def _normalize_period(period: str) -> str:
    return datetime.strptime(period.strip(), "%d %b, %Y").date().isoformat()


def _normalize_metric_label(label: str) -> str:
    cleaned = label.replace("*", " ").replace("&", " and ").replace("/", " ").replace("(", " ").replace(")", " ")
    cleaned = re.sub(r"[^A-Za-z0-9]+", " ", cleaned)
    return re.sub(r"\s+", " ", cleaned).strip().lower()


def _parse_probe42_value(value: str) -> Any:
    text = str(value or "").strip()
    if not text or text == "-":
        return None
    if text in {"Yes", "No"}:
        return text
    normalized = text.replace(",", "")
    try:
        return float(normalized)
    except ValueError:
        return text


def _normalize_meta_key(label: str) -> str:
    return _normalize_metric_label(label).replace(" ", "_")


def _coerce_meta_value(label: str, value: str) -> Any:
    if not value or value == "-":
        return None
    if label in {"Paid Up Capital", "Authorized Capital", "Sum of Charges"}:
        match = re.search(r"([\d,]+(?:\.\d+)?)", value)
        return float(match.group(1).replace(",", "")) if match else value
    return value


def _index_of(lines: list[str], target: str) -> int | None:
    for index, line in enumerate(lines):
        if line == target:
            return index
    return None


def _first_index_matching(lines: list[str], pattern: str) -> int | None:
    regex = re.compile(pattern)
    for index, line in enumerate(lines):
        if regex.search(line):
            return index
    return None


def _is_probe42_noise_line(text: str) -> bool:
    return (
        not text
        or text == "Probe42.in"
        or text.startswith("Page ")
        or text.startswith("© PROBE")
        or text.startswith("Marked Copy For")
        or text.startswith("See Annexure")
        or text.startswith("* ")
    )


def _ratio_pct(numerator: float | None, denominator: float | None) -> float | None:
    ratio = _safe_ratio(numerator, denominator)
    return round(ratio * 100.0, 4) if ratio is not None else None


def _safe_ratio(numerator: float | None, denominator: float | None) -> float | None:
    if numerator is None or denominator in {None, 0}:
        return None
    return round(float(numerator) / float(denominator), 6)


def _safe_sum(values: list[float | None]) -> float | None:
    clean = [value for value in values if value is not None]
    if not clean:
        return None
    return round(float(sum(clean)), 6)


def _to_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None
