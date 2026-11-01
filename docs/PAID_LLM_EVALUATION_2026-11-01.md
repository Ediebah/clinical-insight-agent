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
