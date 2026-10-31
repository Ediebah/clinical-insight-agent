"""Each check fires when it should, stays quiet when it should not, and says so when it cannot run."""
import numpy as np
import pandas as pd
import pytest

import caveat
from caveat import Config, Session, analyze, render


def kinds(rep):
    return set(rep.kinds())


def skipped_checks(rep):
    return {s.check for s in rep.skipped}


# ───────────────────────────── proportions ─────────────────────────────
def test_small_sample_fires_and_escalates_below_tiny_n():
    df = pd.DataFrame({"g": ["a", "b"], "k": [12, 4], "n": [309, 8]})
    rep = analyze(df, numerator="k", denominator="n")
    assert "small_sample" in kinds(rep)
    assert rep.of_kind("small_sample")[0].severity == "caution"     # n=8 < tiny_n


def test_small_sample_quiet_when_all_groups_are_large():
    df = pd.DataFrame({"g": ["a", "b"], "k": [100, 120], "n": [1000, 1100]})
    assert "small_sample" not in kinds(analyze(df, numerator="k", denominator="n"))


def test_contrasts_reports_a_real_difference_with_a_ci():
    df = pd.DataFrame({"g": ["a", "b"], "k": [200, 50], "n": [1000, 1000]})
    rep = analyze(df, "compare a and b", numerator="k", denominator="n")
    f = rep.of_kind("contrasts")[0]
    assert f.severity == "warn" and "risk difference" in f.message and "CI" in f.message


def test_contrasts_says_noise_and_reports_the_mde_when_nothing_survives():
    """The addition that matters: 'no difference' is only meaningful next to what was detectable."""
    df = pd.DataFrame({"g": ["a", "b"], "k": [100, 105], "n": [1000, 1000]})
    rep = analyze(df, "compare a and b", numerator="k", denominator="n")
    f = rep.of_kind("contrasts")[0]
    assert f.severity == "info" and "within noise" in f.message
    assert "smallest difference" in f.message and "underpowered" in f.message


def test_contrasts_skips_with_a_reason_when_roles_are_missing():
    df = pd.DataFrame({"label": ["a", "b"], "score": [1.5, 2.5]})
    rep = analyze(df, "compare")
    assert "contrasts" in skipped_checks(rep)
    reason = next(s for s in rep.skipped if s.check == "contrasts")
    assert "numerator" in reason.reason and "numerator=" in reason.fix


def test_contrasts_refuses_rather_than_crawling_on_a_huge_frame():
    df = pd.DataFrame({"g": [str(i) for i in range(200)], "k": [1] * 200, "n": [10] * 200})
    rep = analyze(df, "which is highest?", numerator="k", denominator="n",
                  config=Config(max_contrast_rows=60))
    assert "contrasts" in skipped_checks(rep)
    # the cheaper multiplicity warning still fires, so the user is not left with nothing
    assert "multiple_comparisons" in kinds(rep)


def test_contrasts_stay_quiet_on_a_question_that_is_not_a_comparison():
    """Pairwise FDR answers 'do these differ', which is only worth saying if someone asked. On a
    listing query it is noise dressed as rigour."""
    df = pd.DataFrame({"payer": ["Aetna", "Cigna"], "members": [500, 510],
                       "total_eligible": [1000, 1000]})
    rep = analyze(df, "List members and eligibility for each payer")
    assert "contrasts" not in kinds(rep)
    s = next(s for s in rep.skipped if s.check == "contrasts")
    assert "not read as a comparison" in s.reason


def test_contrasts_run_when_no_question_is_supplied_at_all():
    """No question is no signal either way, so the caller gets the analysis rather than silence."""
    df = pd.DataFrame({"payer": ["Aetna", "Cigna"], "members": [500, 510],
                       "total_eligible": [1000, 1000]})
    assert "contrasts" in kinds(analyze(df))


def test_confounding_does_not_fire_on_a_bare_count_outcome():
    """A raw event count across differently-sized groups is a denominator problem, not a
    confounding one; treating it as an outcome fires on almost any table with a count in it."""
    df = pd.DataFrame({"treatment": ["A", "B"], "cases": [81, 234], "total": [87, 270]})
    rep = analyze(df, "which treatment has the higher success rate?")
    assert "confounding" not in kinds(rep)
    s = next(s for s in rep.skipped if s.check == "confounding")
    assert "bare count is not an outcome" in s.fix


