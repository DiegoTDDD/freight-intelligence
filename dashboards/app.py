import hashlib
import io
import json
import os
from datetime import date
from functools import partial
from pathlib import Path
from zipfile import ZipFile

import polars as pl
import streamlit as st

from freight_intelligence.api.transport_results import load_transport_results
from freight_intelligence.dashboard_data import file_signature, load_projection_bundle
from freight_intelligence.dashboard_i18n import translate
from freight_intelligence.dashboard_workspaces import render_brazil, render_geographic_routes
from freight_intelligence.evaluation_results import load_temporal_report
from freight_intelligence.ml.annual_forecast import INTERPRETATION
from freight_intelligence.ml.faf_historical import prepare_report
from freight_intelligence.ml.historical_evaluation import historical_report
from freight_intelligence.optimization.planner import (
    compare_solutions,
    parse_scenario_json,
    replace_planner_inputs,
    simulate_scenario,
    snapshot_solution,
)
from freight_intelligence.optimization.road_routing import route_vehicle

ROOT = Path(os.environ.get("LOGINEXUS_DASHBOARD_DATA_ROOT", Path(__file__).resolve().parents[1]))
BASE = ROOT / "data/gold/faf5"

st.set_page_config(
    page_title="Freight Intelligence",
    page_icon="🚚",
    layout="wide",
)

language = st.sidebar.selectbox(
    "Language / Idioma",
    ["en", "pt"],
    index=1 if os.environ.get("LOGINEXUS_LANGUAGE") == "pt" else 0,
    format_func=lambda value: {"pt": "Português", "en": "English"}[value],
    key="language",
)
t = partial(translate, language=language)


def show_table(data, **options):
    """Localize displayed headers while preserving downloadable/internal schemas."""
    if hasattr(data, "columns") and language == "pt":
        options.setdefault("column_config", {column: t(column) for column in data.columns})
    return st.dataframe(data, **options)


st.title(t("LogiNexus"))
st.caption(t("Freight intelligence · FAF5 analytics"))

view = st.sidebar.selectbox(
    t("Workspace"),
    [
        "Freight analytics",
        "Brazilian freight",
        "Real road routes",
        "Scenario extrapolations",
        "Temporal evaluation",
        "Historical observations",
        "Transport plan",
        "Scenario planner",
        "Supplied road route",
    ],
    key="workspace",
    format_func=lambda value: str(t(value)),
)
st.sidebar.caption(t("Browse saved results or try a transport scenario."))


if view == "Brazilian freight":
    render_brazil(t)
    st.stop()

if view == "Real road routes":
    render_geographic_routes(t)
    st.stop()

if view == "Supplied road route":
    st.subheader(t("Route on a supplied road network"))
    st.info(
        t(
            "Provide a directed road graph, vehicle dimensions and costs. This tool does not "
            "download maps or verify current road conditions. No network is preloaded."
        )
    )
    st.caption(
        t(
            "JSON requires network, vehicle, origin and destination. Each link must declare "
            "distance_km, toll, max_gross_weight_t, max_height_m and closed, plus its ids/endpoints."
        )
    )
    with st.form("road_route", enter_to_submit=False):
        uploaded = st.file_uploader(
            t("Road network and vehicle JSON"), type=["json"], max_upload_size=8, key="road_upload"
        )
        pasted = st.text_area(
            t("Or paste routing request JSON"), height=220, max_chars=262144, key="road_request"
        )
        st.caption(
            t("Selected file takes precedence over pasted JSON. No files are saved on the server.")
        )
        submitted = st.form_submit_button(t("Calculate supplied-network route"))
    if submitted:
        st.session_state.pop("road_result", None)
        try:
            payload = uploaded.getvalue() if uploaded is not None else pasted.encode("utf-8")
            if not payload or len(payload) > 8 * 1024 * 1024:
                raise ValueError("Routing request must be nonempty and at most 8 MiB")
            request = json.loads(payload.decode("utf-8-sig"))
            if not isinstance(request, dict):
                raise TypeError("Routing request must be an object")
            result = route_vehicle(
                request.get("network"),
                request.get("vehicle"),
                request.get("origin"),
                request.get("destination"),
            )
            result["input_sha256"] = hashlib.sha256(payload).hexdigest()
            st.session_state["road_result"] = result
        except (ValueError, TypeError, OverflowError, RecursionError) as error:
            st.error(t(f"Supplied-network route failed: {error}"))
    result = st.session_state.get("road_result")
    if result is not None:
        st.subheader(t("Last submitted route"))
        st.warning(t(result["interpretation"]))
        st.caption(t(f"Source: {result['source']} · Vehicle: {result['vehicle_id']}"))
        st.caption(t("Pending input edits apply only after calculating a new route."))
        with st.container(horizontal=True):
            st.metric(t("Route distance (km)"), f"{result['distance_km']:,.2f}", border=True)
            st.metric(
                t(f"Supplied cost ({result['cost_unit']})"),
                f"{result['total_cost']:,.2f}",
                border=True,
            )
            st.metric(
                t("Links excluded by restrictions"), len(result["excluded_edges"]), border=True
            )
        st.write(t("Ordered nodes:"), result["nodes"])
        st.write(t("Ordered links:"), result["edges"])
        if result.get("legs"):
            st.subheader(t("Cost and distance by link"))
            st.caption(
                t(f"Distance costs and tolls use {result['cost_unit']} supplied by the input.")
            )
            show_table(
                pl.DataFrame(result["legs"]).select(
                    "sequence",
                    "edge_id",
                    "origin",
                    "destination",
                    "distance_km",
                    "distance_cost",
                    "toll",
                    "total_cost",
                ),
                hide_index=True,
            )
        with st.expander(t("Excluded links and input traceability")):
            st.write(t(result.get("excluded_edge_reasons", result["excluded_edges"])))
            st.code(result["input_sha256"])
        st.download_button(
            t("Download supplied-network route"),
            json.dumps(result, indent=2, allow_nan=False),
            "road_route.json",
            mime="application/json",
            key="road_download",
        )
    st.stop()


