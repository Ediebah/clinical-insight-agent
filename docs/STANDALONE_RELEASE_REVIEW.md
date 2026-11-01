# Standalone package release review

Status: **standalone releases published on 2026-10-31**. The project is an exploratory research prototype. It is not for patient care, clinical decisions, trial stopping, regulatory submissions, or confidential data. This document records evidence and open decisions; it is not legal advice or a clinical validation.

## Release notes

### clinical-insight-caveat 0.1.2

- Provides deterministic checks for selected statistical concerns in result tables, with no language model required. The Python import remains `caveat`.
- Can miss problems or flag valid analyses. Findings and skipped checks need independent review; they do not establish that an analysis is valid.
- Includes package-level research-use boundaries and omits the incomplete validation directory and the Berkeley fixture from the source archive.

### clinical-insight-assurance 0.3.0

- Provides exploratory Bayesian design and interim calculations without a language model. The Python import remains `assurance`.
- Requires explicit treatment priors and decision thresholds at the high-level entry points; two-arm analyses also require an explicit control prior. Two-arm interim analyses require complete arm counts, and the application requires a named control arm.
- Corrects the two-arm prior-only verdict and reported total enrollment. Refuses unsupported control-prior singularities, visibly underresolved control densities, and two-arm interim outcome grids above the enumeration cap. A grid-mass diagnostic is not a bound on numerical error; results near a decision threshold need independent numerical review.
- This is a breaking change from the unpublished 0.2.0 candidate. Its implicit defaults are no longer accepted by the high-level API. Low-level primitives expose additional defaults and require expert review. The old 0.2.0 candidate has known defects and must not be published.

## Artifact scope and verification

The four artifacts, source commits, hashes, clean-install tests, and Python-version evidence are recorded in [release status](RELEASE_STATUS.md). The package code passed all six checks in [PR #64](https://github.com/Ediebah/clinical-insight-agent/pull/64); the caveat source archive was subsequently revised to exclude the Berkeley fixture. The local key-free suite passed 648 tests with numerical warnings from existing modeling tests. The assurance minimum-dependency run emitted four SciPy warnings. Paid LLM evaluation and independent clinical validation were not performed.

The two wheels contain their respective Python modules, distribution metadata, and the project's MIT license; the wheels do not bundle NumPy, pandas, SciPy, datasets, or model weights. These libraries are resolved separately during installation. The two source archives contain code, tests, package metadata, README and license files. The revised caveat source archive and wheel exclude `tests/test_real_data.py`, which contains a 12-row aggregate Berkeley admissions fixture. The source module retains a short historical reference to Berkeley; it does not contain the fixture table.

Earlier Git history contains the fixture and cites Bickel, Hammel, and O'Connell (1975). The current checkout replaces the two copies of its numeric table with a constructed regression fixture. The [R project dataset documentation](https://stat.ethz.ch/R-manual/R-devel/library/datasets/html/UCBAdmissions.html) independently describes the six-department aggregate and cites the paper. That documentation does not establish the specific source from which this fixture was copied or grant redistribution rights. The fixture's provenance and applicable rights remain open for the public repository and other distributions that include it.

## Resolved runtime and third-party terms

On 2026-10-31, each wheel was installed separately in a fresh macOS arm64 Python 3.12.13 environment; `pip check` passed. The observed runtime resolution was:

| Package | Installed runtime distributions | Installer |
|---|---|---|
| caveat 0.1.2 | NumPy 2.5.4, pandas 3.1.0, python-dateutil 3.0.0, six 1.17.0, tzdata 2026.6 | pip 26.2.2 |
| assurance 0.3.0 | NumPy 2.5.4, SciPy 1.18.1 | pip 26.2.2 |

The [caveat inventory](caveat_runtime_inventory_2026-10-31.json) and [assurance inventory](assurance_runtime_inventory_2026-10-31.json) capture declared metadata and hashes of installed distribution license files for these specific environments. An absent `License-Expression` field is not proof that a dependency has no license. The NumPy metadata lists multiple component licenses, and the installed SciPy and pandas distributions contain additional license notices. See their upstream [NumPy](https://github.com/numpy/numpy/blob/v2.5.4/LICENSE.txt), [SciPy](https://github.com/scipy/scipy/blob/v1.18.1/LICENSE.txt), and [pandas](https://github.com/pandas-dev/pandas/blob/v3.1.0/LICENSE) licenses, and inspect the notices in the exact distributions being shipped. SciPy documents that binary packages may include additional native libraries; actual contents vary by platform and build. See [SciPy's binary-distribution guide](https://docs.scipy.org/doc/scipy/building/redistributable_binaries.html).

The installed macOS NumPy 2.5.4 and SciPy 1.18.1 license files identify bundled OpenBLAS and LAPACK components and GCC runtime libraries licensed as `GPL-3.0-or-later WITH GCC-exception-3.1`. The project wheels do not include those libraries; they were installed separately as dependencies. Retain and review the relevant notices and exception terms when redistributing those dependency binaries. This observation does not resolve the obligations for a particular combined distribution.

These inventories describe one resolution, not a lockfile or an exhaustive audit of every supported platform. The project declares lower bounds, not a fixed set of dependency versions, so future installs can differ. Review the applicable notices and obligations for the actual wheelhouse, container, platform, or product being redistributed. The full app and its GPL-3.0-or-later dependency remain a separate distribution review.

## Advisory check and remaining decisions

`pip-audit` 2.10.1 queried the clean runtime environments on 2026-10-31, before publication. It returned no known advisory entries for the distributions it could query. It skipped the then-unpublished project distributions, so it did not audit this project's code. Reports: [caveat](caveat_dependency_audit_2026-10-31.json) and [assurance](assurance_dependency_audit_2026-10-31.json). This is point-in-time evidence, not proof of security or a finding for other versions.

The maintainer authorized publication, and the two releases were uploaded through their protected trusted-publishing workflows. The public PyPI version endpoints returned hashes matching the reviewed files. Review Berkeley fixture provenance and rights for historical versions or other distributions that include it, and review dependency notices and numerical limitations for the actual use or distribution. Future releases require their own review and versioned artifacts.

The package descriptions embedded in the initial PyPI artifacts were built before publication and contain outdated statements that the names were unconfirmed or unpublished. This repository's package READMEs are corrected; the initial released artifacts have not been replaced. Metadata-only patches 0.1.3 and 0.3.1 are published with the corrected descriptions; the initial artifacts remain unchanged.
