"""Brazilian observed freight and real-map routing workspaces."""

import hashlib
import io
import json
from pathlib import Path
from zipfile import ZipFile

import polars as pl
import streamlit as st

from freight_intelligence.optimization.geographic_routing import LIMITATIONS, request_route

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
            "tons": "Toneladas úteis (TU)",
            "tonne_km": "Toneladas-quilômetro úteis (TKU)",
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


@st.cache_data(ttl=86400, max_entries=64, show_spinner=False)
def cached_route(origin_lon, origin_lat, destination_lon, destination_lat):
    return request_route(origin_lon, origin_lat, destination_lon, destination_lat)


def render_geographic_routes(t):
    import pydeck as pdk

    st.subheader(t("Routes on real roads"))
    st.info(
        t(
            "Use coordinates to obtain a reference driving route from OSRM/OpenStreetMap. "
            "The public demo is for light, noncommercial use and may be unavailable."
        )
    )
    st.warning(LIMITATIONS)
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
        consent = st.checkbox(
            t("Send these coordinates to the public OSRM service to calculate a route")
        )
        st.caption(
            t(
                "Coordinates are sent to an external service, which may log them. "
                "Do not submit private locations. Initial coordinates represent São Paulo and Campinas."
            )
        )
        submitted = st.form_submit_button(t("Calculate route on the map"))
    if st.button(t("Show saved São Paulo–Campinas route (no new routing request)")):
        st.session_state["geographic_route"] = json.loads(
            (DEPLOYMENT / "route_examples/sao_paulo_campinas.geojson").read_bytes()
        )
    if submitted:
        st.session_state.pop("geographic_route", None)
        if not consent:
            st.error(t("Confirm coordinate sharing before calculating a new route."))
        else:
            try:
                with st.spinner(t("Calculating route…")):
                    st.session_state["geographic_route"] = cached_route(
                        origin_lon, origin_lat, destination_lon, destination_lat
                    )
            except (ValueError, KeyError, TypeError, json.JSONDecodeError) as error:
                st.error(str(error))
    result = st.session_state.get("geographic_route")
    if result is None:
        return
    feature = result["features"][0]
    props, path = feature["properties"], feature["geometry"]["coordinates"]
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
            tooltip={"text": "OSRM · OpenStreetMap"},
        )
    )
    st.markdown(
        "© [OpenStreetMap contributors](https://www.openstreetmap.org/copyright) · "
        "[OSRM / FOSSGIS](https://routing.openstreetmap.de/about.html) · "
        "[Corrigir o mapa / Fix the map](https://www.openstreetmap.org/fixthemap)"
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
