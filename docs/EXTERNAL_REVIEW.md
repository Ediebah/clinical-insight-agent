# External research review: invitation and checklist

**As of 2026-11-01, no independent evaluation has been completed under this protocol.** An open
invitation, an issue report, or a code download is not itself independent validation or adoption.

## Volunteer review

Researchers, statisticians, developers, and other contributors are welcome to test the toolkit and
report problems. You do not need an invitation or an API key to reproduce the key-free examples.

1. Install from the [README](../README.md), then run the [public-data demonstration](../examples/breast_cancer_research_demo.md)
   or a synthetic example. Review the stated assumptions, limitations, and dataset terms.
2. Try a supported or unsupported case using synthetic, non-sensitive inputs. Check units,
   denominators, missing assumptions, and whether the tool requests clarification when needed.
3. Share a reproducible failure or suggestion using the
   [research-case issue template](https://github.com/Ediebah/clinical-insight-agent/issues/new?template=research_case.yml)
   or [bug-report template](https://github.com/Ediebah/clinical-insight-agent/issues/new?template=bug_report.yml).
   Include the version, steps, expected and observed behavior, and a rationale. Do not include
   patient data, credentials, or confidential material. Report security issues privately using the
   [security policy](../.github/SECURITY.md).

Open testing is valuable feedback. It is not automatically a blinded or independently adjudicated
study; maintainers should report its scope and any limitations accurately. Maintainer response is
best effort, with no response-time commitment.

## Suggested reviewer profiles

For a separately designed independent evaluation, the project needs at least two researchers who
did not develop the toolkit: a biostatistician with trial or
observational-analysis experience, and a researcher with applied prediction-model or data-engineering
experience. A third reviewer with security or software-supply-chain expertise can assess distribution
risks. State affiliations, compensation, conflicts, available time, scope, and how disagreements
will be handled before work begins.

## Review material

- The [capability map](CAPABILITIES.md), [evaluation record](EVALUATION.md), and
  [governance](GOVERNANCE.md), including unsupported methods and research-only boundaries.
- The [key-free public-data demonstration](../examples/breast_cancer_research_demo.md), its dataset
  attribution and limitations, specification, and generated research bundle.
- The [independent evaluation handoff](../benchmarks/independent_review/README.md). The independent
  team controls its own sequestered cases, labels, adjudication, and output lock.
- The exact image and license inventory from the relevant CI artifact, plus the prior
  [image-audit record](IMAGE_AUDIT_2026-11-01.md) and [distribution handoff](DISTRIBUTION_REVIEW.md).
  The prior scan is point-in-time evidence,
  not a security certification or a substitute for reviewing the exact distribution.

Independent reviewers can identify a narrow use case, reproduce the demonstration, inspect input and
denominator assumptions, try supported and unsupported cases, examine limitations, and record
conflicts or failures. No PHI, sensitive uploads, patient-care use, or confidential information is
part of this review. Provide an accessible private channel for security findings as described in
[SECURITY.md](../.github/SECURITY.md).

After any review, publish an agreed, accurate account of the scope, methods, reviewer independence,
limitations, disagreements, and results. Do not claim independent validation until the study was
actually conducted and supports the specific claim.
