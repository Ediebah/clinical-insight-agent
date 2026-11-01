# Reproducible exploratory association: breast-cancer dataset

**This is a software demonstration, not external validation, a clinical prediction study, or a
published-result reproduction.** The specification and analysis were prepared after this familiar
dataset was available. The single predictor was chosen for a compact example, not selected by a
prespecified comparative study. Results cannot establish diagnostic accuracy or clinical utility.

## Data and question

The question is whether `mean_radius` is associated with the recorded binary `malignant` label in
the local `breast_cancer.csv` file. The 569 records and 30 features derive from the
[UCI Breast Cancer Wisconsin (Diagnostic) dataset](https://doi.org/10.24432/C5DW2B), attributed to
Wolberg, Mangasarian, Street and Street (1993), and distributed by UCI under CC BY 4.0. The local
features match the scikit-learn copy rounded to five decimal places; the `malignant` indicator
reverses scikit-learn's target coding. See [data provenance](../docs/DATA_PROVENANCE.md) and
[third-party notices](../THIRD_PARTY_NOTICES.md). The dataset contains observations derived from
clinical specimens; its public status is not an assessment of consent or re-identification risk.

The checked local CSV SHA-256 is
`68fe2bb10940a3f51553a922c1b1ad3024ad84b700dd4ec5495dc06dfd132bb5`. It has 569 rows:
212 malignant and 357 benign labels. The outcome and chosen predictor have no missing values in
this file. No rows were excluded for this run. This does not establish independence of samples,
representativeness, or provenance of all source records.

## Specification and execution

Review [breast_cancer_logistic_spec.json](breast_cancer_logistic_spec.json): all rows, one
predictor, binary outcome, exploratory logistic regression, and the assumptions stated there.
`--confirm` records the operator's explicit approval; it does not prove prior registration.
Run from the repository root in an installed environment:

```bash
python -m agent.cli analyze \
  --spec examples/breast_cancer_logistic_spec.json \
  --csv examples/breast_cancer.csv --confirm > breast-cancer-bundle.json
python -c 'import json; from agent.research import verify_bundle; b=json.load(open("breast-cancer-bundle.json")); print("bundle integrity:", verify_bundle(b))'
```

No LLM or API key is needed. The bundle contains the approved specification, code and data
fingerprints, software versions, results, and diagnostics; it does not contain the original rows.
The script fits one specified logistic model: there is no model-selection contest, train/test split,
calibration study, or external validation. Review data and code fingerprints and software versions
before comparing reruns; hashes support integrity, not scientific validity or proof of timing.

## Observed result and review

On 2026-11-01, with numpy 2.5.0, pandas 3.0.3, scipy 1.18.0 and statsmodels 0.14.6, the model used
569 records and reported an odds ratio of **2.811** per one dataset unit of `mean_radius`, with a
model-based 95% confidence interval of **2.342–3.374**. The fitted model reported pseudo-R² 0.561.
These figures are rounded; the generated bundle records the full numerical values. Different
versions or implementation changes may change the result.

The model's `issues` list was empty in this run. That is not a finding that assumptions hold: the
checks cannot establish independence, absence of confounding or selection bias, adequate functional
form, correct labels, or external performance. The result is an unadjusted association, not a causal
effect; a model-based interval depends on the model and data assumptions. The standalone `caveat`
result-table checker was not run here, and no LLM narrative was generated. The script uses the same
statistical backend as the application, so this is not an independent numerical implementation.

There is no evidence here that a model works in a different site, population, or time period; no
calibration or clinical utility estimate is supplied. Do not use this demonstration for patient care,
diagnosis, screening, triage, or treatment decisions. An independent prediction-model evaluation
would need a frozen model and a separately defined evaluation cohort and should be reported with
[TRIPOD+AI](https://www.bmj.com/content/385/bmj-2023-078378) and assessed using
[PROBAST+AI](https://www.bmj.com/content/388/bmj-2024-082505) where applicable.
