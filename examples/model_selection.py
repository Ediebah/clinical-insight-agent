"""Demonstrate exploratory model selection on three familiar public datasets.

The engine compares candidates using nested cross-validation. Its classification composite averages
ROC-AUC, PR-AUC, and balanced accuracy; it does not measure calibration or establish clinical utility.
These familiar datasets and internal folds are not independent external validation.

    Data: examples/heart_disease_cleveland.csv, examples/heart_failure.csv,
          examples/breast_cancer.csv. See docs/DATA_PROVENANCE.md for source and limitations.

Run:  .venv/bin/python examples/model_selection.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))   # run as a standalone script
from agent import modeling  # noqa: E402

HERE = Path(__file__).resolve().parent


def report(title: str, df: pd.DataFrame, outcome: str, predictors: list[str]) -> None:
    r = modeling.compare_models(df, outcome, predictors)
    print(f"{title}")
    if r.error:
        print(f"   Could not run: {r.error}\n")
        return
    print("   leaderboard (composite = mean of roc_auc, pr_auc, balanced accuracy):")
    for row in r.leaderboard:
        mark = " * " if row["is_winner"] else "   "
        auc = row.get("components", {}).get("roc_auc")
        extra = f"   [auc {auc:.3f}]" if auc is not None else ""
        print(f"    {mark}{row['model']:20s} {row['score']:.3f} ± {row['std']:.3f}{extra}")
    print(f"   engine picked: {r.verdict['winner']}")
    print(f"   {r.fit_stat}\n")


def main() -> None:
    print("The agent compares candidate models and keeps the best-fitting one\n" + "=" * 66 + "\n")

    hd = pd.read_csv(HERE / "heart_disease_cleveland.csv")
    report("Heart disease · Cleveland (Detrano et al., 1989)", hd, "heart_disease",
           ["age", "sex", "cp", "trestbps", "chol", "thalach", "exang", "oldpeak", "ca", "thal"])

    hf = pd.read_csv(HERE / "heart_failure.csv")
    report("Heart failure · DEATH_EVENT (Chicco & Jurman, 2020)", hf, "DEATH_EVENT",
           ["age", "ejection_fraction", "serum_creatinine", "serum_sodium", "high_blood_pressure", "sex",
            "anaemia", "diabetes", "creatinine_phosphokinase", "platelets", "smoking"])

    bc = pd.read_csv(HERE / "breast_cancer.csv")
    report("Breast cancer · WDBC (Wolberg et al., 1995)", bc, "malignant",
           [c for c in bc.columns if c != "malignant"])

    print("These internal comparisons do not establish calibration, external performance or clinical utility.")


if __name__ == "__main__":
    main()
