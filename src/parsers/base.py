from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from ..schemas.models import Company, ParsedRationaleBundle, ParserMessage, RationaleDocument, RationaleFeatures
from ..utils import extract_sections, slugify
from .common import (
    determine_document_type,
    extract_analytical_approach,
    extract_feature_flags,
    extract_inline_section,
    extract_key_financial_indicators,
    extract_key_points,
    extract_liquidity_label,
    extract_qualitative_summary,
    extract_standalone_or_consolidated,
    infer_company_name_from_text,
    infer_doc_date,
    split_sensitivities,
)


class BaseAgencyParser(ABC):
    agency_name: str
    parser_name: str
    extra_section_aliases: dict[str, tuple[str, ...]] = {}

    def __init__(self) -> None:
        self._warnings: list[ParserMessage] = []
        self._errors: list[ParserMessage] = []

    def parse(
        self,
        *,
        pdf_path: Path,
        source_file: str,
        text: str,
        text_hash: str,
        extractor_used: str,
    ) -> ParsedRationaleBundle:
        self._warnings = []
        self._errors = []

        sections = extract_sections(text, self.extra_section_aliases or None)
        company_name = self.extract_company_name(text=text, source_file=source_file)
        rating_date = self.extract_rating_date(text=text)
        rationale_doc_id = self._build_doc_id(company_name=company_name, text_hash=text_hash)

        if not company_name:
            self.warn("Missing company name after parser heuristics.", field_name="company_name")
            company_name = Path(source_file).stem
        if not rating_date:
            self.warn("Missing rating date.", field_name="rating_date")

        company = Company(
            company_id=slugify(company_name),
            company_name=company_name,
        )
        document = RationaleDocument(
            rationale_doc_id=rationale_doc_id,
            company_name=company_name,
            agency_name=self.agency_name,
            doc_date=rating_date,
            source_file=source_file,
            pdf_path=str(pdf_path),
            parsed_status="parsed",
            document_type=determine_document_type(text),
            text_hash=text_hash,
        )

        analytical_approach = extract_analytical_approach(text, sections)
        standalone_or_consolidated = extract_standalone_or_consolidated(text, analytical_approach)
        strengths_source = sections.get("strengths") or extract_inline_section(
            text,
            start_aliases=("Key Rating Drivers - Strengths", "Key strengths", "Strengths"),
            end_aliases=("Key Rating Drivers - Weaknesses", "Key weaknesses", "Weaknesses", "Liquidity", "Rating sensitivity factors"),
        )
        weaknesses_source = sections.get("weaknesses") or extract_inline_section(
            text,
            start_aliases=("Key Rating Drivers - Weaknesses", "Key weaknesses", "Weaknesses"),
            end_aliases=("Liquidity", "Rating sensitivity factors", "About the Company", "About the company"),
        )
        strengths = extract_key_points(strengths_source)
        weaknesses = extract_key_points(weaknesses_source)
        sensitivities_up, sensitivities_down = split_sensitivities(sections.get("rating_sensitivities"))
        feature_flags = extract_feature_flags(text, sections)

        features = RationaleFeatures(
            rationale_doc_id=rationale_doc_id,
            agency_name=self.agency_name,
            company_name=company_name,
            analytical_approach=analytical_approach,
            standalone_or_consolidated=standalone_or_consolidated,
            liquidity_label=extract_liquidity_label(text, sections),
            strengths_json=strengths,
            weaknesses_json=weaknesses,
            sensitivities_up_json=sensitivities_up,
            sensitivities_down_json=sensitivities_down,
            qualitative_summary=extract_qualitative_summary(sections),
            **feature_flags,
        )

        rating_events = self.extract_rating_events(
            text=text,
            sections=sections,
            rationale_doc_id=rationale_doc_id,
            company_name=company_name,
            rating_date=rating_date,
        )
        if not rating_events:
            self.warn("No rating events extracted from the document.", field_name="rating_events")

        bundle = ParsedRationaleBundle(
            company=company,
            rationale_document=document,
            rationale_features=features,
            rating_events=rating_events,
            key_financial_indicators=extract_key_financial_indicators(sections.get("key_financial_indicators")),
            sections=sections,
            parser_name=self.parser_name,
            extracted_text_method=extractor_used,
            warnings=list(self._warnings),
            errors=list(self._errors),
        )
        return bundle

    def extract_company_name(self, *, text: str, source_file: str) -> str:
        return infer_company_name_from_text(text, agency_name=self.agency_name, source_file=source_file)

    def extract_rating_date(self, *, text: str):
        return infer_doc_date(text)

    @abstractmethod
    def extract_rating_events(
        self,
        *,
        text: str,
        sections: dict[str, str],
        rationale_doc_id: str,
        company_name: str,
        rating_date,
    ):
        raise NotImplementedError

    def warn(self, message: str, *, field_name: str | None = None) -> None:
        self._warnings.append(
            ParserMessage(
                severity="warning",
                message=message,
                field_name=field_name,
                parser_name=self.parser_name,
            )
        )

    def error(self, message: str, *, field_name: str | None = None) -> None:
        self._errors.append(
            ParserMessage(
                severity="error",
                message=message,
                field_name=field_name,
                parser_name=self.parser_name,
            )
        )

    def _build_doc_id(self, *, company_name: str, text_hash: str) -> str:
        return f"{self.agency_name}__{slugify(company_name)}__{text_hash[:12]}"