if view == "Historical observations":
    st.subheader(t("Historical observations evaluation"))
    st.info(
        t(
            "Evaluate an identified annual series. Source classification is declared by its provider. "
            "The included example is synthetic; it does not establish accuracy on real freight."
        )
    )
    examples = Path(__file__).resolve().parents[1] / "docs/examples"
    st.caption(
        t(
            "Local FAF5.5.1 estimates can be evaluated separately for 2017–2021. "
            "This reads existing annual totals only; it does not run ingestion."
        )
    )
    if st.button(t("Evaluate local FAF historical estimates"), key="historical_faf"):
        st.session_state.pop("historical_result", None)
        try:
            gold_path = BASE / "annual_kpis.parquet"
            documentation_path = (
                ROOT / "data/raw/faf5/forecast/bts_FAF_HiLoForecasts_README_20230929.txt"
            )
            if gold_path.stat().st_size > 2097152 or documentation_path.stat().st_size > 65536:
                raise ValueError("Local annual totals or documentation exceed expected size limits")
            st.session_state["historical_result"] = prepare_report(
                gold_path.read_bytes(), documentation_path.read_bytes(), date.today().isoformat()
            )
            st.success(t("Local historical estimates evaluated. Projection years were excluded."))
        except (OSError, ValueError, pl.exceptions.PolarsError) as error:
            st.error(t(f"Local FAF historical estimates unavailable: {error}"))
    if st.button(t("Load synthetic historical example"), key="historical_example"):
        st.session_state["historical_csv"] = (examples / "historical_synthetic.csv").read_text(
            encoding="utf-8"
        )
        st.session_state["historical_manifest"] = (
            examples / "historical_synthetic_manifest.json"
        ).read_text(encoding="utf-8")
        st.session_state.pop("historical_result", None)
    with st.form("historical_evaluation", enter_to_submit=False):
        csv_file = st.file_uploader(
            t("Annual observations CSV"), type=["csv"], max_upload_size=2, key="historical_file"
        )
        csv_text = st.text_area(
            t("Or paste annual CSV"), height=160, max_chars=2097152, key="historical_csv"
        )
        manifest_text = st.text_area(
            t("Source manifest JSON"), height=200, max_chars=65536, key="historical_manifest"
        )
        st.caption(
            t(
                "CSV columns: metric_type, year, total_value. A selected file takes precedence "
                "over pasted CSV. The manifest identifies source, scope, date, units and record kind."
            )
        )
        training = st.number_input(t("Minimum training points"), 2, 100, 4, key="historical_train")
        testing = st.number_input(t("Reserved test points"), 1, 100, 3, key="historical_test")
        forecast_years = st.number_input(
            t("Forecast years after each series"), 0, 10, 0, key="historical_forecast_years"
        )
        st.caption(t("Zero creates an evaluation only. Forecasts are optional point estimates."))
        submitted = st.form_submit_button(t("Evaluate historical series"))
    if submitted:
        st.session_state.pop("historical_result", None)
        try:
            source = csv_file.getvalue() if csv_file is not None else csv_text.encode("utf-8")
            st.session_state["historical_result"] = historical_report(
                source,
                manifest_text.encode("utf-8"),
                int(training),
                int(testing),
                int(forecast_years),
            )
        except (
            ValueError,
            TypeError,
            OverflowError,
            RecursionError,
            pl.exceptions.PolarsError,
        ) as error:
            st.error(t(f"Historical evaluation failed: {error}"))
    result = st.session_state.get("historical_result")
    if result is not None:
        with ZipFile(io.BytesIO(result)) as archive:
            metadata = json.loads(archive.read("metadata.json"))
            scores = pl.read_csv(archive.read("scores.csv"))
            predictions = pl.read_csv(archive.read("predictions.csv"))
            observations = pl.read_csv(archive.read("observations.csv"))
            forecast = (
                pl.read_csv(archive.read("forecast.csv"))
                if "forecast.csv" in archive.namelist()
                else None
            )
            lineage = (
                json.loads(archive.read("lineage.json"))
                if "lineage.json" in archive.namelist()
                else None
            )
        st.subheader(t("Last submitted evaluation"))
        st.warning(t(metadata["interpretation"]))
        provenance = metadata["provenance"]
        st.caption(t(f"Dataset: {provenance['dataset_id']} · Scope: {provenance['scope']}"))
        st.caption(t(f"Source: {provenance['source']} · Retrieved: {provenance['retrieved_at']}"))
        st.caption(t("Input edits apply only after submitting a new evaluation."))
        st.caption(
            t(
                f"Submitted split: minimum training {metadata['min_train_points']} points; "
                f"reserved test {metadata['test_points']} points per metric."
            )
        )
        if lineage is not None:
            st.warning(t(lineage["reserved_test"]))
            with st.expander(t("Historical subset and source traceability")):
                st.write(t("Included years:"), lineage["included_years"])
                st.write(t("Excluded years:"), lineage["excluded_years"])
                st.caption(t(lineage["classification_basis"]))
                st.caption(t(lineage["limitations"]))
                st.code(
                    f"Gold SHA-256: {lineage['gold_sha256']}\n"
                    f"Documentation SHA-256: {lineage['documentation_sha256']}"
                )
        st.write(t("Units:"), provenance["units"])
        st.write(t("Selected baselines:"), metadata["selected_models"])
        st.caption(t("Selection uses validation MAE only; the final test is reserved."))
        metric = st.selectbox(
            t("Historical metric"),
            sorted(metadata["selected_models"]),
            key="historical_metric",
            format_func=lambda value: str(t(value)),
        )
        selected_model = metadata["selected_models"][metric]
        unit = provenance["units"][metric]
        selected_test = scores.filter(
            (pl.col("metric_type") == metric)
            & (pl.col("model") == selected_model)
            & (pl.col("phase") == "test")
        ).row(0, named=True)
        st.caption(t(f"Reserved test for selected model: {selected_model}. Unit: {unit}."))
        with st.container(horizontal=True):
            for label, field in (("Test MAE", "mae"), ("Test RMSE", "rmse")):
                value = selected_test[field]
                st.metric(
                    t(label), f"{value:,.2f}" if value is not None else "Unavailable", border=True
                )
            wape = selected_test["wape"]
            st.metric(
                t("Test WAPE"), f"{wape:.2%}" if wape is not None else "Unavailable", border=True
            )
        phase = st.selectbox(
            t("Evaluation window"), ["test", "validation"], key="historical_phase", format_func=lambda value: str(t(value))
        )
        model_names = [selected_model] + [
            name for name in sorted(scores["model"].unique()) if name != selected_model
        ]
        model = st.selectbox(
            t("Comparison model"), model_names, key="historical_model", format_func=lambda value: str(t(value))
        )
        chart_rows = predictions.filter(
            (pl.col("metric_type") == metric)
            & (pl.col("model") == model)
            & (pl.col("phase") == phase)
        ).sort("year")
        st.subheader(t("Supplied values and predictions"))
        st.caption(
            t(
                f"{phase.title()} · {model} · {unit}. Validation uses expanding training prefixes; "
                "test predictions share a fixed training origin. Lines connect supplied target years."
            )
        )
        if chart_rows.is_empty():
            st.info(t("This model has no predictions in the selected window."))
        else:
            st.line_chart(
                chart_rows.select("year", "actual", "prediction"),
                x="year",
                y=["actual", "prediction"],
                x_label="Target year",
                y_label=unit,
            )
            st.subheader(t("Absolute prediction errors"))
            st.bar_chart(
                chart_rows.select("year", "absolute_error"),
                x="year",
                y="absolute_error",
                x_label="Target year",
                y_label=unit,
            )
        show_table(scores.filter(pl.col("metric_type") == metric), hide_index=True)
        with st.expander(t("Predictions by origin and target year")):
            show_table(predictions, hide_index=True)
        if forecast is not None:
            st.subheader(t("Forecast after supplied history"))
            future = forecast.filter(pl.col("metric_type") == metric).sort("year")
            history = observations.filter(pl.col("metric_type") == metric).sort("year")
            st.caption(
                t(
                    f"Model: {selected_model}. Refit on all supplied points after test scoring. "
                    f"Forecast years: {future['year'].min()}–{future['year'].max()}. Unit: {unit}."
                )
            )
            st.warning(
                t(
                    "Point estimates only, without prediction intervals or a future accuracy guarantee. "
                    "Synthetic input produces a synthetic demonstration forecast."
                )
            )
            timeline = pl.concat(
                [
                    history.select(
                        "year",
                        pl.col("total_value").cast(pl.Float64).alias("supplied"),
                        pl.lit(None, dtype=pl.Float64).alias("forecast"),
                    ),
                    future.select(
                        "year",
                        pl.lit(None, dtype=pl.Float64).alias("supplied"),
                        pl.col("forecast_value").alias("forecast"),
                    ),
                ]
            )
            st.line_chart(
                timeline,
                x="year",
                y=["supplied", "forecast"],
                x_label="Year",
                y_label=unit,
            )
            show_table(future, hide_index=True)
        st.download_button(
            t("Download historical evaluation"),
            result,
            "historical_evaluation.zip",
            mime="application/zip",
            key="historical_download",
        )
    st.stop()


