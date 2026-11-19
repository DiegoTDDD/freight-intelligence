"""Rebuild port pairs offline from reviewed original ANTAQ destination exports."""

import hashlib
import json

import openpyxl
import polars as pl

from freight_intelligence.brazil_water_ports import CONTRACTS, DEFAULT_ROOT, SCOPE, SOURCE, validate


def prepare(root=DEFAULT_ROOT):
    records = []
    files = []
    for slug, contract in CONTRACTS.items():
        for suffix, field in ((".xlsx", "xlsx_sha256"), ("_context.jpg", "context_sha256")):
            path = root / f"port_pairs_{slug}_2025{suffix}"
            raw = path.read_bytes()
            if len(raw) > 1024**2 or hashlib.sha256(raw).hexdigest() != contract[field]:
                raise ValueError("ANTAQ port-pair original evidence differs from reviewed source")
            files.append({"path": path.name, "bytes": len(raw), "sha256": contract[field]})
        workbook = openpyxl.load_workbook(root / f"port_pairs_{slug}_2025.xlsx", read_only=True, data_only=True)
        try:
            if workbook.sheetnames != ["Sheet1"]:
                raise ValueError("Unexpected ANTAQ sheets")
            rows = list(workbook.active.values)
        finally:
            workbook.close()
        if rows[0] != ("UF de Destino", "Instalação de Destino", "Quantidade Transportada"):
            raise ValueError("Unexpected ANTAQ port-pair source headers")
        for state, port, tonnes in rows[1:]:
            records.append({"year": 2025, "origin_port": contract["origin_port"],
                            "origin_state": contract["origin_state"], "destination_port": port,
                            "destination_state": state, "tonnes": tonnes})
    data = pl.DataFrame(records).sort("origin_port", "destination_state", "destination_port")
    validate(data)
    raw = data.write_csv().encode()
    files.append({"path": "port_pairs.csv", "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()})
    metadata = {"schema_version": 1, "year": 2025, "unit": "tonnes", "scope": SCOPE,
                "source": SOURCE, "source_table": "GR4.2 - Porto/UF Destino", "reviewed_on": "2026-11-19",
                "panel_updated_at": "2026-04-01 08:17", "origins": CONTRACTS,
                "filters": {"year": [2025], "months": "all", "DadosEscala": 1,
                            "FlagCabotagem": 1, "destination": "unfiltered", "cargo": "unfiltered"},
                "method": "Separate original destination exports conditioned on each single origin; never inferred from marginal totals",
                "precision": "Unrounded numeric XLSX values retained; each origin sum rounds to the displayed whole-tonne total",
                "files": files}
    (root / "port_pairs.csv").write_bytes(raw)
    (root / "port_pairs_provenance.json").write_bytes((json.dumps(metadata, indent=2) + "\n").encode())
    return data


if __name__ == "__main__":
    print(f"Prepared {prepare().height} reviewed ANTAQ port pairs")
