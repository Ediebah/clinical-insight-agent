# Clinical Insight Agent 1.1.0-rc.2 — research preview

This source release provides exploratory research software. It is not for patient care, clinical
decisions, trial stopping, regulated submissions, PHI, or confidential data. A reviewer must assess
the specification, data, assumptions, diagnostics, and results. The software has not been
independently clinically validated.

## Changes since v1.1.0-rc.1

- Reports bounded diagnostics when a synthetic proposal fails validation, without retaining
  arbitrary provider text or exception messages.
- For a narrowly recognized two-arm wording, attributes a control Beta prior that a model copied
  into treatment fields. It discloses the correction and the Beta(1,1) base used to update pilot
  counts in the proposed specification. Ambiguous cases still require review. This is not a general
  natural-language understanding guarantee.
- Archives a pre-correction 7/8 and post-correction 8/8 public synthetic development rerun. The
  cases informed the change; these runs are not independent performance estimates. See the
  [challenge protocol](https://github.com/Ediebah/clinical-insight-agent/blob/v1.1.0-rc.2/benchmarks/prospective_v1/PROTOCOL.md).

## Installation

```bash
git clone https://github.com/Ediebah/clinical-insight-agent.git
cd clinical-insight-agent
git checkout v1.1.0-rc.2
```

Follow the [README](https://github.com/Ediebah/clinical-insight-agent/blob/v1.1.0-rc.2/README.md)
for the application and key-free examples. The existing standalone distributions remain
`clinical-insight-caveat==0.1.3` and `clinical-insight-assurance==0.3.1`. This app preview does
not publish new PyPI versions.

## Evidence and limitations

The small, public synthetic challenge was authored by project maintainers and is not independent,
blinded, or a measure of clinical performance. The model alias is mutable. Its checks do not validate
SQL semantics, numerical results, or patient outcomes. Review the report and method assumptions
before drawing conclusions. The post-change 8/8 report tested source commit
`5dbe914687bce77e6be5f7a9e071706d0ad26975`; this release adds documentation and release metadata
after that run.

The container audit has unresolved operating-system advisories. The application depends on
scikit-survival, which declares GPL-3.0-or-later; distribution-specific license review has not been
established. Earlier Git history retains data with incomplete provenance. See the
[image audit](https://github.com/Ediebah/clinical-insight-agent/blob/v1.1.0-rc.2/docs/IMAGE_AUDIT_2026-11-01.md),
[data provenance](https://github.com/Ediebah/clinical-insight-agent/blob/v1.1.0-rc.2/docs/DATA_PROVENANCE.md),
and [standalone release review](https://github.com/Ediebah/clinical-insight-agent/blob/v1.1.0-rc.2/docs/STANDALONE_RELEASE_REVIEW.md).
There is no LTS, clinical-use, regulatory, or production-support guarantee.
