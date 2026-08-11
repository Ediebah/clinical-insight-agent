# BYOD On-Device De-identification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a user upload real clinical data by scanning it locally for identifiers, letting them decide per column what to drop, mask, or keep, and scrubbing every path by which their data could reach the language model.

**Architecture:** Three layers. A structural layer drops or masks flagged columns from the DataFrame before it reaches DuckDB, closing two exits at once. A boundary layer scrubs the catalog's example values. A policy layer threads the list of flagged-but-kept columns into `agent._preview_csv`, the single choke point through which frame content reaches any prompt. A new `agent/deid.py` is the only module that imports `openmed`.

**Tech Stack:** Python 3.12, `openmed` 2.0.0 (Apache-2.0), ONNX Runtime, pandas, Streamlit, pytest.

**Spec:** `docs/superpowers/specs/2026-08-11-byod-deidentification-design.md`

## Global Constraints

- **Never claim the data is de-identified, HIPAA-compliant, safe to share, or cleared for any regulatory purpose.** The model publishes no recall figures. Permitted wording is fixed in Task 6.
- **Fail open, loudly.** If `openmed` is missing or the model cannot load, the upload still works, the original warning is shown unmodified, and the UI states that de-identification is unavailable. Never a silent no-op.
- **The demo-warehouse path must be byte-for-byte unchanged.** When `deid_columns` is falsy there must be no model load, no scrub, and no latency. Task 5 has the regression test.
- **CI must never download a model.** All tests mock `openmed`.
- **Never echo a detected identifier back to the screen.** Previews in the UI are redacted.
- Python floor is **3.10** (`openmed` requirement); this project runs 3.12.
- Model id, used verbatim: `OpenMed/OpenMed-PII-SuperClinical-Small-44M-v1-onnx-android`

---

## File Structure

| File | Responsibility |
|---|---|
| `agent/deid.py` (create) | The only `openmed` importer. Scan, scrub, apply decisions. No Streamlit import. |
| `tests/test_deid.py` (create) | Unit tests for the above, `openmed` mocked. |
| `agent/userdata.py` (modify) | `build_catalog` scrubs example values. |
| `agent/agent.py` (modify) | `deid_columns` threaded from `run_analysis` to `_preview_csv`. |
| `app.py` (modify) | The decision panel in the BYOD block; passes `deid_columns` to `run_analysis`. |
| `requirements.txt` (modify) | Pin `openmed` and `onnxruntime`. |

---

### Task 1: The `deid` module — availability and scrubbing

**Files:**
- Create: `agent/deid.py`
- Test: `tests/test_deid.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `available() -> bool`, `scrub_values(values: list[str]) -> list[str]`, `ColumnFinding` dataclass with fields `column: str`, `entity_types: list[str]`, `hit_rate: float`, `examples: list[str]`, `suggested: str`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_deid.py
"""De-identification wrapper. openmed is mocked throughout: CI must never download a model."""
import sys
import types

import pandas as pd
import pytest

from agent import deid


def _fake_openmed(spans_by_text):
    """A stand-in openmed module. spans_by_text maps input text -> [(label, substring)]."""
    mod = types.ModuleType("openmed")

    def deidentify(text, method="mask"):
        result = text
        for _label, sub in spans_by_text.get(text, []):
            result = result.replace(sub, "[REDACTED]")
        return types.SimpleNamespace(deidentified_text=result)

    def extract_pii(text, model_name=None):
        ents = [types.SimpleNamespace(label=label, text=sub)
                for label, sub in spans_by_text.get(text, [])]
        return types.SimpleNamespace(entities=ents)

    mod.deidentify = deidentify
    mod.extract_pii = extract_pii
    return mod


def test_available_is_false_when_openmed_is_absent(monkeypatch):
    monkeypatch.setitem(sys.modules, "openmed", None)
    assert deid.available() is False


def test_available_never_raises_on_a_broken_import(monkeypatch):
    broken = types.ModuleType("openmed")   # importable but missing the API we need
    monkeypatch.setitem(sys.modules, "openmed", broken)
    assert deid.available() is False


def test_scrub_values_masks_detected_spans(monkeypatch):
    monkeypatch.setitem(sys.modules, "openmed",
                        _fake_openmed({"John Doe": [("NAME", "John Doe")]}))
    assert deid.scrub_values(["John Doe", "42"]) == ["[REDACTED]", "42"]


def test_scrub_values_returns_input_unchanged_when_unavailable(monkeypatch):
    monkeypatch.setitem(sys.modules, "openmed", None)
    assert deid.scrub_values(["John Doe"]) == ["John Doe"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_deid.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'agent.deid'`

