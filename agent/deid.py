"""On-device PII/PHI detection for uploaded data, via OpenMed's local ONNX models.

The ONLY module that imports `openmed`. No Streamlit import, so it is testable headless.

This is a DETECTOR that informs a human decision, never a gate that certifies data. OpenMed's
model card publishes no recall figures and states that local execution does not by itself
guarantee regulatory compliance, so a clean scan must never be presented as an all-clear. See
docs/superpowers/specs/2026-08-11-byod-deidentification-design.md.

Every function fails OPEN: if the model is unavailable the caller still works, unscrubbed, and
the UI is responsible for saying so. A silent no-op would be worse than no feature at all.

Inference goes through `OnnxModel`, NOT `openmed.deidentify()` / `extract_pii()`. Those exist as
symbols but raise `ImportError: HuggingFace transformers is required` at call time, and
transformers pulls torch (111 MB) for a job that is pure ONNX inference. Verified by installing
`openmed[onnx-runtime]` and calling both.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from urllib.parse import urlparse

import pandas as pd

log = logging.getLogger(__name__)

MODEL_ID = "OpenMed/OpenMed-PII-SuperClinical-Small-44M-v1-onnx-android"
REDACTION = "[REDACTED]"

# Bias toward RECALL. A false positive costs the user one unnecessary question about a column; a
# miss is a disclosure. Measured: "Mass General" scored 0.485, so a 0.5 cut would already drop a
# real identifier.
SCORE_THRESHOLD = 0.35

# At/above this share of sampled values carrying an identifier, the column IS identifiers and the
# suggested action becomes "drop" — structurally certain, rather than trusting per-cell recall.
DROP_THRESHOLD = 0.8

# Quasi-identifiers: attributes that raise re-identification risk IN COMBINATION but are not
# direct identifiers on their own, and which are load-bearing covariates for this agent.
#
# `age` is the case that forced this. Under HIPAA Safe Harbor an age is an identifier only above
# 89, but the model flags every age — and a real scan of ages 41/52/63 suggested dropping the
# column. Age is the most common covariate in the modeling suite ("adjusting for age and sex",
# every Cox model), so a default of drop would gut the analysis the feature exists to enable.
# These are surfaced to the user, but default to KEEP.
QUASI_LABELS = frozenset({
    "age", "gender", "sex", "race", "ethnicity", "religion", "religious_belief", "sexuality",
    "sexual_orientation", "marital_status", "nationality", "language",
})

# Loading the ONNX model takes ~12s (6 files from HF Hub on first use), so it is cached here.
# _LOAD_FAILED latches: without it, a 60-column scan would retry a 12s failing load per value.
_MODEL = None
_LOAD_FAILED = False


@dataclass
class ColumnFinding:
    """One flagged column. `examples` are REDACTED previews — never echo a raw identifier."""
    column: str
    entity_types: list[str] = field(default_factory=list)
    hit_rate: float = 0.0
    examples: list[str] = field(default_factory=list)
    suggested: str = "mask"          # "drop" | "mask" | "keep"
    severity: str = "direct"         # "direct" | "quasi"


def _merge_spans(spans: list[tuple[int, int, str]]) -> list[tuple[int, int]]:
    """Collapse adjacent and overlapping spans into single ranges.

    The real model emits `first_name` and `last_name` as separate touching spans, which produced
    `[REDACTED][REDACTED]` for one name; overlapping spans on an MRN produced
    `[REDACTED]RN[REDACTED]`, leaving a fragment of the identifier in the clear. Merging first
    means one redaction per contiguous run, with nothing left between.
    """
    if not spans:
        return []
    ordered = sorted((s, e) for s, e, _label in spans)
    merged = [ordered[0]]
    for start, end in ordered[1:]:
        last_start, last_end = merged[-1]
        if start <= last_end:                 # touching (==) or overlapping (<)
            merged[-1] = (last_start, max(last_end, end))
        else:
            merged.append((start, end))
    return merged


def _load_model():
    """Load the ONNX model. Separate from _model() so tests can monkeypatch just the load."""
    import openmed
    return openmed.OnnxModel.from_pretrained(MODEL_ID)


def _model():
    """The cached model, or None. Never raises — a missing model must not break an upload."""
    global _MODEL, _LOAD_FAILED
    if _MODEL is not None:
        return _MODEL
    if _LOAD_FAILED:
        return None
    try:
        _MODEL = _load_model()
    except Exception as exc:  # noqa: BLE001
        log.info("de-identification model unavailable: %s", exc)
        _LOAD_FAILED = True
        return None
    return _MODEL


def available() -> bool:
    return _model() is not None


def _spans(text: str) -> list[tuple[int, int, str]]:
    """(start, end, label) for entities above the threshold. Empty on any failure."""
    m = _model()
    if m is None:
        return []
    try:
        return [(e.start, e.end, e.label) for e in m(text)
                if getattr(e, "score", 1.0) >= SCORE_THRESHOLD]
    except Exception as exc:  # noqa: BLE001
        log.warning("detection failed for one value: %s", exc)
        return []


def scrub_values(values: list[str]) -> list[str]:
    """Mask detected identifiers in each string. Returns the input unchanged if unavailable."""
    if _model() is None:
        return list(values)
    out = []
    for v in values:
        text = str(v)
        try:
            # Merge first (adjacent/overlapping spans would otherwise leave fragments), then
            # replace from the END so an earlier substitution can't shift later offsets.
            for start, end in sorted(_merge_spans(_spans(text)), reverse=True):
                text = text[:start] + REDACTION + text[end:]
            out.append(text)
        except Exception as exc:  # noqa: BLE001
            log.warning("scrub failed for one value: %s", exc)
            out.append(REDACTION)      # fail CLOSED per value: an unscrubbable value is redacted
    return out


def scan_columns(df: pd.DataFrame, sample: int = 20) -> list[ColumnFinding]:
    """Sample each column and report which look like they hold identifiers.

    Sampling, not exhaustive: the frame can be 12M cells and never leaves the machine, so the
    scan exists to inform a per-COLUMN decision, not to find every cell. That structural framing
    is what keeps the feature honest despite the model's unpublished recall.
    """
    if _model() is None:
        return []
    findings: list[ColumnFinding] = []
    for col in df.columns:
        values = [str(v) for v in df[col].dropna().unique()[:sample]]
        if not values:
            continue
        labels, hits = [], 0
        for v in values:
            found = [label for _s, _e, label in _spans(v)]
            if found:
                hits += 1
                labels.extend(found)
        if not hits:
            continue
        rate = hits / len(values)
        kinds = sorted(set(labels))
        # "direct" if ANY label is a direct identifier: a notes column holding both an age and a
        # name must not be softened to quasi just because one of its labels is demographic.
        severity = "quasi" if all(k in QUASI_LABELS for k in kinds) else "direct"
        if severity == "quasi":
            suggested = "keep"                          # see QUASI_LABELS — dropping guts analysis
        else:
            suggested = "drop" if rate >= DROP_THRESHOLD else "mask"
        findings.append(ColumnFinding(
            column=str(col),
            entity_types=kinds,
            hit_rate=rate,
            examples=scrub_values(values[:3]),          # redacted previews only
            suggested=suggested,
            severity=severity,
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
