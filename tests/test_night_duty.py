import copy
from fractions import Fraction

import pytest
from fastapi.testclient import TestClient

from freight_intelligence.api.app import create_app
from freight_intelligence.optimization.weekly_duty import example_history, review_week


def history_at(start, duration, activity="work"):
    events = []
    if start:
        events.append({"activity": "rest", "minutes": start})
    events.append({"activity": activity, "minutes": duration})
    if start + duration < 10080:
        events.append({"activity": "rest", "minutes": 10080 - start - duration})
    return {**example_history(), "events": events}


@pytest.mark.parametrize("start,duration,night", [
    (1319, 1, 0), (1320, 1, 1), (299, 1, 1), (300, 1, 0),
    (1319, 2, 1), (299, 2, 1), (1320, 420, 420),
    (1320, 480, 420), (0, 10080, 2940), (9960, 120, 120),
])
def test_local_window_boundaries_and_exact_conversion(start, duration, night):
    report = review_week(history_at(start, duration))["night_accounting"]
    assert report["observed_night_work_minutes"] == night
    assert report["observed_day_work_minutes"] == duration - night
    value = report["base_window_equivalent_work_minutes"]
    assert Fraction(value["numerator"], value["denominator"]) == duration - night + Fraction(night * 8, 7)
    assert sum(report["daily_night_work_minutes"]) == night


@pytest.mark.parametrize("activity,counted", [("work", True), ("waiting", True), ("driving", True),
                                               ("rest", False), ("meal", False), ("driving_break", False)])
def test_only_work_is_reduced_and_rest_driving_limits_use_real_minutes(activity, counted):
    result = review_week(history_at(1320, 420, activity))
    assert result["night_accounting"]["observed_night_work_minutes"] == (420 if counted else 0)
    if activity == "driving":
        assert result["total_work_minutes"] == 420
        assert any(v["code"] == "selected_continuous_driving_limit_exceeded" for v in result["violations"])


def test_night_example_excludes_meal_retains_waiting_and_requires_extension_review():
    history = example_history("night_shift")
    result = review_week(history)
    night = result["night_accounting"]
    assert result["coverage_complete"] and result["total_work_minutes"] == 420
    assert night["observed_night_work_minutes"] == 360
    assert night["daily_night_work_minutes"] == [120, 240, 0, 0, 0, 0, 0]
    assert night["base_window_equivalent_work_minutes"] == {"numerator": 3300, "denominator": 7}
    assert night["post_05_extension_requires_review"]
    assert "post_05_night_extension_requires_review" in result["review_reasons"]
    assert result["status"] == "manual_review_required" and result["dispatch_authorized"] is False
    assert night["wages_calculated"] is False and night["extension_conversion_applied"] is False
    split = copy.deepcopy(history)
    split["events"][3:4] = [{"activity": "waiting", "minutes": 1}] * 180
    assert review_week(split)["night_accounting"] == night


@pytest.mark.parametrize("start,duration,extension", [(1320, 420, False), (1320, 421, True),
                                                     (300, 420, False), (1440, 301, True)])
def test_post_five_extension_is_not_silently_converted(start, duration, extension):
    result = review_week(history_at(start, duration))
    assert result["night_accounting"]["post_05_extension_requires_review"] is extension


def test_future_dates_and_incomplete_coverage_do_not_gain_unsupported_conversion_or_rest():
    history = example_history("night_shift")
    history["week_start"] = "2026-12-21"
    result = review_week(history)
    assert result["night_accounting"]["observed_night_work_minutes"] == 360
    assert result["night_accounting"]["base_window_equivalent_work_minutes"] is None
    assert result["night_accounting"]["nominal_night_hour_seconds"] is None
    history["events"].pop()
    result = review_week(history)
    assert result["daily_totals"][-1]["work_minutes"] is None
    assert result["night_accounting"]["daily_night_work_minutes"][-1] is None
    assert not result["coverage_complete"] and result["dispatch_authorized"] is False


def test_night_example_is_identical_over_stateless_get_and_post():
    with TestClient(create_app()) as client:
        response = client.get("/brazil/duty-review?example=night_shift")
        assert response.status_code == 200
        example = response.json()
        response = client.post("/brazil/duty-review", json=example["input"])
        assert response.status_code == 200
        assert response.json()["review"] == example["review"]
        assert response.json()["records_saved"] is False