def test_boundary_rate_flags_zero_and_full_cells():
    df = pd.DataFrame({"g": ["a", "b", "c"], "k": [0, 10, 5], "n": [30, 10, 30]})
    rep = analyze(df, numerator="k", denominator="n")
    f = rep.of_kind("boundary_rate")[0]
    assert "0/30" in f.message and "10/10" in f.message
    assert f.severity == "warn"


def test_winners_curse_flags_a_top_group_that_is_also_tiny():
    df = pd.DataFrame({"g": ["a", "b", "c", "d"], "k": [4, 100, 90, 80],
                       "n": [5, 400, 400, 400]})
    rep = analyze(df, "which group is highest?", numerator="k", denominator="n")
    f = rep.of_kind("winners_curse")[0]
    assert f.severity == "caution" and "sample-size artifact" in f.message


def test_winners_curse_quiet_when_the_leader_is_well_powered():
    df = pd.DataFrame({"g": ["a", "b", "c"], "k": [300, 100, 90], "n": [400, 400, 400]})
    assert "winners_curse" not in kinds(analyze(df, "which is highest?",
                                                numerator="k", denominator="n"))


def test_missing_denominator_fires_on_a_bare_rate():
    df = pd.DataFrame({"g": ["a", "b"], "prevalence_pct": [3.9, 37.3]})
    assert "missing_denominator" in kinds(analyze(df, "prevalence by group"))


def test_inconsistent_rate_warns_and_withholds_count_contrasts():
    df = pd.DataFrame({"g": ["a", "b"], "k": [10, 20], "n": [50, 50], "rate": [.1, .2]})
    rep = analyze(df, "compare", group="g", numerator="k", denominator="n", rate="rate")
    assert "rate_denominator_mismatch" in kinds(rep)
    assert "contrasts" not in kinds(rep)
    assert "contrasts" in skipped_checks(rep)
    assert "adjusted" in rep.of_kind("rate_denominator_mismatch")[0].message


@pytest.mark.parametrize("rates", [[.2, .4], [20.0, 40.0], [.201, .399], [20.1, 39.9]])
def test_consistent_fraction_or_percent_rate_allows_contrasts(rates):
    df = pd.DataFrame({"g": ["a", "b"], "k": [10, 20], "n": [50, 50], "rate": rates})
    rep = analyze(df, "compare", group="g", numerator="k", denominator="n", rate="rate")
    assert "rate_denominator_mismatch" not in kinds(rep)
    assert "contrasts" in kinds(rep)


def test_custom_contrast_check_cannot_bypass_rate_consistency():
    df = pd.DataFrame({"g": ["a", "b"], "k": [10, 20], "n": [50, 50], "rate": [.1, .2]})
    rep = analyze(df, "compare", group="g", numerator="k", denominator="n", rate="rate",
                  checks=["contrasts"])
    assert "rate_denominator_mismatch" in kinds(rep)
    assert "contrasts" not in kinds(rep)
    assert "contrasts" in skipped_checks(rep)


@pytest.mark.parametrize("rates", [[20.0, 27.0], [120.0, 80.0]])
def test_adjusted_or_other_units_are_not_declared_wrong(rates):
    df = pd.DataFrame({"g": ["a", "b"], "k": [10, 20], "n": [50, 50], "rate": rates})
    rep = analyze(df, "compare", group="g", numerator="k", denominator="n", rate="rate")
    message = rep.of_kind("rate_denominator_mismatch")[0].message
    assert "may be adjusted" in message and "cannot determine which value is correct" in message
    assert {"contrasts", "boundary_rate", "winners_curse", "simpsons"} <= skipped_checks(rep)


@pytest.mark.parametrize("k,n,rate", [(10, 0, .1), (60, 50, .1), (np.nan, 50, .1),
                                      (10, 50, np.nan), (np.inf, 50, .1), (10.5, 50, .1)])
def test_invalid_or_missing_rate_inputs_withhold_count_contrasts(k, n, rate):
    df = pd.DataFrame({"g": ["a", "b"], "k": [10, k], "n": [50, n], "rate": [.2, rate]})
    rep = analyze(df, "compare", group="g", numerator="k", denominator="n", rate="rate")
    assert "rate_denominator_unverifiable" in kinds(rep)
    assert "contrasts" not in kinds(rep)
    assert "contrasts" in skipped_checks(rep)


