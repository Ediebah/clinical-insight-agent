# Security policy

This is a research prototype. The demo warehouse uses synthetic data, while the app also accepts uploads.
Non-sensitive uploads only are supported. Model-generated SQL, local logs, temporary files, and external
model calls create security and privacy boundaries; see `docs/PRIVACY.md`.

## Reporting a vulnerability

Please do not open a public issue for a security problem. Email ediebahdivine@gmail.com with:

- a description of the issue and where it is in the code,
- steps to reproduce, and
- the impact you think it has.

I aim to acknowledge a report within a few days.

## Design notes (intentional, not bugs)

- The SQL engine is opened read-only, with external access disabled and no extension autoloading, so DuckDB
  rejects every write and every attempt to reach the filesystem or a URL at the engine. On top of that there
  is a statement denylist, single-statement enforcement, an outer row cap, and an append-only audit log. See
  `agent/warehouse.py`.
- The OpenAI API key is a runtime secret and is never committed. Do not paste real keys into issues or PRs.
- Bring-your-own-data is for non-sensitive data only. Column names and a few example values are sent to the
  LLM, so uploading PHI or secrets is unsupported and out of scope.

## Supported versions

The project tracks `main`. Fixes land there; there are no long-lived release branches.
