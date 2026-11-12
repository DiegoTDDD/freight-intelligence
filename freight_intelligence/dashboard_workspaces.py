"""Brazilian observed freight and real-map routing workspaces."""

import hashlib
import io
import json
import os
from pathlib import Path
from zipfile import ZipFile

import polars as pl
import streamlit as st

from freight_intelligence.brazil_modes import load_modes
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
    view = st.selectbox("Brazilian freight coverage", ["Railway detail", "All five modes"],
                        key="brazil_view")
    if view == "All five modes":
        render_modes()
        return
    st.subheader(t("Brazilian railway freight"))
    st.caption(t("ANTT · reported cargo movements · 2006–2025 · complete calendar years"))
    st.info(
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
        st.error(t("The verified Brazilian data snapshot is unavailable."))
        return
    metric = st.selectbox(
        t("Metric"),
        ["tons", "tonne_km"],
        key="brazil_metric",
        format_func=lambda value: {
            "tons": t("Net tonnes (TU)"),
            "tonne_km": t("Net tonne-kilometres (TKU)"),
        }[value],
    )
    unit = "TU" if metric == "tons" else "TKU"
    year = st.selectbox(
        t("Year"),
        tables["annual"]["year"].to_list(),
        index=tables["annual"].height - 1,
        key="brazil_year",
    )
    annual = tables["annual"]
    total = annual.filter(pl.col("year") == year)[metric][0]
    prior = annual.filter(pl.col("year") == year - 1)
    with st.container(horizontal=True):
        st.metric(t("Reported movements"), f"{total:,.0f} {unit}")
        delta = (total / prior[metric][0] - 1) * 100 if prior.height and prior[metric][0] else None
        st.metric(t("Annual change"), f"{delta:+.2f}%" if delta is not None else "—")
        st.metric(t("Complete years"), annual.height)
    st.subheader(t("Observed railway history"))
    st.line_chart(
        annual.select("year", metric).rename({"year": t("Year"), metric: unit}), x=t("Year"), y=unit
    )
    st.subheader(t("Monthly movements"))
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
        st.subheader(t(heading))
        table = tables[name].filter(pl.col("year") == year).sort(metric, descending=True).head(20)
        st.dataframe(
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
    st.subheader(t("Forecast evaluation on reported history"))
    selected = metadata["selected_models"][metric]
    test = scores.filter(
        (pl.col("metric_type") == metric)
        & (pl.col("model") == selected)
        & (pl.col("phase") == "test")
    )
    st.caption(
        t(
            "Training starts with eight years. Models are selected on validation through 2022; "
            "2023–2025 are reserved for the final test. No model is chosen using test errors."
        )
    )
    with st.container(horizontal=True):
        st.metric(t("Selected baseline"), t(selected))
        st.metric(t("Test MAE"), f"{test['mae'][0]:,.0f} {unit}")
        st.metric(t("Test WAPE"), f"{test['wape'][0]:.2%}")
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
    st.dataframe(scores.filter(pl.col("metric_type") == metric), hide_index=True)
    st.subheader(t("Forecasts after the observed series"))
    st.warning(
        t(
            "Forecasts for 2026–2028 are model estimates, not observations. "
            "Administrative reports can be revised and coverage can change. "
            "A held-out test does not guarantee future accuracy."
        )
    )
    st.dataframe(forecast.filter(pl.col("metric_type") == metric), hide_index=True)
    st.download_button(
        t("Download observations and evaluation"),
        report,
        "antt_historico_avaliacao.zip",
        "application/zip",
    )
    st.download_button(
        t("Download annual data"),
        (root / "observations.csv").read_bytes(),
        "antt_observacoes_anuais.csv",
        "text/csv",
    )
    with st.expander(t("Sources, units and traceability")):
        st.markdown(
            "[ANTT — SIADE](https://dados.antt.gov.br/dataset/438a5184-09db-49a3-88c8-0bad418b4409)"
        )
        st.caption(
            t(
                "Source: ANTT. Administrative reported movements, not a census of unique shipments. "
                "The partial 2026 archive is excluded. License: Creative Commons Attribution."
            )
        )
        st.json(provenance)


def render_modes():
    st.subheader("Brazilian freight: five-mode indicator atlas")
    st.info("Official indicators for road, rail, water, air and pipelines. Each series has its "
            "own scope and unit. These are not comparable modal shares or complete shipment coverage.")
    try:
        data, metadata = load_modes()
    except (OSError, ValueError, KeyError, pl.exceptions.PolarsError):
        st.error("The verified modal indicator snapshot is unavailable.")
        return
    coverage = data.group_by("mode", "indicator", "unit", "scope").agg(
        pl.col("year").min().alias("first_year"), pl.col("year").max().alias("last_year")
    ).sort("mode", "indicator")
    st.dataframe(coverage, hide_index=True)
    mode = st.selectbox("Mode", sorted(data["mode"].unique()), key="brazil_mode")
    subset = data.filter(pl.col("mode") == mode)
    indicator = st.selectbox("Indicator", sorted(subset["indicator"].unique()),
                             key="brazil_indicator")
    series = subset.filter(pl.col("indicator") == indicator).sort("year")
    st.caption(series["scope"][0])
    st.metric("Latest reported indicator", f"{series['value'][-1]:,.2f} {series['unit'][0]}",
              help="Retains source unit and chart rounding; no conversion to common tonnage.")
    st.caption(f"Reference year: {series['year'][-1]}")
    st.line_chart(series.select("year", "value"), x="year", y="value")
    st.dataframe(series, hide_index=True)
    st.markdown(f"[Official source]({series['source_url'][0]})")
    st.download_button("Download all modal indicators (CSV)", data.write_csv().encode(),
                       "brazil_modal_indicators.csv", "text/csv")
    with st.expander("Coverage, quality notes and source hashes"):
        for note in metadata["quality_notes"]:
            st.warning(note)
        st.json(metadata)


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
    import pydeck as pdk

    st.subheader(t("Routes on real roads"))
    mode = st.selectbox("Routing engine", ["Car reference (OSRM)", "Truck (Valhalla)"],
                        key="routing_engine")
    truck = mode == "Truck (Valhalla)"
    truck_live = os.environ.get("LOGINEXUS_TRUCK_DEMO_ENABLED") == "true"
    if truck and not truck_live:
        st.info("Live truck routing is unavailable in this deployment. "
                "Use the saved truck example below to inspect the route and vehicle profile.")
    preset = st.selectbox("Demonstration truck profile", list(PROFILES), key="truck_profile") \
        if truck else None
    st.info(
        "Truck-specific route calculation on OpenStreetMap roads. Example profiles are editable; "
        "they are not legal vehicle categories or authorization to travel." if truck else t(
            "Use coordinates to obtain a reference driving route from OSRM/OpenStreetMap. "
            "The public demo is for light, noncommercial use and may be unavailable."
        )
    )
    st.warning(TRUCK_LIMITATIONS if truck else t(LIMITATIONS))
    with st.form("geographic_route_form", enter_to_submit=False):
        left, right = st.columns(2)
        with left:
            origin_lat = st.number_input(t("Origin latitude"), -85.0, 85.0, -23.5505, format="%.6f")
            origin_lon = st.number_input(
                t("Origin longitude"), -180.0, 180.0, -46.6333, format="%.6f"
            )
        with right:
            destination_lat = st.number_input(
                t("Destination latitude"), -85.0, 85.0, -22.9056, format="%.6f"
            )
            destination_lon = st.number_input(
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
                    vehicle[field] = st.number_input(
                        label, min_value=2 if field == "axle_count" else 0.1,
                        max_value=limits[field], value=PROFILES[preset][field],
                        key=f"truck_{preset}_{field}",
                    )
            vehicle["hazmat"] = st.checkbox("Hazardous materials", key="truck_hazmat")
        consent = st.checkbox(
            "Send these coordinates and truck profile to the public Valhalla service"
            if truck else t("Send these coordinates to the public OSRM service to calculate a route")
        )
        st.caption(
            t(
                "Coordinates are sent to an external service, which may log them. "
                "Do not submit private locations. Initial coordinates represent São Paulo and Campinas."
            )
        )
        submitted = st.form_submit_button(t("Calculate route on the map"),
                                         disabled=truck and not truck_live)
    saved_car = st.button(t("Show saved São Paulo–Campinas route (no new routing request)"))
    saved_truck = st.button("Show saved truck route: São Paulo–Campinas (no routing request)")
    if saved_car or saved_truck:
        st.session_state.pop("geographic_route", None)
        try:
            st.session_state["geographic_route"] = saved_route(
                "sao_paulo_campinas_truck.geojson" if saved_truck else "sao_paulo_campinas.geojson"
            )
        except (OSError, ValueError, KeyError, StopIteration):
            st.error("The verified saved route is unavailable.")
    if submitted:
        st.session_state.pop("geographic_route", None)
        if not consent:
            st.error(t("Confirm coordinate sharing before calculating a new route."))
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
                st.error(t(str(error)))
    result = st.session_state.get("geographic_route")
    if result is None:
        return
    feature = result["features"][0]
    props, path = feature["properties"], feature["geometry"]["coordinates"]
    st.caption(f"Calculated profile: {props['profile']} · {props['provider']}")
    st.caption(t(props["limitations"]))
    if props.get("vehicle"):
        st.json(props["vehicle"], expanded=False)
        with st.expander("Truck itinerary instructions"):
            for index, instruction in enumerate(props["instructions"], start=1):
                st.write(f"{index}. {instruction}")
    with st.container(horizontal=True):
        st.metric(t("Route distance (km)"), f"{props['distance_km']:,.2f}")
        st.metric(t("Estimated driving minutes"), f"{props['duration_minutes']:,.1f}")
    st.caption(
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
    st.markdown(
        "© [OpenStreetMap contributors](https://www.openstreetmap.org/copyright) · "
        + provider_link + " · "
        "[Fix the map](https://www.openstreetmap.org/fixthemap)"
    )
    st.caption(t("The basemap also loads tiles from an external map provider."))
    st.download_button(
        t("Download route GeoJSON"),
        json.dumps(result, ensure_ascii=False, indent=2),
        "rota_real.geojson",
        "application/geo+json",
    )
    with st.expander(t("Sources, units and traceability")):
        st.json(props)
