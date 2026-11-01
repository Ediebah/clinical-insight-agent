# Independent evaluation handoff

**Status: prepared, not conducted.** No independent reviewers, private cases, adjudication, or
results are represented by this directory. The public `prospective_v1` cases informed development
and cannot be reused as a held-out set.

## Scope

An independent team can assess whether the application proposes the requested supported analysis,
preserves stated numerical inputs, asks for missing decision-relevant information, and refuses
unsupported requests. This is an evaluation of a specified software and model configuration. It is
not validation of SQL, numerical estimators, data privacy, clinical performance, or general use.
Numerical and SQL checks need their own reference calculations and review.

## Roles and separation

1. **Case authors:** external to the project; write synthetic or redistributable cases and keep
   their questions, gold labels, and references private from project maintainers until results lock.
2. **Two adjudicators:** independently review each proposed case and expected result. Record
   disagreements and resolve them before execution. Do not treat agreement alone as validity.
3. **Runner:** freezes the exact application commit, dependency versions, model identifier, prompt,
   tools, and data source. Record whether the model identifier is mutable. The runner must not see
   gold answers before producing and locking outputs; the case custodian may need to operate the
   runner to preserve this separation.
4. **Analyst:** scores locked outputs against locked adjudicated labels, records all exclusions and
   failures, and produces a report that reviewers check before public release. Do not silently edit
   labels or exclude failed runs after seeing outputs.

## Before running

- Complete [protocol-template.md](protocol-template.md), including the primary endpoint, case
  categories and counts, numerical tolerances, refusals, planned number of model calls, model cost
  limit, repetitions, failure handling, data-use permissions, and reporting plan. Missing fields
  mean the study is not ready to run.
- Use only synthetic or explicitly redistributable, non-sensitive cases. Do not upload patient
  data, credentials, or confidential information. Confirm terms for any external data and model.
- Predefine a case as supported, requiring clarification, or unsupported. For proposals, specify
  the required inputs and what is forbidden to invent. For refusals, specify which missing or
  unsupported condition must be identified. Mark unclear cases for adjudication rather than
  forcing an answer.
- Include cases with missing assumptions, wrong denominators, explicit and ambiguous units,
  conflicting priors, competing risks, and claims that require abstention. An independently
  authored set must also contain ordinary supported cases; do not select only known failures.
- Store sealed cases and labels outside the public repository. Record hashes, access controls,
  lock dates, and the identities and roles of reviewers. A hash or a file date alone does not prove
  that cases were sequestered or specified before outputs were observed.

## Execution and reporting

Run only the frozen version and preserve structured outputs, errors, token usage where available,
timestamps, and any deviations. A provider/network failure is not a correct clinical abstention.
Treat a change to code, prompt, model, labels, or scoring after unblinding as a new development
iteration; evaluate the revised version with a new independently authored set.

Report counts and denominators by case category, individual errors, rates of correct proposals and
appropriate refusals, and uncertainty appropriate to the sample size. State how repeated calls and
shared case families were handled. Do not summarize a small convenience set as real-world accuracy.
Publish a sanitized case-level report and all reproducibility information that can be shared without
exposing restricted data, along with limitations and disagreements. If the cases cannot be published,
say so and document how independent reviewers can inspect them.

For a prediction-model study on a separate population or period, define the frozen model and the
independent evaluation cohort separately; the software case challenge is not an external validation
of a prediction model. Use [TRIPOD+AI](https://www.bmj.com/content/385/bmj-2023-078378) for reporting
and [PROBAST+AI](https://www.bmj.com/content/388/bmj-2024-082505) for risk-of-bias assessment where
applicable. Neither checklist certifies this software.
