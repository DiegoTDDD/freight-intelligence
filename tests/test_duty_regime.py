import copy

import pytest
from fastapi.testclient import TestClient

from freight_intelligence.api.app import create_app
from freight_intelligence.optimization.weekly_duty import example_history, review_week


@pytest.mark.parametrize("regime", [None, "unknown", "collective_or_exempt"])
@pytest.mark.parametrize("example", ["balanced_week", "night_limit_exceeded", "seven_workdays", "short_daily_rest"])
def test_unknown_special_or_omitted_regime_never_receives_standard_reference_verdicts(regime, example):
    history = example_history(example)
    original = review_week(history)
    if regime is None:
        del history["employment_regime"]
    else:
        history["employment_regime"] = regime
    before = copy.deepcopy(history)
    result = review_week(history)
    assert history == before
    assert result["status"] == "manual_review_required" and result["violations"] == []
    assert result["normal_week_reference_minutes"] is None
    assert result["regime_assessment"] == {"declared_regime": regime or "unknown", "reference_checks_enabled": False,
                                          "actual_regime_verified": False}
    for key in ("total_work_minutes", "covered_minutes", "daily_totals", "timeline"):
        assert result[key] == original[key]
    assert all(s["work_limit_minutes"] is None for s in result["shifts"])
    assert all(r["qualifies_selected_daily_rest"] is None and r["qualifies_selected_combined_weekly_rest"] is None
               for r in result["rest_periods"])
    night = result["night_accounting"]
    assert night["base_window_equivalent_work_minutes"] is None
    assert night["observed_night_work_minutes"] == original["night_accounting"]["observed_night_work_minutes"]
    assert night["extension_sensitivity"]["conditional_equivalent_work_minutes"] is None
    comparisons = [*night["shift_reference_comparisons"], night["week_reference_comparison"],
                   *night["extension_sensitivity"]["shift_scenarios"], night["extension_sensitivity"]["week_reference_comparison"]]
    assert all(r["reference_minutes"] is None and r["exceeded"] is None and r["excess_equivalent_minutes"] is None
               for r in comparisons)
    assert result["dispatch_authorized"] is False


def test_explicit_standard_profile_retains_the_existing_results_but_does_not_verify_employment():
    result = review_week(example_history())
    assert result["status"] == "within_selected_weekly_planning_limits"
    assert result["normal_week_reference_minutes"] == 2640
    assert result["regime_assessment"]["reference_checks_enabled"] is True
    assert result["regime_assessment"]["actual_regime_verified"] is False


@pytest.mark.parametrize("regime", [None, True, [], {}, 1, "standard", "STANDARD_PRIVATE_EMPLOYEE"])
def test_invalid_regime_values_are_rejected(regime):
    history = example_history()
    history["employment_regime"] = regime
    with pytest.raises(ValueError, match="employment_regime"):
        review_week(history)


def test_outside_reviewed_dates_also_withholds_all_selected_policy_verdicts():
    history = example_history("night_limit_exceeded")
    history["week_start"] = "2026-12-21"
    result = review_week(history)
    assert result["status"] == "manual_review_required" and result["violations"] == []
    assert result["regime_assessment"]["reference_checks_enabled"] is False
    assert all(s["work_limit_minutes"] is None for s in result["shifts"])
    assert all(r["qualifies_selected_daily_rest"] is None for r in result["rest_periods"])


def test_new_examples_legacy_omission_and_invalid_profile_have_explicit_api_behavior():
    with TestClient(create_app()) as client:
        for example in ("unknown_regime", "special_regime"):
            response = client.get("/brazil/duty-review", params={"example": example})
            assert response.status_code == 200
            body = response.json()
            posted = client.post("/brazil/duty-review", json=body["input"])
            assert posted.status_code == 200 and posted.json()["review"] == body["review"]
            assert body["review"]["status"] == "manual_review_required"
        history = example_history()
        del history["employment_regime"]
        assert client.post("/brazil/duty-review", json=history).json()["review"]["normal_week_reference_minutes"] is None
        history["employment_regime"] = "not-a-regime"
        assert client.post("/brazil/duty-review", json=history).status_code == 422
        schema = client.get("/openapi.json").json()["paths"]["/brazil/duty-review"]["post"]["requestBody"]
        assert schema["content"]["application/json"]["schema"]["properties"]["employment_regime"]["default"] == "unknown"
