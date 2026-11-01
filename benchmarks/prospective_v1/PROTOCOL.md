# Prospective synthetic specification challenge, version 1.0.0

## Purpose and independence

This is a small, public challenge of proposed analysis specifications and explicit refusals. Its
cases were written after the earlier development evaluations and were not used to tune the current
routing prompt. The case file is frozen before the first run; its SHA-256 is
`6c4daf00a80a823782ef6deff251704fe7452a276d25aa037950609a25841448`. The runner refuses a different
file under this version. The source commit, prompt and specification source hashes, model alias,
demo database hash, and run timestamp are recorded in each result.

**This is not an independent, blinded, or externally adjudicated benchmark.** The project authors
wrote the cases and labels after seeing earlier results. The cases are public, and the model's
training history is unknown. The version fingerprint does not prove preregistration or lack of
prior exposure. An independent research team should author and adjudicate a new, sequestered set
before using it for an independent performance claim.

## Cases and scoring

Eight cases are constructed, not patient records: four ask for Bayesian specifications with
explicit inputs; three lack a required prior or thresholds or contain an invalid prior; one asks
for unsupported competing-risk analysis. Expected parameters are stated directly in the case
file. Review them and their statistical assumptions before interpreting results.

The runner calls the same model router and specification builder through a proposal-only harness.
It does not call the full application path, approve a specification, or execute generated analysis
SQL. It can use read-only catalog and vocabulary lookups for context; application preflight and the
aggregate path are outside this benchmark. For valid proposals it checks the method, selected numerical fields, prior family,
framing, direction, and whether a query is present where expected. For missing or invalid inputs,
it checks for a specific refusal or a proposed specification that fails the required-input
validator. For competing risks, it requires an explicit refusal. A generic network or provider
error is a failure, not an abstention. Results record expected and observed selected fields for
proposals and a reason for each failure.

The score is a count of cases, not an estimate of real-world accuracy. It does not validate the
meaning of generated SQL, the dataset's denominator, the model's computation, the content of
assumptions, or human review. A valid case that requests clarification fails the completion score,
even when clarification is safer than guessing. Cases are neither representative nor sufficient
for clinical claims. No statistical accuracy threshold was selected for this small set; the runner
exits nonzero if any case does not meet its stated expectation so that failures remain visible.

## Execution and reuse

Run only with synthetic or non-sensitive data. A hosted model call costs money. The manual
`prospective-evaluation` workflow requires the exact confirmation phrase and has no schedule.
It uses the committed synthetic demo and the `gpt-4o` model alias; the alias is mutable and does not
identify a model snapshot. It records available token counts, not a billing total. Reports contain
only synthetic case IDs, selected specification fields, and run metadata. Workflow artifacts
expire after 90 days; archive an appropriately reviewed report if it is needed for a release.

For an invalid proposal, newer reports also record the validation stage, a coarse issue category,
and bounded numeric, boolean, and known framing fields. They do not record arbitrary provider text
or exception messages. These diagnostics are not available in reports generated before this change.
They cannot reconstruct a previous model response. The original v1 baseline was 7/8; its two-arm
proposal failed validation for a reason that was not retained. A key-free replay of the expected
fields passes, but it does not reveal what the model actually returned. This diagnostic change was
motivated by that result; any subsequent use of this case set is development evaluation, not a new
independent or held-out assessment.

Freeze the source commit and cases before the baseline run. Do not tune the routing prompt or
labels against these cases and then describe a repeated score as held out. If results guide a
change, this set becomes development data for that change; prepare and freeze a new set before
making a prospective claim. Independent reviewers should separately assess the labels, cases, and
SQL/numerical behavior; this protocol does not claim that review has occurred.
