"""Unit tests for the automated dbt model builder's pure logic (no dbt / no API key)."""
import pytest
import yaml

from agent import model_builder as mb


def test_slug_prefixes_and_sanitizes():
    assert mb._slug("Patient Med Spend") == "mart_gen_patient_med_spend"
    # a mart_ name is re-prefixed (never kept) so a generated model can't collide with / overwrite a real mart
    assert mb._slug("mart_cost_summary") == "mart_gen_cost_summary"


def test_count_tests():
    spec = {"tests": [
        {"column": "id", "checks": ["not_null", "unique"]},
        {"column": "amount", "checks": ["not_null"], "min_value": 0},
        {"column": "kind", "values": ["a", "b"]},
    ]}
    assert mb._count_tests(spec) == 2 + 2 + 1                        # 2 checks + (not_null+range) + values


def test_schema_yaml_renders_range_and_accepted_values():
    spec = {"description": "demo", "tests": [
        {"column": "patient_id", "checks": ["not_null", "unique"]},
        {"column": "total_cost", "checks": ["not_null"], "min_value": 0},
        {"column": "tier", "values": ["gold", "silver"]},
    ]}
    yml = mb._schema_yaml("mart_gen_demo", spec)
    assert "name: mart_gen_demo" in yml
    assert "- not_null" in yml and "- unique" in yml
    assert "dbt_utils.accepted_range" in yml and "min_value: 0" in yml   # range test, not accepted_values
    assert "accepted_values" in yml and 'values: ["gold", "silver"]' in yml


def test_schema_yaml_escapes_hostile_description():
    # the LLM writes the description; the sandbox blocks hooks in the .sql, so a YAML injection
    # here (a quote + a config: block with a pre_hook) must render as TEXT, never as structure —
    # dbt executes hooks with a read-write connection on `dbt build`
    hostile = 'handy summary"\n    config:\n      pre_hook: "delete from dim_patient"\n    x: "'
    spec = {"description": hostile, "tests": [{"column": "id", "checks": ["not_null"]}]}
    doc = yaml.safe_load(mb._schema_yaml("mart_gen_demo", spec))
    assert len(doc["models"]) == 1
    model = doc["models"][0]
    assert set(model.keys()) == {"name", "description", "columns"}   # no injected config/hooks
    assert model["description"] == hostile                           # survives as a literal string


def test_schema_yaml_rejects_non_identifier_column():
    # a column "name" carrying YAML structure is a hallucination or an attack — fail closed
    spec = {"description": "d",
            "tests": [{"column": 'id"\n    config: {pre_hook: "drop table x"}', "checks": ["not_null"]}]}
    with pytest.raises(mb.UnsafeModelError):
        mb._schema_yaml("mart_gen_demo", spec)


def test_schema_yaml_rejects_non_numeric_range_bounds():
    spec = {"description": "d",
            "tests": [{"column": "amount", "min_value": '0}\n    config: {pre_hook: "x"}'}]}
    with pytest.raises(mb.UnsafeModelError):
        mb._schema_yaml("mart_gen_demo", spec)


def test_schema_yaml_plain_specs_round_trip():
    # ordinary descriptions with awkward-but-benign characters must still parse and round-trip
    spec = {"description": "Per-patient spend: 100% of \"active\" meds, cost > $0",
            "tests": [{"column": "patient_id", "checks": ["not_null", "unique"]},
                      {"column": "tier", "values": ["gold", "silver"]},
                      {"column": "amount", "min_value": 0, "max_value": 1e9}]}
    doc = yaml.safe_load(mb._schema_yaml("mart_gen_x", spec))
    assert doc["models"][0]["description"] == spec["description"]
    cols = {c["name"]: c for c in doc["models"][0]["columns"]}
    assert set(cols) == {"patient_id", "tier", "amount"}
