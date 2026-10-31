# Release preparation status

Status checked 2026-10-31. This is a technical inventory, not a legal opinion or a publication authorization. A public repository is available, but no release or package publication is asserted here.

## Package names

- The official [PyPI JSON API for `assurance`](https://pypi.org/pypi/assurance/json) returned an existing project, version 0.1.36, with a different description and publisher (I-Ops Operations Intelligence, LLC). Do not publish this library under that name without confirmed ownership and rights; `pip install assurance` presently refers to that separate project.
- The [PyPI JSON endpoint for `caveat`](https://pypi.org/pypi/caveat/json) returned HTTP 404. This does not establish availability, reservation status, or ownership.
- The [PyPI JSON endpoint for `clinical-insight-assurance`](https://pypi.org/pypi/clinical-insight-assurance/json) returned HTTP 404. It is a candidate distribution name, not a reserved name or confirmation that it can be used. A change to the distribution name can retain the `assurance` Python import, subject to packaging and conflict review.
- Confirm the maintainer's PyPI account, chosen names, namespace ownership, publishing permissions, and trusted-publishing configuration before uploading anything. HTTP results can change.

## Dependency and data review

The installed application environment's direct dependency metadata identifies `scikit-survival==0.28.0` as GPL-3.0-or-later. Its distribution implications require review for the actual product and artifacts. The two standalone projects do not directly depend on it. Some installed packages have no machine-readable license expression, or describe multiple bundled components, so metadata alone is not a complete license audit. Review transitive packages, binary notices, installation artifacts, data, and any deployed model weights. See [third-party notices](../THIRD_PARTY_NOTICES.md).

The demo database checksum identifies the current file, but its exact Synthea version and generating inputs remain unresolved. CI separately generates data with Synthea 4.0.0; that does not prove the origin of the committed database. See [data provenance](DATA_PROVENANCE.md).

## Build evidence and outstanding checks

PR #55's CI passed the application and warehouse job, plus independent wheel build, install, and package-test jobs for both packages on Python 3.10 and 3.12. A passing run is evidence for those jobs and environments, not for all compatible Python versions, platforms, transitive-license terms, or production use. Maintainers must verify the release commit and rerun the applicable checklist, including release artifact checksums and security review, before publication. Paid LLM evaluations and external clinical validation are not included in this evidence.
