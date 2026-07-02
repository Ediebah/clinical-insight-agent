"""Industry-grade visualization: KPI cards + an annotated, story-telling chart.

Deterministic (no LLM) so the visualization is reliable. From the result's shape we produce:
  * kpi_cards(df)  — 1-3 headline metric cards (the extremes + spread) for instant reading.
  * build_chart(df) — a layered Altair chart: sorted bars, direct value labels, the extreme
                      highlighted, and — the differentiator — Wilson 95% CI error bars whenever the
                      result carries a numerator + denominator, so uncertainty is shown, not hidden.

Themed to the clinical-teal palette.
"""
from __future__ import annotations

import re

import altair as alt
import numpy as np
import pandas as pd

from .guardrails import wilson_ci

TEAL = "#4fd1c5"
TEAL_HI = "#8af7ea"
TEAL_DIM = "#2c6f68"
MUTED = "#8ea0b0"
GRID = "#1a2531"
DOMAIN = "#20303f"
INK = "#cfe0ec"

_TIERS = [
    re.compile(r"(rate|pct|percent|prevalence|proportion|ratio)", re.I),
    re.compile(r"(avg|mean|median)", re.I),
    re.compile(r"(cost|amount|charge|price|expense|income|revenue)", re.I),
    re.compile(r"(count|num|total|sum|_n$|^n$)", re.I),
]
_ID = re.compile(r"(_id$|^id$|code$|zip|latitude|longitude|_seq$)", re.I)
_TIME = re.compile(r"(date|year|month|day|_at$|start|stop|time)", re.I)
_NUMER = re.compile(r"(patients_with|_with_|numerator|cases|events|readmit|readmiss|affected|positive)", re.I)
_DENOM = re.compile(r"(total|denom|cohort|sample|population|_size|(^|_)n($|_)|num_patients|total_patients)", re.I)
_PCTISH = re.compile(r"(pct|percent|rate|prevalence|proportion)", re.I)
_MONEY = re.compile(r"(cost|amount|charge|price|expense|income|revenue)", re.I)


def _numeric(df):
    return [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]


def _cats(df):
    return [c for c in df.columns if not pd.api.types.is_numeric_dtype(df[c])]


def _pick_measure(df):
    nums = [c for c in _numeric(df) if not _ID.search(str(c))]
    if not nums:
        return None
    for tier in _TIERS:
        hit = [c for c in nums if tier.search(str(c))]
        if hit:
            return hit[0]
    return nums[0]


def _fmt(col, v) -> str:
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "—"
    c = str(col).lower()
    if _PCTISH.search(c):
        return f"{v:.1f}%"
    if _MONEY.search(c):
        return f"${v:,.0f}"
    return f"{int(v):,}" if float(v).is_integer() else f"{v:,.1f}"


def kpi_cards(df: pd.DataFrame, question: str = "") -> list[dict]:
    """1-3 headline cards. For a category × measure result: the top, the bottom, and the spread."""
    if df is None or len(df) == 0:
        return []
    y = _pick_measure(df)
    if y is None:
        return []
    cats = [c for c in _cats(df) if not _ID.search(str(c))]
    if len(df) == 1:
        return [{"label": str(y).replace("_", " "), "value": _fmt(y, df.iloc[0][y]), "sub": ""}]
    if not cats:
        col = df[y].dropna()
        return [{"label": f"max {y}".replace("_", " "), "value": _fmt(y, col.max()), "sub": ""},
                {"label": f"median {y}".replace("_", " "), "value": _fmt(y, col.median()), "sub": ""}]
    x = cats[0]
    top = df.loc[df[y].idxmax()]
    bot = df.loc[df[y].idxmin()]
    return [
        {"label": f"highest {x}".replace("_", " "), "value": str(top[x]), "sub": _fmt(y, top[y])},
        {"label": f"lowest {x}".replace("_", " "), "value": str(bot[x]), "sub": _fmt(y, bot[y])},
        {"label": "spread", "value": _fmt(y, top[y] - bot[y]), "sub": "high − low"},
    ]


