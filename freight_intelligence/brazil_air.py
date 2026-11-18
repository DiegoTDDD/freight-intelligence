"""Hash-checked ANAC stage aggregates and observed-subtotal forecast reports."""

import hashlib
import io
import json
from pathlib import Path
from zipfile import ZipFile

import polars as pl

DEFAULT_ROOT = Path(__file__).resolve().parents[1] / "deployment/brazil_air"
CARGO_FIELDS = ("paid_cargo_kg", "free_cargo_kg", "mail_kg")
COUNTS = ("source_rows", *[f"missing_{name}" for name in CARGO_FIELDS])


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
    with ZipFile(io.BytesIO(raw_files["forecast.zip"])) as archive:
        report = {"metadata": json.loads(archive.read("metadata.json")),
                  "scores": pl.read_csv(archive.read("scores.csv")),
                  "forecast": pl.read_csv(archive.read("forecast.csv")),
                  "predictions": pl.read_csv(archive.read("predictions.csv"))}
        if hashlib.sha256(archive.read("observations.csv")).hexdigest() != report["metadata"]["input_sha256"]:
            raise ValueError("ANAC forecast input integrity mismatch")
        observations = pl.read_csv(archive.read("observations.csv")).sort("metric_type", "year")
        expected_history = annual.filter(pl.col("year") >= 2010).select(
            pl.concat_str("nature", pl.lit("_paid_observed_subtotal")).alias("metric_type"),
            "year", pl.col("paid_cargo_kg").alias("total_value")).sort("metric_type", "year")
        if not observations.equals(expected_history):
            raise ValueError("ANAC forecast no longer matches annual observed subtotals")
    return tables, metadata, report
