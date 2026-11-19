"""Rebuild ANTAQ cabotage OD offline from all reviewed single-origin exports."""

import hashlib
import json
import math

import openpyxl
import polars as pl

from freight_intelligence.brazil_water_ports import (
    CONTRACT_SHA256,
    DEFAULT_ROOT,
    FILTERS,
    SCOPE,
    SOURCE,
    evidence_files,
    read_contract,
    validate,
)


def read_export(path, headers):
    workbook = openpyxl.load_workbook(path, read_only=True, data_only=True)
    try:
        if workbook.sheetnames != ["Sheet1"]:
            raise ValueError("Unexpected ANTAQ sheets")
        rows = list(workbook.active.values)
    finally:
        workbook.close()
    if rows[0] != headers:
        raise ValueError("Unexpected ANTAQ port-pair source headers")
    return rows[1:]


def prepare(root=DEFAULT_ROOT):
    contract = read_contract(root)
    records, files = [], []
    for name, expected in evidence_files(contract).items():
        raw = (root / name).read_bytes()
        if len(raw) > 1024**2 or hashlib.sha256(raw).hexdigest() != expected:
            raise ValueError("ANTAQ port-pair original evidence differs from reviewed source")
        files.append({"path": name, "bytes": len(raw), "sha256": expected})
    for slug, origin in contract["origins"].items():
        rows = read_export(root / f"port_pairs_{slug}_2025.xlsx",
                           ("UF de Destino", "Instalação de Destino", "Quantidade Transportada"))
        for state, port, tonnes in rows:
            records.append({"year": 2025, "origin_port": origin["origin_port"],
                            "origin_state": origin["origin_state"], "destination_port": port,
                            "destination_state": state, "tonnes": tonnes})
    # Independent unfiltered exports establish complete origin and destination populations.
    for direction in ("origins", "destinations"):
        word = "Origem" if direction == "origins" else "Destino"
        rows = read_export(root / contract["catalogues"][direction]["xlsx"],
                           (f"UF de {word}", f"Instalação de {word}", "Quantidade Transportada"))
        expected = ({(o["origin_state"], o["origin_port"]): o["tonnes"] for o in contract["origins"].values()}
                    if direction == "origins" else
                    {(o["destination_state"], o["destination_port"]): o["tonnes"] for o in contract["destinations"]})
        if len(rows) != len(expected) or {(state, port) for state, port, _ in rows} != set(expected):
            raise ValueError("ANTAQ full-population catalogue coverage differs")
        if any(not math.isclose(tonnes, expected[state, port], rel_tol=0, abs_tol=1e-6)
               for state, port, tonnes in rows):
            raise ValueError("ANTAQ full-population catalogue totals differ")
    data = pl.DataFrame(records).sort("origin_port", "destination_state", "destination_port")
    validate(data, contract)
    raw = data.write_csv().encode()
    if hashlib.sha256(raw).hexdigest() != contract["csv_sha256"]:
        raise ValueError("ANTAQ OD reconstruction differs from reviewed values")
    files.extend([{"path": "port_pairs.csv", "bytes": len(raw), "sha256": contract["csv_sha256"]},
                  {"path": "port_pairs_contract.json", "bytes": (root / "port_pairs_contract.json").stat().st_size,
                   "sha256": CONTRACT_SHA256}])
    metadata = {"schema_version": 1, "year": 2025, "unit": "tonnes", "scope": SCOPE,
                "source": SOURCE, "source_table": "GR4.2 - Porto/UF Destino", "reviewed_on": "2026-11-19",
                "panel_updated_at": "2026-04-01 08:17", "origins": contract["origins"], "filters": FILTERS,
                "origin_count": 98, "destination_count": 71, "pair_count": 510,
                "population_tonnes": contract["population_tonnes"],
                "displayed_population_tonnes": contract["displayed_population_tonnes"],
                "method": "All 98 single-origin destination exports, independently reconciled to unfiltered origin and destination catalogues; never inferred from marginals",
                "precision": "Unrounded numeric XLSX values retained; every origin and destination reconciles within 0.000001 t; grand sum rounds to the displayed whole-tonne total",
                "files": files}
    (root / "port_pairs.csv").write_bytes(raw)
    (root / "port_pairs_provenance.json").write_bytes((json.dumps(metadata, indent=2) + "\n").encode())
    return data


if __name__ == "__main__":
    print(f"Prepared {prepare().height} reviewed ANTAQ cabotage OD pairs")
