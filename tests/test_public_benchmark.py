from agent import public_benchmark


def test_benchmark_records_expected_and_actual_results():
    results = public_benchmark.run()
    assert {r["category"] for r in results} >= {"method", "unsupported", "denominator", "missing_input"}
    assert all("expected" in r and "actual" in r for r in results)
    assert all(r["passed"] for r in results)
