# PyPI publishing workflows

On 2026-10-31, the maintainer authorized and published `clinical-insight-caveat` 0.1.2 and `clinical-insight-assurance` 0.3.0 to PyPI. The former pending publishers were used to create the projects. The old pending publisher for `caveat` had been removed. Before future releases, review the contents, dependency and data terms, checksums, and publication intent.

The manual-only `.github/workflows/publish-caveat.yml` and `.github/workflows/publish-assurance.yml` workflows build their respective libraries from their fixed source commits, compare both generated distributions against reviewed SHA-256 values, and install and test the wheel in a separate environment. A checksum mismatch stops the workflow. Each publishing job targets the `pypi` GitHub environment and obtains an OpenID Connect token for PyPI Trusted Publishing. No API token is stored in the repository.

The workflows published `clinical-insight-caveat` 0.1.3 and `clinical-insight-assurance` 0.3.1 to correct stale PyPI descriptions. Both workflows still pin those published artifacts; a future release requires new reviewed source, version, hashes, and a separate publication decision. The earlier assurance 0.2.0 candidate was superseded after correctness issues were found. The `caveat` and `assurance` Python import names are retained. The separate PyPI project named `assurance` belongs to another publisher.

## GitHub protection

The repository's `pypi` environment was configured with `Ediebah` as a required reviewer and a custom deployment rule for the `main` branch. Administrator bypass was disabled. Self-review is allowed, so this is an owner-approval gate, not independent review. Repository administrators can still change the environment's settings; verify the rules immediately before a release. The `main` branch policy does not itself protect that branch against unauthorized changes.

## PyPI setup and release decisions

The trusted publishers use GitHub owner `Ediebah`, repository `clinical-insight-agent`, and environment `pypi`. The `clinical-insight-assurance` publisher uses `publish-assurance.yml`; the `clinical-insight-caveat` publisher uses `publish-caveat.yml`. These configurations grant their workflows publishing authority. PyPI rejected reuse of one configuration for two pending project names, and the old `caveat` publisher and `publish.yml` workflow were removed. See [PyPI's trusted-publishing documentation](https://docs.pypi.org/trusted-publishers/creating-a-project-through-oidc/).

Before authorizing publishers or publishing, review the distribution's full dependency and data terms, artifact contents, checksums, source commit, applicable security findings, and final release notes. The full app includes a GPL-3.0-or-later dependency; the two standalone packages do not directly declare it. No statement here resolves distribution-specific obligations. See [release status](RELEASE_STATUS.md) and [third-party notices](../THIRD_PARTY_NOTICES.md).

The initial uploads succeeded end to end via [caveat workflow run](https://github.com/Ediebah/clinical-insight-agent/actions/runs/41278590358) and [assurance workflow run](https://github.com/Ediebah/clinical-insight-agent/actions/runs/41278715089). The metadata-only patch uploads succeeded via [caveat workflow run](https://github.com/Ediebah/clinical-insight-agent/actions/runs/41280522923) and [assurance workflow run](https://github.com/Ediebah/clinical-insight-agent/actions/runs/41280619201). This verifies those runs, not future releases or clinical validity. The tools remain exploratory and do not support clinical use or sensitive-data uploads.
