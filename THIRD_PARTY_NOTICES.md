# Third-party notices

These notices identify selected upstream materials in the repository and application. They are not an exhaustive inventory of direct or transitive dependencies. Check the applicable terms for the exact versions and materials in any distribution.

## Public datasets

The UCI records for these datasets state that they are licensed under [Creative Commons Attribution 4.0 International](https://creativecommons.org/licenses/by/4.0/). This repository contains modified files; the known modifications are documented in [data provenance](docs/DATA_PROVENANCE.md).

- Janosi, A., Steinbrunn, W., Pfisterer, M., and Detrano, R. (1989). **Heart Disease** [dataset]. UCI Machine Learning Repository. [Dataset and citation](https://archive.ics.uci.edu/dataset/45/heart+disease); [DOI](https://doi.org/10.24432/C52P4X). The local Cleveland example selects and recodes records and derives a binary outcome.
- **Heart Failure Clinical Records** (2020) [dataset]. UCI Machine Learning Repository. [Dataset and citation](https://archive.ics.uci.edu/dataset/519/heart+failure+clinical+records); [DOI](https://doi.org/10.24432/C5Z89R). The local file adds an ejection-fraction group. Associated paper: Chicco, D. and Jurman, G., [BMC Medical Informatics and Decision Making](https://doi.org/10.1186/s12911-020-1023-5).
- Wolberg, W., Mangasarian, O., Street, N., and Street, W. (1993). **Breast Cancer Wisconsin (Diagnostic)** [dataset]. UCI Machine Learning Repository. [Dataset and citation](https://archive.ics.uci.edu/dataset/17/breast+cancer+wisconsin+diagnostic); [DOI](https://doi.org/10.24432/C5DW2B). The local file uses rounded feature values and a recoded outcome.

## Synthetic data and software

The current demo warehouse was generated with Synthea 4.0.0 using the inputs and software recorded in the [build manifest](docs/demo_dataset_manifest.json). This does not establish the incomplete provenance of an earlier demo retained in Git history; see [data provenance](docs/DATA_PROVENANCE.md). Synthea's [download page](https://synthetichealth.github.io/downloads.html) describes its synthetic data and asks users to cite: Walonoski, J., et al. (2018), [Synthea: An approach, method, and software mechanism for generating synthetic patients and the synthetic electronic health care record](https://doi.org/10.1093/jamia/ocx079), *Journal of the American Medical Informatics Association*, 25(3), 230–238. The [Synthea 4.0.0 software license](https://github.com/synthetichealth/synthea/blob/v4.0.0/LICENSE) is Apache-2.0.

The application pins [scikit-survival 0.28.0](https://pypi.org/project/scikit-survival/0.28.0/), whose package metadata declares GPL-3.0-or-later. Review the obligations for the actual distribution before release. The two standalone libraries do not directly declare this dependency.

The optional identifier detector uses the [OpenMed model](https://huggingface.co/OpenMed/OpenMed-PII-SuperClinical-Small-44M-v1-onnx-android), whose model card declares Apache-2.0. First-use downloads request [revision `82f57fcab68125b05f1aa9fdd41319732358311b`](https://huggingface.co/OpenMed/OpenMed-PII-SuperClinical-Small-44M-v1-onnx-android/tree/82f57fcab68125b05f1aa9fdd41319732358311b). Check the exact revision and its terms before redistribution. The detector does not establish de-identification.
