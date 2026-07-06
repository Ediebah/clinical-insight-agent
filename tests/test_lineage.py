"""Tests for data-lineage / provenance (agent/lineage.py). Deterministic — reads the committed
semantic catalog (lineage baked in by build_catalog.py); no DB, no API key."""
from agent import lineage
from agent.retrieval import load_catalog

CAT = load_catalog()


def test_catalog_lineage_traces_to_raw_or_is_generated():
    # Synthea-derived tables trace back to a raw source; the two demo marts built from generate_series
    # (mart_experiments, mart_trials) honestly have NO upstream — the lineage reflects that.
    generated = {"mart_experiments", "mart_trials"}
    for t in CAT["tables"]:
        layers = {d["layer"] for d in t.get("upstream", [])}
        if t["name"] in generated:
            assert not t.get("upstream") and not t.get("depends_on")
        else:
            assert "raw" in layers, f"{t['name']} has no raw source in its lineage"
            assert t.get("depends_on"), f"{t['name']} has no immediate parents"


def test_detect_resolves_lineage_questions():
    assert lineage.detect("Where does the 30-day readmission rate come from?", CAT) == "mart_readmissions"
    assert lineage.detect("How is dim_patient built, and from what source?", CAT) == "dim_patient"
    assert lineage.detect("what feeds fct_encounters?", CAT) == "fct_encounters"


def test_detect_ignores_non_lineage_questions():
    # an ANALYSIS question that merely names a table must NOT be hijacked as a lineage question
    assert lineage.detect("What is the 30-day readmission rate by age group?", CAT) is None
    assert lineage.detect("How does patient survival differ by sex?", CAT) is None


def test_detect_noop_without_catalog():
    assert lineage.detect("where does the readmission rate come from?", None) is None


def test_downstream_direction():
    assert lineage.is_downstream("what depends on fct_encounters?") is True
    assert lineage.is_downstream("where does fct_encounters come from?") is False


def test_provenance_traces_readmissions():
    p = lineage.provenance("mart_readmissions", CAT)
    assert p["depends_on"] == ["fct_encounters"]
    assert "synthea.encounters" in p["sources"]
    upstream_names = {d["name"] for d in p["upstream"]}
    assert {"stg_encounters", "fct_encounters"} <= upstream_names


def test_downstream_of_lists_dependents():
    deps = lineage.downstream_of("fct_encounters", CAT)
    assert "mart_readmissions" in deps and "mart_cost_by_condition" in deps


def test_answer_upstream_and_downstream():
    up = lineage.answer("mart_readmissions", CAT)
    assert "comes from" in up and "synthea.encounters" in up and "fct_encounters" in up
    down = lineage.answer("fct_encounters", CAT, downstream=True)
    assert "depends on" in down.lower() and "mart_readmissions" in down


def test_for_tables_attaches_chains():
    lin = lineage.for_tables(["mart_readmissions", "dim_patient"], CAT)
    assert len(lin["tables"]) == 2
    assert any("stg_encounters" in t["chain"] for t in lin["tables"])
    assert "synthea.patients" in lin["sources"]
    # BYOD / no catalog / unresolved → None (no-op)
    assert lineage.for_tables(["mart_readmissions"], None) is None
    assert lineage.for_tables(["not_a_real_table"], CAT) is None
