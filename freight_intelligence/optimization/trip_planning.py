"""Dated corridor toll estimates and selected Brazilian daytime duty checks."""

import hashlib
import json
import math
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

DEFAULT_ROOT = Path(__file__).resolve().parents[2] / "deployment/trip_planning"


def load_rules(root=DEFAULT_ROOT):
    root = Path(root)
    if (root / "manifest.json").stat().st_size > 8192:
        raise ValueError("Oversized trip-planning manifest")
    manifest = json.loads((root / "manifest.json").read_bytes())
    record, = manifest["files"]
    if manifest.get("schema_version") != 1 or record["path"] != "rules.json":
        raise ValueError("Invalid trip-planning manifest")
    path = root / "rules.json"
    if path.stat().st_size > 65536:
        raise ValueError("Trip-planning rules exceed size limit")
    raw = path.read_bytes()
    if len(raw) != record["bytes"] or hashlib.sha256(raw).hexdigest() != record["sha256"]:
        raise ValueError("Trip-planning rules integrity mismatch")
    rules = json.loads(raw)
    date.fromisoformat(rules["reviewed_on"])
    date.fromisoformat(rules["tariff_effective_from"])
    if (rules.get("schema_version") != 1 or rules["currency"] != "BRL"
            or len(rules["stations"]) != 8 or len({s["id"] for s in rules["stations"]}) != 8):
        raise ValueError("Invalid reviewed trip-planning population")
    keys = {"continuous_driving_minutes", "driving_break_minutes", "meal_minutes",
            "prior_continuous_rest_minutes", "normal_work_minutes",
            "authorized_overtime_work_minutes", "max_shift_span_minutes"}
    limits = rules["limits"]
    if (set(limits) != keys or any(type(v) is not int or not 0 < v <= 1440 for v in limits.values())
            or limits["authorized_overtime_work_minutes"] < limits["normal_work_minutes"]
            or limits["prior_continuous_rest_minutes"] + limits["max_shift_span_minutes"] != 1440):
        raise ValueError("Invalid reviewed duty limits")
    for station in rules["stations"]:
        if (station["highway"] not in {"SP-330", "SP-348"}
                or type(station["commercial_per_axle_cents"]) is not int
                or not 0 < station["commercial_per_axle_cents"] < 100000):
            raise ValueError("Invalid reviewed commercial toll")
        for side in ("north_km", "south_km"):
            try:
                position = Decimal(station[side])
            except InvalidOperation as error:
                raise ValueError("Invalid toll chainage") from error
            if not position.is_finite() or not 0 < position < 200:
                raise ValueError("Invalid toll chainage")
    return rules


def integer(value, low, high, field):
    if type(value) is not int or not low <= value <= high:
        raise ValueError(f"{field} must be an integer between {low} and {high}")
    return value


def toll_quote(rules, highway, origin_km, destination_km, axles, as_of):
    integer(axles, 2, 9, "Billable axles")
    if highway not in {"SP-330", "SP-348"}:
        raise ValueError("Only the reviewed SP-330/SP-348 corridor is supported")
    positions = []
    for value in (origin_km, destination_km):
        if type(value) not in (int, float) or not math.isfinite(value) or not 20 <= value <= 100:
            raise ValueError("Choose corridor chainages between km 20 and km 100")
        positions.append(Decimal(str(value)))
    origin, destination = positions
    if origin == destination:
        raise ValueError("Choose different origin and destination chainages")
    as_of = date.fromisoformat(as_of) if isinstance(as_of, str) else as_of
    if type(as_of) is not date:
        raise ValueError("An explicit reference date is required")
    base = {"highway": highway, "origin_km": str(origin), "destination_km": str(destination),
            "billable_axles": axles, "as_of": as_of.isoformat(), "currency": "BRL",
            "tariff_effective_from": rules["tariff_effective_from"], "reviewed_on": rules["reviewed_on"]}
    if not date.fromisoformat(rules["tariff_effective_from"]) <= as_of <= date.fromisoformat(rules["reviewed_on"]):
        return {**base, "status": "outside_reviewed_date_window", "total_cents": None, "crossings": []}
    direction = "north" if destination > origin else "south"
    stations = [s for s in rules["stations"] if s["highway"] == highway]
    for station in stations:
        if Decimal(station[direction + "_km"]) in positions:
            raise ValueError("An endpoint exactly on a toll plaza is ambiguous; specify its approach side")
    crossed = [s for s in stations if min(positions) < Decimal(s[direction + "_km"]) < max(positions)]
    crossed.sort(key=lambda s: Decimal(s[direction + "_km"]), reverse=direction == "south")
    lines = [{"station_id": s["id"], "name": s["name"], "chainage_km": s[direction + "_km"],
              "per_axle_cents": s["commercial_per_axle_cents"],
              "total_cents": s["commercial_per_axle_cents"] * axles} for s in crossed]
    return {**base, "direction": direction, "status": "reviewed_date_estimate",
            "crossings": lines, "total_cents": sum(row["total_cents"] for row in lines)}


