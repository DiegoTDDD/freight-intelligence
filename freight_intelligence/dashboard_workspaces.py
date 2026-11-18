"""Brazilian observed freight and real-map routing workspaces."""

import hashlib
import io
import json
import os
from pathlib import Path
from zipfile import ZipFile

import polars as pl
import streamlit as st

from freight_intelligence.brazil_air import CARGO_FIELDS, load_air
from freight_intelligence.brazil_gas_history import load_gas_history, missing_groups
from freight_intelligence.brazil_gas_results import load_gas
from freight_intelligence.brazil_modes import load_modes
from freight_intelligence.brazil_road import load_road, load_road_monthly
from freight_intelligence.brazil_water import load_water
from freight_intelligence.dashboard_ui import LocalizedUI
from freight_intelligence.optimization.geographic_routing import LIMITATIONS, request_route
from freight_intelligence.optimization.truck_routing import (
    LIMITATIONS as TRUCK_LIMITATIONS,
)
from freight_intelligence.optimization.truck_routing import PROFILES, request_truck_route

DEPLOYMENT = Path(__file__).resolve().parents[1] / "deployment"


@st.cache_data(ttl=3600, max_entries=2)
def load_brazil(signature):
    root = DEPLOYMENT / "brazil_data"
    provenance = json.loads((root / "provenance.json").read_bytes())
    for record in provenance["files"]:
        if Path(record["path"]).name != record["path"]:
            raise ValueError("Invalid snapshot path")
        if hashlib.sha256((root / record["path"]).read_bytes()).hexdigest() != record["sha256"]:
            raise ValueError("Brazil snapshot integrity mismatch")
    tables = {
        name: pl.read_parquet(root / f"{name}.parquet")
        for name in ("annual", "monthly", "commodities", "corridors", "railways")
    }
    report = (root / "historical_evaluation.zip").read_bytes()
    with ZipFile(io.BytesIO(report)) as bundle:
        metadata = json.loads(bundle.read("metadata.json"))
        predictions = pl.read_csv(bundle.read("predictions.csv"))
        scores = pl.read_csv(bundle.read("scores.csv"))
        forecast = pl.read_csv(bundle.read("forecast.csv"))
    return tables, provenance, report, metadata, predictions, scores, forecast


