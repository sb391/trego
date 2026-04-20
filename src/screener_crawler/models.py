from dataclasses import asdict, dataclass


@dataclass(slots=True, frozen=True)
class PaginationInfo:
    total_results: int
    current_page: int
    total_pages: int


@dataclass(slots=True, frozen=True)
class FetchedPage:
    url: str
    html: str
    page_number: int


@dataclass(slots=True, frozen=True)
class CompanyDiscoveryRecord:
    industry_slug: str
    company_name: str
    company_page_url: str
    company_slug: str
    industry_name: str
    industry_url: str
    listing_rank: int | None
    cmp: float | None
    pe: float | None
    market_cap: float | None
    dividend_yield: float | None
    quarterly_profit: float | None
    quarterly_profit_growth: float | None
    quarterly_sales: float | None
    quarterly_sales_growth: float | None
    roce: float | None
    promoter_holding: float | None
    discovered_at: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(slots=True, frozen=True)
class ParsedIndustryPage:
    industry_slug: str
    industry_name: str
    industry_url: str
    pagination: PaginationInfo
    companies: list[CompanyDiscoveryRecord]


@dataclass(slots=True, frozen=True)
class IndustryOverviewRecord:
    industry_name: str
    industry_url: str
    industry_slug: str
    screener_hierarchy_code: str | None
    number_of_companies: int | None
    total_market_cap: float | None
    median_market_cap: float | None
    median_pe: float | None
    weighted_avg_sales_growth: float | None
    weighted_avg_opm: float | None
    weighted_avg_roce: float | None
    median_1y_return: float | None
    discovered_at: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(slots=True, frozen=True)
class ParsedIndustriesOverview:
    overview_url: str
    industries: list[IndustryOverviewRecord]
