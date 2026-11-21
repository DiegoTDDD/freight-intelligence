"""Bounded, explicit-history weekly screening; never infer rest from missing data."""

import hashlib
import json
from datetime import date, timedelta
from pathlib import Path

from freight_intelligence.optimization.night_extension import extension_sensitivity

DEFAULT_ROOT = Path(__file__).resolve().parents[2] / "deployment/duty_review"
MAX_BYTES = 65536
MAX_EVENTS = 300
ACTIVITIES = {"rest", "driving", "work", "waiting", "meal", "driving_break"}
WORK = {"driving", "work", "waiting"}


def load_policy(root=DEFAULT_ROOT):
    root = Path(root)
    if (root / "manifest.json").stat().st_size > 8192 or (root / "policy.json").stat().st_size > MAX_BYTES:
        raise ValueError("Oversized weekly-duty policy")
    record, = json.loads((root / "manifest.json").read_bytes())["files"]
    raw = (root / "policy.json").read_bytes()
    if record["path"] != "policy.json" or len(raw) != record["bytes"] or hashlib.sha256(raw).hexdigest() != record["sha256"]:
        raise ValueError("Weekly-duty policy integrity mismatch")
    policy = json.loads(raw)
    if not isinstance(policy, dict) or policy.get("schema_version") != 1:
        raise ValueError("Unknown weekly-duty policy")
    keys = {"week_minutes", "normal_week_minutes", "normal_day_minutes", "authorized_day_minutes",
            "daily_rest_minutes", "weekly_combined_rest_minutes", "max_consecutive_workdays",
            "continuous_drive_minutes", "driving_break_minutes", "meal_minutes", "max_shift_span_minutes"}
    limits = policy.get("limits")
    if (not isinstance(limits, dict) or set(limits) != keys
            or any(type(v) is not int or not 0 < v <= 10080 for v in limits.values())
            or limits["week_minutes"] != 10080
            or limits["normal_day_minutes"] > limits["authorized_day_minutes"]
            or limits["daily_rest_minutes"] + limits["max_shift_span_minutes"] != 1440):
        raise ValueError("Invalid weekly-duty policy limits")
    if date.fromisoformat(policy["supported_from"]) > date.fromisoformat(policy["reviewed_on"]):
        raise ValueError("Invalid weekly-duty policy period")
    night = policy.get("night_accounting")
    if (night != {"start_minute": 1320, "end_minute": 300, "nominal_hour_seconds": 3150, "source_id": "clt_73"}
            or any(type(night[k]) is not int for k in ("start_minute", "end_minute", "nominal_hour_seconds"))):
        raise ValueError("Invalid reviewed night-accounting policy")
    if policy.get("extension_sensitivity_profile") != "observed_night_continuation_05_to_22_if_applicable_v1":
        raise ValueError("Invalid reviewed extension-sensitivity profile")
    return policy


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON fields are not accepted")
        result[key] = value
    return result


def parse_history(raw):
    if not isinstance(raw, bytes) or not 0 < len(raw) <= MAX_BYTES:
        raise ValueError("Weekly history must be nonempty and at most 64 KiB")
    try:
        result = json.loads(raw, object_pairs_hook=unique_object)
    except (UnicodeError, RecursionError) as error:
        raise ValueError("Invalid weekly-history JSON encoding or depth") from error
    if not isinstance(result, dict):
        raise TypeError("Weekly history must be a JSON object")
    return result


