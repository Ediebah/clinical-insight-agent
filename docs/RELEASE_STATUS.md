# Release preparation status

Status checked 2026-10-31. This is a technical inventory, not a legal opinion or clinical validation. The two standalone distributions are published on PyPI; the full application remains a research prototype.

For standalone release notes, artifact scope, clean runtime inventories, advisory checks, and historical fixture provenance, see [standalone package release review](STANDALONE_RELEASE_REVIEW.md).

## Package names

- The official [PyPI JSON API for `assurance`](https://pypi.org/pypi/assurance/json) returned an existing project, version 0.1.36, with a different description and publisher (I-Ops Operations Intelligence, LLC). Do not publish this library under that name without confirmed ownership and rights; `pip install assurance` presently refers to that separate project.
- The [PyPI JSON endpoint for `caveat`](https://pypi.org/pypi/caveat/json) returned HTTP 404. This does not establish availability, reservation status, or ownership.
- [clinical-insight-caveat 0.1.2](https://pypi.org/project/clinical-insight-caveat/0.1.2/) and [clinical-insight-assurance 0.3.0](https://pypi.org/project/clinical-insight-assurance/0.3.0/) were published on 2026-10-31. Their Python imports remain `caveat` and `assurance`; avoid co-installing conflicting modules.
- The corresponding PyPI JSON version endpoints listed the four artifact hashes below after publication. Future releases require fresh ownership, permissions, terms, and checksum checks.
- Each published package was installed from PyPI into a separate clean Python 3.12 environment, ran a synthetic example with LLM key and endpoint variables unset, and passed `pip check`.
- [clinical-insight-caveat 0.1.3](https://pypi.org/project/clinical-insight-caveat/0.1.3/) and [clinical-insight-assurance 0.3.1](https://pypi.org/project/clinical-insight-assurance/0.3.1/) are published metadata-only patches that correct stale wording in the package descriptions.

## Dependency and data review

The installed application environment's direct dependency metadata identifies `scikit-survival==0.28.0` as GPL-3.0-or-later. Its distribution implications require review for the actual product and artifacts. The two standalone projects do not directly depend on it. Some installed packages have no machine-readable license expression, or describe multiple bundled components, so metadata alone is not a complete license audit. Review transitive packages, binary notices, installation artifacts, data, and any deployed model weights. See [third-party notices](../THIRD_PARTY_NOTICES.md).

The [runtime license metadata inventory](runtime_license_metadata_2026-10-31.json) records declarations for the same 84-distribution clean environment as the dependency snapshot. Thirty-nine distributions did not provide a `License-Expression` field; some provide classifiers, short license text, or license files instead. Three lengthy license fields were omitted from the snapshot and need source review. Missing metadata does not mean a package has no license. These declarations are not a legal assessment, and the inventory includes the installed environment rather than a verified dependency graph or all bundled components.

A local development-environment advisory check found findings in 11 installed distributions. A separately resolved runtime initially reported findings for Pillow and pip; the candidate updates the relevant pins and a follow-up query found no advisory entries among the distributions it could check. The two then-unpublished libraries were skipped, the older development environment was not changed, and a release-specific image and dependency audit remain open. See [dependency advisory check](DEPENDENCY_AUDIT.md).

The optional identifier model now requests immutable revision `82f57fcab68125b05f1aa9fdd41319732358311b`, which the upstream metadata identified as its main revision on 2026-10-31. New local evaluation records include that revision; historical records did not record one. The pin improves traceability, not evidence of de-identification or compliance. Verify the exact artifact and its terms for the distribution.

The current demo database was rebuilt from the checksum-verified Synthea 4.0.0 release and has a recorded [generation manifest](demo_dataset_manifest.json). The provenance of the earlier demo database remains incomplete in Git history. See [data provenance](DATA_PROVENANCE.md).

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

The published caveat artifacts were built from source commit `73c7876b24e4f853a1d5e90de3e24afc0669c096`, and assurance from `4e2ce9fb3694bdf83476924341337dc89b72f9f5`. Each wheel and source archive was installed in a separate clean Python 3.12 environment on macOS. The caveat wheel passed 85 repository tests; its source archive passed the 78 tests included in that archive, followed by `pip check` in both environments. The excluded seven tests use a Berkeley fixture whose repository-level provenance remains unresolved. Each assurance installation passed 81 tests and `pip check`. Assurance also passed 81 tests on Python 3.10 with NumPy 1.23.5 and SciPy 1.10.1, with four SciPy divide-by-zero warnings during two-arm calculations. These checks do not establish numerical accuracy in all cases, distribution rights, or clinical validation. The PyPI version endpoints reported these hashes:

- `clinical_insight_caveat-0.1.2-py3-none-any.whl`: SHA-256 `58ec40d509d1dab2d8d3610e5a3955ebbc44ce6f6c174c88a0666a5b69150a84`
- `clinical_insight_caveat-0.1.2.tar.gz`: SHA-256 `a226b889052ee2ee1062b10522340a7c6d02bc7ab18ec3d33158fd95fd73aa08`
- `clinical_insight_assurance-0.3.0-py3-none-any.whl`: SHA-256 `e458c1e1b2ab57263f4c0bbb52dc6c602ecbba5f374de50744eec853676b0a2d`
- `clinical_insight_assurance-0.3.0.tar.gz`: SHA-256 `a3acd756625413941a497a9c2704ee659b9ba75288d88f423e3ad499f1edba92`

The published metadata-only patches were built twice from commit `844c58c2e6737ca1cfe9fbc2f51e24576f1d1f5b` with matching hashes. Their package descriptions no longer claim the already-published projects are unverified or unpublished. Each wheel and source archive was installed in a separate Python 3.12 environment and tested against the repository suites: 85 caveat tests and 81 assurance tests per artifact, with `pip check` passing. The 78 tests included in the caveat source archive also passed. Assurance passed 81 tests on Python 3.10 with NumPy 1.23.5 and SciPy 1.10.1, with four SciPy divide-by-zero warnings. Both wheel examples ran without an LLM key. The caveat source archive still excludes the unresolved Berkeley fixture. After publication, each patch was installed from PyPI into a separate clean Python 3.12 environment, passed `pip check`, and ran its synthetic example with LLM key and endpoint variables unset. Assurance was installed using the official PyPI index after the default mirror initially had not listed the new version. The PyPI version endpoints returned the following matching hashes after publication:

- `clinical_insight_caveat-0.1.3-py3-none-any.whl`: SHA-256 `10f3ee4e3e3f8a0153c48b832924a0c97045a73e46adb7ef9a4f56da8ba5179a`
- `clinical_insight_caveat-0.1.3.tar.gz`: SHA-256 `29bbb0a5dfdda0d321dc1b5635538953f14b995212aae0ef2b4f4c0d08d0469a`
- `clinical_insight_assurance-0.3.1-py3-none-any.whl`: SHA-256 `d6e3967060cfd033f1a40d94aff08db34ccca59e2af075c1f739848cc2df0845`
- `clinical_insight_assurance-0.3.1.tar.gz`: SHA-256 `6d86306c8b383670ff1dad934dcf67c78179e1972904bcceca8de0baafa07649`
