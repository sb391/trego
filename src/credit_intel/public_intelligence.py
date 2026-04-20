from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

import pandas as pd

from .config import CreditIntelConfig
from .search_engine import SearchEngineClient


ADVERSE_KEYWORD_GROUPS = {
    "fraud_signal_hits": {
        "fraud",
        "forgery",
        "embezzlement",
        "diversion",
        "misappropriation",
        "siphoning",
        "wilful defaulter",
        "willful defaulter",
        "scam",
        "sfio",
        "ed raid",
    },
    "regulatory_action_hits": {
        "sebi",
        "rbi penalty",
        "penalty",
        "show cause",
        "adjudication",
        "regulatory action",
        "nclt",
        "nclat",
        "suspension",
        "disqualified",
    },
    "insolvency_signal_hits": {
        "insolvency",
        "ibc",
        "bankruptcy",
        "resolution professional",
        "liquidation",
        "default",
        "npa",
        "restructuring",
        "cdr",
    },
    "litigation_signal_hits": {
        "litigation",
        "court",
        "legal notice",
        "petition",
        "lawsuit",
        "criminal case",
        "f.i.r",
        "fir",
    },
}
INDUSTRY_POSITIVE_KEYWORDS = {
    "growth",
    "demand",
    "tailwind",
    "expansion",
    "capacity addition",
    "opportunity",
    "recovery",
    "supportive",
    "favorable",
    "export demand",
}
INDUSTRY_NEGATIVE_KEYWORDS = {
    "slowdown",
    "pressure",
    "regulatory risk",
    "volatility",
    "oversupply",
    "decline",
    "weak demand",
    "disruption",
    "ban",
    "inflation",
}


def build_public_intelligence_dataset(
    *,
    companies_frame: pd.DataFrame,
    output_dir: Path,
    config: CreditIntelConfig | None = None,
    force: bool = False,
    limit: int | None = None,
) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    config = config or CreditIntelConfig()
    config.ensure_directories()
    search_client = SearchEngineClient(config)

    mentions_path = output_dir / "public_mentions.csv"
    context_path = output_dir / "public_intelligence_context.csv"

    if companies_frame.empty:
        pd.DataFrame().to_csv(mentions_path, index=False)
        pd.DataFrame().to_csv(context_path, index=False)
        return {
            "public_mentions": mentions_path,
            "public_intelligence_context": context_path,
        }

    working = companies_frame.copy()
    rename_map = {}
    for column in working.columns:
        normalized = str(column).strip().casefold()
        if normalized in {"name", "company", "company name"} and "company_name" not in working.columns:
            rename_map[column] = "company_name"
        elif normalized in {"company_id", "company id"} and "company_id" not in working.columns:
            rename_map[column] = "company_id"
        elif normalized in {"industry", "sub industry", "sub_industry"} and "sub_industry" not in working.columns:
            rename_map[column] = "sub_industry"
        elif normalized in {"industry group", "industry_group"} and "industry_group" not in working.columns:
            rename_map[column] = "industry_group"
    if rename_map:
        working = working.rename(columns=rename_map)
    if "company_id" not in working.columns:
        working["company_id"] = working["company_name"].astype(str).str.replace(r"[^A-Za-z0-9]+", "_", regex=True).str.strip("_")
    working = working.drop_duplicates(subset=["company_id"]).reset_index(drop=True)
    if limit is not None:
        working = working.head(limit).copy()

    industry_cache: dict[str, dict[str, Any]] = {}
    context_rows: list[dict[str, Any]] = []
    mention_rows: list[dict[str, Any]] = []

    for row in working.to_dict(orient="records"):
        company_name = str(row.get("company_name") or "").strip()
        if not company_name:
            continue
        company_id = str(row.get("company_id") or "").strip()
        sub_industry = str(row.get("sub_industry") or row.get("industry") or row.get("industry_group") or "").strip()

        adverse_query = (
            f'"{company_name}" '
            '("fraud" OR "default" OR "insolvency" OR "NCLT" OR "SEBI" OR "penalty" OR "criminal case" OR "lawsuit")'
        )
        adverse_results = search_client.search(adverse_query, max_results=config.public_risk_search_limit)
        adverse_scores, adverse_mentions = _score_adverse_mentions(adverse_results)

        industry_scores = {"industry_outlook_score": None}
        industry_mentions: list[dict[str, Any]] = []
        industry_label = _select_industry_label(row)
        if industry_label:
            cache_key = industry_label.casefold()
            if cache_key not in industry_cache or force:
                industry_query = f'India "{industry_label}" industry outlook growth forecast regulation'
                industry_results = search_client.search(industry_query, max_results=config.industry_outlook_search_limit)
                filtered_results = _filter_industry_results(industry_results, industry_label)
                industry_cache[cache_key] = _score_industry_outlook(filtered_results)
            industry_scores = {
                "industry_outlook_score": industry_cache[cache_key]["industry_outlook_score"],
            }
            industry_mentions = list(industry_cache[cache_key]["mentions"])

        context_rows.append(
            {
                "company_id": company_id,
                "company_name": company_name,
                "as_of_date": date.today().isoformat(),
                "source_type": "public_intelligence",
                **adverse_scores,
                **industry_scores,
                "notes": "Automated public-domain adverse-risk and industry-outlook scan.",
            }
        )
        for mention in adverse_mentions:
            mention_rows.append(
                {
                    "company_id": company_id,
                    "company_name": company_name,
                    "mention_type": "adverse_news",
                    **mention,
                }
            )
        for mention in industry_mentions:
            mention_rows.append(
                {
                    "company_id": company_id,
                    "company_name": company_name,
                    "mention_type": "industry_outlook",
                    **mention,
                }
            )

    pd.DataFrame(context_rows).to_csv(context_path, index=False)
    pd.DataFrame(mention_rows).to_csv(mentions_path, index=False)
    return {
        "public_mentions": mentions_path,
        "public_intelligence_context": context_path,
    }