def render_brazil(t):
    ui = LocalizedUI(t)
    view = ui.selectbox("Brazilian freight coverage", ["Railway detail", "All five modes"],
                        key="brazil_view")
    if view == "All five modes":
        render_modes(t)
        return
    ui.subheader(t("Brazilian railway freight"))
    ui.caption(t("ANTT · reported cargo movements · 2006–2025 · complete calendar years"))
    ui.info(
        t(
            "Federal railway concessions only. These figures do not represent all Brazilian freight. "
            "Summing reported flows can count the same cargo again at successive railway movements."
        )
    )
    root = DEPLOYMENT / "brazil_data"
    try:
        signature = tuple(
            (p.name, p.stat().st_size, p.stat().st_mtime_ns) for p in sorted(root.iterdir())
        )
        tables, provenance, report, metadata, predictions, scores, forecast = load_brazil(signature)
    except (OSError, ValueError, KeyError, pl.exceptions.PolarsError):
        ui.error(t("The verified Brazilian data snapshot is unavailable."))
        return
    metric = ui.selectbox(
        t("Metric"),
        ["tons", "tonne_km"],
        key="brazil_metric",
        format_func=lambda value: {
            "tons": t("Net tonnes (TU)"),
            "tonne_km": t("Net tonne-kilometres (TKU)"),
        }[value],
    )
    unit = "TU" if metric == "tons" else "TKU"
    year = ui.selectbox(
        t("Year"),
        tables["annual"]["year"].to_list(),
        index=tables["annual"].height - 1,
        key="brazil_year",
    )
    annual = tables["annual"]
    total = annual.filter(pl.col("year") == year)[metric][0]
    prior = annual.filter(pl.col("year") == year - 1)
    with st.container(horizontal=True):
        ui.metric(t("Reported movements"), f"{total:,.0f} {unit}")
        delta = (total / prior[metric][0] - 1) * 100 if prior.height and prior[metric][0] else None
        ui.metric(t("Annual change"), f"{delta:+.2f}%" if delta is not None else "—")
        ui.metric(t("Complete years"), annual.height)
    ui.subheader(t("Observed railway history"))
    st.line_chart(
        annual.select("year", metric).rename({"year": t("Year"), metric: unit}), x=t("Year"), y=unit
    )
    ui.subheader(t("Monthly movements"))
    st.bar_chart(
        tables["monthly"]
        .filter(pl.col("year") == year)
        .select("month", metric)
        .rename({"month": t("Month"), metric: unit}),
        x=t("Month"),
        y=unit,
    )
    for name, heading in (
        ("commodities", "Main commodities"),
        ("corridors", "State-to-state flows"),
        ("railways", "Railway operators"),
    ):
        ui.subheader(t(heading))
        table = tables[name].filter(pl.col("year") == year).sort(metric, descending=True).head(20)
        ui.dataframe(
            table.rename(
                {
                    "year": t("Year"),
                    "tons": "TU",
                    "tonne_km": "TKU",
                    **{
                        column: t(column)
                        for column in table.columns
                        if column not in {"year", "tons", "tonne_km"}
                    },
                }
            ),
            hide_index=True,
        )
    ui.subheader(t("Forecast evaluation on reported history"))
    selected = metadata["selected_models"][metric]
    test = scores.filter(
        (pl.col("metric_type") == metric)
        & (pl.col("model") == selected)
        & (pl.col("phase") == "test")
    )
    ui.caption(
        t(
            "Training starts with eight years. Models are selected on validation through 2022; "
            "2023–2025 are reserved for the final test. No model is chosen using test errors."
        )
    )
    with st.container(horizontal=True):
        ui.metric(t("Selected baseline"), t(selected))
        ui.metric(t("Test MAE"), f"{test['mae'][0]:,.0f} {unit}")
        ui.metric(t("Test WAPE"), f"{test['wape'][0]:.2%}")
    rows = predictions.filter(
        (pl.col("metric_type") == metric)
        & (pl.col("model") == selected)
        & (pl.col("phase") == "test")
    )
    st.line_chart(
        rows.select("year", "actual", "prediction").rename(
            {"year": t("Year"), "actual": t("Observed"), "prediction": t("Forecast")}
        ),
        x=t("Year"),
        y=[t("Observed"), t("Forecast")],
    )
    ui.dataframe(scores.filter(pl.col("metric_type") == metric), hide_index=True)
    ui.subheader(t("Forecasts after the observed series"))
    ui.warning(
        t(
            "Forecasts for 2026–2028 are model estimates, not observations. "
            "Administrative reports can be revised and coverage can change. "
            "A held-out test does not guarantee future accuracy."
        )
    )
    ui.dataframe(forecast.filter(pl.col("metric_type") == metric), hide_index=True)
    ui.download_button(
        t("Download observations and evaluation"),
        report,
        "antt_historico_avaliacao.zip",
        "application/zip",
    )
    ui.download_button(
        t("Download annual data"),
        (root / "observations.csv").read_bytes(),
        "antt_observacoes_anuais.csv",
        "text/csv",
    )
    with ui.expander(t("Sources, units and traceability")):
        ui.markdown(
            "[ANTT — SIADE](https://dados.antt.gov.br/dataset/438a5184-09db-49a3-88c8-0bad418b4409)"
        )
        ui.caption(
            t(
                "Source: ANTT. Administrative reported movements, not a census of unique shipments. "
                "The partial 2026 archive is excluded. License: Creative Commons Attribution."
            )
        )
        st.json(provenance)


