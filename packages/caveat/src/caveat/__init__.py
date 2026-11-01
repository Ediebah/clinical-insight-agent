"""caveat — statistical caveats for analysis results.

Given a result table and the question that produced it, say what would stop a statistician
believing it: unstable denominators, differences that vanish under FDR, skew that makes a mean
misleading, an ordering that reverses inside strata.

Everything is deterministic and computed from the data. Nothing here calls a model. That is the
point: an LLM may *phrase* a caveat, but it must never be the thing that decides whether one
applies, because a model that invents caveats will also omit them.

    >>> import pandas as pd, caveat
    >>> df = pd.DataFrame({"arm": ["a", "b"], "cases": [8, 4], "n": [20, 900]})
    >>> report = caveat.analyze(df, question="which arm has the higher rate?")
    >>> print(caveat.render(report))

Roles are inferred (from column names, and from the shape of the numbers when names are useless).
Pass them when you know them:

    >>> caveat.analyze(df, numerator="cases", denominator="n", group="arm")

A report also carries what it could NOT do, so an empty result never masquerades as a clean one:

    >>> for s in report.skipped: print(s)
"""
from __future__ import annotations

import pandas as pd

from .checks import CHECKS, Config, Ctx
from .findings import Finding, Report, Skip, render
from .roles import Roles, UnknownColumn, infer_roles, resolve

__version__ = "0.1.3"

__all__ = [
    "CHECK_ORDER",
    "Config",
    "Finding",
    "Report",
    "Roles",
    "Session",
    "Skip",
    "UnknownColumn",
    "analyze",
    "infer_roles",
    "render",
]

# missing_data first (it conditions everything below it); multiple_comparisons last, because it
# defers to `contrasts` when that ran and corrected the family properly.
CHECK_ORDER = (
    "missing_data",
    "rate_denominator_consistency",
    "small_sample",
    "contrasts",
    "boundary_rate",
    "winners_curse",
    "simpsons",
    "skew",
    "mean_contrasts",
    "confounding",
    "missing_denominator",
    "multiple_comparisons",
)


def analyze(df: pd.DataFrame, question: str = "", *,
            roles: Roles | dict | None = None,
            config: Config | None = None,
            checks=None,
            strict: bool = False,
            **role_kwargs) -> Report:
    """Analyse a result table and return a Report.

    df       the result to critique — one row per group, or per observation for `mean_contrasts`
    question the question that produced it; some checks only apply to comparisons
    roles    explicit column roles, as a Roles or a dict
    config   thresholds (see Config); the defaults suit small-sample work
    checks   names to run, defaulting to all of CHECK_ORDER
    strict   re-raise check errors instead of recording them as skips. Off by default so a caveat
             library can never be the thing that breaks a caller's analysis; on for your own tests.
    **role_kwargs  shorthand: analyze(df, numerator="cases", denominator="n")
    """
    cfg = config or Config()
    if df is None or len(df) == 0:
        return Report(
            findings=[Finding("empty_result", "caution",
                              "The result has no rows - there is nothing to interpret. An empty "
                              "result is not a finding of zero; the query may simply not match.")],
            roles=Roles())

    merged = dict(roles.as_dict() if isinstance(roles, Roles) else (roles or {}))
    merged.pop("source", None)
    merged.update(role_kwargs)
    resolved = resolve(df, merged)

    ctx = Ctx(df=df, roles=resolved, question=question, config=cfg)
    selected = list(checks) if checks is not None else list(CHECK_ORDER)
    unknown = [c for c in selected if c not in CHECKS]
    if unknown:
        raise ValueError(f"unknown check(s): {unknown}. Available: {list(CHECK_ORDER)}")

    count_checks = {"contrasts", "boundary_rate", "winners_curse", "simpsons"}
    needs_rate_check = bool(count_checks.intersection(selected) or
                            "rate_denominator_consistency" in selected)
    if needs_rate_check:
        try:
            CHECKS["rate_denominator_consistency"](ctx)
        except Exception as e:
            if strict:
                raise
            ctx.rate_consistency_blocks_counts = True
            ctx.add("rate_denominator_unverifiable", "caution",
                    f"Rate consistency could not be checked ({type(e).__name__}); "
                    "count-based inference is withheld.")

    did_contrasts = False
    for name in selected:
        if name == "rate_denominator_consistency":
            continue  # The preflight also applies when callers request a subset of checks.
        if name in count_checks and ctx.rate_consistency_blocks_counts:
            ctx.skip(name, "supplied rate and counts are inconsistent or cannot be checked",
                     "clarify the rate and count relationship before count-based inference")
            continue
        fn = CHECKS[name]
        try:
            if name == "multiple_comparisons":
                fn(ctx, did_contrasts=did_contrasts)
            else:
                fn(ctx)
                if name == "contrasts":
                    did_contrasts = any(f.kind == "contrasts" for f in ctx.findings)
        except Exception as e:
            if strict:
                raise
            ctx.skip(name, f"check raised {type(e).__name__}: {e}",
                     "run with strict=True to see the traceback")

    return Report(findings=ctx.findings, roles=resolved, skipped=ctx.skipped,
                  tests_run=ctx.tests_run)


class Session:
    """Accumulates multiplicity across successive analyses.

    Every call to analyze() corrects within its own family, which is the right thing and is also
    not enough. An agent that answers twenty questions against one dataset has run twenty families
    and corrected none of them against each other — the garden of forking paths, arrived at by
    conversation rather than by intent. Nothing else flags this because nothing else sees the
    sequence; a Session does.

        >>> s = caveat.Session()
        >>> for q, df in questions: report = s.analyze(df, q)

    The warning is deliberately about *interpretation*, not a corrected q-value: with an
    exploratory sequence there is no honest family-wide correction to apply after the fact, only
    the obligation to say how much looking was done.
    """

    def __init__(self, config: Config | None = None, *, warn_after_tests: int = 20,
                 warn_after_families: int = 5):
        self.config = config or Config()
        self.warn_after_tests = warn_after_tests
        self.warn_after_families = warn_after_families
        self.tests_run = 0
        self.families = 0
        self.analyses = 0

    def analyze(self, df, question: str = "", **kw) -> Report:
        kw.setdefault("config", self.config)
        report = analyze(df, question, **kw)
        self.analyses += 1
        self.tests_run += report.tests_run
        if report.tests_run:
            self.families += 1
        if self.tests_run >= self.warn_after_tests or self.families >= self.warn_after_families:
            report.findings.append(Finding(
                "session_multiplicity", "warn",
                f"Across this session: {self.analyses} analyses, {self.families} families of "
                f"comparisons, {self.tests_run} hypothesis tests. Each was corrected within itself "
                f"but not across the sequence, so the chance that at least one 'significant' result "
                f"so far is spurious is far above {self.config.alpha:.0%}. Treat findings after this "
                f"much looking as hypotheses to confirm on new data, not conclusions."))
        return report

    def reset(self) -> None:
        self.tests_run = self.families = self.analyses = 0
