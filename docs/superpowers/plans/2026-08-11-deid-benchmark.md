# De-identification Benchmark Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Measure the OpenMed de-identification model's recall and precision against identifiers Synthea already knows, so the feature's status stops being "reduces exposure by an unmeasured amount."

**Architecture:** A new `agent/deid_eval.py`, run as `python -m agent.deid_eval`, follows `agent/guardrail_eval.py`'s shape and appends one record per run to `agent/deid_eval_history.jsonl`. It builds a labelled corpus from `raw.patients`, in a normalised and a raw variant, and scores two layers: column classification via `deid.scan_columns` and span masking via `deid.scrub_values`. Not run in CI — CI unit-tests the harness against a mock model.

**Tech Stack:** Python 3.12, DuckDB, pandas, `agent.deid` (OpenMed ONNX), pytest.

**Spec:** `docs/superpowers/specs/2026-08-11-deid-benchmark-design.md`

## Global Constraints

- **CI must never download a model.** Every test mocks `agent.deid`. The benchmark itself is on-demand only and must not be added to `.github/workflows/ci.yml`.
- **The normalised figure is not a real-world recall number.** Any wording produced by this work must not present it as one — the distribution underneath is still Synthea's.
- **Do not change `deid.SCORE_THRESHOLD` in this work.** The benchmark exists to inform that decision; tuning against the same corpus used to report the score is circular.
- **Ground truth lives in `raw.patients`**, present only in the full local warehouse `data/healthcare.duckdb` — not in the committed `data/healthcare_demo.duckdb`. A missing table must produce a clear message naming the rebuild step, not a traceback.
- Model id, verbatim: `OpenMed/OpenMed-PII-SuperClinical-Small-44M-v1-onnx-android`
- History file format: one JSON object per line, `ts` first, matching `agent/route_eval_history.jsonl`.

## Verified facts

Established by querying the warehouse, not assumed:

- `raw.patients` columns: `Id BIRTHDATE DEATHDATE SSN DRIVERS PASSPORT PREFIX FIRST MIDDLE LAST SUFFIX MAIDEN MARITAL RACE ETHNICITY GENDER BIRTHPLACE ADDRESS CITY STATE COUNTY FIPS ZIP LAT LON HEALTHCARE_EXPENSES HEALTHCARE_COVERAGE INCOME`
- Example values: `FIRST='Ashely524'`, `LAST='Brekke496'`, `SSN='999-28-1649'`, `ZIP='00000'`, `ADDRESS='873 Mayer Avenue'`, `DRIVERS='S99979150'`, `PASSPORT='X41702617X'`, `BIRTHDATE='1997-10-25'`
- `dim_patient` in the demo DB carries **no** name, SSN, or address — confirming the full-warehouse prerequisite.
- `agent/deid.py` exposes: `available()`, `scan_columns(df, sample=20) -> list[ColumnFinding]`, `scrub_values(list[str]) -> list[str]`, `scrub_frame(df, columns)`, `apply_decisions(df, drop, mask)`, `REDACTION == "[REDACTED]"`, `MODEL_ID`, `SCORE_THRESHOLD`. `ColumnFinding` fields: `column, entity_types, hit_rate, examples, suggested, severity`.

---

## File Structure

| File | Responsibility |
|---|---|
| `agent/deid_eval.py` (create) | Corpus construction, scoring, `main()`, history append |
| `tests/test_deid_eval.py` (create) | Harness tests, `agent.deid` mocked |
| `agent/deid_eval_history.jsonl` (created at first run) | One record per run |
| `RUNBOOK.md` (modify) | How to run it and how to read it |

---

### Task 1: Load ground truth and normalise it

