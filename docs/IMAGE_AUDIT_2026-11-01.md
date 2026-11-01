# Application image audit — 2026-11-01

This is point-in-time evidence for one **test image**, not a security certification or a review of
all deployments. The image was built from the pull-request merge commit
`0ed06e2ebb5b05cbf62dd1be5a0163a739adc54f` in
[CI run 41282803196](https://github.com/Ediebah/clinical-insight-agent/actions/runs/41282803196).
The Docker image ID was `sha256:d500fa7c88ecc92dee25b8b32f06a110cb361e6bbf313f0209c1365edd2a9f16`;
the inspected base was `python@sha256:aa943ce411423c7582288f18707ff66eddcbaeb510502d747a72aeb34f30d159`.
The image passed the no-key health and Streamlit smoke checks.

The Python package inventory contained 85 distributions. `pip-audit` 2.10.1 reported no advisory
entries for those installed names and versions. It does not assess the application source, binary
contents, or every vendored component. The exact report is
[image_pip_audit_2026-11-01.json](audits/image_pip_audit_2026-11-01.json), SHA-256
`043335d26309067c05e1436836046821722ca0466530f67f3e84f499e9528e3a`.

Trivy reported 166 OS package/advisory entries (72 distinct IDs), including 44 high-severity
entries across eight IDs. No fixed version was listed for those 166 OS entries in this scan. A
missing fix in the report is not an independent determination of vendor status or exploitability.
Trivy also reported eight Python component/advisory entries, including five high-severity entries.
The reported older `msgpack`, `setuptools`, and `urllib3` versions matched versions listed in pip
26.2.2's bundled component inventory, while the separately installed `setuptools` and `urllib3`
versions were newer. That explains why a scan of installed distributions and a scan including
bundled components differ. The [full Trivy report](audits/image_trivy_2026-11-01.json.gz) has
SHA-256 `1e6297a4dd3de9caa0b0c6bd84c2c475697e1d87b7c5e025771df763993dad40`.

A second image, built in [CI run 41283126650](https://github.com/Ediebah/clinical-insight-agent/actions/runs/41283126650)
from merge commit `1071a70fb22a56e5c6d77d3bb5b3f334daa62bc6`, removed pip from the runtime image.
Its image ID was `sha256:7288e8c80af0d6110fae5bffca28f17310d3d93f644d177414aa3ed6050f6f2e`
and it used the same base digest. The installer-removal smoke check passed. Pip-audit returned no
advisories for the 84 installed distributions; Trivy reported no Python library advisories and
again reported 166 OS entries, 44 high across eight IDs, with no fixed version listed. Reports:
[Trivy](audits/image_trivy_without_pip_2026-11-01.json.gz), SHA-256
`0e545f6ca9881967a15a536df280bf02edcd9ceef59b65b4584ce7193e9532de`; and
[pip-audit](audits/image_pip_audit_without_pip_2026-11-01.json), SHA-256
`f67d6ebc09a615491234f22fce31d448f9c433604f81cb70018980a60e3fa9a1`.

The CI scan records findings without failing on severity, so a green CI status does not mean that
the image is free of advisories. Assess the specific execution paths, available vendor updates, and
deployment controls before distribution. The base tag and transitive dependencies can change at
later builds; scan the exact image to be used.
