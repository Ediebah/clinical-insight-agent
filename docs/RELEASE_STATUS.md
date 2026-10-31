# Release preparation status

Status checked 2026-10-31. This is a technical inventory, not a legal opinion or a publication authorization. A public repository is available, but no release or package publication is asserted here.

## Package names

- The official [PyPI JSON API for `assurance`](https://pypi.org/pypi/assurance/json) returned an existing project, version 0.1.36, with a different description and publisher (I-Ops Operations Intelligence, LLC). Do not publish this library under that name without confirmed ownership and rights; `pip install assurance` presently refers to that separate project.
- The [PyPI JSON endpoint for `caveat`](https://pypi.org/pypi/caveat/json) returned HTTP 404. This does not establish availability, reservation status, or ownership.
- The [PyPI JSON endpoint for `clinical-insight-assurance`](https://pypi.org/pypi/clinical-insight-assurance/json) returned HTTP 404. The standalone project's distribution metadata now uses this candidate name, but it is not reserved and may not be available when publishing. Its Python import remains `assurance`; other distributions may expose the same import, so avoid co-installing conflicting modules.
- Confirm the maintainer's PyPI account, chosen names, namespace ownership, publishing permissions, and trusted-publishing configuration before uploading anything. HTTP results can change.

## Dependency and data review

The installed application environment's direct dependency metadata identifies `scikit-survival==0.28.0` as GPL-3.0-or-later. Its distribution implications require review for the actual product and artifacts. The two standalone projects do not directly depend on it. Some installed packages have no machine-readable license expression, or describe multiple bundled components, so metadata alone is not a complete license audit. Review transitive packages, binary notices, installation artifacts, data, and any deployed model weights. See [third-party notices](../THIRD_PARTY_NOTICES.md).

The demo database checksum identifies the current file, but its exact Synthea version and generating inputs remain unresolved. CI separately generates data with Synthea 4.0.0; that does not prove the origin of the committed database. See [data provenance](DATA_PROVENANCE.md).

## Build evidence and outstanding checks

PR #55's CI passed the application and warehouse job, plus independent wheel build, install, and package-test jobs for both packages on Python 3.10 and 3.12. A passing run is evidence for those jobs and environments, not for all compatible Python versions, platforms, transitive-license terms, or production use. Maintainers must verify the release commit and rerun the applicable checklist, including release artifact checksums and security review, before publication. Paid LLM evaluations and external clinical validation are not included in this evidence.

After changing the candidate distribution name, the `clinical-insight-assurance` 0.2.0 wheel and source archive were each installed in a separate clean Python 3.12 environment on macOS. Both installations passed the 63 assurance tests. The wheel environment's import resolved to its installed `assurance` module, and `pip check` passed. These local candidate files are not published release artifacts:

- `clinical_insight_assurance-0.2.0-py3-none-any.whl`: SHA-256 `e4d67b121621bfba44647cbc10bca790690c9e6c0578c486137ff5f4d20b4cca`
- `clinical_insight_assurance-0.2.0.tar.gz`: SHA-256 `21701d35de44bd7ce7517d1392de7aca85e85f7fec1615f17e7fa3fcafac7733`