**Files:**
- Create: `agent/deid_eval.py`
- Test: `tests/test_deid_eval.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `Identity` dataclass with fields `first: str`, `last: str`, `ssn: str`, `address: str`, `city: str`, `zip: str`, `mrn: str`, `birthdate: str`; `normalise(rows: list[dict]) -> list[Identity]`; `raw_identities(rows: list[dict]) -> list[Identity]`; `load_rows(db_path: str | Path, limit: int) -> list[dict]`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_deid_eval.py
"""Benchmark harness tests. agent.deid is mocked: CI must never download a model."""
import pytest

from agent import deid_eval


_ROW = {
    "Id": "d545798e-09a4-ef89-abc5-9f62dc5a5095",
    "FIRST": "Ashely524", "LAST": "Brekke496",
    "SSN": "999-28-1649", "ADDRESS": "873 Mayer Avenue",
    "CITY": "Shrewsbury", "ZIP": "00000", "BIRTHDATE": "1997-10-25",
}


def test_raw_identities_keep_synthea_markers():
    ident = deid_eval.raw_identities([_ROW])[0]
    assert ident.first == "Ashely524"          # suffix retained
    assert ident.ssn == "999-28-1649"
    assert ident.zip == "00000"


def test_normalise_strips_name_suffixes():
    ident = deid_eval.normalise([_ROW])[0]
    assert ident.first == "Ashely"
    assert ident.last == "Brekke"


def test_normalise_replaces_the_placeholder_zip_and_reserved_ssn():
    """00000 is not a postcode and 999- is a never-issued SSN range. Both are Synthea markers
    that would make the measurement describe Synthea rather than clinical text."""
    ident = deid_eval.normalise([_ROW])[0]
    assert ident.zip != "00000" and len(ident.zip) == 5 and ident.zip.isdigit()
    assert not ident.ssn.startswith("999-")
    assert len(ident.ssn) == 11 and ident.ssn[3] == "-" and ident.ssn[6] == "-"


def test_normalise_is_deterministic():
    """A benchmark that moves between runs cannot show a regression."""
    a = deid_eval.normalise([_ROW])[0]
    b = deid_eval.normalise([_ROW])[0]
    assert (a.ssn, a.zip) == (b.ssn, b.zip)


def test_mrn_is_derived_from_the_patient_id():
    ident = deid_eval.normalise([_ROW])[0]
    assert ident.mrn.startswith("MRN ")
    assert ident.mrn != "MRN "


def test_load_rows_names_the_rebuild_step_when_raw_is_missing(tmp_path):
    import duckdb
    p = tmp_path / "empty.duckdb"
    duckdb.connect(str(p)).close()
    with pytest.raises(SystemExit) as e:
        deid_eval.load_rows(p, limit=10)
    assert "load_raw.py" in str(e.value)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_deid_eval.py -v`
Expected: FAIL — `ImportError: cannot import name 'deid_eval' from 'agent'`

- [ ] **Step 3: Write minimal implementation**

