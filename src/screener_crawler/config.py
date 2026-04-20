from dataclasses import dataclass
from pathlib import Path


SCREENER_BASE_URL = "https://www.screener.in"
DEFAULT_INDUSTRIES_OVERVIEW_URL = f"{SCREENER_BASE_URL}/market/"
DEFAULT_DAIRY_PRODUCTS_URL = f"{SCREENER_BASE_URL}/market/IN04/IN0401/IN040104/IN040104002/"
DEFAULT_USER_AGENT = "ScreenerIndustryCrawler/0.1 (+local research; respects robots.txt)"
PARSER_VERSION = "0.4.0"


@dataclass(slots=True, frozen=True)
class CrawlerSettings:
    user_agent: str = DEFAULT_USER_AGENT
    timeout_seconds: float = 30.0
    delay_seconds: float = 2.0
    max_retries: int = 3
    raw_html_path: Path = Path("data/raw/industry_page.html")
    processed_csv_path: Path = Path("data/processed/companies_master.csv")
    industries_raw_html_path: Path = Path("data/raw/industries/industries_overview.html")
    industry_master_csv_path: Path = Path("data/processed/industry_master.csv")