def render_modes(t):
    ui = LocalizedUI(t)
    ui.subheader("Brazilian freight: five-mode indicator atlas")
    ui.info("Official indicators for road, rail, water, air and pipelines. Each series has its "
            "own scope and unit. These are not comparable modal shares or complete shipment coverage.")
    try:
        data, metadata = load_modes()
    except (OSError, ValueError, KeyError, pl.exceptions.PolarsError):
        ui.error("The verified modal indicator snapshot is unavailable.")
        return
    coverage = data.group_by("mode", "indicator", "unit", "scope").agg(
        pl.col("year").min().alias("first_year"), pl.col("year").max().alias("last_year")
    ).sort("mode", "indicator")
    ui.dataframe(coverage, hide_index=True)
    mode = ui.selectbox("Mode", sorted(data["mode"].unique()), key="brazil_mode")
    subset = data.filter(pl.col("mode") == mode)
    indicator = ui.selectbox("Indicator", sorted(subset["indicator"].unique()),
                             key="brazil_indicator")
    series = subset.filter(pl.col("indicator") == indicator).sort("year")
    ui.caption(series["scope"][0])
    if "partial" in series["status"][0]:
        ui.warning("Observed subtotal with missing source fields. Coverage is disclosed in the "
                   "detailed mode view; do not treat it as complete national freight.")
    ui.metric("Latest reported indicator", f"{series['value'][-1]:,.2f} {series['unit'][0]}",
              help="Retains source unit and chart rounding; no conversion to common tonnage.")
    ui.caption(f"Reference year: {series['year'][-1]}")
    if series.height > 1:
        st.line_chart(series.select("year", "value"), x="year", y="value")
    else:
        st.bar_chart(series.select("year", "value"), x="year", y="value")
    ui.dataframe(series, hide_index=True)
    ui.markdown(f"[Official source]({series['source_url'][0]})")
    ui.download_button("Download all modal indicators (CSV)", data.write_csv().encode(),
                       "brazil_modal_indicators.csv", "text/csv")
    if mode == "pipeline":
        render_gas_movements(t)
    if mode == "water":
        render_water_freight(t)
    if mode == "road":
        render_road_flows(t)
    if mode == "air":
        render_air_freight(t)
    with ui.expander("Coverage, quality notes and source hashes"):
        for note in metadata["quality_notes"]:
            ui.warning(note)
        st.json(metadata)


