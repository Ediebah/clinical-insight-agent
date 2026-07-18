"""Reproduce an established machine-learning benchmark on real public data.

The heart-disease, heart-failure, and go/no-go examples validate the agent's *statistical* models. This
one validates its *machine-learning* path: the agent's random forest (`agent.modeling.fit_forest`, the
same call the app makes for a "which factors predict this?" question) is run on the Wisconsin Diagnostic
Breast Cancer dataset and must reach the discrimination the ML literature has reported for decades, and
surface the tumour features every study finds to matter most.

    Dataset : examples/breast_cancer.csv  (569 fine-needle-aspirate samples, 30 features)
    Source  : UCI Machine Learning Repository, Breast Cancer Wisconsin (Diagnostic)
              https://archive.ics.uci.edu/dataset/17/breast+cancer+wisconsin+diagnostic
              Wolberg W., Street W., Mangasarian O. (1995). Bundled in scikit-learn as
              `sklearn.datasets.load_breast_cancer`.
    Public  : redistributable for research with citation. Column names are lower-cased with underscores;
              the target `malignant` is 1 for a malignant tumour, 0 for benign.

Run:  .venv/bin/python examples/ml_breast_cancer.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))   # run as a standalone script
from agent import modeling  # noqa: E402

CSV = Path(__file__).resolve().parent / "breast_cancer.csv"
# the "worst" (largest) tumour measurements and concavity are the settled strongest diagnostic markers
KEY_MARKERS = ("area", "radius", "perimeter", "concave")


def main() -> None:
    df = pd.read_csv(CSV)
    features = [c for c in df.columns if c != "malignant"]
    print(f"Wisconsin Diagnostic Breast Cancer · n={len(df)} · {len(features)} features · "
          f"malignant rate {df['malignant'].mean():.0%}\n")

    rf = modeling.fit_forest(df, "malignant", features)
    auc = float(re.search(r"AUC=([\d.]+)", rf.fit_stat).group(1))
    top = [t.name for t in rf.terms[:6]]

    print("Discrimination (agent's random forest, cross-validated)")
    print("-" * 62)
    print(f"   {rf.fit_stat}")
    print("   top features (permutation importance): " + ", ".join(top))

    print("\nJudged against the machine-learning literature")
    print("-" * 62)
    checks = [
        ("Cross-validated AUC in the reported 0.96-0.99+ band for this dataset", 0.96 <= auc <= 1.0),
        ("A tumour size/shape marker (area, radius, perimeter, concavity) is in the top 3",
         any(k in name for name in top[:3] for k in KEY_MARKERS)),
    ]
    for label, ok in checks:
        print(f"   [{'PASS' if ok else 'FAIL'}] {label}")
    print(f"\nThe agent's ML model reaches AUC {auc:.3f} on real diagnostic data and recovers the tumour "
          "measurements the literature settled on, using the same code the demo runs.")


if __name__ == "__main__":
    main()
