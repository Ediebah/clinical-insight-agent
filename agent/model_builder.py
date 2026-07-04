"""Automated dbt model generation + validation (self-healing).

Turns a natural-language data need into a *validated* dbt model:

    1. SPEC     a plain-English need (e.g. "avg medication cost + order count per patient")
    2. DRAFT    the agent writes a dbt model (SELECT over existing ref()s) + schema tests   [LLM]
    3. WRITE    the .sql model + a schema.yml with not_null/unique/… tests
    4. BUILD    `dbt build --select <model>` — compiles, materializes, AND runs the tests
    5. SELF-HEAL if compile/run/test fails, the agent reads the error and rewrites the SQL,   [LLM]
                then rebuilds — up to N attempts
    6. REPORT   the created model, its tests, row count, and green status

Generated files + the table are removed in a `finally` (pass --keep to keep them). Uses the FULL
warehouse (needs the ref-able upstream models).

Run:  .venv/bin/python -m agent.model_builder ["your data need"] [--keep]   (needs OPENAI_API_KEY)
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import duckdb

from . import llm

ROOT = Path(__file__).resolve().parent.parent
DBT = ROOT / ".venv" / "bin" / "dbt"
WAREHOUSE = ROOT / "warehouse"
DB = ROOT / "data" / "healthcare.duckdb"
MART_DIR = WAREHOUSE / "models" / "marts" / "analytics"
RUN_RESULTS = WAREHOUSE / "target" / "run_results.json"
MAX_TRIES = 3
GEN_PREFIX = "mart_gen_"          # generated models are FORCED under this prefix — never a real mart
DBT_TIMEOUT = 300                 # seconds; bound each dbt invocation so a runaway build can't hang forever

DEFAULT_NEED = ("A per-patient summary of medication spend: one row per patient with the number of "
                "medication orders and their total and average cost. Test that patient_id is unique "
                "and not null and that total cost is never negative.")


class UnsafeModelError(Exception):
    """Raised when a generated model's name or SQL would be unsafe to write/build (fail closed)."""


def _dbt(*args) -> subprocess.CompletedProcess:
    try:
        return subprocess.run([str(DBT), *args, "--profiles-dir", "."],
                              cwd=WAREHOUSE, capture_output=True, text=True, timeout=DBT_TIMEOUT)
    except subprocess.TimeoutExpired:
        # Surface as an ordinary build failure so the caller reports/heals instead of hanging forever.
        return subprocess.CompletedProcess(
            [str(DBT), *args], 124, "",
            f"dbt exceeded the {DBT_TIMEOUT}s timeout and was terminated.")


def _schema_context() -> str:
    """Compact list of ref-able models + columns so the agent writes valid SQL."""
    con = duckdb.connect(str(DB), read_only=True)
    try:
        rows = con.execute(
            "select table_name, column_name from information_schema.columns "
            "where table_schema='main' and table_name not like 'stg_%' order by table_name").fetchall()
    finally:
        con.close()
    tables: dict[str, list[str]] = {}
    for t, c in rows:
        tables.setdefault(t, []).append(c)
    return "\n".join(f"  {t}({', '.join(cols)})" for t, cols in tables.items())


def _slug(name: str) -> str:
    """Slugify an LLM-supplied model name to a SAFE identifier under GEN_PREFIX.

    The prefix is forced UNCONDITIONALLY: any leading mart_/mart_gen_ the model tried to
    supply is stripped first, so a hallucinated name like "mart_readmissions" can never
    resolve onto a real hand-built mart — it becomes "mart_gen_readmissions".
    """
    s = re.sub(r"[^a-z0-9_]", "_", (name or "").lower()).strip("_")
    s = re.sub(r"^(?:mart_gen_|mart_)+", "", s).strip("_")   # drop any prefix the LLM supplied
    return f"{GEN_PREFIX}{s}" if s else f"{GEN_PREFIX}model"


def _is_generated(p: Path) -> bool:
    """True only for our generated artifacts: mart_gen_*.sql / _mart_gen_*.yml (never a real mart)."""
    return p.name.lstrip("_").startswith(GEN_PREFIX)


def _safe_unlink(p: Path, pre_existing: set[str]) -> None:
    """Delete p only if it is a generated artifact this run created — never a real/pre-existing file."""
    if _is_generated(p) and p.name not in pre_existing:
        p.unlink(missing_ok=True)


