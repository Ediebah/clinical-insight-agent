# Validated on real public data

The live demo runs on synthetic EHR data (Synthea), which keeps the whole project public and free of
PHI but gives a reviewer no ground truth to check the statistics against. This example closes that gap:
it runs the agent's own models on a real, decades-analysed public dataset and confirms it reproduces
the **established** findings, not just that it runs without error.

## The dataset

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

## Why it matters

These numbers come from the same `agent/modeling.py` code the live app runs. The reproduction is
**CI-enforced**: `tests/test_validation.py` asserts the AUC stays in the published band and the key
odds ratios keep their established magnitude and direction, so a change that silently breaks the
modeling is caught against real ground truth, not just synthetic data.

You can also reproduce it interactively: open the app, choose **Bring your own data**, upload
`heart_disease_cleveland.csv`, and ask *"what predicts heart disease, adjusting for the other factors?"*
