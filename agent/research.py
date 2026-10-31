"""Explicit exploratory analysis specifications and portable, data-free audit bundles."""
from __future__ import annotations

import hashlib
import importlib.metadata
import json
import math
import re
from dataclasses import fields
from pathlib import Path
from typing import Protocol

import numpy as np
import pandas as pd

from . import modeling
from .research_rules import require_bayesian_inputs

SCHEMA_VERSION = "1.0"
METHODS = frozenset({"logistic", "ols", "survival", "cox", "association", "forest", "best_model",
                     "survival_ml", "decision_curve", "failure_analysis", "timeseries", "causal",
                     "experiment", "noninferiority", "interim", "sample_size", "assurance"})
ALIASES = {"compare": "best_model", "compare_models": "best_model", "rsf": "survival_ml"}
FIELDS = ("schema_version", "question", "population", "outcome", "predictors", "method", "assumptions",
          "exclusions", "data_source", "sql", "parameters")


def from_route(question: str, route: dict, data_source: str) -> dict:
    method = ALIASES.get(route.get("model_type"), route.get("model_type"))
    parameters = {k: v for k, v in route.items()
                  if k not in {"model_type", "outcome", "predictors", "analytic_sql"}}
    if method in {"survival", "cox", "survival_ml"}:
        parameters.pop("event", None)
    if method == "association":
        parameters.pop("var_b", None)
    if method == "timeseries":
        parameters.pop("value_col", None)
    if method in {"assurance", "interim"}:
        # The model may return illustrative values from its prompt. Keep numerical values only if the
        # question contains the number; this is a necessary check, not proof of correct attribution.
        numbers = set()
        for match in re.finditer(r"(?<![\w.])-?(?:\d+(?:\.\d+)?|\.\d+)\s*%?", question):
            token = match.group().strip()
            value = float(token.rstrip("%").strip())
            numbers.add(value / 100 if token.endswith("%") else value)
        for key in ("n_planned", "tv", "lrv", "gate_tv", "gate_lrv", "stop_lrv", "prior_successes",
                    "prior_n", "prior_a", "prior_b", "prior_mu", "prior_sd", "sd", "control_rate"):
            value = parameters.get(key)
            if value is not None:
                try:
                    numeric = float(value) if not isinstance(value, bool) else float("nan")
                except (TypeError, ValueError):
                    numeric = float("nan")
                if not math.isfinite(numeric) or not any(
                        math.isclose(numeric, n, rel_tol=1e-9, abs_tol=1e-9) for n in numbers):
                    parameters[key] = None
    return {"schema_version": SCHEMA_VERSION, "question": question,
            "population": "Population selected by the SQL; review the query.",
            "outcome": route.get("event") if method in {"survival", "cox", "survival_ml"} else
                       (route.get("var_b") if method == "association" else
                        (route.get("value_col") if method == "timeseries" else route.get("outcome"))) or "",
            "predictors": route.get("predictors") or [], "method": method,
            "assumptions": ["Exploratory analysis; review method assumptions."],
            "exclusions": [], "data_source": data_source, "sql": route.get("analytic_sql") or "",
            "parameters": parameters}


def validate_spec(spec: dict) -> None:
    if not isinstance(spec, dict):
        raise ValueError("specification must be an object")
    missing = [k for k in FIELDS if k not in spec]
    if missing:
        raise ValueError("missing specification fields: " + ", ".join(missing))
    if spec["schema_version"] != SCHEMA_VERSION:
        raise ValueError("unsupported specification version")
    if spec["method"] not in METHODS:
        raise ValueError(f"unsupported method: {spec['method']}")
    for key in ("question", "population", "data_source"):
        if not isinstance(spec[key], str) or not spec[key].strip():
            raise ValueError(f"{key} must be a non-empty description")
    if not isinstance(spec["outcome"], str) or (spec["method"] not in {"assurance", "sample_size"}
                                                and not spec["outcome"].strip()):
        raise ValueError("outcome must identify the analysis endpoint")
    for key in ("predictors", "assumptions", "exclusions"):
        if not isinstance(spec[key], list) or any(not isinstance(v, str) for v in spec[key]):
            raise ValueError(f"{key} must be a list of strings")
    if not isinstance(spec["parameters"], dict) or not isinstance(spec["sql"], str):
        raise ValueError("parameters must be an object and sql must be text")
    alias = "event" if spec["method"] in {"survival", "cox", "survival_ml"} else \
        ("var_b" if spec["method"] == "association" else ("value_col" if spec["method"] == "timeseries" else None))
    if alias and alias in spec["parameters"] and spec["parameters"][alias] != spec["outcome"]:
        raise ValueError(f"{alias} conflicts with the canonical outcome field")


class DataAdapter(Protocol):
    def read(self) -> pd.DataFrame:
        """Return the approved analysis data without modifying the source."""


class DataFrameAdapter:
    def __init__(self, frame: pd.DataFrame):
        self.frame = frame

    def read(self) -> pd.DataFrame:
        return self.frame.copy(deep=True)


class DuckDBAdapter:
    def __init__(self, path: str | Path, sql: str, max_rows: int = 100_000):
        self.path, self.sql, self.max_rows = Path(path), sql, max_rows

    def read(self) -> pd.DataFrame:
        from .warehouse import run_query
        frame = run_query(self.sql, max_rows=self.max_rows, db_path=self.path)
        if frame.attrs.get("truncated"):
            raise ValueError("The cohort is truncated; narrow it before analysis")
        return frame