- [ ] **Step 3: Write minimal implementation**

```python
# agent/deid.py
"""On-device PII/PHI detection for uploaded data, via OpenMed's local ONNX models.

The ONLY module that imports `openmed`. No Streamlit import, so it is testable headless.

This is a DETECTOR that informs a human decision, never a gate that certifies data. OpenMed's
model card publishes no recall figures and states that local execution does not by itself
guarantee regulatory compliance, so a clean scan must never be presented as an all-clear. See
docs/superpowers/specs/2026-08-11-byod-deidentification-design.md.

Every function fails OPEN: if the model is unavailable the caller still works, unscrubbed, and
the UI is responsible for saying so. A silent no-op would be worse than no feature at all.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

import pandas as pd

log = logging.getLogger(__name__)

MODEL_ID = "OpenMed/OpenMed-PII-SuperClinical-Small-44M-v1-onnx-android"
REDACTION = "[REDACTED]"

# No module-level model cache here: openmed's top-level API caches the loaded model itself, and
# the import is resolved from sys.modules after the first call. Lazy by construction — importing
# this module costs nothing, and the 44M model downloads only on the first real scan.


@dataclass
class ColumnFinding:
    """One flagged column. `examples` are REDACTED previews — never echo a raw identifier."""
    column: str
    entity_types: list[str] = field(default_factory=list)
    hit_rate: float = 0.0
    examples: list[str] = field(default_factory=list)
    suggested: str = "mask"          # "drop" | "mask"


def _openmed():
    """Import openmed, or return None. Never raises — a missing model must not break an upload."""
    try:
        import openmed
    except Exception as exc:  # noqa: BLE001
        log.info("openmed unavailable: %s", exc)
        return None
    if openmed is None or not hasattr(openmed, "deidentify") or not hasattr(openmed, "extract_pii"):
        log.info("openmed present but missing the expected API")
        return None
    return openmed


def available() -> bool:
    return _openmed() is not None


def scrub_values(values: list[str]) -> list[str]:
    """Mask detected identifiers in each string. Returns the input unchanged if unavailable."""
    om = _openmed()
    if om is None:
        return list(values)
    out = []
    for v in values:
        try:
            out.append(om.deidentify(str(v), method="mask").deidentified_text)
        except Exception as exc:  # noqa: BLE001
            log.warning("scrub failed for one value: %s", exc)
            out.append(REDACTION)      # fail CLOSED per value: an unscrubbable value is redacted
    return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_deid.py -v`
Expected: PASS — 4 tests

- [ ] **Step 5: Commit**

```bash
git add agent/deid.py tests/test_deid.py
git commit -m "Add a fail-open de-identification wrapper over openmed"
```

---

### Task 2: Column scanning and decisions

**Files:**
- Modify: `agent/deid.py`
- Test: `tests/test_deid.py`

**Interfaces:**
- Consumes: `ColumnFinding`, `_openmed()`, `REDACTION` from Task 1.
- Produces: `scan_columns(df: pd.DataFrame, sample: int = 20) -> list[ColumnFinding]`, `apply_decisions(df: pd.DataFrame, drop: list[str], mask: list[str]) -> pd.DataFrame`, `scrub_frame(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame`.

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_deid.py

def test_scan_flags_an_identifying_column_and_ignores_a_numeric_one(monkeypatch):
    monkeypatch.setitem(sys.modules, "openmed", _fake_openmed({
        "John Doe": [("NAME", "John Doe")],
        "Jane Roe": [("NAME", "Jane Roe")],
    }))
    df = pd.DataFrame({"patient": ["John Doe", "Jane Roe"], "age": [41, 52]})
    findings = deid.scan_columns(df)
    assert [f.column for f in findings] == ["patient"]
    assert findings[0].entity_types == ["NAME"]
    assert findings[0].hit_rate == 1.0


