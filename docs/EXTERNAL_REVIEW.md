# External research review: invitation and checklist

**Status: no reviewers recruited or reviews completed.** This page is a draft for the project
owner to adapt and send. Do not describe an invitation, expressed interest, or code download as
independent validation or adoption.

## Suggested reviewer profiles

Seek at least two researchers who did not develop the toolkit: a biostatistician with trial or
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

Ask reviewers to identify a narrow use case, reproduce the demonstration, inspect input and
denominator assumptions, try supported and unsupported cases, examine limitations, and record
conflicts or failures. No PHI, sensitive uploads, patient-care use, or confidential information is
part of this review. Provide an accessible private channel for security findings as described in
[SECURITY.md](../.github/SECURITY.md).

## Draft invitation — not sent

> We are seeking an independent review of Clinical Insight Agent, an exploratory open-source
> research toolkit. The review would focus on reproducibility, specification review, statistical
> assumptions, and cases in which the toolkit should request clarification or refuse. It does not
> involve patient care or sensitive data. The work, expected time, any compensation, and the
> publication and conflict-of-interest arrangements would be agreed in advance. Would you be
> interested in reviewing the scope?

After any review, publish an agreed, accurate account of the scope, methods, reviewer independence,
limitations, disagreements, and results. Do not claim independent validation until the study was
actually conducted and supports the specific claim.
