"""Review-pinned 2025 ANTT state pairs, reconciled to independent margins."""

import hashlib
import json
from functools import lru_cache
from pathlib import Path

import polars as pl

from freight_intelligence.brazil_road import DEFAULT_ROOT, STATES
from freight_intelligence.brazil_road_history import source_integer

CONTRACT_SHA256 = "118855f3cefe65afe1fb4874fce21d2332ac1726f33f5b7ef548ce0030377110"
CODES = {*STATES.split("|"), "EX"}


def parse_capture(raw):
    capture = json.loads(raw)
    if (set(capture) != {"year", "origin_margins", "destination_margins", "pairs"}
            or capture["year"] != 2025
            or any(set(capture[key]) != CODES for key in ("origin_margins", "destination_margins", "pairs"))):
        raise ValueError("Changed ANTT year or geographic coverage")
    rows = []
    for origin, destinations in capture["pairs"].items():
        if not destinations or not set(destinations).issubset(CODES):
            raise ValueError("Invalid ANTT destination categories")
        for destination, value in destinations.items():
            rows.append({"year": 2025, "origin_state": origin, "destination_state": destination,
                         "tonnes": source_integer(value), "same_state": origin == destination})
    data = pl.DataFrame(rows).sort("origin_state", "destination_state")
    for field, margins in (("origin_state", "origin_margins"), ("destination_state", "destination_margins")):
        actual = dict(data.group_by(field).agg(pl.col("tonnes").sum()).iter_rows())
        if actual != {code: source_integer(value) for code, value in capture[margins].items()}:
            raise ValueError("ANTT paired observations do not reconcile with independent margins")
    if data.height != 775 or data["tonnes"].sum() != 1368627704:
        raise ValueError("Changed reviewed ANTT population")
    return data


def read_contract(root):
    raw = (Path(root) / "state_od_provenance.json").read_bytes()
    if hashlib.sha256(raw).hexdigest() != CONTRACT_SHA256:
        raise ValueError("Changed ANTT state-pair review contract")
    return json.loads(raw)


def load_state_pairs(root=DEFAULT_ROOT):
    root = Path(root).resolve()
    metadata = read_contract(root)
    signature = tuple((entry["path"], (root / entry["path"]).stat().st_mtime_ns,
                       (root / entry["path"]).stat().st_size) for entry in metadata["files"])
    return _load_pairs(root, signature)


@lru_cache(maxsize=1)
def _load_pairs(root, signature):
    metadata = read_contract(root)
    for entry in metadata["files"]:
        name = entry["path"]
        if Path(name).name != name:
            raise ValueError("Invalid ANTT evidence path")
        raw = (root / name).read_bytes()
        if len(raw) != entry["bytes"] or hashlib.sha256(raw).hexdigest() != entry["sha256"]:
            raise ValueError("Changed ANTT state-pair evidence")
    expected = parse_capture((root / "state_od_capture.json").read_bytes())
    if expected.write_csv().encode() != (root / "state_od.csv").read_bytes():
        raise ValueError("ANTT state-pair table differs from reviewed capture")
    return expected, metadata
