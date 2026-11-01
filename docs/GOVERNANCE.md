# Governance, safety and trust

Clinical Insight Agent is an exploratory research prototype. It is not for patient care, clinical
decisions, trial stopping, regulated submissions, PHI, or confidential data. Its checks and results
require independent review; they do not establish that an analysis is valid.

## Data and privacy

The demo warehouse is synthetic. The app also accepts uploads, which reach the server; only
synthetic or other non-sensitive input is supported. Column names, sample values, questions, SQL,
and selected results can reach the configured model endpoint. Logs and temporary files can persist.
The identifier scanner is sampled and may miss identifiers; it is not de-identification. See
[privacy and data flow](PRIVACY.md) and [data provenance](DATA_PROVENANCE.md).

## Controls and limits

- Warehouse queries use read-only DuckDB connections, SQL validation, and a result cap. These are
  layers of defense, not proof that every injection or unsafe operation will be prevented.
- Inferential workflows present an editable analysis specification for review. The SQL determines
  the executed cohort; descriptions of populations and exclusions are not independently enforced.
  Truncated cohorts are refused rather than silently modeled.
- Statistical checks are deterministic for fixed inputs and environments but can miss errors or flag
  valid results. Model-generated interpretations and verifier outputs can also be wrong.
- Local audit and feedback logs are not immutable, centrally managed, or a complete security audit.
  Research bundles are traceability artifacts, not proof of independent validation or preregistration.
- CI covers key-free tests, package checks, the synthetic dbt warehouse, and an image scan. A passing
  scan does not mean no vulnerabilities are present. Paid LLM evaluations are reported separately.
  See [evaluation](EVALUATION.md) and the [image audit](IMAGE_AUDIT_2026-11-01.md).

## Maintenance and reporting

The project is maintained as a research prototype without an LTS or production-support commitment.
See [contributing](../CONTRIBUTING.md) for setup and review expectations. Report suspected security or
privacy vulnerabilities privately using the instructions in the [security policy](../.github/SECURITY.md);
do not include sensitive data or secrets in a public issue. Ordinary bugs and feature requests may
be reported through GitHub issues.

Real-world deployment involving sensitive data or clinical decisions requires separate design,
legal and security review, independent validation, and any applicable regulatory work. This
repository does not establish that those requirements have been met.
