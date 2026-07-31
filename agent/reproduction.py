"""Published-design parsing and deterministic decision reproduction.

The language model extracts an explicit statistical design. It never performs
the calculation. The validated design is then passed to the existing exact
beta-binomial engine.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from typing import Any

from scipy import stats

from . import bayes, llm

SUPPORTED_ENDPOINT = "single_arm_binary"

_FIELDS = (
    "publication_title",
    "doi",
    "endpoint_type",
    "observed_successes",
    "observed_n",
    "planned_n",
    "prior_a",
    "prior_b",
    "efficacy_reference",
    "efficacy_gate",
    "futility_cutoff",
    "published_predictive_probability",
    "published_final_boundary",
    "published_decision",
)

_REQUIRED_COMPUTATION_FIELDS = (
    "observed_successes",
    "observed_n",
    "planned_n",
    "prior_a",
    "prior_b",
    "efficacy_reference",
    "efficacy_gate",
    "futility_cutoff",
)

_PARSER_SYSTEM = """You extract a published Bayesian interim design into JSON.

Scope: single-arm studies with a binary endpoint and a beta-binomial model.
Do not calculate, reconstruct, or guess any value. Use null when the supplied
text does not state a value. Do not insert conventional clinical-trial defaults.

Return exactly these keys:
{
  "publication_title": string|null,
  "doi": string|null,
  "endpoint_type": "single_arm_binary"|null,
  "observed_successes": integer|null,
  "observed_n": integer|null,
  "planned_n": integer|null,
  "prior_a": number|null,
  "prior_b": number|null,
  "efficacy_reference": number|null,
  "efficacy_gate": number|null,
  "futility_cutoff": number|null,
  "published_predictive_probability": number|null,
  "published_final_boundary": integer|null,
  "published_decision": "STOP"|"CONSIDER"|"GO"|null
}

Definitions:
- efficacy_reference is the response rate in a final rule such as
  P(response rate > efficacy_reference | final data) > efficacy_gate.
- efficacy_gate is that final posterior-probability threshold.
- futility_cutoff is the interim predictive-probability threshold for stopping.
- published_final_boundary is the minimum total final successes required.
- Normalize stated percentages to proportions from 0 to 1.
- Extract only information present in the supplied text. A DOI alone is not
  evidence for any design value.
