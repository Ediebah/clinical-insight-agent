from agent import causal_simulation, modeling


def test_uplift_reports_propensity_clipping():
    frame = causal_simulation.generate(seed=3, n=300, scenario="unequal")
    result = modeling.fit_uplift(frame, "outcome", "treatment", ["x", "z"])
    assert result.error is None
    assert 0 <= result.robustness["propensity"]["clipped_fraction"] <= 1
    assert result.robustness["propensity"]["bounds"] == [0.025, 0.975]


def test_simulation_measures_bias_and_coverage_against_known_effect():
    report = causal_simulation.evaluate(replicates=2, n=300, seed=4, scenarios=["unequal"])
    row = report[0]
    assert row["true_effect"] == 2.0
    assert row["successful"] == 2
    assert 0 <= row["coverage"] <= 1
    assert row["oracle"]["successful"] == 2
    assert 0 <= row["oracle"]["coverage"] <= 1


def test_misspecified_scenario_omits_a_true_confounder():
    frame = causal_simulation.generate(seed=7, n=300, scenario="misspecified")
    assert "oracle_u" in frame
    estimate, lower, upper = causal_simulation.oracle(frame, "misspecified")
    assert lower <= estimate <= upper


def test_causal_cross_fitting_does_not_encode_categories_before_folds(monkeypatch):
    frame = causal_simulation.generate(seed=8, n=300, scenario="unequal")
    frame["group"] = [f"category_{i % 7}" for i in range(len(frame))]
    monkeypatch.setattr(modeling.pd, "get_dummies", lambda *a, **k: (_ for _ in ()).throw(
        AssertionError("full-data encoding")))
    result = modeling.fit_uplift(frame, "outcome", "treatment", ["x", "group"])
    assert result.error is None
