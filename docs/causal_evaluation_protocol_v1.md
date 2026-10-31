# Causal simulation protocol v1

This protocol was written before the run reported in `causal_evaluation_v1.json`. It is an internal analysis specification, not an independently timestamped preregistration. The estimator and data-generating scenarios were already known from earlier development and a 10-replicate smoke run.

## Objective and scope

Characterize the current cross-fitted AIPW estimator on four fixed synthetic data-generating mechanisms. The estimand is the population mean difference under treatment versus control, fixed at 2.0. These cases cannot establish clinical validity, universal causal identification, or external transportability.

## Fixed design

- Use `agent.causal_simulation.generate` scenarios `unequal`, `weak_overlap`, `nonlinear`, and `misspecified`, in that order. Use the independent known-nuisance reference `oracle` supplied in the same module; it has access to the data-generating functions and unobserved confounder and is a mathematical reference, not an external software implementation.
- For each scenario, generate 100 replicates of 500 observations with seeds 320000 through 320099. Reuse seeds across scenarios; summarize each scenario separately, without interpreting scenarios as independent paired comparisons.
- Fit `agent.modeling.fit_uplift` to outcome `outcome`, treatment `treatment`, and observed predictors `x` and `z`. The misspecified scenario deliberately omits the true confounder `oracle_u` from the estimator. Keep the estimator's existing clipping rules and settings unchanged.
- Attempt every planned replicate. Record exceptions, returned errors, non-finite estimates or intervals as failures. Report success counts and the entire failure list, and do not treat failed fits as non-covering fits. Estimates and coverage are conditional on successful fits.
- Report mean bias with Monte Carlo standard error (sample SD of estimates divided by square root of successful fits), empirical 95% interval coverage with Wilson 95% intervals, mean clipped fraction, and the same bias/coverage summaries for the known-nuisance reference. Store per-replicate estimates and interval endpoints, not generated records.
- With 100 successful replicates and true coverage near 95%, the approximate Monte Carlo standard error of coverage is 2.2 percentage points. Failure, extreme weights, and unknown true coverage can increase uncertainty; do not use these results as a pass/fail certification or a precise estimate of nominal coverage.

## Execution and deviations

Run `scripts/run_causal_evaluation.py` with the specified options and preserve the report, including software versions, code and protocol fingerprints, start and finish times, and failures. Any deviation or interrupted run must be recorded; do not change seeds, scenarios, replicate count, or estimator after seeing results without identifying a new protocol version.