"""


def parse_published_design(text: str) -> dict[str, Any]:
    """Extract a reproduction specification from user-supplied prose."""
    source = (text or "").strip()
    if len(source) < 40:
        raise ValueError("Paste enough design text to identify the interim and final rules.")

    raw = llm.complete_json(_PARSER_SYSTEM, source, temperature=0)
    if not isinstance(raw, dict):
        raise ValueError("The design parser did not return a structured result.")

    spec = {field: raw.get(field) for field in _FIELDS}
    spec["endpoint_type"] = _clean_text(spec.get("endpoint_type"))
    spec["publication_title"] = _clean_text(spec.get("publication_title"))
    spec["doi"] = normalize_doi(spec.get("doi"))
    spec["published_decision"] = _clean_decision(spec.get("published_decision"))

    for field in ("observed_successes", "observed_n", "planned_n", "published_final_boundary"):
        spec[field] = _coerce_optional_integer(spec.get(field), field)
    for field in ("prior_a", "prior_b"):
        spec[field] = _coerce_optional_float(spec.get(field), field)
    for field in (
        "efficacy_reference",
        "efficacy_gate",
        "futility_cutoff",
        "published_predictive_probability",
    ):
        spec[field] = _coerce_optional_probability(spec.get(field), field)

    spec["missing_fields"] = [
        field for field in _REQUIRED_COMPUTATION_FIELDS if spec.get(field) is None
    ]
    return spec


def validate_reproduction_spec(spec: dict[str, Any]) -> dict[str, Any]:
    """Normalize and validate a user-confirmed reproduction specification."""
    normalized = {field: spec.get(field) for field in _FIELDS}
    normalized["publication_title"] = _clean_text(normalized.get("publication_title"))
    normalized["doi"] = normalize_doi(normalized.get("doi"))
    normalized["endpoint_type"] = _clean_text(normalized.get("endpoint_type"))
    normalized["published_decision"] = _clean_decision(normalized.get("published_decision"))

    if normalized["endpoint_type"] != SUPPORTED_ENDPOINT:
        raise ValueError(
            "This workflow currently supports only a single-arm binary beta-binomial design."
        )

    for field in ("observed_successes", "observed_n", "planned_n"):
        normalized[field] = _coerce_required_integer(normalized.get(field), field)
    normalized["published_final_boundary"] = _coerce_optional_integer(
        normalized.get("published_final_boundary"), "published_final_boundary"
    )

    for field in ("prior_a", "prior_b"):
        normalized[field] = _coerce_required_float(normalized.get(field), field)
    for field in ("efficacy_reference", "efficacy_gate", "futility_cutoff"):
        normalized[field] = _coerce_required_probability(normalized.get(field), field)
    normalized["published_predictive_probability"] = _coerce_optional_probability(
        normalized.get("published_predictive_probability"),
        "published_predictive_probability",
    )

    successes = normalized["observed_successes"]
    observed_n = normalized["observed_n"]
    planned_n = normalized["planned_n"]
    if observed_n <= 0:
        raise ValueError("Observed sample size must be greater than zero.")
    if not 0 <= successes <= observed_n:
        raise ValueError("Observed successes must be between zero and the observed sample size.")
    if planned_n <= observed_n:
        raise ValueError("Planned sample size must be greater than the interim sample size.")
    if planned_n - observed_n > bayes.MAX_ENUM:
        raise ValueError(
            f"The exact reproduction workflow supports at most {bayes.MAX_ENUM:,} remaining subjects."
        )
    if normalized["prior_a"] <= 0 or normalized["prior_b"] <= 0:
        raise ValueError("Beta prior parameters must be greater than zero.")

    boundary = normalized["published_final_boundary"]
    if boundary is not None and not 0 <= boundary <= planned_n:
        raise ValueError("Published final boundary must be between zero and planned N.")

    normalized["missing_fields"] = []
    return normalized


def run_reproduction(spec: dict[str, Any], tolerance: float = 0.001) -> dict[str, Any]:
    """Run a confirmed design through the exact deterministic engine."""
    if tolerance <= 0:
        raise ValueError("Comparison tolerance must be greater than zero.")
    resolved = validate_reproduction_spec(spec)

    successes = resolved["observed_successes"]
    observed_n = resolved["observed_n"]
    planned_n = resolved["planned_n"]
    prior_a = resolved["prior_a"]
    prior_b = resolved["prior_b"]
    reference = resolved["efficacy_reference"]
    gate = resolved["efficacy_gate"]
    futility = resolved["futility_cutoff"]

    prior = bayes.Prior(
        "Confirmed publication prior",
        "beta",
        (prior_a, prior_b),
        f"User-confirmed Beta({prior_a:g},{prior_b:g}) prior.",
    )
    rule = bayes.DecisionRule(
        tv=reference,
        lrv=reference,
        gate_tv=gate,
        gate_lrv=gate,
        stop_lrv=futility,
    )
    predictive_probability = float(
        bayes.predictive_prob_success(prior, successes, observed_n, planned_n, rule)
    )
    final_grid = bayes.go_grid_binary(prior, planned_n, rule)
    successful_totals = [total for total, is_success in enumerate(final_grid) if is_success]
    final_boundary = min(successful_totals) if successful_totals else None
    post_a, post_b = bayes.beta_posterior(prior_a, prior_b, successes, observed_n)
    posterior_probability = float(
        bayes.prob_exceeds("beta", post_a, post_b, reference, True)
    )
    posterior_mean = float(post_a / (post_a + post_b))
    credible_interval = [float(value) for value in stats.beta.ppf([0.025, 0.975], post_a, post_b)]
    computed_decision, _ = bayes.decide(
        posterior_probability,
        posterior_probability,
        rule,
    )
    if predictive_probability < futility:
        computed_decision = "STOP"

    published_probability = resolved["published_predictive_probability"]
    published_boundary = resolved["published_final_boundary"]
    published_decision = resolved["published_decision"]

    comparisons = [
        _comparison(
            "Predictive probability",
            predictive_probability,
            published_probability,
            tolerance=tolerance,
        ),
        _comparison("Final boundary", final_boundary, published_boundary, exact=True),
        _comparison("Interim decision", computed_decision, published_decision, exact=True),
    ]
    assessed = [row["match"] for row in comparisons if row["match"] is not None]
    overall_match = all(assessed) if assessed else None

    output = {
        "computed": {
            "predictive_probability": predictive_probability,
            "final_boundary": final_boundary,
            "responses_needed": (
                max(0, final_boundary - successes) if final_boundary is not None else None
            ),
            "decision": computed_decision,
            "posterior_mean": posterior_mean,
            "credible_interval": credible_interval,
            "posterior_probability_above_reference": posterior_probability,
        },
        "comparisons": comparisons,
        "overall_match": overall_match,
        "tolerance": tolerance,
        "resolved_design": resolved,
        "engine": "exact beta-binomial enumeration",
    }
    canonical = json.dumps(output, sort_keys=True, separators=(",", ":"), default=str)
    output["audit_fingerprint"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return output


def normalize_doi(value: Any) -> str | None:
    """Return a canonical DOI string, or None if absent."""
    text = _clean_text(value)
    if not text:
        return None
    text = re.sub(r"^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)", "", text, flags=re.I)
    return text.strip() or None


def doi_url(doi: Any) -> str | None:
    """Create a safe DOI link for a DOI-shaped identifier."""
    canonical = normalize_doi(doi)
    if not canonical or not re.fullmatch(r"10\.\d{4,9}/[-._;()/:A-Z0-9]+", canonical, re.I):
        return None
    return f"https://doi.org/{canonical}"


def _comparison(
    metric: str,
    computed: Any,
    published: Any,
    *,
    tolerance: float | None = None,
    exact: bool = False,
) -> dict[str, Any]:
    if published is None:
        return {"metric": metric, "computed": computed, "published": None, "match": None}
    if exact:
        matches = computed == published
    else:
        matches = math.isclose(float(computed), float(published), abs_tol=float(tolerance or 0))
    return {
        "metric": metric,
        "computed": computed,
        "published": published,
        "match": bool(matches),
    }


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _clean_decision(value: Any) -> str | None:
    text = _clean_text(value)
    if not text:
        return None
    decision = text.upper()
    return decision if decision in {"STOP", "CONSIDER", "GO"} else None


def _coerce_optional_float(value: Any, field: str) -> float | None:
    if value is None or str(value).strip() == "":
        return None
    try:
        number = float(str(value).strip())
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be numeric.") from exc
    if not math.isfinite(number):
        raise ValueError(f"{field} must be finite.")
    return number


def _coerce_required_float(value: Any, field: str) -> float:
    number = _coerce_optional_float(value, field)
    if number is None:
        raise ValueError(f"{field} is required.")
    return number


def _coerce_optional_integer(value: Any, field: str) -> int | None:
    number = _coerce_optional_float(value, field)
    if number is None:
        return None
    if not number.is_integer():
        raise ValueError(f"{field} must be a whole number.")
    return int(number)


def _coerce_required_integer(value: Any, field: str) -> int:
    number = _coerce_optional_integer(value, field)
    if number is None:
        raise ValueError(f"{field} is required.")
    return number


def _coerce_optional_probability(value: Any, field: str) -> float | None:
    if value is None or str(value).strip() == "":
        return None
    text = str(value).strip()
    is_percent = text.endswith("%")
    if is_percent:
        text = text[:-1].strip()
    try:
        number = float(text)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be a probability or percentage.") from exc
    if is_percent or 1 < number <= 100:
        number /= 100
    if not math.isfinite(number) or not 0 <= number <= 1:
        raise ValueError(f"{field} must be between 0 and 1.")
    return number


def _coerce_required_probability(value: Any, field: str) -> float:
    number = _coerce_optional_probability(value, field)
    if number is None:
        raise ValueError(f"{field} is required.")
    return number