def test_multiple_comparisons_defers_to_contrasts_when_they_ran():
    df = pd.DataFrame({"g": [str(i) for i in range(12)], "k": [5] * 12, "n": [100] * 12})
    rep = analyze(df, "which group is highest?", numerator="k", denominator="n")
    assert "contrasts" in kinds(rep)
    assert "multiple_comparisons" not in kinds(rep)   # already corrected, rigorously


# ───────────────────────────── continuous ─────────────────────────────
def test_skew_reports_median_iqr_and_a_bootstrap_interval():
    rng = np.random.default_rng(0)
    df = pd.DataFrame({"cost": rng.lognormal(7.0, 1.0, size=200)})
    f = analyze(df, measure="cost").of_kind("skew")[0]
    assert "right-skewed" in f.message and "Median=" in f.message and "IQR" in f.message


def test_skew_flags_a_mean_with_no_dispersion():
    df = pd.DataFrame({"g": ["a", "b"], "avg_cost": [1200.0, 1500.0]})
    f = analyze(df).of_kind("skew")[0]
    assert "without any dispersion" in f.message


def test_mean_contrasts_finds_a_real_difference_between_groups():
    """The half of analytics that had no rigorous contrast before."""
    rng = np.random.default_rng(0)
    df = pd.DataFrame({
        "arm": ["a"] * 60 + ["b"] * 60,
        "spend": list(rng.normal(100, 10, 60)) + list(rng.normal(140, 10, 60)),
    })
    f = analyze(df, "compare spend by arm", group="arm", measure="spend").of_kind("mean_contrasts")[0]
    assert f.severity == "warn" and "survive BH-FDR" in f.message


def test_mean_contrasts_reports_noise_when_groups_match():
    rng = np.random.default_rng(0)
    df = pd.DataFrame({"arm": ["a"] * 60 + ["b"] * 60,
                       "spend": list(rng.normal(100, 10, 120))})
    f = analyze(df, "compare spend", group="arm", measure="spend").of_kind("mean_contrasts")[0]
    assert f.severity == "info" and "within noise" in f.message


def test_mean_contrasts_skips_on_pre_aggregated_rows():
    """One row per group is a table of means, not the observations needed to compare them."""
    df = pd.DataFrame({"arm": ["a", "b"], "spend": [100.0, 140.0]})
    rep = analyze(df, "compare spend", group="arm", measure="spend")
    s = next(s for s in rep.skipped if s.check == "mean_contrasts")
    assert "per-observation rows" in s.fix


# ───────────────────────────── structural ─────────────────────────────
def test_simpsons_detects_a_reversal_inside_strata():
    df = pd.DataFrame({"treatment": ["A", "B", "A", "B"],
                       "severity": ["mild", "mild", "severe", "severe"],
                       "cases": [81, 234, 192, 55],
                       "total": [87, 270, 263, 80]})
    rep = analyze(df, "which treatment has the higher success rate?",
                  group="treatment", stratifier="severity",
                  numerator="cases", denominator="total")
    assert rep.of_kind("simpsons")[0].severity == "caution"


def test_simpsons_skips_without_a_stratifier_and_says_how_to_enable():
    df = pd.DataFrame({"g": ["a", "b"], "k": [1, 2], "n": [10, 20]})
    rep = analyze(df, "which is higher?", numerator="k", denominator="n", stratifier=None)
    s = next((s for s in rep.skipped if s.check == "simpsons"), None)
    assert s is not None and "stratifier=" in s.fix


def test_confounding_needs_a_comparison_question():
    df = pd.DataFrame({"g": ["a", "b"], "rate": [0.1, 0.3], "k": [10, 30], "n": [100, 100]})
    assert "confounding" in kinds(analyze(df, "which group has the higher rate?"))
    quiet = analyze(df, "list the groups")
    assert "confounding" not in kinds(quiet)
    assert "confounding" in skipped_checks(quiet)


