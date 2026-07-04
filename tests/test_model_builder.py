"""Unit tests for the automated dbt model builder's pure logic (no dbt / no API key)."""
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
