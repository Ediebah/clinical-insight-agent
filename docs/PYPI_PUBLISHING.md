# Candidate PyPI publishing workflow

This is a proposed workflow for maintainer review, not a published release. It does not configure a PyPI trusted publisher and does not reserve either package name. The `magic` PyPI account has no active or pending trusted publishers at the time of preparation. Do not upload a package until the maintainer confirms name ownership, distribution-specific license terms, the release contents, and publication intent.

The proposed `.github/workflows/publish.yml` is manual-only. It builds one selected library from the fixed source commit `0dff8a848724c08a23ecae6c3a9ad14f08ffc22d`, compares both generated distributions against reviewed SHA-256 values, and installs and tests the wheel in a separate environment. A checksum mismatch stops the workflow. The second job targets the `pypi` GitHub environment and obtains an OpenID Connect token for PyPI Trusted Publishing. No API token is stored in the repository.

The fixed source commit and hashes are specific to the current candidates, `caveat` 0.1.2 and `clinical-insight-assurance` 0.2.0. A future release requires a reviewed change to those values; the workflow is not a generic release system. The `assurance` Python import name is retained. The separate PyPI project named `assurance` belongs to another publisher.

## GitHub protection

The repository's `pypi` environment was configured with `Ediebah` as a required reviewer and a custom deployment rule for the `main` branch. Administrator bypass was disabled. Self-review is allowed, so this is an owner-approval gate, not independent review. Repository administrators can still change the environment's settings; verify the rules immediately before a release. The `main` branch policy does not itself protect that branch against unauthorized changes.

## PyPI setup and release decisions

The prospective pending publishers would each use GitHub owner `Ediebah`, repository `clinical-insight-agent`, workflow `publish.yml`, and environment `pypi`, with one PyPI project name per publisher. Creating either pending publisher grants the specified GitHub workflow authority to publish that project and requires explicit approval. A pending publisher does not reserve a project name; a 404 is not proof that it is available. See [PyPI's pending-publisher documentation](https://docs.pypi.org/trusted-publishers/creating-a-project-through-oidc/).

Before authorizing publishers or publishing, review the distribution's full dependency and data terms, artifact contents, checksums, source commit, applicable security findings, and final release notes. The full app includes a GPL-3.0-or-later dependency; the two standalone packages do not directly declare it. No statement here resolves distribution-specific obligations. See [release status](RELEASE_STATUS.md) and [third-party notices](../THIRD_PARTY_NOTICES.md).

The workflow is not tested end to end with PyPI. Creating the GitHub environment and opening this draft PR do not authorize PyPI registration or publication. The release is exploratory and does not support clinical use or sensitive-data uploads.
