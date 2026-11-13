"""Integrity and schema validation for curated Brazilian modal indicators."""

import hashlib
import json
from pathlib import Path

import polars as pl

MODES = ("road", "rail", "water", "air", "pipeline")
DEFAULT_ROOT = Path(__file__).resolve().parents[1] / "deployment/brazil_modes"
CONTRACTS = {
    "mdfe_recorded_tonnes": ("road", "tonnes", 2025, 2025),
    "antaq_2025_port_throughput": ("water", "million_tonnes", 2025, 2025),
    "coastal_cabotage_volume": ("water", "million_tonnes", 2025, 2025),
    "inland_navigation_volume": ("water", "million_tonnes", 2025, 2025),
    "mdfe_recorded_trips": ("road", "million_trips", 2025, 2025),
    "mdfe_transport_work": ("road", "billion_tonne_km", 2025, 2025),
    "registered_trucks": ("road", "million_vehicles", 2010, 2024),
    "rail_net_tonnes": ("rail", "tonnes", 2006, 2025),
    "rail_transport_work": ("rail", "tonne_km", 2006, 2025),
    "port_throughput": ("water", "million_tonnes", 2010, 2024),
    "domestic_paid_cargo": ("air", "million_kg", 2010, 2024),
    "international_paid_cargo": ("air", "million_kg", 2010, 2024),
    "anp_gas_receipt_observed_subtotal": ("pipeline", "million_m3", 2025, 2025),
    "anp_gas_delivery_observed_subtotal": ("pipeline", "million_m3", 2025, 2025),
    "transpetro_oil_pipeline_movement": ("pipeline", "million_m3_at_20C", 2010, 2024),
}


def load_modes(root=DEFAULT_ROOT):
    root = Path(root)
    metadata = json.loads((root / "provenance.json").read_bytes())
    if metadata.get("schema_version") != 1:
        raise ValueError("Unsupported modal snapshot schema")
    record, = metadata["files"]
    if record["path"] != "indicators.csv":
        raise ValueError("Invalid modal snapshot path")
    raw = (root / "indicators.csv").read_bytes()
    if len(raw) > 1024 * 1024 or hashlib.sha256(raw).hexdigest() != record["sha256"]:
        raise ValueError("Modal indicator snapshot integrity mismatch")
    data = pl.read_csv(raw)
    columns = {"mode", "indicator", "year", "value", "unit", "scope", "source_url",
               "source_page", "status"}
    if set(data.columns) != columns or data.is_empty() or any(data.null_count().row(0)):
        raise ValueError("Incomplete modal indicators")
    if set(data["mode"]) != set(MODES) or not data["year"].dtype.is_integer():
        raise ValueError("Invalid mode or year")
    if not data["value"].dtype.is_numeric() or not data["value"].is_finite().all():
        raise ValueError("Invalid modal indicator values")
    if (data["value"] < 0).any() or data.select("mode", "indicator", "year").is_duplicated().any():
        raise ValueError("Negative or duplicate modal indicators")
    if data.filter((pl.col("year") < 2000) | (pl.col("year") > 2025)).height:
        raise ValueError("Unexpected modal reference period")
    if set(data["indicator"]) != set(CONTRACTS):
        raise ValueError("Missing or unknown modal indicator")
    for group in data.partition_by("indicator"):
        if group["unit"].n_unique() != 1 or group["mode"].n_unique() != 1:
            raise ValueError("Mixed units or modes within an indicator")
        mode, unit, start, end = CONTRACTS[group["indicator"][0]]
        if (group["unit"][0] != unit or group["mode"][0] != mode
                or set(group["year"]) != set(range(start, end + 1))):
            raise ValueError("Modal unit, mode or year coverage differs from the reviewed contract")
    return data.sort("mode", "indicator", "year"), metadata
