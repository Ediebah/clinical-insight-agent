"""Validation on real public data (keyless, no LLM).

The agent must not merely *run* on real inputs; it must reproduce the *established* findings. This file
is the "judged against the literature" guardrail across the agent's statistical methods: if a change
silently breaks the modeling, CI catches it against real ground truth, not synthetic data. Three
independent literatures are pinned here:

  * Logistic + random forest — UCI Cleveland heart-disease dataset (Detrano et al., 1989). The
    dominant coronary-artery-disease predictors (diseased vessels ``ca``, asymptomatic chest pain,
    male sex, ST depression ``oldpeak``, max heart rate ``thalach`` inverse) and the achievable
    discrimination (AUC ~0.84–0.91) are long settled. Data: ``examples/heart_disease_cleveland.csv``.
  * Cox proportional hazards + Kaplan-Meier — UCI Heart Failure Clinical Records (Chicco & Jurman,
    2020). Lower ejection fraction and higher serum creatinine are the headline mortality predictors.
    Data: ``examples/heart_failure.csv``.
  * Bayesian interim go/no-go — reproduces the published predictive-probability futility calculation
    of Chen & Chen (2019), a single-arm phase II worked example, to within 0.001.
"""
import re
from pathlib import Path

import pandas as pd

from agent import bayes, modeling

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


# ── Cox / survival: UCI Heart Failure Clinical Records (Chicco & Jurman 2020) ──────────────────────
_HF_CSV = Path(__file__).resolve().parent.parent / "examples" / "heart_failure.csv"
_HF_PREDICTORS = ["age", "ejection_fraction", "serum_creatinine", "serum_sodium",
                  "high_blood_pressure", "sex"]


def _hf() -> pd.DataFrame:
    return pd.read_csv(_HF_CSV)


def test_heart_failure_dataset_is_present_and_is_time_to_event():
    d = _hf()
    assert len(d) == 299
    assert set(["time", "DEATH_EVENT", "ejection_fraction", "serum_creatinine"]).issubset(d.columns)
    assert d["DEATH_EVENT"].isin([0, 1]).all()
    assert (d["time"] > 0).all()


def test_cox_recovers_the_established_heart_failure_hazard_ratios():
    r = modeling.fit_cox(_hf(), "time", "DEATH_EVENT", _HF_PREDICTORS)
    assert r.error is None

    ef = _term(r, "ejection_fraction")                    # higher EF lowers mortality (the top predictor)
    assert ef.estimate < 1.0 and ef.p < 0.01

    creat = _term(r, "serum_creatinine")                  # higher creatinine raises mortality
    assert creat.estimate > 1.0 and creat.p < 0.01

    age = _term(r, "age")
    assert age.estimate > 1.0 and age.p < 0.01


def test_kaplan_meier_separates_reduced_from_preserved_ejection_fraction():
    r = modeling.fit_survival(_hf(), "time", "DEATH_EVENT", predictors=None, group="ef_group")
    assert r.error is None and r.km
    final = {g: [p for p in r.km if p["group"] == g][-1]["survival"]
             for g in {p["group"] for p in r.km}}
    assert final["EF < 40 (reduced)"] < final["EF >= 40"]   # reduced EF -> worse survival


# ── Bayesian go/no-go: reproduce a published interim-futility calculation (Chen & Chen 2019) ──────────
def test_interim_reproduces_the_published_predictive_probability():
    # Chen & Chen (2019), single-arm phase II: p0=0.30, success if P(rate>0.30)>0.95, Beta(1,1) prior,
    # 50 planned with an interim after 25. At 8/25 the paper reports a predictive probability of 0.105.
    interim = pd.DataFrame({"response": [1] * 8 + [0] * 17})
    mr = modeling.fit_interim(interim, "response", n_planned=50, tv=0.30, lrv=0.30,
                              gate_tv=0.95, gate_lrv=0.95, stop_lrv=0.0, prior_a=1, prior_b=1)
    assert mr.error is None
    assert abs(mr.verdict["predictive_prob"] - 0.105) < 0.001


def test_interim_final_success_boundary_matches_the_paper():
    # The paper needs 13 more of the remaining 25 on top of the 8 already seen -> 21 of 50 to win.
    prior = bayes.Prior("Vague", "beta", (1.0, 1.0), "non-informative Beta(1,1)")
    rule = bayes.DecisionRule(tv=0.30, lrv=0.30, gate_tv=0.95, gate_lrv=0.95, stop_lrv=0.0)
    go = bayes.go_grid_binary(prior, 50, rule)
    assert next(r for r in range(51) if go[r] == 1) == 21
