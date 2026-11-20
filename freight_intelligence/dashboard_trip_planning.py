"""Editable, offline corridor cost and daytime duty planning examples."""

import json

import streamlit as st

from freight_intelligence.dashboard_ui import LocalizedUI
from freight_intelligence.optimization.trip_planning import load_rules, plan_trip


def render_trip_planning(t):
    ui = LocalizedUI(t)
    ui.subheader("Trip cost and breaks")
    ui.info("Continuous SP-330/SP-348 travel between km 20 and km 100. Loaded trucks only. "
            "Selected plazas are calculated from chainage, independently of the route map.")
    ui.warning("Planning simulation: actual driver records, weekly rest, night work and safe stopping "
               "places are not verified. This result never authorizes dispatch.")
    try:
        rules = load_rules()
    except (OSError, ValueError, KeyError, TypeError):
        ui.error("Reviewed trip-planning rules are unavailable.")
        return
    ui.caption(t("Tariff reference date: ") + rules["reviewed_on"])
    with st.form("trip_planning_form", enter_to_submit=False):
        a, b, c = st.columns(3)
        with a:
            highway = ui.selectbox("Reference highway", ["SP-330", "SP-348"], key="trip_highway")
            origin = ui.number_input("Origin chainage (km)", 20.0, 100.0, 20.0, key="trip_origin")
            destination = ui.number_input("Destination chainage (km)", 20.0, 100.0, 100.0, key="trip_destination")
            axles = ui.number_input("Billable loaded axles", 2, 9, 2, key="trip_axles")
        inputs = {}
        fields = [("driving_minutes", "Planned driving (min)", 1, 720, 120),
                  ("prework_minutes", "Loading/prework (min)", 0, 720, 30),
                  ("waiting_minutes", "Waiting on duty (min)", 0, 720, 60),
                  ("postwork_minutes", "Delivery/postwork (min)", 1, 720, 30),
                  ("prior_drive_minutes", "Earlier continuous driving (min)", 0, 720, 0),
                  ("prior_work_minutes", "Earlier other work (min)", 0, 720, 0),
                  ("prior_rest_minutes", "Prior uninterrupted daily rest (min)", 0, 1440, 660),
                  ("shift_start_minute", "Shift start (minutes after midnight)", 0, 1439, 480)]
        for index, (key, label, low, high, default) in enumerate(fields):
            with b if index < 4 else c:
                inputs[key] = ui.number_input(label, low, high, default, key="trip_" + key)
        inputs["overtime_authorized"] = ui.checkbox("Up to two overtime hours authorized", key="trip_overtime")
        submitted = st.form_submit_button(t("Calculate cost and breaks"))
    if submitted or "trip_planning_result" not in st.session_state:
        st.session_state.pop("trip_planning_result", None)
        try:
            st.session_state["trip_planning_result"] = plan_trip(
                highway=highway, origin_km=origin, destination_km=destination, axles=axles, **inputs)
        except (ValueError, OSError, KeyError, TypeError) as error:
            ui.error(t(str(error)))
    result = st.session_state.get("trip_planning_result")
    if result is None:
        return
    ui.caption("Shown values use the last submitted inputs and the displayed tariff reference date.")
    quote, duty = result["tolls"], result["duty"]
    columns = st.columns(3)
    with columns[0]:
        ui.metric("Reviewed toll estimate (BRL)", f"{quote['total_cents'] / 100:.2f}")
    with columns[1]:
        ui.metric("Work including waiting (min)", duty["work_minutes"])
    with columns[2]:
        ui.metric("Shift elapsed including breaks (min)", duty["elapsed_minutes"])
    labels = {"within_selected_planning_limits": "Within the selected planning limits",
              "selected_limits_exceeded": "Selected planning limits exceeded",
              "manual_review_required": "Separate review required"}
    ui.info(labels[result["planning_status"]])
    if duty["violations"] or duty["unsupported_context"]:
        ui.dataframe({t("Review flags"): [t(value) for value in duty["violations"] + duty["unsupported_context"]]}, hide_index=True)
    ui.dataframe({t("Toll plaza"): [row["name"] for row in quote["crossings"]],
                  t("Amount (BRL)"): [row["total_cents"] / 100 for row in quote["crossings"]]}, hide_index=True)
    activities = {"prior_driving": "Earlier driving", "prior_other_work": "Earlier work",
                  "loading_or_prework": "Loading/prework", "waiting": "Waiting on duty",
                  "driving": "Driving", "meal_and_driving_break": "Meal and driving break",
                  "driving_break": "Driving break", "delivery_or_postwork": "Delivery/postwork"}
    ui.dataframe([{t("Activity"): t(activities[row["activity"]]), t("From shift minute"): row["start_minute"],
                   t("To shift minute"): row["end_minute"], t("Counts as work"): row["counts_as_work"]}
                  for row in duty["timeline"]], hide_index=True)
    ui.caption("Breaks are time slots, not verified places to stop. Waiting counts as work. "
               "The scenario uses a full one-hour meal, even for short trips.")
    ui.download_button("Download trip-planning scenario (JSON)", json.dumps(result, indent=2),
                       "trip_planning_scenario.json", "application/json")
    with ui.expander("Trip-planning sources and limits"):
        for source in result["sources"]:
            st.markdown(f"[{source['id']}]({source['url']})")
        st.json(result)
