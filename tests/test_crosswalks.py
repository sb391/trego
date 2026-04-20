from __future__ import annotations

from src.schemas.crosswalks import normalize_rating_label


def test_normalize_icra_inc_rating() -> None:
    result = normalize_rating_label("icra", "[ICRA]B+ (Stable); ISSUER NOT COOPERATING")
    assert result.scale_type == "long_term"
    assert result.normalized_label == "B+"
    assert result.outlook == "Stable"
    assert result.is_issuer_not_cooperating is True


def test_normalize_withdrawn_state_without_forced_rank() -> None:
    result = normalize_rating_label("acuite", "Not Applicable | Withdrawn")
    assert result.is_withdrawn is True
    assert result.normalized_label is None
    assert result.rating_rank_numeric is None


def test_normalize_legacy_crisil_p_scale_to_comparable_short_term_rank() -> None:
    result = normalize_rating_label("crisil", "P5")
    assert result.scale_type == "short_term"
    assert result.normalized_label == "D"
    assert result.rating_rank_numeric is not None
