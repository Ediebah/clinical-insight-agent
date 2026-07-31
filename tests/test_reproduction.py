"""Tests for published-design extraction and exact deterministic reproduction."""

import pytest

from agent import reproduction


def _chen_spec():
    return {
        "publication_title": "Chen et al. (2019)",
        "doi": "10.21037/tcr.2019.05.17",
        "endpoint_type": "single_arm_binary",
        "observed_successes": 8,
        "observed_n": 25,
        "planned_n": 50,
        "prior_a": 1,
        "prior_b": 1,
        "efficacy_reference": 0.30,
        "efficacy_gate": 0.95,
        "futility_cutoff": 0.20,
        "published_predictive_probability": 0.105,
        "published_final_boundary": 21,
        "published_decision": "STOP",
    }


def test_parser_extracts_only_supplied_values_and_normalizes_percentages(monkeypatch):
    captured = {}

    def fake_complete_json(system, user, temperature=0):
        captured.update(system=system, user=user, temperature=temperature)
        return {
            "publication_title": "A trial design",
            "doi": "https://doi.org/10.1234/example.1",
            "endpoint_type": "single_arm_binary",
            "observed_successes": 8,
            "observed_n": 25,
            "planned_n": 50,
            "prior_a": 1,
            "prior_b": 1,
            "efficacy_reference": "30%",
            "efficacy_gate": 95,
            "futility_cutoff": None,
            "published_predictive_probability": None,
            "published_final_boundary": None,
            "published_decision": None,
        }

    monkeypatch.setattr(reproduction.llm, "complete_json", fake_complete_json)
    spec = reproduction.parse_published_design(
        "A sufficiently detailed published design description with interim and final decision rules."
    )

    assert spec["doi"] == "10.1234/example.1"
    assert spec["efficacy_reference"] == 0.30
    assert spec["efficacy_gate"] == 0.95
    assert spec["futility_cutoff"] is None
    assert spec["missing_fields"] == ["futility_cutoff"]
    assert "Do not calculate, reconstruct, or guess" in captured["system"]
    assert captured["temperature"] == 0


def test_parser_rejects_too_little_source_text():
    with pytest.raises(ValueError, match="enough design text"):
        reproduction.parse_published_design("8 of 25")


def test_confirmed_spec_requires_every_computation_field():
    spec = _chen_spec()
    spec["efficacy_gate"] = ""
    with pytest.raises(ValueError, match="efficacy_gate is required"):
        reproduction.validate_reproduction_spec(spec)


def test_confirmed_spec_rejects_invalid_interim_counts():
    spec = _chen_spec()
    spec["observed_successes"] = 26
    with pytest.raises(ValueError, match="between zero"):
        reproduction.validate_reproduction_spec(spec)


def test_confirmed_spec_rejects_design_above_exact_enumeration_cap():
    spec = _chen_spec()
    spec["planned_n"] = spec["observed_n"] + reproduction.bayes.MAX_ENUM + 1
    with pytest.raises(ValueError, match="exact reproduction workflow"):
        reproduction.validate_reproduction_spec(spec)


def test_chen_reproduction_matches_probability_boundary_and_decision():
    result = reproduction.run_reproduction(_chen_spec())

    assert result["computed"]["predictive_probability"] == pytest.approx(0.10450076393566671)
    assert result["computed"]["final_boundary"] == 21
    assert result["computed"]["responses_needed"] == 13
    assert result["computed"]["decision"] == "STOP"
    assert result["computed"]["posterior_mean"] == pytest.approx(1 / 3)
    assert result["overall_match"] is True
    assert all(row["match"] is True for row in result["comparisons"])
    assert len(result["audit_fingerprint"]) == 64


def test_editing_futility_cutoff_changes_the_reproduced_decision():
    spec = _chen_spec()
    spec["futility_cutoff"] = 0.10

    result = reproduction.run_reproduction(spec)

    assert result["computed"]["predictive_probability"] == pytest.approx(0.10450076393566671)
    assert result["computed"]["decision"] == "CONSIDER"
    assert result["overall_match"] is False
    decision = next(row for row in result["comparisons"] if row["metric"] == "Interim decision")
    assert decision["match"] is False


def test_invalid_doi_is_not_rendered_as_a_link():
    assert reproduction.doi_url("10.21037/tcr.2019.05.17") == \
        "https://doi.org/10.21037/tcr.2019.05.17"
    assert reproduction.doi_url("javascript:alert(1)") is None
