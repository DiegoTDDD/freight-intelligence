"""Reviewed ANTAQ cabotage OD snapshot, reconciled in both directions."""

import hashlib
import json
import math
from functools import lru_cache
from pathlib import Path

import polars as pl

DEFAULT_ROOT = Path(__file__).resolve().parents[1] / "deployment/brazil_water"
CONTRACT_SHA256 = "651e3243d40e2033adb319e5dbca019eeb84f2fc56810c9be0ff8a6e9278d707"
SOURCE = ("https://aquarela.antaq.gov.br/single/?appid=56c32604-37bd-4993-9904-1b2c87706808"
          "&sheet=bgvJm&opt=currsel%2Cctxmenu")
FILTERS = {"year": [2025], "months": "all", "DadosEscala": 1,
           "FlagCabotagem": 1, "destination": "unfiltered", "cargo": "unfiltered"}
SCOPE = ("Reported 2025 cabotage transport: all 98 origins and 71 destinations in the reviewed "
         "ANTAQ table, with 510 observed links. Includes ports, terminals, offshore and "
         "undetermined source categories. Reconciles the reviewed panel population, not every "
         "Brazilian water mode, unique national consignments or navigable itineraries. "
         "Unlisted pairs are unavailable, not fabricated zeros.")


def read_contract(root=DEFAULT_ROOT):
    raw = (Path(root) / "port_pairs_contract.json").read_bytes()
    if len(raw) > 128 * 1024 or hashlib.sha256(raw).hexdigest() != CONTRACT_SHA256:
        raise ValueError("ANTAQ port-pair reviewed contract integrity mismatch")
    return json.loads(raw)


def evidence_files(contract):
    expected = {}
    for slug, origin in contract["origins"].items():
        expected[f"port_pairs_{slug}_2025.xlsx"] = origin["xlsx_sha256"]
        expected[f"port_pairs_{slug}_2025_context.jpg"] = origin["context_sha256"]
    for catalogue in contract["catalogues"].values():
        expected[catalogue["xlsx"]] = catalogue["xlsx_sha256"]
        expected[catalogue["context"]] = catalogue["context_sha256"]
    return expected


def validate(data, contract):
    columns = {"year", "origin_port", "origin_state", "destination_port", "destination_state", "tonnes"}
    if (set(data.columns) != columns or data.height != contract["pair_count"]
            or any(data.null_count().row(0)) or set(data["year"]) != {2025}
            or data.select("origin_port", "destination_port", "destination_state").is_duplicated().any()
            or not data["tonnes"].dtype.is_numeric() or not data["tonnes"].is_finite().all()
            or (data["tonnes"] <= 0).any()):
        raise ValueError("Invalid reviewed ANTAQ port-pair coverage or values")
    for origin in contract["origins"].values():
        rows = data.filter(pl.col("origin_port") == origin["origin_port"])
        if (rows.height != origin["rows"] or set(rows["origin_state"]) != {origin["origin_state"]}
                or not math.isclose(rows["tonnes"].sum(), origin["tonnes"], rel_tol=0, abs_tol=1e-6)
                or round(rows["tonnes"].sum()) != origin["displayed_tonnes"]):
            raise ValueError("ANTAQ port-pair totals do not reconcile to reviewed origin")
    destinations = data.group_by("destination_state", "destination_port").agg(pl.col("tonnes").sum())
    if destinations.height != contract["destination_count"]:
        raise ValueError("ANTAQ destination coverage mismatch")
    for destination in contract["destinations"]:
        rows = destinations.filter((pl.col("destination_state") == destination["destination_state"])
                                   & (pl.col("destination_port") == destination["destination_port"]))
        if rows.height != 1 or not math.isclose(rows["tonnes"][0], destination["tonnes"], rel_tol=0, abs_tol=1e-6):
            raise ValueError("ANTAQ port-pair totals do not reconcile to reviewed destination")
    if (not math.isclose(data["tonnes"].sum(), contract["population_tonnes"], rel_tol=0, abs_tol=1e-6)
            or round(data["tonnes"].sum()) != contract["displayed_population_tonnes"]):
        raise ValueError("ANTAQ cabotage population reconciliation mismatch")


def load_port_pairs(root=DEFAULT_ROOT):
    root = Path(root).resolve()
    signature = tuple((p.name, p.stat().st_mtime_ns, p.stat().st_size)
                      for p in sorted(root.glob("port_pairs*")) if p.is_file())
    return _load_port_pairs(root, signature)


@lru_cache(maxsize=1)
def _load_port_pairs(root, signature):
    # Shared read-only bundle; all original evidence participates in invalidation.
    contract = read_contract(root)
    raw = (root / "port_pairs_provenance.json").read_bytes()
    if len(raw) > 256 * 1024:
        raise ValueError("Oversized ANTAQ port-pair manifest")
    metadata = json.loads(raw)
    expected = {**evidence_files(contract), "port_pairs.csv": contract["csv_sha256"],
                "port_pairs_contract.json": CONTRACT_SHA256}
    if (metadata.get("schema_version") != 1 or metadata.get("year") != 2025
            or metadata.get("unit") != "tonnes" or metadata.get("origins") != contract["origins"]
            or metadata.get("scope") != SCOPE or metadata.get("source") != SOURCE
            or any(metadata.get(name) != contract[name]
                   for name in ("pair_count", "origin_count", "destination_count", "population_tonnes"))
            or metadata.get("filters") != FILTERS
            or len(metadata["files"]) != len(expected)
            or {r["path"] for r in metadata["files"]} != set(expected)):
        raise ValueError("Invalid ANTAQ port-pair manifest or period context")
    for record in metadata["files"]:
        path = root / record["path"]
        if path.stat().st_size > 1024**2:
            raise ValueError("Oversized ANTAQ port-pair evidence")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != record["sha256"] or digest != expected[record["path"]]:
            raise ValueError("ANTAQ port-pair integrity mismatch")
    data = pl.read_csv(root / "port_pairs.csv")
    validate(data, contract)
    return data.sort("origin_port", "tonnes", descending=[False, True]), metadata
