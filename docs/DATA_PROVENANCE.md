# Data and dependency provenance

The current demo warehouse was generated from the official Synthea 4.0.0 release using fixed
seeds, reference and end dates, and a recorded Java environment. The [build manifest](demo_dataset_manifest.json)
records the generator checksum, command arguments, input CSV checksums and row counts, project-file
checksums, software versions, 16 exported table counts, and the demo file fingerprint. The export
contains all rows from those models; it does not copy the raw schema or sample observations.
Synthea output is synthetic and is not a substitute for clinical evidence.

The [earlier demo commit](https://github.com/Ediebah/clinical-insight-agent/commit/948c4be4ea6214188954149d93bc83cf07902b9f)
and [refresh](https://github.com/Ediebah/clinical-insight-agent/commit/d20b141) did not establish a
complete generation record for the prior database. That file remains in Git history. The new
manifest describes the replacement, not the provenance of historical versions.

To regenerate, verify the Synthea JAR SHA-256 against the manifest, use the recorded version of
Java and the exact arguments in the manifest, run `python scripts/load_raw.py`, run `dbt build`
from `warehouse/` with `--profiles-dir .`, then run `python scripts/create_demo_database.py
--source data/healthcare.duckdb --output data/healthcare_demo_new.duckdb` from the repository root.
Review the new file, counts, hashes, and app behavior before replacing the committed demo. Keep
raw CSVs out of the repository. The generator uses multiple threads; fixed inputs support a
traceable reconstruction but do not guarantee byte-identical CSV or DuckDB files across runs or
platforms. Hashes identify this build; they do not prove scientific validity.

The three public example datasets below are derived from clinical observations; they are not synthetic. Their UCI records state that they are distributed under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). See [third-party notices](../THIRD_PARTY_NOTICES.md) for attribution and source links. UCI describes replacing names and Social Security numbers with dummy values in the Heart Disease data; that statement is not an independent assessment of re-identification risk for these files.

| Local file | Upstream dataset | Local changes and checks | SHA-256 |
|---|---|---|---|
| `examples/heart_disease_cleveland.csv` | [UCI Heart Disease](https://doi.org/10.24432/C52P4X) | The repository describes dropping six Cleveland records with missing `ca` or `thal`, recoding categories, and deriving a binary outcome from `num > 0`. The file contains 297 rows, and the binary derivation was checked. The original transformation run is not documented by a complete manifest. | `3a7a8ce05a7d7c02de93374006dba9fd358d5f2314009998813306c55f33c3ad` |
| `examples/heart_failure.csv` | [UCI Heart Failure Clinical Records](https://doi.org/10.24432/C5Z89R) | The file contains 299 rows and adds an ejection-fraction group using a 40% threshold. | `af09c6cab341c86524781f43356d38691b6e6a4c72673b081239dc8c168e86fd` |
| `examples/breast_cancer.csv` | [UCI Breast Cancer Wisconsin Diagnostic](https://doi.org/10.24432/C5DW2B) | The file contains 569 rows. Its features match the scikit-learn dataset rounded to five decimal places; the malignant indicator reverses scikit-learn's target coding. | `68fe2bb10940a3f51553a922c1b1ad3024ad84b700dd4ec5495dc06dfd132bb5` |

The key-free examples named `synthetic_*.csv` are constructed examples, separate from these clinical datasets. Hashes identify the checked files; they do not establish consent, scientific validity, or provenance for their source records.

The project MIT license covers project software; dependencies, data, and model weights have separate terms. The full application pins `scikit-survival==0.28.0`, whose package declares GPL-3.0-or-later. The effect on a particular distribution requires review of its contents and legal obligations. Neither standalone library directly declares scikit-survival. The direct and transitive dependencies, bundled binaries, datasets, and model weights still require a distribution-specific license review. The optional identifier model is fetched from a third party at the immutable revision recorded in `agent/deid.py`; its model card declares Apache-2.0. Confirm the revision and terms for any distribution. The pin does not establish the revision used for historical evaluation records or validate de-identification. See [third-party notices](../THIRD_PARTY_NOTICES.md) and the [release checklist](RELEASE_CHECKLIST.md).
