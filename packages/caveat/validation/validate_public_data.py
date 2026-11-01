"""Run caveat against real public datasets and check its findings against independent ground truth.

The package's own tests use frames the author invented. That proves the code does what the author
expected and nothing about whether the expectations hold outside their head. This script runs the
library over data it was not built for, compares selected outputs with calculations based on those same data, and prints where the two
agree and where they do not. Some checks use the package's own helper functions; these are not
independent numerical validation.

    python packages/caveat/validation/validate_public_data.py      # from the repo root

Datasets (all committed under examples/, all originally from the UCI ML Repository):
  * Heart Disease, Cleveland    — archive.ics.uci.edu/dataset/45
  * Heart Failure Clinical Records — archive.ics.uci.edu/dataset/519
  * Breast Cancer Wisconsin (Diagnostic) — archive.ics.uci.edu/dataset/17
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

import caveat
from caveat.stats import skewness

EXAMPLES = Path(__file__).resolve().parents[3] / "examples"
_results: list[tuple[str, str, str]] = []      # (verdict, dataset, note)


def check(verdict: str, dataset: str, note: str) -> None:
    _results.append((verdict, dataset, note))
    print(f"  {verdict:5} {note}")


def section(title: str, df: pd.DataFrame, question: str, **kw) -> caveat.Report:
    print(f"\n{'=' * 90}\n{title}\n  Q: {question}")
    rep = caveat.analyze(df, question, **kw)
    print(f"  roles: {rep.roles}")
    for line in (caveat.render(rep) or "  (no findings)").splitlines():
        print(f"    {line}")
    return rep


def heart_disease() -> None:
    hd = pd.read_csv(EXAMPLES / "heart_disease_cleveland.csv")
    hd["disease"] = (hd.num > 0).astype(int)
    g = (hd.groupby("cp").agg(cases=("disease", "sum"), n=("disease", "size")).reset_index())
    truth_small = sorted(g[g.n < 30].cp)
    rep = section("UCI HEART DISEASE (Cleveland, n=297) — disease rate by chest-pain type", g,
                  "Which chest pain type has the highest disease rate?")

    f = rep.of_kind("small_sample")
    ok = f and all(c in f[0].message for c in truth_small)
    check("PASS" if ok else "FAIL", "heart_disease",
          f"flags exactly the under-powered group(s) {truth_small}")

    # the largest true gap, computed independently
    rates = (g.cases / g.n).round(4)
    hi, lo = rates.idxmax(), rates.idxmin()
    true_gap = (rates[hi] - rates[lo]) * 100
    f = rep.of_kind("contrasts")
    ok = f and f"{true_gap:+.1f}pp" in f[0].message
    check("PASS" if ok else "FAIL", "heart_disease",
          f"largest surviving contrast matches the true largest gap ({true_gap:+.1f}pp)")


def heart_failure() -> None:
    hf = pd.read_csv(EXAMPLES / "heart_failure.csv")

    d = (hf.groupby("ef_group").agg(deaths=("DEATH_EVENT", "sum"), n=("DEATH_EVENT", "size"))
           .reset_index())
    true_diff = (d.deaths / d.n).iloc[0] * 100 - (d.deaths / d.n).iloc[1] * 100
    rep = section("UCI HEART FAILURE (n=299) — mortality by ejection-fraction group", d,
                  "Does mortality differ by ejection fraction group?")
    f = rep.of_kind("contrasts")
    ok = f and f"{true_diff:+.1f}pp" in f[0].message
    check("PASS" if ok else "FAIL", "heart_failure",
          f"recovers the known EF mortality gradient ({true_diff:+.1f}pp)")

    cpk = hf.creatinine_phosphokinase
    truth_skew, truth_median = skewness(cpk), cpk.median()
    raw = hf[["creatinine_phosphokinase"]].assign(
        arm=hf.DEATH_EVENT.map({0: "survived", 1: "died"}))
    rep = section("UCI HEART FAILURE — raw per-patient CPK, a strongly skewed clinical assay", raw,
                  "Does creatinine phosphokinase differ between those who died and survived?",
                  group="arm", measure="creatinine_phosphokinase")
    f = rep.of_kind("skew")
    ok = f and f"{truth_skew:.1f}" in f[0].message and f"{truth_median:,.0f}" in f[0].message
    check("PASS" if ok else "FAIL", "heart_failure",
          f"reports the true skew and median (skewness {truth_skew:.2f}, median {truth_median:,.0f})")
    check("PASS" if not rep.of_kind("multiple_comparisons") else "FAIL", "heart_failure",
          "does not mistake 299 patient ROWS for 299 groups")


def breast_cancer() -> None:
    """The adversarial case: 30 continuous feature columns, no counts, no natural denominator.

    This is where a structural heuristic is most likely to embarrass itself by deciding that some
    feature column is a denominator for another and then reporting confident nonsense.
    """
    bc = pd.read_csv(EXAMPLES / "breast_cancer.csv")
    feats = [c for c in bc.columns if c.startswith("mean_")][:8]
    rep = section("UCI BREAST CANCER (n=569) — 30 continuous features, NO counts (adversarial)",
                  bc[feats].head(200), "Which measurement is largest?")
    r = rep.roles
    check("PASS" if not (r.numerator and r.denominator) else "FAIL", "breast_cancer",
          "invents no numerator/denominator where the data has none")
    check("PASS" if not rep.of_kind("contrasts") else "FAIL", "breast_cancer",
          "runs no proportion contrasts on continuous-only data")
    check("PASS" if any(s.check == "contrasts" for s in rep.skipped) else "FAIL", "breast_cancer",
          "says why it could not, instead of returning an empty report")
    check("PASS" if not rep.of_kind("multiple_comparisons") else "FAIL", "breast_cancer",
          "does not warn about 'ranking 200 groups' when there is no grouping column")


def main() -> int:
    print(__doc__.split("\n\n")[0])
    heart_disease()
    heart_failure()
    breast_cancer()

    print(f"\n{'=' * 90}\nSUMMARY")
    for verdict in ("PASS", "FAIL", "MISS"):
        hits = [r for r in _results if r[0] == verdict]
        if hits:
            print(f"  {verdict}: {len(hits)}")
            for _, ds, note in hits:
                print(f"      [{ds}] {note}")
    bad = [r for r in _results if r[0] != "PASS"]
    print(f"\n  {len(_results) - len(bad)}/{len(_results)} checks agree with their reference calculations")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