```python
# agent/deid_eval.py
"""Measure the de-identification model against identifiers Synthea already knows.

`agent/deid.py` reduces exposure by an amount nobody has measured: OpenMed publishes no recall
figures for the model. This harness supplies the missing number, using Synthea's own generated
identifiers as labels — no annotation, and no data-use agreement, which matters because the
standard corpora (i2b2/n2c2) are access-controlled.

Run:  .venv/bin/python -m agent.deid_eval

NOT run in CI: the model is a 453 MB download. CI unit-tests this harness against a mock, in the
same way route_eval and bayes_eval sit outside CI while guardrail_eval runs inside it.

Two corpus variants are scored. Synthea marks its output as fake — names carry numeric suffixes,
ZIP is 00000, SSNs use the reserved 999 prefix — so a figure measured on the raw form describes
Synthea rather than clinical text. The normalised variant is the headline; the gap between the two
measures how much those markers distort the result.
"""
from __future__ import annotations

import hashlib
import re
import sys
from dataclasses import dataclass
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "healthcare.duckdb"
HISTORY = Path(__file__).resolve().parent / "deid_eval_history.jsonl"

_SUFFIX = re.compile(r"\d+$")


@dataclass(frozen=True)
class Identity:
    """One patient's identifiers, as ground truth."""
    first: str
    last: str
    ssn: str
    address: str
    city: str
    zip: str
    mrn: str
    birthdate: str


def _stable_digits(seed: str, n: int) -> str:
    """Deterministic digits from a seed — a benchmark that moves between runs is useless."""
    h = hashlib.sha256(seed.encode()).hexdigest()
    return "".join(str(int(c, 16) % 10) for c in h[:n])


def _mrn(patient_id: str) -> str:
    return f"MRN {_stable_digits(patient_id, 6)}"


def raw_identities(rows: list[dict]) -> list[Identity]:
    """Exactly what Synthea emits, markers and all."""
    return [Identity(
        first=r["FIRST"], last=r["LAST"], ssn=r["SSN"], address=r["ADDRESS"],
        city=r["CITY"], zip=r["ZIP"], mrn=_mrn(r["Id"]), birthdate=r["BIRTHDATE"],
    ) for r in rows]


def normalise(rows: list[dict]) -> list[Identity]:
    """Strip Synthea's synthetic markers so the corpus reads like clinical text.

    Names lose their trailing digits (Brekke496 -> Brekke); the 00000 ZIP and the reserved
    999-prefix SSN are replaced with format-valid fakes derived deterministically from the
    patient id. This does NOT make the distribution real — see the spec's open risks — it only
    removes markers that would make the model's job artificially different.
    """
    out = []
    for r in rows:
        pid = r["Id"]
        out.append(Identity(
            first=_SUFFIX.sub("", r["FIRST"]),
            last=_SUFFIX.sub("", r["LAST"]),
            ssn=f"{_stable_digits(pid + 'a', 3)}-{_stable_digits(pid + 'b', 2)}-"
                f"{_stable_digits(pid + 'c', 4)}",
            address=r["ADDRESS"],
            city=r["CITY"],
            zip=_stable_digits(pid + "z", 5),
            mrn=_mrn(pid),
            birthdate=r["BIRTHDATE"],
        ))
    return out


def load_rows(db_path: str | Path = DB_PATH, limit: int = 200) -> list[dict]:
    """Read raw.patients, or exit with the rebuild instruction.

    raw.patients exists only in the FULL local warehouse. The committed demo database ships the
    modelled tables only, and dim_patient deliberately carries no name, SSN or address.
    """
    cols = ["Id", "FIRST", "LAST", "SSN", "ADDRESS", "CITY", "ZIP", "BIRTHDATE"]
    try:
        con = duckdb.connect(str(db_path), read_only=True)
    except Exception as exc:  # noqa: BLE001
        raise SystemExit(f"Cannot open {db_path}: {exc}\nBuild it first: python scripts/load_raw.py")
    try:
        rows = con.execute(
            f"select {', '.join(cols)} from raw.patients limit {int(limit)}").fetchall()
    except Exception:  # noqa: BLE001
        raise SystemExit(
            f"raw.patients not found in {db_path}.\n"
            "This benchmark needs the FULL warehouse, not the slim demo database. Generate the "
            "Synthea data, then run: python scripts/load_raw.py")
    finally:
        con.close()
    return [dict(zip(cols, r)) for r in rows]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_deid_eval.py -v`
Expected: PASS — 6 tests

- [ ] **Step 5: Commit**

```bash
git add agent/deid_eval.py tests/test_deid_eval.py
git commit -m "Load Synthea ground truth for the de-id benchmark, raw and normalised"
```

---

### Task 2: Column-level scoring

**Files:**
- Modify: `agent/deid_eval.py`
- Test: `tests/test_deid_eval.py`

**Interfaces:**
- Consumes: `Identity` from Task 1.
- Produces: `build_frame(identities: list[Identity]) -> tuple[pd.DataFrame, set[str]]` returning the frame and the set of column names that genuinely hold identifiers; `score_columns(df, truth: set[str]) -> dict` returning `{"recall": float, "precision": float, "flagged": list[str], "missed": list[str], "false_positives": list[str], "quasi_ok": bool}`.

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_deid_eval.py
import pandas as pd

from agent import deid


def _identities(n=3):
    rows = [dict(_ROW, Id=f"id-{i}", FIRST=f"Ashely{i}", LAST=f"Brekke{i}") for i in range(n)]
    return deid_eval.normalise(rows)


