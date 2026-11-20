import copy
import hashlib
import json
import shutil

import pytest
from fastapi.testclient import TestClient

from freight_intelligence.api.app import create_app
from freight_intelligence.optimization.weekly_duty import (
    DEFAULT_ROOT,
    example_history,
    parse_history,
    review_week,
)


def test_balanced_declared_week_reconciles_work_rest_and_daily_totals():
    result = review_week(example_history())
    assert result["status"] == "within_selected_weekly_planning_limits"
    assert result["coverage_complete"] and result["covered_minutes"] == 10080
    assert result["total_work_minutes"] == 2640
    assert [r["work_minutes"] for r in result["daily_totals"]] == [480] * 5 + [240, 0]
    assert sum(r["work_minutes"] for r in result["shifts"]) == 2640
    assert result["rest_periods"][-1]["declared_minutes_including_carry_in"] == 2100
    assert result["rest_periods"][-1]["qualifies_selected_combined_weekly_rest"]
    assert result["dispatch_authorized"] is False
    assert not result["violations"] and not result["review_reasons"]


@pytest.mark.parametrize("gap,exceeded", [(659, True), (660, False), (661, False)])
def test_daily_rest_boundary(gap, exceeded):
    history = example_history("short_daily_rest")
    # Rest between Monday's last work and Tuesday's first work is event 6.
    delta = gap - history["events"][6]["minutes"]
    history["events"][6]["minutes"] = gap
    history["events"][-1]["minutes"] -= delta
    result = review_week(history)
    assert any(r["code"] == "declared_intershift_rest_below_11_hours" for r in result["violations"]) is exceeded


def test_seventh_workday_and_weekly_hours_are_separate_results():
    result = review_week(example_history("seven_workdays"))
    assert any(r["code"] == "seventh_workday_before_selected_weekly_rest" for r in result["violations"])
    assert "weekly_hours_above_normal_reference_require_payroll_agreement_review" in result["review_reasons"]
    assert result["total_work_minutes"] == 2880


def test_incomplete_and_unknown_context_are_never_filled_with_rest_or_work_zeroes():
    result = review_week(example_history("incomplete_week"))
    assert result["status"] == "manual_review_required"
    assert not result["coverage_complete"]
    assert result["daily_totals"][-1]["work_minutes"] is None
    assert result["daily_totals"][-1]["observed_minutes"] == 0
    history = example_history()
    history["carry_in_rest_minutes"] = history["carry_in_consecutive_workdays"] = None
    result = review_week(history)
    assert result["status"] == "manual_review_required"
    assert "unknown_carry_in_history" in result["review_reasons"]
    assert not any(r["code"] == "declared_intershift_rest_below_11_hours" for r in result["violations"])


@pytest.mark.parametrize("week", ["2026-11-16", "2026-12-21", "2027-12-20", "2023-07-03"])
def test_dates_outside_reviewed_period_never_apply_old_weekly_threshold_as_current(week):
    history = example_history()
    history["week_start"] = week
    result = review_week(history)
    assert result["status"] == "manual_review_required"
    assert result["normal_week_reference_minutes"] is None
    assert "week_outside_reviewed_rule_period" in result["review_reasons"]


def test_adjacent_rest_is_uninterrupted_but_waiting_is_work():
    history = example_history()
    last = history["events"].pop()
    history["events"].extend([{"activity": "rest", "minutes": 1000}, {"activity": "rest", "minutes": last["minutes"] - 1000}])
    result = review_week(history)
    assert result["rest_periods"][-1]["qualifies_selected_combined_weekly_rest"]
    assert result["status"] == "within_selected_weekly_planning_limits"
    for event in history["events"]:
        if event["activity"] == "work":
            event["activity"] = "waiting"
    assert review_week(history)["total_work_minutes"] == 2640


@pytest.mark.parametrize("minutes,qualifies", [(2099, False), (2100, True), (2101, True)])
def test_selected_combined_weekly_rest_boundary(minutes, qualifies):
    history = example_history()
    delta = minutes - history["events"][-1]["minutes"]
    history["events"][-1]["minutes"] = minutes
    history["events"][-2]["minutes"] -= delta
    result = review_week(history)
    assert result["rest_periods"][-1]["qualifies_selected_combined_weekly_rest"] is qualifies
    assert ("trailing_weekly_rest_needs_next_window" in result["review_reasons"]) is (not qualifies)


@pytest.mark.parametrize("authorized", [False, True])
def test_weekly_excess_is_not_automatically_approved_by_daily_overtime_flag(authorized):
    history = example_history()
    history["overtime_authorized"] = authorized
    history["events"][-2]["minutes"] += 1
    history["events"][-1]["minutes"] -= 1
    result = review_week(history)
    assert result["total_work_minutes"] == 2641
    assert "weekly_hours_above_normal_reference_require_payroll_agreement_review" in result["review_reasons"]
    assert result["dispatch_authorized"] is False


