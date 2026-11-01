"""The About page's copy carries load-bearing claims — assert they survive editing.

about.py is prose, so it invites casual edits, and it is the first thing every visitor reads. The
disclosures here (synthetic data, no PHI, read-only, the row cap) are the ones a reader relies on
before uploading anything, and the counts are the ones a reader would check against the repo. A
rewrite that quietly drops one of them should fail CI rather than ship.

Deliberately no Streamlit import: about.py is stdlib-only precisely so this runs without the app
harness.
"""
from pathlib import Path

import duckdb

import about


def test_about_md_is_assembled():
    assert len(about.ABOUT_MD) > 1500
    assert about.ABOUT_MD.startswith("# ")


def test_the_data_disclosures_survive():
    """These four are what someone relies on before uploading a file. Losing one is a real defect."""
    md = about.ABOUT_MD.lower()
    assert "synthetic" in md
    assert "non-sensitive" in md
    assert "no phi anywhere in the system" not in md.replace("**", "")
    assert "read-only" in md
    assert "1,000 rows" in md


def test_the_warehouse_counts_match_the_manifest():
    """26 models / 108 tests / 1,334 patients are verified against warehouse/target/manifest.json
    and the shipped demo DB — see the design spec §5. Changing the copy alone must not pass."""
    facts = {label: value for label, value, _ in about.DATA_FACTS}
    assert facts["dbt models"] == "26"
    assert facts["Data tests"] == "108"
    demo = Path(__file__).resolve().parents[1] / "data" / "healthcare_demo.duckdb"
    with duckdb.connect(str(demo), read_only=True) as connection:
        patient_count = connection.execute("select count(*) from main.dim_patient").fetchone()[0]
    assert facts["Patients"] == f"{patient_count:,}"
    assert facts["Queryable tables"] == "16"


def test_models_and_queryable_tables_are_stated_separately():
    """26 is the model count; only 16 are materialized in the demo warehouse. Conflating them
    would tell a user they can query ten tables that aren't there."""
    values = [v for _, v, _ in about.DATA_FACTS]
    assert "26" in values and "16" in values


def test_absence_claim_is_scoped_to_named_conditions():
    """agent/vocabulary.py only declares a term absent when it is recognized as a condition; free
    text falls through to the zero-row self-heal. The copy must not promise more than that."""
    limits = " ".join(head + " " + body for head, body in about.LIMITS).lower()
    assert "name a condition" in limits


def test_every_question_cell_is_complete():
    for q, d, t in about.QUESTION_CELLS:
        assert q.endswith("?"), q
        assert len(d) > 40 and d.endswith(".")
        assert t and "·" in t


def test_pipeline_steps_are_numbered_in_order():
    assert [n for n, _, _ in about.PIPELINE] == ["01", "02", "03", "04", "05", "06"]
