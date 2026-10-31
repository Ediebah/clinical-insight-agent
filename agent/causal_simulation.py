"""Known-effect causal simulations. Reports evidence; does not assert clinical validity."""
from __future__ import annotations

import argparse
import json

import numpy as np
import pandas as pd
from scipy.special import expit

from . import modeling

SCENARIOS = ("unequal", "weak_overlap", "nonlinear", "misspecified")


def generate(seed: int, n: int, scenario: str) -> pd.DataFrame:
    if scenario not in SCENARIOS:
        raise ValueError(f"Unknown scenario: {scenario}")
    rng = np.random.default_rng(seed)
    x, z = rng.normal(size=n), rng.normal(size=n)
    strength = 2.5 if scenario == "weak_overlap" else .7
    u = rng.normal(size=n) if scenario == "misspecified" else np.zeros(n)
    probability = expit(-1.0 + strength * x + .4 * z + 1.2 * u)
    treatment = rng.binomial(1, probability)
    baseline = np.sin(2 * x) + z * z if scenario == "nonlinear" else x + z + u
    outcome = 2.0 * treatment + baseline + rng.normal(size=n)
    return pd.DataFrame({"x": x, "z": z, "oracle_u": u, "treatment": treatment, "outcome": outcome})


def oracle(frame: pd.DataFrame, scenario: str) -> tuple[float, float, float]:
    """Independent AIPW reference using the data-generating nuisance functions."""
    x, z, t, y = (frame[c].to_numpy() for c in ("x", "z", "treatment", "outcome"))
    u = frame["oracle_u"].to_numpy()
    probability = expit(-1.0 + (2.5 if scenario == "weak_overlap" else .7) * x + .4 * z + 1.2 * u)
    mu0 = np.sin(2 * x) + z * z if scenario == "nonlinear" else x + z + u
    score = 2.0 + t * (y - mu0 - 2.0) / probability - (1 - t) * (y - mu0) / (1 - probability)
    estimate = float(np.mean(score))
    se = float(np.std(score, ddof=1) / np.sqrt(len(score)))
    return estimate, estimate - 1.96 * se, estimate + 1.96 * se


def evaluate(replicates=25, n=500, seed=2026, scenarios=SCENARIOS):
    if replicates < 1 or n < 100:
        raise ValueError("Use at least one replicate and 100 observations.")
    report = []
    for scenario in scenarios:
        estimates, covered, clipped, failures = [], [], [], []
        oracle_estimates, oracle_coverage = [], []
        for i in range(replicates):
            frame = generate(seed + i, n, scenario)
            oe, olo, ohi = oracle(frame, scenario)
            oracle_estimates.append(oe)
            oracle_coverage.append(olo <= 2.0 <= ohi)
            result = modeling.fit_uplift(frame, "outcome", "treatment", ["x", "z"])
            if result.error or not result.terms:
                failures.append(result.error or "no estimate")
                continue
            term = result.terms[0]
            estimates.append(term.estimate)
            covered.append(term.ci_low <= 2.0 <= term.ci_high)
            clipped.append(result.robustness["propensity"]["clipped_fraction"])
        report.append({"scenario": scenario, "n": n, "replicates": replicates, "successful": len(estimates),
                       "failures": failures, "true_effect": 2.0,
                       "bias": float(np.mean(estimates) - 2.0) if estimates else None,
                       "coverage": float(np.mean(covered)) if covered else None,
                       "mean_clipped_fraction": float(np.mean(clipped)) if clipped else None,
                       "oracle": {"successful": len(oracle_estimates),
                                  "bias": float(np.mean(oracle_estimates) - 2.0),
                                  "coverage": float(np.mean(oracle_coverage)),
                                  "description": "Independent score using known data-generating functions."},
                       "seed": seed, "limitation": "Monte Carlo estimates have sampling uncertainty; "
                       "this synthetic scenario does not validate clinical use."})
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--replicates", type=int, default=25)
    parser.add_argument("--n", type=int, default=500)
    parser.add_argument("--seed", type=int, default=2026)
    args = parser.parse_args()
    print(json.dumps(evaluate(args.replicates, args.n, args.seed), indent=2))