def _draft(need: str, schema: str, prev_sql: str = "", error: str = "") -> dict:
    fix = ""
    if error:
        fix = (f"\nYour previous model FAILED `dbt build`. Fix it.\nPREVIOUS SQL:\n{prev_sql}\n\n"
               f"ERROR / FAILING TEST:\n{error[:1500]}\n")
    return llm.complete_json(
        "You are an analytics engineer writing a dbt model for a DuckDB warehouse. Reference upstream "
        "models ONLY via {{ ref('model_name') }} (never raw table names). Write standard DuckDB SQL. "
        "Choose tests that actually hold for the data.",
        f"DATA NEED: {need}\n\nRef-able models and their columns:\n{schema}\n{fix}\n"
        'Return JSON: {"model_name":"mart_...", "description":"one line", '
        '"sql":"SELECT ... FROM {{ ref(\'...\') }} ...", "pk":"the primary-key column", '
        '"tests":[{"column":"patient_id","checks":["not_null","unique"]},'
        '{"column":"total_cost","checks":["not_null"],"min_value":0}]}. '
        "Test rules: not_null / unique go in `checks`. For a 'never negative' or range constraint use "
        "min_value / max_value (renders as dbt_utils.accepted_range) — do NOT use accepted_values for "
        "numbers. Use accepted_values only for a small fixed set of categories, via \"values\":[...]. "
        "The SQL must return one row per the pk grain.",
    )


def _count_tests(spec: dict) -> int:
    n = 0
    for c in spec.get("tests", []):
        n += len(c.get("checks", []))
        n += 1 if c.get("values") else 0
        n += 1 if ("min_value" in c or "max_value" in c) else 0
    return n


def _schema_yaml(name: str, spec: dict) -> str:
    """Render a dbt schema.yml (model + column tests) from a draft spec. Pure — unit-tested."""
    col_blocks = []
    for c in spec.get("tests", []):
        lines = [f"      - name: {c['column']}", "        data_tests:"]
        for chk in c.get("checks", []):
            if chk in ("not_null", "unique"):
                lines.append(f"          - {chk}")
        if c.get("values"):
            vals = ", ".join(json.dumps(v) for v in c["values"])
            lines += ["          - accepted_values:", "              arguments:",
                      f"                values: [{vals}]"]
        if "min_value" in c or "max_value" in c:
            lines += ["          - dbt_utils.accepted_range:", "              arguments:"]
            if "min_value" in c:
                lines.append(f"                min_value: {c['min_value']}")
            if "max_value" in c:
                lines.append(f"                max_value: {c['max_value']}")
        col_blocks.append("\n".join(lines))
    return (f"version: 2\n\nmodels:\n  - name: {name}\n"
            f"    description: \"{spec.get('description', 'Generated model.')}\"\n"
            f"    columns:\n" + "\n".join(col_blocks) + "\n")


# ── generated-SQL sandbox ─────────────────────────────────────────────────────────────────────
# The model body is materialized by `dbt build` on a READ-WRITE warehouse connection, so a
# hallucinated/injected pre_hook, post_hook, run_query() or embedded DDL/DML would execute with
# write privileges. We reject anything that isn't a single read-only SELECT/WITH whose ONLY Jinja
# is a bare ref()/source()/var() call — BEFORE it is ever written to disk.
_JINJA_EXPR = re.compile(r"\{\{(.*?)\}\}", re.DOTALL)
_ALLOWED_JINJA = re.compile(
    r"""^\s*(?:ref|source|var)\s*\(\s*
        (?:'[^']*'|"[^"]*")                                   # 1st arg: a quoted string
        (?:\s*,\s*(?:'[^']*'|"[^"]*"|\d+|true|false|null))?   # optional 2nd arg
        \s*\)\s*$""",
    re.IGNORECASE | re.VERBOSE,
)
_FORBIDDEN_SQL = re.compile(
    r"\b(pre_hook|post_hook|run_query|statement|config|insert|update|delete|drop|create|alter|"
    r"truncate|attach|detach|copy|install|load|pragma|export|import|call|grant|revoke|merge|"
    r"vacuum|checkpoint)\b",
    re.IGNORECASE,
)


def _strip_sql_comments(sql: str) -> str:
    sql = re.sub(r"--[^\n]*", " ", sql)                    # line comments
    sql = re.sub(r"/\*.*?\*/", " ", sql, flags=re.DOTALL)  # block comments
    return sql


def _strip_literals(sql: str) -> str:
    """Blank string/identifier literal CONTENTS so keyword/';' scanning ignores them
    (e.g. a value 'DROP ...' or ILIKE '%delete%' must not trip a keyword)."""
    sql = re.sub(r"'(?:[^']|'')*'", "''", sql)
    sql = re.sub(r'"(?:[^"]|"")*"', '""', sql)
    return sql


def _validate_model_sql(sql: str) -> str:
    """Return the SQL unchanged if it is a safe single SELECT/WITH; else raise UnsafeModelError."""
    if not sql or not sql.strip():
        raise UnsafeModelError("generated SQL is empty.")
    cleaned = sql.strip()
    # Only {{ ... }} expressions are allowed — no {% ... %} statements or {# ... #} comments.
    if re.search(r"\{%|\{#", cleaned):
        raise UnsafeModelError("Jinja statement/comment blocks ({% %} / {# #}) are not allowed; "
                               "use only {{ ref()/source()/var() }}.")
    # …and every {{ ... }} must be exactly a bare ref()/source()/var() call (blocks config(),
    # run_query(), env_var(), and smuggling like {{ ref('x') if run_query('drop ...') }}).
    for expr in _JINJA_EXPR.findall(cleaned):
        if not _ALLOWED_JINJA.match(expr):
            raise UnsafeModelError(
                "only ref()/source()/var() Jinja is allowed, got: {{ " + expr.strip() + " }}.")
    # Neutralize the allowed refs, drop comments + literal contents, then scan the residue.
    residue = _JINJA_EXPR.sub(" _ref_ ", cleaned)
    scan = _strip_literals(_strip_sql_comments(residue)).rstrip(";").strip()
    if ";" in scan:
        raise UnsafeModelError("only a single statement is allowed (found ';').")
    if not re.match(r"^\s*(?:select|with)\b", scan, re.IGNORECASE):
        raise UnsafeModelError("the model body must be a single SELECT/WITH query.")
    hit = _FORBIDDEN_SQL.search(scan)
    if hit:
        raise UnsafeModelError(f"forbidden keyword '{hit.group(0).lower()}' in generated SQL.")
    return cleaned


