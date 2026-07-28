"""Which column plays which statistical part.

This is the piece that decides whether the library works on your data or quietly does nothing.

Three layers, in order of trust:

  1. EXPLICIT   — you name the columns. Always wins, and an unknown name is an error rather than a
                  silent fallback, because "I ignored the argument you gave me" is the worst
                  possible behaviour for a tool whose job is to tell you what you missed.
  2. STRUCTURAL — inferred from the numbers themselves: a counts column bounded elementwise by a
                  larger counts column is a numerator inside a denominator, whatever the two are
                  called. This is what makes the library survive columns named `a`, `b`, `cnt`.
  3. NAMING     — regex over column names. Cheap and precise when names are disciplined
                  (`patients_with_condition`, `total_patients`), useless when they are not.

Naming runs before structure only because it is more specific: `total_patients` is evidence about
intent, whereas the structural rule can be satisfied by coincidence. Structure is the safety net.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field, replace

import numpy as np
import pandas as pd

DENOM_RE = re.compile(
    r"(total|denom|cohort|sample|population|_size|(^|_)n($|_)|num_patients|total_patients|"
    r"eligible|at_risk|exposed)", re.IGNORECASE)
NUMER_RE = re.compile(
    r"(patients_with|_with_|numerator|cases|events|readmit|readmiss|affected|positive|"
    r"successes|hits|deaths)", re.IGNORECASE)
RATE_RE = re.compile(r"(rate|pct|percent|prevalence|proportion|share|ratio|incidence)", re.IGNORECASE)
MEAN_RE = re.compile(r"(^avg_|_avg$|average|^mean_|_mean$|median)", re.IGNORECASE)
MEASURE_RE = re.compile(
    r"(cost|amount|charge|price|duration|minutes|value|income|expense|\blos\b|days_|"
    r"length|spend|revenue|latency|score)", re.IGNORECASE)
DISPERSION_RE = re.compile(r"(std|sd|median|iqr|p25|p75|min|max|var|stderr|se)", re.IGNORECASE)

_FIELDS = ("numerator", "denominator", "rate", "measure", "group", "stratifier")


@dataclass(frozen=True)
class Roles:
    """Column roles. Any field may be None, meaning "not identified"."""
    numerator: str | None = None      # count of events, per row
    denominator: str | None = None    # count at risk, per row
    rate: str | None = None           # a precomputed proportion or percentage
    measure: str | None = None        # a continuous quantity (cost, duration, score)
    group: str | None = None          # the primary categorical comparison axis
    stratifier: str | None = None     # a second categorical, for Simpson's-style checks
    source: dict = field(default_factory=dict)   # field -> "explicit" | "structural" | "naming"

    def as_dict(self) -> dict:
        return {f: getattr(self, f) for f in _FIELDS} | {"source": dict(self.source)}

    def identified(self) -> list[str]:
        return [f for f in _FIELDS if getattr(self, f) is not None]

    def __str__(self) -> str:
        if not self.identified():
            return "Roles(nothing identified)"
        return "Roles(" + ", ".join(
            f"{f}={getattr(self, f)!r}[{self.source.get(f, '?')}]" for f in self.identified()) + ")"


class UnknownColumn(ValueError):
    """An explicitly supplied role names a column that isn't in the frame."""


def _numeric(df) -> list[str]:
    return [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]


def _categorical(df) -> list[str]:
    return [c for c in df.columns if not pd.api.types.is_numeric_dtype(df[c])]


def _match(cols, rx) -> list[str]:
    return [c for c in cols if rx.search(str(c))]


def _count_like(df, col) -> bool:
    """Non-negative and whole-valued — a plausible count column whatever its dtype."""
    s = pd.to_numeric(df[col], errors="coerce").dropna()
    if s.empty or (s < 0).any():
        return False
    return bool(np.all(np.isclose(s % 1, 0)))


def _structural_counts(df) -> tuple[str | None, str | None]:
    """Find (numerator, denominator) from the numbers alone.

    A denominator contains its numerator: k[i] <= n[i] for every row, with n positive throughout.
    Among candidate pairs prefer the largest denominator total, which picks the population column
    over an intermediate subtotal. Requires at least one row where k < n, otherwise the two columns
    are duplicates rather than a part and a whole.
    """
    cols = [c for c in _numeric(df) if _count_like(df, c)]
    best, best_total = (None, None), -1.0
    for n_col in cols:
        n = pd.to_numeric(df[n_col], errors="coerce")
        if n.isna().any() or (n <= 0).any():
            continue
        for k_col in cols:
            if k_col == n_col:
                continue
            k = pd.to_numeric(df[k_col], errors="coerce")
            if k.isna().any() or (k > n).any() or not (k < n).any():
                continue
            total = float(n.sum())
            if total > best_total:
                best, best_total = (k_col, n_col), total
    return best


