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
