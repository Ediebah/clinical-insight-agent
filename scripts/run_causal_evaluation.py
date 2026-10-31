"""Execute the fixed synthetic evaluation protocol and save aggregate evidence."""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import math
import platform
import sys
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from scipy.stats import binomtest

from agent import causal_simulation, modeling

ROOT = Path(__file__).resolve().parents[1]
SCENARIOS = causal_simulation.SCENARIOS


def fingerprint(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_one(task: tuple[str, int, int]) -> dict:
    scenario, seed, n = task
    row = {"scenario": scenario, "seed": seed}
    try:
        frame = causal_simulation.generate(seed, n, scenario)
        estimate, low, high = causal_simulation.oracle(frame, scenario)
        if not all(math.isfinite(x) for x in (estimate, low, high)) or low > high:
            raise ValueError("Non-finite or invalid oracle interval")
        row["oracle"] = {"estimate": estimate, "low": low, "high": high}
    except Exception as exc:
        row["oracle_error"] = f"{type(exc).__name__}: {exc}"
        return row
    try:
        result = modeling.fit_uplift(frame, "outcome", "treatment", ["x", "z"])
        if result.error or not result.terms:
            raise ValueError(result.error or "No estimate returned")
        term = result.terms[0]
        values = [term.estimate, term.ci_low, term.ci_high,
                  result.robustness["propensity"]["clipped_fraction"]]
        if not all(math.isfinite(x) for x in values) or values[1] > values[2]:
            raise ValueError("Non-finite estimate, interval, or clipping fraction")
        row["estimate"] = {"estimate": values[0], "low": values[1],
                           "high": values[2], "clipped_fraction": values[3]}
    except Exception as exc:
        row["error"] = f"{type(exc).__name__}: {exc}"
    return row


def summarize(rows: list[dict], key: str) -> dict:
    data = [row[key] for row in rows if key in row]
    if not data:
        return {"successful": 0, "bias": None, "bias_mcse": None,
                "coverage": None, "coverage_wilson_95": None}
    estimates = np.asarray([row["estimate"] for row in data])
    count = sum(row["low"] <= 2.0 <= row["high"] for row in data)
    ci = binomtest(count, len(data)).proportion_ci(confidence_level=.95, method="wilson")
    return {"successful": len(data), "bias": float(np.mean(estimates) - 2.0),
            "bias_mcse": float(np.std(estimates, ddof=1) / np.sqrt(len(data))) if len(data) > 1 else None,
            "coverage": count / len(data), "coverage_count": count,
            "coverage_wilson_95": [ci.low, ci.high]}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    if args.workers < 1:
        parser.error("workers must be positive")
    started = datetime.now(timezone.utc).isoformat()
    tasks = [(scenario, 320000 + i, 500) for scenario in SCENARIOS for i in range(100)]
    rows = []
    with ProcessPoolExecutor(max_workers=args.workers) as executor:
        for i, row in enumerate(executor.map(run_one, tasks), start=1):
            rows.append(row)
            if i % 25 == 0:
                print(f"Completed {i}/{len(tasks)} replicates", file=sys.stderr, flush=True)
    scenarios = []
    for scenario in SCENARIOS:
        subset = [row for row in rows if row["scenario"] == scenario]
        estimator = summarize(subset, "estimate")
        clipped = [row["estimate"]["clipped_fraction"] for row in subset if "estimate" in row]
        estimator["mean_clipped_fraction"] = float(np.mean(clipped)) if clipped else None
        scenarios.append({"scenario": scenario, "estimator": estimator,
                          "oracle": summarize(subset, "oracle"),
                          "failures": [{"seed": row["seed"], "error": row.get("error", row.get("oracle_error"))}
                                       for row in subset if "error" in row or "oracle_error" in row]})
    packages = ("numpy", "scipy", "pandas", "scikit-learn", "statsmodels")
    result = {"protocol": "causal_evaluation_protocol_v1", "started_utc": started,
              "finished_utc": datetime.now(timezone.utc).isoformat(), "n": 500,
              "replicates_per_scenario": 100, "seed_start": 320000, "workers": args.workers,
              "python": platform.python_version(),
              "versions": {name: importlib.metadata.version(name) for name in packages},
              "fingerprints_sha256": {str(path.relative_to(ROOT)): fingerprint(path) for path in (
                  ROOT / "docs/causal_evaluation_protocol_v1.md", ROOT / "scripts/run_causal_evaluation.py",
                  ROOT / "agent/causal_simulation.py", ROOT / "agent/modeling.py")},
              "scenarios": scenarios, "replicates": rows}
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")


if __name__ == "__main__":
    main()
