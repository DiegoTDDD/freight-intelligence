"""Run locally with uvicorn freight_intelligence.api.app:app --host 127.0.0.1."""

from enum import Enum
from pathlib import Path
from typing import Literal

import polars as pl
from fastapi import APIRouter, FastAPI, HTTPException, Query

from freight_intelligence.api.security import authentication_dependencies
from freight_intelligence.api.transport_results import load_transport_results
from freight_intelligence.brazil_gas_results import DEFAULT_ROOT as BRAZIL_GAS
from freight_intelligence.brazil_gas_results import load_gas
from freight_intelligence.brazil_modes import DEFAULT_ROOT as BRAZIL_MODES
from freight_intelligence.brazil_modes import load_modes
from freight_intelligence.brazil_road import DEFAULT_ROOT as BRAZIL_ROAD
from freight_intelligence.brazil_road import STATES, load_road
from freight_intelligence.brazil_water import DEFAULT_ROOT as BRAZIL_WATER
from freight_intelligence.brazil_water import load_water
from freight_intelligence.dashboard_data import load_projection_files
from freight_intelligence.evaluation_results import load_temporal_report
from freight_intelligence.ml.annual_forecast import INTERPRETATION, PROJECT_ROOT


class Metric(str, Enum):
    tons = "tons"
    value = "value"
    tmiles = "tmiles"


def read_table(path: Path, columns: set[str]) -> pl.DataFrame:
    try:
        data = pl.read_parquet(path)
        if not columns.issubset(data.columns):
            raise ValueError("Required columns are missing")
        if data.is_empty():
            raise ValueError("Dataset is empty")
        if any(data.select(sorted(columns)).null_count().row(0)):
            raise ValueError("Dataset contains null values")
        if data["metric_type"].dtype != pl.String or not data["year"].dtype.is_integer():
            raise ValueError("Invalid metric/year types")
        if not set(data["metric_type"]).issubset({metric.value for metric in Metric}):
            raise ValueError("Invalid metric")
        value_column = "forecast_value" if "forecast_value" in columns else "total_value"
        values = data[value_column]
        if not values.dtype.is_numeric() or not values.is_finite().all() or (values < 0).any():
            raise ValueError("Values must be finite and nonnegative")
        if "result_type" in columns and set(data["result_type"]) != {"faf_scenario_extrapolation"}:
            raise ValueError("Invalid forecast interpretation")
        return data
    except (OSError, ValueError, pl.exceptions.PolarsError) as error:
        raise HTTPException(
            status_code=503,
            detail="Analytical dataset unavailable; generate and validate it before serving.",
        ) from error


