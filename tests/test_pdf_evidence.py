"""Tests for bounded, page-preserving publication PDF extraction."""

import io

import pytest
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from agent import pdf_evidence


def make_text_pdf(page_texts: list[str]) -> bytes:
    writer = PdfWriter()
    for text in page_texts:
        page = writer.add_blank_page(width=612, height=792)
        font = DictionaryObject(
            {
                NameObject("/Type"): NameObject("/Font"),
                NameObject("/Subtype"): NameObject("/Type1"),
                NameObject("/BaseFont"): NameObject("/Helvetica"),
            }
        )
        page[NameObject("/Resources")] = DictionaryObject(
            {NameObject("/Font"): DictionaryObject({NameObject("/F1"): font})}
        )
        escaped = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        stream = DecodedStreamObject()
        stream.set_data(f"BT /F1 10 Tf 72 720 Td ({escaped}) Tj ET".encode("latin-1"))
        page[NameObject("/Contents")] = stream
    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()


def test_extracts_text_with_page_numbers_and_document_fingerprint():
    data = make_text_pdf(
        [
            "Single-arm binary interim design with 8 responses among 25 patients. "
            "The planned sample size is 50 with a Beta 1,1 prior and a 20 percent futility cutoff."
        ]
    )

    document = pdf_evidence.extract_pdf_evidence(data, "../chen-example.pdf")

    assert document["filename"] == "chen-example.pdf"
    assert document["page_count"] == 1
    assert document["text_page_count"] == 1
    assert len(document["sha256"]) == 64
    assert document["pages"][0]["page"] == 1
    assert "8 responses among 25" in document["pages"][0]["text"]


def test_rejects_non_pdf_and_oversized_input_before_parsing():
    with pytest.raises(ValueError, match="not a valid PDF"):
        pdf_evidence.extract_pdf_evidence(b"not a pdf", "bad.pdf")
    with pytest.raises(ValueError, match="10 MB"):
        pdf_evidence.extract_pdf_evidence(b"%PDF-" + b"0" * pdf_evidence.MAX_PDF_BYTES, "huge.pdf")


def test_rejects_image_only_pdf_and_page_count_over_limit():
    with pytest.raises(ValueError, match="image-only"):
        pdf_evidence.extract_pdf_evidence(make_text_pdf([""]), "scan.pdf")
    with pytest.raises(ValueError, match="limit is 40"):
        pdf_evidence.extract_pdf_evidence(
            make_text_pdf(["enough text " * 12] * (pdf_evidence.MAX_PDF_PAGES + 1)),
            "long.pdf",
        )


def test_selects_labelled_passages_and_validates_exact_page_quote():
    document = {
        "pages": [
            {"page": 1, "text": "Background material " * 20},
            {
                "page": 7,
                "text": "At interim, 8 responses among 25 patients gave predictive probability 10.5%.",
            },
        ]
    }

    passages = pdf_evidence.select_relevant_passages(document)

    assert "=== PAGE 7 ===" in passages
    assert pdf_evidence.page_contains_quote(
        document, 7, "8 responses   among 25 patients"
    )
    assert not pdf_evidence.page_contains_quote(document, 1, "8 responses among 25 patients")
