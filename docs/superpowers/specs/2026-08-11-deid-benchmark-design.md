# De-identification benchmark from Synthea ground truth — Design

**One-line:** Measure the OpenMed de-identification model's recall and precision against identifiers Synthea already knows, so the feature's honest status stops being "reduces exposure by an unmeasured amount."

**Status:** design, architecture approved, awaiting spec review.

## 1. Motivation

This repository's headline differentiator is that its numbers are checkable. `README.md` leads with
*"Validated on real public data"*, and `tests/test_validation.py` CI-enforces six method
reproductions against published literature.

The de-identification feature merged in #53 breaks that pattern. It is the one component with no
ground truth behind it: OpenMed publishes no recall figures, so the spec, the UI copy, and the
README all say some version of *reduces exposure by an unmeasured amount*. That is honest, but it is
a hedge where the rest of the project offers a measurement.

The hedge also has a concrete cost. During the build, the model masked an MRN's label but left the
digits exposed in one row, and left `RN` uncovered in another. That was discovered by eyeballing one
test frame. A benchmark turns that anecdote into a per-entity-type number.

## 2. Ground truth is already in the warehouse

Verified against `raw.patients` in `data/healthcare.duckdb`:

```
Id BIRTHDATE DEATHDATE SSN DRIVERS PASSPORT PREFIX FIRST MIDDLE LAST SUFFIX MAIDEN
MARITAL RACE ETHNICITY GENDER BIRTHPLACE ADDRESS CITY STATE COUNTY FIPS ZIP LAT LON
HEALTHCARE_EXPENSES HEALTHCARE_COVERAGE INCOME
```

Synthea generates each patient's identifiers as **known fields**, so a labelled corpus needs no
annotation and no data-use agreement. This is the whole reason the benchmark is feasible: the
standard de-identification corpora (i2b2/n2c2) are access-controlled, and this project does not need
them.

**Prerequisite:** the eval reads `raw.patients`, which exists only in the full local warehouse
(`data/healthcare.duckdb`), not in the committed slim demo (`data/healthcare_demo.duckdb`, which
ships the 16 modelled tables only). Running it requires the full rebuild path documented in the
README. The eval must say so plainly when the table is missing rather than failing obscurely.

## 3. The realism problem, and what to do about it

Synthea deliberately marks its output as fake, and that threatens the measurement's validity:

| Field | Example | Problem |
|---|---|---|
| `FIRST` / `LAST` | `Ashely524`, `Brekke496` | Numeric suffixes — not how names appear in clinical text |
| `ZIP` | `00000` | Placeholder, not a real postcode |
| `SSN` | `999-28-1649` | The `999` prefix is a reserved, never-issued range |
| `ADDRESS` | `873 Mayer Avenue` | Realistic, usable as-is |
| `DRIVERS` / `PASSPORT` | `S99979150`, `X41702617X` | Plausible, usable as-is |

A recall figure measured on `Brekke496` does not transfer to real notes. The digits could push it
either way: an unusual token might be *easier* to flag, or the model might not read it as a name at
all. Reporting that number as though it described clinical text would be exactly the overclaiming
this work exists to prevent.

**Therefore two corpus variants, both scored:**

- **normalised** — trailing digits stripped from names, `00000` ZIP and `999-` SSN replaced with
  format-valid fakes. This is the **headline** number.
- **raw** — exactly what Synthea emits.

The gap between them is not noise to be discarded; it is the measurement of how much Synthea's
markers flatter or penalise the model, and it belongs in the output.

## 4. Architecture

**`agent/deid_eval.py`**, run as `python -m agent.deid_eval`, following `agent/guardrail_eval.py`'s
shape. Appends one JSON record per run to `agent/deid_eval_history.jsonl`, matching
`eval_history.jsonl`, `route_eval_history.jsonl`, and `bayes_eval_history.jsonl`.

**Not in CI, deliberately.** `tests/test_validation.py` is CI-enforced because it runs sklearn and
statsmodels — cheap and offline. This benchmark needs the ONNX model, a **453 MB** Hub download.
CI already runs only the deterministic `guardrail_eval`; `eval.py`, `route_eval.py`, and
`bayes_eval.py` are all on-demand. This joins the second family.

