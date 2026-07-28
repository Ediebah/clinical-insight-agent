# Validation against real public data

The package's own tests use frames the author invented. That proves the code does what the author
expected, and nothing about whether the expectations hold outside their head.

This directory runs `caveat` over datasets it was **not built for**, computes the ground truth
independently (from the raw data, or from the published literature), and reports where the two
agree — and, more usefully, where they did not.

```bash
python packages/caveat/validation/validate_public_data.py     # from the repo root
```

Current result: **12/12 checks agree with independent ground truth.**

## Datasets

| Dataset | Source | Why it is here |
|---|---|---|
| UC Berkeley graduate admissions, 1973 | Bickel, Hammel & O'Connell, *Science* **187**:398 (1975) | The canonical *documented* Simpson's paradox. Ground truth is in the paper, not in this repo. |
| Heart Disease (Cleveland, n=297) | [UCI 45](https://archive.ics.uci.edu/dataset/45/heart+disease) | Real clinical subgroups, one genuinely under-powered |
| Heart Failure Clinical Records (n=299) | [UCI 519](https://archive.ics.uci.edu/dataset/519/heart+failure+clinical+records) | A strongly skewed clinical assay, and a known mortality gradient |
| Breast Cancer Wisconsin (n=569) | [UCI 17](https://archive.ics.uci.edu/dataset/17/breast+cancer+wisconsin+diagnostic) | **Adversarial**: 30 continuous features, no counts, no denominator |

## What it got right

Berkeley is the headline. Given the raw 12-row table and **no configuration at all**, `caveat`
inferred every role structurally (`admitted`/`applied` match no naming pattern) and reported:

```
! [contrasts] 1/1 pairwise contrasts survive BH-FDR (pooled across strata).
              Largest: M vs W, risk difference +14.2pp (95% CI [11.3, 17.0], q=0.000).
!! [simpsons] Simpson's paradox risk: marginally `M` > `W`, but within stratum A, B, D
              the ordering reverses. The pooled comparison is confounded by `dept`.
```

The published marginal is 44.5% vs 30.4% — a 14.1pp gap — and the reversal is documented in four of
the six departments. It gives you the number *and* tells you not to trust it, which is the whole
point of the library.

The rest checked out against values computed from the raw data: the only under-powered chest-pain
subgroup (`typical_angina`, n=23), the largest true disease-rate gap (+54.2pp), the known ejection-
fraction mortality gradient (+20.5pp), and the CPK distribution (skewness 4.44, median 250).

## What it got wrong

Three real defects, all found here and all fixed. This section is the reason the directory exists.

**Contrasts cross-multiplied strata.** On Berkeley the original headline was *"women in department A
vs men in department F, +76.5pp"*. Arithmetically true; a comparison nobody asked for. When a
stratifier is present each row is a group-within-stratum cell, so contrasting rows crosses the two.
Now it pools to the group level and lets `simpsons` say whether pooling is safe.

**`multiple_comparisons` counted rows, not groups.** A two-arm comparison of 299 patients produced
*"Comparing or ranking 299 groups inflates false positives"*. The first fix used the group column's
cardinality, which was still wrong for the adversarial case — 200 rows with no grouping column at
all still produced *"ranking 200 groups"*. Without a group column there is no family of comparisons
to correct, so the check now declines and says why. A multiplicity warning nobody can act on is
noise with a statistical accent.

**A stale precision claim.** Not a code defect, but found the same way: the runbook claimed
`guardrail_eval` scored 100% precision. It scores **58%**. That eval gates on misses, false alarms
and severity, never on precision, so the number had drifted with nothing to catch it.

## The adversarial case is the one to watch

Breast Cancer is 30 continuous feature columns with no counts. It is where a structural heuristic is
most likely to embarrass itself by deciding one feature is a denominator for another and then
reporting confident nonsense. It correctly identified **nothing**, ran no proportion contrasts, and
recorded why each check was skipped:

```
roles: Roles(nothing identified)
skipped: contrasts: needs both a numerator and a denominator column (pass numerator=..., denominator=...)
```

An empty report that explains itself is a very different object from an empty report that does not.

## Honest limits

- Four datasets is a start, not coverage. Three are clinical.
- The Berkeley assertions are pinned in `tests/test_real_data.py` and run in CI; the UCI checks
  live in this script because the CSVs sit outside the package.
- Nothing here measures how often role inference misfires on *arbitrary* data. It shows it behaves
  on four real tables and declines on the one designed to trip it. That is evidence, not a bound.
