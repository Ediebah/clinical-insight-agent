# Contributing

Thanks for taking a look. The project is maintained by one person, and issues and pull requests are
welcome, whether it is a bug, a rough edge, or an idea.

## Getting set up

The [root contributor guide](../CONTRIBUTING.md) contains examples. The README quickstart covers
app-only changes. In short:

```bash
uv venv --python 3.12 && uv pip install -r requirements-dev.txt
```

You need `git`, `uv`, a JDK 17+ (only to regenerate Synthea data), and an OpenAI key for the parts that call
the model. Most of the checks run without a key.

## Before you open a pull request

Run the same checks CI runs:

```bash
.venv/bin/pytest                            # the full unit-test suite, no key needed
ruff check .                                # lint
.venv/bin/python -m agent.guardrail_eval    # deterministic guardrail eval, no key
```

If you touch the warehouse, rebuild and test it:

```bash
cd warehouse && ../.venv/bin/dbt build --profiles-dir . && cd ..
```

CI (`.github/workflows/ci.yml`) also generates Synthea data, rebuilds dbt models, and runs data tests.
A green local unit run does not establish that the full CI workflow passed.

## A few conventions

- Keep the statistics honest. The guardrail is deterministic on purpose: the model may phrase a caveat but
  never invent or drop one. Changes that let the LLM fabricate numbers or skip a caveat will not be merged.
- The SQL engine stays read-only. Do not loosen the hardening in `agent/warehouse.py` without a strong reason
  and tests.
- The demo uses synthetic data; some examples use public datasets. Do not add patient data, PHI, or secrets to the repo, the tests, or
  the fixtures.
- Match the surrounding style, and add or update tests for anything you change.

## Reporting bugs and asking for features

Use the issue templates. For anything security-related, follow `SECURITY.md` instead of opening a public
issue.
