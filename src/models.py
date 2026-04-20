from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass(slots=True)
class CorporateRecord:
    row_index: int
    company_id: str
    company_name: str
    search_name: str
    normalized_name: str
    normalized_tokens: tuple[str, ...]
    nse_code: str | None
    bse_code: str | None
    isin_code: str | None
    industry_group: str | None
    industry: str | None

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["normalized_tokens"] = list(self.normalized_tokens)
        return payload


@dataclass(slots=True)
class SearchCandidate:
    rank: int
    name: str
    url: str
    company_slug: str
    normalized_name: str
    normalized_tokens: tuple[str, ...]
    source_payload: dict[str, object] = field(default_factory=dict)


@dataclass(slots=True)
class MatchScore:
    candidate: SearchCandidate
    total_score: float
    exact_name_match: bool
    normalized_name_match: bool
    token_overlap: float
    sequence_similarity: float
    nse_code_match: bool
    bse_code_match: bool
    reasons: list[str]


@dataclass(slots=True)
class MatchDecision:
    company: CorporateRecord
    search_query: str
    candidates: list[SearchCandidate]
    scored_candidates: list[MatchScore]
    status: str
    matched_candidate: SearchCandidate | None
    confidence: float
    reason: str


@dataclass(slots=True)
class DownloadStatusRecord:
    company_id: str
    company_name: str
    nse_code: str | None
    bse_code: str | None
    screener_url: str | None
    local_file_path: str | None
    status: str
    downloaded_at: str | None
    validation_status: str | None
    notes: str | None


@dataclass(slots=True)
class AmbiguousMatchRecord:
    company_id: str
    intended_name: str
    nse_code: str | None
    bse_code: str | None
    search_query: str
    candidate_1: str | None
    candidate_2: str | None
    candidate_3: str | None
    reason: str


@dataclass(slots=True)
class FailedDownloadRecord:
    company_id: str
    company_name: str
    stage_failed: str
    error_message: str
    retry_count: int
    timestamp: str


@dataclass(slots=True)
class DownloadResult:
    company_id: str
    company_name: str
    screener_url: str
    status: str
    local_file_path: str | None
    downloaded_at: str | None
    validation_status: str | None
    notes: str | None


@dataclass(slots=True)
class CreditRatingLink:
    event_id: str
    company_id: str
    company_name: str
    nse_code: str | None
    bse_code: str | None
    screener_url: str
    rating_update_url: str
    rating_date: str | None
    rating_date_display: str | None
    rating_agency: str | None
    notes: str | None


@dataclass(slots=True)
class CreditRatingRecord:
    event_id: str
    company_id: str
    company_name: str
    nse_code: str | None
    bse_code: str | None
    screener_url: str
    rating_update_url: str
    rating_date: str | None
    rating_date_display: str | None
    rating_agency: str | None
    rating: str | None
    rating_scale: str | None
    extraction_method: str | None
    extracted_at: str | None
    notes: str | None


@dataclass(slots=True)
class CreditRatingStatusRecord:
    company_id: str
    company_name: str
    nse_code: str | None
    bse_code: str | None
    screener_url: str | None
    status: str
    ratings_found: int
    updated_at: str | None
    notes: str | None


@dataclass(slots=True)
class CreditRatingFailureRecord:
    company_id: str
    company_name: str
    rating_update_url: str | None
    stage_failed: str
    error_message: str
    retry_count: int
    timestamp: str
