"""Unit tests for RAG retrieval (uses the committed semantic_catalog.json; no key needed)."""
from agent import retrieval


def test_tokens_stem_plurals():
    toks = retrieval._tokens("patients conditions medications")
    assert {"patient", "condition", "medication"} <= set(toks)


def test_retrieve_surfaces_the_right_table():
    got = [t["name"] for t in retrieval.retrieve("how many patients are deceased?")["tables"]]
    assert "dim_patient" in got


def test_render_context_lists_tables_and_columns():
    ctx = retrieval.render_context(retrieval.retrieve("prevalence of hypertension by age group"))
    assert "AVAILABLE TABLES" in ctx and "columns:" in ctx