def _score_adverse_mentions(results: list[dict[str, Any]]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    mention_rows: list[dict[str, Any]] = []
    counters = {
        "promoter_adverse_hits": 0,
        "public_negative_news_hits": 0,
        "fraud_signal_hits": 0,
        "regulatory_action_hits": 0,
        "insolvency_signal_hits": 0,
        "litigation_signal_hits": 0,
    }

    for rank, result in enumerate(results, start=1):
        blob = " ".join(
            [
                str(result.get("title") or ""),
                str(result.get("snippet") or ""),
                str(result.get("url") or ""),
            ]
        ).lower()
        categories = []
        for field, keywords in ADVERSE_KEYWORD_GROUPS.items():
            hits = sum(1 for keyword in keywords if keyword in blob)
            if hits:
                counters[field] += hits
                categories.append(field)
        if categories:
            counters["public_negative_news_hits"] += 1
        if "promoter" in blob or "director" in blob:
            counters["promoter_adverse_hits"] += int(bool(categories))
        mention_rows.append(
            {
                "rank": rank,
                "title": result.get("title"),
                "url": result.get("url"),
                "snippet": result.get("snippet"),
                "category_json": json.dumps(categories),
            }
        )

    public_risk_score = min(
        10.0,
        (
            (counters["fraud_signal_hits"] * 2.5)
            + (counters["regulatory_action_hits"] * 1.75)
            + (counters["insolvency_signal_hits"] * 2.25)
            + (counters["litigation_signal_hits"] * 1.25)
            + (counters["promoter_adverse_hits"] * 1.5)
            + (counters["public_negative_news_hits"] * 0.5)
        ),
    )
    counters["public_risk_score"] = round(float(public_risk_score), 4)
    counters["public_risk_flag"] = bool(public_risk_score >= 4.0)
    return counters, mention_rows


def _score_industry_outlook(results: list[dict[str, Any]]) -> dict[str, Any]:
    positive_hits = 0
    negative_hits = 0
    mentions: list[dict[str, Any]] = []

    for rank, result in enumerate(results, start=1):
        blob = " ".join(
            [
                str(result.get("title") or ""),
                str(result.get("snippet") or ""),
                str(result.get("url") or ""),
            ]
        ).lower()
        positive_hits += sum(1 for keyword in INDUSTRY_POSITIVE_KEYWORDS if keyword in blob)
        negative_hits += sum(1 for keyword in INDUSTRY_NEGATIVE_KEYWORDS if keyword in blob)
        mentions.append(
            {
                "rank": rank,
                "title": result.get("title"),
                "url": result.get("url"),
                "snippet": result.get("snippet"),
            }
        )

    outlook_score = max(-5.0, min(5.0, float(positive_hits - negative_hits)))
    return {
        "industry_outlook_score": round(outlook_score, 4),
        "mentions": mentions[:5],
    }


def _select_industry_label(row: dict[str, Any]) -> str:
    sub_industry = str(row.get("sub_industry") or "").strip()
    industry = str(row.get("industry") or "").strip()
    industry_group = str(row.get("industry_group") or "").strip()
    if sub_industry and sub_industry.casefold() not in {"other agricultural products", "other agri products"}:
        return sub_industry
    if industry:
        return industry
    return industry_group or sub_industry


def _filter_industry_results(results: list[dict[str, Any]], industry_label: str) -> list[dict[str, Any]]:
    if not results:
        return []
    label_tokens = {
        token
        for token in str(industry_label).lower().replace("&", " ").split()
        if len(token) > 3 and token not in {"india", "industry", "companies"}
    }
    filtered: list[dict[str, Any]] = []
    for result in results:
        resolved_url = unquote(str(result.get("url") or ""))
        parsed = urlparse(resolved_url)
        domain = (parsed.netloc or "").lower()
        blob = " ".join(
            [
                str(result.get("title") or ""),
                str(result.get("snippet") or ""),
                resolved_url,
            ]
        ).lower()
        if "wikipedia.org" in domain:
            continue
        if "climate change" in blob and not (label_tokens & {"edible", "oil", "sugar", "tea", "rice", "coffee"}):
            continue
        if label_tokens and not any(token in blob for token in label_tokens):
            continue
        filtered.append(result)
    return filtered if filtered else results[:3]
