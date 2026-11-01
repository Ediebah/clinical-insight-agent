# Candidate PyPI publishing workflow

These workflows prepare candidate releases; neither package has been published. The `magic` PyPI account has a pending publisher for the old `caveat` distribution name, not the intended `clinical-insight-caveat` name. A pending publisher does not reserve a package name. Do not upload a package until the maintainer confirms name ownership, distribution-specific license terms, the release contents, and publication intent.

The manual-only `.github/workflows/publish.yml` and `.github/workflows/publish-assurance.yml` workflows build their respective libraries from their fixed source commits, compare both generated distributions against reviewed SHA-256 values, and install and test the wheel in a separate environment. A checksum mismatch stops the workflow. Each publishing job targets the `pypi` GitHub environment and obtains an OpenID Connect token for PyPI Trusted Publishing. No API token is stored in the repository.

The fixed source commits and hashes are specific to the candidates, `clinical-insight-caveat` 0.1.2 and `clinical-insight-assurance` 0.2.0. A future release requires a reviewed change to those values; the workflows are not a generic release system. The `caveat` and `assurance` Python import names are retained. The separate PyPI project named `assurance` belongs to another publisher.

## GitHub protection

The repository's `pypi` environment was configured with `Ediebah` as a required reviewer and a custom deployment rule for the `main` branch. Administrator bypass was disabled. Self-review is allowed, so this is an owner-approval gate, not independent review. Repository administrators can still change the environment's settings; verify the rules immediately before a release. The `main` branch policy does not itself protect that branch against unauthorized changes.

## PyPI setup and release decisions

The old `caveat` pending publisher uses GitHub owner `Ediebah`, repository `clinical-insight-agent`, workflow `publish.yml`, and environment `pypi`. PyPI rejected reuse of that configuration for a different pending project. The proposed `clinical-insight-assurance` publisher uses the same owner, repository, and environment with the distinct workflow `publish-assurance.yml`; the proposed `clinical-insight-caveat` publisher requires replacing the old pending publisher or a different workflow. Registering either grants that workflow publishing authority and requires explicit approval. A pending publisher does not reserve a project name; a 404 is not proof that it is available. See [PyPI's pending-publisher documentation](https://docs.pypi.org/trusted-publishers/creating-a-project-through-oidc/).

Before authorizing publishers or publishing, review the distribution's full dependency and data terms, artifact contents, checksums, source commit, applicable security findings, and final release notes. The full app includes a GPL-3.0-or-later dependency; the two standalone packages do not directly declare it. No statement here resolves distribution-specific obligations. See [release status](RELEASE_STATUS.md) and [third-party notices](../THIRD_PARTY_NOTICES.md).

The workflows are not tested end to end with PyPI. The release is exploratory and does not support clinical use or sensitive-data uploads.
