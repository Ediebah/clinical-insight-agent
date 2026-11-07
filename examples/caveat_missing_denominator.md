# Rate-only tables: what `caveat` reports and what it skips

**This is a key-free software example on three constructed rows, not patient data, an analysis
of real clinics, or a validation of the checks.** It shows how the standalone `caveat` library
responds to a table that gives a rate without the counts behind it.

## Data and question

The table has one row per clinic and a percentage, and nothing else:

| clinic | screening_rate_pct |
|---|---|
| North | 62.5 |
| South | 48.0 |
| East | 71.0 |

The question is "Which clinic has the highest screening rate?" The values are invented for the
example and describe no real population.

## Run it

From the repository root:

```bash
python -m pip install ./packages/caveat
python examples/caveat_missing_denominator.py
```

The example uses only the locally installed `caveat` package, pandas and numpy. It calls no model
and needs no API key, database, network access or patient data. The script is
[caveat_missing_denominator.py](caveat_missing_denominator.py).

## Output

<!-- expected-output -->
```text
Roles(rate='screening_rate_pct'[naming], group='clinic'[structural])
! [confounding] This compares `screening_rate_pct` across `clinic` **unadjusted**. Groups likely differ in composition, exposure and selection into each group, which can produce the whole gap. Before any causal reading, standardize or fit a covariate-adjusted model; a crude comparison is descriptive only.
! [missing_denominator] `screening_rate_pct` is a rate shown without the count it was computed over - a rate is a base-rate trap without its N. Add the group size so it can be judged.
- [skipped] small_sample: no denominator column identified (pass denominator='<col>')
- [skipped] contrasts: needs both a numerator and a denominator column (pass numerator='<col>', denominator='<col>')
- [skipped] boundary_rate: needs a numerator and a denominator column
- [skipped] winners_curse: needs a numerator, a denominator and at least 3 groups
- [skipped] simpsons: needs group, stratifier, numerator and denominator (pass stratifier='<col>' to enable)
- [skipped] skew: no continuous measure column identified (pass measure='<col>')
- [skipped] mean_contrasts: needs a group column and a continuous measure (pass group='<col>', measure='<col>')
```

`tests/test_research_examples.py` runs the script and checks that it prints exactly this block, so
the example fails in CI if the library's output changes.

## Reading the output

- **Roles.** `caveat` recognized the percentage as a rate from its column name and the clinic as the
  group, because it is the only text column. It found no numerator (events) or denominator (number
  at risk), because the table has none.
- **`missing_denominator`.** The rate has no N behind it. 62.5% could be 5 of 8 people or 500 of
  800, and those support very different conclusions.
- **`confounding`.** The question compares clinics, so the library notes that the comparison is
  unadjusted and descriptive. It fires on any group comparison of a rate or measure. It does not
  mean the library found a specific confounder.
- **Skipped checks.** `small_sample`, `contrasts`, `boundary_rate` and `winners_curse` need counts.
  `simpsons` also needs a stratifier. `skew` and `mean_contrasts` need a continuous measure, which a
  rate table does not have. A skipped check is not a clean result: it did not run.
- **Checks in neither list.** `missing_data` and `multiple_comparisons` ran and had nothing to
  report: no values are missing, and three groups are below the ten-group threshold for a ranking
  warning. `rate_denominator_consistency` has nothing to compare without counts.

## Why it does not fill in the missing counts

The same three percentages are compatible with opposite readings. Supplying denominators of 8, 25
and 100 makes `small_sample` flag two clinics and leaves no pairwise difference surviving
correction. Supplying 100 times those denominators makes all three differences survive. A rate-only
table cannot tell these apart, so the library reports the gap instead of guessing.

To let the count-based checks run, add the number screened and the number eligible for each row and
name the columns:

```python
caveat.analyze(df, "Which clinic has the highest screening rate?",
               numerator="screened", denominator="eligible", rate="screening_rate_pct")
```

When a rate and counts are both supplied, `rate_denominator_consistency` runs first. If the rate
does not match the counts as a fraction or percentage within 0.5 percentage points, or the values
cannot be compared, `contrasts`, `boundary_rate`, `winners_curse` and `simpsons` are withheld.
`small_sample` still runs on the supplied denominator, so a small-group warning can appear
alongside the mismatch finding.

## What this cannot establish

- **The at-risk population.** `caveat` cannot infer who should be in the denominator. "Eligible"
  might mean everyone registered at a clinic or only people due for screening, and the rate changes
  with that choice. Agreement between a rate and its counts shows that the arithmetic is consistent,
  not that the denominator is the intended population.
- **Causality.** A rate table alone cannot show that a clinic causes a higher or lower rate. The
  difference may reflect who attends each clinic, how eligibility was defined, or how screening was
  recorded. Adjusting for those requires data and a design that this table does not contain.
- **Validity.** A finding is not proof of an error, and the absence of a finding is not proof that
  an analysis is sound. Use only non-sensitive data, and have a qualified reviewer assess the
  specification, data and conclusions. This toolkit is for exploratory research, not patient care,
  clinical decisions or regulated submissions.
