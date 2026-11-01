# Clinical Insight Agent 1.1.0-rc.1 — research preview

This source release contains an exploratory research application, a key-free research CLI, and the
`caveat` and `assurance` libraries. It is not for patient care, clinical decisions, trial stopping,
regulated submissions, PHI, or confidential data. A reviewer must assess the specification, data,
assumptions, diagnostics, and results; the software has not been independently clinically validated.

## Changes since v1.0.0

- Adds reviewable analysis specifications and portable research bundles, plus documented key-free
  interfaces for supported analyses and the standalone libraries.
- Moves learned preprocessing into training folds for model comparison, adds nested evaluation,
  reports integrated Brier score separately, and documents causal and statistical limitations.
- Refuses unsupported competing risks, truncated inferential cohorts, missing Bayesian inputs, and
  explicitly null or non-boolean Bayesian outcome directions.
- Rebuilds the demo from recorded Synthea 4.0.0 inputs and fixes a readmission false negative.
- Adds data adapters, synthetic regression cases, contributor guidance, dependency provenance,
  and container-audit evidence. The prospective specification challenge is a small public test,
  not an independent or blinded validation.

## Installation

To check out this exact application preview, run:

```bash
git clone https://github.com/Ediebah/clinical-insight-agent.git
cd clinical-insight-agent
git checkout v1.1.0-rc.1
```

Follow the [README](https://github.com/Ediebah/clinical-insight-agent/blob/v1.1.0-rc.1/README.md) to install and run the app. You can also install the already
published standalone distributions `clinical-insight-caveat==0.1.3` and
`clinical-insight-assurance==0.3.1`. Their Python imports remain `caveat` and `assurance`. This app
preview does not publish new PyPI versions.

## Evidence and remaining limitations

The key-free suite, dbt checks, package builds, and container smoke test are run in CI. See the
release's exact CI run and [evaluation record](https://github.com/Ediebah/clinical-insight-agent/blob/v1.1.0-rc.1/docs/PAID_LLM_EVALUATION_2026-11-01.md). The latest
focused paid Bayesian development run passed 7/8 cases after prompt changes informed by earlier
cases; one case required clarification. It is not an independent holdout result.

The container audit found unresolved OS advisories, including high-severity entries for which the
scan listed no fixed version. See [image audit](https://github.com/Ediebah/clinical-insight-agent/blob/v1.1.0-rc.1/docs/IMAGE_AUDIT_2026-11-01.md). The application
depends on scikit-survival, which declares GPL-3.0-or-later; review the actual distribution's
third-party licenses, bundled components, data and model terms. Distribution-specific legal review
has not been established. Earlier Git history retains a Berkeley fixture and a previous demo whose
exact provenance remains incomplete. See [data provenance](https://github.com/Ediebah/clinical-insight-agent/blob/v1.1.0-rc.1/docs/DATA_PROVENANCE.md) and the
[standalone release review](https://github.com/Ediebah/clinical-insight-agent/blob/v1.1.0-rc.1/docs/STANDALONE_RELEASE_REVIEW.md).

The project does not offer an LTS, clinical-use, regulatory, or production-support guarantee.