def _write(spec: dict) -> tuple[Path, Path, str]:
    name = _slug(spec.get("model_name", ""))
    sql = _validate_model_sql(spec.get("sql", ""))     # sandbox BEFORE anything touches the warehouse
    sql_path = MART_DIR / f"{name}.sql"
    yml_path = MART_DIR / f"_{name}.yml"
    # Never clobber a pre-existing file: real hand-built marts live in this same directory.
    for p in (sql_path, yml_path):
        if p.exists():
            raise UnsafeModelError(
                f"target {p.name} already exists in {MART_DIR.name}/ — refusing to overwrite it.")
    sql_path.write_text(sql + "\n")
    yml_path.write_text(_schema_yaml(name, spec))
    return sql_path, yml_path, name


def _failure_text(name: str, build: subprocess.CompletedProcess) -> str | None:
    """Return a human-readable failure (compile error or failing test), or None if all green."""
    if RUN_RESULTS.exists():
        data = json.loads(RUN_RESULTS.read_text())
        bad = [r for r in data.get("results", []) if r["status"] in ("fail", "error")]
        if bad:
            b = bad[0]
            return f"{b['unique_id'].split('.')[-1]}: {b['status']} — {b.get('message') or b.get('failures')}"
    if build.returncode != 0:
        tail = (build.stdout or "") + (build.stderr or "")
        return tail[-1500:].strip() or "dbt build failed"
    return None


def build_model(need: str, keep: bool = False) -> int:
    if not DB.exists():
        print(f"✗ Full warehouse not found at {DB}. Build it first (loader + dbt build).")
        return 1

    print(f"▶ AUTOMATED dbt MODEL BUILDER\n  need: {need}\n")
    schema = _schema_context()
    # Snapshot the marts dir up front so cleanup NEVER removes a file we did not create this run.
    pre_existing = {p.name for p in MART_DIR.glob("*")} if MART_DIR.exists() else set()
    written: list[Path] = []
    table_name = ""
    try:
        spec, error, prev_sql = None, "", ""
        for attempt in range(1, MAX_TRIES + 1):
            spec = _draft(need, schema, prev_sql, error)
            for p in written:                        # clear any prior attempt's (generated) files
                _safe_unlink(p, pre_existing)
            sql_path, yml_path, table_name = _write(spec)
            written = [sql_path, yml_path]
            label = "DRAFT" if attempt == 1 else f"SELF-HEAL #{attempt - 1}"
            print(f"{attempt}. {label:11} → {table_name}  (pk: {spec.get('pk')}, "
                  f"tests: {_count_tests(spec)})")

            build = _dbt("build", "--select", table_name)
            error = _failure_text(table_name, build) or ""
            prev_sql = spec["sql"]
            if not error:
                break
            print(f"   ✗ {error.splitlines()[0][:120]}")

        if error:
            print(f"\n✗ Could not produce a passing model after {MAX_TRIES} attempts.")
            return 1

        con = duckdb.connect(str(DB), read_only=True)
        try:
            n = con.execute(f"select count(*) from main.{table_name}").fetchone()[0]
        finally:
            con.close()
        n_tests = _count_tests(spec)
        print(f"\n✅ BUILT + VALIDATED  `{table_name}`  ({n:,} rows, {n_tests} passing tests)")
        print(f"   {spec.get('description', '')}")
        print("\n   SQL:")
        for line in spec["sql"].strip().splitlines():
            print(f"     {line}")
        if keep:
            print(f"\n   kept: {written[0].relative_to(ROOT)} (+ schema yml)")
        return 0
    except UnsafeModelError as e:
        print(f"\n✗ Refusing to build: {e}")
        return 1
    finally:
        if not keep:
            for p in written:
                _safe_unlink(p, pre_existing)
            if table_name.startswith(GEN_PREFIX):    # never drop a table lacking the generated prefix
                con = duckdb.connect(str(DB))
                try:
                    con.execute(f"drop table if exists main.{table_name}")
                finally:
                    con.close()


def main() -> int:
    args = [a for a in sys.argv[1:] if a != "--keep"]
    keep = "--keep" in sys.argv
    need = " ".join(args) if args else DEFAULT_NEED
    return build_model(need, keep=keep)


if __name__ == "__main__":
    raise SystemExit(main())
