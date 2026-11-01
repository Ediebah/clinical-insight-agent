# caveat

The distribution is named `clinical-insight-caveat`; its Python import remains `caveat`.

**Statistical caveats for analysis results.** Give it a result table and the question that produced
it; it tells you what would stop a statistician believing the answer.

Everything is deterministic and computed from the data. Nothing here calls a model — an LLM may
*phrase* a caveat, but it must never decide whether one applies, because a model that invents
caveats will also omit them.

```python
import pandas as pd, caveat

df = pd.DataFrame({"arm": ["a", "b"], "cases": [8, 4], "n": [20, 900]})
print(caveat.render(caveat.analyze(df, "which arm has the higher rate?")))
```

```text
!! [small_sample] 1 group(s) have n < 30 in `n` — estimates unstable. e.g. a (n=20).
!  [contrasts] 1/1 pairwise contrasts survive BH-FDR (q<0.05). Largest: a vs b,
   risk difference +39.6pp (95% CI [18.1, 61.4], q=0.000). Report differences with CIs, not raw ranks.
!  [confounding] This compares `cases` across `arm` **unadjusted** ...
```

## Why this exists

Text-to-SQL and analytics agents got good at producing correct queries and stayed bad at knowing
when the answer means nothing. A query over eight rows returns a number, an agent reports it as a
finding, and nothing in the stack says *the top group is also the smallest, and no pairwise
difference survives correction*.

Adjacent tools solve adjacent problems. Data-quality frameworks (Great Expectations, pandera)
validate **inputs** against expectations. Profilers (ydata-profiling) describe **datasets**.
Statistics libraries (statsmodels, pingouin) supply the **tests** but not the decision about which
caveat applies here. `guardrails-ai` validates the **shape and safety of LLM output**, not the
soundness of a conclusion. This library occupies the gap: given a *result*, which caveats apply.

## What it checks

| Check | Fires when |
|---|---|
| `small_sample` | group denominators below a stability threshold |
| `contrasts` | pairwise risk differences, Newcombe CIs, Benjamini-Hochberg across the family |
| `mean_contrasts` | pairwise differences of means, bootstrapped and BH-corrected |
| `boundary_rate` | groups at 0% or 100%, where a point estimate overstates certainty |
| `winners_curse` | the top-ranked group is also one of the smallest |
| `simpsons` | the marginal ordering reverses inside strata |
| `skew` | a mean that misrepresents a skewed distribution, or one shown with no dispersion |
| `confounding` | an outcome compared across groups with no adjustment |
| `missing_denominator` | a rate with no N behind it |
| `rate_denominator_consistency` | a supplied rate disagrees with the supplied counts, or the relationship cannot be checked |
| `multiple_comparisons` | many groups ranked without correction |
| `missing_data` | nulls that silently change every denominator below them |

When nothing survives correction, `contrasts` reports the **minimum detectable effect** — because
"no difference" only means something next to what the data could have detected.

When a supplied rate does not match the counts as a fraction or percentage within 0.5 percentage
points, count-based contrasts and related checks are withheld. The rate may be adjusted, use other
units, or describe a different population; the check does not determine which value is correct.
Likewise, agreement cannot establish that the denominator represents the intended population.
Missing or invalid inputs also withhold those checks. Review column roles and the rate definition.

## Column roles

Roles are resolved in three layers. Explicit always wins, and naming an absent column raises rather
than falling back silently.

```python
caveat.analyze(df, numerator="cases", denominator="n", group="arm")
```

Left to itself it infers, first from column names and then **from the shape of the numbers** — a
count column bounded elementwise by a larger count column is a numerator inside a denominator
whatever the two are called. That structural layer is what keeps the library useful on columns
named `a`, `b`, `cnt`.

```python
report = caveat.analyze(df)
print(report.roles)
# Roles(numerator='a'[structural], denominator='b'[structural], group='grp'[structural])
```

## It tells you what it could not do

A report with no findings is ambiguous: clean data, or a tool that identified nothing? `caveat`
never leaves you guessing.

```python
for s in report.skipped:
    print(s)
# contrasts: needs both a numerator and a denominator column (pass numerator='<col>', denominator='<col>')
```

## Multiplicity across a session

Each `analyze()` corrects within its own family, which is right and is not enough. An agent that
answers twenty questions against one dataset has run twenty families and corrected none against
each other — the garden of forking paths, arrived at by conversation rather than intent.

```python
session = caveat.Session()
for question, df in conversation:
    report = session.analyze(df, question)
```

After enough looking, every report carries a `session_multiplicity` warning. The warning is about
interpretation rather than a corrected q-value: for an exploratory sequence there is no honest
family-wide correction to apply after the fact, only the obligation to say how much looking was done.

## Configuration

```python
caveat.analyze(df, config=caveat.Config(
    min_n=100,                                    # a web funnel is not a clinical trial
    alpha=0.01,
    confounders=("age", "sex", "comorbidity burden"),   # named in the confounding message
))
```

## Install

```bash
python -m pip install ./packages/caveat
```

Run from the repository root. The PyPI name and ownership have not been verified for this project.
Requires numpy and pandas. **No scipy** — the normal CDF comes from `math.erf` and Wilson,
Newcombe, Benjamini-Hochberg and the bootstraps are implemented in-package, so this stays
installable inside someone else's agent without dragging in a research stack.

## License

MIT