def render_air_freight(t):
    ui = LocalizedUI(t)
    ui.subheader("ANAC air freight · airports and reported stages")
    try:
        tables, metadata, report = load_air()
    except (OSError, ValueError, KeyError, TypeError, pl.exceptions.PolarsError):
        ui.error("The verified ANAC air freight snapshot is unavailable.")
        return
    ui.info(metadata["interpretation"])
    view = ui.selectbox("Air freight view", ["Monthly history", "Airport pairs", "Airport totals",
                                            "Forecast evaluation"], key="air_view")
    nature = ui.selectbox("Air flight nature", ["domestic", "international"], key="air_nature")
    if view == "Forecast evaluation":
        ui.warning("Forecasts model observed paid-cargo subtotals, not complete demand or unique "
                   "consignments. Missing source fields remain excluded. Point forecasts have no uncertainty intervals.")
        name = nature + "_paid_observed_subtotal"
        scores = report["scores"].filter(pl.col("metric_type") == name)
        chosen = scores.filter(pl.col("selected") & (pl.col("phase") == "test"))
        ui.caption("Training starts in 2010 with eight years. Validation selects the model through "
                   "2022; 2023–2025 are reserved for test. Forecasts cover 2026–2028 after refitting.")
        ui.metric("Reserved-test WAPE", f"{chosen['wape'][0]:.2%}")
        ui.dataframe(scores, hide_index=True)
        forecasts = report["forecast"].filter(pl.col("metric_type") == name)
        st.line_chart(forecasts, x="year", y="forecast_value")
        ui.dataframe(forecasts, hide_index=True)
        ui.download_button("Download ANAC evaluation and forecast report", (DEPLOYMENT / "brazil_air/forecast.zip").read_bytes(),
                           "anac_observed_subtotal_evaluation.zip", "application/zip")
        return
    metric = ui.selectbox("Air cargo measure", list(CARGO_FIELDS), key="air_metric",
                          format_func={"paid_cargo_kg": "Paid cargo (kg)", "free_cargo_kg": "Free cargo (kg)",
                                       "mail_kg": "Mail (kg)"}.get)
    data = tables["monthly"] if view == "Monthly history" else tables["pairs"]
    years = sorted(data["year"].unique())
    year = ui.selectbox("Air reference year", years, index=len(years)-1, key=f"air_year_{view}")
    data = data.filter((pl.col("year") == year) & (pl.col("nature") == nature))
    month = ui.selectbox("Air reference month", [0, *range(1, 13)],
                         format_func=lambda value: "All months" if value == 0 else str(value), key="air_month")
    if month:
        data = data.filter(pl.col("month") == month)
    if view == "Airport pairs":
        origin = ui.selectbox("Air origin airport (source code)", ["All", *sorted(data["origin"].unique())], key="air_origin")
        destination = ui.selectbox("Air destination airport (source code)", ["All", *sorted(data["destination"].unique())], key="air_destination")
        if origin != "All":
            data = data.filter(pl.col("origin") == origin)
        if destination != "All":
            data = data.filter(pl.col("destination") == destination)
    ui.metric("Observed cargo subtotal (kg)", f"{data[metric].sum():,.0f}")
    missing = int(data[f"missing_{metric}"].sum())
    ui.metric("Missing source cargo fields", missing)
    if missing:
        ui.warning("Observed subtotal: missing cargo fields are counted and excluded, not imputed as zero.")
    if view == "Monthly history":
        st.bar_chart(data.sort("month"), x="month", y=metric)
        shown = data.sort("month")
    elif view == "Airport totals":
        direction = ui.selectbox("Air airport aggregation", ["origin", "destination"], key="air_direction")
        shown = data.group_by(direction).agg(pl.col(metric).sum()).rename({direction: "airport"})
        shown = shown.join(tables["airports"], on="airport", how="left").sort(metric, descending=True)
        st.bar_chart(shown.head(20), x="airport", y=metric)
        ui.caption("Departure and arrival totals overlap. Do not add them to calculate national freight.")
    else:
        shown = data.group_by("origin", "destination").agg(pl.col(metric).sum()).sort(metric, descending=True)
        ui.caption("Airport pairs describe reported flight stages, not booking availability or unique shipment OD. Detail covers 2024–2025.")
    ui.dataframe(shown.head(100), hide_index=True)
    ui.download_button("Download selected ANAC aggregates (CSV)", shown.write_csv().encode(),
                       "anac_selected_air_freight.csv", "text/csv")
    with ui.expander("ANAC source, coverage and airport reference"):
        st.json(metadata)
        ui.dataframe(tables["airports"], hide_index=True)


