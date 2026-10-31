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

An initial [smoke run](causal_smoke_results.json) used only 10 replicates per scenario (300 observations,
seed 2026). All 40 fits completed. Estimated bias was -0.028 for unequal allocation, +0.172 for weak
overlap, -0.121 for the nonlinear scenario, and +0.929 with an omitted confounder. Empirical interval
coverage was 100%, 90%, 100%, and 10%, respectively;
each observation changes those percentages by 10 points, so they are too imprecise to establish coverage.
The weak-overlap case clipped an average of 13.6% of propensity estimates. The report includes the
independent known-nuisance reference. Run a larger, prespecified experiment before making performance claims.

Model comparison fits transformations within training folds and uses an outer loop to assess model selection. Fold standard deviations are not confidence intervals. The same development dataset does not substitute for independent temporal or external evaluation. For survival, Brier score is reported as integrated Brier score, without a reference-based skill claim. Time-dependent metrics may be unavailable in a fold.

The LLM-backed evaluation workflow is scheduled separately because it uses paid calls. Its synthetic runs automatically approve their generated specifications for evaluation only; this is not a human review. Record model identity, prompt version, test-set version, run date, failures and costs when reporting those results.

Use TRIPOD+AI for transparent reporting of prediction studies and PROBAST+AI for risk-of-bias assessment; completing either does not certify this software.