What CI *does* guard is the harness: corpus construction and scoring are unit-tested against a mock
model, so a broken scorer fails fast while the measurement itself stays on demand.

## 5. Column-level measurement

Exercises `deid.scan_columns`, the layer the design's structural guarantee rests on.

Frames are assembled with **known identifier columns** (`first`, `last`, `ssn`, `address`, `zip`,
`mrn`, `birthdate`) and **known-clean columns** (`systolic_bp`, `cured`, `encounter_count`,
`cost_usd`). Reported over columns:

- **recall** — identifier columns flagged / identifier columns present
- **precision** — identifier columns flagged / all columns flagged (a clean column flagged is a
  false positive, which costs the user an unnecessary decision)
- **severity correctness** — that `age` and `sex` land as `quasi` and default to `keep`, since a
  regression there silently destroys the covariates the modelling suite depends on

## 6. Span-level measurement

Exercises `deid.scrub_values` — where the observed failure was.

Known identifier values are embedded into templated note text, then the output is checked for
survival of each inserted string. Ground truth is exact by construction: the harness knows precisely
what it inserted and where.

- **per-entity-type recall** — for each of name, SSN, address, ZIP, MRN, date, phone: the share of
  inserted instances no longer present in the scrubbed output
- **leak examples** — up to a handful of concrete survivals per type, so a poor score comes with
  evidence rather than a bare number

Per-entity-type is the required granularity. An aggregate would have averaged away the MRN failure,
which is the specific thing that motivated this.

## 7. Output

One record per run, appended to `agent/deid_eval_history.jsonl`:

```json
{"model": "OpenMed/OpenMed-PII-SuperClinical-Small-44M-v1-onnx-android",
 "threshold": 0.35, "n_patients": 200,
 "normalised": {"column_recall": 0.0, "column_precision": 0.0,
                "span_recall": {"name": 0.0, "ssn": 0.0, "address": 0.0}},
 "raw": {"column_recall": 0.0, "column_precision": 0.0,
         "span_recall": {"name": 0.0, "ssn": 0.0, "address": 0.0}}}
```

Values above are shape only. Console output follows `guardrail_eval`'s style so the family reads
consistently.

**The measured number then replaces the hedge** in `README.md`, the de-identification spec, and the
About copy. If it is poor, that is the finding and it ships as-is: a bad number honestly reported is
worth more than the present "unmeasured", and it would justify making Drop the only option for
high-severity columns.

## 8. Testing

- `tests/test_deid_eval.py` (new) — corpus construction produces the labelled shape it claims;
  normalisation strips suffixes and replaces the placeholder ZIP and reserved SSN; scoring returns
  1.0 when a mock model detects everything and 0.0 when it detects nothing; per-entity-type recall
  is computed per type rather than aggregated. **`openmed` is mocked throughout — CI must never
  download a model.**
- A missing `raw.patients` produces a clear message naming the rebuild step, not a traceback.

**What these tests do not establish** is the model's quality. They verify the instrument. The
measurement is the artefact in `deid_eval_history.jsonl`.

## 9. Scope

**In:** `agent/deid_eval.py`, `agent/deid_eval_history.jsonl`, `tests/test_deid_eval.py`, a RUNBOOK
entry, and updating the hedged wording once a number exists.

**Out:** running it in CI; i2b2/n2c2 or any access-controlled corpus; retraining or fine-tuning;
changing `SCORE_THRESHOLD` as part of this work — the benchmark exists to inform that decision, and
tuning the threshold against the same corpus used to report the score would be circular.

## 10. Open risks

1. **Synthetic names remain synthetic.** Stripping `496` from `Brekke496` yields a plausible
   surname, but the underlying distribution is still Synthea's. The normalised number is closer to
   clinical text than the raw one, not equal to it, and the output must not be presented as a
   real-world recall figure.
2. **Templated notes are not real notes.** Ground truth requires knowing what was inserted, which
   requires construction. Real clinical text is messier and would likely score worse.
3. **The model has run-to-run variance.** The same MRN column scored 100% locally and 80% on the
   deployed app. The eval should record enough context to make a run reproducible, and a small
   change between runs should not be read as a regression.