def test_build_frame_labels_identifier_columns_and_includes_clean_ones():
    df, truth = deid_eval.build_frame(_identities())
    assert {"first", "last", "ssn", "address", "zip", "mrn", "birthdate"} <= truth
    assert {"systolic_bp", "cured", "encounter_count", "cost_usd"} <= set(df.columns)
    assert not ({"systolic_bp", "cured", "encounter_count", "cost_usd"} & truth)
    assert len(df) == 3


def test_score_columns_is_perfect_when_every_identifier_column_is_flagged(monkeypatch):
    df, truth = deid_eval.build_frame(_identities())

    def fake_scan(frame, sample=20):
        return [deid.ColumnFinding(column=c, entity_types=["x"], hit_rate=1.0,
                                   examples=[], suggested="drop", severity="direct")
                for c in truth]
    monkeypatch.setattr(deid, "scan_columns", fake_scan)
    out = deid_eval.score_columns(df, truth)
    assert out["recall"] == 1.0
    assert out["precision"] == 1.0
    assert out["missed"] == []


def test_score_columns_reports_misses_and_false_positives(monkeypatch):
    df, truth = deid_eval.build_frame(_identities())

    def fake_scan(frame, sample=20):
        # flags one real identifier, misses the rest, and flags one clean column
        return [deid.ColumnFinding(column="first", entity_types=["first_name"], hit_rate=1.0,
                                   examples=[], suggested="drop", severity="direct"),
                deid.ColumnFinding(column="cured", entity_types=["age"], hit_rate=1.0,
                                   examples=[], suggested="keep", severity="quasi")]
    monkeypatch.setattr(deid, "scan_columns", fake_scan)
    out = deid_eval.score_columns(df, truth)
    assert out["recall"] == 1 / len(truth)
    assert out["precision"] == 0.5
    assert "cured" in out["false_positives"]
    assert "ssn" in out["missed"]


def test_score_columns_checks_that_age_and_sex_stay_quasi(monkeypatch):
    """A regression here silently destroys the covariates the modeling suite depends on."""
    df, truth = deid_eval.build_frame(_identities())

    def fake_scan(frame, sample=20):
        return [deid.ColumnFinding(column="age", entity_types=["age"], hit_rate=1.0,
                                   examples=[], suggested="drop", severity="direct")]
    monkeypatch.setattr(deid, "scan_columns", fake_scan)
    assert deid_eval.score_columns(df, truth)["quasi_ok"] is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_deid_eval.py -k "build_frame or score_columns" -v`
Expected: FAIL — `AttributeError: module 'agent.deid_eval' has no attribute 'build_frame'`

- [ ] **Step 3: Write minimal implementation**

```python
# append to agent/deid_eval.py
import pandas as pd

from . import deid

# Columns holding real identifiers, and columns that must NOT be flagged. A clean column flagged
# is a false positive that costs the user an unnecessary decision.
IDENTIFIER_COLUMNS = {"first", "last", "ssn", "address", "zip", "mrn", "birthdate"}
CLEAN_COLUMNS = ("systolic_bp", "cured", "encounter_count", "cost_usd")


def build_frame(identities: list[Identity]) -> tuple[pd.DataFrame, set[str]]:
    """A frame with known identifier columns, known-clean columns, and the two quasi covariates."""
    n = len(identities)
    df = pd.DataFrame({
        "first": [i.first for i in identities],
        "last": [i.last for i in identities],
        "ssn": [i.ssn for i in identities],
        "address": [i.address for i in identities],
        "zip": [i.zip for i in identities],
        "mrn": [i.mrn for i in identities],
        "birthdate": [i.birthdate for i in identities],
        # quasi covariates — must survive as `quasi`, not be suggested for dropping
        "age": [40 + (k % 45) for k in range(n)],
        "sex": ["M" if k % 2 else "F" for k in range(n)],
        # known-clean
        "systolic_bp": [110 + (k % 40) for k in range(n)],
        "cured": [k % 2 for k in range(n)],
        "encounter_count": [1 + (k % 9) for k in range(n)],
        "cost_usd": [100.0 + k for k in range(n)],
    })
    return df, set(IDENTIFIER_COLUMNS)