def create_app(
    gold_dir: Path | None = None,
    model_dir: Path | None = None,
    transport_dir: Path | None = None,
    evaluation_dir: Path | None = None,
    brazil_dir: Path | None = None,
    gas_dir: Path | None = None,
    water_dir: Path | None = None,
    road_dir: Path | None = None,
) -> FastAPI:
    gold = Path(gold_dir) if gold_dir is not None else PROJECT_ROOT / "data/gold/faf5"
    models = Path(model_dir) if model_dir is not None else PROJECT_ROOT / "models/faf5/annual"
    transport = (
        Path(transport_dir)
        if transport_dir is not None
        else PROJECT_ROOT / "artifacts/optimization/transport"
    )
    app = FastAPI(
        title="LogiNexus Freight Intelligence API",
        version="0.1.0",
        description=(
            "Read-only access to FAF annual indicators and scenario extrapolations. "
            "Source units: thousands of tons, millions of 2017 USD, and millions of ton-miles. "
            "Future FAF years are scenarios, not observed outcomes. "
            "Optional datasets return 503 when unavailable; requests never run the pipeline."
        ),
    )
    data_routes = APIRouter(dependencies=authentication_dependencies())
    temporal_directory = (
        Path(evaluation_dir)
        if evaluation_dir is not None
        else PROJECT_ROOT / "artifacts/evaluation/annual"
    )

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @data_routes.get("/ready")
    def ready():
        read_table(gold / "annual_kpis.parquet", {"metric_type", "year", "total_value"})
        return {"status": "ready", "annual_kpis": "available"}

    @data_routes.get("/annual-kpis")
    def annual_kpis(
        metric_type: Metric | None = None,
        start_year: int | None = Query(default=None, ge=1900, le=2100),
        end_year: int | None = Query(default=None, ge=1900, le=2100),
    ):
        if start_year is not None and end_year is not None and start_year > end_year:
            raise HTTPException(status_code=422, detail="start_year must not exceed end_year")
        data = read_table(gold / "annual_kpis.parquet", {"metric_type", "year", "total_value"})
        if metric_type is not None:
            data = data.filter(pl.col("metric_type") == metric_type.value)
        if start_year is not None:
            data = data.filter(pl.col("year") >= start_year)
        if end_year is not None:
            data = data.filter(pl.col("year") <= end_year)
        return {
            "source": "FAF5 annual Gold indicators; includes projected scenario years",
            "count": data.height,
            "data": data.sort(["metric_type", "year"]).to_dicts(),
        }

    @data_routes.get("/brazil/indicators")
    def brazil_indicators(
        mode: Literal["road", "rail", "water", "air", "pipeline"] | None = None,
        start_year: int = Query(default=2000, ge=2000, le=2025),
        end_year: int = Query(default=2025, ge=2000, le=2025),
    ):
        if start_year > end_year:
            raise HTTPException(status_code=422, detail="start_year must not exceed end_year")
        try:
            data, metadata = load_modes(brazil_dir if brazil_dir is not None else BRAZIL_MODES)
        except (OSError, ValueError, KeyError, TypeError, pl.exceptions.PolarsError) as error:
            raise HTTPException(status_code=503, detail="Brazilian modal indicators unavailable") \
                from error
        data = data.filter(pl.col("year").is_between(start_year, end_year))
        if mode is not None:
            data = data.filter(pl.col("mode") == mode)
        return {"count": data.height, "data": data.to_dicts(),
                "interpretation": metadata["interpretation"],
                "quality_notes": metadata["quality_notes"], "sources": metadata["sources"],
                "excluded_series": metadata.get("excluded_series", [])}

    @data_routes.get("/brazil/road-flows")
    def brazil_road_flows(
        origin_state: str | None = Query(default=None, pattern=f"^({STATES})$"),
        destination_state: str | None = Query(default=None, pattern=f"^({STATES})$"),
        same_region: bool | None = None,
    ):
        try:
            data, metadata = load_road(road_dir if road_dir is not None else BRAZIL_ROAD)
        except (OSError, ValueError, KeyError, TypeError, pl.exceptions.PolarsError) as error:
            raise HTTPException(status_code=503, detail="Verified regional road flows unavailable.") from error
        if origin_state is not None:
            data = data.filter(pl.col("origin_state") == origin_state)
        if destination_state is not None:
            data = data.filter(pl.col("destination_state") == destination_state)
        if same_region is not None:
            same = ((pl.col("origin_state") == pl.col("destination_state"))
                    & (pl.col("origin_region") == pl.col("destination_region")))
            data = data.filter(same if same_region else ~same)
        return {"count": data.height, "data": data.to_dicts(), "metadata": metadata}

    @data_routes.get("/brazil/water-freight")
    def brazil_water_freight(
        dataset: Literal["navigation_totals", "inland_commodities",
                         "coastal_state_endpoints", "grain_regions"] | None = None,
        year: int | None = Query(default=None, ge=2024, le=2025),
        direction: Literal["origin", "destination", "movements", "exports",
                           "not_applicable"] | None = None,
    ):
        try:
            data, metadata = load_water(water_dir if water_dir is not None else BRAZIL_WATER)
        except (OSError, ValueError, KeyError, TypeError, pl.exceptions.PolarsError) as error:
            raise HTTPException(status_code=503, detail="Verified ANTAQ references unavailable") \
                from error
        if dataset is not None:
            data = data.filter(pl.col("dataset") == dataset)
        if year is not None:
            data = data.filter(pl.col("year") == year)
        if direction is not None:
            data = data.filter(pl.col("direction") == direction)
        return {"count": data.height, "data": data.to_dicts(),
                "method": metadata["method"], "quality_notes": metadata["quality_notes"],
                "sources": metadata["sources"]}

    @data_routes.get("/brazil/gas-movements")
    def brazil_gas_movements(
        month: int | None = Query(default=None, ge=1, le=12),
        point_type: Literal["receipt", "delivery"] | None = None,
        operator_id: str | None = Query(default=None, pattern=r"^\d{1,20}$"),
    ):
        try:
            data, annual, metadata = load_gas(gas_dir if gas_dir is not None else BRAZIL_GAS)
        except (OSError, ValueError, KeyError, TypeError, pl.exceptions.PolarsError) as error:
            raise HTTPException(status_code=503, detail="Verified ANP gas movements unavailable") \
                from error
        if month is not None:
            data = data.filter(pl.col("month") == month)
        if point_type is not None:
            data = data.filter(pl.col("point_type") == point_type)
        if operator_id is not None:
            data = data.filter(pl.col("operator_id") == operator_id)
        return {"count": data.height, "data": data.to_dicts(),
                "interpretation": metadata["interpretation"],
                "annual_full_dataset_reference": annual, "sources": metadata["sources"],
                "unit": "thousand_m3", "year": 2025}

    @data_routes.get("/annual-forecast")
    def annual_forecast(metric_type: Metric | None = None):
        try:
            _, data, _ = load_projection_files(models, gold / "annual_kpis.parquet")
        except (OSError, ValueError, TypeError, pl.exceptions.PolarsError) as error:
            raise HTTPException(
                status_code=503,
                detail="Forecast bundle unavailable or inconsistent with current annual indicators.",
            ) from error
        if metric_type is not None:
            data = data.filter(pl.col("metric_type") == metric_type.value)
        return {
            "interpretation": INTERPRETATION,
            "count": data.height,
            "data": data.sort(["metric_type", "year"]).to_dicts(),
        }

    def transport_bundle():
        try:
            return load_transport_results(transport)
        except ValueError as error:
            raise HTTPException(
                status_code=503,
                detail="Transport results unavailable; generate and validate a scenario first.",
            ) from error

    @data_routes.get("/transport-plan")
    def transport_plan(
        origin: str | None = Query(default=None, min_length=1, max_length=200),
        destination: str | None = Query(default=None, min_length=1, max_length=200),
        active_only: bool = False,
        limit: int = Query(default=100, ge=1, le=1000),
        offset: int = Query(default=0, ge=0),
    ):
        summary, arcs, _ = transport_bundle()
        rows = sorted(
            [
                row
                for row in arcs
                if (origin is None or row["origin"] == origin)
                and (destination is None or row["destination"] == destination)
                and (not active_only or row["flow"] > 1e-7)
            ],
            key=lambda row: row["arc_id"],
        )
        page = rows[offset : offset + limit]
        return {
            "summary": summary,
            "total": len(rows),
            "count": len(page),
            "limit": limit,
            "offset": offset,
            "data": page,
        }

    @data_routes.get("/transport-plan/nodes")
    def transport_nodes(
        limit: int = Query(default=100, ge=1, le=1000),
        offset: int = Query(default=0, ge=0),
    ):
        summary, _, nodes = transport_bundle()
        page = sorted(nodes, key=lambda row: row["node_id"])[offset : offset + limit]
        return {
            "summary": summary,
            "total": len(nodes),
            "count": len(page),
            "limit": limit,
            "offset": offset,
            "data": page,
        }

    def temporal_bundle():
        try:
            return load_temporal_report(temporal_directory, gold / "annual_kpis.parquet")
        except (OSError, ValueError, TypeError, pl.exceptions.PolarsError) as error:
            raise HTTPException(
                status_code=503,
                detail="Temporal evaluation unavailable; generate a current validated report first.",
            ) from error

    @data_routes.get("/temporal-evaluation")
    def temporal_scores(
        metric_type: Metric | None = None, phase: Literal["validation", "test"] | None = None
    ):
        metadata, scores, _ = temporal_bundle()
        if metric_type is not None:
            scores = scores.filter(pl.col("metric_type") == metric_type.value)
        if phase is not None:
            scores = scores.filter(pl.col("phase") == phase)
        return {
            "metadata": metadata,
            "count": scores.height,
            "data": scores.sort(["metric_type", "phase", "model"]).to_dicts(),
        }

    @data_routes.get("/temporal-evaluation/predictions")
    def temporal_predictions(
        metric_type: Metric | None = None,
        phase: Literal["validation", "test"] | None = None,
        selected_only: bool = False,
        limit: int = Query(default=100, ge=1, le=1000),
        offset: int = Query(default=0, ge=0),
    ):
        metadata, _, rows = temporal_bundle()
        if metric_type is not None:
            rows = rows.filter(pl.col("metric_type") == metric_type.value)
        if phase is not None:
            rows = rows.filter(pl.col("phase") == phase)
        if selected_only:
            rows = rows.filter(pl.col("selected"))
        page = rows.sort(["metric_type", "phase", "model", "origin_year", "year"]).slice(
            offset, limit
        )
        return {
            "metadata": metadata,
            "total": rows.height,
            "count": page.height,
            "limit": limit,
            "offset": offset,
            "data": page.to_dicts(),
        }

    app.include_router(data_routes)
    return app


app = create_app()
