from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import fitz
import pdfplumber
from pypdf import PdfReader

from .text import compute_text_hash, normalize_multiline_text


logging.getLogger("pypdf").setLevel(logging.ERROR)
logging.getLogger("pypdf._reader").setLevel(logging.ERROR)


AGENCY_DETECTION_PATTERNS = {
    "crisil": ("crisil ratings", "crisil limited", "crisil"),
    "care": ("care ratings", "careedge ratings", "careedge"),
    "india_ratings": ("india ratings and research", "ind-ra", "india ratings"),
    "acuite": ("acuite ratings", "acuite ratings & research", "acuite"),
    "brickwork": ("brickwork ratings", "bwr "),
    "infomerics": ("infomerics", "ivr "),
    "icra": ("icra",),
}


@dataclass(slots=True)
class ExtractedPdfText:
    text: str
    extractor_used: str
    page_count: int
    text_hash: str


def extract_pdf_text(pdf_path: Path) -> ExtractedPdfText:
    candidates: list[tuple[str, str, int]] = []

    for extractor_name, extractor in (
        ("pdfplumber", _extract_with_pdfplumber),
        ("pymupdf", _extract_with_pymupdf),
        ("pypdf", _extract_with_pypdf),
    ):
        try:
            text, page_count = extractor(pdf_path)
        except Exception:
            continue
        normalized = normalize_multiline_text(text)
        if normalized:
            candidates.append((extractor_name, normalized, page_count))

    if not candidates:
        raise ValueError(f"Unable to extract text from {pdf_path}")

    extractor_used, text, page_count = max(candidates, key=lambda item: len(item[1]))
    return ExtractedPdfText(
        text=text,
        extractor_used=extractor_used,
        page_count=page_count,
        text_hash=compute_text_hash(text),
    )


def detect_agency_name(source_file: str, text: str) -> str:
    lowered = f"{source_file}\n{text[:3000]}".lower()
    for agency_name, tokens in AGENCY_DETECTION_PATTERNS.items():
        if any(token in lowered for token in tokens):
            return agency_name
    raise ValueError(f"Unable to detect rating agency for {source_file}")


def _extract_with_pdfplumber(pdf_path: Path) -> tuple[str, int]:
    pages: list[str] = []
    with pdfplumber.open(pdf_path) as pdf:
        for page_number, page in enumerate(pdf.pages, start=1):
            page_text = page.extract_text() or ""
            pages.append(f"=== Page {page_number} ===\n{page_text}")
        return "\n\n".join(pages), len(pdf.pages)


def _extract_with_pymupdf(pdf_path: Path) -> tuple[str, int]:
    pages: list[str] = []
    with fitz.open(pdf_path) as pdf:
        for page_number, page in enumerate(pdf, start=1):
            page_text = page.get_text("text") or ""
            pages.append(f"=== Page {page_number} ===\n{page_text}")
        return "\n\n".join(pages), len(pdf)


def _extract_with_pypdf(pdf_path: Path) -> tuple[str, int]:
    pages: list[str] = []
    reader = PdfReader(str(pdf_path))
    for page_number, page in enumerate(reader.pages, start=1):
        page_text = page.extract_text() or ""
        pages.append(f"=== Page {page_number} ===\n{page_text}")
    return "\n\n".join(pages), len(reader.pages)