def test_scan_suggests_drop_at_high_hit_rate_and_mask_below(monkeypatch):
    monkeypatch.setitem(sys.modules, "openmed", _fake_openmed({
        "John Doe": [("NAME", "John Doe")],
        "seen in clinic": [],
        "no issues": [],
        "no concerns": [],
        "stable": [],
    }))
    high = pd.DataFrame({"name": ["John Doe"] * 4})
    low = pd.DataFrame({"notes": ["John Doe", "seen in clinic", "no issues", "stable"]})
    assert deid.scan_columns(high)[0].suggested == "drop"
    assert deid.scan_columns(low)[0].suggested == "mask"


def test_scan_examples_never_contain_the_raw_identifier(monkeypatch):
    monkeypatch.setitem(sys.modules, "openmed", _fake_openmed({
        "John Doe": [("NAME", "John Doe")]}))
    finding = deid.scan_columns(pd.DataFrame({"patient": ["John Doe"]}))[0]
    assert all("John Doe" not in e for e in finding.examples)


def test_scan_returns_nothing_when_unavailable(monkeypatch):
    monkeypatch.setitem(sys.modules, "openmed", None)
    assert deid.scan_columns(pd.DataFrame({"patient": ["John Doe"]})) == []


def test_apply_decisions_drops_and_masks_exactly_the_named_columns(monkeypatch):
    monkeypatch.setitem(sys.modules, "openmed", _fake_openmed({
        "John Doe": [("NAME", "John Doe")]}))
    df = pd.DataFrame({"a": ["John Doe"], "b": ["John Doe"], "c": [7]})
    out = deid.apply_decisions(df, drop=["a"], mask=["b"])
    assert list(out.columns) == ["b", "c"]
    assert out["b"].iloc[0] == "[REDACTED]"
    assert out["c"].iloc[0] == 7


def test_scrub_frame_touches_only_the_named_columns(monkeypatch):
    monkeypatch.setitem(sys.modules, "openmed", _fake_openmed({
        "John Doe": [("NAME", "John Doe")]}))
    df = pd.DataFrame({"keep": ["John Doe"], "other": ["John Doe"]})
    out = deid.scrub_frame(df, ["keep"])
    assert out["keep"].iloc[0] == "[REDACTED]"
    assert out["other"].iloc[0] == "John Doe"


def test_scrub_frame_is_a_noop_for_an_empty_column_list(monkeypatch):
    monkeypatch.setitem(sys.modules, "openmed", _fake_openmed({}))
    df = pd.DataFrame({"a": ["x"]})
    assert deid.scrub_frame(df, []) is df
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_deid.py -v`
Expected: FAIL — `AttributeError: module 'agent.deid' has no attribute 'scan_columns'`

- [ ] **Step 3: Write minimal implementation**

```python
# append to agent/deid.py

DROP_THRESHOLD = 0.8       # at/above this share of sampled values, the column IS identifiers


def _detect(text: str) -> list[str]:
    """Entity labels found in one string. Empty on any failure — callers treat that as 'no hit'."""
    om = _openmed()
    if om is None:
        return []
    try:
        return [e.label for e in om.extract_pii(str(text), model_name=MODEL_ID).entities]
    except Exception as exc:  # noqa: BLE001
        log.warning("detect failed for one value: %s", exc)
        return []


def scan_columns(df: pd.DataFrame, sample: int = 20) -> list[ColumnFinding]:
    """Sample each column and report which look like they hold identifiers.

    Sampling, not exhaustive: the frame can be 12M cells and never leaves the machine, so the
    scan exists to inform a per-COLUMN decision, not to find every cell. That structural framing
    is what keeps the feature honest despite the model's unpublished recall.
    """
    if _openmed() is None:
        return []
    findings: list[ColumnFinding] = []
    for col in df.columns:
        values = [str(v) for v in df[col].dropna().unique()[:sample]]
        if not values:
            continue
        labels, hits = [], 0
        for v in values:
            found = _detect(v)
            if found:
                hits += 1
                labels.extend(found)
        if not hits:
            continue
        rate = hits / len(values)
        findings.append(ColumnFinding(
            column=str(col),
            entity_types=sorted(set(labels)),
            hit_rate=rate,
            examples=scrub_values(values[:3]),          # redacted previews only
            suggested="drop" if rate >= DROP_THRESHOLD else "mask",
        ))
    return findings


def apply_decisions(df: pd.DataFrame, drop: list[str], mask: list[str]) -> pd.DataFrame:
    """Drop the named columns outright and mask identifiers within the others.

    Dropping happens before the frame reaches DuckDB, so a dropped column can appear neither in
    the catalog's example values nor in any query result — one action closes two exits.
    """
    out = df.drop(columns=[c for c in drop if c in df.columns])
    for col in mask:
        if col in out.columns:
            out[col] = scrub_values([str(v) for v in out[col]])
    return out