def duty_plan(rules, *, driving_minutes=120, prework_minutes=30, waiting_minutes=60,
              postwork_minutes=30, prior_drive_minutes=0, prior_work_minutes=0,
              prior_rest_minutes=660, overtime_authorized=False, shift_start_minute=480):
    inputs = {"driving_minutes": driving_minutes, "prework_minutes": prework_minutes,
              "waiting_minutes": waiting_minutes, "postwork_minutes": postwork_minutes,
              "prior_drive_minutes": prior_drive_minutes, "prior_work_minutes": prior_work_minutes,
              "prior_rest_minutes": prior_rest_minutes, "overtime_authorized": overtime_authorized,
              "shift_start_minute": shift_start_minute}
    for name in ("driving_minutes", "prework_minutes", "waiting_minutes", "postwork_minutes",
                 "prior_drive_minutes", "prior_work_minutes"):
        integer(inputs[name], 1 if name in {"driving_minutes", "postwork_minutes"} else 0, 720, name)
    integer(prior_rest_minutes, 0, 1440, "prior_rest_minutes")
    integer(shift_start_minute, 0, 1439, "shift_start_minute")
    if type(overtime_authorized) is not bool:
        raise ValueError("Overtime authorization must be Boolean")
    limits = rules["limits"]
    violations, timeline = [], []
    elapsed, meal_added = 0, False

    def event(kind, minutes, work):
        nonlocal elapsed
        if minutes:
            timeline.append({"activity": kind, "start_minute": elapsed, "end_minute": elapsed + minutes,
                             "minutes": minutes, "counts_as_work": work})
            elapsed += minutes

    if prior_rest_minutes < limits["prior_continuous_rest_minutes"]:
        violations.append("insufficient_prior_continuous_daily_rest")
    if prior_drive_minutes > limits["continuous_driving_minutes"]:
        violations.append("prior_continuous_driving_limit_exceeded")
    event("prior_driving", prior_drive_minutes, True)
    event("prior_other_work", prior_work_minutes, True)
    event("loading_or_prework", prework_minutes, True)
    event("waiting", waiting_minutes, True)  # ADI 5322: waiting is not off-duty rest.
    remaining, continuous = driving_minutes, prior_drive_minutes
    while remaining:
        capacity = max(0, limits["continuous_driving_minutes"] - continuous)
        if capacity == 0:
            kind = "meal_and_driving_break" if not meal_added else "driving_break"
            duration = limits["meal_minutes"] if not meal_added else limits["driving_break_minutes"]
            event(kind, duration, False)
            meal_added, continuous = True, 0
            continue
        block = min(remaining, capacity)
        event("driving", block, True)
        continuous += block
        remaining -= block
    if not meal_added:
        # Keep an actual work activity after the intrashift meal, even for a short route.
        event("meal_and_driving_break", limits["meal_minutes"], False)
    event("delivery_or_postwork", postwork_minutes, True)
    work = sum(row["minutes"] for row in timeline if row["counts_as_work"])
    allowed = limits["authorized_overtime_work_minutes"] if overtime_authorized else limits["normal_work_minutes"]
    if work > allowed:
        violations.append("selected_daily_work_limit_exceeded")
    if elapsed > limits["max_shift_span_minutes"]:
        violations.append("shift_leaves_less_than_11_hours_in_24_hour_cycle")
    unsupported = []
    if shift_start_minute < 300 or shift_start_minute + elapsed > 1320:
        unsupported.append("night_work_or_multiday_requires_separate_review")
    return {"inputs": inputs, "timeline": timeline, "work_minutes": work, "elapsed_minutes": elapsed,
            "selected_work_limit_minutes": allowed, "overtime_minutes": max(0, work - limits["normal_work_minutes"]),
            "violations": violations, "unsupported_context": unsupported,
            "status": "selected_limits_exceeded" if violations else "manual_review_required" if unsupported else "within_selected_planning_limits",
            "dispatch_authorized": False,
            "unverified": ["Actual driver history and tachograph records", "Weekly rest and collective agreements",
                           "Night-work conversion and payroll", "Safe stopping places, traffic and loading forecasts"]}


def plan_trip(*, highway="SP-330", origin_km=20.0, destination_km=100.0, axles=2,
              as_of=None, root=DEFAULT_ROOT, **duty_inputs):
    rules = load_rules(root)
    quote = toll_quote(rules, highway, origin_km, destination_km, axles, as_of or rules["reviewed_on"])
    duty = duty_plan(rules, **duty_inputs)
    return {"tolls": quote, "duty": duty, "sources": rules["sources"], "reviewed_on": rules["reviewed_on"],
            "planning_status": "manual_review_required" if quote["total_cents"] is None else duty["status"],
            "vehicle_scope": rules["vehicle_scope"], "labor_scope": rules["labor_scope"],
            "interpretation": rules["interpretation"], "dispatch_authorized": False}