if view == "Scenario planner":
    st.subheader(t("Transport scenario planner"))
    st.info(
        t(
            "Edit supply, demand, link costs and capacities, then submit a simulation. Results stay in this session and do not replace any saved plan."
        )
    )
    st.caption(
        t(
            "The starting example is synthetic. Positive node balances supply freight, negative balances demand it, and zero allows transit. Costs are per flow unit."
        )
    )
    example = json.loads(
        (Path(__file__).resolve().parents[1] / "docs/examples/transport_scenario.json").read_text(
            encoding="utf-8"
        )
    )
    reference = st.session_state.get("planner_reference")
    if reference is not None:
        st.caption(
            t(
                f"Reference retained: {reference['summary']['scenario']} — cost {reference['summary']['total_cost']:,.2f} {reference['summary']['cost_unit']}."
            )
        )
        if st.button(t("Clear comparison reference"), key="planner_clear_reference"):
            st.session_state.pop("planner_reference", None)
    with st.expander(t("Import a scenario JSON")):
        uploaded = st.file_uploader(
            t("Scenario JSON file"), type=["json"], max_upload_size=1, key="planner_upload"
        )
        pasted = st.text_area(
            t("Or paste scenario JSON"), key="planner_import_json", height=160, max_chars=262144
        )
        if st.button(t("Load scenario"), key="planner_import"):
            try:
                payload = uploaded.getvalue() if uploaded is not None else pasted.encode("utf-8")
                imported = parse_scenario_json(payload)
                replace_planner_inputs(st.session_state, imported)
                st.success(
                    t("Scenario loaded. Check the tables and submit the simulation when ready.")
                )
            except (ValueError, TypeError, OverflowError, RecursionError) as error:
                st.error(t(f"Scenario not imported: {error}"))
        st.caption(
            t(
                "UTF-8 JSON, up to 256 KiB. A selected file takes precedence over pasted text. Loading does not run the solver."
            )
        )
    if st.button(t("Restore synthetic example"), key="planner_reset"):
        replace_planner_inputs(st.session_state, example)
    example = st.session_state.get("planner_seed", example)
    for field in ("name", "flow_unit", "cost_unit"):
        if f"planner_{field}" not in st.session_state:
            st.session_state[f"planner_{field}"] = example[field]
    revision = st.session_state.get("planner_revision", 0)
    node_key = "planner_nodes" if revision == 0 else f"planner_nodes_{revision}"
    arc_key = "planner_arcs" if revision == 0 else f"planner_arcs_{revision}"
    with st.form("scenario_planner", enter_to_submit=False):
        name = st.text_input(t("Scenario name"), key="planner_name", max_chars=140)
        flow_unit = st.text_input(t("Flow unit"), key="planner_flow_unit", max_chars=100)
        cost_unit = st.text_input(t("Cost unit"), key="planner_cost_unit", max_chars=100)
        st.subheader(t("Nodes: supply and demand"))
        edited_nodes = st.data_editor(
            pl.DataFrame(example["nodes"])
            .with_columns(pl.col("balance").cast(pl.Float64))
            .to_pandas(),
            num_rows="dynamic",
            hide_index=True,
            key=node_key,
            column_config={
                "id": st.column_config.TextColumn("Node ID", required=True),
                "balance": st.column_config.NumberColumn(
                    "Supply (+) / demand (-)", required=True, format="%.2f"
                ),
            },
        )
        st.subheader(t("Directed links"))
        edited_arcs = st.data_editor(
            pl.DataFrame(example["arcs"])
            .with_columns(pl.col("capacity", "unit_cost").cast(pl.Float64))
            .to_pandas(),
            num_rows="dynamic",
            hide_index=True,
            key=arc_key,
            column_config={
                "id": st.column_config.TextColumn("Link ID", required=True),
                "origin": st.column_config.TextColumn("Origin node", required=True),
                "destination": st.column_config.TextColumn("Destination node", required=True),
                "capacity": st.column_config.NumberColumn("Capacity", min_value=0.0, required=True),
                "unit_cost": st.column_config.NumberColumn(
                    "Cost per flow unit", min_value=0.0, required=True
                ),
            },
        )
        st.caption(
            t("Interactive limit: 100 nodes and 500 links. All supply and demand must balance.")
        )
        submitted = st.form_submit_button(
            t("Simulate scenario"), type="primary", key="planner_submit"
        )
    if submitted:
        st.session_state.pop("planner_solution", None)
        scenario = {
            "name": name,
            "flow_unit": flow_unit,
            "cost_unit": cost_unit,
            "nodes": edited_nodes.to_dict("records"),
            "arcs": edited_arcs.to_dict("records"),
        }
        try:
            with st.spinner(t("Solving the submitted scenario...")):
                st.session_state["planner_solution"] = simulate_scenario(scenario)
        except (ValueError, TypeError, OverflowError) as error:
            st.error(t(f"Scenario not solved: {error}"))
    result_area = st.container()
    solution = st.session_state.get("planner_solution")
    if solution is not None:
        with result_area:
            summary = solution["summary"]
            st.success(
                t(
                    "Submitted scenario solved. This result is separate from your saved transport plan."
                )
            )
            st.caption(t(f"Last successful submission: {summary['scenario']}"))
            with st.container(horizontal=True):
                st.metric(t("Simulated total cost"), f"{summary['total_cost']:,.2f}", border=True)
                st.metric(t("Simulated supply"), f"{summary['total_supply']:,.2f}", border=True)
                st.metric(t("Simulation status"), summary["status"].capitalize(), border=True)
            st.caption(t(f"Flow unit: {summary['flow_unit']}. Cost unit: {summary['cost_unit']}."))
            st.caption(t(summary["interpretation"]))
            st.download_button(
                t("Download scenario and solution"),
                solution["archive"],
                "transport_scenario.zip",
                "application/zip",
                key="planner_download",
            )
            with st.expander(t("Simulation allocation and balance checks")):
                show_table(solution["allocation"], hide_index=True)
                show_table(solution["node_balances"], hide_index=True)
            if st.button(t("Use this result as reference"), key="planner_use_reference"):
                st.session_state["planner_reference"] = snapshot_solution(solution)
                st.success(
                    t(
                        "Reference stored for this session. Edit or import an alternative and simulate it to compare."
                    )
                )
            reference = st.session_state.get("planner_reference")
            if reference is not None:
                st.subheader(t("Comparison with reference"))
                try:
                    comparison = compare_solutions(reference, solution)
                except ValueError as error:
                    st.warning(t(str(error)))
                else:
                    report = comparison["summary"]
                    st.caption(
                        t(
                            f"Reference: {report['reference_name']}. Candidate: {report['candidate_name']}."
                        )
                    )
                    with st.container(horizontal=True):
                        st.metric(
                            t("Reference cost"), f"{report['reference_cost']:,.2f}", border=True
                        )
                        st.metric(
                            t("Candidate cost"), f"{report['candidate_cost']:,.2f}", border=True
                        )
                        percentage = report["relative_cost_change"]
                        st.metric(
                            t("Cost change vs reference"),
                            f"{report['cost_change']:+,.2f}",
                            delta=f"{percentage:+.2%}" if percentage is not None else None,
                            delta_color="inverse",
                            border=True,
                        )
                    st.caption(t(report["interpretation"]))
                    show_table(comparison["flow_changes"], hide_index=True)
                    st.download_button(
                        t("Download comparison bundle"),
                        comparison["archive"],
                        "transport_comparison.zip",
                        "application/zip",
                        key="planner_comparison_download",
                    )
    st.stop()


