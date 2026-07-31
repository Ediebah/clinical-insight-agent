"""Bounded, in-memory extraction of text evidence from publication PDFs."""

from __future__ import annotations

import hashlib
import io
import re
import unicodedata
from pathlib import Path
from typing import Any

from pypdf import PdfReader
from pypdf.errors import PdfReadError

MAX_PDF_BYTES = 10 * 1024 * 1024
MAX_PDF_PAGES = 40
MAX_TOTAL_TEXT_CHARS = 120_000
MAX_LLM_CONTEXT_CHARS = 40_000
MIN_EXTRACTED_TEXT_CHARS = 100

_PASSAGE_CHARS = 4_000
_PASSAGE_OVERLAP = 400
_KEYWORDS = (
    "interim",
    "predictive probability",
    "futility",
    "beta",
    "posterior",
    "response",
    "sample size",
    "boundary",
    "go/no-go",
    "early stop",
    "single-arm",
)


def extract_pdf_evidence(data: bytes, filename: str = "publication.pdf") -> dict[str, Any]:
    """Extract bounded page text from a text-based PDF without writing it to disk."""
    if not isinstance(data, bytes) or not data:
        raise ValueError("The uploaded PDF is empty.")
    if len(data) > MAX_PDF_BYTES:
        raise ValueError("The PDF exceeds the 10 MB upload limit.")
    if not data.lstrip().startswith(b"%PDF-"):
        raise ValueError("The uploaded file is not a valid PDF.")

    try:
        reader = PdfReader(io.BytesIO(data), strict=True)
    except (PdfReadError, OSError, ValueError) as exc:
        raise ValueError("The PDF could not be read. Upload an unencrypted text-based PDF.") from exc

    if reader.is_encrypted:
        raise ValueError("Encrypted PDFs are not supported.")
    page_count = len(reader.pages)
    if page_count == 0:
        raise ValueError("The PDF has no pages.")
    if page_count > MAX_PDF_PAGES:
        raise ValueError(f"The PDF has {page_count} pages; the limit is {MAX_PDF_PAGES}.")

    pages: list[dict[str, Any]] = []
    total_chars = 0
    text_page_count = 0
    for page_number, page in enumerate(reader.pages, start=1):
        try:
            page_text = page.extract_text() or ""
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"Text extraction failed on page {page_number}.") from exc
        page_text = _normalize_page_text(page_text)
        remaining = max(0, MAX_TOTAL_TEXT_CHARS - total_chars)
        page_text = page_text[:remaining]
        if page_text:
            text_page_count += 1
            total_chars += len(page_text)
        pages.append({"page": page_number, "text": page_text})
        if total_chars >= MAX_TOTAL_TEXT_CHARS:
            break

    if total_chars < MIN_EXTRACTED_TEXT_CHARS:
        raise ValueError(
            "No usable text was found. This workflow does not support scanned or image-only PDFs yet."
        )

    safe_name = Path(filename or "publication.pdf").name.replace("\x00", "")
    return {
        "filename": safe_name or "publication.pdf",
        "sha256": hashlib.sha256(data).hexdigest(),
        "page_count": page_count,
        "text_page_count": text_page_count,
        "extracted_chars": total_chars,
        "pages": pages,
    }


def select_relevant_passages(
    document: dict[str, Any], *, focus_pages: set[int] | None = None
) -> str:
    """Return page-labelled passages within a fixed model context cap.

    The first two front-matter passages are retained for publication identity.
    When a user selects a worked scenario, its cited pages receive the highest
    priority so that a different example in the same methods paper cannot win
    the relevance ranking by accident.
    """
    pages = document.get("pages") or []
    focus_pages = set(focus_pages or ())
    candidates: list[tuple[int, int, int, str]] = []
    for page in pages:
        page_number = int(page.get("page") or 0)
        text = str(page.get("text") or "").strip()
        if not text:
            continue
        start = 0
        window_index = 0
        while start < len(text):
            passage = text[start : start + _PASSAGE_CHARS].strip()
            if passage:
                lowered = passage.casefold()
                keyword_score = sum(lowered.count(keyword) for keyword in _KEYWORDS)
                numeric_score = min(8, len(re.findall(r"\b\d+(?:\.\d+)?%?\b", passage)))
                front_matter_bonus = 2_000 if page_number <= 2 and window_index == 0 else 0
                focus_bonus = 4_000 if page_number in focus_pages else 0
                candidates.append(
                    (
                        keyword_score * 4 + numeric_score + front_matter_bonus + focus_bonus,
                        page_number,
                        start,
                        passage,
                    )
                )
            if start + _PASSAGE_CHARS >= len(text):
                break
            start += _PASSAGE_CHARS - _PASSAGE_OVERLAP
            window_index += 1

    selected: list[tuple[int, int, str]] = []
    used_chars = 0
    for _score, page_number, start, passage in sorted(
        candidates, key=lambda item: (-item[0], item[1], item[2])
    ):
        labelled = f"=== PAGE {page_number} ===\n{passage}"
        if used_chars + len(labelled) > MAX_LLM_CONTEXT_CHARS:
            continue
        selected.append((page_number, start, labelled))
        used_chars += len(labelled) + 2
        if used_chars >= MAX_LLM_CONTEXT_CHARS - _PASSAGE_CHARS:
            break

    if not selected:
        raise ValueError("No usable PDF passages were available for design extraction.")
    selected.sort(key=lambda item: (item[0], item[1]))
    return "\n\n".join(labelled for _page, _start, labelled in selected)


def page_contains_quote(document: dict[str, Any], page_number: int, quote: str) -> bool:
    """Check whether a short citation quote occurs on its claimed PDF page."""
    if not isinstance(page_number, int) or page_number < 1:
        return False
    cleaned_quote = _normalize_for_match(quote)
    if not cleaned_quote or len(cleaned_quote) > 500:
        return False
    for page in document.get("pages") or []:
        if page.get("page") == page_number:
            return cleaned_quote in _normalize_for_match(str(page.get("text") or ""))
    return False


def _normalize_page_text(text: str) -> str:
    text = text.replace("\x00", " ").replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _normalize_for_match(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", str(text or ""))
    normalized = normalized.replace("\u00ad", "")
    normalized = re.sub(r"(?<=\w)-\s+(?=\w)", "", normalized)
    normalized = normalized.translate(
        str.maketrans(
            {
                "‐": "-",
                "‑": "-",
                "‒": "-",
                "–": "-",
                "—": "-",
                "−": "-",
                "‘": "'",
                "’": "'",
                "“": '"',
                "”": '"',
            }
        )
    )
    normalized = re.sub(r"(?<=\w)-(?=\w)", "", normalized)
    normalized = re.sub(r"\s+([,.;:!?%)\]])", r"\1", normalized)
    normalized = re.sub(r"([(\[])\s+", r"\1", normalized)
    return " ".join(normalized.split()).casefold()
