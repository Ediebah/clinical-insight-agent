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
from dataclasses import dataclass, field

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
    suggested: str = "mask"          # "drop" | "mask"


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
            # Replace from the END so an earlier substitution can't shift later offsets.
            for start, end, _label in sorted(_spans(text), key=lambda s: s[0], reverse=True):
                text = text[:start] + REDACTION + text[end:]
            out.append(text)
        except Exception as exc:  # noqa: BLE001
            log.warning("scrub failed for one value: %s", exc)
            out.append(REDACTION)      # fail CLOSED per value: an unscrubbable value is redacted
    return out