@st.cache_data(ttl=30, max_entries=8)
def saved_projections(root, signature):
    return load_projection_bundle(Path(root))


@st.cache_data(ttl=30, max_entries=8)
def saved_transport(directory, signature):
    return load_transport_results(Path(directory))


@st.cache_data(ttl=30, max_entries=8)
def saved_temporal(directory, source, signature):
    return load_temporal_report(Path(directory), Path(source))


if view == "Temporal evaluation":
    st.subheader(t("Temporal model evaluation"))
    st.info(t(INTERPRETATION))
    directory = ROOT / "artifacts/evaluation/annual"
    try:
        signature = file_signature(
            [
                BASE / "annual_kpis.parquet",
                *[
                    directory / name
                    for name in ("metadata.json", "scores.parquet", "predictions.parquet")
                ],
            ]
        )
        metadata, scores, predictions = saved_temporal(
            str(directory), str(BASE / "annual_kpis.parquet"), signature
        )
    except (OSError, ValueError, TypeError, pl.exceptions.PolarsError):
        st.warning(
            t(
                "A current, complete temporal evaluation is not available yet. Generate the evaluation report before viewing this workspace."
            )
        )
        st.stop()
    metric = st.selectbox(
        t("Metric"), sorted(metadata["selected_models"]), key="temporal_metric", format_func=lambda value: str(t(value))
    )
    phase = st.selectbox(
        t("Evaluation phase"),
        ["validation", "test"],
        index=1,
        format_func=lambda value: (
            "Rolling validation" if value == "validation" else "Reserved final test"
        ),
        key="temporal_phase",
    )
    filtered = scores.filter((pl.col("metric_type") == metric) & (pl.col("phase") == phase)).sort(
        "model"
    )
    selected_model = metadata["selected_models"][metric]
    selected_score = filtered.filter(pl.col("model") == selected_model)
    with st.container(horizontal=True):
        st.metric(t("Validation-selected baseline"), selected_model.upper(), border=True)
        wape = selected_score["wape"].item() if selected_score.height == 1 else None
        st.metric(
            t("Selected baseline WAPE"), f"{wape:.2%}" if wape is not None else "N/A", border=True
        )
        st.metric(t("Reserved test points"), str(metadata["test_points"]), border=True)
    st.caption(
        t(
            "The baseline is chosen using validation only. Final-test errors never change that choice. Validation and test may use different calendar horizons."
        )
    )
    st.subheader(t("Baseline comparison"))
    show_table(
        filtered.select(
            "model",
            "mae",
            "rmse",
            "wape",
            "eligible",
            "folds_expected",
            "folds_available",
            "selected",
        ),
        hide_index=True,
        column_config={"wape": st.column_config.NumberColumn("WAPE", format="percent")},
    )
    chart_scores = filtered.filter(pl.col("eligible")).drop_nulls("mae")
    if not chart_scores.is_empty():
        st.bar_chart(
            chart_scores,
            x="model",
            y="mae",
            x_label="Baseline",
            y_label="Mean absolute error (source units)",
        )
    available = filtered["model"].to_list()
    baseline = st.selectbox(
        t("Prediction baseline"),
        available,
        index=available.index(selected_model) if selected_model in available else 0,
        key="temporal_baseline",
        format_func=lambda value: str(t(value)),
    )
    rows = predictions.filter(
        (pl.col("metric_type") == metric)
        & (pl.col("phase") == phase)
        & (pl.col("model") == baseline)
    ).sort(["origin_year", "year"])
    st.subheader(t("Origin and target predictions"))
    if rows.is_empty():
        st.info(t("This baseline was unavailable for the selected phase."))
    show_table(
        rows.select(
            "origin_year", "year", "horizon_years", "actual", "prediction", "absolute_error"
        ),
        hide_index=True,
    )
    st.download_button(
        t("Download displayed predictions"),
        rows.write_csv(),
        "temporal_predictions.csv",
        "text/csv",
    )
    st.caption(
        t(
            "These are saved report values. Opening this page does not run training or evaluation and does not replace current extrapolations."
        )
    )
    st.stop()


