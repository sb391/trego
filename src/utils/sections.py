from __future__ import annotations

import re

from .text import compact_spaces, normalize_multiline_text


DEFAULT_SECTION_ALIASES: dict[str, tuple[str, ...]] = {
    "summary_of_rating_action": (
        "Summary of rating action",
        "Rating Action",
        "Summary of rating action / facilities",
        "Summary of Rating Actions",
        "Details of Instruments",
        "Facilities/Instruments",
        "Ratings",
    ),
    "rationale": (
        "Detailed Rationale",
        "Detailed Rationale of the Rating Action",
        "Rationale and key rating drivers",
        "Rationale for Rating",
        "Rationale",
        "Detailed description of key rating drivers",
    ),
    "analytical_approach": ("Analytical Approach", "Analytical approach"),
    "strengths": ("Strengths", "Key strengths", "Key Rating Drivers - Strengths"),
    "weaknesses": ("Weaknesses", "Key weaknesses", "Key Rating Drivers - Weaknesses"),
    "liquidity": (
        "Liquidity",
        "Liquidity:",
        "Liquidity Adequate",
        "Liquidity: Adequate",
        "Liquidity: Strong",
        "Liquidity position",
    ),
    "rating_sensitivities": (
        "Rating sensitivity factors",
        "Key Rating Sensitivities",
        "Rating Sensitivities",
        "Upward Factors",
        "Downward Factors",
    ),
    "key_financial_indicators": ("Key Financial Indicators", "Key financial indicators"),
    "about_company": ("About the Company", "About the company", "ABOUT THE ENTITY"),
    "rating_history": ("Rating history for past three years", "RATING HISTORY FOR THE PREVIOUS THREE YEARS"),
    "rating_action_outlook": ("RATING ACTION / OUTLOOK / NATURE OF NON-COOPERATION",),
    "key_rating_drivers": ("Key Rating Drivers", "List of Key Rating Drivers"),
}


def extract_sections(text: str, section_aliases: dict[str, tuple[str, ...]] | None = None) -> dict[str, str]:
    aliases = section_aliases or DEFAULT_SECTION_ALIASES
    normalized_text = normalize_multiline_text(text)
    lines = normalized_text.splitlines()
    matches: list[tuple[int, str, int, str]] = []

    for index, line in enumerate(lines):
        compact = compact_spaces(line)
        if not compact:
            continue
        for section_name, candidates in aliases.items():
            matched_alias = _match_heading(compact, candidates)
            if matched_alias:
                matches.append((index, section_name, len(matched_alias), compact))
                break

    sections: dict[str, str] = {}
    for match_index, (line_index, section_name, heading_length, line_text) in enumerate(matches):
        next_index = matches[match_index + 1][0] if match_index + 1 < len(matches) else len(lines)
        inline_suffix = compact_spaces(line_text[heading_length:].lstrip(":|-"))
        section_lines = []
        if inline_suffix:
            section_lines.append(inline_suffix)
        section_lines.extend(lines[line_index + 1 : next_index])
        sections[section_name] = normalize_multiline_text("\n".join(section_lines))
    return sections


def _match_heading(line: str, aliases: tuple[str, ...]) -> str | None:
    for alias in aliases:
        pattern = rf"^{re.escape(alias)}(?:\s*[:|\-].*)?$"
        if re.match(pattern, line, flags=re.I):
            return alias
    return None