def _add_ci(d: pd.DataFrame, y: str):
    """Add Wilson 95% CI columns (in the measure's units) if a numerator + denominator are present."""
    numer = [c for c in _numeric(d) if _NUMER.search(str(c))]
    denom = [c for c in _numeric(d) if _DENOM.search(str(c))]
    if not numer or not denom:
        return False
    kcol, ncol = numer[0], max(denom, key=lambda c: d[c].sum())
    scale = 100.0 if (_PCTISH.search(str(y)) or d[y].max() > 1.5) else 1.0
    los, his = [], []
    for _, row in d.iterrows():
        n = int(row[ncol]) if pd.notna(row[ncol]) else 0
        k = int(row[kcol]) if pd.notna(row[kcol]) else 0
        lo, hi = wilson_ci(k, n) if n > 0 else (np.nan, np.nan)
        los.append(lo * scale)
        his.append(hi * scale)
    d["_ci_lo"], d["_ci_hi"] = los, his
    return not d["_ci_lo"].isna().all()


def build_chart(df: pd.DataFrame, question: str = ""):
    """Layered Altair chart: bars + value labels + highlighted extreme + Wilson CI error bars."""
    if df is None or len(df) < 2:
        return None
    y = _pick_measure(df)
    if y is None:
        return None

    time_cols = [c for c in df.columns if _TIME.search(str(c)) or pd.api.types.is_datetime64_any_dtype(df[c])]
    cats = [c for c in _cats(df) if not _ID.search(str(c))]

    if time_cols:                                            # time series → line
        x = time_cols[0]
        d = df[[x, y]].dropna()
        is_dt = pd.api.types.is_datetime64_any_dtype(df[x])
        chart = alt.Chart(d).mark_line(point=alt.OverlayMarkDef(color=TEAL), color=TEAL).encode(
            x=alt.X(f"{x}:{'T' if is_dt else 'O'}", title=str(x)),
            y=alt.Y(f"{y}:Q", title=str(y)),
            tooltip=list(d.columns),
        )
        return _finish(chart, 300)

    if cats:                                                 # category × measure → annotated bars
        x = cats[0]
        keep = [c for c in df.columns if c == x or pd.api.types.is_numeric_dtype(df[c])]
        d = df[keep].dropna(subset=[y]).sort_values(y, ascending=False).head(15).copy()
        top_val = d[y].max()
        d["_top"] = d[y] == top_val
        d["_label"] = d[y].map(lambda v: _fmt(y, v))
        has_ci = _add_ci(d, y)

        base = alt.Chart(d).encode(y=alt.Y(f"{x}:N", sort="-x", title=None))
        bars = base.mark_bar().encode(
            x=alt.X(f"{y}:Q", title=str(y).replace("_", " ")),
            color=alt.condition("datum._top", alt.value(TEAL_HI), alt.value(TEAL)),
            tooltip=[c for c in d.columns if not c.startswith("_")],
        )
        layers = [bars]
        if has_ci:                                           # Wilson 95% CI error bars
            layers.append(base.mark_rule(color=INK, opacity=0.8).encode(
                x=alt.X("_ci_lo:Q"), x2="_ci_hi:Q"))
            layers.append(base.mark_tick(color=INK, thickness=2, size=8).encode(x="_ci_lo:Q"))
            layers.append(base.mark_tick(color=INK, thickness=2, size=8).encode(x="_ci_hi:Q"))
        layers.append(base.mark_text(align="left", dx=5, color=MUTED, fontSize=11).encode(
            x=alt.X(f"{y}:Q"), text="_label:N"))
        chart = alt.layer(*layers)
        title = f"{str(y).replace('_', ' ')} by {str(x).replace('_', ' ')}"
        if has_ci:
            title += "  ·  bars = estimate, whiskers = 95% CI"
        return _finish(chart, min(400, 70 + 30 * len(d)), title)

    return None


def _finish(chart, height: int, title: str = ""):
    c = chart.properties(height=height, background="transparent")
    if title:
        c = c.properties(title=title)
    return (c.configure_axis(labelColor=MUTED, titleColor=MUTED, gridColor=GRID, domainColor=DOMAIN)
            .configure_view(strokeWidth=0)
            .configure_title(color=INK, fontSize=13, anchor="start", font="IBM Plex Sans"))
