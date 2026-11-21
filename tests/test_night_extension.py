import copy
from fractions import Fraction

import pytest
from fastapi.testclient import TestClient

from freight_intelligence.api.app import create_app
from freight_intelligence.optimization.weekly_duty import example_history, review_week


def result_for(start, minutes, activity="work"):
    events = []
    if start:
        events.append({"activity": "rest", "minutes": start})
    events.append({"activity": activity, "minutes": minutes})
    if start + minutes < 10080:
        events.append({"activity": "rest", "minutes": 10080 - start - minutes})
    return review_week({**example_history(), "events": events})


def test_conditional_excess_is_not_an_authoritative_violation_or_approval():
    result = review_week(example_history("night_extension_sensitive"))
    night = result["night_accounting"]
    conditional = night["extension_sensitivity"]
    assert result["total_work_minutes"] == 421
    assert night["base_window_equivalent_work_minutes"] == {"numerator": 3307, "denominator": 7}
    assert night["shift_reference_comparisons"][0]["exceeded"] is False
    assert conditional["candidate_work_minutes"] == 61
    assert conditional["conditional_equivalent_work_minutes"] == {"numerator": 3368, "denominator": 7}
    assert conditional["increment_over_base_equivalent_minutes"] == {"numerator": 61, "denominator": 7}
    assert conditional["shift_scenarios"][0]["exceeded"] is True
    assert conditional["shift_scenarios"][0]["continuation_windows"][0]["full_22_to_05_shift_span_observed"]
    assert result["status"] == "manual_review_required" and result["violations"] == []
    assert "conditional_extension_reference_exceeded_requires_review" in result["review_reasons"]
    assert conditional["applicability"] == "not_determined" and conditional["replaces_base_result"] is False
    assert night["extension_conversion_applied"] is False and result["dispatch_authorized"] is False


@pytest.mark.parametrize("start,minutes,candidate", [(1320, 420, 0), (1320, 421, 1), (300, 60, 0),
                                                     (299, 2, 1), (0, 10080, 7140), (9960, 120, 0)])
def test_continuation_boundaries_and_no_night_window_double_count(start, minutes, candidate):
    result = result_for(start, minutes)
    night = result["night_accounting"]
    conditional = night["extension_sensitivity"]
    assert conditional["candidate_work_minutes"] == candidate
    base = night["base_window_equivalent_work_minutes"]
    value = conditional["conditional_equivalent_work_minutes"]
    assert Fraction(value["numerator"], value["denominator"]) == Fraction(base["numerator"], base["denominator"]) + Fraction(candidate, 7)
    assert candidate <= night["observed_day_work_minutes"]
    assert sum(s["candidate_work_minutes"] for s in conditional["shift_scenarios"]) == candidate
    if start == 299:
        assert not conditional["shift_scenarios"][0]["continuation_windows"][0]["full_22_to_05_shift_span_observed"]


@pytest.mark.parametrize("activity,counted", [("work", True), ("waiting", True), ("driving", True),
                                               ("meal", False), ("driving_break", False), ("rest", False)])
def test_only_actual_continuation_work_counts_and_rest_ends_the_shift(activity, counted):
    history = example_history("night_shift")
    history["events"][4]["activity"] = activity
    result = review_week(history)
    assert result["night_accounting"]["extension_sensitivity"]["candidate_work_minutes"] == (60 if counted else 0)
    if activity == "rest":
        assert result["night_accounting"]["observed_night_work_minutes"] == 360


def test_new_daytime_shift_after_daily_rest_is_not_continuation():
    history = example_history("night_shift")
    history["events"][-1:] = [{"activity": "rest", "minutes": 660}, {"activity": "work", "minutes": 60},
                             {"activity": "rest", "minutes": 7560}]
    conditional = review_week(history)["night_accounting"]["extension_sensitivity"]
    assert conditional["candidate_work_minutes"] == 60
    assert conditional["shift_scenarios"][-1]["candidate_work_minutes"] == 0