def scrub_frame(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    """Mask identifiers in the named columns of a result frame. Returns df unchanged if none."""
    cols = [c for c in columns if c in df.columns]
    if not cols:
        return df
    out = df.copy()
    for col in cols:
        out[col] = scrub_values([str(v) for v in out[col]])
    return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_deid.py -v`
Expected: PASS — 11 tests

- [ ] **Step 5: Commit**

```bash
git add agent/deid.py tests/test_deid.py
git commit -m "Scan uploaded columns for identifiers and apply per-column decisions"
```

---

### Task 3: Scrub the catalog's example values

**Files:**
- Modify: `agent/userdata.py` (the `build_catalog` function)
- Test: `tests/test_userdata.py`

**Interfaces:**
- Consumes: `deid.scrub_values` from Task 1.
- Produces: no new signature; `build_catalog` behaviour changes.

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_userdata.py
import pandas as pd

from agent import userdata


def test_build_catalog_scrubs_example_values(monkeypatch):
    """Example values are one of only three things that reach the LLM — they must be scrubbed."""
    monkeypatch.setattr("agent.deid.scrub_values", lambda vals: ["[REDACTED]" for _ in vals])
    cat = userdata.build_catalog(pd.DataFrame({"patient": ["John Doe", "Jane Roe"]}), "t")
    assert cat["tables"][0]["columns"][0]["example_values"] == ["[REDACTED]", "[REDACTED]"]


def test_build_catalog_survives_a_broken_scrubber(monkeypatch):
    """A failing de-id must not break an upload — fail open."""
    def boom(_vals):
        raise RuntimeError("model gone")
    monkeypatch.setattr("agent.deid.scrub_values", boom)
    cat = userdata.build_catalog(pd.DataFrame({"patient": ["John Doe"]}), "t")
    assert cat["tables"][0]["columns"][0]["example_values"] == ["John Doe"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_userdata.py -k build_catalog -v`
Expected: FAIL — the first test returns `['John Doe', 'Jane Roe']`

- [ ] **Step 3: Write minimal implementation**

In `agent/userdata.py`, replace the `examples` line inside `build_catalog`:

```python
        examples = [str(v)[:28] for v in pd.unique(s.dropna())[:3]]
```

with:

```python
        examples = [str(v)[:28] for v in pd.unique(s.dropna())[:3]]
        # These values reach the LLM verbatim (see the module docstring), so they are the one
        # place a kept column can still leak. Fail open: a broken scrubber must not break upload.
        try:
            from . import deid
            examples = deid.scrub_values(examples)
        except Exception:  # noqa: BLE001
            pass
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_userdata.py -v`
Expected: PASS — all tests in the file

- [ ] **Step 5: Commit**

```bash
git add agent/userdata.py tests/test_userdata.py
git commit -m "Scrub the BYOD catalog's example values before they reach the model"
```

---

### Task 4: Thread the policy into the prompt choke point

**Files:**
- Modify: `agent/agent.py` (`_preview_csv` at :196, `_verify` at :207, `_interpret` at :235, `run_analysis` at :662)
- Test: `tests/test_agent.py`

**Interfaces:**
- Consumes: `deid.scrub_frame` from Task 2.
- Produces: `run_analysis(question, max_tries=..., catalog=None, db_path=None, deid_columns: list[str] | None = None)`; `_preview_csv(df, rows, deid_columns=None)`; `_verify(question, sql, df, deid_columns=None)`; `_interpret(question, sql, df, findings, deid_columns=None)`.

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_agent.py
import pandas as pd

from agent import agent as agent_mod


def test_preview_csv_scrubs_only_the_policy_columns(monkeypatch):
    monkeypatch.setattr("agent.deid.scrub_frame",
                        lambda df, cols: df.assign(**{c: "[REDACTED]" for c in cols}))
    df = pd.DataFrame({"notes": ["John Doe"], "n": [1]})
    out = agent_mod._preview_csv(df, 30, deid_columns=["notes"])
    assert "John Doe" not in out
    assert "[REDACTED]" in out


def test_preview_csv_does_not_touch_deid_when_policy_is_empty(monkeypatch):
    """The demo-warehouse path must be byte-for-byte unchanged: no scrub, no model load."""
    def boom(_df, _cols):
        raise AssertionError("deid must not be called when deid_columns is falsy")
    monkeypatch.setattr("agent.deid.scrub_frame", boom)
    df = pd.DataFrame({"a": ["x"], "n": [1]})
    assert "x" in agent_mod._preview_csv(df, 30)
    assert "x" in agent_mod._preview_csv(df, 30, deid_columns=[])
    assert "x" in agent_mod._preview_csv(df, 30, deid_columns=None)


def test_run_analysis_accepts_a_deid_columns_argument():
    import inspect
    sig = inspect.signature(agent_mod.run_analysis)
    assert "deid_columns" in sig.parameters
    assert sig.parameters["deid_columns"].default is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_agent.py -k "preview_csv or deid_columns" -v`
Expected: FAIL — `TypeError: _preview_csv() got an unexpected keyword argument 'deid_columns'`

- [ ] **Step 3: Write minimal implementation**

In `agent/agent.py`, change `_preview_csv`:

```python
def _preview_csv(df: pd.DataFrame, rows: int, deid_columns: list[str] | None = None) -> str:
    """CSV preview capped in BOTH dimensions — at most `rows` rows AND _CELL_WIDTH chars per cell —
    so one huge cell (e.g. a whole file dumped into an uploaded column) can't blow up the token count.

    This is the ONLY path by which frame content reaches a prompt, which is why the BYOD de-id
    policy is applied here: one choke point, rather than trusting every future call site.
    `deid_columns` is empty for the demo warehouse, and the import is skipped entirely then.
    """
    head = df.head(rows).copy()
    if deid_columns:
        from . import deid
        head = deid.scrub_frame(head, deid_columns)
    for col in head.columns:
        head[col] = head[col].map(_truncate_cell)
    return head.to_csv(index=False)
```

Change `_verify` (line ~207) — signature and the preview call:

```python
def _verify(question: str, sql: str, df: pd.DataFrame, deid_columns: list[str] | None = None) -> dict:
    """Critic pass: does the SQL actually answer THIS question? Confidence + issues."""
    preview = _preview_csv(df, 15, deid_columns)
```

Change `_interpret` (line ~235) — signature and the preview call:

```python
def _interpret(question: str, sql: str, df: pd.DataFrame, findings: list[guardrails.Finding],
               deid_columns: list[str] | None = None) -> str:
    preview = _preview_csv(df, 30, deid_columns)
```

Change `run_analysis` (line ~662):

```python
def run_analysis(question: str, max_tries: int = MAX_SQL_TRIES,
                 catalog: dict | None = None, db_path=None,
                 deid_columns: list[str] | None = None) -> AgentResult:
```

Then update the two call sites inside `run_analysis` to pass it through: the `_verify(...)` call and `result.interpretation = _interpret(question, sql, df, result.findings)` at line ~802, which becomes:

```python
            result.interpretation = _interpret(question, sql, df, result.findings, deid_columns)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_agent.py -v`
Expected: PASS — the whole file, including the pre-existing tests

- [ ] **Step 5: Commit**

```bash
git add agent/agent.py tests/test_agent.py
git commit -m "Thread the BYOD de-id policy into the single prompt choke point"
```

---

### Task 5: The decision panel in the BYOD block

**Files:**
- Modify: `app.py` (the BYOD upload block at ~1470-1495, and the `run_analysis` call at ~1785)
- Test: `tests/test_app_smoke.py`

**Interfaces:**
- Consumes: `deid.available`, `deid.scan_columns`, `deid.apply_decisions` (Tasks 1-2); `run_analysis(..., deid_columns=...)` (Task 4).
- Produces: `st.session_state.byod["deid_columns"]` — the flagged-but-kept column list.

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_app_smoke.py

def test_byod_upload_still_works_when_deid_is_unavailable(monkeypatch):
    """Fail open: a missing model must never block an upload."""
    monkeypatch.setattr("agent.deid.available", lambda: False)
    at = AppTest.from_file("app.py", default_timeout=120).run()
    at.segmented_control[0].set_value("🔬 Analyze").run()
    at.radio[0].set_value("Bring your own data").run()
    assert not at.exception, [str(e.value) for e in at.exception]
    assert at.file_uploader
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_app_smoke.py -k deid -v`
Expected: FAIL. `deid.available` exists from Task 1, so `monkeypatch.setattr` succeeds; the test
fails at `at.radio[0]` because the BYOD block has no de-id panel and the radio indices differ from
what the panel will produce. Read the actual failure before implementing — if it instead errors on
`agent.deid` not existing, Task 1 was not completed.

- [ ] **Step 3: Write minimal implementation**

In `app.py`, inside the BYOD block, between `_df, _notes = userdata.read_upload(...)` and
`_dbp, _cat, _tbl, _clean = userdata.prepare_upload(...)`, insert the scan and decision panel:

```python
            from agent import deid
            _deid_kept: list[str] = []
            if deid.available():
                _findings = deid.scan_columns(_df)
                if _findings:
                    st.markdown("<div class='eyebrow'>Possible identifiers found</div>",
                                unsafe_allow_html=True)
                    st.markdown(
                        f"{len(_findings)} of {len(_df.columns)} columns look like they hold "
                        "identifiers. Choose what to do with each. **Keep** leaves the column in "
                        "your data; its values are scrubbed on the way to the model, but that "
                        "depends on detection quality the model's authors have not published.")
                    _drop, _mask = [], []
                    for _f in _findings:
                        _choice = st.radio(
                            f"`{_f.column}` — {', '.join(_f.entity_types)} "
                            f"({_f.hit_rate:.0%} of sampled values)",
                            ["Drop", "Mask", "Keep"],
                            index=0 if _f.suggested == "drop" else 1,
                            horizontal=True, key=f"deid_{_f.column}")
                        if _choice == "Drop":
                            _drop.append(_f.column)
                        elif _choice == "Mask":
                            _mask.append(_f.column)
                        else:
                            _deid_kept.append(_f.column)
                    _df = deid.apply_decisions(_df, _drop, _mask)
            else:
                st.caption("On-device de-identification is unavailable — install `openmed` to "
                           "scan uploads for identifiers. The warning above still applies.")
```

Then add the kept-column list to the session entry, changing:

```python
                "file_id": _fid, "rows": len(_clean), "ncols": len(_clean.columns), "cols": _cols}
```

to:

```python
                "file_id": _fid, "rows": len(_clean), "ncols": len(_clean.columns), "cols": _cols,
                "deid_columns": [c for c in _deid_kept if c in _clean.columns]}
```

Finally, pass the policy through at the `run_analysis` call (~line 1785):

```python
        st.session_state.result = run_analysis(
            question, catalog=(_b or {}).get("catalog"), db_path=(_b or {}).get("db_path"),
            deid_columns=(_b or {}).get("deid_columns"))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_app_smoke.py -v`
Expected: PASS — all cases including the pre-existing About and Analyze smoke tests

- [ ] **Step 5: Commit**

```bash
git add app.py tests/test_app_smoke.py
git commit -m "Add the per-column de-identification decision panel to the upload path"
```

---

### Task 6: Honest claim wording and the loopback check

**Files:**
- Modify: `agent/deid.py`, `app.py`
- Test: `tests/test_deid.py`

**Interfaces:**
- Consumes: nothing new.
- Produces: `llm_is_on_this_machine() -> bool`, `assurance_line(scrubbed: bool) -> str`.

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_deid.py

@pytest.mark.parametrize("url,expected", [
    ("http://localhost:11434/v1", True),
    ("http://127.0.0.1:11434/v1", True),
    ("http://[::1]:11434/v1", True),
    ("https://api.groq.com/openai/v1", False),      # a REMOTE custom endpoint
    ("https://api.together.xyz/v1", False),
    ("", False),                                     # unset -> hosted OpenAI
])
def test_loopback_check_is_true_only_for_this_machine(monkeypatch, url, expected):
    """llm._is_local() is documented as true for remote free-tier endpoints, so it must NOT be
    used here: it would assert 'nothing left this machine' exactly when that is false."""
    monkeypatch.setenv("OPENAI_BASE_URL", url)
    assert deid.llm_is_on_this_machine() is expected


def test_assurance_line_never_claims_compliance(monkeypatch):
    monkeypatch.setenv("OPENAI_BASE_URL", "")
    line = deid.assurance_line(scrubbed=True)
    lowered = line.lower()
    assert "identifiers were removed" in lowered
    assert "nothing left this machine" not in lowered
    for forbidden in ("hipaa", "compliant", "de-identified", "safe to share", "anonymised",
                      "anonymized"):
        assert forbidden not in lowered


def test_assurance_line_adds_the_local_claim_only_on_loopback(monkeypatch):
    monkeypatch.setenv("OPENAI_BASE_URL", "http://localhost:11434/v1")
    assert "nothing left this machine" in deid.assurance_line(scrubbed=True).lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_deid.py -k "loopback or assurance" -v`
Expected: FAIL — `AttributeError: module 'agent.deid' has no attribute 'llm_is_on_this_machine'`

- [ ] **Step 3: Write minimal implementation**

```python
# append to agent/deid.py
import os
from urllib.parse import urlparse

_LOOPBACK = {"localhost", "127.0.0.1", "::1", "[::1]"}


def llm_is_on_this_machine() -> bool:
    """True only when OPENAI_BASE_URL points at loopback.

    Deliberately NOT llm._is_local(), whose own docstring says it is true for "Ollama, LM Studio,
    vLLM, a free-tier API" — a REMOTE endpoint such as Groq also sets OPENAI_BASE_URL. Using it
    would assert "nothing left this machine" in precisely the case where that is false.
    """
    url = os.getenv("OPENAI_BASE_URL", "")
    if not url:
        return False                     # unset -> hosted OpenAI
    try:
        host = urlparse(url).hostname or ""
    except Exception:  # noqa: BLE001
        return False
    return host in _LOOPBACK


def assurance_line(scrubbed: bool) -> str:
    """The ONLY sanctioned wording. Defaults to the weaker claim; never mentions compliance.

    The model publishes no recall figures and its card states that local execution does not by
    itself guarantee regulatory compliance, so nothing here may imply the data is de-identified,
    HIPAA-compliant, or safe to share.
    """
    if not scrubbed:
        return "On-device de-identification did not run."
    line = "Identifiers were removed before anything reached the language model."
    if llm_is_on_this_machine():
        line += " With a local model, nothing left this machine."
    return line
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_deid.py -v`
Expected: PASS — 11 tests from Tasks 1-2 plus 8 new

- [ ] **Step 5: Show the line in the UI, then commit**

In `app.py`, immediately after the `st.success(f"Loaded **{_tbl}** …")` line, add:

```python
            if deid.available():
                st.caption(deid.assurance_line(scrubbed=True))
```

```bash
git add agent/deid.py app.py tests/test_deid.py
git commit -m "Gate the privacy claim on a loopback check, not the misnamed _is_local"
```

---

### Task 7: Pin the dependencies

**Files:**
- Modify: `requirements.txt`

**Interfaces:**
- Consumes: nothing.
- Produces: nothing importable; makes Tasks 1-6 runnable on the deploy.

- [ ] **Step 1: Add the pins**

Append to `requirements.txt`, after `openpyxl==3.1.5`:

```
# On-device PII/PHI detection for uploaded data (agent/deid.py). Apache-2.0. The 44M ONNX model
# downloads from HF Hub on FIRST UPLOAD only — importing the package costs nothing, so app
# cold-start is unaffected and a user who never uploads never pays for it.
openmed==2.0.0
onnxruntime==1.24.0
```

Also bump the rebuild marker comment near the top of the file, which this project uses to force a
Streamlit Cloud rebuild:

```
# Streamlit Cloud rebuild marker: on-device de-identification, 2026-08-11.
```

- [ ] **Step 2: Verify the install resolves locally**

Run: `uv pip install -r requirements.txt --python .venv/bin/python`
Expected: resolves with no conflict against the existing pandas 3.0.3 / numpy 2.5.0 pins. **If it
conflicts, stop and report** — do not loosen the existing pins, which are the versions the app is
verified against.

- [ ] **Step 3: Confirm the real package satisfies the wrapper's expectations**

Run:
```bash
.venv/bin/python -c "
from agent import deid
print('available:', deid.available())
print(deid.scrub_values(['Patient John Doe, MRN 123456']))"
```
Expected: `available: True`, and the output string has the name and MRN replaced. This is the first
point at which the real model downloads. **If detection is obviously poor, record what you saw** —
the spec's §10 lists unmeasured recall as the central open risk.

- [ ] **Step 4: Run the full suite**

Run: `.venv/bin/python -m pytest -q -p no:warnings && .venv/bin/python -m ruff check .`
Expected: all pass, ruff clean. Tests still mock `openmed`, so they must not have slowed down.

- [ ] **Step 5: Commit**

```bash
git add requirements.txt
git commit -m "Pin openmed and onnxruntime for on-device de-identification"
```

---

### Task 8: Document it

**Files:**
- Modify: `about.py`, `RUNBOOK.md`, `CONCEPTS.md`

**Interfaces:**
- Consumes: the finished feature.
- Produces: user-facing documentation.

- [ ] **Step 1: Update the About page's BYOD copy**

In `about.py`, replace `BYOD_NOTE` with:

```python
BYOD_NOTE = (
    "Upload a CSV or Excel file and the agent profiles it, infers each column's structural role, "
    "and runs the same modeling suite against it. A local model first scans the columns for "
    "identifiers and asks you what to drop, mask, or keep — it runs on this machine and sends "
    "nothing anywhere. It reduces what reaches the language model; it does **not** make the data "
    "de-identified or safe to share, and on this hosted demo the file has already reached the "
    "server."
)
```

- [ ] **Step 2: Run the About copy tests**

Run: `.venv/bin/python -m pytest tests/test_about.py -v`
Expected: PASS. The disclosure test asserts `synthetic`, `no phi`, `read-only`, and `1,000 rows`
appear in `ABOUT_MD`; the wording above keeps the limits section intact, so they still do. **If it
fails, fix the copy, not the test** — those assertions are the point of the file.

- [ ] **Step 3: Add a RUNBOOK section**

Append to `RUNBOOK.md`, under the BYOD material:

```markdown
### On-device de-identification (uploads)

Scans an uploaded table for identifiers with a local ONNX model before anything reaches the LLM.

```bash
# Verify it is installed and working (downloads the 44M model on first run)
.venv/bin/python -c "
from agent import deid
print('available:', deid.available())
print(deid.scrub_values(['Patient John Doe, MRN 123456']))"
```

It is a **detector that informs your decision**, not a guarantee. OpenMed publishes no recall
figures for this model, so a clean scan is not an all-clear. To run fully offline, point the app at
a local model (`OPENAI_BASE_URL=http://localhost:11434/v1`) — only then does nothing leave the
machine.
```

- [ ] **Step 4: Add the reasoning to CONCEPTS.md**

Append verbatim:

```markdown
## Why de-identification is a detector, not a gate

The upload scanner uses a local ONNX model whose authors publish **no recall figures** — the model
card says to "evaluate recall, thresholds, and span behavior on appropriately governed data before
deployment," and that "local execution … does not by itself guarantee regulatory compliance."

That single fact determines the whole design. A gate that blocks on detection would turn every
*pass* into an all-clear the model cannot support, and one missed identifier is a disclosure. So the
scanner reports what it found and a human decides. The tool never says the data is clean; it says
what it saw.

The decision is deliberately **per column, not per cell**. Dropping a column is structurally
certain: the column is gone before the frame reaches DuckDB, so it cannot appear in the catalog's
example values or in any query result. That guarantee holds even if the model's recall is poor,
which is exactly the property a per-cell scrub lacks — masking depends on catching every instance.
Per-cell scrubbing is kept only as a second pass over what the user chose to keep.

The same caution governs the wording. Claiming "nothing left this machine" requires the language
model to actually be on this machine, so it is gated on a **loopback check** of `OPENAI_BASE_URL`
rather than on `llm._is_local()` — that helper is documented as true for "Ollama, LM Studio, vLLM,
a free-tier API", so a remote endpoint like Groq satisfies it and would make the claim false
precisely when it matters. Unset or non-loopback gets only the weaker line.
```

- [ ] **Step 5: Commit**

```bash
git add about.py RUNBOOK.md CONCEPTS.md
git commit -m "Document on-device de-identification and what it does not promise"
```

---

## Verification checklist

Before opening a PR:

- [ ] `.venv/bin/python -m pytest -q -p no:warnings` — full suite green, exit 0
- [ ] `.venv/bin/python -m ruff check .` — clean
- [ ] Drive the app live: upload a CSV containing obvious identifiers, confirm the panel appears, confirm Drop removes the column from the result, confirm Keep still scrubs the preview
- [ ] Confirm the demo-warehouse path is unchanged: run a question with no upload and check no model loads (the Task 4 test asserts this, but confirm the latency by eye)
- [ ] Confirm the app still starts with `openmed` uninstalled (`uv pip uninstall openmed`) and shows the unavailable caption
