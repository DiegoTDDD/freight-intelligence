"""Conditional continuation arithmetic; never determine employment-rule applicability."""


def extension_sensitivity(timeline, shifts, base, policy, supported):
    limits, window = policy["limits"], policy["night_accounting"]

    def comparison(numerator, reference):
        return {"reference_minutes": reference if supported else None,
                "exceeded": numerator > reference * 7 if supported else None,
                "excess_equivalent_minutes": {"numerator": max(0, numerator - reference * 7), "denominator": 7} if supported else None}

    scenarios, total_candidate = [], 0
    for shift, original in zip(shifts, base["shift_reference_comparisons"], strict=True):
        work = [event for event in timeline if event["counts_as_work"]
                and shift["start_minute"] <= event["start_minute"] < shift["end_minute"]]
        continuations = []
        for day in range(shift["start_minute"] // 1440, (shift["end_minute"] - 1) // 1440 + 1):
            five, twenty_two = day * 1440 + window["end_minute"], day * 1440 + window["start_minute"]
            night_start = (day - 1) * 1440 + window["start_minute"]
            preceding_night_work = any(min(e["end_minute"], five) > max(e["start_minute"], night_start) for e in work)
            if not preceding_night_work:
                continue
            # These daytime intervals are disjoint; base night windows are never counted twice.
            end = min(twenty_two, shift["end_minute"])
            minutes = sum(max(0, min(e["end_minute"], end) - max(e["start_minute"], five)) for e in work)
            if minutes:
                continuations.append({"start_minute": five, "end_minute": end, "observed_work_minutes": minutes,
                                      "full_22_to_05_shift_span_observed": night_start >= 0 and shift["start_minute"] <= night_start})
        candidate = sum(c["observed_work_minutes"] for c in continuations)
        total_candidate += candidate
        numerator = original["real_work_minutes"] * 7 + original["night_work_minutes"] + candidate
        scenarios.append({"start_minute": shift["start_minute"], "end_minute": shift["end_minute"],
                          "candidate_work_minutes": candidate, "continuation_windows": continuations,
                          "conditional_equivalent_work_minutes": {"numerator": numerator, "denominator": 7} if supported else None,
                          **comparison(numerator, shift["work_limit_minutes"])})
    total_work = base["observed_night_work_minutes"] + base["observed_day_work_minutes"]
    numerator = total_work * 7 + base["observed_night_work_minutes"] + total_candidate
    return {"profile": policy["extension_sensitivity_profile"], "applicability": "not_determined",
            "candidate_work_minutes": total_candidate,
            "conditional_equivalent_work_minutes": {"numerator": numerator, "denominator": 7} if supported else None,
            "increment_over_base_equivalent_minutes": {"numerator": total_candidate, "denominator": 7} if supported else None,
            "shift_scenarios": scenarios, "week_reference_comparison": comparison(numerator, limits["normal_week_minutes"]),
            "replaces_base_result": False, "wages_calculated": False,
            "assumption": "If applicable, also reduce observed 05:00-22:00 work in the same declared shift following observed night work. Meals/rest are excluded. No applicability, payroll or dispatch decision."}
