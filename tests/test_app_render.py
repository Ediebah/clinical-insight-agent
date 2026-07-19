"""Regression: app._render_model must render every model_type without crashing.

app.py has its OWN markdown renderer, separate from modeling.render(). The model-selection engine and the
evaluation lenses produce result shapes (a leaderboard, a `robustness={"task": ...}` marker, net-benefit
and calibration series) that this renderer had never seen — and a KeyError on `robustness['verdict']`
reached the deployed app. These tests exercise the real renderer on those shapes so it can't regress.
"""
import warnings
from pathlib import Path

import pandas as pd
import pytest

warnings.filterwarnings("ignore")
app = pytest.importorskip("app")   # imports the Streamlit app in bare mode (module-level st.* are no-ops)

from agent import modeling  # noqa: E402

_CSV = Path(__file__).resolve().parent.parent / "examples" / "heart_disease_cleveland.csv"
_PREDS = ["age", "sex", "cp", "trestbps", "chol", "thalach", "exang", "oldpeak", "ca", "thal"]


def _hd() -> pd.DataFrame:
    return pd.read_csv(_CSV)


def test_render_model_selection_shows_the_leaderboard_without_crashing():
    out = app._render_model(modeling.compare_models(_hd(), "heart_disease", _PREDS).as_dict())
    assert "MODEL_SELECTION" in out and "Picked" in out
    assert "logistic regression" in out and "random forest" in out    # leaderboard rows render


def test_render_decision_curve_without_crashing():
    out = app._render_model(
        modeling.decision_curve(_hd(), "heart_disease", _PREDS, model="logistic").as_dict())
    assert "DECISION_CURVE" in out and "net benefit" in out


def test_render_failure_analysis_without_crashing():
    out = app._render_model(
        modeling.failure_analysis(_hd(), "heart_disease", _PREDS, model="logistic").as_dict())
    assert "FAILURE_ANALYSIS" in out and "calibration" in out.lower()
