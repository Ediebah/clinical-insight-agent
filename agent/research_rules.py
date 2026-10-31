"""Lightweight validation shared by key-free entry points."""
import math
import numbers


def require_bayesian_inputs(params: dict, *, require_prior: bool = True) -> None:
    for key in ("tv", "lrv", "n_planned", "n", "control_rate"):
        if params.get(key) is None:
            continue
        try:
            value = float(params[key])
        except (ValueError, TypeError):
            raise ValueError(f"{key} must be a finite number") from None
        if not math.isfinite(value):
            raise ValueError(f"{key} must be a finite number")
        if key in {"n_planned", "n"} and (value <= 0 or not value.is_integer()):
            raise ValueError(f"{key} must be a positive integer")
        if key == "control_rate" and not 0 <= value <= 1:
            raise ValueError("control_rate must be a probability between 0 and 1")
    missing = [k for k in ("gate_tv", "gate_lrv", "stop_lrv") if params.get(k) is None]
    if missing:
        raise ValueError("Explicit decision thresholds required: " + ", ".join(missing))
    for key in ("gate_tv", "gate_lrv", "stop_lrv"):
        try:
            value = float(params[key])
        except (ValueError, TypeError):
            raise ValueError(f"{key} must be a probability between 0 and 1") from None
        if not math.isfinite(value) or not 0 <= value <= 1:
            raise ValueError(f"{key} must be a probability between 0 and 1")
    endpoint = params.get("endpoint_type", params.get("endpoint", "proportion"))
    if endpoint not in ("proportion", "mean"):
        raise ValueError("Unsupported Bayesian endpoint type")
    if params.get("endpoint") is not None and params.get("endpoint_type") is not None and \
            params["endpoint"] != params["endpoint_type"]:
        raise ValueError("Conflicting Bayesian endpoint types")
    pairs = (("prior_a", "prior_b"), ("prior_successes", "prior_n"), ("prior_mu", "prior_sd"))
    present = [pair for pair in pairs if any(params.get(k) is not None for k in pair)]
    if not present and not require_prior:
        return
    allowed = pairs[:2] if endpoint == "proportion" else pairs[2:]
    if len(present) != 1 or present[0] not in allowed or any(params.get(k) is None for k in present[0]):
        raise ValueError("Supply one complete prior compatible with the endpoint; conflicting or unused prior inputs are not allowed.")
    try:
        a, b = (float(params[k]) for k in present[0])
    except (ValueError, TypeError):
        raise ValueError("Prior parameters must be finite numbers") from None
    if not math.isfinite(a) or not math.isfinite(b):
        raise ValueError("Prior parameters must be finite numbers")
    if present[0] == pairs[0] and (a <= 0 or b <= 0):
        raise ValueError("Beta prior parameters must be positive")
    if present[0] == pairs[1] and (a < 0 or b <= 0 or a > b or not a.is_integer() or not b.is_integer()):
        raise ValueError("Prior study counts must be integers with 0 <= successes <= n and n > 0")
    if present[0] == pairs[2] and b <= 0:
        raise ValueError("Normal prior standard deviation must be positive")


def json_safe(value):
    if isinstance(value, dict):
        return {str(k): json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(v) for v in value]
    if isinstance(value, bool):
        return value
    if isinstance(value, numbers.Integral):
        return int(value)
    if isinstance(value, numbers.Real):
        return float(value) if math.isfinite(value) else None
    return value
