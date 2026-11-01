# Contributing

The most useful thing you can contribute here is **a labelled case**.

This exploratory research toolkit can propose statistical methods for review. The labelled case
collections help detect selected regressions; they do not establish correctness, clinical validity,
or performance on arbitrary questions. A small synthetic case can be contributed and tested
without an API key.

Start with [issue #58](https://github.com/Ediebah/clinical-insight-agent/issues/58) for a
missing-denominator example or [issue #59](https://github.com/Ediebah/clinical-insight-agent/issues/59)
for an in-memory adapter example. Both use synthetic data and need no model or database.

## The four contribution surfaces

| File | What a case looks like | Runs without a key? |
|---|---|---|
| [`agent/eval_dataset.py`](agent/eval_dataset.py) → `GOLD` | a question + reference SQL that computes its true answer | reference SQL: yes |
| `agent/eval_dataset.py` → `ROUTES` | a question + the model type it must reach | gate check: yes |
| `agent/eval_dataset.py` → `BAYES` | a go/no-go question + the parameters it should extract | labels: yes |
| [`agent/guardrail_eval.py`](agent/guardrail_eval.py) → `CASES` | a result table + which caveats should and must not fire | yes |

Every one is a plain Python list. You add an entry; CI tells you whether it holds.

## Worked example: adding a routing case

The router picks one of ~17 model types. A misroute is the agent's most dangerous failure, because
it does not error — it returns a confident, well-rendered model of the *wrong kind*. So the cases
that matter most are the ones that discriminate between **near neighbours**.

```python
Route("sv_adjusted",
      "How does time to readmission differ by sex, adjusting for age?",
      "survival",
      "not logistic — the event timing varies, and a fixed-window model would discard it"),
```

Competing-risk analysis is unsupported and must be refused, not routed to ordinary survival.
The fourth field is the point. Record *what this case must not pick*, not just what it should. Those
pairs are where the router's prompt spends its "prefer X over Y" rules, and therefore what a prompt
edit breaks first. A suite of unambiguous questions proves nothing.

Then:

```bash
pytest tests/test_agent.py -q        # free: your question must pass the _MODEL_HINT gate
```

If that fails, the question never reaches the router at all and the case would be scoring a code
path the app cannot take. That has happened for real — "should we run this study?", the most direct
way to ask for a go/no-go, was silently unreachable until a labelled case caught it.

## Worked example: adding a guardrail case

```python
Case("ceiling_effect",
     pd.DataFrame({"arm": ["A", "B"], "cured": [98, 99], "total": [100, 100]}),
     "Which arm has the higher cure rate?",
     expected={"contrasts", "boundary_rate"},
     forbidden={"small_sample"}),
```

**`expected` must be exhaustive** — every finding the case should produce, not just the one you are
demonstrating. This is the whole meaning of the precision number. While each case carried a single
illustrative label, precision read 58% and every "false positive" was a correct finding; the metric
was measuring how completely the cases had been labelled, not how well the code behaved.

Derive the labels from how you built the case, not from what the code currently emits. If they
disagree, you have found something.

```bash
python -m agent.guardrail_eval      # free, no key: precision / recall / per-case verdict
```

## Setup

```bash
uv venv --python 3.12
uv pip install -r requirements-dev.txt
pytest -q                            # key-free application test suite
ruff check .
```

To run the agent itself you need `OPENAI_API_KEY` in `agent/.env` (copy `agent/.env.example`), and
a warehouse — see [DEPLOY.md](DEPLOY.md). **You do not need either to contribute a labelled case.**

## The two extracted packages

`packages/caveat` (statistical caveats for any result table) and `packages/assurance` (Bayesian
go/no-go) are standalone libraries with no healthcare, warehouse or agent dependency. They have
their own test suites:

```bash
pytest packages/caveat/tests packages/assurance/tests -q
python packages/caveat/validation/validate_public_data.py   # against real published data
```

Contributions there are welcome on their own terms — a new check, a new endpoint, a dataset for the
validation suite. `packages/caveat/validation/README.md` documents both what the library caught and
what it got wrong, and that second section is the more useful one.

## What CI checks

Every push and PR runs the deterministic, free half: ruff, the full pytest suite, both package
suites, a dbt build with data tests, and `guardrail_eval`.

The older LLM-backed workflow contains a configured schedule, but it was disabled when last
checked on 2026-11-01; see [evaluation](docs/EVALUATION.md). The separate prospective challenge is
manual-only and requires explicit authorization for paid calls. Its public cases are not an
independent benchmark. Do not assume a newly added labelled case is fully evaluated by the free
checks: model routing and SQL generation require separate evaluation.

## House rules

- **Comments say why, not what.** The code says what it does.
- **Measure before you trust a change.** Two real defects in this repo were found by taking a
  baseline first and discovering the number was not what the docs claimed.
- **A tool must never silently do nothing.** If a check cannot run, it says so and says what would
  let it. An empty result and a clean result must never look the same.
