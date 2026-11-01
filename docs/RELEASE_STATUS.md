# Release preparation status

Status checked 2026-10-31. This is a technical inventory, not a legal opinion or a publication authorization. A public repository is available, but no release or package publication is asserted here.

## Package names

- The official [PyPI JSON API for `assurance`](https://pypi.org/pypi/assurance/json) returned an existing project, version 0.1.36, with a different description and publisher (I-Ops Operations Intelligence, LLC). Do not publish this library under that name without confirmed ownership and rights; `pip install assurance` presently refers to that separate project.
- The [PyPI JSON endpoint for `caveat`](https://pypi.org/pypi/caveat/json) returned HTTP 404. This does not establish availability, reservation status, or ownership.
- The [PyPI JSON endpoint for `clinical-insight-caveat`](https://pypi.org/pypi/clinical-insight-caveat/json) returned HTTP 404 on 2026-10-31. The distribution metadata now uses this name; its Python import remains `caveat`. The response does not reserve the name or establish availability.
- The [PyPI JSON endpoint for `clinical-insight-assurance`](https://pypi.org/pypi/clinical-insight-assurance/json) returned HTTP 404. The standalone project's distribution metadata now uses this candidate name, but it is not reserved and may not be available when publishing. Its Python import remains `assurance`; other distributions may expose the same import, so avoid co-installing conflicting modules.
- Confirm the maintainer's PyPI account, chosen names, namespace ownership, publishing permissions, and trusted-publishing configuration before uploading anything. HTTP results can change.

## Dependency and data review

The installed application environment's direct dependency metadata identifies `scikit-survival==0.28.0` as GPL-3.0-or-later. Its distribution implications require review for the actual product and artifacts. The two standalone projects do not directly depend on it. Some installed packages have no machine-readable license expression, or describe multiple bundled components, so metadata alone is not a complete license audit. Review transitive packages, binary notices, installation artifacts, data, and any deployed model weights. See [third-party notices](../THIRD_PARTY_NOTICES.md).

The [runtime license metadata inventory](runtime_license_metadata_2026-10-31.json) records declarations for the same 84-distribution clean environment as the dependency snapshot. Thirty-nine distributions did not provide a `License-Expression` field; some provide classifiers, short license text, or license files instead. Three lengthy license fields were omitted from the snapshot and need source review. Missing metadata does not mean a package has no license. These declarations are not a legal assessment, and the inventory includes the installed environment rather than a verified dependency graph or all bundled components.

A local development-environment advisory check found findings in 11 installed distributions. A separately resolved runtime initially reported findings for Pillow and pip; the candidate updates the relevant pins and a follow-up query found no advisory entries among the distributions it could check. The two local unpublished libraries were skipped, the older development environment was not changed, and a release-specific image and dependency audit remain open. See [dependency advisory check](DEPENDENCY_AUDIT.md).

The optional identifier model now requests immutable revision `82f57fcab68125b05f1aa9fdd41319732358311b`, which the upstream metadata identified as its main revision on 2026-10-31. New local evaluation records include that revision; historical records did not record one. The pin improves traceability, not evidence of de-identification or compliance. Verify the exact artifact and its terms for the distribution.

The demo database checksum identifies the current file, but its exact Synthea version and generating inputs remain unresolved. CI separately generates data with Synthea 4.0.0; that does not prove the origin of the committed database. See [data provenance](DATA_PROVENANCE.md).

## Build evidence and outstanding checks

PR #55's CI passed the application and warehouse job, plus independent wheel build, install, and package-test jobs for both packages on Python 3.10 and 3.12. A passing run is evidence for those jobs and environments, not for all compatible Python versions, platforms, transitive-license terms, or production use. Maintainers must verify the release commit and rerun the applicable checklist, including release artifact checksums and security review, before publication. Paid LLM evaluations and external clinical validation are not included in this evidence.

The historical `clinical-insight-assurance` 0.2.0 wheel and source archive were each installed in a separate clean Python 3.12 environment on macOS and passed 63 assurance tests. Subsequent review found missing-input and two-arm decision defects; these 0.2.0 artifacts are superseded and must not be published. The hashes below are historical evidence, not current release candidates:

- `clinical_insight_assurance-0.2.0-py3-none-any.whl`: SHA-256 `e4d67b121621bfba44647cbc10bca790690c9e6c0578c486137ff5f4d20b4cca`
- `clinical_insight_assurance-0.2.0.tar.gz`: SHA-256 `21701d35de44bd7ce7517d1392de7aca85e85f7fec1615f17e7fa3fcafac7733`

Before the distribution rename, the historical `caveat` 0.1.2 candidate wheel and source archive were separately installed in clean Python 3.12 environments on macOS. Each passed the 85 standalone tests, and imports resolved to the installed package. These hashes describe the old name and do not identify a `clinical-insight-caveat` release:

- `caveat-0.1.2-py3-none-any.whl`: SHA-256 `1b8772d3f8cc85e8f44c62eea0c6166f3a9b686ff77d37d30d588a19e8795a63`
- `caveat-0.1.2.tar.gz`: SHA-256 `97b02a6ee9b1fe3b18dcefad1350acb78b4731c86ceff65e4f7242f4e548d0fc`

The earlier renamed `clinical-insight-caveat` 0.1.2 distributions were built twice from commit `b78290d26b3f153f042fca2f6741de2a495c6385` with matching hashes. Each was installed in a separate clean Python 3.12 environment on macOS, passed 85 standalone tests and `pip check`. These historical artifacts predate the package-level research-use clarification:

- `clinical_insight_caveat-0.1.2-py3-none-any.whl`: SHA-256 `4ba7af255fd7800400057de2ef3ee466f6f7edf5aae075292a26f34a4dc060c6`
- `clinical_insight_caveat-0.1.2.tar.gz`: SHA-256 `5eee7a4b653524e35c36ba5e18d55c7179a0e73a2934d57bd5e6b2364c4eb167`
