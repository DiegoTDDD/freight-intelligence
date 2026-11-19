"""Reviewed, explicitly conditioned ANTAQ port pairs; bounded public snapshot."""

import hashlib
import json
import math
from pathlib import Path

import polars as pl

DEFAULT_ROOT = Path(__file__).resolve().parents[1] / "deployment/brazil_water"
SOURCE = ("https://aquarela.antaq.gov.br/single/?appid=56c32604-37bd-4993-9904-1b2c87706808"
          "&sheet=bgvJm&opt=currsel%2Cctxmenu")
CONTRACTS = {
    "santos": {"origin_port": "Santos", "origin_state": "SP", "rows": 30,
               "tonnes": 8790074.053, "displayed_tonnes": 8790074,
               "xlsx_sha256": "cef03c802d32ccf31d3f3ad96aa2c864a0fe418fe817d980f057783bc87edb98",
               "context_sha256": "fdd03ec2bbeeb4488f39a3468f3d54d14a94294d948bfbd20332af9407fd2286"},
    "suape": {"origin_port": "Suape", "origin_state": "PE", "rows": 34,
              "tonnes": 6531260.247, "displayed_tonnes": 6531260,
              "xlsx_sha256": "2d1406ecb9c775ec3e12261964be6e84b2b686f0f55014d80827958352546560",
              "context_sha256": "c6293939e3d2e0872ed9ece47ece0af1997679bb91ac01247e55f339c7ceecc1"},
    "manaus": {"origin_port": "Manaus", "origin_state": "AM", "rows": 13,
               "tonnes": 2687002.543, "displayed_tonnes": 2687003,
               "xlsx_sha256": "c4bc5a1c56dd17d05a2b0c9862d79dd182e42f87fee0247ca7b700ab6316f7f5",
               "context_sha256": "e1d27eacc77f7ab0ddcf0bf2d51ebb812d78cc59c4a340ce692fcbeb822f3bdd"},
}
SCOPE = ("Reported 2025 cabotage transport from three reviewed origins: Santos, Suape and Manaus. "
         "Each destination table was exported with exactly one named origin selected, all months "
         "and no destination/cargo filters. Partial origin coverage, not a national total, unique "
         "consignments or a navigable itinerary. Unlisted pairs are unavailable, not zero.")


def validate(data):
    columns = {"year", "origin_port", "origin_state", "destination_port", "destination_state", "tonnes"}
    if (set(data.columns) != columns or data.height != 77 or any(data.null_count().row(0))
            or set(data["year"]) != {2025}
            or data.select("origin_port", "destination_port", "destination_state").is_duplicated().any()
            or not data["tonnes"].dtype.is_numeric() or not data["tonnes"].is_finite().all()
            or (data["tonnes"] <= 0).any()):
        raise ValueError("Invalid reviewed ANTAQ port-pair coverage or values")
    for contract in CONTRACTS.values():
        rows = data.filter(pl.col("origin_port") == contract["origin_port"])
        if (rows.height != contract["rows"] or set(rows["origin_state"]) != {contract["origin_state"]}
                or not math.isclose(rows["tonnes"].sum(), contract["tonnes"], rel_tol=0, abs_tol=1e-6)
                or round(rows["tonnes"].sum()) != contract["displayed_tonnes"]):
            raise ValueError("ANTAQ port-pair totals do not reconcile to reviewed origin")


def load_port_pairs(root=DEFAULT_ROOT):
    root = Path(root)
    raw = (root / "port_pairs_provenance.json").read_bytes()
    if len(raw) > 65536:
        raise ValueError("Oversized ANTAQ port-pair manifest")
    metadata = json.loads(raw)
    expected = {"port_pairs.csv"}
    for slug in CONTRACTS:
        expected.update({f"port_pairs_{slug}_2025.xlsx", f"port_pairs_{slug}_2025_context.jpg"})
    if (metadata.get("schema_version") != 1 or metadata.get("year") != 2025
            or metadata.get("unit") != "tonnes" or metadata.get("origins") != CONTRACTS
            or metadata.get("filters") != {"year": [2025], "months": "all", "DadosEscala": 1,
                                           "FlagCabotagem": 1, "destination": "unfiltered", "cargo": "unfiltered"}
            or len(metadata["files"]) != len(expected)
            or {r["path"] for r in metadata["files"]} != expected):
        raise ValueError("Invalid ANTAQ port-pair manifest or period context")
    for record in metadata["files"]:
        content = (root / record["path"]).read_bytes()
        digest = hashlib.sha256(content).hexdigest()
        if len(content) > 1024**2 or digest != record["sha256"]:
            raise ValueError("ANTAQ port-pair integrity mismatch")
        for slug, contract in CONTRACTS.items():
            for suffix, field in ((".xlsx", "xlsx_sha256"), ("_context.jpg", "context_sha256")):
                if record["path"] == f"port_pairs_{slug}_2025{suffix}" and digest != contract[field]:
                    raise ValueError("ANTAQ port-pair original evidence differs from reviewed source")
    data = pl.read_csv(root / "port_pairs.csv")
    validate(data)
    return data.sort("origin_port", "tonnes", descending=[False, True]), metadata
