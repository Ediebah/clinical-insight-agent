# Evaluation and reproducibility

Tests support software maintenance; they do not establish clinical performance. The project uses authored unit cases, synthetic warehouse checks, selected public-data comparisons, and separate LLM evaluations. Each has a different scope.

```bash
pytest tests packages/caveat/tests packages/assurance/tests
python -m agent.public_benchmark
python -m agent.guardrail_eval
python -m agent.causal_simulation --replicates 25 --n 500 --seed 2026
```

The public benchmark is a small, versioned, key-free contract suite. It tests method registration, unsupported-method status, a missing-denominator warning, and missing Bayesian inputs. It does not measure end-to-end LLM routing accuracy. Submit an independently specified counterexample with expected behavior and a rationale.

The causal simulation measures bias, empirical interval coverage, failures, and clipped propensity fraction under unequal allocation, weak overlap, nonlinear outcomes, and an omitted confounder. A separate reference uses the known data-generating nuisance functions, including the omitted confounder. Coverage and bias themselves have Monte Carlo uncertainty; choose enough replicates for the precision needed and report failures. Simulated results do not validate real-world causal claims.

The [v1 evaluation protocol](causal_evaluation_protocol_v1.md) specified 100 replicates per scenario
before the [run](causal_evaluation_v1.json), after earlier development and a 10-replicate smoke test.
All 400 estimator fits completed; each used 500 observations and a true effect of 2.0. The table gives
empirical coverage of nominal 95% intervals and Wilson intervals for that coverage. Bias uncertainty is
the Monte Carlo standard error. These are exploratory scenario-specific findings, not clinical validation.

| Scenario | Bias (Monte Carlo SE) | Coverage (95% Wilson interval) | Mean propensity clipping |
|---|---:|---:|---:|
| Unequal allocation | -0.036 (0.019) | 98% (93.0%–99.4%) | 1.8% |
| Weak overlap | +0.143 (0.024) | 88% (80.2%–93.0%) | 13.9% |
| Nonlinear outcome | -0.012 (0.022) | 99% (94.6%–99.8%) | 1.8% |
| Omitted confounder | +0.947 (0.021) | 4% (1.6%–9.8%) | 0.8% |

Weak overlap is associated here with substantial clipping and below-nominal coverage. The omitted
confounder produces severe bias despite little clipping: overlap diagnostics cannot detect all
violations of causal assumptions. The known-nuisance reference had 96%, 97%, 96%, and 96% coverage
in these scenarios, respectively; it uses the true generating functions and, in the omitted-confounder
case, information unavailable to the fitted estimator. It is a mathematical reference rather than a
separately implemented external software package. The coverage intervals remain wide at 100 replicates.
The earlier [smoke run](causal_smoke_results.json) remains available separately.

Model comparison fits transformations within training folds and uses an outer loop to assess model selection. Fold standard deviations are not confidence intervals. The same development dataset does not substitute for independent temporal or external evaluation. For survival, Brier score is reported as integrated Brier score, without a reference-based skill claim. Time-dependent metrics may be unavailable in a fold.

The LLM-backed evaluation workflow is scheduled separately because it uses paid calls. Its synthetic runs automatically approve their generated specifications for evaluation only; this is not a human review. Record model identity, prompt version, test-set version, run date, failures and costs when reporting those results.

Use TRIPOD+AI for transparent reporting of prediction studies and PROBAST+AI for risk-of-bias assessment; completing either does not certify this software.
