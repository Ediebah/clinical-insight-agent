# Changelog

Notable changes to the Clinical Insight Agent. Format follows [Keep a Changelog](https://keepachangelog.com/);
versions follow [SemVer](https://semver.org/).

## [1.0.0] — 2026-07-13

First versioned release: the complete pipeline — synthetic data → dbt warehouse → semantic layer →
self-checking agent → biostatistics UI — is built, tested (151 unit tests, 108 dbt data tests, CI on
every push), and deployed.

### Added
- End-to-end agent loop: retrieval over a semantic catalog, planning, read-only SQL with self-healing,
  citations, a deterministic statistical guardrail (Wilson/Newcombe CIs, BH-FDR, confounding and
  Simpson's checks), an LLM critic verify step, and interpretation with honest caveats.
- Ten model families fit in code, not by the LLM: logistic/OLS regression, Cox + Kaplan-Meier,
  random-forest importance, Holt-Winters forecasting, cross-fitted AIPW causal effects, A/B
  ship-decisions, non-inferiority (Farrington-Manning), power/sample-size, and two-variable association —
  each with data-preparation audit trails, assumption diagnostics, and a specification-curve
  robustness check for adjusted models.
- dbt warehouse on DuckDB: 26 models (staging → star schema → analytics marts), 108 data tests,
  docs on every model, reproducible Synthea generation (seed 12345).
- Bring-your-own-data: upload a CSV/Excel and the same agent, guardrail, and models run on it in a
  session-scoped database.
- Word (SAR-style) report export, condition-vocabulary grounding (lay terms → SNOMED descriptions),
  dbt lineage answers, a pre-flight data-quality gate, a monitoring tab, and a keyless local-model
  path via `OPENAI_BASE_URL` (Ollama etc.).
- Security hardening: engine-level read-only SQL (external access disabled), statement validation,
  prompt-injection guard, YAML-escaped generated schema files, per-session upload isolation, and a
  non-root container with a healthcheck.

### Fixed
- 30-day readmission logic: overlapping stays no longer shadow genuine readmissions, and
  died-in-stay index admissions are excluded from the denominator (rate corrected 7.29% → 9.09%);
  the singular dbt test now guards both flag directions plus the denominator.
- Two-level string outcomes are coded deterministically (recognized labels, else alphabetical, always
  disclosed) instead of by row order, which could silently flip A/B verdicts and effect signs.
- Row-capped query results are reported as lower bounds instead of exact totals.
- Excel uploads: the missing engine dependency is included, with decompression-bomb and row-cap
  guards at parse time.
- Local/OpenAI-compatible endpoints that accept-but-ignore JSON mode now work (salvage + prompt
  escalation); LLM traces are per-thread so concurrent sessions don't corrupt each other's cost data.

[1.0.0]: https://github.com/Ediebah/clinical-insight-agent/releases/tag/v1.0.0
