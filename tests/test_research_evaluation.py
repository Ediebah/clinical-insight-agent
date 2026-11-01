"""Regression tests for validation boundaries and metric names."""
import numpy as np
import pandas as pd

from agent import modeling


def test_prediction_cv_does_not_preprocess_full_dataset(monkeypatch):
    rng = np.random.default_rng(12)
    frame = pd.DataFrame({"x": rng.normal(size=80), "z": rng.normal(size=80),
                          "y": np.tile([0, 1], 40)})
    monkeypatch.setattr(modeling, "_prepare", lambda *a, **k: (_ for _ in ()).throw(
        AssertionError("full-data preprocessing is prohibited")))
    result = modeling.fit_forest(frame, "y", ["x", "z"])
    assert result.error is None


def test_prediction_pipeline_handles_missing_and_unseen_categories():
    rng = np.random.default_rng(29)
    frame = pd.DataFrame({"x": rng.normal(size=80), "group": [f"site_{i}" for i in range(80)],
                          "y": np.tile([0, 1], 40)})
    frame.loc[::7, "x"] = np.nan
    result = modeling.fit_forest(frame, "y", ["x", "group"])
    assert result.error is None
    assert {term.name for term in result.terms} == {"x", "group"}


def test_nonconverged_logistic_fit_discloses_it():
    rng = np.random.default_rng(21)
    x = rng.normal(size=1200)
    result = modeling.fit_logistic(pd.DataFrame({"y": (x > 0).astype(int), "x": x}), "y", ["x"])
    assert result.error is None
    assert any("converg" in issue.lower() for issue in result.issues)


def test_nonconverged_cox_fit_discloses_it(monkeypatch):
    from pathlib import Path

    import pandas as pd
    from statsmodels.base.model import LikelihoodModel

    original_fit = LikelihoodModel.fit

    def one_iteration(self, *args, **kwargs):
        kwargs.update(maxiter=1, disp=False)
        return original_fit(self, *args, **kwargs)

    monkeypatch.setattr(LikelihoodModel, "fit", one_iteration)
    data = pd.read_csv(Path(__file__).resolve().parents[1] / "examples/heart_failure.csv")
    result = modeling.fit_cox(data, "time", "DEATH_EVENT", ["age", "serum_creatinine"])
    assert result.error is None
    assert any("converg" in issue.lower() for issue in result.issues)


def test_concurrent_cox_fits_keep_convergence_status_with_the_correct_fit(monkeypatch):
    import threading
    from pathlib import Path

    import pandas as pd
    from statsmodels.base.model import LikelihoodModel

    original_fit = LikelihoodModel.fit
    entered_a, entered_b, emitted_a, done_b = (threading.Event() for _ in range(4))
    local = threading.local()

    def controlled(self, *args, **kwargs):
        count = getattr(local, "count", 0)
        local.count = count + 1
        if count:
            return original_fit(self, *args, **kwargs)
        kwargs["disp"] = False
        if threading.current_thread().name == "A":
            entered_a.set()
            assert entered_b.wait(10)
            kwargs["maxiter"] = 1
            result = original_fit(self, *args, **kwargs)
            emitted_a.set()
            assert done_b.wait(10)
            return result
        entered_b.set()
        assert emitted_a.wait(10)
        return original_fit(self, *args, **kwargs)

    monkeypatch.setattr(LikelihoodModel, "fit", controlled)
    data = pd.read_csv(Path(__file__).resolve().parents[1] / "examples/heart_failure.csv")
    results = {}

    def run(name):
        results[name] = modeling.fit_cox(data, "time", "DEATH_EVENT", ["age", "serum_creatinine"])
        if name == "B":
            done_b.set()

    a = threading.Thread(target=run, args=("A",), name="A")
    b = threading.Thread(target=run, args=("B",), name="B")
    a.start()
    assert entered_a.wait(10)
    b.start()
    a.join(20)
    b.join(20)
    assert not a.is_alive() and not b.is_alive()
    assert results["A"].error is None and results["B"].error is None
    assert any("converg" in issue.lower() for issue in results["A"].issues)
    assert not any("converg" in issue.lower() for issue in results["B"].issues)


def test_survival_reports_integrated_brier_score_not_skill():
    from sklearn.model_selection import KFold
    from sksurv.linear_model import CoxPHSurvivalAnalysis
    from sksurv.util import Surv
    rng = np.random.default_rng(8)
    x = rng.normal(size=(90, 2))
    y = Surv.from_arrays(rng.random(90) > .2, rng.uniform(1, 20, 90))
    metrics, _ = modeling._survival_composite_cv(CoxPHSurvivalAnalysis, {}, x, y, KFold(3))
    assert "integrated_brier_score" in metrics
    assert "brier_skill" not in metrics


def test_survival_preparation_does_not_impute_before_split(monkeypatch):
    rng = np.random.default_rng(11)
    frame = pd.DataFrame({"x": rng.normal(size=60), "z": rng.normal(size=60),
                          "duration": rng.uniform(1, 10, 60), "event": np.tile([0, 1], 30)})
    frame.loc[0, "x"] = np.nan
    monkeypatch.setattr(modeling, "_prepare", lambda *a, **k: (_ for _ in ()).throw(
        AssertionError("full-data preprocessing is prohibited")))
    _, _, _, x, _, error = modeling._survival_xy(frame, "duration", "event", ["x", "z"], "rsf")
    assert error is None and x.isna().any().any()


def test_auto_risk_does_not_choose_model_using_all_outcomes(monkeypatch):
    rng = np.random.default_rng(14)
    frame = pd.DataFrame({"x": rng.normal(size=80), "z": rng.normal(size=80),
                          "y": np.tile([0, 1], 40)})
    monkeypatch.setattr(modeling, "compare_models", lambda *a, **k: (_ for _ in ()).throw(
        AssertionError("selection must be nested")))
    result = modeling.failure_analysis(frame, "y", ["x", "z"], model="auto")
    assert result.error is None


def test_model_selection_reports_nested_out_of_sample_performance():
    rng = np.random.default_rng(15)
    x = rng.normal(size=100)
    frame = pd.DataFrame({"x": x, "z": rng.normal(size=100), "y": (x > 0).astype(int)})
    result = modeling.compare_models(frame, "y", ["x", "z"])
    assert result.error is None
    assert result.robustness["evaluation"] == "nested_cross_validation"
    assert "outer_score" in result.robustness
    assert all("component_std" in row for row in result.leaderboard)


def test_survival_model_comparison_handles_missing_values_with_nested_cv(monkeypatch):
    rng = np.random.default_rng(23)
    n = 90
    frame = pd.DataFrame({"x": rng.normal(size=n), "z": rng.normal(size=n),
                          "duration": rng.uniform(1, 20, n), "event": np.tile([0, 1, 1], 30)})
    frame.loc[::10, "x"] = np.nan
    monkeypatch.setattr(modeling, "_RSF_GRID", {"n_estimators": [10], "min_samples_leaf": [5],
                                                "max_features": ["sqrt"]})
    result = modeling.compare_survival_models(frame, "duration", "event", ["x", "z"])
    assert result.error is None
    assert result.robustness["evaluation"] == "nested_cross_validation"
    assert all("integrated_brier_score" in row["components"] for row in result.leaderboard)