def test_continuous_driving_meals_and_night_scope_are_checked():
    history = example_history()
    history["events"][1]["activity"] = "driving"  # 30 + 210 before the meal.
    history["events"][3]["activity"] = "work"  # Meal is no longer a qualifying break.
    result = review_week(history)
    codes = {r["code"] for r in result["violations"]}
    assert "selected_continuous_driving_limit_exceeded" in codes
    assert "selected_full_meal_policy_not_met" in codes
    history = example_history()
    history["events"][0]["minutes"] -= 240
    history["events"][-1]["minutes"] += 240
    assert "night_or_multiday_regime_requires_review" in review_week(history)["review_reasons"]


@pytest.mark.parametrize("defect", ["unknown_field", "bad_activity", "boolean_minutes", "negative", "too_many",
                                    "over_week", "bad_date", "iso_week_date", "bad_context"])
def test_malformed_inputs_are_rejected_without_mutating_caller(defect):
    payload = example_history()
    if defect == "unknown_field":
        payload["driver_name"] = "not accepted"
    elif defect == "bad_activity":
        payload["events"][0]["activity"] = []
    elif defect == "boolean_minutes":
        payload["events"][0]["minutes"] = True
    elif defect == "negative":
        payload["events"][0]["minutes"] = -1
    elif defect == "too_many":
        payload["events"] *= 9
    elif defect == "over_week":
        payload["events"][-1]["minutes"] += 1
    elif defect == "bad_date":
        payload["week_start"] = "2026-11-10"
    elif defect == "iso_week_date":
        payload["week_start"] = "2026-W46-1"
    else:
        payload["carry_in_rest_minutes"] = -1
    before = copy.deepcopy(payload)
    with pytest.raises(ValueError):
        review_week(payload)
    assert before == payload


def test_json_bounds_duplicates_and_changed_policy_are_rejected(tmp_path):
    for raw in (b"", b"x" * 65537, b'{"events":[],"events":[]}', b"\xff", b"[" * 1200 + b"]" * 1200):
        with pytest.raises((ValueError, TypeError)):
            parse_history(raw)
    root = tmp_path / "rules"
    shutil.copytree(DEFAULT_ROOT, root)
    (root / "policy.json").write_bytes(b"{}")
    with pytest.raises(ValueError, match="integrity"):
        review_week(example_history(), root)


@pytest.mark.parametrize("defect", ["missing_limit", "wrong_type", "boolean_limit", "missing_night", "float_night"])
def test_structurally_invalid_rehashed_policy_returns_unavailable_not_server_error(tmp_path, defect):
    root = tmp_path / "rules"
    shutil.copytree(DEFAULT_ROOT, root)
    policy = json.loads((root / "policy.json").read_bytes())
    if defect == "missing_limit":
        del policy["limits"]["meal_minutes"]
    elif defect == "wrong_type":
        policy["limits"] = []
    elif defect == "boolean_limit":
        policy["limits"]["meal_minutes"] = True
    elif defect == "missing_night":
        del policy["night_accounting"]
    else:
        policy["night_accounting"]["nominal_hour_seconds"] = 3150.0
    raw = json.dumps(policy).encode()
    (root / "policy.json").write_bytes(raw)
    manifest = json.loads((root / "manifest.json").read_bytes())
    manifest["files"][0].update(bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())
    (root / "manifest.json").write_bytes(json.dumps(manifest).encode())
    with TestClient(create_app(weekly_rules_dir=root)) as client:
        assert client.get("/brazil/duty-review").status_code == 503


def test_api_stateless_post_limits_and_missing_policy(tmp_path, monkeypatch):
    with TestClient(create_app()) as client:
        example = client.get("/brazil/duty-review").json()
        result = client.post("/brazil/duty-review", json=example["input"])
        assert result.status_code == 200 and result.json()["records_saved"] is False
        assert result.json()["review"] == example["review"]
        assert client.post("/brazil/duty-review", content=b"x" * 65537,
                           headers={"Content-Type": "application/json"}).status_code == 413
        assert client.post("/brazil/duty-review", content="{}").status_code == 415
        assert client.post("/brazil/duty-review", json={}).status_code == 422
        assert client.post("/brazil/duty-review", content=b'{"events":[],"events":[]}',
                           headers={"Content-Type": "application/json"}).status_code == 422
        schema = client.get("/openapi.json").json()["paths"]["/brazil/duty-review"]["post"]["requestBody"]
        assert schema["content"]["application/json"]["schema"]["properties"]["events"]["maxItems"] == 300
    with TestClient(create_app(weekly_rules_dir=tmp_path)) as client:
        assert client.get("/brazil/duty-review").status_code == 503
    key = "weekly-reader-" + "x" * 32
    path = tmp_path / "users.json"
    path.write_text(json.dumps({"users": [{"id": "reader", "key_sha256": hashlib.sha256(key.encode()).hexdigest(),
                                         "enabled": True, "permissions": ["evaluation"]}]}), encoding="utf-8")
    monkeypatch.setenv("LOGINEXUS_REQUIRE_AUTH", "true")
    monkeypatch.setenv("LOGINEXUS_API_USERS_FILE", str(path))
    monkeypatch.delenv("LOGINEXUS_API_KEY", raising=False)
    with TestClient(create_app()) as client:
        assert client.get("/brazil/duty-review").status_code == 401
        assert client.post("/brazil/duty-review", json=example_history()).status_code == 401
        assert client.post("/brazil/duty-review", json=example_history(), headers={"X-API-Key": key}).status_code == 403