def score_columns(df: pd.DataFrame, truth: set[str]) -> dict:
    """Precision and recall over COLUMNS, plus the quasi-severity check."""
    findings = deid.scan_columns(df)
    flagged = {f.column for f in findings}
    hits = flagged & truth
    missed = truth - flagged
    false_positives = {c for c in flagged - truth if c in CLEAN_COLUMNS}
    # age and sex are expected to be flagged, but as `quasi` suggesting keep — never dropped.
    quasi_ok = all(f.severity == "quasi" and f.suggested == "keep"
                   for f in findings if f.column in ("age", "sex"))
    return {
        "recall": len(hits) / len(truth) if truth else 1.0,
        "precision": len(hits) / len(flagged) if flagged else 1.0,
        "flagged": sorted(flagged),
        "missed": sorted(missed),
        "false_positives": sorted(false_positives),
        "quasi_ok": quasi_ok,
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_deid_eval.py -v`
Expected: PASS — 10 tests

- [ ] **Step 5: Commit**

```bash
git add agent/deid_eval.py tests/test_deid_eval.py
git commit -m "Score column-level identifier detection against known labels"
```

---

### Task 3: Span-level scoring, per entity type

**Files:**
- Modify: `agent/deid_eval.py`
- Test: `tests/test_deid_eval.py`

**Interfaces:**
- Consumes: `Identity` from Task 1.
- Produces: `build_notes(identities) -> list[tuple[str, dict[str, str]]]` — each note text paired with `{entity_type: inserted_value}`; `score_spans(notes) -> dict` returning `{"recall": {type: float}, "overall": float, "leaks": {type: list[str]}}`.

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_deid_eval.py

def test_build_notes_pairs_each_note_with_what_was_inserted():
    notes = deid_eval.build_notes(_identities(2))
    assert len(notes) == 2
    text, truth = notes[0]
    for kind in ("name", "ssn", "address", "zip", "mrn", "date"):
        assert kind in truth
        assert truth[kind] in text          # ground truth by construction


def test_score_spans_is_perfect_when_everything_is_masked(monkeypatch):
    notes = deid_eval.build_notes(_identities(2))
    monkeypatch.setattr(deid, "scrub_values",
                        lambda vals: ["[REDACTED]" for _ in vals])
    out = deid_eval.score_spans(notes)
    assert out["overall"] == 1.0
    assert all(v == 1.0 for v in out["recall"].values())
    assert all(not v for v in out["leaks"].values())


def test_score_spans_is_zero_when_nothing_is_masked(monkeypatch):
    notes = deid_eval.build_notes(_identities(2))
    monkeypatch.setattr(deid, "scrub_values", lambda vals: list(vals))
    out = deid_eval.score_spans(notes)
    assert out["overall"] == 0.0
    assert all(v == 0.0 for v in out["recall"].values())


def test_score_spans_reports_recall_per_type_not_aggregated(monkeypatch):
    """An aggregate would have averaged away the MRN failure that motivated this benchmark."""
    notes = deid_eval.build_notes(_identities(2))

    def masks_names_only(vals):
        out = []
        for v in vals:
            for _text, truth in notes:
                v = v.replace(truth["name"], "[REDACTED]")
            out.append(v)
        return out
    monkeypatch.setattr(deid, "scrub_values", masks_names_only)
    out = deid_eval.score_spans(notes)
    assert out["recall"]["name"] == 1.0
    assert out["recall"]["ssn"] == 0.0
    assert out["leaks"]["ssn"]          # the surviving value is reported as evidence
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_deid_eval.py -k "build_notes or score_spans" -v`
Expected: FAIL — `AttributeError: module 'agent.deid_eval' has no attribute 'build_notes'`

- [ ] **Step 3: Write minimal implementation**

```python
# append to agent/deid_eval.py

_NOTE = ("Patient {name} (MRN {mrn_digits}), DOB {date}, SSN {ssn}, resides at {address}, "
         "{city} {zip}. Seen today in clinic; vitals stable and follow-up arranged.")

ENTITY_TYPES = ("name", "ssn", "address", "zip", "mrn", "date")


def build_notes(identities: list[Identity]) -> list[tuple[str, dict[str, str]]]:
    """Note-like text with known identifiers embedded, paired with what was inserted.

    Templated, not real: ground truth requires knowing exactly what went in. Real clinical text is
    messier and would very likely score worse — see the spec's open risks.
    """
    out = []
    for i in identities:
        name = f"{i.first} {i.last}"
        mrn_digits = i.mrn.replace("MRN ", "")
        text = _NOTE.format(name=name, mrn_digits=mrn_digits, date=i.birthdate, ssn=i.ssn,
                            address=i.address, city=i.city, zip=i.zip)
        out.append((text, {"name": name, "ssn": i.ssn, "address": i.address,
                           "zip": i.zip, "mrn": mrn_digits, "date": i.birthdate}))
    return out


def score_spans(notes: list[tuple[str, dict[str, str]]]) -> dict:
    """Per-entity-type recall: the share of inserted values no longer present after scrubbing."""
    scrubbed = deid.scrub_values([t for t, _ in notes])
    found = {k: 0 for k in ENTITY_TYPES}
    total = {k: 0 for k in ENTITY_TYPES}
    leaks: dict[str, list[str]] = {k: [] for k in ENTITY_TYPES}
    for out_text, (_orig, truth) in zip(scrubbed, notes):
        for kind, value in truth.items():
            total[kind] += 1
            if value not in out_text:
                found[kind] += 1
            elif len(leaks[kind]) < 5:      # evidence, capped so output stays readable
                leaks[kind].append(value)
    recall = {k: (found[k] / total[k] if total[k] else 1.0) for k in ENTITY_TYPES}
    all_found, all_total = sum(found.values()), sum(total.values())
    return {"recall": recall,
            "overall": all_found / all_total if all_total else 1.0,
            "leaks": leaks}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_deid_eval.py -v`
Expected: PASS — 14 tests

- [ ] **Step 5: Commit**

```bash
git add agent/deid_eval.py tests/test_deid_eval.py
git commit -m "Score span masking per entity type, with leak evidence"
```

---

### Task 4: The runnable entry point

**Files:**
- Modify: `agent/deid_eval.py`
- Test: `tests/test_deid_eval.py`

**Interfaces:**
- Consumes: everything from Tasks 1–3.
- Produces: `run(limit: int = 200, db_path=DB_PATH) -> dict` — the full record; `main(argv=None) -> int`.

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_deid_eval.py
import json


def test_run_scores_both_variants_and_records_the_gap(monkeypatch):
    monkeypatch.setattr(deid_eval, "load_rows",
                        lambda db_path=None, limit=200: [dict(_ROW, Id=f"id-{i}")
                                                         for i in range(3)])
    monkeypatch.setattr(deid, "available", lambda: True)
    monkeypatch.setattr(deid, "scan_columns", lambda frame, sample=20: [])
    monkeypatch.setattr(deid, "scrub_values", lambda vals: list(vals))
    rec = deid_eval.run(limit=3)
    assert set(rec) >= {"ts", "model", "threshold", "n_patients", "normalised", "raw"}
    assert rec["n_patients"] == 3
    for variant in ("normalised", "raw"):
        assert "column_recall" in rec[variant]
        assert "span_recall" in rec[variant]
        assert set(rec[variant]["span_recall"]) == set(deid_eval.ENTITY_TYPES)


def test_run_records_the_threshold_and_model_it_measured_at(monkeypatch):
    """A score without its threshold and model id cannot be compared against a later run."""
    monkeypatch.setattr(deid_eval, "load_rows",
                        lambda db_path=None, limit=200: [dict(_ROW, Id="id-0")])
    monkeypatch.setattr(deid, "scan_columns", lambda frame, sample=20: [])
    monkeypatch.setattr(deid, "scrub_values", lambda vals: list(vals))
    monkeypatch.setattr(deid, "SCORE_THRESHOLD", 0.42)
    rec = deid_eval.run(limit=1)
    assert rec["threshold"] == 0.42
    assert rec["model"] == deid.MODEL_ID


def test_main_exits_nonzero_and_says_so_when_the_model_is_unavailable(monkeypatch, capsys):
    monkeypatch.setattr(deid, "available", lambda: False)
    assert deid_eval.main([]) == 1
    assert "unavailable" in capsys.readouterr().out.lower()


def test_history_record_is_one_json_object_per_line(tmp_path, monkeypatch):
    hist = tmp_path / "h.jsonl"
    monkeypatch.setattr(deid_eval, "HISTORY", hist)
    deid_eval.append_history({"ts": "x", "overall": 1.0})
    deid_eval.append_history({"ts": "y", "overall": 0.5})
    lines = hist.read_text().strip().split("\n")
    assert len(lines) == 2
    assert json.loads(lines[1])["ts"] == "y"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_deid_eval.py -k "run_scores or main_exits or history_record" -v`
Expected: FAIL — `AttributeError: module 'agent.deid_eval' has no attribute 'run'`

- [ ] **Step 3: Write minimal implementation**

```python
# append to agent/deid_eval.py
import datetime as _dt
import json


def append_history(record: dict) -> None:
    """One JSON object per line, matching route_eval_history.jsonl and its siblings."""
    with HISTORY.open("a") as fh:
        fh.write(json.dumps(record) + "\n")


def _score_variant(identities: list[Identity]) -> dict:
    df, truth = build_frame(identities)
    cols = score_columns(df, truth)
    spans = score_spans(build_notes(identities))
    return {
        "column_recall": round(cols["recall"], 3),
        "column_precision": round(cols["precision"], 3),
        "column_missed": cols["missed"],
        "column_false_positives": cols["false_positives"],
        "quasi_ok": cols["quasi_ok"],
        "span_overall": round(spans["overall"], 3),
        "span_recall": {k: round(v, 3) for k, v in spans["recall"].items()},
        "leaks": spans["leaks"],
    }


def run(limit: int = 200, db_path=DB_PATH) -> dict:
    """Score both corpus variants and return the record."""
    rows = load_rows(db_path, limit)
    return {
        "ts": _dt.datetime.now().replace(microsecond=0).isoformat(),
        "model": deid.MODEL_ID,
        "threshold": deid.SCORE_THRESHOLD,
        "n_patients": len(rows),
        "normalised": _score_variant(normalise(rows)),
        "raw": _score_variant(raw_identities(rows)),
    }


def _print(rec: dict) -> None:
    print(f"\n  model={rec['model']}")
    print(f"  threshold={rec['threshold']}  n={rec['n_patients']}\n")
    for variant in ("normalised", "raw"):
        v = rec[variant]
        print(f"  {variant.upper()}")
        print(f"    columns   recall={v['column_recall']:.0%}  "
              f"precision={v['column_precision']:.0%}  quasi_ok={v['quasi_ok']}")
        if v["column_missed"]:
            print(f"      missed: {v['column_missed']}")
        if v["column_false_positives"]:
            print(f"      false positives: {v['column_false_positives']}")
        print(f"    spans     overall={v['span_overall']:.0%}")
        for kind, score in v["span_recall"].items():
            leak = v["leaks"].get(kind) or []
            note = f"   e.g. survived: {leak[0]!r}" if leak else ""
            print(f"      {kind:<9} {score:.0%}{note}")
        print()
    head = rec["normalised"]["span_overall"]
    print(f"  HEADLINE (normalised span recall): {head:.1%}")
    print("  Not a real-world figure — the distribution is still Synthea's.\n")


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if not deid.available():
        print("De-identification model unavailable — install openmed[onnx-runtime] first.")
        return 1
    limit = 200
    for a in argv:
        if a.startswith("--limit="):
            limit = int(a.split("=", 1)[1])
    rec = run(limit=limit)
    _print(rec)
    append_history(rec)
    print(f"  appended to {HISTORY.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_deid_eval.py -v && .venv/bin/python -m ruff check agent/deid_eval.py tests/test_deid_eval.py`
Expected: PASS — 18 tests, ruff clean

- [ ] **Step 5: Commit**

```bash
git add agent/deid_eval.py tests/test_deid_eval.py
git commit -m "Add the runnable de-id benchmark entry point and history file"
```

---

### Task 5: Run it for real, and publish the number

**Files:**
- Create: `agent/deid_eval_history.jsonl` (by running)
- Modify: `RUNBOOK.md`, `README.md`, `about.py`, `docs/superpowers/specs/2026-08-11-byod-deidentification-design.md`

**Interfaces:**
- Consumes: `main()` from Task 4.
- Produces: a measured number, and wording that reflects it.

- [ ] **Step 1: Run the benchmark**

Run: `.venv/bin/python -m agent.deid_eval --limit=200`

Expected: a table of per-entity-type recall for both variants, a headline figure, and a new line
in `agent/deid_eval_history.jsonl`.

**If `raw.patients` is missing**, the command names the rebuild step. Build the full warehouse
first (Synthea generate, then `python scripts/load_raw.py`) — do not fall back to the demo
database, which carries no identifiers.

- [ ] **Step 2: Record what was measured**

Write the actual figures into this plan's checkbox as a comment, and into the commit message in
Step 5. **Do not tune `deid.SCORE_THRESHOLD` in response** — that is explicitly out of scope, and
tuning against the corpus used to report the score is circular. If the score is poor, that is the
finding.

- [ ] **Step 3: Add a RUNBOOK entry**

Append to `RUNBOOK.md`:

```markdown
### De-identification benchmark

Measures the de-id model against identifiers Synthea already knows. **Needs the full warehouse**
(`data/healthcare.duckdb`) — the slim demo database carries no identifiers.

```bash
.venv/bin/python -m agent.deid_eval --limit=200
```

Two corpus variants are scored. **normalised** strips Synthea's markers (name suffixes, the 00000
ZIP, the reserved 999- SSN) and is the headline; **raw** is what Synthea emits. The gap between
them shows how much those markers distort the result.

Span recall is reported per entity type on purpose — an aggregate would average away a single
type failing, which is exactly what happened with MRNs during development.

Results append to `agent/deid_eval_history.jsonl`. Not run in CI: the model is a 453 MB download.

**The normalised figure is not a real-world recall number.** The distribution is still Synthea's,
and the notes are templated. Real clinical text would very likely score worse.
```

- [ ] **Step 4: Replace the hedged wording with the measured number**

Three places currently say some version of "reduces exposure by an unmeasured amount". Update each
to cite the measured figure, its corpus, and its limits:

- `README.md` — wherever the de-identification feature is described
- `about.py` — `BYOD_NOTE`, keeping every existing disclosure (`tests/test_about.py` asserts
  `synthetic`, `no phi`, `read-only`, `1,000 rows` survive; if it fails, fix the copy not the test)
- `docs/superpowers/specs/2026-08-11-byod-deidentification-design.md` — §8's "what the tests
  deliberately do not establish" and §10's first open risk

Keep the claim ceiling from that spec's §6: never "de-identified", "HIPAA", "compliant", or
"safe to share".

- [ ] **Step 5: Verify and commit**

Run: `.venv/bin/python -m pytest -q -p no:warnings && .venv/bin/python -m ruff check .`
Expected: full suite green, ruff clean.

```bash
git add agent/deid_eval_history.jsonl RUNBOOK.md README.md about.py docs/
git commit -m "Measure de-identification recall and publish the number"
```

---

## Verification checklist

- [ ] `.venv/bin/python -m pytest -q -p no:warnings` — green, exit 0
- [ ] `.venv/bin/python -m ruff check .` — clean
- [ ] `agent/deid_eval_history.jsonl` has a record with both variants and per-type span recall
- [ ] `grep -rn "unmeasured" README.md about.py docs/` returns nothing stale
- [ ] `.github/workflows/ci.yml` is **unchanged** — this must not run in CI
- [ ] `deid.SCORE_THRESHOLD` is **unchanged**
