# Dependency advisory check

On 2026-10-31, `pip-audit` 2.10.1 queried PyPI's advisory service for packages installed in the local Python 3.12 development environment. This environment includes runtime, development, build and potentially unrelated packages; it is not a lockfile or an inventory of every deployment. Advisory results change over time and do not prove exploitability or the absence of other vulnerabilities.

The tool reported 155 advisory entries across 11 installed distributions. Some entries repeat advisory identifiers or represent aliases, so the entry count is not a count of distinct vulnerabilities. The local `caveat` distribution could not be checked against PyPI. The reported installed versions were:

| Distribution | Installed version at audit | Advisory entries |
|---|---:|---:|
| anyio | 4.14.1 | 3 |
| certifi | 2026.6.17 | 2 |
| filelock | 3.32.2 | 12 |
| GitPython | 3.1.50 | 39 |
| msgpack | 1.2.1 | 1 |
| pillow | 12.3.0 | 39 |
| pip | 25.0.1 | 12 |
| pypdf | 6.14.2 | 34 |
| setuptools | 83.0.0 | 1 |
| sqlparse | 0.5.5 | 9 |
| urllib3 | 2.7.0 | 3 |

`pypdf` was the direct runtime pin in `requirements.txt`. The project reads PDF evidence with `PdfReader`; the [upstream advisory for CVE-2026-119203](https://github.com/advisories/GHSA-5849-834g-hvw5) describes a malformed-file infinite-loop condition affecting versions before 6.21.4. The runtime pin was updated to 6.21.4. A separate audit of that candidate version reported no known advisories at the time checked; this is not proof that it is free of vulnerabilities. PDF handling remains bounded by the project's research-only, non-sensitive-data scope.

The other ten distributions remain findings in the audited **local environment**. Some may be transitive, development-only, or not present in a clean deployment. Before release, resolve a fresh environment from the intended artifacts, record exact transitive versions, rerun the advisory scan, review applicable execution paths and fixes, and retain the report. Do not infer that updating `pypdf` fixed those other findings. Do not publish private data or secrets in an audit report.

An initial clean Python 3.12 runtime installation resolved 92 distributions. Its audit reported 51 advisory entries for Pillow 12.3.0 and pip 25.0.1; the local `caveat` and `clinical-insight-assurance` distributions were skipped because they were not found on PyPI. The original Streamlit 1.58.0 pin constrained Pillow to versions below 13. The candidate updates Streamlit to 1.66.1, pins Pillow 13.0.0, and uses pip 26.2.2 in the Docker build and documented setup. With those versions installed in the temporary environment, a follow-up audit reported no advisory entries for the distributions it could query; the two local libraries were still skipped. This is point-in-time evidence for that environment, not a security guarantee or an audit of the application source.

A second clean environment installed the final pinned requirements from scratch and passed `pip check`. The [resolved inventory](runtime_environment_2026-10-31.json) records its 84 installed distributions and a SHA-256 of the requirements file. An advisory query returned no entries for the 82 distributions it could check; it skipped the two unpublished local libraries. The four documented key-free CLI and benchmark commands also completed with API-key environment variables removed. The inventory is not a lockfile, and the same requirements may resolve different transitive versions on another date or platform.

The accompanying [license metadata snapshot](runtime_license_metadata_2026-10-31.json) records what those installed distributions declare. It was generated in that environment with `python scripts/collect_license_inventory.py --output license-metadata.json`. It is a starting point for checking actual license files and bundled components, not a legal review or proof of permission to distribute them.

The Dockerfile copies both local package directories before installing `requirements.txt`. A subsequent CI image build and vulnerability scan identified unresolved OS findings and components bundled in pip; see the [image audit](IMAGE_AUDIT_2026-11-01.md). A second scan after removing pip found no Python library advisories; the OS findings remained. Audit the exact image before use or distribution.

The check was performed without automatic dependency changes:

```bash
pip-audit --path /path/to/environment/lib/python3.12/site-packages \
  --format json --output dependency-audit.json
```
