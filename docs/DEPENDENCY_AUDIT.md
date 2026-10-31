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

The check was performed without automatic dependency changes:

```bash
pip-audit --path /path/to/environment/lib/python3.12/site-packages \
  --format json --output dependency-audit.json
```
