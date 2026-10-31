import math

from scripts.run_causal_evaluation import summarize


def test_summary_reports_monte_carlo_uncertainty_and_coverage():
    rows = [
        {"estimate": {"estimate": 1.0, "low": 0.0, "high": 3.0}},
        {"estimate": {"estimate": 3.0, "low": 2.1, "high": 4.0}},
        {"error": "failed fit"},
    ]
    result = summarize(rows, "estimate")
    assert result["successful"] == 2
    assert result["bias"] == 0.0
    assert math.isclose(result["bias_mcse"], 1.0)
    assert result["coverage"] == 0.5
    assert result["coverage_wilson_95"][0] < 0.5 < result["coverage_wilson_95"][1]


def test_summary_handles_no_successful_fits():
    result = summarize([{"error": "failed fit"}], "estimate")
    assert result["successful"] == 0
    assert result["bias"] is None
    assert result["coverage"] is None