def render_road_flows(t):
    ui = LocalizedUI(t)
    try:
        data, metadata = load_road()
        monthly, _ = load_road_monthly()
    except (OSError, ValueError, KeyError, TypeError, pl.exceptions.PolarsError):
        ui.error("The verified regional road flow snapshot is unavailable.")
        return
    ui.subheader("Monthly road freight and annual reconciliation · 2025")
    reconciliation = metadata["reconciliation"]
    ui.metric("MDF-e tonnes · sum of 12 published months", f"{reconciliation['annual_tonnes']:,.0f}")
    ui.success("The 12 monthly totals sum to 1.3687 billion tonnes, consistent with the "
               "yearbook summary rounded to 1.4 billion. Includes paid and own-account transport.")
    st.bar_chart(monthly, x="month", y="tonnes")
    ui.dataframe(monthly, hide_index=True)
    ui.caption("Integer-tonne labels from ANTT Chart 45, not raw individual shipments. Paid "
               "shares are rounded percentages; they do not give exact paid tonnage. "
               "MDF-e excludes within-municipality trips and has other documented exemptions.")
    ui.download_button("Download monthly road tonnage (CSV)", monthly.write_csv().encode(),
                       "antt_monthly_road_tonnage_2025.csv", "text/csv")
    with ui.expander("How the annual total and regional reference are kept separate"):
        ui.write("The 1.165 billion-tonne figure is retained only as the publication's regional "
                 "reference. It is not substituted for the all-transport annual sum. The source "
                 "does not explain its scope difference; the project does not infer an exact "
                 "paid-only total from rounded percentages.")
        st.json(reconciliation)
        st.json(metadata["monthly_source"])
    ui.subheader("Reported regional road freight flows · 2025")
    ui.info(metadata["interpretation"])
    ui.warning("These are 16 selected regional flows, not complete national coverage or operational truck routes. "
               "A same-region flow is not necessarily a within-city trip.")
    origin = ui.selectbox("Road origin state", ["All", *sorted(data["origin_state"].unique())],
                          key="road_origin_state")
    destination = ui.selectbox("Road destination state",
                               ["All", *sorted(data["destination_state"].unique())],
                               key="road_destination_state")
    kind = ui.selectbox("Regional flow type", ["All published flows", "Within the same region",
                                               "Between different regions"], key="road_flow_type")
    view = data
    if origin != "All":
        view = view.filter(pl.col("origin_state") == origin)
    if destination != "All":
        view = view.filter(pl.col("destination_state") == destination)
    same = ((pl.col("origin_state") == pl.col("destination_state"))
            & (pl.col("origin_region") == pl.col("destination_region")))
    if kind != "All published flows":
        view = view.filter(same if kind == "Within the same region" else ~same)
    ui.metric("Published flows matching filters", view.height)
    if view.is_empty():
        ui.info("No published flow matches these filters. Unlisted flows are unavailable, not zero.")
    else:
        chart = view.with_columns(pl.concat_str("origin_state", pl.lit(" · "), "origin_region",
                                                pl.lit(" → "), "destination_state", pl.lit(" · "),
                                                "destination_region").alias("Regional flow"))
        st.bar_chart(chart, x="Regional flow", y="tonnes")
        ui.dataframe(view, hide_index=True)
    ui.caption("Shares are the source's rounded percentages, not shares of the filtered table. "
               "RGIs are groups of municipalities; no reverse flow or road geometry is inferred.")
    ui.download_button("Download published regional road flows (CSV)", data.write_csv().encode(),
                       "antt_regional_road_flows_2025.csv", "text/csv")
    with ui.expander("Road flow source and coverage"):
        st.json(metadata)