if view == "Scenario extrapolations":
    st.subheader(t("Annual scenario extrapolations"))
    st.info(t(INTERPRETATION))
    directory = ROOT / "models/faf5/annual"
    try:
        signature = file_signature(
            [
                BASE / "annual_kpis.parquet",
                directory / "forecast.parquet",
                directory / "evaluation.parquet",
                directory / "metadata.json",
            ]
        )
        source, projections, evaluation = saved_projections(str(ROOT), signature)
    except (OSError, ValueError, pl.exceptions.PolarsError):
        st.warning(
            t(
                "Saved scenario results are unavailable or do not match the current indicators. Generate and validate the scenario results before viewing them."
            )
        )
        st.stop()
    labels = {"tons": "Freight volume", "value": "Freight value", "tmiles": "Ton-miles"}
    selected = st.selectbox(
        t("Metric"),
        sorted(projections["metric_type"].unique()),
        format_func=lambda value: labels.get(value, value),
        key="projection_metric",
    )
    series = projections.filter(pl.col("metric_type") == selected).sort("year")
    source_series = source.filter(pl.col("metric_type") == selected).sort("year")
    scores = evaluation.filter(pl.col("metric_type") == selected).sort("mae")
    with st.container(horizontal=True):
        st.metric(t("Extension through"), str(series["year"].max()), border=True)
        st.metric(t("Selected baseline"), series["model"][0].upper(), border=True)
        st.metric(t("Final extension value"), f"{series['forecast_value'][-1]:,.0f}", border=True)
    st.caption(
        t(
            "Values retain the source FAF units. Published FAF values already include projected years."
        )
    )
    chart = (
        source_series.select(
            pl.col("year").alias("Year"), pl.col("total_value").alias("Published FAF scenario")
        )
        .join(
            series.select(
                pl.col("year").alias("Year"), pl.col("forecast_value").alias("Saved extension")
            ),
            on="Year",
            how="full",
            coalesce=True,
        )
        .with_columns(
            pl.when(pl.col("Year") == source_series["year"].max())
            .then(pl.col("Published FAF scenario"))
            .otherwise(pl.col("Saved extension"))
            .alias("Saved extension")
        )
        .sort("Year")
    )
    st.line_chart(chart, x="Year", y=["Published FAF scenario", "Saved extension"])
    st.subheader(t("Saved extension values"))
    displayed = series.select("year", "forecast_value", "model").rename(
        {"year": "Year", "forecast_value": "Value", "model": "Baseline"}
    )
    show_table(displayed, hide_index=True)
    st.download_button(
        t("Download extension values"), displayed.write_csv(), "scenario_extension.csv", "text/csv"
    )
    st.subheader(t("Baseline comparison"))
    st.caption(
        t(
            "Errors use held-out FAF scenario points. They are model-selection scores, not independent tests against future observed demand."
        )
    )
    show_table(
        scores.select("model", "mae", "rmse", "wape", "selected"),
        hide_index=True,
        column_config={"wape": st.column_config.NumberColumn("WAPE", format="percent")},
    )
    st.stop()