def run_spec(spec: dict, frame: pd.DataFrame, *, approved: bool = False,
             source_identity: str = "in-memory dataframe") -> modeling.ModelResult:
    validate_spec(spec)
    if not approved:
        raise ValueError("explicit approval is required before analysis")
    if spec["sql"].strip():
        raise ValueError("SQL is not applied to in-memory data; supply an already selected cohort with empty SQL")
    if spec["population"].strip().lower() != "all rows" or spec["exclusions"]:
        raise ValueError("The direct analysis cannot apply cohort restrictions or exclusions; "
                         "provide the already selected data and specify population as 'all rows'.")
    if spec["data_source"] != source_identity:
        raise ValueError("The specification data source does not match the supplied data source identity.")
    if frame.attrs.get("truncated"):
        raise ValueError("The cohort is truncated; narrow it before analysis")
    from .agent import _fit_model
    route = dict(spec["parameters"])
    route.update(model_type=spec["method"], outcome=spec["outcome"], predictors=spec["predictors"])
    if spec["method"] in {"survival", "cox", "survival_ml"}:
        route["event"] = spec["outcome"]
    if spec["method"] == "association":
        route["var_b"] = spec["outcome"]
    if spec["method"] == "timeseries":
        route["value_col"] = spec["outcome"]
    if spec["method"] == "sample_size":
        return modeling.calc_sample_size(**spec["parameters"])
    if spec["method"] == "assurance":
        require_bayesian_inputs(spec["parameters"])
        return modeling.calc_assurance(**spec["parameters"])
    return _fit_model(route, frame)


def _json_safe(value):
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    if isinstance(value, (float, np.floating)) and not math.isfinite(value):
        return None
    if isinstance(value, np.generic):
        return value.item()
    return value


def _digest(value: dict) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     allow_nan=False).encode()).hexdigest()


_SECRET = re.compile(r"(?i)\b(?:api[_-]?key|password|secret|access[_-]?token)\s*[=:]\s*['\"]?\S+|"
                     r"\bbearer\s+[a-z0-9._-]+|\bsk-[a-z0-9_-]{12,}")
_OMIT_KEYS = re.compile(r"(?i)^(?:rows|records|dataframe|raw_data|api_key|password|secret|access_token)$")


def _without_private_fields(value):
    if isinstance(value, dict):
        return {k: _without_private_fields(v) for k, v in value.items() if not _OMIT_KEYS.match(str(k))}
    if isinstance(value, list):
        return [_without_private_fields(v) for v in value]
    return value


def _contains_private_fields(value) -> bool:
    if isinstance(value, dict):
        return any(_OMIT_KEYS.match(str(k)) or _contains_private_fields(v) for k, v in value.items())
    if isinstance(value, list):
        return any(_contains_private_fields(v) for v in value)
    return False


def make_bundle(spec: dict, result: dict, *, frame: pd.DataFrame | None = None,
                interpretation: str | None = None) -> dict:
    validate_spec(spec)
    if _contains_private_fields(spec):
        raise ValueError("Raw record or credential fields are not permitted in the specification.")
    if _SECRET.search(json.dumps(spec)) or (interpretation and _SECRET.search(interpretation)):
        raise ValueError("Possible secret detected in specification or interpretation; remove it before export.")
    versions = {}
    for name in ("numpy", "pandas", "scipy", "scikit-learn", "statsmodels", "duckdb"):
        try:
            versions[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            pass
    root = Path(__file__).resolve().parent.parent
    sources = sorted((root / "agent").glob("*.py"))
    sources += sorted((root / "packages").glob("*/src/*/*.py"))
    sources += sorted((root / "warehouse" / "models").rglob("*.sql"))
    sources += sorted((root / "warehouse" / "models").rglob("*.yml"))
    sources += [root / name for name in ("app.py", "about.py", "requirements.txt") if (root / name).exists()]
    manifest = {str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest() for path in sources}
    data_hash = None
    if frame is not None:
        h = hashlib.sha256()
        h.update(json.dumps(list(map(str, frame.columns))).encode())
        h.update(pd.util.hash_pandas_object(frame, index=True).values.tobytes())
        data_hash = h.hexdigest()
    allowed = {f.name for f in fields(modeling.ModelResult)}
    safe_result = _without_private_fields({k: v for k, v in result.items() if k in allowed})
    if safe_result.get("model_type") == "timeseries":
        safe_result["series"] = [row for row in safe_result.get("series", [])
                                 if isinstance(row, dict) and row.get("kind") == "forecast"]
    if _SECRET.search(json.dumps(safe_result, default=str)):
        raise ValueError("Possible secret detected in result; remove it before export.")
    bundle = _json_safe({"bundle_version": "1.0", "specification": spec,
                         "data_fingerprint": {"sha256": data_hash, "rows": None if frame is None else len(frame)},
                         "code_fingerprint": {"manifest_sha256": _digest(manifest), "files": manifest},
                         "software_versions": versions,
                         "result": safe_result, "llm_interpretation": interpretation,
                         "limitations": "Research only. Fingerprints establish neither validation nor prior timing. "
                                        "Model-generated text may vary. Raw source records are not included."})
    bundle["sha256"] = _digest(bundle)
    return bundle


def verify_bundle(bundle: dict) -> bool:
    return isinstance(bundle, dict) and isinstance(bundle.get("sha256"), str) and \
        bundle["sha256"] == _digest({k: v for k, v in bundle.items() if k != "sha256"})
