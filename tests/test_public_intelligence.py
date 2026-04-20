from __future__ import annotations

from src.credit_intel.public_intelligence import _score_adverse_mentions, _score_industry_outlook


def test_score_adverse_mentions_detects_risk_categories() -> None:
    scores, mentions = _score_adverse_mentions(
        [
            {
                "title": "Company faces SEBI penalty after default concerns",
                "snippet": "The company and promoter are under regulatory review after a default and lawsuit filing.",
                "url": "https://example.com/sebi-penalty",
            },
            {
                "title": "Fraud probe opened against director",
                "snippet": "SFIO and ED raid allegations continue.",
                "url": "https://example.com/fraud-probe",
            },
        ]
    )

    assert scores["public_negative_news_hits"] >= 2
    assert scores["fraud_signal_hits"] >= 1
    assert scores["regulatory_action_hits"] >= 1
    assert scores["insolvency_signal_hits"] >= 1
    assert scores["litigation_signal_hits"] >= 1
    assert scores["promoter_adverse_hits"] >= 1
    assert scores["public_risk_score"] > 0
    assert bool(scores["public_risk_flag"]) is True
    assert len(mentions) == 2


def test_score_industry_outlook_balances_positive_and_negative_signals() -> None:
    result = _score_industry_outlook(
        [
            {
                "title": "Industry growth and export demand improve outlook",
                "snippet": "A supportive demand recovery and expansion cycle is visible.",
                "url": "https://example.com/growth",
            },
            {
                "title": "Sector faces pressure from inflation and slowdown",
                "snippet": "Weak demand and regulatory risk may continue.",
                "url": "https://example.com/pressure",
            },
        ]
    )

    assert "industry_outlook_score" in result
    assert "mentions" in result
    assert len(result["mentions"]) == 2