if view == "Transport plan":
    st.subheader(t("Saved transport plan"))
    directory = ROOT / "artifacts/optimization/transport"
    try:
        signature = file_signature(
            [
                directory / name
                for name in ("summary.json", "allocation.parquet", "node_balances.parquet")
            ]
        )
        summary, arcs, nodes = saved_transport(str(directory), signature)
    except (OSError, ValueError, pl.exceptions.PolarsError):
        st.warning(
            t(
                "A complete, validated transport scenario is not available yet. Prepare the scenario results before viewing the plan."
            )
        )
        st.stop()
    st.info(t(summary["interpretation"]))
    st.caption(t(f"Scenario: {summary['scenario']}"))
    with st.container(horizontal=True):
        st.metric(t("Total scenario cost"), f"{summary['total_cost']:,.2f}", border=True)
        st.metric(t("Total supply"), f"{summary['total_supply']:,.2f}", border=True)
        st.metric(t("Solution status"), summary["status"].capitalize(), border=True)
    st.caption(t(f"Flow unit: {summary['flow_unit']}. Cost unit: {summary['cost_unit']}."))
    data = pl.DataFrame(arcs)
    origin = st.selectbox(
        t("Origin"),
        [None, *sorted(data["origin"].unique())],
        format_func=lambda value: t("All origins") if value is None else value,
        key="transport_origin",
    )
    destination = st.selectbox(
        t("Destination"),
        [None, *sorted(data["destination"].unique())],
        format_func=lambda value: t("All destinations") if value is None else value,
        key="transport_destination",
    )
    active_only = st.checkbox(t("Allocated links only"), value=True)
    if origin is not None:
        data = data.filter(pl.col("origin") == origin)
    if destination is not None:
        data = data.filter(pl.col("destination") == destination)
    if active_only:
        data = data.filter(pl.col("flow") > 1e-7)
    data = data.sort(["flow", "arc_id"], descending=[True, False])
    st.caption(
        t(f"{data.height} matching links. Scenario totals above apply to the complete plan.")
    )
    if data.is_empty():
        st.info(t("No links match these filters."))
    else:
        st.bar_chart(data.head(20), x="arc_id", y="flow", x_label="Link", y_label="Allocated flow")
    show_table(
        data.head(1000),
        hide_index=True,
        column_config={
            "utilization": st.column_config.NumberColumn("Capacity utilization", format="percent")
        },
    )
    st.caption(t("Table shows at most 1,000 matching links; the download includes every match."))
    st.download_button(
        t("Download matching links"), data.write_csv(), "transport_allocation.csv", "text/csv"
    )
    with st.expander(t("Node balance checks")):
        show_table(pl.DataFrame(nodes), hide_index=True)
    st.stop()


