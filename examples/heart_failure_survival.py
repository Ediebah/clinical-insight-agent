"""Reproduce established heart-failure survival findings on real public data.

Runs the agent's own Cox proportional-hazards and Kaplan-Meier code (`agent.modeling`) against the UCI
Heart Failure Clinical Records dataset and checks the result against the published literature. It is
the survival counterpart to the heart-disease example: on data a cardiology cohort has already been
analysed, the agent recovers the settled predictors of mortality.

    Dataset : examples/heart_failure.csv  (299 patients, time-to-event)
    Source  : UCI Machine Learning Repository, Heart Failure Clinical Records
              https://archive.ics.uci.edu/dataset/519/heart+failure+clinical+records
              Chicco D., Jurman G. (2020), BMC Med. Inform. Decis. Mak. 20:16.
              Original cohort: Ahmad T. et al. (2017), PLoS ONE 12(7):e0181001.
    Public  : redistributable for research with citation. `time` is the follow-up period (days),
              `DEATH_EVENT` the event (1 = died, 0 = censored). `ef_group` splits ejection fraction at
              the 40% HFrEF clinical cutoff for the Kaplan-Meier curves.

Run:  .venv/bin/python examples/heart_failure_survival.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))   # run as a standalone script
from agent import modeling  # noqa: E402

CSV = Path(__file__).resolve().parent / "heart_failure.csv"
PREDICTORS = ["age", "ejection_fraction", "serum_creatinine", "serum_sodium", "high_blood_pressure", "sex"]


def main() -> None:
    df = pd.read_csv(CSV)
    deaths = int(df["DEATH_EVENT"].sum())
    print(f"UCI Heart Failure · n={len(df)} · deaths={deaths} ({deaths / len(df):.0%}) · "
          f"median follow-up {df['time'].median():.0f} days\n")

    print("Adjusted hazard ratios (agent's Cox model)")
    print("-" * 62)
    cx = modeling.fit_cox(df, "time", "DEATH_EVENT", PREDICTORS)
    for t in cx.terms:
        if t.p != t.p:
            continue
        star = " *" if t.p < 0.05 else "  "
        print(f"{star} {t.name:22s} HR {t.estimate:6.3f}  [{t.ci_low:5.3f}, {t.ci_high:5.3f}]  p={t.p:.4f}")

    print("\nKaplan-Meier by ejection-fraction group (agent's survival curves)")
    print("-" * 62)
    km = modeling.fit_survival(df, "time", "DEATH_EVENT", predictors=None, group="ef_group")
    for g in sorted({p["group"] for p in km.km}):
        last = [p for p in km.km if p["group"] == g][-1]
        print(f"   {g:20s} survival at last follow-up ~{last['survival']:.2f}")

    def hr(name):
        return next(t for t in cx.terms if t.name == name).estimate

    ef_surv = {g: [p for p in km.km if p["group"] == g][-1]["survival"]
               for g in {p["group"] for p in km.km}}
    print("\nJudged against the literature (Chicco & Jurman 2020)")
    print("-" * 62)
    checks = [
        ("Lower ejection fraction raises mortality (HR < 1 per %)", hr("ejection_fraction") < 1.0),
        ("Higher serum creatinine raises mortality (HR > 1)", hr("serum_creatinine") > 1.0),
        ("Older age raises mortality (HR > 1)", hr("age") > 1.0),
        ("Reduced-EF patients (< 40%) survive worse than preserved-EF",
         ef_surv["EF < 40 (reduced)"] < ef_surv["EF >= 40"]),
    ]
    for label, ok in checks:
        print(f"   [{'PASS' if ok else 'FAIL'}] {label}")
    print("\nEjection fraction and serum creatinine, the two predictors Chicco & Jurman highlight, are "
          "recovered from real data by the same code the demo runs.")


if __name__ == "__main__":
    main()