def test_observed_night_work_before_midnight_still_marks_continuation_for_review():
    history = example_history()
    history["events"] = [{"activity": kind, "minutes": minutes} for kind, minutes in
                         (("rest", 1320), ("work", 120), ("meal", 300), ("work", 60), ("rest", 8280))]
    result = review_week(history)
    night = result["night_accounting"]
    assert night["extension_sensitivity"]["candidate_work_minutes"] == 60
    assert night["post_05_extension_requires_review"] is True
    assert "post_05_night_extension_requires_review" in result["review_reasons"]


def test_splitting_events_does_not_change_candidates_or_conditional_totals():
    history = example_history("night_extension_sensitive")
    expected = review_week(history)["night_accounting"]["extension_sensitivity"]
    history["events"][4:5] = [{"activity": "work", "minutes": 1}] * 61
    assert review_week(history)["night_accounting"]["extension_sensitivity"] == expected


def test_unknown_context_incomplete_boundaries_and_future_dates_remain_explicit():
    history = example_history("night_extension_sensitive")
    history["carry_in_rest_minutes"] = history["carry_in_consecutive_workdays"] = None
    history["events"].pop()
    result = review_week(history)
    assert "unknown_carry_in_history" in result["review_reasons"]
    assert "shift_still_open_at_window_boundary" in result["review_reasons"]
    assert result["daily_totals"][-1]["work_minutes"] is None
    assert result["night_accounting"]["extension_sensitivity"]["candidate_work_minutes"] == 61
    future = copy.deepcopy(history)
    future["week_start"] = "2026-12-21"
    conditional = review_week(future)["night_accounting"]["extension_sensitivity"]
    assert conditional["candidate_work_minutes"] == 61
    assert conditional["conditional_equivalent_work_minutes"] is None
    assert conditional["increment_over_base_equivalent_minutes"] is None
    for comparison in [*conditional["shift_scenarios"], conditional["week_reference_comparison"]]:
        assert comparison["reference_minutes"] is None and comparison["exceeded"] is None
    assert conditional["applicability"] == "not_determined"


def test_conditional_reference_excess_does_not_trigger_on_unsupported_dates():
    history = example_history("night_extension_sensitive")
    history["week_start"] = "2026-12-21"
    result = review_week(history)
    assert "conditional_extension_reference_exceeded_requires_review" not in result["review_reasons"]


def test_weekly_conditional_excess_is_separate_from_base_and_daily_authorization():
    events, clock = [], 0
    for day in range(5):
        start = day * 1440 + 1320
        events.append({"activity": "rest", "minutes": start - clock})
        events.extend({"activity": kind, "minutes": minutes} for kind, minutes in
                      (("driving", 180), ("meal", 60), ("waiting", 180), ("work", 108)))
        clock = start + 528
    events.append({"activity": "rest", "minutes": 10080 - clock})
    result = review_week({**example_history(), "events": events, "overtime_authorized": True})
    night = result["night_accounting"]
    assert night["week_reference_comparison"]["exceeded"] is False
    conditional = night["extension_sensitivity"]
    assert conditional["week_reference_comparison"]["exceeded"] is True
    assert conditional["week_reference_comparison"]["excess_equivalent_minutes"] == {"numerator": 240, "denominator": 7}
    assert all(row["exceeded"] is False for row in conditional["shift_scenarios"])
    assert result["violations"] == [] and result["status"] == "manual_review_required"


def test_conditional_example_get_and_post_preserve_source_and_scenario_separation():
    with TestClient(create_app()) as client:
        response = client.get("/brazil/duty-review?example=night_extension_sensitive")
        assert response.status_code == 200
        example = response.json()
        assert example["review"] == review_week(example["input"])
        response = client.post("/brazil/duty-review", json=example["input"])
        assert response.status_code == 200 and response.json()["records_saved"] is False
        assert response.json()["review"] == example["review"]