@st.cache_data(ttl=30, max_entries=4)
def load_data(signature):
    annual = pl.read_parquet(BASE / "annual_kpis.parquet")
    commodity = pl.read_parquet(BASE / "commodity_mix.parquet")
    mode = pl.read_parquet(BASE / "mode_mix.parquet")
    corridors = pl.read_parquet(BASE / "top_corridors.parquet")
    growth = pl.read_parquet(BASE / "annual_growth.parquet")
    cagr = pl.read_parquet(BASE / "annual_cagr.parquet")
    commodity_growth = pl.read_parquet(BASE / "commodity_growth.parquet")
    share_change = pl.read_parquet(BASE / "commodity_share_change.parquet")

    return (
        annual,
        commodity,
        mode,
        corridors,
        growth,
        cagr,
        commodity_growth,
        share_change,
    )


try:
    signature = file_signature(
        [
            BASE / name
            for name in (
                "annual_kpis.parquet",
                "commodity_mix.parquet",
                "mode_mix.parquet",
                "top_corridors.parquet",
                "annual_growth.parquet",
                "annual_cagr.parquet",
                "commodity_growth.parquet",
                "commodity_share_change.parquet",
            )
        ]
    )
    (annual, commodity, mode, corridors, growth, cagr, commodity_growth, share_change) = load_data(
        signature
    )
except (OSError, ValueError, pl.exceptions.PolarsError):
    st.warning(
        t(
            "Freight analytics are unavailable. Prepare and validate the Gold indicators before viewing this workspace."
        )
    )
    st.stop()

METRICS = {
    "Tons": "tons",
    "Freight value": "value",
    "Ton-miles": "tmiles",
}

metric_label = st.selectbox(t("Primary metric"), list(METRICS), format_func=lambda value: str(t(value)))
metric_type = METRICS[metric_label]
st.caption(t("FAF units: thousands of source tons; millions of 2017 USD; millions of ton-miles. Future years are scenarios, not observations."))

# KPIs
selected_annual = annual.filter(pl.col("metric_type") == metric_type)
latest_year = selected_annual["year"].max()
latest = selected_annual.filter(pl.col("year") == latest_year)

latest_total = latest["total_value"].item()
latest_growth = growth.filter(
    (pl.col("metric_type") == metric_type) & (pl.col("year") == latest_year)
)

