# Starter contribution backlog

Each item is suitable for a scoped issue after the maintainer confirms its scope. Do not include patient data.

1. **Benchmark case:** Add a synthetic result table with a missing denominator. Include independent expected findings, a case ID, and a key-free test.
2. **Numerical oracle:** Add a Bayesian boundary checked against an independent hand calculation or reference implementation. Cite the reference and assumptions.
3. **Documentation:** Add a small, executable no-key example for one `caveat` check, including a case the check cannot assess.
4. **Adapter:** Implement a read-only adapter for a synthetic data source, with isolation, error and truncation tests. Do not claim OMOP compatibility without a separately tested mapping.
5. **Evaluation:** Add a known-effect causal simulation with a prespecified generating process, estimand, failure reporting, and an independent reference.

See [CONTRIBUTING.md](../CONTRIBUTING.md) for setup and the [security policy](../.github/SECURITY.md) for private reporting. Maintainer response is best effort; no response-time or support commitment is implied.
