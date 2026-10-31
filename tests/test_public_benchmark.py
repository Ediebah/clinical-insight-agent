import json

import pytest

from agent import public_benchmark, research


def test_benchmark_records_expected_and_actual_results():
    results = public_benchmark.run()
    assert {r["category"] for r in results} >= {"method", "unsupported", "denominator", "missing_input"}
    assert all("expected" in r and "actual" in r for r in results)
    assert not public_benchmark.has_unexpected_failures(results)


def test_benchmark_reports_known_denominator_failure_and_refuses_missing_assumptions():
    results = {row["id"]: row for row in public_benchmark.run()}
    assert results["inconsistent_rate_denominator"]["expected"] != results["inconsistent_rate_denominator"]["actual"]
    assert not results["inconsistent_rate_denominator"]["passed"]
    assert results["inconsistent_rate_denominator"]["status"] == "known_failure"
    assert results["missing_method_assumptions"]["passed"]
    assert results["consistent_rate_denominator"]["passed"]


def test_unexpected_failure_cannot_be_hidden_as_known():
    rows = [{"passed": False, "status": "unexpected_failure"}]
    assert public_benchmark.has_unexpected_failures(rows)


def test_blank_assumption_is_refused():
    cases = json.loads(public_benchmark.CASES.read_text())["cases"]
    spec = next(case["specification"] for case in cases if case["id"] == "missing_method_assumptions")
    spec["assumptions"] = ["   "]
    with pytest.raises(ValueError, match="non-empty statement"):
        research.validate_spec(spec)