growth_rate = (
    latest_growth["growth_rate"].item() * 100
    if latest_growth.height and latest_growth["growth_rate"].item() is not None
    else None
)

kpi1, kpi2, kpi3 = st.columns(3)
kpi1.metric(t("Forecast year"), latest_year)
kpi2.metric(t(metric_label), f"{latest_total:,.0f}")
kpi3.metric(
    t("Change since prior point"),
    f"{growth_rate:+.2f}%" if growth_rate is not None else "N/A",
)

st.divider()

# Annual evolution
st.subheader(t("Annual Freight Evolution"))

annual_chart = (
    selected_annual.select(["year", "total_value"]).sort("year").to_pandas().set_index("year")
)
st.line_chart(annual_chart)

# Annual growth
st.subheader(t("Change between available years"))

selected_growth = growth.filter(pl.col("metric_type") == metric_type).sort("year")

growth_chart = (
    selected_growth.select(["year", "absolute_change"]).drop_nulls().to_pandas().set_index("year")
)
st.caption(
    t("Absolute change since the previous available year; intervals may span multiple years.")
)
st.bar_chart(growth_chart)

growth_table = (
    selected_growth.select(
        [
            "year",
            "total_value",
            "previous_total_value",
            "absolute_change",
            "growth_rate",
        ]
    )
    .with_columns((pl.col("growth_rate") * 100).alias("growth_rate_pct"))
    .drop("growth_rate")
    .rename({"growth_rate_pct": "growth_rate_percent"})
)
show_table(growth_table.to_pandas(), width="stretch")

# CAGR
st.subheader(t("Compound Annual Growth Rate (CAGR)"))

cagr_table = cagr.with_columns((pl.col("cagr") * 100).alias("cagr_percent")).select(
    [
        "metric_type",
        "start_year",
        "end_year",
        "start_value",
        "end_value",
        "cagr_percent",
    ]
)
show_table(cagr_table.to_pandas(), width="stretch")

# Commodity growth
st.subheader(t("Commodity Growth"))

top_n = st.slider(t("Number of commodities"), min_value=5, max_value=20, value=10)
top_commodities = commodity_growth.sort("cagr", descending=True).head(top_n)

commodity_chart = (
    top_commodities.select(["commodity_name", "cagr"])
    .with_columns((pl.col("cagr") * 100).alias("cagr_percent"))
    .select(["commodity_name", "cagr_percent"])
    .to_pandas()
    .set_index("commodity_name")
)
st.bar_chart(commodity_chart)

commodity_table = top_commodities.with_columns((pl.col("cagr") * 100).alias("cagr_percent"))
show_table(commodity_table.to_pandas(), width="stretch")

# Commodity share changes
st.subheader(t("Change in Commodity Share"))

share_direction = st.radio(
    t("Show"),
    ["All", "Share gained", "Share lost"],
    horizontal=True,
    format_func=lambda value: str(t(value)),
)

filtered_shares = share_change
if share_direction == "Share gained":
    filtered_shares = filtered_shares.filter(pl.col("share_change") > 0)
elif share_direction == "Share lost":
    filtered_shares = filtered_shares.filter(pl.col("share_change") < 0)

share_table = filtered_shares.sort("share_change", descending=True).with_columns(
    (pl.col("start_share") * 100).alias("start_share_percent"),
    (pl.col("end_share") * 100).alias("end_share_percent"),
    (pl.col("share_change") * 100).alias("share_change_pp"),
)
show_table(share_table.to_pandas(), width="stretch")

# Freight modes
st.subheader(t("Freight Mode Mix"))
mode_latest = mode.filter(pl.col("year") == latest_year)
if "dms_mode" in mode_latest.columns:
    names = {1: "Truck", 2: "Rail", 3: "Water", 4: "Air (include truck-air)",
             5: "Multiple modes & mail", 6: "Pipeline", 7: "Other and unknown", 8: "No domestic mode"}
    mode_latest = mode_latest.with_columns(
        pl.col("dms_mode").replace_strict({key: t(value) for key, value in names.items()},
                                         default=t("Other and unknown")).alias(t("Domestic mode")))
show_table(mode_latest.to_pandas(), width="stretch")

# Top corridors
st.subheader(t("Top Freight Corridors"))
top = corridors.filter(pl.col("year") == latest_year).sort("tons", descending=True).head(20)
show_table(top.to_pandas(), width="stretch")

# Commodity mix
st.subheader(t("Commodity Mix"))

commodity_years = sorted(commodity["year"].unique().to_list())
selected_year = st.selectbox(
    t("Commodity mix year"),
    commodity_years,
    index=len(commodity_years) - 1,
    format_func=lambda value: str(t(value)),
)

commodity_latest = commodity.filter(pl.col("year") == selected_year)
show_table(commodity_latest.to_pandas(), width="stretch")

st.caption(
    t("Source: Freight Analysis Framework (FAF5), U.S. Bureau of Transportation Statistics / ORNL.")
)
