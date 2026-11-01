"""Demonstrate exploratory survival-model comparison on a public dataset.

The agent tunes a Cox model and a random survival forest inside training folds, selecting by
concordance. It reports concordance, time-dependent AUC, and integrated Brier score separately.
Fold variation is not a confidence interval. This demonstration is not external validation.

    Dataset : examples/heart_failure.csv  (299 patients, time-to-event)
    Source  : UCI Heart Failure Clinical Records; Chicco D., Jurman G. (2020), BMC Med. Inform. Decis.
              Mak. 20:16. Original cohort: Ahmad T. et al. (2017), PLoS ONE 12(7):e0181001.
    Needs   : the optional `scikit-survival` package (pip install scikit-survival).

Run:  .venv/bin/python examples/survival_ml.py
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))   # run as a standalone script
from agent import modeling  # noqa: E402

CSV = Path(__file__).resolve().parent / "heart_failure.csv"
PREDICTORS = ["age", "ejection_fraction", "serum_creatinine", "serum_sodium", "high_blood_pressure",
              "sex", "anaemia", "diabetes", "creatinine_phosphokinase", "platelets", "smoking"]


def main() -> None:
    df = pd.read_csv(CSV)
    r = modeling.compare_survival_models(df, "time", "DEATH_EVENT", PREDICTORS)
    if r.error:
        print(f"Could not run: {r.error}")
        return

    print("UCI Heart Failure · survival model selection")
    print("Model selection uses concordance; other metrics are reported separately.")
    print("-" * 78)
    def fmt(value):
        return f"{value:.3f}" if value is not None and math.isfinite(value) else "unavailable"

    for row in r.leaderboard:
        mark = " * " if row["is_winner"] else "   "
        c = row["components"]
        print(f"  {mark}{row['model']:26s} C {fmt(c.get('harrell_c'))} · "
              f"time-dependent AUC {fmt(c.get('td_auc'))} · "
              f"integrated Brier {fmt(c.get('integrated_brier_score'))}")
    print(f"\n   engine picked: {r.verdict['winner']}")
    print(f"   {r.fit_stat}")
    print("   winning model's top predictors: " + ", ".join(t.name for t in r.terms[:3]))
    for issue in r.issues:
        print(f"   review: {issue}")
    print(f"\n{r.note}")


if __name__ == "__main__":
    main()
