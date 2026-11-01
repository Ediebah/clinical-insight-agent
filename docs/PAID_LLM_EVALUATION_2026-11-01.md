# Paid LLM evaluation — 2026-11-01

The [one-time workflow run](https://github.com/Ediebah/clinical-insight-agent/actions/runs/41282345128)
used source commit `07ab9df5c65db784e8f2cdd0bfe5bb4d5bd7fb21`, the configured `gpt-4o` model
name, and a separately generated small synthetic warehouse. It predates the demo and readmission
changes in this pull request. The scheduled workflow was disabled again after dispatch.

- Aggregation: 34 of 34 scored cases agreed with the benchmark reference. One of 35 cases was
  skipped because the condition was absent in the generated warehouse. The keyword-based
  caveat-faithfulness check flagged one of five interpretations (4/5 passed).
- Routing: 40 of 40 cases satisfied the benchmark's route, required-key, and SQL checks.
- Bayesian numeric agreement: 4 of 8 cases passed the benchmark's ±0.01 tolerance. The failed
  cases were `bo_assurance_futile`, `bo_assurance_two_arm`, `bo_interim_consider`, and
  `bo_interim_two_arm`; the workflow failed its pre-set threshold. For `bo_interim_consider`, the
  agent reported 0.4172 versus the reference 0.2896. The original log does not capture enough
  extracted input detail to identify the cause of every mismatch.

The Bayesian reference calls the same modeling implementation with the benchmark's selected
inputs; it is a comparison of extraction and execution, not independent numerical validation.
The evaluation automatically approves generated specifications for synthetic cases; it does not
measure human review. These small, selected tests do not establish general accuracy, clinical
validation, or performance on sensitive data. Results can vary by model and run.

A [focused repeat](https://github.com/Ediebah/clinical-insight-agent/actions/runs/41283134318)
on commit `bbebbe5062d4133b99d8d87797f7feea2b1c08e7` scored 3/8 and failed the same threshold.
The added diagnostics showed that two cases were safely stopped because stated decision gates were
not extracted, and two two-arm cases lacked targets after the numeric grounding check. In the
interim mismatch, the extracted `prior_successes=1, prior_n=1` did not match the stated Beta(1,1)
prior, changing the predictive probability from 0.2896 to 0.4172. The benchmark automatically
approved that incorrect specification, so this is not evidence that a human reviewed it. The code
now clears that ambiguous representation and requires correction; updated percentage-point
grounding and prompt guidance need separate evaluation.

A [repeat after the prior safeguard and percentage-point changes](https://github.com/Ediebah/clinical-insight-agent/actions/runs/41283448761)
on commit `06eab022198f1c38cbd114a7920bc73ad9a48c78` scored 6/8 and failed the same threshold.
The previously misread single-arm Beta-prior case agreed with the reference in this run. One
study-design case was routed to a request for clarification, and one two-arm case was stopped
because the control prior was not extracted into the required fields. These refusals did not produce
an incorrect numerical result, but the benchmark did not complete those requested analyses. A
single small repeat is not sufficient to estimate a stable failure rate or prove the safeguard
covers every prior-extraction error.
