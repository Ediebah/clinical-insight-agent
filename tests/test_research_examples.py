"""Examples must describe the results the implementation actually returns."""
import importlib.util
from pathlib import Path
from types import SimpleNamespace


def test_survival_example_reports_integrated_brier_without_calling_it_skill(monkeypatch, capsys):
    path = Path(__file__).resolve().parents[1] / "examples/survival_ml.py"
    spec = importlib.util.spec_from_file_location("survival_example", path)
    survival_ml = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(survival_ml)

    result = SimpleNamespace(error=None, fit_stat="nested C-index=0.700±0.050", issues=[],
                             note="Exploratory", verdict={"winner": "Cox"}, terms=[],
                             leaderboard=[{"model": "Cox", "is_winner": True, "score": .7,
                                           "components": {"harrell_c": .7, "td_auc": .75,
                                                          "integrated_brier_score": .2}}])
    monkeypatch.setattr(survival_ml.modeling, "compare_survival_models", lambda *_a, **_k: result)
    survival_ml.main()
    output = capsys.readouterr().out.lower()
    assert "integrated brier" in output
    assert "skill" not in output
    assert "0.200" in output
