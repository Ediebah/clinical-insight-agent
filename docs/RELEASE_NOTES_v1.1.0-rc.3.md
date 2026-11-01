# Clinical Insight Agent 1.1.0-rc.3 — research preview

This source release provides exploratory research software. It is not for patient care, clinical
decisions, trial stopping, regulated submissions, PHI, or confidential data. A reviewer must assess
the specification, data, assumptions, diagnostics, and results. The software has not been
independently clinically validated.

## Changes since v1.1.0-rc.2

- Rate-like results display original values until the user selects fraction or percent. Wilson
  intervals for categorical charts require user-selected numerator and denominator counts that
  agree with the rate. The user must still assess denominator meaning and binomial assumptions.
- Cox optimizer non-convergence and unavailable status are flagged per fit. Report-cache identity
  covers the complete result; an unserializable result bypasses the shared cache.
- Adds a [key-free public-data demonstration](https://github.com/Ediebah/clinical-insight-agent/blob/v1.1.0-rc.3/examples/breast_cancer_research_demo.md)
  and an [independent-evaluation handoff](https://github.com/Ediebah/clinical-insight-agent/blob/v1.1.0-rc.3/benchmarks/independent_review/README.md).
  The demonstration is an exploratory association, not external validation. No independent
  evaluation has yet been conducted under the handoff protocol.
- Corrects the survival example to report integrated Brier score separately and clarifies evidence
  and provenance limitations in other examples and notices.
- Adds a voluntary open-review path and links two key-free starter issues. Open testing does not
  itself establish independent validation.

## Installation

```bash
git clone https://github.com/Ediebah/clinical-insight-agent.git
cd clinical-insight-agent
git checkout v1.1.0-rc.3
```

Follow the [README](https://github.com/Ediebah/clinical-insight-agent/blob/v1.1.0-rc.3/README.md).
The existing standalone distributions remain `clinical-insight-caveat==0.1.3` and
`clinical-insight-assurance==0.3.1`. This application preview does not publish new PyPI versions.

## Evidence and limitations

The public synthetic specification challenge's 7/8 and 8/8 development results used cases that
informed the changes. They are not independent, blinded, SQL or numerical validation, or a clinical
performance estimate. The latest 8/8 report tested commit
`5dbe914687bce77e6be5f7a9e071706d0ad26975`, which predates the changes in this preview; no
post-rc.3 model evaluation has been run. Review the
[challenge protocol](https://github.com/Ediebah/clinical-insight-agent/blob/v1.1.0-rc.3/benchmarks/prospective_v1/PROTOCOL.md)
and case reports for scope and limitations.

The full application includes scikit-survival, which declares GPL-3.0-or-later; legal review of the
exact distribution remains outstanding. OS advisory findings have been recorded for a test image,
and exposure depends on the actual deployment. Earlier Git history retains data with incomplete
provenance. See the [distribution handoff](https://github.com/Ediebah/clinical-insight-agent/blob/v1.1.0-rc.3/docs/DISTRIBUTION_REVIEW.md),
[image audit](https://github.com/Ediebah/clinical-insight-agent/blob/v1.1.0-rc.3/docs/IMAGE_AUDIT_2026-11-01.md),
and [data provenance](https://github.com/Ediebah/clinical-insight-agent/blob/v1.1.0-rc.3/docs/DATA_PROVENANCE.md).
There is no LTS, clinical-use, regulatory, or production-support guarantee.