def render_water_freight(t):
    ui = LocalizedUI(t)
    ui.subheader("ANTAQ navigation and regional references")
    try:
        data, metadata = load_water()
    except (OSError, ValueError, KeyError, TypeError, pl.exceptions.PolarsError):
        ui.error("The verified ANTAQ reference snapshot is unavailable.")
        return
    labels = {"navigation_totals": "Navigation reference totals",
              "inland_commodities": "Leading inland cargo categories",
              "coastal_state_endpoints": "Coastal container origin/destination states",
              "grain_regions": "Maize/soybean regional port aggregates",
              "port_monthly": "Monthly port handling (2025)"}
    dataset = ui.selectbox("Water reference dataset", list(labels),
                           format_func=labels.get, key="brazil_water_dataset")
    view = data.filter(pl.col("dataset") == dataset)
    years = sorted(view["year"].unique())
    year = ui.selectbox("Water reference year", years, index=len(years) - 1,
                        key=f"water_year_{dataset}")
    view = view.filter(pl.col("year") == year)
    directions = sorted(view["direction"].unique())
    if directions != ["not_applicable"]:
        direction = ui.selectbox("Water reference direction", directions,
                                 key=f"water_direction_{dataset}")
        view = view.filter(pl.col("direction") == direction)
    ui.info(view["scope"][0])
    ui.warning("Reference populations overlap. Do not add port, navigation, export or endpoint "
               "totals together. State endpoints do not identify paired routes; absent states "
               "are unavailable, not zero.")
    unit = {"million_tonnes": "Million tonnes", "thousand_TEU": "Thousand TEU",
            "tonnes": "Tonnes"}[view["unit"][0]]
    chart = view.select("category", "value").rename({"category": "Category", "value": unit})
    st.bar_chart(chart, x="Category", y=unit)
    ui.dataframe(view, hide_index=True)
    ui.download_button("Download ANTAQ reference tables (CSV)", data.write_csv().encode(),
                       "antaq_navigation_references.csv", "text/csv")
    with ui.expander("ANTAQ source, precision and coverage"):
        st.json(metadata)


def render_gas_movements(t):
    ui = LocalizedUI(t)
    year = ui.selectbox("Gas reference year", [2024, 2025], index=1, key="brazil_gas_year")
    ui.subheader(f"Reported gas-pipeline movements · {year}")
    try:
        if year == 2025:
            data, _, metadata = load_gas()
        else:
            data, _, metadata = load_gas_history()
            data = data.filter(pl.col("year") == year)
    except (OSError, ValueError, KeyError, TypeError, pl.exceptions.PolarsError):
        ui.error("The verified ANP gas movement snapshot is unavailable.")
        return
    ui.info(metadata["interpretation"])
    if year < 2025:
        ui.warning("Historical coverage differs by operator and contract. Missing fields and "
                   "excluded identical duplicate rows are disclosed; year comparisons are not changes in unique national supply.")
    kind = ui.selectbox("Gas point type", ["delivery", "receipt"], key="brazil_gas_point_type")
    operators = ["All reported operators", *sorted(data["operator"].unique())]
    operator = ui.selectbox("Gas operator", operators, key="brazil_gas_operator")
    view = data.filter(pl.col("point_type") == kind)
    if operator != operators[0]:
        view = view.filter(pl.col("operator") == operator)
    with st.container(horizontal=True):
        ui.metric("Reported calendar months", view["month"].n_unique())
        ui.metric("Reported operators", view["operator_id"].n_unique())
        ui.metric("Missing daily cells", int(view["missing_daily_values"].sum()))
    monthly = view.group_by("month").agg(pl.col("volume_thousand_m3").sum()).sort("month")
    ui.caption("Reported signed-volume subtotals in thousand m³. Missing cells remain missing; "
               "the same gas can cross multiple operators. No production series is substituted.")
    st.bar_chart(monthly, x="month", y="volume_thousand_m3")
    ui.dataframe(view, hide_index=True)
    ui.download_button("Download ANP gas movements and coverage (CSV)", data.write_csv().encode(),
                       f"anp_gas_movements_{year}.csv", "text/csv")
    operator_ids = view["operator_id"].unique().to_list()
    groups = missing_groups(metadata, kind)
    groups = [row for row in groups if row["operator_id"] in operator_ids]
    with ui.expander("Investigated missing gas source values"):
        ui.caption("Blank source cells remain missing. Dates identify absent reports, not confirmed zero flows.")
        if groups:
            display = pl.DataFrame([{**row, "dates": ", ".join(row["dates"])} for row in groups])
            ui.dataframe(display.head(100), hide_index=True)
            ui.caption(f"Missing-source record groups: {len(groups)}; table shows at most 100.")
            ui.download_button("Download missing gas value diagnostics (CSV)", display.write_csv().encode(),
                               f"anp_missing_gas_values_{year}.csv", "text/csv")
        else:
            ui.info("No missing realized-volume cells in the selected operator/direction scope.")


