# Changelog

Notable changes to the Clinical Insight Agent. Format follows [Keep a Changelog](https://keepachangelog.com/);
versions follow [SemVer](https://semver.org/).

## [1.1.0-rc.1] — 2026-11-01 — research preview

- Reject an explicitly null or non-boolean Bayesian outcome direction instead of interpreting it as lower-is-better.
- Add a public prospective synthetic specification challenge and a manually authorized paid workflow.
  The challenge is not independently authored, blinded, or clinical validation.
- Add public governance and correct the security-reporting guidance.

- Clear generated prior-study counts that duplicate stated Beta shape parameters when no treatment
  Beta prior was extracted; request a correction. Recognize explicitly stated percentage-point inputs. The paid Bayesian
  evaluation identified this issue and remains separate from deterministic validation.

- Rebuild the synthetic demo warehouse from recorded Synthea 4.0.0 inputs and export all rows of
  its 16 named models. Add a build manifest and a safe export tool. Earlier Git history retains the
  previous demo and Berkeley fixture, whose exact provenance remains incomplete.
- Fix a readmission false negative where a same-day return hid a later qualifying admission.
  Add a regression test for that case.
- Replace the unverified Berkeley numeric table in the current checkout with a constructed
  stratified regression case. The replacement is not external validation.

- Publish `clinical-insight-caveat` 0.1.3 and `clinical-insight-assurance` 0.3.1 as metadata-only
  patches that correct outdated publication statements on their PyPI pages. The package calculations
  are unchanged from 0.1.2 and 0.3.0 respectively.
- Require review of inferential analysis specifications; preserve the approved SQL and refuse
  truncated cohorts, implicit causal subsampling, unsupported competing risks, and missing or invalid
  Bayesian inputs.
- Add key-free command-line entry points, a versioned synthetic benchmark, read-only adapters, and
  research bundles that exclude source history by default.
- Use nested evaluation for model selection and fold-local preprocessing. Report integrated Brier
  score separately and label training-set permutation importance as exploratory.
- Add causal simulations, a capability map, privacy and provenance notes, contributor guidance,
  citation metadata, and package-distribution CI.
- Reject analysis specifications with empty or blank assumptions. Flag rates inconsistent with
  supplied counts and withhold count-based inference until the relationship is clarified.
- Pin the optional identifier model to an immutable upstream revision; historical evaluations
  did not record a revision and are not evidence of de-identification.
- Update the directly pinned PDF parser to 6.21.4 after a dependency-advisory review; other
  dependencies and deployment-specific security controls still require review.
- Update Streamlit and Pillow to allow a patched Pillow release, and copy local libraries before
  installing the runtime requirements in the Dockerfile.
- Keep Streamlit's CORS and XSRF protections enabled in the default container command.
- Require explicit Bayesian priors and decision gates in direct entry points, and explicit control
  priors and control arms for two-arm analyses. Correct the standalone two-arm prior-only verdict.
- Refuse oversized two-arm interim grids and control priors with endpoint singularities rather than
  returning unlabeled or invalid numerical results. Record control priors in design locks.
- Add research-use boundaries to both standalone package descriptions. Update the Bayesian
  extraction-evaluation examples to state their assumptions; earlier results are not comparable.

The section below records earlier changelog claims; it has not been independently audited here.
Standalone versions `clinical-insight-assurance` 0.3.0 (imported as `assurance`, with breaking
changes to required Bayesian inputs) and `clinical-insight-caveat` 0.1.2 (imported as `caveat`)
were published to PyPI on 2026-10-31. The full application remains a research prototype.

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