def _structural_rate(df, numerator, denominator) -> str | None:
    """A float column that reproduces numerator/denominator (as a fraction or a percentage)."""
    if not numerator or not denominator:
        return None
    k = pd.to_numeric(df[numerator], errors="coerce")
    n = pd.to_numeric(df[denominator], errors="coerce")
    with np.errstate(divide="ignore", invalid="ignore"):
        frac = (k / n).to_numpy(dtype=float)
    for c in _numeric(df):
        if c in (numerator, denominator):
            continue
        v = pd.to_numeric(df[c], errors="coerce").to_numpy(dtype=float)
        if np.allclose(v, frac, rtol=0.02, atol=1e-6, equal_nan=True) or \
           np.allclose(v, frac * 100, rtol=0.02, atol=1e-3, equal_nan=True):
            return c
    return None


def _pick_categoricals(df) -> tuple[str | None, str | None]:
    """Primary group and stratifier: the lowest-cardinality categoricals, most-repeated first.

    Cardinality beats column order — a stratifier with two levels is a better comparison axis than
    an id-like column that happens to appear first.
    """
    cats = [c for c in _categorical(df) if 2 <= df[c].nunique(dropna=True) <= max(2, len(df))]
    if not cats:
        return None, None
    ranked = sorted(cats, key=lambda c: (df[c].nunique(dropna=True), list(df.columns).index(c)))
    return (ranked[0], ranked[1] if len(ranked) > 1 else None)


def infer_roles(df: pd.DataFrame) -> Roles:
    """Best-effort roles from naming first, then structure for whatever naming missed."""
    if df is None or len(df) == 0:
        return Roles()
    num_cols, src = _numeric(df), {}

    numerator = next(iter(_match(num_cols, NUMER_RE)), None)
    denoms = [c for c in num_cols if DENOM_RE.search(str(c))]
    denominator = max(denoms, key=lambda c: df[c].sum()) if denoms else None
    if numerator:
        src["numerator"] = "naming"
    if denominator:
        src["denominator"] = "naming"

    # Structure fills whatever the names did not, and can supply the pair outright.
    if numerator is None or denominator is None:
        s_num, s_den = _structural_counts(df)
        if numerator is None and s_num:
            numerator, src["numerator"] = s_num, "structural"
        if denominator is None and s_den:
            denominator, src["denominator"] = s_den, "structural"

    # A denominator that turned out to be the numerator of record is not a denominator.
    if numerator and denominator and numerator == denominator:
        denominator = None
        src.pop("denominator", None)

    rate = next(iter(_match(num_cols, RATE_RE)), None)
    if rate:
        src["rate"] = "naming"
    else:
        rate = _structural_rate(df, numerator, denominator)
        if rate:
            src["rate"] = "structural"

    measure = next((c for c in num_cols
                    if MEASURE_RE.search(str(c))
                    and not DENOM_RE.search(str(c)) and not RATE_RE.search(str(c))), None)
    if measure:
        src["measure"] = "naming"

    group, stratifier = _pick_categoricals(df)
    if group:
        src["group"] = "structural"
    if stratifier:
        src["stratifier"] = "structural"

    return Roles(numerator=numerator, denominator=denominator, rate=rate, measure=measure,
                 group=group, stratifier=stratifier, source=src)


def resolve(df: pd.DataFrame, explicit: Roles | dict | None = None) -> Roles:
    """Merge caller-supplied roles over inferred ones.

    Raises UnknownColumn if an explicit role names a column that isn't there — passing
    `denominator="total"` and getting silence would be worse than getting nothing at all.
    """
    inferred = infer_roles(df)
    if not explicit:
        return inferred
    given = explicit.as_dict() if isinstance(explicit, Roles) else dict(explicit)
    given.pop("source", None)
    given = {k: v for k, v in given.items() if v is not None}

    unknown = {k: v for k, v in given.items() if k in _FIELDS and v not in df.columns}
    if unknown:
        raise UnknownColumn(
            "these roles name columns that are not in the frame: "
            + ", ".join(f"{k}={v!r}" for k, v in sorted(unknown.items()))
            + f". Available: {list(df.columns)}")
    bad = sorted(set(given) - set(_FIELDS))
    if bad:
        raise UnknownColumn(f"unknown role(s): {bad}. Valid roles: {list(_FIELDS)}")

    src = dict(inferred.source) | {k: "explicit" for k in given}
    return replace(inferred, **given, source=src)
