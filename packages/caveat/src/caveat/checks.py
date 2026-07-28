"""The checks.

Each takes a Ctx and appends Findings, or appends a Skip saying what it would have needed. Every
check is domain-neutral: no check knows what a patient is. Thresholds live in Config because the n
below which a proportion is unstable is a judgement that differs between a clinical trial and a
web funnel.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .findings import Finding, Skip
from .roles import DISPERSION_RE, MEAN_RE, Roles
from .stats import (
    benjamini_hochberg,
    bootstrap_diff_ci,
    bootstrap_mean_ci,
    mde_two_proportions,
    newcombe_diff_ci,
    skewness,
    two_proportion_p,
    wilson_ci,
)


@dataclass
class Config:
    min_n: int = 30                 # below this a proportion is called unstable
    tiny_n: int = 10                # below this it is escalated to `caution`
    alpha: float = 0.05
    power: float = 0.80
    skew_moderate: float = 1.0
    skew_high: float = 2.0
    many_groups: int = 10           # ranking this many without correction invites a false positive
    max_contrast_rows: int = 60     # pairwise contrasts are O(n^2); refuse rather than crawl
    missing_frac: float = 0.05      # flag a column missing more than this share
    min_rows_for_distribution: int = 20
    confounders: tuple[str, ...] = ()   # domain-specific candidates named in the confounding message
    bootstrap_n: int = 2000
    seed: int = 0


@dataclass
class Ctx:
    df: pd.DataFrame
    roles: Roles
    question: str = ""
    config: Config = field(default_factory=Config)
    findings: list = field(default_factory=list)
    skipped: list = field(default_factory=list)
    tests_run: int = 0

    def add(self, kind, severity, message):
        self.findings.append(Finding(kind, severity, message))

    def skip(self, check, reason, fix=""):
        self.skipped.append(Skip(check, reason, fix))

    def label(self, idx) -> str:
        r = self.roles
        parts = [str(self.df.loc[idx, c]) for c in (r.group, r.stratifier) if c]
        return " / ".join(parts) if parts else f"row {idx}"


_COMPARE_WORDS = ("highest", "lowest", "which", "compare", "difference", "differ", "top", "rank",
                  "vs", "versus", "between", "most", "least", "driver", "drives", " by ", "best",
                  "worst", "more", "less")


def _is_comparison(question: str) -> bool:
    q = f" {(question or '').lower()} "
    return any(w in q for w in _COMPARE_WORDS)


def _groups(ctx) -> list[tuple]:
    """(index, k, n) per row, for rows with a positive denominator."""
    r, df = ctx.roles, ctx.df
    return [(i, int(df.loc[i, r.numerator]), int(df.loc[i, r.denominator]))
            for i in df.index if df.loc[i, r.denominator] > 0]


def _contrast_units(ctx) -> list[tuple]:
    """(label, k, n) per unit worth contrasting.

    When a stratifier is present each ROW is a group-within-stratum cell, and contrasting rows
    cross-multiplies the two. On the Berkeley 1973 admissions table that produced "women in
    department A vs men in department F, +76.5pp" as the headline: arithmetically true, and a
    comparison nobody asked for. Pool to the group level instead and let `simpsons` say whether
    pooling is safe — which on that table it does, loudly.
    """
    r, df = ctx.roles, ctx.df
    if r.group and r.stratifier:
        agg = df.groupby(r.group)[[r.numerator, r.denominator]].sum()
        return [(str(g), int(row[r.numerator]), int(row[r.denominator]))
                for g, row in agg.iterrows() if row[r.denominator] > 0]
    return [(ctx.label(i), int(df.loc[i, r.numerator]), int(df.loc[i, r.denominator]))
            for i in df.index if df.loc[i, r.denominator] > 0]


# ───────────────────────────── proportion checks ─────────────────────────────
def small_sample(ctx: Ctx) -> None:
    r, df, cfg = ctx.roles, ctx.df, ctx.config
    if not r.denominator:
        return ctx.skip("small_sample", "no denominator column identified",
                        "pass denominator='<col>'")
    small = df[df[r.denominator] < cfg.min_n]
    if len(small) == 0:
        return
    worst = small.nsmallest(min(3, len(small)), r.denominator)
    ex = "; ".join(f"{ctx.label(i)} (n={int(worst.loc[i, r.denominator])})" for i in worst.index)
    sev = "caution" if (small[r.denominator] < cfg.tiny_n).any() else "warn"
    ctx.add("small_sample", sev,
            f"{len(small)} group(s) have n < {cfg.min_n} in `{r.denominator}` - estimates unstable. "
            f"e.g. {ex}.")


def contrasts(ctx: Ctx) -> None:
    """Every pairwise risk difference, with Newcombe CIs and BH-FDR across the family.

    The point of this check: a table of per-group rates invites reading the biggest number as the
    winner. The question is whether any pair actually differs once the family is corrected, and
    often the answer is no.
    """
    r, df, cfg = ctx.roles, ctx.df, ctx.config
    if not (r.numerator and r.denominator):
        return ctx.skip("contrasts", "needs both a numerator and a denominator column",
                        "pass numerator='<col>', denominator='<col>'")
    # Pairwise FDR answers "do these differ", which is only worth saying if someone asked. On a
    # listing query ("members and eligibility per payer") it is noise dressed as rigour. A caller
    # who supplies no question gets the contrasts, having given no signal either way.
    if ctx.question and not _is_comparison(ctx.question):
        return ctx.skip("contrasts", "the question does not read as a comparison",
                        "omit `question` to contrast regardless")
    if len(df) < 2:
        return ctx.skip("contrasts", "only one row - nothing to contrast")
    if len(df) > cfg.max_contrast_rows:
        return ctx.skip("contrasts", f"{len(df)} rows exceeds max_contrast_rows "
                                     f"({cfg.max_contrast_rows}); pairwise is quadratic",
                        "raise Config.max_contrast_rows or aggregate first")
    grp = _contrast_units(ctx)
    if len(grp) < 2:
        return ctx.skip("contrasts", "fewer than two rows have a positive denominator")

    pairs, pvals = [], []
    for a in range(len(grp)):
        for b in range(a + 1, len(grp)):
            label_a, k1, n1 = grp[a]
            label_b, k2, n2 = grp[b]
            d, lo, hi = newcombe_diff_ci(k1, n1, k2, n2)
            p = two_proportion_p(k1, n1, k2, n2)
            pairs.append((label_a, label_b, d, lo, hi, p))
            pvals.append(p)
    ctx.tests_run += len(pvals)
    q = benjamini_hochberg(pvals)
    sig = [(pairs[t], q[t]) for t in range(len(pairs)) if q[t] < cfg.alpha]

    if not sig:
        ns = [n for _, _, n in grp]
        k_tot = sum(k for _, k, _ in grp)
        n_tot = sum(ns) or 1
        mde = mde_two_proportions(int(np.median(ns)), int(np.median(ns)), k_tot / n_tot,
                                  cfg.alpha, cfg.power)
        extra = ("" if math.isnan(mde) else
                 f" At the median group size (n={int(np.median(ns))}) the smallest difference this "
                 f"data could have detected is about {mde*100:.0f}pp, so 'no difference' here means "
                 f"'underpowered for anything smaller', not 'equivalent'.")
        ctx.add("contrasts", "info",
                f"No pairwise difference among {len(grp)} groups survives Benjamini-Hochberg FDR "
                f"(q>={cfg.alpha}); observed gaps are within noise.{extra}")
        return
    sig.sort(key=lambda x: abs(x[0][2]), reverse=True)
    (label_a, label_b, d, lo, hi, _p), qv = sig[0]
    pooled = " (pooled across strata)" if (ctx.roles.group and ctx.roles.stratifier) else ""
    ctx.add("contrasts", "warn",
            f"{len(sig)}/{len(pairs)} pairwise contrasts survive BH-FDR (q<{cfg.alpha}){pooled}. "
            f"Largest: {label_a} vs {label_b}, risk difference {d*100:+.1f}pp "
            f"(95% CI [{lo*100:.1f}, {hi*100:.1f}], q={qv:.3f}). Report differences with CIs, "
            f"not raw ranks.")


def boundary_rate(ctx: Ctx) -> None:
    """0/n and n/n are not 0% and 100% with certainty — they are the intervals Wald collapses on."""
    r = ctx.roles
    if not (r.numerator and r.denominator):
        return ctx.skip("boundary_rate", "needs a numerator and a denominator column")
    hits = []
    for i, k, n in _groups(ctx):
        if k == 0 or k == n:
            lo, hi = wilson_ci(k, n)
            hits.append(f"{ctx.label(i)} = {k}/{n} (95% CI [{lo*100:.1f}, {hi*100:.1f}]%)")
    if hits:
        ctx.add("boundary_rate", "warn" if any("= 0/" in h for h in hits) else "info",
                f"{len(hits)} group(s) sit at 0% or 100%, where a point estimate badly overstates "
                f"certainty: {'; '.join(hits[:3])}. Report the interval, not the point.")


def winners_curse(ctx: Ctx) -> None:
    """The top-ranked group being one of the smallest is the classic selection artifact."""
    r, df, cfg = ctx.roles, ctx.df, ctx.config
    if not (r.numerator and r.denominator) or len(df) < 3:
        return ctx.skip("winners_curse", "needs a numerator, a denominator and at least 3 groups")
    grp = _groups(ctx)
    if len(grp) < 3:
        return
    rates = sorted(((k / n, i, n) for i, k, n in grp), reverse=True)
    top_rate, top_i, top_n = rates[0]
    median_n = float(np.median([n for _, _, n in rates]))
    if top_n < median_n and top_n < cfg.min_n:
        lo, hi = wilson_ci(int(df.loc[top_i, r.numerator]), top_n)
        ctx.add("winners_curse", "caution",
                f"The highest-ranked group ({ctx.label(top_i)}, {top_rate*100:.1f}%) is also one of "
                f"the smallest (n={top_n} vs median {median_n:.0f}). Extremes concentrate in small "
                f"groups by construction, so this ranking is partly a sample-size artifact - its "
                f"own 95% CI is [{lo*100:.1f}, {hi*100:.1f}]%.")


def missing_denominator(ctx: Ctx) -> None:
    r = ctx.roles
    if r.rate and not r.denominator:
        ctx.add("missing_denominator", "warn",
                f"`{r.rate}` is a rate shown without the count it was computed over - a rate is a "
                f"base-rate trap without its N. Add the group size so it can be judged.")


def multiple_comparisons(ctx: Ctx, did_contrasts: bool = False) -> None:
    cfg, r = ctx.config, ctx.roles
    if did_contrasts:
        return   # already handled rigorously, with FDR
    # Rows are not groups. On a per-observation frame — which mean_contrasts explicitly expects —
    # counting rows claimed "ranking 299 groups" for a two-arm comparison of 299 patients, and
    # "ranking 200 groups" for a table of 200 measurements with no grouping column at all.
    # Without a group column there is no family of comparisons to correct, so say so rather than
    # guess: a multiplicity warning nobody can act on is just noise with a statistical accent.
    if not (r.group and r.group in ctx.df.columns):
        return ctx.skip("multiple_comparisons", "no group column identified, so there is no family "
                                                "of comparisons to correct", "pass group='<col>'")
    n_groups = ctx.df[r.group].nunique()
    if n_groups >= cfg.many_groups and _is_comparison(ctx.question):
        ctx.add("multiple_comparisons", "warn",
                f"Comparing or ranking {n_groups} groups inflates false positives. Correct "
                f"before calling any single difference real: Bonferroni "
                f"alpha/{n_groups} = {cfg.alpha/n_groups:.4f}, or Benjamini-Hochberg FDR.")


# ───────────────────────────── continuous checks ─────────────────────────────
def skew(ctx: Ctx) -> None:
    r, df, cfg = ctx.roles, ctx.df, ctx.config
    if not r.measure:
        return ctx.skip("skew", "no continuous measure column identified", "pass measure='<col>'")
    vals = df[r.measure].dropna().to_numpy()
    if len(vals) >= cfg.min_rows_for_distribution:
        sk = skewness(vals)
        if abs(sk) >= cfg.skew_moderate:
            med = float(np.median(vals))
            q1, q3 = np.percentile(vals, [25, 75])
            lo, hi = bootstrap_mean_ci(vals, cfg.bootstrap_n, cfg.seed)
            side = "right" if sk > 0 else "left"
            ctx.add("skew", "warn" if abs(sk) >= cfg.skew_high else "info",
                    f"`{r.measure}` is {side}-skewed (skewness {sk:.1f}); the mean "
                    f"{'over' if sk > 0 else 'under'}states the typical value. "
                    f"Median={med:,.0f} (IQR {q1:,.0f}-{q3:,.0f}); bootstrap 95% CI for the mean "
                    f"[{lo:,.0f}, {hi:,.0f}]. Prefer median/IQR for skewed data.")
        return
    mean_cols = [c for c in df.columns if MEAN_RE.search(str(c))]
    if mean_cols and not any(DISPERSION_RE.search(str(c)) for c in df.columns):
        ctx.add("skew", "info",
                f"`{mean_cols[0]}` is a mean shown without any dispersion. A mean alone cannot be "
                f"judged - request median + IQR, or the distribution, to confirm it is "
                f"representative.")


def mean_contrasts(ctx: Ctx) -> None:
    """Pairwise differences of means across groups, bootstrapped and BH-corrected.

    The proportion path has had rigorous contrasts for a while; means had nothing, which left half
    of ordinary analytics uncovered. Bootstrapped rather than t-tested because the measures this
    fires on (cost, duration, spend) are exactly the ones that are not normal.
    """
    r, df, cfg = ctx.roles, ctx.df, ctx.config
    if not (r.group and r.measure):
        return ctx.skip("mean_contrasts", "needs a group column and a continuous measure",
                        "pass group='<col>', measure='<col>'")
    if ctx.question and not _is_comparison(ctx.question):
        return ctx.skip("mean_contrasts", "the question does not read as a comparison",
                        "omit `question` to contrast regardless")
    sub = df[[r.group, r.measure]].dropna()
    counts = sub.groupby(r.group)[r.measure].count()
    usable = [g for g, n in counts.items() if n >= 2]
    if len(usable) < 2:
        return ctx.skip("mean_contrasts", "fewer than two groups have 2+ raw observations",
                        "this check needs per-observation rows, not pre-aggregated means")
    if len(usable) > cfg.max_contrast_rows:
        return ctx.skip("mean_contrasts", f"{len(usable)} groups exceeds max_contrast_rows")

    vals = {g: sub.loc[sub[r.group] == g, r.measure].to_numpy() for g in usable}
    pairs, pvals = [], []
    for a in range(len(usable)):
        for b in range(a + 1, len(usable)):
            ga, gb = usable[a], usable[b]
            d, lo, hi, p = bootstrap_diff_ci(vals[ga], vals[gb], cfg.bootstrap_n, cfg.seed)
            pairs.append((ga, gb, d, lo, hi))
            pvals.append(p)
    ctx.tests_run += len(pvals)
    q = benjamini_hochberg(pvals)
    sig = [(pairs[t], q[t]) for t in range(len(pairs)) if q[t] < cfg.alpha]
    if not sig:
        ctx.add("mean_contrasts", "info",
                f"No pairwise difference in mean `{r.measure}` across {len(usable)} groups survives "
                f"BH-FDR (q>={cfg.alpha}); the spread between group means is within noise.")
        return
    sig.sort(key=lambda x: abs(x[0][2]), reverse=True)
    (ga, gb, d, lo, hi), qv = sig[0]
    ctx.add("mean_contrasts", "warn",
            f"{len(sig)}/{len(pairs)} pairwise mean differences survive BH-FDR (q<{cfg.alpha}). "
            f"Largest: {ga} vs {gb}, difference {d:+,.1f} (bootstrap 95% CI [{lo:,.1f}, {hi:,.1f}], "
            f"q={qv:.3f}).")


# ───────────────────────────── structural checks ─────────────────────────────
def confounding(ctx: Ctx) -> None:
    r, cfg = ctx.roles, ctx.config
    # A rate or a measure is an outcome; a bare count is not. Comparing raw event counts across
    # groups of different sizes is a denominator problem (missing_denominator's job), and warning
    # about confounding on top of it would fire on almost every table that has a count in it.
    outcome = r.rate or r.measure
    if not (r.group and outcome):
        return ctx.skip("confounding", "needs a group column and a rate or measure outcome",
                        "a bare count is not an outcome; pass rate='<col>' or measure='<col>'")
    if not _is_comparison(ctx.question):
        return ctx.skip("confounding", "the question does not read as a comparison",
                        "pass question='...' describing what is being compared")
    named = ", ".join(cfg.confounders[:3]) if cfg.confounders else \
        "composition, exposure and selection into each group"
    ctx.add("confounding", "warn",
            f"This compares `{outcome}` across `{r.group}` **unadjusted**. Groups likely differ in "
            f"{named}, which can produce the whole gap. Before any causal reading, standardize or "
            f"fit a covariate-adjusted model; a crude comparison is descriptive only.")


def simpsons(ctx: Ctx) -> None:
    """Does the marginal ordering reverse inside strata?"""
    r, df = ctx.roles, ctx.df
    if not (r.group and r.stratifier and r.numerator and r.denominator):
        return ctx.skip("simpsons", "needs group, stratifier, numerator and denominator",
                        "pass stratifier='<col>' to enable")

    def rate_by(frame, col):
        out = {}
        for lvl, x in frame.groupby(col):
            tot = x[r.denominator].sum()
            if tot > 0:
                out[lvl] = x[r.numerator].sum() / tot
        return out

    marg = rate_by(df, r.group)
    if len(marg) < 2:
        return
    ordered = sorted(marg, key=marg.get, reverse=True)
    top, bottom = ordered[0], ordered[-1]
    reversed_in = []
    for lvl, sub in df.groupby(r.stratifier):
        rr = rate_by(sub, r.group)
        if top in rr and bottom in rr and rr[bottom] > rr[top]:
            reversed_in.append(str(lvl))
    if reversed_in:
        ctx.add("simpsons", "caution",
                f"Simpson's paradox risk: marginally `{top}` > `{bottom}`, but within stratum "
                f"{', '.join(reversed_in[:3])} the ordering reverses. The pooled comparison is "
                f"confounded by `{r.stratifier}` - report stratified, not collapsed.")


def missing_data(ctx: Ctx) -> None:
    """Nulls in the result change every denominator silently."""
    df, cfg = ctx.df, ctx.config
    if len(df) == 0:
        return
    frac = df.isna().mean()
    bad = frac[frac > cfg.missing_frac].sort_values(ascending=False)
    if len(bad) == 0:
        return
    ex = "; ".join(f"`{c}` {v*100:.0f}% missing" for c, v in list(bad.items())[:3])
    ctx.add("missing_data", "warn" if bad.max() > 0.2 else "info",
            f"{len(bad)} column(s) have missing values above {cfg.missing_frac*100:.0f}%: {ex}. "
            f"Every statistic below is computed on the rows that remain, which may not be the "
            f"population you think it is.")


CHECKS = {
    "missing_data": missing_data,
    "small_sample": small_sample,
    "contrasts": contrasts,
    "boundary_rate": boundary_rate,
    "winners_curse": winners_curse,
    "simpsons": simpsons,
    "skew": skew,
    "mean_contrasts": mean_contrasts,
    "confounding": confounding,
    "missing_denominator": missing_denominator,
    "multiple_comparisons": multiple_comparisons,
}
