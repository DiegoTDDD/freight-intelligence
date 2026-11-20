"""Hash-checked ANAC stage aggregates and observed-subtotal forecast reports."""

import hashlib
import io
import json
from pathlib import Path
from zipfile import BadZipFile, ZipFile

import polars as pl

DEFAULT_ROOT = Path(__file__).resolve().parents[1] / "deployment/brazil_air"
CARGO_FIELDS = ("paid_cargo_kg", "free_cargo_kg", "mail_kg")
FORECAST_MEASURES = {"paid_cargo_kg": "paid", "free_cargo_kg": "free", "mail_kg": "mail"}
COUNTS = ("source_rows", *[f"missing_{name}" for name in CARGO_FIELDS])


def forecast_history(annual, measures=CARGO_FIELDS):
    """Keep six observed kilogram subtotals separate, using the reviewed 2010 cutoff."""
    return pl.concat([
        annual.filter(pl.col("year") >= 2010).select(
            pl.concat_str("nature", pl.lit("_" + FORECAST_MEASURES[field] + "_observed_subtotal")).alias("metric_type"),
            "year", pl.col(field).alias("total_value"))
        for field in measures
    ]).sort("metric_type", "year")


def load_air(root=DEFAULT_ROOT):
    root = Path(root)
    metadata = json.loads((root / "provenance.json").read_bytes())
    names = {"monthly.parquet", "pairs.parquet", "annual.parquet", "airports.parquet",
             "forecast.zip"}
    files = metadata["files"]
    if metadata.get("schema_version") != 1 or len(files) != 5 or {r["path"] for r in files} != names:
        raise ValueError("Invalid ANAC snapshot manifest")
    raw_files = {}
    for record in files:
        raw = (root / record["path"]).read_bytes()
        if len(raw) > 8 * 1024**2 or hashlib.sha256(raw).hexdigest() != record["sha256"]:
            raise ValueError("ANAC snapshot integrity mismatch")
        raw_files[record["path"]] = raw
    tables = {name: pl.read_parquet(raw_files[f"{name}.parquet"])
              for name in ("monthly", "pairs", "annual", "airports")}
    for name in ("monthly", "annual", "pairs"):
        data = tables[name]
        if data.is_empty() or any(data.null_count().row(0)) or data.height > 100000:
            raise ValueError("Empty, incomplete or oversized ANAC aggregate")
        for field in (*CARGO_FIELDS, *COUNTS):
            if not data[field].dtype.is_integer() or (data[field] < 0).any():
                raise ValueError("Invalid ANAC kilograms or coverage counts")
        if not set(data["nature"]).issubset({"domestic", "international"}):
            raise ValueError("Invalid ANAC nature")
        if (not data["year"].dtype.is_integer()
                or not data["year"].is_between(2000, metadata["end_year"]).all()):
            raise ValueError("Invalid ANAC years")
        for field in CARGO_FIELDS:
            if (data[f"missing_{field}"] > data["source_rows"]).any():
                raise ValueError("Missing ANAC fields exceed contributing rows")
        keys = ["year", "nature"]
        if name != "annual":
            if not data["month"].dtype.is_integer() or not data["month"].is_between(1, 12).all():
                raise ValueError("Invalid ANAC month")
            keys.append("month")
        if name == "pairs":
            keys.extend(["origin", "destination"])
            if data["year"].min() < metadata["pair_start_year"]:
                raise ValueError("ANAC pair period differs from contract")
        if data.select(keys).is_duplicated().any():
            raise ValueError("Duplicate ANAC aggregate")
    monthly, annual = tables["monthly"], tables["annual"]
    expected = monthly.group_by("year", "nature").agg(
        *[pl.col(field).sum() for field in (*CARGO_FIELDS, *COUNTS)],
        pl.col("month").n_unique().alias("reported_months"),
    ).sort("year", "nature")
    if (not expected.equals(annual.sort("year", "nature"))
            or not annual["reported_months"].eq(12).all()):
        raise ValueError("ANAC annual and monthly aggregates disagree")
    airports = tables["airports"]
    if (airports.is_empty() or airports.height > 5000 or airports["airport"].n_unique() != airports.height
            or not set(tables["pairs"]["origin"]).union(tables["pairs"]["destination"]).issubset(airports["airport"])):
        raise ValueError("Invalid ANAC airport references")
    # Pair rows can omit source records with missing endpoints, but cannot exceed
    # their containing monthly kilograms or row counts.
    pairs = tables["pairs"].group_by("year", "month", "nature").agg(
        *[pl.col(field).sum().alias(field + "_pairs") for field in (*CARGO_FIELDS, "source_rows")])
    joined = pairs.join(monthly, on=["year", "month", "nature"], how="left")
    if any(joined.select(pl.col(field + "_pairs") > pl.col(field)).to_series().any()
           for field in (*CARGO_FIELDS, "source_rows")):
        raise ValueError("ANAC pair subtotals exceed monthly population")
    try:
        archive = ZipFile(io.BytesIO(raw_files["forecast.zip"]))
    except BadZipFile as error:
        raise ValueError("Invalid ANAC forecast archive") from error
    with archive:
        names = {"metadata.json", "observations.csv", "source_manifest.json", "scores.csv", "forecast.csv", "predictions.csv"}
        if (len(archive.infolist()) != 6 or set(archive.namelist()) != names
                or any(item.file_size > 128 * 1024 for item in archive.infolist())):
            raise ValueError("Invalid ANAC forecast archive members")
        report = {"metadata": json.loads(archive.read("metadata.json")),
                  "scores": pl.read_csv(archive.read("scores.csv")),
                  "forecast": pl.read_csv(archive.read("forecast.csv")),
                  "predictions": pl.read_csv(archive.read("predictions.csv"))}
        if hashlib.sha256(archive.read("observations.csv")).hexdigest() != report["metadata"]["input_sha256"]:
            raise ValueError("ANAC forecast input integrity mismatch")
        observations = pl.read_csv(archive.read("observations.csv")).sort("metric_type", "year")
        dataset = report["metadata"]["provenance"]["dataset_id"]
        if dataset == "anac_paid_stage_subtotals_2010_2025":
            measures = ("paid_cargo_kg",)  # Reviewed legacy report remains readable.
        elif dataset == "anac_cargo_and_mail_stage_subtotals_2010_2025":
            measures = CARGO_FIELDS
        else:
            raise ValueError("Unknown ANAC forecast population")
        expected_history = forecast_history(annual, measures)
        if not observations.equals(expected_history):
            raise ValueError("ANAC forecast no longer matches annual observed subtotals")
        info = report["metadata"]
        manifest_bytes = archive.read("source_manifest.json")
        manifest = json.loads(manifest_bytes)
        metrics = set(expected_history["metric_type"])
        if (info.get("manifest_sha256") != hashlib.sha256(manifest_bytes).hexdigest()
                or manifest != info["provenance"] or manifest.get("units") != {metric: "kg" for metric in metrics}
                or manifest.get("source") != metadata["source"]
                or manifest.get("record_kind") != "historical_observations"
                or info.get("selection_uses") != "validation_only" or info.get("min_train_points") != 8
                or info.get("test_points") != 3):
            raise ValueError("Invalid ANAC forecast source or split contract")
        choices = info.get("selected_models", {})
        models = {"persistence", "linear", "cagr"}
        if set(choices) != metrics or not set(choices.values()).issubset(models):
            raise ValueError("Invalid ANAC forecast model choices")
        scores = report["scores"]
        if scores.height != len(metrics) * 6 or scores.select("metric_type", "phase", "model").is_duplicated().any():
            raise ValueError("Incomplete ANAC forecast scores")
        for metric in metrics:
            for phase in ("validation", "test"):
                rows = scores.filter((pl.col("metric_type") == metric) & (pl.col("phase") == phase))
                if set(rows["model"]) != models:
                    raise ValueError("Missing ANAC forecast baseline")
                if phase == "validation":
                    winner = rows.filter(pl.col("model") == choices[metric])
                    eligible = rows.filter(pl.col("eligible"))
                    if not winner["eligible"].item() or winner["mae"].item() != eligible["mae"].min():
                        raise ValueError("ANAC model choice differs from validation selection")
        actuals = {(r["metric_type"], r["year"]): r["total_value"] for r in observations.to_dicts()}
        end_year = metadata["end_year"]
        for name in ("scores", "predictions"):
            frame = report[name]
            if set(frame["metric_type"]) != metrics or set(frame["phase"]) != {"validation", "test"}:
                raise ValueError("Incomplete ANAC forecast populations")
            for row in frame.to_dicts():
                if row["selected"] != (row["model"] == choices[row["metric_type"]]):
                    raise ValueError("Invalid ANAC selected-model flag")
                if name == "predictions":
                    if row["actual"] != actuals.get((row["metric_type"], row["year"])):
                        raise ValueError("ANAC forecast actuals differ from observations")
                    if (row["phase"] == "test" and (row["origin_year"] != end_year - 3
                            or row["year"] not in range(end_year - 2, end_year + 1))
                            or row["phase"] == "validation" and not row["origin_year"] < row["year"] <= end_year - 3):
                        raise ValueError("ANAC reserved-test boundary mismatch")
        forecast = report["forecast"]
        if forecast.height != len(metrics) * 3 or any(forecast.null_count().row(0)):
            raise ValueError("Incomplete ANAC forecasts")
        for metric in metrics:
            rows = forecast.filter(pl.col("metric_type") == metric)
            if (rows.height != 3 or set(rows["year"]) != set(range(end_year + 1, end_year + 4))
                    or set(rows["source_end_year"]) != {end_year} or set(rows["unit"]) != {"kg"}
                    or set(rows["model"]) != {choices[metric]}):
                raise ValueError("ANAC forecast target/unit mismatch")
        for name, fields in (("scores", ("mae", "rmse", "wape")),
                             ("predictions", ("actual", "prediction", "absolute_error", "squared_error")),
                             ("forecast", ("forecast_value",))):
            for field in fields:
                values = report[name][field].drop_nulls()
                if not values.dtype.is_numeric() or not values.is_finite().all() or (values < 0).any():
                    raise ValueError("Invalid ANAC forecast numeric results")
    return tables, metadata, report
