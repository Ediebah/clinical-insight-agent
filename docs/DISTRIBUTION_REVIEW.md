# Distribution and security review handoff

**Status: not a legal opinion, security certification, or clearance to distribute.** The project
owner must arrange review of the exact distribution and intended use. No reviewer has signed off
on the project merely because this checklist exists.

## Inputs for the exact candidate

1. Record the repository commit, release tag, build command, base-image digest, platform, and image
   digest. The CI `container-smoke` job uploads an `image-audit-<commit>` artifact with image and
   base-image metadata, OS and Python inventories, declared license metadata, pip-audit results,
   and Trivy results. CI builds a test image; it does not prove that a later independently built
   image has identical contents. Artifact retention is limited.
2. Review the complete advisories and affected versions, fix availability and vendor status,
   reachable execution paths, deployment controls, and residual risk. A scan records potential
   findings; it does not establish exploitability or safety. Do not treat green CI as zero findings.
3. Identify the exact shipped software, transitive and bundled components, datasets, model weights,
   notices, source obligations, and third-party terms. Metadata inventories are inputs to review,
   not conclusive license analysis. The full application includes scikit-survival, whose package
   declares GPL-3.0-or-later; the consequences depend on the actual distribution and require legal
   review. The two standalone packages have separate dependency trees.
4. Document a responsible owner, findings, decisions, evidence links, dates, recheck triggers, and
   escalation route. The [security policy](../.github/SECURITY.md) describes private reporting.
   Do not include secrets or private deployment details in a public report.

The [2026-11-01 image audit](IMAGE_AUDIT_2026-11-01.md) is a point-in-time record for specific test
images. It reported unresolved OS advisory entries, including high-severity entries; the scan did
not list fixed versions for those entries. Vendor status, exposure, and newer image contents may
change and must be checked again. The [data provenance](DATA_PROVENANCE.md) and
[third-party notices](../THIRD_PARTY_NOTICES.md) document known sources and unresolved history.

## Review record template

- Candidate commit, image digest, platform, and artifact link: `TBD`
- Reviewers, roles, date, and scope: `TBD`
- Scanner versions and database dates; tool failures or exclusions: `TBD`
- Findings, affected components, available fixes, reachability assessment, and mitigation: `TBD`
- License inventory, data/model terms, attribution, and legal reviewer decision: `TBD`
- Residual risk, owner, recheck date, and approval or refusal to distribute: `TBD`
