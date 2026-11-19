"""Read hash-checked vintage forecasts without training or mixing modal units."""

import hashlib
import io
import json
from pathlib import Path
from zipfile import BadZipFile, ZipFile

import polars as pl

from freight_intelligence.brazil_modes import load_modes

DEFAULT_ROOT = Path(__file__).resolve().parents[1] / "deployment/brazil_modal_forecasts"
SERIES = {"port_throughput": ("water", "million_tonnes"),
          "transpetro_oil_pipeline_movement": ("pipeline", "million_m3_at_20C")}


def load_modal_forecasts(root=DEFAULT_ROOT, *, modes_root=None):
    root = Path(root)
    metadata = json.loads((root / "provenance.json").read_bytes())
    record, = metadata["files"]
    if (metadata.get("schema_version") != 1 or metadata.get("source_end_year") != 2024
            or metadata.get("test_years") != [2022, 2023, 2024]
            or metadata.get("forecast_years") != [2025, 2026, 2027]
            or record["path"] != "forecast.zip"):
        raise ValueError("Invalid modal forecast manifest")
    raw = (root / "forecast.zip").read_bytes()
    if len(raw) > 1024**2 or hashlib.sha256(raw).hexdigest() != record["sha256"]:
        raise ValueError("Modal forecast integrity mismatch")
    names = {"observations.csv", "source_manifest.json", "metadata.json", "scores.csv",
             "predictions.csv", "forecast.csv"}
    try:
        with ZipFile(io.BytesIO(raw)) as bundle:
            members = bundle.infolist()
            if len(members) != 6 or {m.filename for m in members} != names or any(m.file_size > 65536 for m in members):
                raise ValueError("Invalid modal forecast archive")
            files = {name: bundle.read(name) for name in names}
    except BadZipFile as error:
        raise ValueError("Invalid modal forecast archive") from error
    report = {"metadata": json.loads(files["metadata.json"]),
              **{name: pl.read_csv(files[name + ".csv"]) for name in ("observations", "scores", "predictions", "forecast")}}
    source_manifest = json.loads(files["source_manifest.json"])
    units = {name: contract[1] for name, contract in SERIES.items()}
    info = report["metadata"]
    if (info.get("input_sha256") != hashlib.sha256(files["observations.csv"]).hexdigest()
            or info.get("manifest_sha256") != hashlib.sha256(files["source_manifest.json"]).hexdigest()
            or info.get("selection_uses") != "validation_only" or info.get("min_train_points") != 8
            or info.get("test_points") != 3 or source_manifest.get("units") != units
            or source_manifest.get("record_kind") != "historical_observations"):
        raise ValueError("Invalid modal forecast source or split contract")
    data, _ = load_modes() if modes_root is None else load_modes(modes_root)
    expected = data.filter(pl.col("indicator").is_in(list(SERIES))).select(
        pl.col("indicator").alias("metric_type"), "year", pl.col("value").alias("total_value")
    ).sort("metric_type", "year")
    observations = report["observations"].sort("metric_type", "year")
    if observations.height != 30 or not observations.equals(expected):
        raise ValueError("Modal forecast differs from current reviewed histories")
    choices = info.get("selected_models", {})
    if set(choices) != set(SERIES) or not set(choices.values()).issubset({"persistence", "linear", "cagr"}):
        raise ValueError("Invalid modal forecast choices")
    scores = report["scores"]
    if scores.height != 12 or scores.select("metric_type", "phase", "model").is_duplicated().any():
        raise ValueError("Incomplete modal candidate scores")
    for metric in SERIES:
        for phase in ("validation", "test"):
            subset = scores.filter((pl.col("metric_type") == metric) & (pl.col("phase") == phase))
            if set(subset["model"]) != {"persistence", "linear", "cagr"}:
                raise ValueError("Missing modal candidate baseline")
            if phase == "validation":
                selected = subset.filter(pl.col("model") == choices[metric])
                if selected["mae"][0] != subset["mae"].min():
                    raise ValueError("Modal model choice is not validation-selected")
    for name in ("scores", "predictions"):
        frame = report[name]
        if frame.is_empty() or any(frame.null_count().row(0)) or set(frame["metric_type"]) != set(SERIES):
            raise ValueError("Incomplete modal forecast results")
        if set(frame["phase"]) != {"validation", "test"}:
            raise ValueError("Invalid modal forecast phases")
        for row in frame.to_dicts():
            if row["selected"] != (row["model"] == choices[row["metric_type"]]):
                raise ValueError("Invalid selected-model flags")
    test = report["predictions"].filter(pl.col("phase") == "test")
    validation = report["predictions"].filter(pl.col("phase") == "validation")
    if (set(test["year"]) != {2022, 2023, 2024} or set(test["origin_year"]) != {2021}
            or validation["year"].max() > 2021):
        raise ValueError("Modal reserved-test boundary mismatch")
    actual = {(r["metric_type"], r["year"]): r["total_value"] for r in observations.to_dicts()}
    if any(r["actual"] != actual.get((r["metric_type"], r["year"])) for r in report["predictions"].to_dicts()):
        raise ValueError("Modal test actuals differ from observations")
    forecast = report["forecast"]
    if forecast.height != 6 or any(forecast.null_count().row(0)):
        raise ValueError("Incomplete modal vintage forecasts")
    for metric in SERIES:
        subset = forecast.filter(pl.col("metric_type") == metric)
        if (set(subset["year"]) != {2025, 2026, 2027} or set(subset["source_end_year"]) != {2024}
                or set(subset["unit"]) != {units[metric]} or set(subset["model"]) != {choices[metric]}
                or set(subset["result_type"]) != {"supplied_historical_forecast"}):
            raise ValueError("Modal forecast period/unit mismatch")
    for frame, columns in ((report["scores"], ("mae", "rmse", "wape")),
                           (report["predictions"], ("actual", "prediction", "absolute_error", "squared_error")),
                           (forecast, ("forecast_value",))):
        for column in columns:
            values = frame[column]
            if not values.dtype.is_numeric() or not values.is_finite().all() or (values < 0).any():
                raise ValueError("Invalid modal forecast numeric results")
    return report, metadata
