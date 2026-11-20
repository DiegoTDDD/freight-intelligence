"""Review declared seven-day activity records without persisting driver histories."""

import json

import polars as pl
import streamlit as st

from freight_intelligence.dashboard_ui import LocalizedUI
from freight_intelligence.optimization.weekly_duty import (
    example_history,
    load_policy,
    parse_history,
    review_week,
)


def render_weekly_duty(t):
    ui = LocalizedUI(t)

    def review_label(code):
        translated = t(code)
        labels = {"night_or_multiday_regime_requires_review": "Night or multi-day regime requires review",
                  "night_regime_and_reduced_hour_limits_require_review": "Night regime and reduced-hour limits require review",
                  "post_05_night_extension_requires_review": "Work after 05:00 needs night-extension review"}
        return translated if translated != code else labels.get(code, code.replace("_", " ").capitalize())

    ui.subheader("Seven-day duty review")
    ui.warning("Declared scenarios only. Actual driver records, payroll and collective or exempt regimes "
               "are not authenticated. No result authorizes dispatch.")
    try:
        policy = load_policy()
    except (OSError, ValueError, KeyError, TypeError):
        ui.error("Reviewed weekly-duty policy is unavailable.")
        return
    names = {"balanced_week": "Balanced declared week", "short_daily_rest": "Short daily rest",
             "seven_workdays": "Seven workdays", "incomplete_week": "Incomplete history",
             "night_shift": "Night shift and extension"}
    preset = ui.selectbox("Weekly example", list(names), format_func=names.get, key="weekly_example")
    ui.caption("Events cover consecutive minutes from Monday midnight. Rest must be explicitly declared; "
               "carry-in context may be null when unknown. Examples contain no real driver identities.")
    with ui.expander("Edit the declared activity history (JSON)"), st.form("weekly_duty_review_form", enter_to_submit=False):
        raw = st.text_area(t("Weekly activity JSON"), json.dumps(example_history(preset), indent=2),
                           height=240, max_chars=65536, key="weekly_json_" + preset)
        submitted = st.form_submit_button(t("Review declared week"))
    key = "weekly_review_" + preset
    if submitted or key not in st.session_state:
        st.session_state.pop(key, None)
        try:
            payload = parse_history(raw.encode("utf-8"))
            st.session_state[key] = {"input": payload, "review": review_week(payload)}
        except (ValueError, TypeError, KeyError, OSError) as error:
            ui.error(t(str(error)))
    saved = st.session_state.get(key)
    if saved is None:
        return
    result = saved["review"]
    ui.caption("Results use the last submitted JSON for the selected example.")
    ui.caption(t("Declared week starting: ") + result["week_start"] + t(" · Policy reviewed: ") + policy["reviewed_on"])
    columns = st.columns(3)
    with columns[0]:
        ui.metric("Covered hours", f"{result['covered_minutes'] / 60:.2f}")
    with columns[1]:
        ui.metric("Declared work hours", f"{result['total_work_minutes'] / 60:.2f}")
    with columns[2]:
        ui.metric("Selected-rule flags", len(result["violations"]))
    labels = {"within_selected_weekly_planning_limits": "Within the selected weekly planning limits",
              "selected_limits_exceeded": "Selected planning limits exceeded",
              "manual_review_required": "Separate review required"}
    ui.info(labels[result["status"]])
    night = result["night_accounting"]
    with st.container(border=True):
        ui.subheader("Night-work accounting")
        columns = st.columns(2)
        with columns[0]:
            ui.metric("Actual night work hours", f"{night['observed_night_work_minutes'] / 60:.2f}")
        with columns[1]:
            equivalent = night["base_window_equivalent_work_minutes"]
            value = f"{equivalent['numerator'] / equivalent['denominator'] / 60:.2f}" if equivalent else t("Unavailable")
            ui.metric("Base-window equivalent work hours", value)
        ui.caption("Actual night work counts only work from 22:00 to 05:00. The equivalent includes daytime work "
                   "plus night work at 52 minutes 30 seconds per nominal hour. Meals and rest are excluded. "
                   "Post-05:00 extension and pay require separate review; no wage is calculated.")
    if result["violations"]:
        ui.dataframe([{t("Review flags"): review_label(row["code"]), t("Minute in week"): row["minute"]}
                      for row in result["violations"]], hide_index=True)
    if result["review_reasons"]:
        ui.dataframe({t("Separate review required"): [review_label(value) for value in result["review_reasons"]]}, hide_index=True)
    daily = pl.DataFrame(result["daily_totals"]).select(
        pl.col("date").alias(t("Date")), (pl.col("work_minutes") / 60).alias(t("Declared work hours")))
    st.bar_chart(daily, x=t("Date"), y=t("Declared work hours"))
    ui.dataframe(pl.DataFrame(result["shifts"]), hide_index=True)
    with ui.expander("Declared rest periods and activity timeline"):
        ui.dataframe(pl.DataFrame(result["rest_periods"]), hide_index=True)
        ui.dataframe(pl.DataFrame(result["timeline"]), hide_index=True)
    ui.caption("Rule thresholds apply only to the supported reviewed dates. Future legal transitions, "
               "night-work regimes and incomplete boundaries need separate review; overtime is not automatically approved.")
    ui.download_button("Download weekly review (JSON)", json.dumps(saved, indent=2),
                       "declared_week_review.json", "application/json")
    with ui.expander("Weekly policy and sources"):
        st.json(policy)