def test_confounding_names_configured_domain_confounders():
    df = pd.DataFrame({"g": ["a", "b"], "rate": [0.1, 0.3], "k": [10, 30], "n": [100, 100]})
    cfg = Config(confounders=("age", "sex", "comorbidity burden"))
    f = analyze(df, "which group is higher?", config=cfg).of_kind("confounding")[0]
    assert "comorbidity burden" in f.message


def test_confounding_is_domain_neutral_by_default():
    df = pd.DataFrame({"g": ["a", "b"], "rate": [0.1, 0.3], "k": [10, 30], "n": [100, 100]})
    f = analyze(df, "which group is higher?").of_kind("confounding")[0]
    assert "patient" not in f.message.lower() and "composition" in f.message


def test_missing_data_flags_and_scales_severity():
    df = pd.DataFrame({"g": list("abcdefghij"),
                       "v": [1, 2, None, None, None, 6, 7, 8, 9, 10]})
    f = analyze(df).of_kind("missing_data")[0]
    assert "30% missing" in f.message and f.severity == "warn"


# ───────────────────────────── report plumbing ─────────────────────────────
def test_empty_frame_returns_an_explicit_finding_not_silence():
    rep = analyze(pd.DataFrame())
    assert rep.kinds() == ["empty_result"]
    assert "not a finding of zero" in rep.findings[0].message


def test_report_is_iterable_truthy_and_reports_worst_severity():
    df = pd.DataFrame({"g": ["a", "b"], "k": [12, 4], "n": [309, 8]})
    rep = analyze(df, numerator="k", denominator="n")
    assert bool(rep) and len(rep) == len(list(rep))
    assert rep.worst() == "caution"


def test_clean_report_is_falsy_and_has_no_worst():
    df = pd.DataFrame({"g": ["a", "b"], "k": [100, 105], "n": [1000, 1000]})
    rep = analyze(df, numerator="k", denominator="n", checks=["small_sample", "winners_curse"])
    assert not rep and rep.worst() is None


def test_unknown_check_name_raises():
    with pytest.raises(ValueError, match="unknown check"):
        analyze(pd.DataFrame({"a": [1]}), checks=["nope"])


def test_strict_mode_surfaces_a_failing_check_instead_of_hiding_it(monkeypatch):
    """Off by default so a caveat library can never break a caller's analysis; on for tests."""
    def boom(ctx):
        raise RuntimeError("kaboom")
    monkeypatch.setitem(caveat.CHECKS, "small_sample", boom)
    df = pd.DataFrame({"g": ["a"], "k": [1], "n": [10]})
    rep = analyze(df, checks=["small_sample"])
    assert "kaboom" in next(s for s in rep.skipped if s.check == "small_sample").reason
    with pytest.raises(RuntimeError):
        analyze(df, checks=["small_sample"], strict=True)


def test_render_is_ascii_by_default_and_can_show_skips():
    df = pd.DataFrame({"g": ["a", "b"], "k": [12, 4], "n": [309, 8]})
    rep = analyze(df, numerator="k", denominator="n")
    out = render(rep)
    assert out.isascii() and "[small_sample]" in out
    assert "[skipped]" in render(rep, show_skipped=True)


# ───────────────────────────── session multiplicity ─────────────────────────────
def test_session_warns_once_enough_looking_has_happened():
    """Nothing else flags this, because nothing else sees the sequence."""
    df = pd.DataFrame({"g": list("abcde"), "k": [5, 6, 7, 8, 9], "n": [100] * 5})
    s = Session(warn_after_tests=15)
    reports = [s.analyze(df, "which is highest?", numerator="k", denominator="n")
               for _ in range(3)]
    assert "session_multiplicity" not in reports[0].kinds()      # 10 tests
    assert "session_multiplicity" in reports[-1].kinds()         # 30 tests
    assert s.tests_run == 30 and s.families == 3


def test_session_reset_clears_accumulated_multiplicity():
    df = pd.DataFrame({"g": list("abcde"), "k": [5, 6, 7, 8, 9], "n": [100] * 5})
    s = Session(warn_after_tests=15)
    for _ in range(3):
        s.analyze(df, "which is highest?", numerator="k", denominator="n")
    s.reset()
    assert s.tests_run == 0
    assert "session_multiplicity" not in s.analyze(
        df, "which is highest?", numerator="k", denominator="n").kinds()
