"""Smoke test: the Streamlit app renders end-to-end without an exception (no API key needed).

app.py is the deployed surface, but nothing else imports it — without this test a syntax error or a
broken import in app.py ships green (all unit tests pass, CI import-smoke covers only agent.*).
AppTest executes the real script against the committed demo warehouse in Streamlit's test harness.
"""
import io

from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject
from streamlit.testing.v1 import AppTest


def _publication_pdf() -> bytes:
    text = (
        "Single-arm binary interim design. At interim, 8 responses among 25 patients were observed. "
        "Planned sample size was 50. Beta 1,1 prior. Final success required response rate above 30 "
        "percent with posterior probability above 95 percent. Futility cutoff was 20 percent."
    )
    writer = PdfWriter()
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
    stream = DecodedStreamObject()
    stream.set_data(f"BT /F1 10 Tf 72 720 Td ({text}) Tj ET".encode("latin-1"))
    page[NameObject("/Contents")] = stream
    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()


def test_app_renders_without_exception():
    at = AppTest.from_file("app.py", default_timeout=120)
    at.run()
    assert not at.exception, [str(e.value) for e in at.exception]
    assert at.title or at.markdown or at.tabs        # something actually rendered


def test_reproduction_protocol_lock_runs_confirmed_design(monkeypatch):
    from agent import reproduction

    parsed = {
        "publication_title": "Chen et al. (2019)",
        "doi": "10.21037/tcr.2019.05.17",
        "endpoint_type": "single_arm_binary",
        "observed_successes": 8,
        "observed_n": 25,
        "planned_n": 50,
        "prior_a": 1,
        "prior_b": 1,
        "efficacy_reference": 0.30,
        "efficacy_gate": 0.95,
        "futility_cutoff": 0.20,
        "published_predictive_probability": 0.105,
        "published_final_boundary": 21,
        "published_decision": "STOP",
        "missing_fields": [],
    }
    monkeypatch.setattr(reproduction, "parse_published_design", lambda _text: parsed.copy())

    at = AppTest.from_file("app.py", default_timeout=120).run()
    at.segmented_control[0].set_value("🧾 Reproduce").run()
    at.button(key="repro_load_example").click().run()
    at.button(key="repro_parse").click().run()

    assert not at.exception, [str(e.value) for e in at.exception]
    assert at.text_input(key="repro_gate").value == "0.95"
    assert at.text_input(key="repro_futility").value == "0.2"

    at.checkbox(key="repro_confirm").check()
    at.button(key="FormSubmitter:repro_lock_form-Confirm protocol lock and reproduce").click().run()

    assert not at.exception, [str(e.value) for e in at.exception]
    assert any("MATCH" in str(item.value) for item in at.markdown)
    assert any("Protocol lock · confirmed inputs" in str(item.value) for item in at.markdown)
    assert any("comparison-table" in str(item.value) for item in at.markdown)


def test_reproduction_pdf_mode_exposes_bounded_upload_path():
    at = AppTest.from_file("app.py", default_timeout=120).run()
    at.segmented_control[0].set_value("🧾 Reproduce").run()
    at.radio(key="repro_source_mode").set_value("Upload publication PDF").run()

    assert not at.exception, [str(e.value) for e in at.exception]
    assert at.file_uploader(key="repro_pdf")
    assert at.button(key="repro_parse_pdf")
    assert any("text-based PDFs only" in str(item.value) for item in at.markdown)


def test_reproduction_pdf_upload_populates_page_linked_protocol_lock(monkeypatch):
    from agent import reproduction

    def fake_parse(document):
        return {
            "publication_title": "Uploaded trial",
            "doi": "10.1234/upload.1",
            "endpoint_type": "single_arm_binary",
            "observed_successes": 8,
            "observed_n": 25,
            "planned_n": 50,
            "prior_a": 1,
            "prior_b": 1,
            "efficacy_reference": 0.30,
            "efficacy_gate": 0.95,
            "futility_cutoff": 0.20,
            "published_predictive_probability": None,
            "published_final_boundary": None,
            "published_decision": None,
            "missing_fields": [],
            "source_mode": "pdf",
            "source_filename": document["filename"],
            "source_sha256": document["sha256"],
            "source_page_count": document["page_count"],
            "source_text_page_count": document["text_page_count"],
            "evidence": {
                "observed_n": {
                    "page": 1,
                    "quote": "At interim, 8 responses among 25 patients were observed.",
                }
            },
            "citation_warnings": [],
        }

    monkeypatch.setattr(reproduction, "parse_published_pdf_design", fake_parse)
    at = AppTest.from_file("app.py", default_timeout=120).run()
    at.segmented_control[0].set_value("🧾 Reproduce").run()
    at.radio(key="repro_source_mode").set_value("Upload publication PDF").run()
    at.file_uploader(key="repro_pdf").upload(
        "uploaded-trial.pdf", _publication_pdf(), "application/pdf"
    ).run()
    at.button(key="repro_parse_pdf").click().run()

    assert not at.exception, [str(e.value) for e in at.exception]
    assert at.text_input(key="repro_observed_n").value == "25"
    assert any("PDF EVIDENCE" in str(item.value) for item in at.markdown)
    assert any("PAGE 1" in str(item.value) for item in at.markdown)
    assert any("uploaded-trial.pdf" in str(item.value) for item in at.markdown)

    at.checkbox(key="repro_confirm").check()
    at.button(key="FormSubmitter:repro_lock_form-Confirm protocol lock and reproduce").click().run()

    assert not at.exception, [str(e.value) for e in at.exception]
    assert any("PDF source: uploaded-trial.pdf" in str(item.value) for item in at.caption)
