# Clinical Insight Agent

An open-source **exploratory research toolkit** for reviewing statistical analyses over synthetic or other non-sensitive data. It combines a read-only DuckDB/dbt demo warehouse, a natural-language interface, deterministic statistical routines, and two standalone Python libraries.

**Research prototype:** not for patient care, clinical decisions, regulated submissions, PHI, or confidential data. Human review and independent validation are required. A statistical warning is not proof that an analysis is valid.

**Distribution notice:** the full application pins scikit-survival, which declares GPL-3.0-or-later. Dataset, model, and dependency terms are separate from this project's MIT license; see [third-party notices](THIRD_PARTY_NOTICES.md) and review the actual distribution before release.

## Choose an entry point

| Entry point | Use | Requires an LLM? |
|---|---|---|
| Application | Explore the demo warehouse, review an analysis specification, and inspect results | Natural-language questions do; dashboard and direct calculations do not |
| `caveat` | Check a result table for selected statistical concerns | No |
| `assurance` | Explore Bayesian trial-design and interim calculations | No |
| Research CLI | Run an explicit specification or either library from the command line | No |

## Quickstart

Python 3.12 is the tested application version. A checkout includes a synthetic demo database. For the full app:

```bash
git clone https://github.com/Ediebah/clinical-insight-agent
cd clinical-insight-agent
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
cp agent/.env.example agent/.env  # add OPENAI_API_KEY if using hosted model
.venv/bin/streamlit run app.py
```

The dashboard works without an API key. Natural-language analysis needs a configured model endpoint. A custom endpoint is not necessarily local; verify its host and data policy yourself. The first identifier scan may download a model.

Install either library from this checkout without installing the app:

```bash
python -m pip install ./packages/caveat
python -m pip install ./packages/assurance
```

Package-index publication and name ownership have not been verified for these names. Do not use `pip install caveat` or `pip install assurance` as instructions for this repository until verified.

## Key-free examples

With the full dependencies installed, run:

```bash
python -m agent.cli caveat --csv examples/synthetic_result.csv --question 'Compare rates'
python -m agent.cli assurance --json examples/assurance_design.json
python -m agent.cli analyze --spec examples/association_spec.json --csv examples/synthetic_observations.csv --confirm
python -m agent.public_benchmark
```

The final command reports expected and actual behavior for a small versioned set of synthetic cases. It is a regression check, not an estimate of accuracy on arbitrary questions. For Python use, see the [caveat](packages/caveat/README.md) and [assurance](packages/assurance/README.md) examples.

For inferential questions, the app proposes an editable JSON specification. Review the population, SQL, outcome, predictors, method, assumptions, exclusions, and decision parameters before approval. An approved query is not automatically rewritten. Truncated cohorts are refused rather than silently modeled.
The SQL determines the executed cohort; population and exclusion descriptions are review notes and
are not independently enforced against the query.

The direct DataFrame/CSV mode analyzes all supplied rows and refuses SQL or unapplied exclusions.
For CSV, the path must match the specification. See [data adapters](docs/ADAPTERS.md).

## Privacy and reproducibility

Uploads reach the app server. Column names, sample values, questions, SQL, and selected results may reach the configured model endpoint. Questions, SQL, and feedback can be stored in local logs. Uploaded data is temporarily materialized in DuckDB; cleanup is attempted when the upload is removed or the source changes, but abrupt termination can leave temporary files. See [Privacy and data flow](docs/PRIVACY.md).

Identifier scanning is sampled, may be unavailable, and can fail to detect identifiers. It is **not** de-identification or authorization to upload sensitive information.

A research bundle records the specification, SQL, software versions, source and data fingerprints, diagnostics, result, and separately labeled model-generated interpretation. Raw source rows are not intentionally included. The bundle can still contain sensitive information in user-entered text or result summaries: use only non-sensitive data and inspect it before sharing. Hashes support comparison and integrity checks, not scientific validation, author identity, or proof a design preceded data review.

## Methods and evidence

See [capability map](docs/CAPABILITIES.md), [evaluation](docs/EVALUATION.md), and [dataset provenance](docs/DATA_PROVENANCE.md). Cross-validation and a few public-data examples support regression testing and exploratory assessment; they are not external clinical validation. Competing risks, PHI handling, and clinical deployment are unsupported.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md), the [starter backlog](docs/STARTER_ISSUES.md), [security policy](.github/SECURITY.md), and [code of conduct](.github/CODE_OF_CONDUCT.md). Statistical failure cases, documentation, and independently calculated numerical references are welcome. Please do not include patient data, credentials, or confidential information in an issue.

```bash
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python -m pytest tests packages/caveat/tests packages/assurance/tests
.venv/bin/ruff check .
```

The CI workflow also builds the synthetic dbt warehouse. Paid LLM evaluations are separate. The code is available under the [MIT license](LICENSE); bundled datasets and dependencies have their own terms.
