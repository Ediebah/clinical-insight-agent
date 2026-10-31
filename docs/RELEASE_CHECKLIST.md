# Release preparation

This document is a checklist, not a published release or a support guarantee.

1. Choose and record a version and release commit. Confirm package-index names and account ownership; PyPI's `assurance` is a different existing project. See [release status](RELEASE_STATUS.md).
2. Run the full key-free test, lint, dbt and package build workflows on supported environments; document unavailable checks and known failures.
3. Review dataset redistribution permissions and attribution, dependency and bundled-binary licenses, model-weight terms, security reports, and secrets for the actual distribution. In particular, obtain distribution-specific legal review of the app's GPL-3.0-or-later scikit-survival dependency. Audit transitive dependencies, and pin and review the exact identifier-model revision if distributing it. See [third-party notices](../THIRD_PARTY_NOTICES.md). Verify the synthetic demo database's source, generation manifest, and checksum; the existing checksum alone does not establish its provenance.
4. Build source and wheel distributions for both libraries. Install each artifact in a clean environment, run its examples and tests, and calculate SHA-256 checksums.
5. Update release notes, support policy, version metadata, citation metadata, and compatibility matrix. Mark behavior that changed and migrations needed.
6. Only after maintainer review, create the repository release and publish packages to confirmed destinations. Record artifact hashes and exact published versions.

Supported application target: Python 3.12 with the pinned application requirements. Package metadata permits Python 3.10 or newer, but a wider compatibility matrix has not yet been demonstrated by this release checklist. No LTS or response-time commitment is currently offered.
