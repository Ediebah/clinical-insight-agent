"""Validation on real public data (keyless, no LLM).

The agent must not merely *run* on a real dataset; it must reproduce the *established* findings. This
file pins the agent's own logistic and random-forest models against the UCI Cleveland heart-disease
dataset (Detrano et al., 1989), where the coronary-artery-disease risk factors and the achievable
discrimination are long settled in the literature. It is the "judged against the literature" guardrail:
if a change silently breaks the modeling, CI catches it against real ground truth, not synthetic data.

Data: ``examples/heart_disease_cleveland.csv`` (297 complete cases; UCI ML repository, public).
Published benchmarks reproduced here:
  * discrimination AUC ~0.84–0.91 (logistic / tree models on this dataset);
  * the dominant predictors are the number of diseased vessels (``ca``), chest-pain type
    (asymptomatic = highest risk), male sex, ST depression (``oldpeak``), and max heart rate
    (``thalach``, inverse) — all textbook CAD markers.
"""
import re
from pathlib import Path

import pandas as pd

from agent import modeling

_CSV = Path(__file__).resolve().parent.parent / "examples" / "heart_disease_cleveland.csv"
_PREDICTORS = ["age", "sex", "cp", "trestbps", "chol", "thalach", "exang", "oldpeak", "ca", "thal"]


def _data() -> pd.DataFrame:
    return pd.read_csv(_CSV)


def _term(mr, name):
    """The fitted term with exactly this name (substrings collide: 'ca' is inside 'atypical')."""
    return next(t for t in mr.terms if t.name == name)


def test_dataset_is_present_and_shaped_as_expected():
    d = _data()
    assert len(d) == 297                                  # 303 raw minus 6 rows with missing ca/thal
    assert set(["heart_disease", "ca", "sex", "cp", "oldpeak", "thalach"]).issubset(d.columns)
    assert d["heart_disease"].isin([0, 1]).all()
    assert 0.40 < d["heart_disease"].mean() < 0.52        # ~46% disease prevalence in Cleveland


def test_random_forest_discrimination_matches_the_literature():
    """Cross-validated AUC must land in the published range (~0.84–0.91); seeded, so deterministic."""
    r = modeling.fit_forest(_data(), "heart_disease", _PREDICTORS)
    assert r.error is None
    auc = float(re.search(r"AUC=([\d.]+)", r.fit_stat).group(1))
    assert 0.84 <= auc <= 0.93, f"AUC {auc} outside the published band"   # observed 0.903
    top = {t.name for t in r.terms[:4]}                   # the top features are the established CAD markers
    assert "ca" in top and "thal" in top


def test_logistic_recovers_the_established_odds_ratios_and_directions():
    r = modeling.fit_logistic(_data(), "heart_disease", _PREDICTORS)
    assert r.error is None

    ca = _term(r, "ca")                                   # number of diseased vessels: the strongest marker
    assert ca.estimate > 1.5 and ca.p < 0.01

    male = _term(r, "C(sex)[T.male]")
    assert male.estimate > 1.0 and male.p < 0.05          # males carry higher CAD odds

    oldpeak = _term(r, "oldpeak")                          # ST depression raises the odds
    assert oldpeak.estimate > 1.0 and oldpeak.p < 0.05

    thalach = _term(r, "thalach")                          # higher max heart rate lowers the odds (inverse)
    assert thalach.estimate < 1.0 and thalach.p < 0.05


def test_logistic_chest_pain_asymptomatic_is_the_highest_risk_category():
    """Asymptomatic chest pain is the reference; every other type must sit at LOWER odds (OR < 1),
    the well-known 'asymptomatic presentation is the most dangerous' finding."""
    r = modeling.fit_logistic(_data(), "heart_disease", _PREDICTORS)
    cp_terms = [t for t in r.terms if t.name.startswith("C(cp)") and "(ref)" not in t.name]
    assert len(cp_terms) == 3                              # atypical, non-anginal, typical (asymptomatic is ref)
    assert all(t.estimate < 1.0 for t in cp_terms)