@st.cache_data(ttl=86400, max_entries=64, show_spinner=False)
def cached_route(origin_lon, origin_lat, destination_lon, destination_lat):
    return request_route(origin_lon, origin_lat, destination_lon, destination_lat)


@st.cache_data(ttl=86400, max_entries=64, show_spinner=False)
def cached_truck_route(origin, destination, vehicle):
    return request_truck_route(origin, destination, vehicle)


def saved_route(filename):
    root = DEPLOYMENT / "route_examples"
    manifest = json.loads((root / "manifest.json").read_bytes())
    record = next(item for item in manifest["files"] if item["path"] == filename)
    if Path(filename).name != filename:
        raise ValueError("Invalid saved route path")
    raw = (root / filename).read_bytes()
    if len(raw) > 2 * 1024 * 1024 or hashlib.sha256(raw).hexdigest() != record["sha256"]:
        raise ValueError("Saved route integrity mismatch")
    return json.loads(raw)


def render_geographic_routes(t):
    ui = LocalizedUI(t)
    import pydeck as pdk

    ui.subheader(t("Routes on real roads"))
    mode = ui.selectbox("Routing engine", ["Car reference (OSRM)", "Truck (Valhalla)"],
                        key="routing_engine")
    truck = mode == "Truck (Valhalla)"
    truck_live = os.environ.get("LOGINEXUS_TRUCK_DEMO_ENABLED") == "true"
    if truck and not truck_live:
        ui.info("Live truck routing is unavailable in this deployment. "
                "Use the saved truck example below to inspect the route and vehicle profile.")
    preset = ui.selectbox("Demonstration truck profile", list(PROFILES), key="truck_profile") \
        if truck else None
    ui.info(
        "Truck-specific route calculation on OpenStreetMap roads. Example profiles are editable; "
        "they are not legal vehicle categories or authorization to travel." if truck else t(
            "Use coordinates to obtain a reference driving route from OSRM/OpenStreetMap. "
            "The public demo is for light, noncommercial use and may be unavailable."
        )
    )
    ui.warning(TRUCK_LIMITATIONS if truck else t(LIMITATIONS))
    with st.form("geographic_route_form", enter_to_submit=False):
        left, right = st.columns(2)
        with left:
            origin_lat = ui.number_input(t("Origin latitude"), -85.0, 85.0, -23.5505, format="%.6f")
            origin_lon = ui.number_input(
                t("Origin longitude"), -180.0, 180.0, -46.6333, format="%.6f"
            )
        with right:
            destination_lat = ui.number_input(
                t("Destination latitude"), -85.0, 85.0, -22.9056, format="%.6f"
            )
            destination_lon = ui.number_input(
                t("Destination longitude"), -180.0, 180.0, -47.0608, format="%.6f"
            )
        vehicle = None
        if truck:
            vehicle = {}
            columns = st.columns(3)
            labels = {"height": "Height (m)", "width": "Width (m)", "length": "Length (m)",
                      "weight": "Loaded gross weight (t)", "axle_load": "Maximum axle load (t)",
                      "axle_count": "Axle count"}
            limits = {"height": 10.0, "width": 10.0, "length": 50.0, "weight": 100.0,
                      "axle_load": 40.0, "axle_count": 12}
            for index, (field, label) in enumerate(labels.items()):
                with columns[index % 3]:
                    vehicle[field] = ui.number_input(
                        label, min_value=2 if field == "axle_count" else 0.1,
                        max_value=limits[field], value=PROFILES[preset][field],
                        key=f"truck_{preset}_{field}",
                    )
            vehicle["hazmat"] = ui.checkbox("Hazardous materials", key="truck_hazmat")
        consent = ui.checkbox(
            "Send these coordinates and truck profile to the public Valhalla service"
            if truck else t("Send these coordinates to the public OSRM service to calculate a route")
        )
        ui.caption(
            t(
                "Coordinates are sent to an external service, which may log them. "
                "Do not submit private locations. Initial coordinates represent São Paulo and Campinas."
            )
        )
        submitted = st.form_submit_button(t("Calculate route on the map"),
                                         disabled=truck and not truck_live)
    saved_car = ui.button(t("Show saved São Paulo–Campinas route (no new routing request)"))
    saved_truck = ui.button("Show saved truck route: São Paulo–Campinas (no routing request)")
    if saved_car or saved_truck:
        st.session_state.pop("geographic_route", None)
        try:
            st.session_state["geographic_route"] = saved_route(
                "sao_paulo_campinas_truck.geojson" if saved_truck else "sao_paulo_campinas.geojson"
            )
        except (OSError, ValueError, KeyError, StopIteration):
            ui.error("The verified saved route is unavailable.")
    if submitted:
        st.session_state.pop("geographic_route", None)
        if not consent:
            ui.error(t("Confirm coordinate sharing before calculating a new route."))
        else:
            try:
                with st.spinner(t("Calculating route…")):
                    st.session_state["geographic_route"] = (
                        cached_truck_route([origin_lon, origin_lat],
                                           [destination_lon, destination_lat], vehicle)
                        if truck else cached_route(
                            origin_lon, origin_lat, destination_lon, destination_lat
                        )
                    )
            except (ValueError, KeyError, TypeError, json.JSONDecodeError) as error:
                ui.error(t(str(error)))
    result = st.session_state.get("geographic_route")
    if result is None:
        return
    feature = result["features"][0]
    props, path = feature["properties"], feature["geometry"]["coordinates"]
    ui.caption(f"Calculated profile: {props['profile']} · {props['provider']}")
    ui.caption(t(props["limitations"]))
    if props.get("vehicle"):
        st.json(props["vehicle"], expanded=False)
        with ui.expander("Truck itinerary instructions"):
            for index, instruction in enumerate(props["instructions"], start=1):
                ui.write(f"{index}. {instruction}")
    with st.container(horizontal=True):
        ui.metric(t("Route distance (km)"), f"{props['distance_km']:,.2f}")
        ui.metric(t("Estimated driving minutes"), f"{props['duration_minutes']:,.1f}")
    ui.caption(
        t("The map shows the last calculated or loaded route. Edits apply on the next submission.")
    )
    st.pydeck_chart(
        pdk.Deck(
            layers=[
                pdk.Layer(
                    "GeoJsonLayer",
                    result,
                    stroked=True,
                    filled=False,
                    get_line_color=[0, 130, 125],
                    line_width_min_pixels=4,
                )
            ],
            initial_view_state=pdk.ViewState(
                longitude=(path[0][0] + path[-1][0]) / 2,
                latitude=(path[0][1] + path[-1][1]) / 2,
                zoom=8,
            ),
            map_style="light",
            tooltip={"text": f"{props['provider']} · OpenStreetMap"},
        )
    )
    provider_link = (
        "[Valhalla / FOSSGIS](https://valhalla.openstreetmap.de/)"
        if props["profile"] == "truck" else
        "[OSRM / FOSSGIS](https://routing.openstreetmap.de/about.html)"
    )
    ui.markdown(
        "© [OpenStreetMap contributors](https://www.openstreetmap.org/copyright) · "
        + provider_link + " · "
        "[Fix the map](https://www.openstreetmap.org/fixthemap)"
    )
    ui.caption(t("The basemap also loads tiles from an external map provider."))
    ui.download_button(
        t("Download route GeoJSON"),
        json.dumps(result, ensure_ascii=False, indent=2),
        "rota_real.geojson",
        "application/geo+json",
    )
    with ui.expander(t("Sources, units and traceability")):
        st.json(props)
