"""Small, public, key-free contract benchmark; not a population accuracy estimate."""
import json
from pathlib import Path

import pandas as pd

from . import research

CASES = Path(__file__).with_name("public_benchmark_cases.json")


def run():
    import caveat
    fixture = json.loads(CASES.read_text())
    results = []
    for case in fixture["cases"]:
        category = case["category"]
        if category in ("method", "unsupported"):
            actual = "supported" if case["method"] in research.METHODS else "unsupported"
        elif category == "denominator":
            report = caveat.analyze(pd.DataFrame(case["data"]), question=case["question"])
            actual = "missing_denominator" if "missing_denominator" in report.kinds() else "not flagged"
        elif category == "missing_input":
            try:
                research.require_bayesian_inputs(case["parameters"])
                actual = "accepted"
            except ValueError:
                actual = "refused"
        else:
            raise ValueError(f"Unknown benchmark category: {category}")
        results.append({"version": fixture["version"], "id": case["id"], "category": category,
                        "expected": case["expected"], "actual": actual, "passed": actual == case["expected"]})
    return results


if __name__ == "__main__":
    rows = run()
    print(json.dumps(rows, indent=2))
    raise SystemExit(0 if all(row["passed"] for row in rows) else 1)
