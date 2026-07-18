# Validated on real public data

The live demo runs on synthetic EHR data (Synthea), which keeps the whole project public and free of
PHI but gives a reviewer no ground truth to check the statistics against. These examples close that
gap: they run the agent's own models on real, already-analysed public data and confirm it reproduces
the **established** findings, not just that it runs without error. Each one is CI-enforced in
`tests/test_validation.py`, so a change that silently breaks the modeling is caught against real
ground truth.

| Example | Agent method | Real source | Reproduced |
|---|---|---|---|
| `heart_disease_validation.py` | logistic regression + random forest | UCI Cleveland heart disease | `ca` OR 3.07, AUC 0.90 |
| `heart_failure_survival.py` | Cox PH + Kaplan-Meier | UCI Heart Failure Clinical Records | ejection-fraction HR 0.95, creatinine HR 1.36 |
| `bayesian_interim_futility.py` | Bayesian interim go/no-go | Chen & Chen (2019), phase II worked example | predictive probability 0.105 |

## 1. Logistic regression — the dataset

`heart_disease_cleveland.csv` — the Cleveland subset of the UCI Heart Disease dataset (297 complete
cases of the 303 raw rows; the 6 with a missing vessel count or thalassemia value are dropped).

- Source: [UCI Machine Learning Repository, Heart Disease](https://archive.ics.uci.edu/dataset/45/heart+disease)
- Origin: Detrano R. et al. (1989), *International application of a new probability algorithm for the
  diagnosis of coronary artery disease*, American Journal of Cardiology 64:304–310.
- Public and redistributable for research with citation. Only the 14 canonical columns are used; the
  `num` field (0–4 disease severity) is binarised to `heart_disease` (0 = none, 1 = any disease), and
  the categorical fields (`sex`, `cp`, `exang`, `thal`) are given readable labels.

## What the agent reproduces

Run it:

```bash
.venv/bin/python examples/heart_disease_validation.py
```

The agent's logistic model recovers the settled coronary-artery-disease risk factors, with the right
directions and significance:

| Predictor | Adjusted OR | Established finding |
|---|---|---|
| Number of diseased vessels (`ca`) | **3.07** (p < 0.0001) | the single strongest marker of disease |
| Male sex | **3.92** (p = 0.006) | higher CAD prevalence in men |
| Asymptomatic chest pain | reference (highest risk) | the most dangerous presentation; all other types sit at lower odds |
| ST depression (`oldpeak`) | **1.70** (p = 0.009) | ischemia on exertion |
| Max heart rate (`thalach`) | **0.98** (p = 0.017) | lower exercise capacity signals disease (inverse) |

The random forest reaches a cross-validated **AUC of 0.90**, inside the published 0.84–0.91 band for
this dataset, with `ca`, `thal`, `sex`, `exang`, and `oldpeak` as the top features.

You can also reproduce it interactively: open the app, choose **Bring your own data**, upload
`heart_disease_cleveland.csv`, and ask *"what predicts heart disease, adjusting for the other factors?"*

## 2. Cox regression and survival — the dataset

`heart_failure.csv` — the UCI Heart Failure Clinical Records dataset (299 patients with a follow-up
time and a death event), the cohort of Ahmad et al. (2017) analysed by Chicco & Jurman (2020).

- Source: [UCI Machine Learning Repository, Heart Failure Clinical Records](https://archive.ics.uci.edu/dataset/519/heart+failure+clinical+records)
- Origin: Chicco D., Jurman G. (2020), *Machine learning can predict survival of patients with heart
  failure from serum creatinine and ejection fraction alone*, BMC Medical Informatics and Decision
  Making 20:16.
- `time` is the follow-up period in days, `DEATH_EVENT` the event indicator; `ef_group` splits ejection
  fraction at the 40% HFrEF clinical cutoff for the Kaplan-Meier curves.

Run it:

```bash
.venv/bin/python examples/heart_failure_survival.py
```

The agent's Cox model recovers the settled time-to-event mortality predictors, and its Kaplan-Meier
curves separate reduced from preserved ejection fraction:

| Predictor | Adjusted HR | Established finding |
|---|---|---|
| Ejection fraction | **0.95** per % (p < 0.0001) | the top predictor; a stronger heart lowers mortality |
| Serum creatinine | **1.36** (p < 0.0001) | worse renal function raises mortality |
| Age | **1.05** per year (p < 0.0001) | older patients die sooner |

Ejection fraction and serum creatinine are exactly the two variables Chicco & Jurman single out as
sufficient to predict survival. Kaplan-Meier survival ends near **0.50** for reduced-EF (< 40%)
patients versus **0.74** for preserved-EF.

## 3. Bayesian go/no-go — the reference

The Bayesian decision engine reasons over response counts, not a table of rows, so its ground truth is
a *published calculation* rather than a dataset. `bayesian_interim_futility.py` reproduces the worked
interim-futility example of Chen & Chen (2019).

- Reference: Chen D.-G., Chen J.D. (2019), *Application of Bayesian predictive probability for interim
  futility analysis in single-arm phase II trial*, Translational Cancer Research 8(Suppl 4):S404–S411.
- The design: single-arm phase II, response worth pursuing only if the true rate exceeds 30%; success
  is declared when the posterior P(rate > 0.30) exceeds 0.95 under a non-informative Beta(1,1) prior;
  50 patients planned with an interim look after 25.

Run it:

```bash
.venv/bin/python examples/bayesian_interim_futility.py
```

At the interim look of **8 responders in 25**, the paper reports a predictive probability of success of
**0.105** — 13 or more of the remaining 25 would be needed to reach the winning boundary of 21/50. The
agent's own interim entry point (`modeling.fit_interim`, the call the app makes for a *"continue or
stop?"* question) returns **0.1045**, the same number to three decimals.

## Why it matters

Every number above comes from the same `agent/modeling.py` code the live app runs, and every one is
**CI-enforced** in `tests/test_validation.py`: the AUC stays in the published band, the odds ratios and
hazard ratios keep their established magnitude and direction, and the predictive probability stays
within 0.001 of the published value. A change that silently breaks the modeling is caught against real
ground truth, not just synthetic data.