def night_accounting(timeline, shifts, policy, supported):
    """Account observed 22:00-05:00 work exactly; do not infer extension or wages."""
    night_policy = policy["night_accounting"]
    daily = [0] * 7
    for event in timeline:
        if not event["counts_as_work"]:
            continue
        for day in range(event["start_minute"] // 1440, (event["end_minute"] - 1) // 1440 + 1):
            for left, right in ((day * 1440, day * 1440 + night_policy["end_minute"]),
                                (day * 1440 + night_policy["start_minute"], (day + 1) * 1440)):
                daily[day] += max(0, min(right, event["end_minute"]) - max(left, event["start_minute"]))
    observed = sum(daily)
    total = sum(e["minutes"] for e in timeline if e["counts_as_work"])
    # A reduced-hour equivalent minute is 60/52.5 = 8/7 real minutes.
    # Keep sevenths as integers; only the display layer rounds.
    equivalent = {"numerator": (total - observed) * 7 + observed * 8, "denominator": 7} if supported else None
    def compare(numerator, reference):
        return {"reference_minutes": reference if supported else None,
                "exceeded": numerator > reference * 7 if supported else None,
                "excess_equivalent_minutes": {"numerator": max(0, numerator - reference * 7), "denominator": 7} if supported else None}

    extension, shift_comparisons = False, []
    for shift in shifts:
        work = [e for e in timeline if e["counts_as_work"]
                and shift["start_minute"] <= e["start_minute"] < shift["end_minute"]]
        shift_night = 0
        for event in work:
            for day in range(event["start_minute"] // 1440, (event["end_minute"] - 1) // 1440 + 1):
                for left, right in ((day * 1440, day * 1440 + night_policy["end_minute"]),
                                    (day * 1440 + night_policy["start_minute"], (day + 1) * 1440)):
                    shift_night += max(0, min(right, event["end_minute"]) - max(left, event["start_minute"]))
        numerator = shift["work_minutes"] * 7 + shift_night
        shift_comparisons.append({"start_minute": shift["start_minute"], "end_minute": shift["end_minute"],
                                  "real_work_minutes": shift["work_minutes"], "night_work_minutes": shift_night,
                                  "base_window_equivalent_work_minutes": {"numerator": numerator, "denominator": 7} if supported else None,
                                  **compare(numerator, shift["work_limit_minutes"])})
        for day in range(shift["start_minute"] // 1440, (shift["end_minute"] - 1) // 1440 + 1):
            five = day * 1440 + night_policy["end_minute"]
            if (any(e["start_minute"] < five and e["end_minute"] > day * 1440 for e in work)
                    and any(e["end_minute"] > five for e in work)):
                extension = True
    covered = timeline[-1]["end_minute"]
    return {"observed_night_work_minutes": observed, "observed_day_work_minutes": total - observed,
            "daily_night_work_minutes": [v if covered > i * 1440 else None for i, v in enumerate(daily)],
            "base_window_equivalent_work_minutes": equivalent,
            "shift_reference_comparisons": shift_comparisons,
            "week_reference_comparison": compare(total * 7 + observed, policy["limits"]["normal_week_minutes"]),
            "post_05_extension_requires_review": extension,
            "conversion_supported_for_week": supported, "nominal_night_hour_seconds": 3150 if supported else None,
            "window": "22:00 inclusive to 05:00 exclusive, Sao Paulo local time",
            "source_id": "clt_73", "extension_conversion_applied": False, "wages_calculated": False}


def review_week(payload, root=DEFAULT_ROOT):
    policy = load_policy(root)
    required = {"week_start", "events", "carry_in_rest_minutes", "carry_in_consecutive_workdays", "overtime_authorized"}
    if not isinstance(payload, dict) or set(payload) != required:
        raise ValueError("Use exactly the documented weekly-history fields; no driver identifiers")
    if not isinstance(payload["week_start"], str) or len(payload["week_start"]) != 10:
        raise ValueError("week_start must be a Monday in YYYY-MM-DD form")
    start_date = date.fromisoformat(payload["week_start"])
    if start_date.isoformat() != payload["week_start"] or start_date.weekday() != 0 or type(payload["overtime_authorized"]) is not bool:
        raise ValueError("Use a Monday start and Boolean overtime authorization")
    events = payload["events"]
    if not isinstance(events, list) or not 1 <= len(events) <= MAX_EVENTS:
        raise ValueError("Weekly history requires 1-300 events")
    carry_rest, carry_days = payload["carry_in_rest_minutes"], payload["carry_in_consecutive_workdays"]
    for value, maximum in ((carry_rest, 10080), (carry_days, 6)):
        if value is not None and (type(value) is not int or not 0 <= value <= maximum):
            raise ValueError("Invalid declared carry-in history")
    for event in events:
        if (not isinstance(event, dict) or set(event) != {"activity", "minutes"}
                or not isinstance(event["activity"], str) or event["activity"] not in ACTIVITIES or type(event["minutes"]) is not int
                or not 1 <= event["minutes"] <= 10080):
            raise ValueError("Every event requires a known activity and positive integer minutes")
    covered = sum(event["minutes"] for event in events)
    if covered > 10080:
        raise ValueError("History exceeds the seven-day window")
    limits = policy["limits"]
    flags, unknown, timeline, shifts, rests = [], [], [], [], []
    daily_work = [0] * 7

    def flag(code, minute):
        item = {"code": code, "minute": minute}
        if item not in flags:
            flags.append(item)

    if covered != 10080:
        unknown.append("incomplete_seven_day_coverage")
    if carry_rest is None or carry_days is None:
        unknown.append("unknown_carry_in_history")
    if start_date < date.fromisoformat(policy["supported_from"]) or start_date + timedelta(days=6) > date.fromisoformat(policy["reviewed_on"]):
        unknown.append("week_outside_reviewed_rule_period")
    normal_reference = limits["normal_week_minutes"] if "week_outside_reviewed_rule_period" not in unknown else None
    clock = total_work = continuous = 0
    consecutive, last_work_day = carry_days or 0, None
    shift_start, shift_work, meal_seen, meal_followed = None, 0, False, False
    pending_rest, rest_start = carry_rest or 0, 0
    rest_known = carry_rest is not None
    last_was_rest = True

    def finish_shift(end):
        nonlocal shift_start, shift_work, meal_seen, meal_followed
        if shift_start is None:
            return
        allowed = limits["authorized_day_minutes"] if payload["overtime_authorized"] else limits["normal_day_minutes"]
        shifts.append({"start_minute": shift_start, "end_minute": end, "work_minutes": shift_work,
                       "elapsed_minutes": end - shift_start, "work_limit_minutes": allowed})
        if shift_work > allowed:
            flag("selected_shift_work_limit_exceeded", end)
        if end - shift_start > limits["max_shift_span_minutes"]:
            flag("selected_shift_span_exceeded", end)
        if not meal_seen or not meal_followed:
            flag("selected_full_meal_policy_not_met", end)
        shift_start, shift_work, meal_seen, meal_followed = None, 0, False, False

    def finish_rest(next_work, boundary=False):
        nonlocal pending_rest, rest_known, last_was_rest, consecutive, continuous
        if not last_was_rest:
            return
        if pending_rest:
            rests.append({"start_minute": rest_start, "end_minute": clock,
                          "declared_minutes_including_carry_in": pending_rest,
                          "qualifies_selected_daily_rest": pending_rest >= limits["daily_rest_minutes"],
                          "qualifies_selected_combined_weekly_rest": pending_rest >= limits["weekly_combined_rest_minutes"]})
        if next_work and rest_known and pending_rest < limits["daily_rest_minutes"]:
            flag("declared_intershift_rest_below_11_hours", clock)
        if pending_rest >= limits["weekly_combined_rest_minutes"]:
            consecutive = 0
        if pending_rest >= limits["driving_break_minutes"]:
            continuous = 0
        if boundary and 0 < pending_rest < limits["weekly_combined_rest_minutes"]:
            unknown.append("trailing_weekly_rest_needs_next_window")
        pending_rest, rest_known, last_was_rest = 0, True, False

    for event in events:
        kind, duration = event["activity"], event["minutes"]
        end = clock + duration
        timeline.append({"activity": kind, "start_minute": clock, "end_minute": end, "minutes": duration,
                         "counts_as_work": kind in WORK})
        if kind == "rest":
            if not last_was_rest:
                finish_shift(clock)
                rest_start, pending_rest, rest_known = clock, 0, True
            last_was_rest = True
            pending_rest += duration
        else:
            finish_rest(True)
            if shift_start is None and kind in WORK:
                shift_start = clock
            if kind in WORK:
                total_work += duration
                shift_work += duration
                if meal_seen:
                    meal_followed = True
                for day in range(clock // 1440, (end - 1) // 1440 + 1):
                    daily_work[day] += min(end, (day + 1) * 1440) - max(clock, day * 1440)
                    if day != last_work_day:
                        consecutive += 1
                        last_work_day = day
                        if consecutive > limits["max_consecutive_workdays"]:
                            flag("seventh_workday_before_selected_weekly_rest", max(clock, day * 1440))
            if kind == "driving":
                continuous += duration
                if continuous > limits["continuous_drive_minutes"]:
                    flag("selected_continuous_driving_limit_exceeded", clock)
            if kind in {"meal", "driving_break"} and duration >= limits["driving_break_minutes"]:
                continuous = 0
            if kind == "meal" and duration >= limits["meal_minutes"] and shift_work:
                meal_seen = True
            for day in range(clock // 1440, (end - 1) // 1440 + 1):
                left, right = max(clock, day * 1440), min(end, (day + 1) * 1440)
                if left < day * 1440 + 300 or right > day * 1440 + 1320:
                    unknown.append("night_or_multiday_regime_requires_review")
        clock = end
    if last_was_rest:
        finish_rest(False, boundary=True)
    else:
        finish_shift(clock)
        unknown.append("shift_still_open_at_window_boundary")
    if normal_reference is not None and total_work > normal_reference:
        unknown.append("weekly_hours_above_normal_reference_require_payroll_agreement_review")
    if not any(r["qualifies_selected_combined_weekly_rest"] for r in rests):
        unknown.append("no_complete_combined_weekly_rest_observed")
    night = night_accounting(timeline, shifts, policy, normal_reference is not None)
    night["extension_sensitivity"] = extension_sensitivity(timeline, shifts, night, policy, normal_reference is not None)
    sensitivity = night["extension_sensitivity"]
    if sensitivity["candidate_work_minutes"]:
        night["post_05_extension_requires_review"] = True
        unknown.append("conditional_night_extension_applicability_requires_review")
        if any(row["exceeded"] for row in sensitivity["shift_scenarios"]) or sensitivity["week_reference_comparison"]["exceeded"]:
            unknown.append("conditional_extension_reference_exceeded_requires_review")
    for comparison in night["shift_reference_comparisons"]:
        if comparison["exceeded"] and comparison["night_work_minutes"]:
            flag("selected_reduced_hour_shift_reference_exceeded", comparison["end_minute"])
    if night["week_reference_comparison"]["exceeded"] and night["observed_night_work_minutes"]:
        unknown.append("reduced_hour_week_reference_exceeded_requires_agreement_review")
    if night["observed_night_work_minutes"]:
        unknown.append("night_regime_and_reduced_hour_limits_require_review")
    if night["post_05_extension_requires_review"]:
        unknown.append("post_05_night_extension_requires_review")
    unknown = sorted(set(unknown))
    return {"status": "selected_limits_exceeded" if flags else "manual_review_required" if unknown else "within_selected_weekly_planning_limits",
            "week_start": payload["week_start"], "timezone": policy["timezone"],
            "covered_minutes": covered, "coverage_complete": covered == 10080, "total_work_minutes": total_work,
            "normal_week_reference_minutes": normal_reference, "violations": flags, "review_reasons": unknown,
            "night_accounting": night,
            "shifts": shifts, "rest_periods": rests, "timeline": timeline, "sources": policy["sources"],
            "daily_totals": [{"date": (start_date + timedelta(days=i)).isoformat(),
                              "work_minutes": value if covered > i * 1440 else None,
                              "observed_minutes": min(1440, max(0, covered - i * 1440)),
                              "full_day_covered": covered >= (i + 1) * 1440}
                             for i, value in enumerate(daily_work)],
            "policy_reviewed_on": policy["reviewed_on"], "scope": policy["scope"],
            "history_authentication": "Declared scenario only; actual records are not authenticated",
            "dispatch_authorized": False}


def example_history(name="balanced_week"):
    if name not in {"balanced_week", "short_daily_rest", "seven_workdays", "incomplete_week", "night_shift", "night_limit_exceeded", "night_extension_sensitive"}:
        raise ValueError("Unknown weekly example")
    if name in {"night_shift", "night_limit_exceeded", "night_extension_sensitive"}:
        # Monday 22:00 to Tuesday 06:00 (or 07:00); meal 01:00-02:00 is excluded.
        final_work = 120 if name == "night_limit_exceeded" else 61 if name == "night_extension_sensitive" else 60
        return {"week_start": "2026-11-09", "carry_in_rest_minutes": 2880,
                "carry_in_consecutive_workdays": 0, "overtime_authorized": False,
                "events": [{"activity": kind, "minutes": minutes} for kind, minutes in
                           (("rest", 1320), ("driving", 180), ("meal", 60),
                            ("waiting", 180), ("work", final_work), ("rest", 8340 - final_work))]}
    events, clock = [], 0

    def add(kind, minutes):
        nonlocal clock
        if minutes:
            events.append({"activity": kind, "minutes": minutes})
            clock += minutes

    days = 7 if name == "seven_workdays" else 6
    for day in range(days):
        start = day * 1440 + (600 if name == "short_daily_rest" and day == 0 else 359 if name == "short_daily_rest" and day == 1 else 480)
        add("rest", start - clock)
        drive = 90 if day >= 5 else 210
        for kind, minutes in (("work", 30), ("driving", drive), ("meal", 60), ("driving", drive), ("work", 30)):
            add(kind, minutes)
    add("rest", 10080 - clock)
    if name == "incomplete_week":
        events[-1]["minutes"] -= 1440
    return {"week_start": "2026-11-09", "carry_in_rest_minutes": 2880,
            "carry_in_consecutive_workdays": 0, "overtime_authorized": False, "events": events}