@pytest.mark.parametrize("duration,authorized,reference,exceeded", [
    (419, False, 480, False), (420, False, 480, False), (421, False, 480, True),
    (539, True, 600, False), (540, True, 600, False), (541, True, 600, True),
])
def test_reduced_hour_reference_boundaries_use_exact_values(duration, authorized, reference, exceeded):
    history = history_at(1320, duration)
    history["overtime_authorized"] = authorized
    result = review_week(history)
    comparison, = result["night_accounting"]["shift_reference_comparisons"]
    assert comparison["reference_minutes"] == reference
    assert comparison["exceeded"] is exceeded
    value = comparison["base_window_equivalent_work_minutes"]
    assert Fraction(value["numerator"], value["denominator"]) == duration + Fraction(min(420, duration), 7)
    assert any(v["code"] == "selected_reduced_hour_shift_reference_exceeded" for v in result["violations"]) is exceeded
    assert comparison["real_work_minutes"] == duration


def test_new_example_catches_reduced_hour_excess_without_changing_real_time_checks():
    result = review_week(example_history("night_limit_exceeded"))
    assert result["total_work_minutes"] == 480
    assert result["shifts"][0]["elapsed_minutes"] == 540
    assert result["status"] == "selected_limits_exceeded"
    assert [v["code"] for v in result["violations"]] == ["selected_reduced_hour_shift_reference_exceeded"]
    comparison, = result["night_accounting"]["shift_reference_comparisons"]
    assert comparison["base_window_equivalent_work_minutes"] == {"numerator": 3720, "denominator": 7}
    assert comparison["excess_equivalent_minutes"] == {"numerator": 360, "denominator": 7}
    assert result["dispatch_authorized"] is False


def test_excess_smaller_than_display_rounding_is_still_detected():
    result = review_week(history_at(1326, 421))  # 22:06-05:07: 414 night + 7 day minutes.
    comparison, = result["night_accounting"]["shift_reference_comparisons"]
    value = comparison["base_window_equivalent_work_minutes"]
    assert value == {"numerator": 3361, "denominator": 7}
    assert f"{value['numerator'] / value['denominator'] / 60:.2f}" == "8.00"
    assert comparison["exceeded"] is True
    assert comparison["excess_equivalent_minutes"] == {"numerator": 1, "denominator": 7}


def test_weekly_reduced_reference_is_separate_from_daily_authorization_and_real_hours():
    events, clock = [], 0
    for day in range(5):
        start = day * 1440 + 1260  # 21:00-06:00, with a 01:00-02:00 meal.
        events.append({"activity": "rest", "minutes": start - clock})
        events.extend({"activity": k, "minutes": m} for k, m in
                      (("work", 240), ("meal", 60), ("waiting", 240)))
        clock = start + 540
    events.append({"activity": "rest", "minutes": 10080 - clock})
    history = {**example_history(), "events": events, "overtime_authorized": True}
    result = review_week(history)
    assert result["total_work_minutes"] == 2400 < result["normal_week_reference_minutes"]
    night = result["night_accounting"]
    assert all(c["exceeded"] is False for c in night["shift_reference_comparisons"])
    assert night["week_reference_comparison"]["reference_minutes"] == 2640
    assert night["week_reference_comparison"]["exceeded"] is True
    assert night["week_reference_comparison"]["excess_equivalent_minutes"] == {"numerator": 120, "denominator": 7}
    assert "reduced_hour_week_reference_exceeded_requires_agreement_review" in result["review_reasons"]
    assert "weekly_hours_above_normal_reference_require_payroll_agreement_review" not in result["review_reasons"]
    assert result["dispatch_authorized"] is False


def test_unsupported_dates_have_no_reference_verdicts_and_daytime_values_are_preserved():
    history = example_history("night_limit_exceeded")
    history["week_start"] = "2026-12-21"
    result = review_week(history)
    night = result["night_accounting"]
    for comparison in [*night["shift_reference_comparisons"], night["week_reference_comparison"]]:
        assert comparison["reference_minutes"] is None
        assert comparison["exceeded"] is None and comparison["excess_equivalent_minutes"] is None
    assert not any(v["code"] == "selected_reduced_hour_shift_reference_exceeded" for v in result["violations"])
    day = review_week(example_history())
    assert all(c["base_window_equivalent_work_minutes"]["numerator"] == c["real_work_minutes"] * 7
               and c["exceeded"] is False for c in day["night_accounting"]["shift_reference_comparisons"])
    assert day["status"] == "within_selected_weekly_planning_limits"


def test_new_example_get_and_post_preserve_exact_reference_evidence():
    with TestClient(create_app()) as client:
        response = client.get("/brazil/duty-review?example=night_limit_exceeded")
        assert response.status_code == 200
        example = response.json()
        assert example["review"] == review_week(example["input"])
        response = client.post("/brazil/duty-review", json=example["input"])
        assert response.status_code == 200
        assert response.json()["review"] == example["review"]
